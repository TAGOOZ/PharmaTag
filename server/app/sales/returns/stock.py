"""Return stock-up: NEW return batches + branch_stock raise (plan/05 §S1.5).

A sales return restores stock as a NEW `stock_batches` row (`typee='return'`,
fresh randomid `r-<invoice_no>-<idx>`) — it never re-fills the consumed sale
batch (the reversal is its own document). The batch cost is the original sale
line's unit cost, so future COGS from returned stock uses the same value that
was consumed. Both helpers audit inside the caller's transaction (G12).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.models import BranchStock, DrugBarcode, StockBatch

BATCH_DUP = HTTPException(
    status.HTTP_409_CONFLICT, "a batch with this reference already exists"
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


async def create_return_batch(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    idx: int,
    drug_id: int,
    qty,
    cost: Decimal,
    price: Decimal,
    vat_rate: Decimal,
    vat_amount,
    total_with_vat,
    expire,
    barcode: str = "",
) -> StockBatch:
    """Create one NEW return batch (randomid r-<invoice_no>-<idx>); rejects dup."""
    randomid = f"r-{invoice_no}-{idx}"
    existing = (
        await session.execute(
            select(StockBatch.id).where(
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == drug_id,
                StockBatch.randomid == randomid,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise BATCH_DUP
    batch = StockBatch(
        branch_id=branch_id,
        drug_id=drug_id,
        randomid=randomid,
        qty=Decimal(qty),
        expire=expire,
        cost=Decimal(cost),
        vat=Decimal(vat_rate),
        price=Decimal(price),
        oldstock=Decimal("0"),
        typee="return",
        vatvalue=Decimal(vat_amount),
        totalwithvat=Decimal(total_with_vat),
        created_by=user_id,
    )
    session.add(batch)
    await session.flush()
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="stock_batches",
        entity_id=batch.id,
        field="qty",
        old_value="0.0000",
        new_value=str(qty),
        drug_id=drug_id,
        barcode=barcode,
        action="return",
        typevalue=invoice_no,
    )
    return batch


async def raise_branch_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    qty_delta,
    barcode: str = "",
) -> BranchStock:
    """Add `qty_delta` back to the drug's branch_stock (locking FOR UPDATE)."""
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
        row = BranchStock(
            branch_id=branch_id,
            drug_id=drug_id,
            qty=Decimal("0"),
            minimum=Decimal("0"),
        )
        session.add(row)
        await session.flush()
    old = Decimal(row.qty)
    new = old + Decimal(qty_delta)
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
        action="return",
        typevalue=invoice_no,
    )
    return row