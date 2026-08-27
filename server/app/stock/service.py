"""Write-path seam for a stock mutation (ticket #2 AC3/AC4).

`adjust_stock` is the canonical shape every money/stock mutation follows:
it runs inside `app.core.db.atomic()` so the branch_stock update, its
`audit_log` row and its `sync_log` outbox row commit or roll back together
(G12, plan/02 §4.1). Later tickets build sales/purchases/returns on this
same skeleton (branch_stock + stock_batches + journal + balances + audit +
outbox in one transaction).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.audit import ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.models import BranchStock, Drug
from app.sales.numbering import acquire_branch_lock

STOCK_ENTITY = "branch_stock"


async def adjust_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    qty_delta: int,
    barcode: str = "",
    source_device_id: Optional[int] = None,
) -> BranchStock:
    """Adjust branch_stock by `qty_delta` (+in/-out), atomically auditing.

    Locks the branch_stock row (SELECT ... FOR UPDATE) so concurrent sales on
    the same drug serialize on the running total (plan/02 §4.1, O-9).
    """
    async with atomic(session):
        row = (
            await session.execute(
                select(BranchStock)
                .where(
                    BranchStock.branch_id == branch_id,
                    BranchStock.drug_id == drug_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(f"no branch_stock row for branch={branch_id} drug={drug_id}")

        old_qty = row.qty
        row.qty = old_qty + qty_delta

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=STOCK_ENTITY,
            entity_id=drug_id,
            field="qty",
            old_value=str(old_qty),
            new_value=str(row.qty),
            drug_id=drug_id,
            barcode=barcode,
            action=ACTION_UPDATE,
        )
        await enqueue_sync(
            session,
            branch_id=branch_id,
            entity=STOCK_ENTITY,
            entity_id=drug_id,
            action=ACTION_UPDATE,
            payload={
                "branch_id": branch_id,
                "drug_id": drug_id,
                "qty": format(money.round4(row.qty), "f"),
                "minimum": format(money.round4(row.minimum), "f"),
                "silsilaid": row.silsilaid or "",
                "classy": row.classy or "",
            },
            source_device_id=source_device_id,
        )
        return row


async def set_minimum(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    minimum,
) -> BranchStock:
    """Set per-branch reorder point (titanksastock.minimum → branch_stock.minimum).

    Creates the BranchStock row with qty 0 when missing (stock snapshot #35).
    Validates exact-decimal 4dp, non-negative, non-NaN, non-overflow; writes
    audit_log (field=minimum) and enqueue_sync (payload qty+minimum) atomically
    under the branch advisory lock (G12).
    """
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)

        drug = await session.get(Drug, drug_id)
        if drug is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "drug not found")

        # --- validate minimum ---
        try:
            min_val = money.dec(minimum)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid minimum") from exc
        # NaN / Infinity must be rejected before any comparison
        try:
            if min_val.is_nan() or min_val.is_infinite():
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid minimum")
        except AttributeError:
            pass
        if min_val < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "minimum must be >= 0")
        # canonical 4dp rounding
        min_val = money.round4(min_val)
        # overflow: Numeric(18,4) max is 10**14 - 0.0001; reject >= 10**14
        if min_val >= Decimal("100000000000000"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "minimum overflow")
        # 18 digits total, 4 after decimal -> max 14 integer digits; already guarded
        # but also reject values whose string representation exceeds 18 digits
        # (e.g. 99999999999999.99995 rounds to 100000000000000.0000 -> overflow)
        # handled by the >= check above.

        row = (
            await session.execute(
                select(BranchStock)
                .where(BranchStock.branch_id == branch_id, BranchStock.drug_id == drug_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if row is None:
            row = BranchStock(
                branch_id=branch_id,
                drug_id=drug_id,
                qty=Decimal("0"),
                minimum=min_val,
                lastedit=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.flush()
            old_min_str = None
            qty_str = format(money.round4(row.qty), "f")
            min_str = format(min_val, "f")
        else:
            old_min = money.dec(row.minimum)
            old_min_str = format(money.round4(old_min), "f")
            row.minimum = min_val
            row.lastedit = datetime.now(timezone.utc)
            session.add(row)
            await session.flush()
            qty_str = format(money.round4(row.qty), "f")
            min_str = format(min_val, "f")

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=STOCK_ENTITY,
            entity_id=drug_id,
            field="minimum",
            old_value=old_min_str,
            new_value=min_str,
            drug_id=drug_id,
            action=ACTION_UPDATE,
        )
        await enqueue_sync(
            session,
            branch_id=branch_id,
            entity=STOCK_ENTITY,
            entity_id=drug_id,
            action=ACTION_UPDATE,
            payload={
                "branch_id": branch_id,
                "drug_id": drug_id,
                "qty": qty_str,
                "minimum": min_str,
                "silsilaid": row.silsilaid or "",
                "classy": row.classy or "",
            },
        )
        return row