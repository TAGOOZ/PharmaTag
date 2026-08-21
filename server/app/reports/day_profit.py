"""Day profit report (S1.9 #15 + S3.2 #24; RPT-OP02 §7 daily-profit inputs).

The profit picture for one (branch, datee) — or across a whole period
(`date_from`/`date_to`, either bound optional): net revenue (sales minus
returns, net of VAT), cost of goods sold, expenses, net profit, VAT and
discounts. The money figures come from the shared drawer ledger buckets
(`period_ledger`, the same source `daily_close` snapshots) so the report,
the day close and the day_totals grid can never disagree; invoice counts
and net revenue are aggregated alongside.

`net_revenue` is VAT-exclusive (sales − returns, both net of VAT) — distinct
from `period_totals`' `net_sales`/`net_purchases`, which are VAT-inclusive
gross totals net of returns.

Window resolution: pass `datee` OR a `date_from`/`date_to` range — mixing
the two is ambiguous (ValueError → 400), an inverted range is 400, and no
params falls back to the business day.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.time import business_date
from app.drawer.movements import period_ledger
from app.models import Invoice


def resolve_window(
    datee: Optional[date], date_from: Optional[date], date_to: Optional[date]
) -> tuple[Optional[date], Optional[date], Optional[date]]:
    """Exactly one mode: a single datee or an ordered from/to range."""
    if datee is not None and (date_from is not None or date_to is not None):
        raise ValueError("pass either datee or a date_from/date_to range, not both")
    if datee is None:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must not be after date_to")
        return date_from, date_to, None
    return None, None, datee


async def _counts(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict[str, int]:
    where = [
        Invoice.branch_id == branch_id,
        Invoice.kind.in_(("sale", "sale_return")),
    ]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)
    rows = (
        await session.execute(
            select(Invoice.kind, func.count(Invoice.id)).where(*where).group_by(Invoice.kind)
        )
    ).all()
    by = {kind: count for kind, count in rows}
    return {"sale": by.get("sale", 0), "sale_return": by.get("sale_return", 0)}


async def day_profit_report(
    session: AsyncSession,
    *,
    branch_id: int,
    datee: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """The day-profit payload (money as exact decimal strings)."""
    date_from, date_to, datee = resolve_window(datee, date_from, date_to)
    if datee is None and date_from is None and date_to is None:
        # ربح اليوم with no params means the business day (the #15 default) —
        # never a lifetime-to-date aggregate.
        datee = business_date()
    ranged = datee is None
    if not ranged:
        date_from = date_to = datee

    ledger = await period_ledger(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )
    net_revenue = money.round2(ledger["sales_net"])

    payload = {
        "branch_id": branch_id,
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
        "expected_cash": money.format2(ledger["expected_cash"]),
        "sales_count": 0,
        "sales_returns_count": 0,
    }
    if ranged:
        payload["date_from"] = date_from.isoformat() if date_from else None
        payload["date_to"] = date_to.isoformat() if date_to else None
    else:
        payload["datee"] = datee.isoformat()
        # the opening float is a per-day figure; Σ of daily floats across a
        # window is meaningless, so ranged payloads omit it
        payload["drawer_start"] = money.format2(ledger["drawer_start"])
    counts = await _counts(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )
    payload["sales_count"] = counts["sale"]
    payload["sales_returns_count"] = counts["sale_return"]
    return payload
