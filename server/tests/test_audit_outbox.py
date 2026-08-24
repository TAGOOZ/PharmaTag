"""Audit + outbox write-path invariants (ticket #2 AC3/AC4, G12).

Every money/stock mutation writes its audit_log row and sync_log outbox row in
the SAME transaction as the mutation. These integration tests prove it against
the real Postgres (pharmatag_test): on success all three land; on any error the
whole write rolls back to nothing — the mutation, its audit row and its outbox
row live or die together.

Tests create their own throwaway drug/branch_stock rows and clean up after
themselves; branch 1 (MAIN) and user 1 (admin) come from the seeded migrations.
"""
import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import DataError, IntegrityError

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


# --- edge cases (ticket #1/#2 edge pass) ---


async def test_adjust_stock_outside_atomic_still_commits_once(stock_drug):
    """The service owns its boundary: calling it with no enclosing atomic()
    commits exactly once (documented), audit + outbox rows land."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        await adjust_stock(
            session, branch_id=BRANCH_ID, user_id=USER_ID, drug_id=drug_id,
            qty_delta=5,
        )
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one()
        assert row.qty == Decimal("15")
    assert len(await _rows_for(drug_id, AuditLog, key="drug_id")) == 1
    assert len(await _rows_for(drug_id, SyncLog, key="entity_id")) == 1


async def test_nested_atomic_joins_outer_and_rolls_back_together(stock_drug):
    """A nested atomic() joins the enclosing transaction; a later outer failure
    rolls back even the inner 'successful' writes (no partial commit)."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        try:
            async with atomic(session):
                await adjust_stock(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    drug_id=drug_id, qty_delta=5,
                )
                async with atomic(session):  # joins, does NOT commit
                    await adjust_stock(
                        session, branch_id=BRANCH_ID, user_id=USER_ID,
                        drug_id=drug_id, qty_delta=3,
                    )
                raise RuntimeError("outer boom")
        except RuntimeError:
            pass
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


async def test_nested_atomic_inner_failure_propagates(stock_drug):
    drug_id = stock_drug
    async with SessionLocal() as session:
        with pytest.raises(RuntimeError):
            async with atomic(session):
                await adjust_stock(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    drug_id=drug_id, qty_delta=5,
                )
                async with atomic(session):
                    raise RuntimeError("inner boom")
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


async def test_audit_failure_rolls_back_the_whole_write(stock_drug):
    """A failure inside the audit append itself (field too long for its column)
    rolls back the mutation AND the outbox with it."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        with pytest.raises(DataError):
            async with atomic(session):
                await adjust_stock(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    drug_id=drug_id, qty_delta=5,
                )
                await audit(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    entity="x" * 60,  # String(50) NOT NULL -> too long
                    field="note", old_value="a", new_value="b",
                )
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


async def test_enqueue_failure_rolls_back_the_whole_write(stock_drug):
    """A failure in the outbox append (FK to a nonexistent branch) rolls back
    the mutation and its audit row too."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            async with atomic(session):
                await adjust_stock(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    drug_id=drug_id, qty_delta=5,
                )
                await enqueue_sync(
                    session, branch_id=999999, entity="branch_stock",
                    action="update",
                )
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


async def test_adjust_stock_missing_row_raises_and_persists_nothing():
    async with SessionLocal() as session:
        drug = Drug(drugname="__t2_no_stock__")
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        await session.commit()
    try:
        with pytest.raises(ValueError):
            async with SessionLocal() as session:
                await adjust_stock(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    drug_id=drug_id, qty_delta=5,
                )
        assert await _rows_for(drug_id, AuditLog, key="drug_id") == []
        assert await _rows_for(drug_id, SyncLog, key="entity_id") == []
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Drug).where(Drug.id == drug_id))
            await session.commit()


