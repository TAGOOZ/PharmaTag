"""Return stock-down: decrement the purchased batch + branch_stock (S1.6).

A purchase return is the exact reverse of the purchase: it removes the returned
quantity from the batch the original purchase line CREATED (`batch_id` on the
line) and lowers `branch_stock` by the same amount. Unlike a sales return there
is no NEW batch — the goods physically leave the store back to the supplier.

Both helpers validate sufficiency (you can't return more than the batch
physically holds, which also caps the batch after partial sales) and write
their `audit_log` row in the caller's transaction (G12).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.audit import ACTION_INSERT, audit, enqueue_sync
from app.models import BranchStock, DrugBarcode, StockBatch

BATCH_MISSING = HTTPException(
    status.HTTP_409_CONFLICT, "purchase batch missing on this store"
)
INSUFFICIENT_BATCH = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "cannot return more than the quantity left in the batch",
)
INSUFFICIENT_STOCK = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "cannot return more than the branch stock on hand",
)


async def _primary_barcode(session: AsyncSession, drug_id: int) -> str:
    """The drug's primary barcode, used for audit/batch provenance."""
    row = (
        await session.execute(
            select(DrugBarcode).where(
                DrugBarcode.drug_id == drug_id,
                DrugBarcode.is_primary.is_(True),
            )
        )
    ).scalars().first()
    return row.barcode if row else ""


async def decrement_purchase_batch(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    batch_id: int,
    drug_id: int,
    qty,
    barcode: str = "",
) -> StockBatch:
    """Lower one purchase batch's qty by `qty` (locking FOR UPDATE); rejects a
    return that would push the batch below zero."""
    batch = (
        await session.execute(
            select(StockBatch)
            .where(
                StockBatch.id == batch_id,
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == drug_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if batch is None:
        raise BATCH_MISSING
    qty_d = Decimal(qty)
    if qty_d > Decimal(batch.qty or 0):
        raise INSUFFICIENT_BATCH
    old = Decimal(batch.qty or 0)
    new = old - qty_d
    batch.qty = new
    batch.lastedit = datetime.now(timezone.utc)
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
        action="purchase_return",
        typevalue=invoice_no,
    )
    return batch


async def decrease_branch_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    qty_delta,
    barcode: str = "",
) -> BranchStock:
    """Lower the drug's branch_stock by `qty_delta` (locking FOR UPDATE)."""
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
    if row is None or Decimal(qty_delta) > Decimal(row.qty or 0):
        raise INSUFFICIENT_STOCK
    old = Decimal(row.qty or 0)
    new = old - Decimal(qty_delta)
    row.qty = new
    row.lastedit = datetime.now(timezone.utc)
    session.add(row)
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
        action="purchase_return",
        typevalue=invoice_no,
    )
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="branch_stock",
        entity_id=drug_id,
        action="purchase_return",
        payload={
            "branch_id": branch_id,
            "drug_id": drug_id,
            "qty": format(money.round4(new), "f"),
            "minimum": format(money.round4(row.minimum or 0), "f"),
            "silsilaid": row.silsilaid or "",
            "classy": row.classy or "",
        },
    )
    return row