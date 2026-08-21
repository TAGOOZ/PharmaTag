"""Day totals report (S3.2, ticket #24; الإجماليات اليومية).

One row per day over a range with the payment splits — cash/network sales,
cash/network returns, manual cash/card, expenses, supplier payments and the
expected drawer cash — plus the day's P&L columns (purchases, discounts,
VAT, COGS, net profit): the Z-report grid across periods. Every figure comes
from the shared bucket engine (`drawer.movements.day_ledgers`), so Σ(rows)
equals `period_ledger` exactly and each row equals that day's `day_ledger`
— the same source `daily_close` snapshots. Money as exact decimal strings.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.drawer.movements import day_ledgers

# The grid's columns, in order: splits first (the handover picture), then
# the day's P&L. Keys are ledger buckets; labels are the Arabic headers.
DAY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("cash_sales", "مبيعات كاش"),
    ("network_sales", "مبيعات شبكة"),
    ("cash_returns", "مرتجعات كاش"),
    ("network_returns", "مرتجعات شبكة"),
    ("manual_cash", "كاش يدوي"),
    ("manual_card", "شبكة يدوي"),
    ("expenses", "مصروفات"),
    ("supplier_payments", "مدفوعات موردين"),
    ("expected_cash", "صافي كاش متوقع"),
    ("purchases", "المشتريات"),
    ("discounts", "الخصومات"),
    ("vat_sales", "ضريبة المبيعات"),
    ("vat_purchases", "ضريبة المشتريات"),
    ("cost_of_sales", "تكلفة المبيعات"),
    ("net_profit", "صافي الربح"),
)


async def day_totals_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Per-day split/P&L rows for (branch, date_from..date_to) + totals."""
    ledgers = await day_ledgers(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )

    keys = [key for key, _ in DAY_COLUMNS]
    days: list[dict] = []
    totals_raw: dict[str, Decimal] = {key: Decimal("0") for key in keys}
    for datee in sorted(ledgers):
        lg = ledgers[datee]
        row = {"datee": datee.isoformat()}
        for key in keys:
            row[key] = money.format2(lg[key])
            totals_raw[key] += lg[key]
        days.append(row)

    totals = {key: money.format2(totals_raw[key]) for key in keys}
    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "days": days,
        "totals": totals,
    }
