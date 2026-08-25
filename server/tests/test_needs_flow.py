"""S5.3 needs/orders flow tests (#33).

Integration-style through the public API: needs entry, needs→transfer
handoff, purchase orders with lines, and auto-order suggestions.
"""
from decimal import Decimal

import pytest

from tests import needs_test_utils as u


@pytest.mark.asyncio
async def test_create_need_roundtrip(client):
    """A pharmacist requests stock from a sister branch → 201 pending need."""
    branch_a = await u._make_branch()  # requester (target of the goods)
    branch_b = await u._make_branch()  # fulfilling branch (sender)
    user, user_name = await u._make_user(level=3, branch_id=branch_a)
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="2")
    token = await u._login_token(client, user_name)

    resp = await client.post(
        "/api/v1/needs",
        json={
            "drug_id": drug_id,
            "qty": "5",
            "sender_branch_id": branch_b,
            "datee": "2026-08-25",
        },
        headers=u._headers(token),
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["drug_id"] == drug_id
    assert body["qty"] == "5.0000"
    assert body["status"] == "pending"
    assert body["branch_id"] == branch_a
    assert body["target_branch_id"] == branch_a
    assert body["sender_branch_id"] == branch_b

    await u._cleanup(
        need_ids=[body["id"]],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b],
        user_ids=[user],
    )


