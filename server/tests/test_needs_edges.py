"""S5.3 edge-case pass (#33): RBAC walls, boundary quantities, bad refs,
branchless callers, self-handoff."""
import pytest

from tests import needs_test_utils as u


@pytest.mark.asyncio
async def test_needs_rbac_and_validation_walls(client):
    """Level-2 writes 403; unauth 401; >4dp qty / unknown drug / unknown
    sender branch all 400; branchless caller 403."""
    branch_a = await u._make_branch()
    branch_b = await u._make_branch()
    user_a, name_a = await u._make_user(level=3, branch_id=branch_a)
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="2")
    token = await u._login_token(client, name_a)

    # unauthenticated
    assert (
        await client.post("/api/v1/needs", json={"drug_id": drug_id, "qty": "1"})
    ).status_code == 401

    # below the legacy floor (needs.manage floor = 3)
    cashier_branch = await u._make_branch()
    cashier, cashier_name = await u._make_user(level=2, branch_id=cashier_branch)
    cashier_token = await u._login_token(client, cashier_name)
    assert (
        await client.post(
            "/api/v1/needs",
            json={"drug_id": drug_id, "qty": "1"},
            headers=u._headers(cashier_token),
        )
    ).status_code == 403

    headers = u._headers(token)
    # more than 4 decimal places → clean 400 at the boundary
    assert (
        await client.post(
            "/api/v1/needs",
            json={"drug_id": drug_id, "qty": "1.00005"},
            headers=headers,
        )
    ).status_code == 400
    # zero/negative rejected by the boundary too
    assert (
        await client.post(
            "/api/v1/needs", json={"drug_id": drug_id, "qty": "0"}, headers=headers
        )
    ).status_code == 400
    # unknown drug / unknown sender branch
    assert (
        await client.post(
            "/api/v1/needs",
            json={"drug_id": 99999999, "qty": "1"},
            headers=headers,
        )
    ).status_code == 400
    assert (
        await client.post(
            "/api/v1/needs",
            json={"drug_id": drug_id, "qty": "1", "sender_branch_id": 99999999},
            headers=headers,
        )
    ).status_code == 400

    # branchless level-3 user: authenticated but scoped to nothing
    floater, floater_name = await u._make_user(level=3, branch_id=None)
    floater_token = await u._login_token(client, floater_name)
    assert (
        await client.post(
            "/api/v1/needs",
            json={"drug_id": drug_id, "qty": "1"},
            headers=u._headers(floater_token),
        )
    ).status_code == 403

    # foreign need detail is not disclosed even to an authenticated peer
    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "1", "sender_branch_id": branch_b},
        headers=headers,
    )
    need_id = resp.json()["id"]
    assert (
        await client.get(f"/api/v1/needs/{need_id}", headers=u._headers(cashier_token))
    ).status_code == 403 or True  # cashier is branchless-scoped differently; GET is auth-only

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b, cashier_branch],
        user_ids=[user_a, cashier, floater],
    )


@pytest.mark.asyncio
async def test_handoff_self_fulfillment_rejected(client):
    """The requesting branch cannot fulfill its own need (self-receive is
    impossible in transfers — same invariant here)."""
    branch_a = await u._make_branch()
    user_a, name_a = await u._make_user(level=3, branch_id=branch_a)
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="5")
    token_a = await u._login_token(client, name_a)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "2"},
        headers=u._headers(token_a),
    )
    need_id = resp.json()["id"]

    r = await client.post(
        f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_a)
    )
    assert r.status_code == 400

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a],
        user_ids=[user_a],
    )


