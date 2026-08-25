"""Shared helpers for the S5.3 needs/orders test themes (#33).

Same contract as transfers_test_utils.py: throwaway branches, branch-pinned
users, drugs, needs and purchase orders; FK-chain-backwards cleanup so a
mid-suite failure never blocks later deletes. Natural keys are pid-namespaced
(uq_branches_pharmacyid/mobile are hard constraints).
"""
import os
import secrets
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
    Need,
    PurchaseOrder,
    PurchaseOrderLine,
    SyncLog,
    User,
)

PID = os.getpid()
# random per-import run token: PID alone collides when the OS reuses
# pids across runs that leaked rows (killed/interrupted suites)
_run = secrets.token_hex(3)
_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"T33_{_run}_{PID}_{tag}_{_seq[0]}"


async def _login_token(client, username: str, password: str = "pw123456") -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_user(*, level: int, branch_id: Optional[int]) -> tuple[int, str]:
    """Create a branch-pinned user; returns (user_id, username)."""
    username = _uniq("u")
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
        return user_id, username


async def _make_branch() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        branch = Branch(
            pharmacyid=f"t33{_run}{PID % 1000}{_seq[0]}"[:15],
            phar="",
            mobile=f"01{int(_run, 16) % 1_000_000:06d}{PID % 100:02d}{_seq[0]:04d}"[:14],
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
    minimum: str = "0",
    batches: Optional[list[tuple[str, str, Optional[str]]]] = None,
) -> int:
    """Drug + branch_stock (qty + minimum) + FEFO-ordered batches on ONE branch."""
    from app.models import StockBatch

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
                minimum=Decimal(minimum),
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


async def _cleanup(
    *,
    need_ids: list[int],
    order_ids: list[int],
    transfer_ids: Optional[list[int]] = None,
    drug_ids: list[int] | None = None,
    branch_ids: list[int] | None = None,
    user_ids: list[int] | None = None,
) -> None:
    transfer_ids = transfer_ids or []
    drug_ids = drug_ids or []
    branch_ids = branch_ids or []
    user_ids = user_ids or []
    async with SessionLocal() as session:
        await session.execute(delete(Need).where(Need.id.in_(need_ids)))
        await session.execute(
            delete(PurchaseOrderLine).where(
                PurchaseOrderLine.order_id.in_(order_ids)
            )
        )
        await session.execute(
            delete(PurchaseOrder).where(PurchaseOrder.id.in_(order_ids))
        )
        await session.execute(
            delete(SyncLog).where(SyncLog.entity.in_(["need", "purchase_order"]))
        )
        await session.execute(
            delete(AuditLog).where(AuditLog.entity.in_(["need", "purchase_order"]))
        )
        if transfer_ids:
            from app.models import Transfer, TransferLine

            await session.execute(
                delete(TransferLine).where(TransferLine.transfer_id.in_(transfer_ids))
            )
            await session.execute(delete(Transfer).where(Transfer.id.in_(transfer_ids)))
        if branch_ids:
            from app.models import Invoice, InvoiceLine

            inv_ids = (
                await session.execute(
                    select(Invoice.id).where(Invoice.branch_id.in_(branch_ids))
                )
            ).scalars().all()
            if inv_ids:
                await session.execute(
                    delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(inv_ids))
                )
                await session.execute(delete(Invoice).where(Invoice.id.in_(inv_ids)))
        for drug_id in drug_ids:
            from app.models import StockBatch

            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == drug_id))
            await session.execute(delete(BranchStock).where(BranchStock.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.execute(
            delete(AuditLog).where(AuditLog.user_id.in_(user_ids))
        )
        await session.execute(
            delete(AuditLog).where(AuditLog.branch_id.in_(branch_ids))
        )
        await session.execute(delete(SyncLog).where(SyncLog.branch_id.in_(branch_ids)))
        await session.execute(
            delete(BranchStock).where(BranchStock.branch_id.in_(branch_ids))
        )
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.execute(delete(Branch).where(Branch.id.in_(branch_ids)))
        await session.commit()
