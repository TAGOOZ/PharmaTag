"""Shared helpers for the S1.3 sales test themes (ticket #9).

Each themed test file imports these; the helpers create + clean up their own
throwaway drug/batch/stock rows on branch 1 (MAIN, seed admin). Cleanup walks
the FK chain (journal_lines → journals → invoices → batches → drugs) so a
mid-suite failure never blocks later deletes.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    BranchStock,
    DrawerMovement,
    Drug,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
    User,
)

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_sale_{tag}_{_seq[0]}__"


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _make_drug_and_stock(
    *,
    tax_type: str = "14%",
    price: str = "10.0000",
    wholesale: str = "8.0000",
    cost_price: str = "5.0000",
    batches: Optional[list[tuple[str, str, Optional[str]]]] = None,
    stock_qty: str = "20.0000",
) -> int:
    """Create a throwaway drug + branch_stock + batches; returns drug_id."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("drug"),
            tax_type=tax_type,
            price=Decimal(price),
            price_wholesale=Decimal(wholesale),
            price_cost=Decimal(cost_price),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=BRANCH_ID, drug_id=drug_id, qty=Decimal(stock_qty), minimum=0
            )
        )
        for i, (qty, cost, expire) in enumerate(batches or []):
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


async def _cleanup(drug_ids: list[int], invoice_ids: list[int]) -> None:
    async with SessionLocal() as session:
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
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == iid)
            )
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
            )
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
        await session.commit()


async def _stock_qty(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
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


async def _make_user(username: str, permission_level: int, branch_id=None, active=True) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash="x",
            permission_level=permission_level,
            branch_id=branch_id,
            active=active,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


def _token_for(user_id: int, branch_id) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=branch_id or 0, roles=[], permission_level=0
    )