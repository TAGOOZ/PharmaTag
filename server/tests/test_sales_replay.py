"""Offline replay of sale outbox rows (ticket #9, G10): replay_pending applies
every pending 'invoice' row for a branch using its explicit allocations (FIFO
is NOT re-run), dedupes by (branch_id, invoice_no), and marks failures without
rolling back the rest. Replaying twice must never double-decrement stock.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.audit import enqueue_sync
from app.models import (
    AuditLog,
    Balance,
    BranchStock,
    Drug,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from app.sync.service import replay_pending

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_replay_{tag}_{_seq[0]}__"


async def _make_drug(batches: list[tuple[str, str, Optional[str]]]) -> int:
    async with SessionLocal() as session:
        drug = Drug(drugname=_uniq("drug"), tax_type="exempt", price=Decimal("10.0000"))
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=BRANCH_ID,
                drug_id=drug_id,
                qty=sum((Decimal(q) for q, _c, _e in batches), Decimal("0")),
                minimum=0,
            )
        )
        for i, (qty, cost, expire) in enumerate(batches):
            session.add(
                StockBatch(
                    branch_id=BRANCH_ID,
                    drug_id=drug_id,
                    randomid=f"{_uniq('b')}{i}",
                    qty=Decimal(qty),
                    cost=Decimal(cost),
                    expire=date.fromisoformat(expire) if expire else None,
                )
            )
        await session.commit()
        return drug_id


async def _batch_ids(drug_id: int) -> dict[str, int]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(select(StockBatch).where(StockBatch.drug_id == drug_id))
        ).scalars().all()
        return {b.randomid: b.id for b in rows}


async def _stock_qty(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
                )
            )
        ).scalar_one()
        return row.qty


async def _journal_totals(invoice_id: int) -> tuple[Decimal, Decimal]:
    async with SessionLocal() as session:
        journal = (
            await session.execute(
                select(Journal).where(Journal.ref_invoice_id == invoice_id)
            )
        ).scalar_one()
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        return (
            sum((l.debit for l in lines), Decimal("0")),
            sum((l.credit for l in lines), Decimal("0")),
        )


def _payload(
    invoice_no: str, drug_id: int, batch_id: int, randomid: str, qty: str = "4"
) -> dict:
    """A realistic outbox snapshot for one exempt line of qty at 10.00/unit."""
    return {
        "branch_id": BRANCH_ID,
        "invoice_no": invoice_no,
        "datee": "2026-08-17",
        "silsilaid": "",
        "kind": "sale",
        "inclusive": True,
        "subtotal": str(Decimal(qty) * Decimal("10.00")),
        "discount": "0.00",
        "vat": "0.00",
        "totalvalue": str(Decimal(qty) * Decimal("10.00")),
        "payed": str(Decimal(qty) * Decimal("10.00")),
        "agel": "0.00",
        "lines": [
            {
                "drug_id": drug_id,
                "qty": qty,
                "unit_price": "10.0000",
                "unit_cost": "5.0000",
                "discount": "0.00",
                "tax_type": "exempt",
                "vat_amount": "0.00",
                "line_total": str(Decimal(qty) * Decimal("10.00")),
                "expire": None,
                "allocations": [
                    {
                        "batch_id": batch_id,
                        "randomid": randomid,
                        "take": qty,
                        "cost": "5.0000",
                        "expire": None,
                    }
                ],
            }
        ],
        "payments": [{"method": "cash", "amount": str(Decimal(qty) * Decimal("10.00"))}],
        "journal": {
            "entry_no": 999,
            "description": f"فاتورة بيع {invoice_no}",
            "entries": [
                {"account_code": "1000", "debit": str(Decimal(qty) * Decimal("10.00")), "credit": "0.00"},
                {"account_code": "4000", "debit": "0.00", "credit": str(Decimal(qty) * Decimal("10.00"))},
                {"account_code": "6000", "debit": str(Decimal(qty) * Decimal("5.00")), "credit": "0.00"},
                {"account_code": "1200", "debit": "0.00", "credit": str(Decimal(qty) * Decimal("5.00"))},
            ],
        },
    }


async def _enqueue(payload: dict) -> None:
    async with SessionLocal() as session:
        await enqueue_sync(
            session,
            branch_id=BRANCH_ID,
            entity="invoice",
            action="insert",
            payload=payload,
        )
        await session.commit()


async def _cleanup(drug_ids: list[int], invoice_ids: list[int], sync_ids: list[int]) -> None:
    async with SessionLocal() as session:
        # any invoice that touches one of our drugs — even one the test never
        # tracked (e.g. created by a replay that applied after an early assert
        # failed) — must be removed before the drugs can be deleted.
        linked = (
            await session.execute(
                select(InvoiceLine.invoice_id).where(
                    InvoiceLine.drug_id.in_(drug_ids)
                )
            )
        ).scalars().all()
        invoice_ids = list(set(invoice_ids) | set(linked))
        for iid in invoice_ids:
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
            await session.execute(delete(Balance).where(Balance.branch_id == BRANCH_ID))
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == iid)
            )
            await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == iid))
            await session.execute(
                delete(SyncLog).where(SyncLog.entity_id == iid)
            )
            await session.execute(delete(AuditLog).where(AuditLog.entity_id == iid))
            await session.execute(delete(Invoice).where(Invoice.id == iid))
        for sid in sync_ids:
            await session.execute(delete(SyncLog).where(SyncLog.id == sid))
        for drug_id in drug_ids:
            await session.execute(
                delete(StockBatch).where(StockBatch.drug_id == drug_id)
            )
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()


async def _replay() -> dict:
    async with SessionLocal() as session:
        return await replay_pending(session, branch_id=BRANCH_ID)


async def test_replay_applies_outbox_sale_and_is_idempotent():
    """A pending invoice outbox row with no matching invoice gets applied; a
    second replay skips it (dedupe by invoice_no) and stock never moves twice."""
    drug_id = await _make_drug([("10.0000", "5.0000", None)])
    batch_ids = await _batch_ids(drug_id)
    sync_ids: list[int] = []
    invoice_ids: list[int] = []
    try:
        payload = _payload("70001", drug_id, batch_ids[list(batch_ids)[0]], list(batch_ids)[0])
        await _enqueue(payload)
        async with SessionLocal() as session:
            sync_ids = (
                await session.execute(
                    select(SyncLog.id).where(SyncLog.payload["invoice_no"].as_string() == "70001")
                )
            ).scalars().all()

        summary = await _replay()
        assert summary["applied"] == 1
        assert summary["skipped"] == 0
        assert summary["failed"] == 0

        async with SessionLocal() as session:
            invoice = (
                await session.execute(select(Invoice).where(Invoice.invoice_no == "70001"))
            ).scalar_one()
            invoice_ids.append(invoice.id)
            assert invoice.totalvalue == Decimal("40.00")
            lines = (
                await session.execute(
                    select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
                )
            ).scalars().all()
            assert len(lines) == 1
            assert lines[0].qty == Decimal("4.0000")
            # explicit allocations used (exactly one batch), stock decremented
            assert lines[0].batch_id == batch_ids[list(batch_ids)[0]]
            row = (
                await session.execute(
                    select(SyncLog).where(SyncLog.branch_id == BRANCH_ID)
                )
            ).scalars().all()
            by_no = {r.payload["invoice_no"]: r for r in row}
            assert by_no["70001"].status == "applied"
        assert await _stock_qty(drug_id) == Decimal("6.0000")
        debit, credit = await _journal_totals(invoice_ids[0])
        assert debit == Decimal("60.00")  # 40 drawer + 20 cogs
        assert credit == Decimal("60.00")

        # second replay: nothing pending anymore (row marked applied in run 1) —
        # no re-apply, no double decrement
        summary = await _replay()
        assert summary == {"applied": 0, "skipped": 0, "failed": 0, "failures": []}
        assert await _stock_qty(drug_id) == Decimal("6.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, sync_ids)


async def test_replay_skips_online_sales_already_invoice_exists():
    """A sale recorded online (invoice present) is deduped on replay — never
    re-decrements, never re-journals."""
    drug_id = await _make_drug([("10.0000", "5.0000", None)])
    batch_ids = await _batch_ids(drug_id)
    sync_ids: list[int] = []
    invoice_ids: list[int] = []
    try:
        # simulate the online write: invoice exists + outbox pending
        payload = _payload("70002", drug_id, batch_ids[list(batch_ids)[0]], list(batch_ids)[0])
        async with SessionLocal() as session:
            from app.sales.service import apply_sale_payload

            invoice = await apply_sale_payload(session, branch_id=BRANCH_ID, payload=payload)
            await session.commit()
            invoice_ids.append(invoice.id)
        await _enqueue(payload)
        async with SessionLocal() as session:
            sync_ids = (
                await session.execute(select(SyncLog.id).where(SyncLog.entity_id == invoice_ids[0]))
            ).scalars().all()

        summary = await _replay()
        assert summary["applied"] == 0
        assert summary["skipped"] == 1
        assert summary["failed"] == 0
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(SyncLog.branch_id == BRANCH_ID)
                )
            ).scalars().all()
            by_no = {r.payload["invoice_no"]: r for r in row}
            assert by_no["70002"].status == "applied"
    finally:
        await _cleanup([drug_id], invoice_ids, sync_ids)


async def test_replay_failed_row_recorded_and_does_not_roll_back_others():
    """A row whose batch is missing on the target store is marked failed; the
    sibling good row still applies."""
    good_drug = await _make_drug([("10.0000", "5.0000", None)])
    bad_drug = await _make_drug([("10.0000", "5.0000", None)])
    good_batches = await _batch_ids(good_drug)
    bad_batches = await _batch_ids(bad_drug)
    sync_ids: list[int] = []
    invoice_ids: list[int] = []
    try:
        good_key = list(good_batches)[0]
        bad_key = list(bad_batches)[0]
        good_payload = _payload("70003", good_drug, good_batches[good_key], good_key)
        bad_payload = _payload("70004", bad_drug, 999999, "no_such_batch")  # batch id gone
        await _enqueue(good_payload)
        await _enqueue(bad_payload)
        async with SessionLocal() as session:
            sync_ids = (
                await session.execute(
                    select(SyncLog.id).where(SyncLog.branch_id == BRANCH_ID)
                )
            ).scalars().all()

        summary = await _replay()
        assert summary["applied"] == 1
        assert summary["skipped"] == 0
        assert summary["failed"] == 1
        assert summary["failures"][0]["invoice_no"] == "70004"

        async with SessionLocal() as session:
            good_invoice = (
                await session.execute(select(Invoice).where(Invoice.invoice_no == "70003"))
            ).scalar_one()
            invoice_ids.append(good_invoice.id)
            assert await _stock_qty(good_drug) == Decimal("6.0000")
            # bad row: no invoice, failed + failure recorded in payload
            rows = (
                await session.execute(
                    select(SyncLog).where(SyncLog.branch_id == BRANCH_ID)
                )
            ).scalars().all()
            by_no = {r.payload["invoice_no"]: r for r in rows}
            assert by_no["70003"].status == "applied"
            assert by_no["70004"].status == "failed"
            assert "failure" in by_no["70004"].payload
            assert await _stock_qty(bad_drug) == Decimal("10.0000")
    finally:
        await _cleanup([good_drug, bad_drug], invoice_ids, sync_ids)


async def test_replay_is_atomic_per_row_and_balanced():
    """Even a replayed multi-line sale journals balanced and audits everything."""
    drug_id = await _make_drug([("20.0000", "5.0000", None)])
    batch_ids = await _batch_ids(drug_id)
    sync_ids: list[int] = []
    invoice_ids: list[int] = []
    try:
        key = list(batch_ids)[0]
        payload = _payload("70005", drug_id, batch_ids[key], key, qty="8")
        await _enqueue(payload)
        async with SessionLocal() as session:
            sync_ids = (
                await session.execute(
                    select(SyncLog.id).where(SyncLog.payload["invoice_no"].as_string() == "70005")
                )
            ).scalars().all()

        summary = await _replay()
        assert summary == {"applied": 1, "skipped": 0, "failed": 0, "failures": []}
        async with SessionLocal() as session:
            invoice = (
                await session.execute(select(Invoice).where(Invoice.invoice_no == "70005"))
            ).scalar_one()
            invoice_ids.append(invoice.id)
            audits = (
                await session.execute(
                    select(AuditLog).where(AuditLog.branch_id == BRANCH_ID)
                )
            ).scalars().all()
            assert {"invoices", "invoice_lines", "journals", "stock_batches", "branch_stock"}.issubset(
                {a.entity for a in audits}
            )
        debit, credit = await _journal_totals(invoice_ids[0])
        assert debit == Decimal("120.00")  # 80 drawer + 40 cogs
        assert credit == Decimal("120.00")
    finally:
        await _cleanup([drug_id], invoice_ids, sync_ids)