"""Expiry-FIFO stock allocation + decrement for the sale slice (plan/02 §4.1).

One sale line may span several batches: allocation walks the drug's batches
ordered by expiry (NULLS LAST) then id, taking from each until the line qty is
met. The drug's branch_stock row and the matching batches are locked FOR UPDATE
so concurrent sales on the same drug can never oversell; `branch_stock.qty` is
the availability gate and the sum of the batch takes is the authoritative
decrement.

Decrements write the batch `qty` (with `oldstock` = pre-sale snapshot) and
`branch_stock.qty` in the SAME transaction as the invoice/journal/audit/outbox,
so a rejected sale leaves no trace (G12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.money import dec, round2
from app.models import BranchStock, StockBatch

INSUFFICIENT_STOCK = HTTPException(
    status.HTTP_409_CONFLICT, "insufficient stock"
)
NO_STOCK = HTTPException(
    status.HTTP_409_CONFLICT, "no stock registered for this drug"
)
MISSING_BATCH = HTTPException(
    status.HTTP_409_CONFLICT, "stock batch missing"
)


@dataclass(frozen=True)
class Allocation:
    """One batch's share of a sale line."""

    batch_id: int
    randomid: str
    take: Decimal
    cost: Decimal  # per-unit cost of this batch
    expire: Optional[date]


async def allocate_expiry_fifo(
    session: AsyncSession,
    *,
    branch_id: int,
    drug_id: int,
    qty,
) -> list[Allocation]:
    """Lock the drug's branch_stock + batches and take `qty` FIFO-by-expiry.

    Raises 400 for a non-positive qty and 409 when stock is insufficient or
    unregistered. Must be called inside the sale's transaction.
    """
    qty = dec(qty)
    if qty <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "qty must be positive"
        )

    branch = (
        await session.execute(
            select(BranchStock)
            .where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if branch is None:
        raise NO_STOCK
    if branch.qty < qty:
        raise INSUFFICIENT_STOCK

    rows = (
        await session.execute(
            select(StockBatch)
            .where(
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == drug_id,
                StockBatch.qty > 0,
            )
            .order_by(
                StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id
            )
            .with_for_update()
        )
    ).scalars().all()

    remaining = qty
    allocations: list[Allocation] = []
    for batch in rows:
        if remaining <= 0:
            break
        take = min(batch.qty, remaining)
        allocations.append(
            Allocation(
                batch_id=batch.id,
                randomid=batch.randomid,
                take=take,
                cost=dec(batch.cost),
                expire=batch.expire,
            )
        )
        remaining -= take
    if remaining > 0:
        raise INSUFFICIENT_STOCK
    return allocations


async def decrement_allocations(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    allocations: list[Allocation],
    barcode: str = "",
) -> Decimal:
    """Decrement the given batch allocations + branch_stock; audit each write.

    Returns the exact line COGS (2dp). Used by both the online sale and the
    offline replay path (explicit allocations — no re-running FIFO).
    """
    total_cost = Decimal("0")
    for alloc in allocations:
        batch = await session.get(StockBatch, alloc.batch_id)
        if batch is None:
            raise MISSING_BATCH
        old = dec(batch.qty)
        new = old - alloc.take
        batch.qty = new
        batch.oldstock = old
        session.add(batch)
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="stock_batches",
            entity_id=batch.id,
            field="qty",
            old_value=str(old),
            new_value=str(new),
            drug_id=drug_id,
            barcode=barcode,
            action="sale",
            typevalue=invoice_no,
        )
        total_cost += alloc.take * alloc.cost

    branch = await session.get(BranchStock, (branch_id, drug_id))
    if branch is None:
        raise NO_STOCK
    old = dec(branch.qty)
    new = old - sum(alloc.take for alloc in allocations)
    branch.qty = new
    branch.lastedit = datetime.now(timezone.utc)
    session.add(branch)
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="branch_stock",
        entity_id=drug_id,
        field="qty",
        old_value=str(old),
        new_value=str(new),
        drug_id=drug_id,
        barcode=barcode,
        action="sale",
        typevalue=invoice_no,
    )
    return round2(total_cost)