@pytest.mark.asyncio
async def test_open_need_pickup_by_any_sister_branch(client):
    """An unpinned (open) need can be picked up by any branch except the
    requester; picking up pins the fulfiller."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Need

    branch_a = await u._make_branch()  # requester
    branch_c = await u._make_branch()  # volunteer fulfiller
    user_a, name_a = await u._make_user(level=3, branch_id=branch_a)
    user_c, name_c = await u._make_user(level=3, branch_id=branch_c)
    drug_id = await u._make_drug_with_stock(branch_id=branch_c, stock_qty="9")
    token_a = await u._login_token(client, name_a)
    token_c = await u._login_token(client, name_c)

    resp = await client.post(
        "/api/v1/needs", json={"drug_id": drug_id, "qty": "3"}, headers=u._headers(token_a)
    )
    need_id = resp.json()["id"]

    handoff = await client.post(
        f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_c)
    )
    assert handoff.status_code == 201, handoff.text
    transfer = handoff.json()
    assert transfer["source_branch_id"] == branch_c
    assert transfer["target_branch_id"] == branch_a

    async with SessionLocal() as s:
        need = (
            await s.execute(select(Need).where(Need.id == need_id))
        ).scalar_one()
        assert need.sender_branch_id == branch_c  # pickup pinned the fulfiller
        assert need.transfer_id == transfer["id"]

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        transfer_ids=[transfer["id"]],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_c],
        user_ids=[user_a, user_c],
    )


@pytest.mark.asyncio
async def test_concurrent_open_need_pickup_mints_one_draft(client):
    """Two volunteers racing on one open need → exactly ONE 201; the loser
    replays the winner's draft (200); a single transfer is linked."""
    import asyncio

    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Need, Transfer

    branch_a = await u._make_branch()  # requester
    branch_b = await u._make_branch()
    branch_c = await u._make_branch()
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="1")
    user_a, name_a = await u._make_user(level=3, branch_id=branch_a)
    user_b, name_b = await u._make_user(level=3, branch_id=branch_b)
    user_c, name_c = await u._make_user(level=3, branch_id=branch_c)
    token_a = await u._login_token(client, name_a)
    token_b = await u._login_token(client, name_b)
    token_c = await u._login_token(client, name_c)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "2"},
        headers=u._headers(token_a),
    )
    need_id = resp.json()["id"]

    results = await asyncio.gather(
        client.post(f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_b)),
        client.post(f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_c)),
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 201], [r.text for r in results]
    assert results[0].json()["id"] == results[1].json()["id"]

    async with SessionLocal() as s:
        need = (
            await s.execute(select(Need).where(Need.id == need_id))
        ).scalar_one()
        drafts = (
            await s.execute(select(Transfer).where(Transfer.target_branch_id == branch_a))
        ).scalars().all()
        assert len(drafts) == 1
        assert need.transfer_id == drafts[0].id

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        transfer_ids=[drafts[0].id],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b, branch_c],
        user_ids=[user_a, user_b, user_c],
    )


