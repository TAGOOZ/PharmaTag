"""Auto-order suggestion engine (#33; F06 half-auto + sales-rate, N1/N3).

Two modes over the caller's branch stock:

* `minimum` (half-auto, F06.2): every `branch_stock` row with
  `qty < minimum` suggests a top-up back to par (`minimum − qty`).
* `sales_rate` (automatic, F06.3): velocity = sold qty over the trailing
  window ÷ window days; suggested = velocity × coverage − on_hand, only when
  positive. Egypt daily-replenishment defaults: window 14d, coverage 7d
  (same-day distributor drops make weekly-cycle Western defaults wrong).

Suggestions are read-only advice — converting them into needs or purchase
orders goes through the normal POST endpoints (N3).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import round4
from app.models import BranchStock, Invoice, InvoiceLine

MODES = ("minimum", "sales_rate")
DEFAULT_WINDOW_DAYS = 14
DEFAULT_COVERAGE_DAYS = 7


class UnknownMode(ValueError):
    pass


async def suggest(
    session: AsyncSession,
    *,
    branch_id: int,
    mode: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    coverage_days: int = DEFAULT_COVERAGE_DAYS,
) -> list[dict]:
    if mode not in MODES:
        raise UnknownMode(mode)

    stock = (
        await session.execute(
            select(BranchStock.drug_id, BranchStock.qty, BranchStock.minimum).where(
                BranchStock.branch_id == branch_id
            )
        )
    ).all()
    on_hand = {drug_id: qty for drug_id, qty, _ in stock}
    minimums = {drug_id: minimum for drug_id, _, minimum in stock}

    suggestions: list[dict] = []
    if mode == "minimum":
        for drug_id, qty, minimum in stock:
            if (minimum or 0) > Decimal("0") and (qty or 0) < (minimum or 0):
                suggestions.append(
                    {
                        "drug_id": drug_id,
                        "on_hand": format(round4(qty or 0), "f"),
                        "minimum": format(round4(minimum or 0), "f"),
                        "avg_daily": None,
                        "suggested_qty": format(round4((minimum or 0) - (qty or 0)), "f"),
                    }
                )
        return suggestions

    # sales_rate: sold quantity per drug over the trailing window at this branch
    since = date.today() - timedelta(days=window_days)
    rows = (
        await session.execute(
            select(InvoiceLine.drug_id, func.sum(InvoiceLine.qty))
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .where(
                InvoiceLine.branch_id == branch_id,
                Invoice.kind == "sale",
                Invoice.datee >= since,
            )
            .group_by(InvoiceLine.drug_id)
        )
    ).all()
    window = Decimal(window_days)
    coverage = Decimal(coverage_days)
    for drug_id, sold in rows:
        avg_daily = round4(Decimal(sold) / window)
        target = round4(avg_daily * coverage)
        current = on_hand.get(drug_id, Decimal("0"))
        gap = target - current
        if gap <= Decimal("0"):
            continue
        suggestions.append(
            {
                "drug_id": drug_id,
                "on_hand": format(round4(current), "f"),
                "minimum": format(round4(minimums.get(drug_id, Decimal("0"))), "f"),
                "avg_daily": format(avg_daily, "f"),
                "suggested_qty": format(gap, "f"),
            }
        )
    return suggestions