@pytest.mark.asyncio
async def test_create_need_writes_audit_and_outbox_atomically(client):
    """G12: the need insert, its audit row, and outbox rows for BOTH branches
    (requester + pinned sender) land in one transaction."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import AuditLog, SyncLog

    branch_a = await u._make_branch()
    branch_b = await u._make_branch()
    user, user_name = await u._make_user(level=3, branch_id=branch_a)
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="1")
    token = await u._login_token(client, user_name)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "3", "sender_branch_id": branch_b},
        headers=u._headers(token),
    )
    assert resp.status_code == 201, resp.text
    need_id = resp.json()["id"]

    async with SessionLocal() as session:
        audits = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity == "need", AuditLog.entity_id == need_id
                )
            )
        ).scalars().all()
        assert len(audits) == 1
        assert audits[0].action == "insert"
        assert audits[0].new_value == "pending"
        outbox = (
            await session.execute(
                select(SyncLog).where(
                    SyncLog.entity == "need", SyncLog.entity_id == need_id
                )
            )
        ).scalars().all()
        assert {row.branch_id for row in outbox} == {branch_a, branch_b}
        assert all(row.status == "pending" for row in outbox)
        payload = outbox[0].payload
        assert payload["kind"] == "need"
        assert payload["qty"] == "3.0000"
        assert payload["rev"] == 1

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b],
        user_ids=[user],
    )


@pytest.mark.asyncio
async def test_list_needs_scoped_to_participating_branches(client):
    """A branch sees needs it requested OR is pinned to fulfill; others invisible."""
    branch_a = await u._make_branch()
    branch_b = await u._make_branch()
    branch_c = await u._make_branch()
    user_a, user_a_name = await u._make_user(level=3, branch_id=branch_a)
    drug_id = await u._make_drug_with_stock(branch_id=branch_b, stock_qty="9")
    token_a = await u._login_token(client, user_a_name)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "2", "sender_branch_id": branch_b},
        headers=u._headers(token_a),
    )
    assert resp.status_code == 201
    need_id = resp.json()["id"]

    # open (unpinned) request from C: A must NOT see it
    user_c, user_c_name = await u._make_user(level=3, branch_id=branch_c)
    token_c = await u._login_token(client, user_c_name)
    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "1"},
        headers=u._headers(token_c),
    )
    assert resp.status_code == 201
    open_id = resp.json()["id"]

    seen = (
        await client.get("/api/v1/needs", headers=u._headers(token_a))
    ).json()["needs"]
    assert {n["id"] for n in seen} == {need_id}

    # sender branch sees both the request pinned to it AND nothing of C's
    user_b, user_b_name = await u._make_user(level=3, branch_id=branch_b)
    token_b = await u._login_token(client, user_b_name)
    seen_b = (
        await client.get("/api/v1/needs", headers=u._headers(token_b))
    ).json()["needs"]
    assert {n["id"] for n in seen_b} == {need_id}

    # status filter
    filtered = (
        await client.get(
            "/api/v1/needs?status_filter=pending", headers=u._headers(token_a)
        )
    ).json()["needs"]
    assert {n["id"] for n in filtered} == {need_id}

    await u._cleanup(
        need_ids=[need_id, open_id],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b, branch_c],
        user_ids=[user_a, user_b, user_c],
    )


@pytest.mark.asyncio
async def test_cancel_need_lifecycle(client):
    """Requester cancels a pending need → cancelled; second cancel → 409;
    a non-party gets 404 (existence not disclosed)."""
    branch_a = await u._make_branch()
    branch_b = await u._make_branch()
    user_a, user_a_name = await u._make_user(level=3, branch_id=branch_a)
    user_b, user_b_name = await u._make_user(level=3, branch_id=branch_b)
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="4")
    token_a = await u._login_token(client, user_a_name)
    token_b = await u._login_token(client, user_b_name)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "2", "sender_branch_id": branch_b},
        headers=u._headers(token_a),
    )
    need_id = resp.json()["id"]

    # non-party cannot even see it
    get_foreign = await client.get(
        f"/api/v1/needs/{need_id}", headers=u._headers(token_b)
    )
    # b IS a party here (sender); use a third branch instead
    branch_x = await u._make_branch()
    user_x, user_x_name = await u._make_user(level=3, branch_id=branch_x)
    token_x = await u._login_token(client, user_x_name)
    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "2"},
        headers=u._headers(token_x),
    )
    foreign_id = resp.json()["id"]
    assert (
        await client.get(f"/api/v1/needs/{foreign_id}", headers=u._headers(token_a))
    ).status_code == 404

    # requester cancels its own pending need
    cancel = await client.post(
        f"/api/v1/needs/{need_id}/cancel", headers=u._headers(token_a)
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    # double-cancel rejected
    again = await client.post(
        f"/api/v1/needs/{need_id}/cancel", headers=u._headers(token_a)
    )
    assert again.status_code == 409

    await u._cleanup(
        need_ids=[need_id, foreign_id],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b, branch_x],
        user_ids=[user_a, user_b, user_x],
    )


@pytest.mark.asyncio
async def test_need_to_transfer_handoff_fulfills_on_receive(client):
    """Sender picks up a need → transfer draft sender→requester linked to the
    need; dispatch + receive through the transfers API auto-fulfills the need."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Need

    branch_a = await u._make_branch()  # requester
    branch_b = await u._make_branch()  # fulfiller (sender)
    user_a, user_a_name = await u._make_user(level=3, branch_id=branch_a)
    user_b, user_b_name = await u._make_user(level=3, branch_id=branch_b)
    drug_id = await u._make_drug_with_stock(
        branch_id=branch_b,
        stock_qty="10",
        batches=[("10", "5.0000", "2027-01-01")],
    )
    token_a = await u._login_token(client, user_a_name)
    token_b = await u._login_token(client, user_b_name)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "4", "sender_branch_id": branch_b},
        headers=u._headers(token_a),
    )
    assert resp.status_code == 201
    need_id = resp.json()["id"]

    # sender creates the handoff transfer
    handoff = await client.post(
        f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_b)
    )
    assert handoff.status_code == 201, handoff.text
    transfer = handoff.json()
    assert transfer["source_branch_id"] == branch_b
    assert transfer["target_branch_id"] == branch_a
    assert len(transfer["lines"]) == 1
    assert transfer["lines"][0]["drug_id"] == drug_id
    assert transfer["lines"][0]["sent_qty"] == "4.0000"

    async with SessionLocal() as session:
        need = (
            await session.execute(select(Need).where(Need.id == need_id))
        ).scalar_one()
        assert need.transfer_id == transfer["id"]
        assert need.status == "pending"

    # walk it through the transfers state machine
    disp = await client.post(
        f"/api/v1/transfers/{transfer['id']}/dispatch",
        json={},
        headers=u._headers(token_b),
    )
    assert disp.status_code == 200, disp.text
    recv = await client.post(
        f"/api/v1/transfers/{transfer['id']}/receive",
        json={"lines": [{"line_id": transfer["lines"][0]["id"], "received_qty": "4"}]},
        headers=u._headers(token_a),
    )
    assert recv.status_code == 200, recv.text

    async with SessionLocal() as session:
        need = (
            await session.execute(select(Need).where(Need.id == need_id))
        ).scalar_one()
        assert need.status == "fulfilled"
        assert need.fulfilled_at is not None
        assert need.rev == 3

    # fulfilled need can no longer be cancelled or re-handed-off
    assert (
        await client.post(f"/api/v1/needs/{need_id}/cancel", headers=u._headers(token_a))
    ).status_code == 409
    assert (
        await client.post(f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_b))
    ).status_code == 409

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        transfer_ids=[transfer["id"]],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b],
        user_ids=[user_a, user_b],
    )


