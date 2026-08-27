"""Shared helpers for the S1.6 purchase-return test themes (ticket #12).

Reuses the S1.4 purchase drug/supplier factories and login helpers; adds a
`_purchase` / `_return` API driver and a return-aware cleanup that deletes
return invoices (which reference their original via `ref_invoice_id`) BEFORE
the originals, so the self-FK never blocks deletes.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    Account,
    AuditLog,
    Balance,
    BranchStock,
    DrawerMovement,
    Drug,
    Invoice,
    InvoiceLine,
    InvoiceVersion,
    Journal,
    JournalLine,
    Party,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from tests.purchase_test_utils import (
    BRANCH_ID,
    _batches,
    _cleanup as _purchase_cleanup,
    _journal_source,
    _journal_totals,
    _login_token,
    _make_drug,
    _make_supplier,
    _stock_qty,
    _uniq,
)

__all__ = [
    "BRANCH_ID",
    "_batches",
    "_cleanup",
    "_journal_codes",
    "_journal_source",
    "_journal_totals",
    "_login_token",
    "_make_drug",
    "_make_supplier",
    "_purchase",
    "_return",
    "_stock_qty",
]


async def _purchase(
    client, token: str, supplier_id: int, lines: list[dict], payments=None, disc_percent=None, datee=None
) -> dict:
    """Create a purchase via the API and return its response body."""
    body = {"supplier_id": supplier_id, "lines": lines}
    if payments is not None:
        body["payments"] = payments
    if disc_percent is not None:
        body["disc_percent"] = disc_percent
    if datee is not None:
        body["datee"] = datee
    r = await client.post(
        "/api/v1/purchases",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _return(client, token: str, purchase: dict, lines: list[dict], payments=None, datee=None) -> dict:
    """Record a purchase return via the API and return its response body."""
    body = {"lines": lines}
    if payments is not None:
        body["payments"] = payments
    if datee is not None:
        body["datee"] = datee
    r = await client.post(
        f"/api/v1/purchases/{purchase['id']}/return",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _journal_codes(invoice_id: int) -> set[str]:
    """Account codes on the invoice's journal (for 'no VAT line' style asserts)."""
    async with SessionLocal() as session:
        journal = (
            await session.execute(
                select(Journal).where(Journal.ref_invoice_id == invoice_id)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(JournalLine, Account)
                .join(Account, Account.id == JournalLine.account_id)
                .where(JournalLine.journal_id == journal.id)
            )
        ).all()
        return {a.code for _, a in rows}


async def _cleanup(drug_ids: list[int], invoice_ids: list[int], party_ids: list[int]) -> None:
    """Return-aware cleanup: any invoice that touches our drugs or is referenced
    by a return must be removed — return invoices before their originals, and
    parties last."""
    async with SessionLocal() as session:
        linked = (
            await session.execute(
                select(InvoiceLine.invoice_id).where(
                    InvoiceLine.drug_id.in_(drug_ids) if drug_ids else False
                )
            )
        ).scalars().all()
        invoice_ids = list(set(invoice_ids) | set(linked))
        if invoice_ids:
            refs = (
                await session.execute(
                    select(Invoice.id).where(Invoice.ref_invoice_id.in_(invoice_ids))
                )
            ).scalars().all()
            invoice_ids = list(set(invoice_ids) | set(refs))
            return_ids = (
                await session.execute(
                    select(Invoice.id).where(
                        Invoice.id.in_(invoice_ids),
                        Invoice.ref_invoice_id.is_not(None),
                    )
                )
            ).scalars().all()
            origin_ids = [iid for iid in invoice_ids if iid not in set(return_ids)]
            for iid in list(return_ids) + origin_ids:
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
                    delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == iid)
                )
                await session.execute(
                    delete(InvoiceVersion).where(InvoiceVersion.invoice_id == iid)
                )
                await session.execute(delete(SyncLog).where(SyncLog.entity_id == iid))
                await session.execute(
                    delete(AuditLog).where(AuditLog.entity_id == iid)
                )
                await session.execute(
                    delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
                )
                await session.execute(delete(Invoice).where(Invoice.id == iid))
        for drug_id in drug_ids:
            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
            await session.execute(delete(SyncLog).where(SyncLog.entity == "branch_stock", SyncLog.entity_id == drug_id))
            for row in (await session.execute(select(SyncLog))).scalars().all():
                if row.payload and row.payload.get("drug_id") == drug_id:
                    await session.execute(delete(SyncLog).where(SyncLog.id == row.id))
        for pid in party_ids:
            await session.execute(
                delete(AuditLog).where(AuditLog.entity == "parties", AuditLog.entity_id == pid)
            )
            await session.execute(delete(Party).where(Party.id == pid))
        await session.execute(delete(Balance).where(Balance.branch_id == BRANCH_ID))
        await session.commit()