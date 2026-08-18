"""Shared helpers for the S1.7 stock-count test themes (ticket #13).

Each themed test file imports these; the helpers create + clean up their own
throwaway drug/batch/stock/correction-request rows on branch 1 (MAIN, seed
admin). Cleanup walks the FK chain (correction requests -> batches -> drugs)
so a mid-suite failure never blocks later deletes.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    Branch,
    BranchStock,
    Drug,
    Journal,
    JournalLine,
    PriceChangeLog,
    StockBatch,
    StockCorrectionRequest,
    SyncLog,
    User,
)

BRANCH_ID = 1

import os as _os

_PID = _os.getpid()

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t13_stock_{_PID}_{tag}_{_seq[0]}__"


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
    stock_qty: Optional[str] = None,
) -> int:
    """Create a throwaway drug + branch_stock + batches; returns drug_id.

    `stock_qty=None` (default) creates the drug with NO branch_stock row (so an
    overage correction must upsert it from zero); pass a value to seed stock.
    """
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
        if stock_qty is not None:
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


async def _cleanup(drug_ids: list[int], request_ids: list[int] | None = None) -> None:
    async with SessionLocal() as session:
        if request_ids:
            await session.execute(
                delete(StockCorrectionRequest).where(
                    StockCorrectionRequest.id.in_(request_ids)
                )
            )
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
            await session.execute(
                delete(PriceChangeLog).where(PriceChangeLog.drug_id == drug_id)
            )
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        for row in (await session.execute(select(SyncLog))).scalars().all():
            if row.payload and row.payload.get("drug_id") in drug_ids:
                await session.execute(delete(SyncLog).where(SyncLog.id == row.id))
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
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


async def _batches(drug_id: int) -> list:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(StockBatch)
                .where(StockBatch.drug_id == drug_id)
                .order_by(StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id)
            )
        ).scalars().all()


async def _request(request_id: int) -> StockCorrectionRequest:
    async with SessionLocal() as session:
        return await session.get(StockCorrectionRequest, request_id)


async def _latest_correction_journal(drug_id: int):
    """The most recent journal whose lines touch the drug's stock account
    (source='correction'), or None. Lines are joined through the stock account
    (1200) because journals carry no drug_id."""
    async with SessionLocal() as session:
        journal = (
            await session.execute(
                select(Journal)
                .join(JournalLine, JournalLine.journal_id == Journal.id)
                .where(Journal.source == "correction")
                .order_by(Journal.id.desc())
            )
        ).scalars().first()
        if journal is None:
            return None
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        return {
            "journal": journal,
            "lines": lines,
            "debit": sum((l.debit for l in lines), Decimal("0")),
            "credit": sum((l.credit for l in lines), Decimal("0")),
        }


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


async def _make_other_branch() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        branch = Branch(
            pharmacyid=f"pt{_seq[0]}",
            phar="",
            mobile="0",
            pharname=_uniq("branch"),
            is_active=True,
        )
        session.add(branch)
        await session.flush()
        branch_id = branch.id
        await session.commit()
        return branch_id


async def _delete_other_branch(branch_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.branch_id == branch_id))
        await session.execute(delete(Branch).where(Branch.id == branch_id))
        await session.commit()


async def _delete_users(user_ids: list[int]) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.user_id.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def _token_for(user_id: int, branch_id) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=branch_id or 0, roles=[], permission_level=0
    )