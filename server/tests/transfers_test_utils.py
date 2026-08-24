"""Shared helpers for the S5.2 inter-pharmacy transfer test themes (#32).

Each themed test file imports these. Helpers create throwaway branches,
branch-pinned users, drugs, source-side stock/batches and transfers, then walk
the FK chain backwards on cleanup so a mid-suite failure never blocks later
deletes. Natural keys are pid-namespaced (uq_branches_pharmacyid/mobile are
hard constraints).
"""
import os
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Branch,
    BranchStock,
    Drug,
    StockBatch,
    SyncLog,
    Transfer,
    TransferLine,
    User,
)

PID = os.getpid()
_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"T32_{PID}_{tag}_{_seq[0]}"


async def _login_token(client, username: str, password: str = "pw123456") -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_user(username: str, *, level: int, branch_id: Optional[int]) -> int:
    from app.auth.security import hash_password

    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash=hash_password("pw123456"),
            permission_level=level,
            branch_id=branch_id,
            active=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _make_branch() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        branch = Branch(
            pharmacyid=f"t32{PID % 100000}{_seq[0]}"[:15],
            phar="",
            mobile=f"01{PID % 10_000_000}{_seq[0]:04d}"[:14],
            pharname=_uniq("branch"),
            is_active=True,
        )
        session.add(branch)
        await session.flush()
        branch_id = branch.id
        await session.commit()
        return branch_id


async def _make_drug_with_stock(
    *,
    branch_id: int,
    stock_qty: str = "10",
    batches: Optional[list[tuple[str, str, Optional[str]]]] = None,
) -> int:
    """Drug + branch_stock + FEFO-ordered batches (qty, cost, expire) on ONE branch."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("drug"),
            tax_type="14%",
            price=Decimal("10.0000"),
            price_wholesale=Decimal("8.0000"),
            price_cost=Decimal("5.0000"),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=branch_id,
                drug_id=drug_id,
                qty=Decimal(stock_qty),
                minimum=0,
            )
        )
        for i, (qty, cost, expire) in enumerate(batches or []):
            session.add(
                StockBatch(
                    branch_id=branch_id,
                    drug_id=drug_id,
                    randomid=f"{_uniq('b')}{i}",
                    qty=Decimal(qty),
                    cost=Decimal(cost),
                    expire=date.fromisoformat(expire) if expire else None,
                )
            )
        await session.commit()
        return drug_id


async def _stock_qty(branch_id: int, drug_id: int) -> Optional[Decimal]:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == branch_id,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one_or_none()
        return None if row is None else row.qty


async def _batches(branch_id: int, drug_id: int) -> list[StockBatch]:
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(StockBatch)
                    .where(
                        StockBatch.branch_id == branch_id,
                        StockBatch.drug_id == drug_id,
                    )
                    .order_by(StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id)
                )
            ).scalars().all()
        )


async def _transfer(transfer_id: int) -> tuple[Transfer, list[TransferLine]]:
    async with SessionLocal() as session:
        transfer = await session.get(Transfer, transfer_id)
        lines = (
            await session.execute(
                select(TransferLine)
                .where(TransferLine.transfer_id == transfer_id)
                .order_by(TransferLine.id)
            )
        ).scalars().all()
        return transfer, list(lines)


async def _cleanup(
    *,
    transfer_ids: list[int],
    drug_ids: list[int],
    branch_ids: list[int],
    user_ids: list[int],
) -> None:
    async with SessionLocal() as session:
        await session.execute(
            delete(TransferLine).where(TransferLine.transfer_id.in_(transfer_ids))
        )
        await session.execute(delete(Transfer).where(Transfer.id.in_(transfer_ids)))
        await session.execute(
            delete(SyncLog).where(SyncLog.entity == "transfer")
        )
        await session.execute(
            delete(AuditLog).where(AuditLog.entity.in_(["transfer", "transfer_line"]))
        )
        for drug_id in drug_ids:
            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            await session.execute(delete(BranchStock).where(BranchStock.drug_id == drug_id))
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.execute(
            delete(SyncLog).where(
                SyncLog.branch_id.in_(branch_ids) | (SyncLog.entity == "transfer")
            )
        )
        await session.execute(delete(AuditLog).where(AuditLog.user_id.in_(user_ids)))
        # every row this file stamped on its own branches: transfer headers,
        # stock movements, and any registry rows written while deactivating a
        # created branch
        await session.execute(
            delete(AuditLog).where(AuditLog.branch_id.in_(branch_ids))
        )
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.execute(delete(Branch).where(Branch.id.in_(branch_ids)))
        await session.commit()
