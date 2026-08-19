"""Day profit report (S1.9, ticket #15; RPT-OP02 §7 daily-profit inputs).

The day's profit picture for one (branch, datee): net revenue (sales minus
returns, net of VAT), cost of goods sold, expenses, net profit, VAT and
discounts. The money figures reuse the drawer day ledger (`day_ledger`, the
same source `daily_close` snapshots) so the report and the day close can never
disagree; invoice counts and net revenue are aggregated here.

`net_revenue` is VAT-exclusive (sales − returns, both net of VAT) — distinct
from `period_totals`' `net_sales`/`net_purchases`, which are VAT-inclusive
gross totals net of returns.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.time import business_date
from app.drawer.movements import day_ledger
from app.models import Invoice

_KINDS = ("sale", "sale_return")


async def day_profit_report(
    session: AsyncSession, *, branch_id: int, datee: Optional[date]
) -> dict:
    """The day-profit report payload (money as exact decimal strings)."""
    datee = datee or business_date()
    ledger = await day_ledger(session, branch_id=branch_id, datee=datee)

    rows = (
        await session.execute(
            select(
                Invoice.kind,
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.totalvalue), 0),
                func.coalesce(func.sum(Invoice.vat), 0),
            )
            .where(
                Invoice.branch_id == branch_id,
                Invoice.datee == datee,
                Invoice.kind.in_(_KINDS),
            )
            .group_by(Invoice.kind)
        )
    ).all()
    by = {kind: {"count": 0, "total": money.dec("0"), "vat": money.dec("0")} for kind in _KINDS}
    for kind, count, total, vat in rows:
        if kind in by:
            by[kind] = {"count": count, "total": money.dec(total), "vat": money.dec(vat)}

    net_revenue = money.round2(
        (by["sale"]["total"] - by["sale"]["vat"])
        - (by["sale_return"]["total"] - by["sale_return"]["vat"])
    )

    return {
        "branch_id": branch_id,
        "datee": datee.isoformat(),
        "sales_count": by["sale"]["count"],
        "sales_returns_count": by["sale_return"]["count"],
        "net_revenue": money.format2(net_revenue),
        "cogs": money.format2(ledger["cost_of_sales"]),
        "expenses": money.format2(ledger["expenses"]),
        "net_profit": money.format2(ledger["net_profit"]),
        "discounts": money.format2(ledger["discounts"]),
        "vat_sales": money.format2(ledger["vat_sales"]),
        "vat_purchases": money.format2(ledger["vat_purchases"]),
        "purchases": money.format2(ledger["purchases"]),
        "net_cash": money.format2(ledger["net_cash"]),
        "net_network": money.format2(ledger["net_network"]),
        "manual_cash": money.format2(ledger["manual_cash"]),
        "manual_card": money.format2(ledger["manual_card"]),
        "drawer_start": money.format2(ledger["drawer_start"]),
        "expected_cash": money.format2(ledger["expected_cash"]),
    }