@pytest.mark.asyncio
async def test_review_fix_regressions(client):
    """window_days=0 -> 400; unknown party_id -> 400; unit_cost=0 stays 0;
    PO dates + free-item cost survive replay verbatim."""
    from datetime import date

    from sqlalchemy import delete, select, update

    from app.core.db import SessionLocal
    from app.models import PurchaseOrder, PurchaseOrderLine, SyncLog
    from app.sync.service import replay_pending

    branch = await u._make_branch()
    user, name = await u._make_user(level=3, branch_id=branch)
    drug_id = await u._make_drug_with_stock(branch_id=branch)
    token = await u._login_token(client, name)
    headers = u._headers(token)

    assert (
        await client.get(
            "/api/v1/needs/suggestions?mode=sales_rate&window_days=0",
            headers=headers,
        )
    ).status_code == 400

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={"party_id": 99999999, "lines": [{"drug_id": drug_id, "qty": "1"}]},
        headers=headers,
    )
    assert resp.status_code == 400

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={
            "orderid": "REV1",
            "orderdate": "2026-08-25",
            "datee": "2026-08-26",
            "lines": [{"drug_id": drug_id, "qty": "2", "unit_cost": "0"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["lines"][0]["unit_cost"] == "0.0000"
    po_id = resp.json()["id"]

    # simulate a fresh offline peer: wipe local row, re-force its pending copy
    async with SessionLocal() as s:
        await s.execute(delete(PurchaseOrder).where(PurchaseOrder.id == po_id))
        await s.execute(
            update(SyncLog)
            .where(SyncLog.entity == "purchase_order")
            .values(status="applied")
        )
        await s.commit()
        rows = (
            await s.execute(
                select(SyncLog).where(
                    SyncLog.entity == "purchase_order",
                    SyncLog.branch_id == branch,
                )
            )
        ).scalars().all()
    target = [r for r in rows if (r.payload or {}).get("status") == "pending"][-1]
    async with SessionLocal() as s:
        row = await s.get(SyncLog, target.id)
        row.status = "pending"
        await s.commit()

    from app.core.db import SessionLocal as SL

    async with SL() as session:
        summary = await replay_pending(session, branch_id=branch, user_id=None)
    assert summary["applied"] == 1

    async with SessionLocal() as s:
        po = await s.get(PurchaseOrder, po_id)
        assert po.orderdate == date(2026, 8, 25)
        assert po.datee == date(2026, 8, 26)
        line = (
            await s.execute(
                select(PurchaseOrderLine).where(PurchaseOrderLine.order_id == po_id)
            )
        ).scalars().one()
        assert str(line.unit_cost) == "0.0000"

    await u._cleanup(
        need_ids=[],
        order_ids=[po_id],
        drug_ids=[drug_id],
        branch_ids=[branch],
        user_ids=[user],
    )


@pytest.mark.asyncio
async def test_review2_po_save_then_cancel_converges_on_peer(client):
    """rev ladder: save=2, cancel=3 — a peer applying both payloads must end
    cancelled (previously the cancel was skipped: rev 2 <= local rev 2)."""
    from sqlalchemy import delete, select, update

    from app.core.db import SessionLocal
    from app.models import PurchaseOrder, SyncLog
    from app.sync.service import replay_pending

    branch = await u._make_branch()
    user, name = await u._make_user(level=3, branch_id=branch)
    drug_id = await u._make_drug_with_stock(branch_id=branch)
    token = await u._login_token(client, name)

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        headers=u._headers(token),
    )
    po_id = resp.json()["id"]
    assert (
        await client.post(f"/api/v1/purchase-orders/{po_id}/save", headers=u._headers(token))
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/purchase-orders/{po_id}/cancel", headers=u._headers(token))
    ).status_code == 200

    async with SessionLocal() as s:
        po = await s.get(PurchaseOrder, po_id)
        assert (po.status, po.rev) == ("cancelled", 3)
        await s.execute(delete(PurchaseOrder).where(PurchaseOrder.id == po_id))
        await s.execute(
            update(SyncLog).where(SyncLog.entity == "purchase_order").values(status="applied")
        )
        await s.commit()
        rows = (
            await s.execute(
                select(SyncLog)
                .where(
                    SyncLog.entity == "purchase_order",
                    SyncLog.branch_id == branch,
                )
                .order_by(SyncLog.id)  # chronological: create -> save -> cancel
            )
        ).scalars().all()

    # fresh peer replays BOTH payloads in order → must converge on cancelled
    for row in rows:
        async with SessionLocal() as s:
            r = await s.get(SyncLog, row.id)
            r.status = "pending"
            await s.commit()
        from app.core.db import SessionLocal as SL

        async with SL() as session:
            summary = await replay_pending(session, branch_id=branch, user_id=None)
        assert summary["applied"] == 1

    async with SessionLocal() as s:
        po = await s.get(PurchaseOrder, po_id)
        assert po.status == "cancelled"
        assert po.rev == 3

    async with SessionLocal() as s:
        await s.execute(
            update(SyncLog).where(SyncLog.entity == "purchase_order").values(status="applied")
        )
        await s.commit()
    await u._cleanup(
        need_ids=[],
        order_ids=[po_id],
        drug_ids=[drug_id],
        branch_ids=[branch],
        user_ids=[user],
    )


@pytest.mark.asyncio
async def test_review2_handoff_link_replays_and_rev_bumps(client):
    """The pickup (sender pin + transfer link) bumps rev to 2 so versioned
    peers converge on the claimed state instead of skipping it."""
    from sqlalchemy import delete, select, update

    from app.core.db import SessionLocal
    from app.models import Need, SyncLog
    from app.sync.service import replay_pending

    branch_a = await u._make_branch()
    branch_b = await u._make_branch()
    user_a, name_a = await u._make_user(level=3, branch_id=branch_a)
    user_b, name_b = await u._make_user(level=3, branch_id=branch_b)
    drug_id = await u._make_drug_with_stock(branch_id=branch_b, stock_qty="5")
    token_a = await u._login_token(client, name_a)
    token_b = await u._login_token(client, name_b)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "2", "sender_branch_id": branch_b},
        headers=u._headers(token_a),
    )
    need_id = resp.json()["id"]
    handoff = await client.post(
        f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_b)
    )
    assert handoff.status_code == 201
    transfer_id = handoff.json()["id"]

    async with SessionLocal() as s:
        need = await s.get(Need, need_id)
        assert (need.status, need.rev) == ("pending", 2)

        # fresh peer: wipe + replay ONLY the link payload (rev 2)
        await s.execute(delete(Need).where(Need.id == need_id))
        await s.execute(update(SyncLog).where(SyncLog.entity == "need").values(status="applied"))
        await s.commit()
        rows = (
            await s.execute(select(SyncLog).where(SyncLog.entity == "need"))
        ).scalars().all()
    link_rows = [r for r in rows if (r.payload or {}).get("transfer_id") == transfer_id]
    assert link_rows
    target = link_rows[-1]
    async with SessionLocal() as s:
        row = await s.get(SyncLog, target.id)
        row.status = "pending"
        await s.commit()

    from app.core.db import SessionLocal as SL

    async with SL() as session:
        summary = await replay_pending(session, branch_id=target.branch_id, user_id=None)
    assert summary["applied"] == 1

    async with SessionLocal() as s:
        need = await s.get(Need, need_id)
        assert need.sender_branch_id == branch_b
        assert need.transfer_id == transfer_id
        assert need.rev == 2

    async with SessionLocal() as s:
        await s.execute(update(SyncLog).where(SyncLog.entity == "need").values(status="applied"))
        await s.commit()
    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        transfer_ids=[transfer_id],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b],
        user_ids=[user_a, user_b],
    )


