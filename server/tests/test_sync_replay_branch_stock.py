"""S1.7 edge pass (ticket #13): the branch_stock outbox rows the correction
approval enqueues must be replayable — LWW by absolute qty (idempotent), and a
row whose target drug is missing on the target store is recorded failed, never
silently dropped (G10). Closes the orphan-outbox gap (edge pass #5)."""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AuditLog, BranchStock, Drug, PriceChangeLog, StockBatch, SyncLog
from app.sync.service import replay_pending
from tests.stock_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def _stock(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == 1, BranchStock.drug_id == drug_id
                )
            )
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


async def _enqueue(drug_id: int, qty: str, action: str = "correction") -> int:
    async with SessionLocal() as session:
        from app.core.audit import enqueue_sync

        row = await enqueue_sync(
            session,
            branch_id=1,
            entity="branch_stock",
            entity_id=drug_id,
            action=action,
            payload={"branch_id": 1, "drug_id": drug_id, "qty": qty},
        )
        await session.commit()
        return row.id


async def test_replay_applies_branch_stock_outbox_row(client):
    """A pending branch_stock row is applied (LWW absolute qty) and marked
    applied; branch_stock lands at the row's qty."""
    # sweep any leaked pending branch_stock rows from previous tests (failed
    # runs leave orphaned pending rows whose drug was deleted → they would be
    # counted as failed and break the exact 1-applied assertion)
    async with SessionLocal() as session:
        from sqlalchemy import delete as _delete

        await session.execute(
            _delete(SyncLog).where(SyncLog.branch_id == 1, SyncLog.entity == "branch_stock", SyncLog.status == "pending")
        )
        await session.commit()
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    row_id = await _enqueue(drug_id, "25.0000")
    try:
        summary = await replay_pending(SessionLocal(), branch_id=1)
        assert summary["applied"] >= 1
        # its own row must be in the applied set
        assert await _stock(drug_id) == Decimal("25.0000")

        async with SessionLocal() as session:
            row = (await session.get(SyncLog, row_id))
            assert row.status == "applied"
            assert row.synced_at is not None
    finally:
        await _cleanup([drug_id])


async def test_replay_branch_stock_is_idempotent(client):
    """Re-applying the same row is a no-op: the qty is absolute, so a second
    pass leaves branch_stock unchanged."""
    async with SessionLocal() as session:
        from sqlalchemy import delete as _delete

        await session.execute(
            _delete(SyncLog).where(SyncLog.branch_id == 1, SyncLog.entity == "branch_stock", SyncLog.status == "pending")
        )
        await session.commit()
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    row_id = await _enqueue(drug_id, "25.0000")
    try:
        first = await replay_pending(SessionLocal(), branch_id=1)
        assert first["applied"] >= 1
        second = await replay_pending(SessionLocal(), branch_id=1)
        assert second["applied"] == 0
        assert second["skipped"] == 0  # nothing pending left to replay
        assert await _stock(drug_id) == Decimal("25.0000")

        async with SessionLocal() as session:
            row = (await session.get(SyncLog, row_id))
            assert row.status == "applied"
    finally:
        await _cleanup([drug_id])


async def test_replay_branch_stock_missing_drug_failed(client):
    """A row whose drug no longer exists on the target store is recorded failed
    with the reason in the payload (G10 — recorded, never lost)."""
    async with SessionLocal() as session:
        from sqlalchemy import delete as _delete

        await session.execute(
            _delete(SyncLog).where(SyncLog.branch_id == 1, SyncLog.entity == "branch_stock", SyncLog.status == "pending")
        )
        await session.commit()
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    row_id = await _enqueue(drug_id, "25.0000")
    # remove ONLY the drug rows, leaving the pending outbox row untouched
    async with SessionLocal() as session:
        for model in (BranchStock, StockBatch, AuditLog, PriceChangeLog):
            await session.execute(
                model.__table__.delete().where(model.drug_id == drug_id)
            )
        await session.execute(Drug.__table__.delete().where(Drug.id == drug_id))
        await session.commit()
    try:
        summary = await replay_pending(SessionLocal(), branch_id=1)
        assert summary["applied"] == 0
        assert summary["failed"] == 1
        async with SessionLocal() as session:
            row = (await session.get(SyncLog, row_id))
            assert row.status == "failed"
            assert row.payload["failure"]
    finally:
        async with SessionLocal() as session:
            await session.execute(
                SyncLog.__table__.delete().where(SyncLog.id == row_id)
            )
            await session.commit()