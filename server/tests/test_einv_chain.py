"""S4.1 chain + reconciliation invariants (ticket #28 AC2/AC5): every log
row's uuid recomputes from its payload + previous_uuid; first-of-device has an
empty previousUUID; counters stay gapless and equal Σ log rows per (branch,
device, kind); tampering is detected."""
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    BranchStock,
    DrawerMovement,
    Drug,
    EInvoiceCounter,
    EInvoiceLog,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from app.einvoicing.chain import verify_chain
from tests.einv_test_utils import (
    _clear_rin,
    _make_user,
    _set_rin,
    _uniq,
)
from tests.sales_test_utils import _token_for
from tests.returns_test_utils import (
    _delete_branch,
    _make_branch,
    _make_drug_and_stock_branch,
)


async def _cleanup(drug_ids: list[int], branch_id: int) -> None:
    async with SessionLocal() as session:
        iids = (
            await session.execute(
                select(Invoice.id).where(Invoice.branch_id == branch_id)
            )
        ).scalars().all()
        for iid in iids:
            jids = (
                await session.execute(
                    select(Journal.id).where(Journal.ref_invoice_id == iid)
                )
            ).scalars().all()
            if jids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.journal_id.in_(jids))
                )
                await session.execute(delete(Journal).where(Journal.id.in_(jids)))
            await session.execute(delete(Balance).where(Balance.branch_id == branch_id))
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == iid)
            )
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == iid)
            )
            await session.execute(
                delete(EInvoiceLog).where(EInvoiceLog.invoice_id == iid)
            )
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
            )
            await session.execute(delete(AuditLog).where(AuditLog.entity_id == iid))
            from app.models import SyncLog

            await session.execute(delete(SyncLog).where(SyncLog.entity_id == iid))
            await session.execute(delete(Invoice).where(Invoice.id == iid))
        await session.execute(
            delete(EInvoiceCounter).where(EInvoiceCounter.branch_id == branch_id)
        )
        await session.execute(delete(AuditLog).where(AuditLog.branch_id == branch_id))
        for drug_id in drug_ids:
            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(
                delete(SyncLog).where(
                    SyncLog.branch_id == branch_id,
                    SyncLog.entity == "branch_stock",
                    SyncLog.entity_id == drug_id,
                )
            )
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()
    await _delete_branch(branch_id)


async def test_chain_verifies_and_tampering_is_detected(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    try:
        token = _token_for(user_id, branch_id)
        for _ in range(3):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text

        ok = await verify_chain(branch_id=branch_id)
        assert ok["ok"] is True, ok["problems"]
        assert ok["problems"] == []

        # tamper with one stored uuid → chain verification fails there
        async with SessionLocal() as session:
            victim = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter.desc())
                    .limit(1)
                )
            ).scalar_one()
            victim.uuid = "0" * 64
            await session.commit()
        bad = await verify_chain(branch_id=branch_id)
        assert bad["ok"] is False
        assert any("uuid" in p for p in bad["problems"])
    finally:
        await _clear_rin()
        await _cleanup([drug_id], branch_id)


async def test_gap_and_counter_reconciliation_violations_detected(client):
    """AC5: counter == Σ log rows per (branch, device, kind), gapless — a
    deleted middle row breaks BOTH the gapless chain and the reconciliation;
    a rolled-forward counter without rows is caught too."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    try:
        token = _token_for(user_id, branch_id)
        for _ in range(3):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text

        # delete the middle receipt row (simulated data loss / manual edit)
        async with SessionLocal() as session:
            middle = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(
                        EInvoiceLog.branch_id == branch_id,
                        EInvoiceLog.kind == "receipt",
                        EInvoiceLog.counter == 2,
                    )
                )
            ).scalar_one()
            await session.delete(middle)
            await session.commit()

        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is False
        joined = "\n".join(report["problems"])
        assert "gap" in joined.lower()          # counters 1,3 → gap at 2
        assert "counter" in joined.lower()      # last_counter 3 != Σ rows 2

        # a counter rolled forward with no matching row is caught as well
        async with SessionLocal() as session:
            await session.commit()
        async with SessionLocal() as session:
            ctr = (
                await session.execute(
                    select(EInvoiceCounter).where(
                        EInvoiceCounter.branch_id == branch_id,
                        EInvoiceCounter.kind == "receipt",
                    )
                )
            ).scalar_one()
            ctr.last_counter += 5
            await session.commit()
        report2 = await verify_chain(branch_id=branch_id)
        assert report2["ok"] is False
        assert any("counter" in p for p in report2["problems"])
    finally:
        await _clear_rin()
        await _cleanup([drug_id], branch_id)