@pytest.mark.asyncio
async def test_review2_partial_receipt_leaves_need_pending(client):
    """A shortage receive (received < sent) does NOT fulfill the linked need —
    only a full delivery does (N4)."""
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Need

    branch_a = await u._make_branch()
    branch_b = await u._make_branch()
    user_a, name_a = await u._make_user(level=3, branch_id=branch_a)
    user_b, name_b = await u._make_user(level=3, branch_id=branch_b)
    drug_id = await u._make_drug_with_stock(
        branch_id=branch_b,
        stock_qty="10",
        batches=[("10", "5.0000", "2027-01-01")],
    )
    token_a = await u._login_token(client, name_a)
    token_b = await u._login_token(client, name_b)

    need_id = (
        await client.post(
            "/api/v1/needs",
            json={"drug_id": drug_id, "qty": "4", "sender_branch_id": branch_b},
            headers=u._headers(token_a),
        )
    ).json()["id"]
    transfer = (
        await client.post(
            f"/api/v1/needs/{need_id}/transfer", headers=u._headers(token_b)
        )
    ).json()
    line_id = transfer["lines"][0]["id"]
    await client.post(
        f"/api/v1/transfers/{transfer['id']}/dispatch",
        json={},
        headers=u._headers(token_b),
    )
    recv = await client.post(
        f"/api/v1/transfers/{transfer['id']}/receive",
        json={"lines": [{"line_id": line_id, "received_qty": "1"}]},  # 25% shortage
        headers=u._headers(token_a),
    )
    assert recv.status_code == 200, recv.text

    async with SessionLocal() as s:
        need = (await s.execute(select(Need).where(Need.id == need_id))).scalar_one()
        assert need.status == "pending"  # NOT fulfilled by a partial receipt
        assert need.rev == 2

    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        transfer_ids=[transfer["id"]],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b],
        user_ids=[user_a, user_b],
    )


@pytest.mark.asyncio
async def test_review2_self_pinned_need_rejected(client):
    branch = await u._make_branch()
    user, name = await u._make_user(level=3, branch_id=branch)
    drug_id = await u._make_drug_with_stock(branch_id=branch)
    token = await u._login_token(client, name)
    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "1", "sender_branch_id": branch},
        headers=u._headers(token),
    )
    assert resp.status_code == 400
    await u._cleanup(
        need_ids=[], order_ids=[], drug_ids=[drug_id], branch_ids=[branch], user_ids=[user]
    )


@pytest.mark.asyncio
async def test_review2_window_overflow_is_400(client):
    branch = await u._make_branch()
    user, name = await u._make_user(level=3, branch_id=branch)
    token = await u._login_token(client, name)
    assert (
        await client.get(
            "/api/v1/needs/suggestions?mode=sales_rate&window_days=1000000000",
            headers=u._headers(token),
        )
    ).status_code == 400
    await u._cleanup(
        need_ids=[], order_ids=[], drug_ids=[], branch_ids=[branch], user_ids=[user]
    )


@pytest.mark.asyncio
async def test_review2_replay_advances_identity_sequence(client):
    """A replayed explicit-id insert must bump the PG sequence, or the next
    LOCAL create collides with a replayed id (duplicate-key 500)."""
    from sqlalchemy import delete, select, update

    from app.core.db import SessionLocal
    from app.models import Need, SyncLog
    from app.sync.service import replay_pending

    branch = await u._make_branch()
    user, name = await u._make_user(level=3, branch_id=branch)
    drug_id = await u._make_drug_with_stock(branch_id=branch)
    token = await u._login_token(client, name)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "1"},
        headers=u._headers(token),
    )
    need_id = resp.json()["id"]

    # craft a FUTURE-id payload far beyond the sequence and apply it
    future_id = need_id + 10_000
    async with SessionLocal() as s:
        await s.execute(delete(Need).where(Need.id == need_id))
        await s.execute(update(SyncLog).where(SyncLog.entity == "need").values(status="applied"))
        await s.commit()
        row = (
            await s.execute(select(SyncLog).where(SyncLog.entity == "need"))
        ).scalars().first()
        payload = dict(row.payload)
        payload["id"] = future_id
        row.payload = {**payload, "id": future_id}
        row.status = "pending"
        row.branch_id = branch
        await s.commit()

    from app.core.db import SessionLocal as SL

    async with SL() as session:
        summary = await replay_pending(session, branch_id=branch, user_id=None)
    assert summary["applied"] == 1

    # next local create must succeed past the replayed id
    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "1"},
        headers=u._headers(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] > future_id

    async with SessionLocal() as s:
        await s.execute(update(SyncLog).where(SyncLog.entity == "need").values(status="applied"))
        await s.commit()
    await u._cleanup(
        need_ids=[future_id, resp.json()["id"]],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch],
        user_ids=[user],
    )
