"""Offline replay of purchase outbox rows (ticket #10, G10): replay_pending
dispatches a pending 'invoice' row to apply_purchase_payload when its kind is
'purchase' — stock is ADDED as a new batch, never double-applied (dedupe by
(branch_id, invoice_no)), and failures are recorded without rolling back the
rest. Replaying twice must never double stock-up.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.audit import enqueue_sync
from app.models import (
    AuditLog,
    BranchStock,
    Drug,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    Party,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from app.sync.service import replay_pending
from tests.purchase_test_utils import _make_supplier

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_preplay_{tag}_{_seq[0]}__"


async def _make_drug() -> int:
    async with SessionLocal() as session:
        drug = Drug(drugname=_uniq("drug"), tax_type="14%", price=Decimal("0.0000"))
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        await session.commit()
        return drug_id


async def _stock_qty(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
                )
            )
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


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


def _purchase_payload(invoice_no: str, drug_id: int, supplier_id: int, qty: str = "10") -> dict:
    """A realistic purchase outbox snapshot: one 14% line at 10.00/unit."""
    return {
        "branch_id": BRANCH_ID,
        "invoice_no": invoice_no,
        "datee": "2026-08-17",
        "kind": "purchase",
        "party_id": supplier_id,
        "inclusive": True,
        "subtotal": "100.00",
        "discount": "0.00",
        "vat": "12.28",
        "totalvalue": "100.00",
        "net": "87.72",
        "payed": "100.00",
        "agel": "0.00",
        "lines": [
            {
                "drug_id": drug_id,
                "qty": qty,
                "unit_price": "10.0000",
                "unit_cost": "8.7720",
                "discount": "0.00",
                "tax_type": "14%",
                "vat_amount": "12.28",
                "line_total": "100.00",
                "expire": "2026-12-31",
                "batch": {
                    "randomid": f"p-{invoice_no}-0",
                    "cost": "8.7720",
                    "vat": "14.00",
                    "price": "10.0000",
                    "vatvalue": "12.28",
                    "totalwithvat": "100.00",
                },
            }
        ],
        "payments": [{"method": "cash", "amount": "100.00"}],
        "journal": {
            "entry_no": 999,
            "description": f"فاتورة مشتريات {invoice_no}",
            "entries": [
                {"account_code": "1200", "debit": "87.72", "credit": "0.00"},
                {"account_code": "2100", "debit": "12.28", "credit": "0.00"},
                {"account_code": "1000", "debit": "0.00", "credit": "100.00"},
            ],
        },
    }


def _sale_payload(invoice_no: str, drug_id: int, batch: StockBatch, qty: str = "4") -> dict:
    """A sale outbox snapshot (as the online sale emits it) for dispatch testing."""
    total = str(Decimal(qty) * Decimal("10.00"))
    return {
        "branch_id": BRANCH_ID,
        "invoice_no": invoice_no,
        "datee": "2026-08-17",
        "kind": "sale",
        "inclusive": True,
        "subtotal": total,
        "discount": "0.00",
        "vat": "0.00",
        "totalvalue": total,
        "payed": total,
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
                "line_total": total,
                "expire": None,
                "allocations": [
                    {
                        "batch_id": batch.id,
                        "randomid": batch.randomid,
                        "take": qty,
                        "cost": "5.0000",
                        "expire": None,
                    }
                ],
            }
        ],
        "payments": [{"method": "cash", "amount": total}],
        "journal": {"entry_no": 999, "source": "sale"},
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


async def _cleanup(drug_ids: list[int], invoice_ids: list[int], party_ids: list[int]) -> None:
    async with SessionLocal() as session:
        linked = (
            await session.execute(
                select(InvoiceLine.invoice_id).where(
                    InvoiceLine.drug_id.in_(drug_ids) if drug_ids else False
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
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == iid)
            )
            await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == iid))
            await session.execute(
                delete(SyncLog).where(SyncLog.entity_id == iid)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.entity_id == iid)
            )
            await session.execute(delete(Invoice).where(Invoice.id == iid))
        for drug_id in drug_ids:
            await session.execute(
                delete(StockBatch).where(StockBatch.drug_id == drug_id)
            )
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.drug_id == drug_id)
            )
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        for pid in party_ids:
            await session.execute(delete(Party).where(Party.id == pid))
        await session.commit()


async def _replay() -> dict:
    async with SessionLocal() as session:
        return await replay_pending(session, branch_id=BRANCH_ID)


async def test_replay_applies_outbox_purchase_and_is_idempotent():
    """A pending purchase row with no matching invoice is applied — batch
    created, stock up, journal balanced; a second replay skips it."""
    drug_id = await _make_drug()
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        await _enqueue(_purchase_payload("80001", drug_id, supplier_id))

        summary = await _replay()
        assert summary == {"applied": 1, "skipped": 0, "failed": 0, "failures": []}

        async with SessionLocal() as session:
            invoice = (
                await session.execute(select(Invoice).where(Invoice.invoice_no == "80001"))
            ).scalar_one()
            invoice_ids.append(invoice.id)
            assert invoice.kind == "purchase"
            assert invoice.totalvalue == Decimal("100.00")
            line = (
                await session.execute(
                    select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
                )
            ).scalar_one()
            assert line.unit_price == Decimal("10.0000")
            assert line.cost == Decimal("8.7720")
            row = (
                await session.execute(
                    select(SyncLog).where(SyncLog.branch_id == BRANCH_ID)
                )
            ).scalars().all()
            by_no = {r.payload["invoice_no"]: r for r in row}
            assert by_no["80001"].status == "applied"
        assert await _stock_qty(drug_id) == Decimal("10.0000")
        debit, credit = await _journal_totals(invoice_ids[0])
        assert debit == Decimal("100.00")
        assert credit == Decimal("100.00")

        # second replay: nothing pending anymore — no re-apply, no double stock-up
        summary = await _replay()
        assert summary == {"applied": 0, "skipped": 0, "failed": 0, "failures": []}
        assert await _stock_qty(drug_id) == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_replay_dispatches_by_kind_sale_and_purchase():
    """A sale payload still decrements stock; a purchase payload adds stock —
    the same replay run handles both."""
    from tests.sales_test_utils import _make_drug_and_stock as make_sale_drug

    sale_drug = await make_sale_drug(
        tax_type="exempt",
        price="10.0000",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    purchase_drug = await _make_drug()
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        async with SessionLocal() as session:
            sale_batch = (
                await session.execute(
                    select(StockBatch).where(StockBatch.drug_id == sale_drug)
                )
            ).scalars().one()
            await enqueue_sync(
                session,
                branch_id=BRANCH_ID,
                entity="invoice",
                action="insert",
                payload=_sale_payload("70090", sale_drug, sale_batch),
            )
            await session.commit()
        await _enqueue(_purchase_payload("80002", purchase_drug, supplier_id))

        summary = await _replay()
        assert summary["applied"] == 2
        assert summary["failed"] == 0
        assert await _stock_qty(sale_drug) == Decimal("6.0000")
        assert await _stock_qty(purchase_drug) == Decimal("10.0000")

        async with SessionLocal() as session:
            invoices = (
                await session.execute(
                    select(Invoice).where(Invoice.invoice_no.in_(["70090", "80002"]))
                )
            ).scalars().all()
            invoice_ids = [i.id for i in invoices]
    finally:
        await _cleanup(
            [sale_drug, purchase_drug], invoice_ids, [supplier_id]
        )