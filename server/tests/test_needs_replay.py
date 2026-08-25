"""Offline-peer convergence for `entity='need'`/`'purchase_order'` rows (#33).

Both branches receive the SAME payload copy of every transition (G12); each
peer replays its own copies. Needs/POs are non-money records — replay restores
recorded state VERBATIM; the rev watermark skips stale/duplicate copies.
"""
import pytest
from sqlalchemy import delete, select, update

from app.core.db import SessionLocal
from app.models import Need, PurchaseOrder, PurchaseOrderLine, SyncLog
from app.sync.service import replay_pending

from tests import needs_test_utils as u


async def _pending_rows(branch_id: int, entity: str) -> list[SyncLog]:
    async with SessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(SyncLog)
                    .where(
                        SyncLog.entity == entity,
                        SyncLog.branch_id == branch_id,
                        SyncLog.status == "pending",
                    )
                    .order_by(SyncLog.id)
                )
            ).scalars().all()
        )


async def _mark_all_applied(entity: str) -> None:
    async with SessionLocal() as s:
        await s.execute(
            update(SyncLog).where(SyncLog.entity == entity).values(status="applied")
        )
        await s.commit()


@pytest.mark.asyncio
async def test_need_replay_restores_verbatim_and_dedupes(client):
    branch_a = await u._make_branch()  # requester
    branch_b = await u._make_branch()  # sender
    user_a, user_a_name = await u._make_user(level=3, branch_id=branch_a)
    drug_id = await u._make_drug_with_stock(branch_id=branch_a, stock_qty="2")
    token_a = await u._login_token(client, user_a_name)
    user_b, user_b_name = await u._make_user(level=3, branch_id=branch_b)
    token_b = await u._login_token(client, user_b_name)

    resp = await client.post(
        "/api/v1/needs",
        json={"drug_id": drug_id, "qty": "4", "sender_branch_id": branch_b},
        headers=u._headers(token_a),
    )
    need_id = resp.json()["id"]
    # transition → second payload revision on both peers
    assert (
        await client.post(f"/api/v1/needs/{need_id}/cancel", headers=u._headers(token_a))
    ).status_code == 200

    # simulate an offline peer that never saw the row: wipe local + outbox marks
    async with SessionLocal() as s:
        await s.execute(delete(Need).where(Need.id == need_id))
        await s.commit()
    await _mark_all_applied("need")

    # re-force ONLY the peer's latest (cancelled) copy pending and replay it
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(SyncLog).where(
                    SyncLog.entity == "need", SyncLog.branch_id == branch_b
                )
            )
        ).scalars().all()
    cancelled_rows = [
        r for r in rows if (r.payload or {}).get("status") == "cancelled"
    ]
    assert cancelled_rows
    target_id = cancelled_rows[-1].id
    async with SessionLocal() as s:
        row = await s.get(SyncLog, target_id)
        row.status = "pending"
        await s.commit()

    from app.core.db import SessionLocal as SL

    async with SL() as session:
        summary = await replay_pending(session, branch_id=branch_b, user_id=None)

    assert summary["applied"] == 1
    async with SessionLocal() as s:
        need = await s.get(Need, need_id)
        assert need is not None
        assert need.status == "cancelled"
        assert need.qty == 4
        assert need.rev == 3

    # replaying again (row now applied) changes nothing; a duplicate pending
    # copy of the same rev is SKIPPED, not double-applied
    async with SessionLocal() as s:
        row = await s.get(SyncLog, target_id)
        row.status = "pending"
        await s.commit()
    async with SL() as session:
        summary = await replay_pending(session, branch_id=branch_b, user_id=None)
    assert summary["skipped"] == 1

    await _mark_all_applied("need")
    await u._cleanup(
        need_ids=[need_id],
        order_ids=[],
        drug_ids=[drug_id],
        branch_ids=[branch_a, branch_b],
        user_ids=[user_a, user_b],
    )


@pytest.mark.asyncio
async def test_po_replay_restores_header_and_lines(client):
    branch = await u._make_branch()
    user, user_name = await u._make_user(level=3, branch_id=branch)
    drug_a = await u._make_drug_with_stock(branch_id=branch)
    token = await u._login_token(client, user_name)

    resp = await client.post(
        "/api/v1/purchase-orders",
        json={"lines": [{"drug_id": drug_a, "qty": "6", "unit_cost": "3.25"}]},
        headers=u._headers(token),
    )
    po_id = resp.json()["id"]
    assert (
        await client.post(
            f"/api/v1/purchase-orders/{po_id}/save", headers=u._headers(token)
        )
    ).status_code == 200

    async with SessionLocal() as s:
        await s.execute(
            delete(PurchaseOrderLine).where(PurchaseOrderLine.order_id == po_id)
        )
        await s.execute(delete(PurchaseOrder).where(PurchaseOrder.id == po_id))
        await s.commit()
    await _mark_all_applied("purchase_order")

    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(SyncLog).where(
                    SyncLog.entity == "purchase_order",
                    SyncLog.branch_id == branch,
                )
            )
        ).scalars().all()
    saved_rows = [r for r in rows if (r.payload or {}).get("status") == "saved"]
    assert saved_rows
    target = saved_rows[-1]
    target.status = "pending"
    async with SessionLocal() as s:
        s.add(target)
        await s.commit()

    from app.core.db import SessionLocal as SL

    async with SL() as session:
        summary = await replay_pending(session, branch_id=branch, user_id=None)
    assert summary["applied"] == 1

    async with SessionLocal() as s:
        po = await s.get(PurchaseOrder, po_id)
        assert po.status == "saved"
        lines = (
            await s.execute(
                select(PurchaseOrderLine).where(
                    PurchaseOrderLine.order_id == po_id
                )
            )
        ).scalars().all()
        assert len(lines) == 1
        assert str(lines[0].qty) == "6.0000"
        assert str(lines[0].unit_cost) == "3.2500"

    await _mark_all_applied("purchase_order")
    await u._cleanup(
        need_ids=[],
        order_ids=[po_id],
        drug_ids=[drug_a],
        branch_ids=[branch],
        user_ids=[user],
    )