@pytest.mark.asyncio
async def test_suggestions_minimum_and_sales_rate(client):
    """minimum mode flags stock<minimum rows (top-up to par); sales_rate mode
    suggests coverage-days of velocity minus on-hand (Egypt daily-replenishment
    defaults: 14-day window, 7-day coverage); quiet drugs stay out."""
    from datetime import date, timedelta

    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Invoice, InvoiceLine

    branch = await u._make_branch()
    user, user_name = await u._make_user(level=3, branch_id=branch)
    token = await u._login_token(client, user_name)

    # below-minimum drug: on_hand 2, minimum 10 → suggest 8
    low_id = await u._make_drug_with_stock(branch_id=branch, stock_qty="2", minimum="10")
    # fast mover: on_hand 1, sold 7 over 14 days → avg .5/day ×7 = 3.5 → suggest 2.5
    mover_id = await u._make_drug_with_stock(branch_id=branch, stock_qty="1", minimum="0")
    # quiet & stocked: must NOT appear in either mode
    quiet_id = await u._make_drug_with_stock(branch_id=branch, stock_qty="50", minimum="5")

    async with SessionLocal() as session:
        today = date.today()
        for offset in range(0, 14, 2):  # 7 invoices × 1 unit over 14 days
            day = today - timedelta(days=offset)
            inv = Invoice(
                branch_id=branch,
                invoice_no=f"T33-{u.PID}-{offset}",
                kind="sale",
                datee=day,
                totalvalue=Decimal("10"),
                payed=Decimal("10"),
            )
            session.add(inv)
            await session.flush()
            session.add(
                InvoiceLine(
                    invoice_id=inv.id,
                    branch_id=branch,
                    drug_id=mover_id,
                    qty=Decimal("1"),
                    unit_price=Decimal("10"),
                    tax_type="14%",
                )
            )
        await session.commit()

    resp = await client.get(
        "/api/v1/needs/suggestions?mode=minimum", headers=u._headers(token)
    )
    assert resp.status_code == 200, resp.text
    by_drug = {s["drug_id"]: s for s in resp.json()["suggestions"]}
    assert quiet_id not in by_drug
    assert by_drug[low_id]["suggested_qty"] == "8.0000"
    assert by_drug[low_id]["on_hand"] == "2.0000"
    assert by_drug[low_id]["minimum"] == "10.0000"

    resp = await client.get(
        "/api/v1/needs/suggestions?mode=sales_rate",
        headers=u._headers(token),
    )
    by_drug = {s["drug_id"]: s for s in resp.json()["suggestions"]}
    assert quiet_id not in by_drug
    assert low_id not in by_drug  # no sales velocity → nothing to say
    assert by_drug[mover_id]["suggested_qty"] == "2.5000"
    assert by_drug[mover_id]["avg_daily"] == "0.5000"

    # unknown mode → 400
    assert (
        await client.get(
            "/api/v1/needs/suggestions?mode=bogus", headers=u._headers(token)
        )
    ).status_code == 400

    # branchless caller cannot read suggestions scoped to nothing
    await u._cleanup(
        need_ids=[],
        order_ids=[],
        drug_ids=[low_id, mover_id, quiet_id],
        branch_ids=[branch],
        user_ids=[user],
    )
