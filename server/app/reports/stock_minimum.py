"""Stock-below-minimum report (S1.9, ticket #15; RPT-ST01).

Branch drugs whose current qty is below the reorder point: qty, minimum,
shortage = minimum − qty, price, sorted by shortage descending. Read-only over
`branch_stock` joined to the drug master.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import money
from app.models import BranchStock, Drug

_MAX_ITEMS = 1000


async def stock_minimum_report(
    session: AsyncSession, *, branch_id: int
) -> dict:
    """The shortage list for the branch (empty when nothing is below minimum)."""
    rows = (
        await session.execute(
            select(BranchStock, Drug)
            .join(Drug, Drug.id == BranchStock.drug_id)
            .where(
                BranchStock.branch_id == branch_id,
                BranchStock.qty < BranchStock.minimum,
            )
            .options(selectinload(Drug.barcodes))
            .order_by(
                (BranchStock.minimum - BranchStock.qty).desc(), Drug.drugname
            )
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
        shortage = money.round4(money.dec(stock.minimum) - money.dec(stock.qty))
        items.append(
            {
                "drug_id": drug.id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear or "",
                "barcode": primary,
                "classy": drug.classy or "",
                "qty": format(money.round4(stock.qty), "f"),
                "minimum": format(money.round4(stock.minimum), "f"),
                "shortage": format(shortage, "f"),
                "price": format(money.round4(drug.price), "f") if drug.price else "0.0000",
            }
        )

    return {"branch_id": branch_id, "count": len(items), "items": items}
