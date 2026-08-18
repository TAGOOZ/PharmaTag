"""Shared helpers for the S1.5 sales-return test themes (ticket #11).

Reuses the S1.3 drug/stock factories and login helpers; adds return-aware
cleanup that deletes return invoices (which reference their original via
`ref_invoice_id`) BEFORE the originals, so the self-FK never blocks deletes.
"""
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    BranchStock,
    Drug,
    Invoice,
    InvoiceLine,
    InvoiceVersion,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from tests.sales_test_utils import (
    BRANCH_ID,
    _cleanup as _cleanup_sales,
    _journal_totals,
    _login_token,
    _make_drug_and_stock,
    _stock_qty,
)

__all__ = [
    "BRANCH_ID",
    "_cleanup",
    "_journal_totals",
    "_login_token",
    "_make_drug_and_stock",
    "_stock_qty",
    "_sale",
    "_return_batches",
]


async def _sale(client, token: str, lines: list[dict], payments=None, disc_percent=None) -> dict:
    """Create a sale via the API and return its response body."""
    body = {"lines": lines}
    if payments is not None:
        body["payments"] = payments
    if disc_percent is not None:
        body["disc_percent"] = disc_percent
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _return_batches(drug_id: int) -> list[StockBatch]:
    """Return batches created by returns for a drug (typee='return')."""
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(StockBatch)
                .where(StockBatch.drug_id == drug_id, StockBatch.typee == "return")
                .order_by(StockBatch.id)
            )
        ).scalars().all()


async def _cleanup(drug_ids: list[int], invoice_ids: list[int]) -> None:
    """Return-aware cleanup: return invoices first (they FK the original via
    `ref_invoice_id`, and their lines FK the original lines via
    `ref_invoice_line_id`), then originals."""
    async with SessionLocal() as session:
        all_ids = list(invoice_ids)
        if all_ids:
            refs = (
                await session.execute(
                    select(Invoice.id).where(
                        Invoice.ref_invoice_id.in_(all_ids)
                    )
                )
            ).scalars().all()
            all_ids = list(set(all_ids) | set(refs))
            for iid in all_ids:
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
                await session.execute(
                    delete(InvoiceVersion).where(InvoiceVersion.invoice_id == iid)
                )
                await session.execute(delete(SyncLog).where(SyncLog.entity_id == iid))
                await session.execute(
                    delete(AuditLog).where(AuditLog.entity_id == iid)
                )
            # return invoices before their originals (self-FK ordering)
            return_ids = (
                await session.execute(
                    select(Invoice.id).where(
                        Invoice.id.in_(all_ids),
                        Invoice.ref_invoice_id.is_not(None),
                    )
                )
            ).scalars().all()
            origin_ids = [
                iid for iid in all_ids if iid not in set(return_ids)
            ]
            for iid in list(return_ids) + origin_ids:
                await session.execute(
                    delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
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
        await session.commit()