async def test_concurrent_adjust_stock_no_lost_update(stock_drug):
    """FOR UPDATE row lock: two concurrent adjustments on the same drug serialize
    on the running total instead of last-writer-wins (O-9)."""
    drug_id = stock_drug

    async def bump(delta: int):
        async with SessionLocal() as session:
            await adjust_stock(
                session, branch_id=BRANCH_ID, user_id=USER_ID,
                drug_id=drug_id, qty_delta=delta,
            )

    await asyncio.gather(bump(5), bump(7))
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one()
        assert row.qty == Decimal("22"), "lost update: concurrent deltas dropped"
    assert len(await _rows_for(drug_id, AuditLog, key="drug_id")) == 2
    assert len(await _rows_for(drug_id, SyncLog, key="entity_id")) == 2


async def test_adjust_stock_zero_delta_is_still_audited(stock_drug):
    drug_id = stock_drug
    async with SessionLocal() as session:
        await adjust_stock(
            session, branch_id=BRANCH_ID, user_id=USER_ID,
            drug_id=drug_id, qty_delta=0,
        )
    audits = await _rows_for(drug_id, AuditLog, key="drug_id")
    assert len(audits) == 1
    assert audits[0].old_value == "10.0000" and audits[0].new_value == "10.0000"
    assert len(await _rows_for(drug_id, SyncLog, key="entity_id")) == 1


async def test_adjust_stock_negative_delta_past_zero_rejected_atomically(stock_drug):
    """rev 029 backstops patterns.md's 'stock never goes negative' invariant:
    a delta past zero trips ck_branch_stock_qty_nonneg at the DB and the whole
    mutation (stock + audit + outbox) rolls back atomically. Insufficient-stock
    business rejection still belongs to callers — the DB is now the hard floor."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            await adjust_stock(
                session, branch_id=BRANCH_ID, user_id=USER_ID,
                drug_id=drug_id, qty_delta=-15,
            )
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
    assert len(await _rows_for(drug_id, AuditLog, key="drug_id")) == 0
    assert len(await _rows_for(drug_id, SyncLog, key="entity_id")) == 0


async def test_adjust_stock_huge_delta_overflows_and_rolls_back(stock_drug):
    """A delta that overflows NUMERIC(18,4) fails at the DB (not the app) and
    still rolls back atomically — mutation + audit + outbox all gone."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        with pytest.raises(DataError):
            async with atomic(session):
                await adjust_stock(
                    session, branch_id=BRANCH_ID, user_id=USER_ID,
                    drug_id=drug_id, qty_delta=10**30,
                )
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


async def test_audit_and_sync_payload_shape(stock_drug):
    """Full audit/outbox row shape: legacy audit fields, exact Numeric(18,4)
    strings, JSONB payload, pending status, source_device passthrough."""
    drug_id = stock_drug
    async with SessionLocal() as session:
        await adjust_stock(
            session, branch_id=BRANCH_ID, user_id=USER_ID,
            drug_id=drug_id, qty_delta=4, barcode="1234567890123",
            source_device_id=1,
        )
    audits = await _rows_for(drug_id, AuditLog, key="drug_id")
    assert len(audits) == 1
    a = audits[0]
    assert a.branch_id == BRANCH_ID
    assert a.user_id == USER_ID
    assert a.entity == "branch_stock"
    assert a.entity_id == drug_id
    assert a.field == "qty"
    assert a.old_value == "10.0000"
    assert a.new_value == "14.0000"
    assert a.drug_id == drug_id
    assert a.barcode == "1234567890123"
    assert a.action == "update"
    outbox = await _rows_for(drug_id, SyncLog, key="entity_id")
    assert len(outbox) == 1
    o = outbox[0]
    assert o.branch_id == BRANCH_ID
    assert o.entity == "branch_stock"
    assert o.entity_id == drug_id
    assert o.action == "update"
    assert o.status == "pending"
    assert o.synced_at is None
    assert o.source_device_id == 1
    assert o.payload == {"branch_id": 1, "drug_id": drug_id, "qty": "14.0000"}