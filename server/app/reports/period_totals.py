"""Sales/purchases period-totals report (S1.9, ticket #15; RPT-OP01/OP03).

Counts + totals per invoice kind over a date range: sales, sales returns,
purchases, purchase returns, and the net figures (net sales/purchases, VAT
net of returns). Read-only over `invoices`; money as exact decimal strings.

`net_sales`/`net_purchases` are VAT-INCLUSIVE gross totals net of returns
(sale total − sale return total) — unlike `day_profit`'s VAT-exclusive
`net_revenue`.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money

from app.models import Invoice

_KINDS = ("sale", "sale_return", "purchase", "purchase_return")


async def period_totals_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Period totals for (branch, date_from..date_to)."""
    where = [Invoice.branch_id == branch_id]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)

    rows = (
        await session.execute(
            select(
                Invoice.kind,
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.totalvalue), 0),
                func.coalesce(func.sum(Invoice.vat), 0),
                func.coalesce(func.sum(Invoice.discount), 0),
            )
            .where(*where)
            .group_by(Invoice.kind)
        )
    ).all()

    by = {
        kind: {
            "count": 0,
            "total": money.dec("0"),
            "vat": money.dec("0"),
            "discount": money.dec("0"),
        }
        for kind in _KINDS
    }
    for kind, count, total, vat, discount in rows:
        if kind in by:
            by[kind] = {
                "count": count,
                "total": money.dec(total),
                "vat": money.dec(vat),
                "discount": money.dec(discount),
            }

    kinds = {
        kind: {
            "count": by[kind]["count"],
            "total": money.format2(by[kind]["total"]),
            "vat": money.format2(by[kind]["vat"]),
            "discount": money.format2(by[kind]["discount"]),
        }
        for kind in _KINDS
    }

    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "kinds": kinds,
        "net_sales": money.format2(by["sale"]["total"] - by["sale_return"]["total"]),
        "net_purchases": money.format2(
            by["purchase"]["total"] - by["purchase_return"]["total"]
        ),
        "net_vat_sales": money.format2(by["sale"]["vat"] - by["sale_return"]["vat"]),
        "net_vat_purchases": money.format2(
            by["purchase"]["vat"] - by["purchase_return"]["vat"]
        ),
        "net_discounts": money.format2(
            by["sale"]["discount"] - by["sale_return"]["discount"]
        ),
    }
