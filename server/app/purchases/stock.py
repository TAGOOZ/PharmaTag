"""Purchase stock-up: create NEW batches and upsert branch_stock (plan/02 §4.2).

The purchase rule (slicing plan §S1.4): a purchase RAISES stock as new
stock_batches rows (fresh randomid) and never overwrites existing batch stock.
The batch's `cost` is the NET (ex-VAT) unit cost — the inventory value that
later sale COGS is computed from; `price` keeps the gross unit cost as charged
by the supplier; `vatvalue`/`totalwithvat` carry the per-line input VAT and
inclusive total.

Both helpers write their `audit_log` row in the caller's transaction (G12).
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


async def create_purchase_batch(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    randomid: str,
    qty,
    cost: Decimal,
    price: Decimal,
    vat_rate: Decimal,
    vat_amount,
    total_with_vat,
    expire,
    barcode: str = "",
) -> StockBatch:
    """Create one NEW purchase batch; rejects a duplicate (branch, drug, randomid)."""
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
        typee="purchase",
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
        action="purchase",
        typevalue=invoice_no,
    )
    return batch


async def upsert_branch_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    qty_delta,
    barcode: str = "",
) -> BranchStock:
    """Add `qty_delta` to the drug's branch_stock, creating the row if the drug
    never had stock before. Locks the row FOR UPDATE so concurrent writes on
    the same drug serialize on the running total."""
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
        action="purchase",
        typevalue=invoice_no,
    )
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="branch_stock",
        entity_id=drug_id,
        action="purchase",
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
