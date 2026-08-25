"""S5.3 purchase-order flow tests (#33).

POs are itemized distributor orders (Egypt market): header + lines, legacy
`orders` status semantics (NULL=pending → 'pending', 'saved'=done). No GL /
stock mutation until the purchases receipt links up (N5) — `received` stays
unreachable in this slice.
"""
import pytest

from tests import needs_test_utils as u


async def _setup(level: int = 3):
    branch = await u._make_branch()
    user, username = await u._make_user(level=level, branch_id=branch)
    drug_a = await u._make_drug_with_stock(branch_id=branch)
    drug_b = await u._make_drug_with_stock(branch_id=branch)
    return branch, user, username, drug_a, drug_b


@pytest.mark.asyncio
async def test_create_po_with_lines_roundtrip(client):
    """Pending PO echoes header + 4-dp lines; audit+outbox land atomically."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import AuditLog, SyncLog

    branch, user, username, drug_a, drug_b = await _setup()
    token = await u._login_token(client, username)

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={
            "orderid": "ORD-1",
            "orderdate": "2026-08-25",
            "lines": [
                {"drug_id": drug_a, "qty": "10", "unit_cost": "5.5"},
                {"drug_id": drug_b, "qty": "2.5"},
            ],
        },
        headers=u._headers(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["branch_id"] == branch
    assert body["orderid"] == "ORD-1"
    assert len(body["lines"]) == 2
    by_drug = {line["drug_id"]: line for line in body["lines"]}
    assert by_drug[drug_a]["qty"] == "10.0000"
    assert by_drug[drug_a]["unit_cost"] == "5.5000"
    assert by_drug[drug_b]["unit_cost"] is None

    po_id = body["id"]
    async with SessionLocal() as session:
        audits = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity == "purchase_order", AuditLog.entity_id == po_id
                )
            )
        ).scalars().all()
        assert len(audits) == 1 and audits[0].action == "insert"
        outbox = (
            await session.execute(
                select(SyncLog).where(
                    SyncLog.entity == "purchase_order", SyncLog.entity_id == po_id
                )
            )
        ).scalars().all()
        assert {row.branch_id for row in outbox} == {branch}
        assert outbox[0].payload["rev"] == 1
        assert len(outbox[0].payload["lines"]) == 2

    # duplicate drug lines rejected
    resp = await client.post(
        "/api/v1/purchase-orders",
        json={
            "lines": [
                {"drug_id": drug_a, "qty": "1"},
                {"drug_id": drug_a, "qty": "2"},
            ]
        },
        headers=u._headers(token),
    )
    assert resp.status_code == 400

    # unknown drug rejected
    resp = await client.post(
        "/api/v1/purchase-orders",
        json={"lines": [{"drug_id": 99999999, "qty": "1"}]},
        headers=u._headers(token),
    )
    assert resp.status_code == 400

    await u._cleanup(
        need_ids=[],
        order_ids=[po_id],
        drug_ids=[drug_a, drug_b],
        branch_ids=[branch],
        user_ids=[user],
    )


@pytest.mark.asyncio
async def test_po_save_and_cancel_lifecycle(client):
    """pending → saved (legacy 'saved'=done); saved → cancelled; terminal
    states reject further transitions."""
    branch, user, username, drug_a, drug_b = await _setup()
    token = await u._login_token(client, username)

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={"lines": [{"drug_id": drug_a, "qty": "3"}]},
        headers=u._headers(token),
    )
    po_id = resp.json()["id"]

    saved = await client.post(f"/api/v1/purchase-orders/{po_id}/save", headers=u._headers(token))
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "saved"

    again = await client.post(f"/api/v1/purchase-orders/{po_id}/save", headers=u._headers(token))
    assert again.status_code == 409

    cancelled = await client.post(
        f"/api/v1/purchase-orders/{po_id}/cancel", headers=u._headers(token)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    assert (
        await client.post(
            f"/api/v1/purchase-orders/{po_id}/cancel", headers=u._headers(token)
        )
    ).status_code == 409

    await u._cleanup(
        need_ids=[],
        order_ids=[po_id],
        drug_ids=[drug_a, drug_b],
        branch_ids=[branch],
        user_ids=[user],
    )


@pytest.mark.asyncio
async def test_po_scoping_and_rbac_walls(client):
    """Foreign branches get 404; cashier-level (2) writes 403; unauth 401."""
    branch, user, username, drug_a, drug_b = await _setup()
    other = await u._make_branch()
    other_user, other_user_name = await u._make_user(level=3, branch_id=other)
    token = await u._login_token(client, username)
    other_token = await u._login_token(client, other_user_name)

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={"lines": [{"drug_id": drug_a, "qty": "3"}]},
        headers=u._headers(token),
    )
    po_id = resp.json()["id"]

    assert (
        await client.get(f"/api/v1/purchase-orders/{po_id}", headers=u._headers(other_token))
    ).status_code == 404
    mine = await client.get("/api/v1/purchase-orders", headers=u._headers(token))
    assert {row["id"] for row in mine.json()["purchase_orders"]} == {po_id}
    theirs = await client.get(
        "/api/v1/purchase-orders", headers=u._headers(other_token)
    )
    assert theirs.json()["purchase_orders"] == []

    # level-2 (below the needs.manage floor of 3) cannot write
    cashier_branch = await u._make_branch()
    cashier, cashier_name = await u._make_user(level=2, branch_id=cashier_branch)
    cashier_token = await u._login_token(client, cashier_name)
    forbidden = await client.post(
        "/api/v1/purchase-orders",
        json={"lines": [{"drug_id": drug_a, "qty": "1"}]},
        headers=u._headers(cashier_token),
    )
    assert forbidden.status_code == 403

    unauth = await client.post(
        "/api/v1/purchase-orders", json={"lines": [{"drug_id": drug_a, "qty": "1"}]}
    )
    assert unauth.status_code == 401

    await u._cleanup(
        need_ids=[],
        order_ids=[po_id],
        drug_ids=[drug_a, drug_b],
        branch_ids=[branch, other, cashier_branch],
        user_ids=[user, other_user, cashier],
    )
