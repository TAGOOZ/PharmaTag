"""Shared helpers for the S1.9 basic-reports test themes (ticket #15).

Drives the branch-1 admin/sales fixtures (same as the money slices) and cleans
up the throwaway drug/batch/stock/invoice rows a report test creates — plus any
manual drawer movements the test records and their audit rows.
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
    InvoiceVersion,
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
    return f"__t2_rep_{tag}_{_seq[0]}__"


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
    cost_price: str = "5.0000",
    batches: Optional[list[tuple[str, str, Optional[str]]]] = None,
    stock_qty: str = "20.0000",
    minimum: str = "0.0000",
) -> int:
    """Create a throwaway drug + branch_stock + batches; returns drug_id."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("drug"),
            tax_type=tax_type,
            price=Decimal(price),
            price_cost=Decimal(cost_price),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=BRANCH_ID,
                drug_id=drug_id,
                qty=Decimal(stock_qty),
                minimum=Decimal(minimum),
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


async def _cleanup(
    drug_ids: list[int],
    invoice_ids: list[int],
    movement_ids: Optional[list[int]] = None,
) -> None:
    async with SessionLocal() as session:
        all_ids = list(invoice_ids)
        if all_ids:
            # include return invoices that reference the given ids
            refs = (
                await session.execute(
                    select(Invoice.id).where(Invoice.ref_invoice_id.in_(all_ids))
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
                await session.execute(delete(Balance).where(Balance.branch_id == BRANCH_ID))
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
                await session.execute(delete(AuditLog).where(AuditLog.entity_id == iid))
            # return invoices before their originals (self-FK ordering)
            return_ids = (
                await session.execute(
                    select(Invoice.id).where(
                        Invoice.id.in_(all_ids),
                        Invoice.ref_invoice_id.is_not(None),
                    )
                )
            ).scalars().all()
            origin_ids = [iid for iid in all_ids if iid not in set(return_ids)]
            for iid in list(return_ids) + origin_ids:
                await session.execute(
                    delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
                )
                await session.execute(delete(Invoice).where(Invoice.id == iid))
        for mid in movement_ids or []:
            await session.execute(
                delete(AuditLog).where(
                    AuditLog.entity == "drawer_movements",
                    AuditLog.entity_id == mid,
                )
            )
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.id == mid)
            )
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


async def _make_user(username: str, permission_level: int, branch_id=None) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash="x",
            permission_level=permission_level,
            branch_id=branch_id,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id
