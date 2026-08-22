"""Minimum-based needs report (S3.3 #25): احتياجات الطلب.

The S1.9 below-minimum shortage list (`stock_minimum`) reshaped as an
order worksheet: each row adds `suggested_order` = max(minimum − qty, 0)
and the latest purchase cost for the drug on the branch (falling back to
the drug-master cost when nothing was purchased yet).

Sales-rate-based auto-order suggestions are OUT of scope — they belong to
the chain auto-order engine (#33, F06.3).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.models import BranchStock, StockBatch
from app.reports.stock_minimum import _MAX_ITEMS, _shortage_rows


async def _last_purchase_costs(
    session: AsyncSession, *, branch_id: int, drug_ids: list[int]
) -> dict[int, object]:
    """drug_id → cost of its most recent purchase lot (one query; ids are
    monotonic so max(id) per drug is the latest lot). Empty when a drug was
    never purchased."""
    if not drug_ids:
        return {}
    latest_ids = (
        select(func.max(StockBatch.id).label("bid"))
        .where(
            StockBatch.branch_id == branch_id,
            StockBatch.typee == "purchase",
            StockBatch.drug_id.in_(drug_ids),
        )
        .group_by(StockBatch.drug_id)
        .subquery()
    )
    rows = await session.execute(
        select(StockBatch.drug_id, StockBatch.cost).where(
            StockBatch.id.in_(select(latest_ids.c.bid))
        )
    )
    return {drug_id: cost for drug_id, cost in rows.all()}


async def stock_needs_report(session: AsyncSession, *, branch_id: int) -> dict:
    """The order-needs worksheet for the branch."""
    total, rows = await _shortage_rows(session, branch_id=branch_id)
    costs = await _last_purchase_costs(
        session, branch_id=branch_id, drug_ids=[stock.drug_id for stock, _ in rows]
    )
    # whole-branch suggested quantity in SQL — correct even when the row
    # list is truncated by the cap (mirrors stock_current's total_value)
    suggested_total = money.dec(
        (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(func.greatest(BranchStock.minimum - BranchStock.qty, 0)),
                        0,
                    )
                ).where(
                    BranchStock.branch_id == branch_id,
                    BranchStock.qty < BranchStock.minimum,
                )
            )
        ).scalar_one()
    )
    items = []
    for stock, drug in rows:
        primary = next(
            (
                b.barcode
                for b in sorted(drug.barcodes, key=lambda b: not b.is_primary)
            ),
            "",
        )
        suggested = max(money.dec(stock.minimum) - money.dec(stock.qty), money.dec("0"))
        # latest purchase cost, falling back to the drug-master cost
        cost = costs.get(stock.drug_id)
        if cost is None:
            cost = drug.price_cost
        items.append(
            {
                "drug_id": drug.id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear or "",
                "barcode": primary,
                "classy": drug.classy or "",
                "qty": format(money.round4(stock.qty), "f"),
                "minimum": format(money.round4(stock.minimum), "f"),
                "shortage": format(money.round4(suggested), "f"),
                "suggested_order": format(money.round4(suggested), "f"),
                "last_cost": (
                    format(money.round4(cost), "f") if cost is not None else None
                ),
            }
        )

    return {
        "branch_id": branch_id,
        "count": total,
        "truncated": total > _MAX_ITEMS,
        "suggested_total": format(money.round4(suggested_total), "f"),
        "items": items,
    }
