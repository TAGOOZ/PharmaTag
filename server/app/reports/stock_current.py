"""Current-stock report (S3.3 #25): رصيد الأصناف.

Every drug on the branch with its running qty (`branch_stock`) and its
stock value at batch cost — Σ `stock_batches.qty × cost` over positive
batches (the same lots sales consume FIFO by expiry). Zero-qty drugs are
included so the sheet doubles as a full item list; sorted by name.

The list is capped at `_MAX_ITEMS` rows; `count` is always the TRUE
number of branch drugs and `truncated` says whether the cap cut the list.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import money
from app.models import BranchStock, Drug, StockBatch

_MAX_ITEMS = 1000


async def _stock_value(session: AsyncSession, *, branch_id: int) -> dict[int, str]:
    """drug_id → Σ(qty × cost) over its positive batches, 2dp string."""
    rows = await session.execute(
        select(
            StockBatch.drug_id,
            func.sum(StockBatch.qty * StockBatch.cost).label("value"),
        )
        .where(StockBatch.branch_id == branch_id, StockBatch.qty > 0)
        .group_by(StockBatch.drug_id)
    )
    return {
        drug_id: format(money.round2(value or 0), "f")
        for drug_id, value in rows.all()
    }


async def _branch_stock_value(
    session: AsyncSession, *, branch_id: int
) -> str:
    """Σ(qty × cost) over ALL positive batches on the branch — computed in
    SQL so the printed total is whole-branch even when the row list is
    truncated by the cap."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(StockBatch.qty * StockBatch.cost), 0)).where(
                StockBatch.branch_id == branch_id,
                StockBatch.qty > 0,
            )
        )
    ).scalar_one()
    return format(money.round2(total), "f")


async def stock_current_report(session: AsyncSession, *, branch_id: int) -> dict:
    """The branch stock sheet (empty when the branch stocks nothing)."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(BranchStock)
            .where(BranchStock.branch_id == branch_id)
        )
    ).scalar_one()
    values = await _stock_value(session, branch_id=branch_id)
    branch_total = await _branch_stock_value(session, branch_id=branch_id)

    rows = (
        await session.execute(
            select(BranchStock, Drug)
            .join(Drug, Drug.id == BranchStock.drug_id)
            .where(BranchStock.branch_id == branch_id)
            .options(selectinload(Drug.barcodes))
            .order_by(Drug.drugname)
            .limit(_MAX_ITEMS)
        )
    ).all()

    items = []
    for stock, drug in rows:
        primary = next(
            (
                b.barcode
                for b in sorted(drug.barcodes, key=lambda b: not b.is_primary)
            ),
            "",
        )
        items.append(
            {
                "drug_id": drug.id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear or "",
                "barcode": primary,
                "classy": drug.classy or "",
                "qty": format(money.round4(stock.qty or 0), "f"),
                "value": values.get(drug.id, "0.00"),
                "price": format(money.round4(drug.price), "f") if drug.price else "0.0000",
            }
        )

    return {
        "branch_id": branch_id,
        "count": total,
        "truncated": total > _MAX_ITEMS,
        "total_value": branch_total,
        "items": items,
    }
