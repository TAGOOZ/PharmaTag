"""Shared helpers for the S1.5 sales-return test themes (ticket #11).

Reuses the S1.3 drug/stock factories and login helpers; adds return-aware
cleanup that deletes return invoices (which reference their original via
`ref_invoice_id`) BEFORE the originals, so the self-FK never blocks deletes.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    Account,
    AuditLog,
    Balance,
    Branch,
    BranchStock,
    DrawerMovement,
    Drug,
    EInvoiceLog,
    Invoice,
    InvoiceLine,
    InvoiceVersion,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
    User,
)
from tests.sales_test_utils import (
    BRANCH_ID,
    _cleanup as _cleanup_sales,
    _journal_totals,
    _login_token,
    _make_drug_and_stock,
    _stock_qty,
    _uniq,
)

__all__ = [
    "BRANCH_ID",
    "_cleanup",
    "_journal_codes",
    "_journal_totals",
    "_login_token",
    "_make_branch",
    "_make_drug_and_stock",
    "_make_drug_and_stock_branch",
    "_return_batches",
    "_sale",
    "_stock_qty",
    "_stock_qty_branch",
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
                select(Account.code)
                .join(JournalLine, JournalLine.account_id == Account.id)
                .where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        return set(rows)


async def _make_branch(*, vat_inclusive: bool) -> int:
    """Create a throwaway branch with the given VAT pricing mode; return its id."""
    import uuid as _uuid

    async with SessionLocal() as session:
        suffix = _uuid.uuid4().hex[:10]
        branch = Branch(
            # uq_branches_pharmacyid / uq_branches_mobile: a leftover branch
            # from a crashed run must never collide with the next one
            pharmacyid=f"pt{suffix}",
            phar="",
            mobile=f"0{suffix}",
            pharname=_uniq("branch"),
            vat_inclusive_prices=vat_inclusive,
            is_active=True,
        )
        session.add(branch)
        await session.flush()
        branch_id = branch.id
        await session.commit()
        return branch_id


async def _make_drug_and_stock_branch(
    branch_id: int,
    *,
    tax_type: str = "14%",
    price: str = "10.0000",
    cost_price: str = "5.0000",
    stock_qty: str = "10.0000",
) -> int:
    """Create a throwaway drug + branch_stock + batch on a NON-MAIN branch."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("drug"),
            tax_type=tax_type,
            price=Decimal(price),
            price_wholesale=Decimal(price),
            price_cost=Decimal(cost_price),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=branch_id, drug_id=drug_id, qty=Decimal(stock_qty), minimum=0
            )
        )
        session.add(
            StockBatch(
                branch_id=branch_id,
                drug_id=drug_id,
                randomid=f"{_uniq('b')}0",
                qty=Decimal(stock_qty),
                cost=Decimal(cost_price),
                expire=None,
            )
        )
        await session.commit()
        return drug_id


async def _stock_qty_branch(branch_id: int, drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == branch_id,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


async def _delete_branch(branch_id: int) -> None:
    """Remove a throwaway branch + its users + balances (they FK the branch).
    Audit rows reference the branch's users, so purge those first."""
    async with SessionLocal() as session:
        user_ids = (
            await session.execute(
                select(User.id).where(User.branch_id == branch_id)
            )
        ).scalars().all()
        if user_ids:
            await session.execute(
                delete(AuditLog).where(AuditLog.user_id.in_(user_ids))
            )
        await session.execute(delete(Balance).where(Balance.branch_id == branch_id))
        await session.execute(delete(User).where(User.branch_id == branch_id))
        await session.execute(delete(Branch).where(Branch.id == branch_id))
        await session.commit()


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
                    delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == iid)
                )
                # the tax document FKs the invoice — purge it first (S4.1)
                await session.execute(
                    delete(EInvoiceLog).where(EInvoiceLog.invoice_id == iid)
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
            await session.execute(delete(SyncLog).where(SyncLog.entity == "branch_stock", SyncLog.entity_id == drug_id))
            for row in (await session.execute(select(SyncLog))).scalars().all():
                if row.payload and row.payload.get("drug_id") == drug_id:
                    await session.execute(delete(SyncLog).where(SyncLog.id == row.id))
        await session.commit()