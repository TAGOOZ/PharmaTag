"""Audit + outbox write-path invariants (ticket #2 AC3/AC4, G12).

Every money/stock mutation writes its audit_log row and sync_log outbox row in
the SAME transaction as the mutation. These integration tests prove it against
the real Postgres (pharmatag_test): on success all three land; on any error the
whole write rolls back to nothing — the mutation, its audit row and its outbox
row live or die together.

Tests create their own throwaway drug/branch_stock rows and clean up after
themselves; branch 1 (MAIN) and user 1 (admin) come from the seeded migrations.
"""
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.audit import audit, enqueue_sync
from app.core.db import SessionLocal, atomic
from app.models import AuditLog, BranchStock, Drug, SyncLog
from app.stock.service import adjust_stock

BRANCH_ID = 1
USER_ID = 1


# the fixture's teardown needs the id; simplest is to yield a mutable holder
@pytest.fixture
async def stock_drug():
    async with SessionLocal() as session:
        drug = Drug(drugname="__t2_audit_test__")
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        await session.execute(
            delete(SyncLog).where(SyncLog.entity_id == drug_id)
        )
        await session.execute(
            delete(AuditLog).where(AuditLog.drug_id == drug_id)
        )
        await session.execute(
            delete(BranchStock).where(BranchStock.drug_id == drug_id)
        )
        row = BranchStock(branch_id=BRANCH_ID, drug_id=drug_id, qty=Decimal("10"))
        session.add(row)
        await session.commit()
        yield drug_id
    async with SessionLocal() as session:
        await session.execute(
            delete(SyncLog).where(SyncLog.entity_id == drug_id)
        )
        await session.execute(
            delete(AuditLog).where(AuditLog.drug_id == drug_id)
        )
        await session.execute(
            delete(BranchStock).where(BranchStock.drug_id == drug_id)
        )
        await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()


async def _rows_for(drug_id: int, model, *, key: str):
    async with SessionLocal() as session:
        result = await session.execute(
            select(model).where(getattr(model, key) == drug_id)
        )
        return result.scalars().all()


async def test_stock_write_commits_audit_and_outbox_atomically(stock_drug):
    drug_id = stock_drug
    async with SessionLocal() as session:
        updated = await adjust_stock(
            session,
            branch_id=BRANCH_ID,
            user_id=USER_ID,
            drug_id=drug_id,
            qty_delta=5,
        )
        # atomic() already committed on success
    assert updated.qty == Decimal("15")

    audits = await _rows_for(drug_id, AuditLog, key="drug_id")
    outbox = await _rows_for(drug_id, SyncLog, key="entity_id")
    assert len(audits) == 1, "exactly one audit_log row for the mutation"
    assert audits[0].entity == "branch_stock"
    assert audits[0].action == "update"
    assert audits[0].old_value == "10.0000"
    assert audits[0].new_value == "15.0000"
    assert len(outbox) == 1, "exactly one sync_log outbox row"
    assert outbox[0].status == "pending"
    assert outbox[0].payload["qty"] == "15.0000"


async def test_failed_write_rolls_back_mutation_audit_and_outbox(stock_drug):
    drug_id = stock_drug
    async with SessionLocal() as session:
        try:
            async with atomic(session):
                await adjust_stock(
                    session,
                    branch_id=BRANCH_ID,
                    user_id=USER_ID,
                    drug_id=drug_id,
                    qty_delta=5,
                )
                raise RuntimeError("boom")
        except RuntimeError:
            pass

    # nothing persisted: qty unchanged, no audit, no outbox
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one()
        assert row.qty == Decimal("10")
    assert await _rows_for(drug_id, AuditLog, key="drug_id") == []
    assert await _rows_for(drug_id, SyncLog, key="entity_id") == []


async def test_audit_and_outbox_append_without_committing():
    """audit()/enqueue_sync() never commit on their own (caller owns boundary)."""
    async with SessionLocal() as session:
        await audit(
            session,
            branch_id=BRANCH_ID,
            user_id=USER_ID,
            entity="manual_journal_entries",
            field="note",
            old_value="a",
            new_value="b",
        )
        await enqueue_sync(
            session, branch_id=BRANCH_ID, entity="manual_journal_entries", action="insert"
        )
        await session.rollback()  # no commit happened inside the helpers
    # rollback proves the helpers joined our transaction instead of auto-committing
    async with SessionLocal() as session:
        n = (
            await session.execute(
                select(SyncLog).where(SyncLog.entity == "manual_journal_entries")
            )
        ).scalars().all()
        assert n == []