"""Drawer handover report (S1.9, ticket #15; RPT-A04).

Per-cashier drawer totals over a date range: opening float, cash sales, card
sales, returns out, expenses, and net cash (opening + cash sales − returns −
expenses, the expected handover). Each row is one `users` row that recorded
movements in the period; totals roll the whole branch up.
Money as exact decimal strings.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.models import DrawerMovement, User


async def drawer_handover_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Drawer handover per cashier for (branch, date_from..date_to)."""
    where = [DrawerMovement.branch_id == branch_id]
    if date_from is not None:
        where.append(DrawerMovement.datee >= date_from)
    if date_to is not None:
        where.append(DrawerMovement.datee <= date_to)

    rows = (
        await session.execute(
            select(
                DrawerMovement.user_id,
                DrawerMovement.direction,
                DrawerMovement.reason,
                DrawerMovement.method,
                func.coalesce(func.sum(DrawerMovement.amount), 0),
            )
            .where(*where)
            .group_by(
                DrawerMovement.user_id,
                DrawerMovement.direction,
                DrawerMovement.reason,
                DrawerMovement.method,
            )
        )
    ).all()

    per_user: dict[int, dict] = {}
    totals = {
        "opening_in": Decimal("0"),
        "cash_sales_in": Decimal("0"),
        "card_sales_in": Decimal("0"),
        "returns_out": Decimal("0"),
        "expenses_out": Decimal("0"),
        "other_in": Decimal("0"),
        "other_out": Decimal("0"),
    }
    user_ids = sorted({user_id for user_id, *_ in rows if user_id is not None})

    name_by_id: dict[int, str] = {}
    if user_ids:
        users = (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars().all()
        name_by_id = {u.id: u.namee or u.username for u in users}

    for user_id, direction, reason, method, amount in rows:
        key = user_id if user_id is not None else 0
        if key not in per_user:
            per_user[key] = {
                "user_id": user_id,
                "name": name_by_id.get(key, "—") if key else "غير مسجل",
                "opening_in": Decimal("0"),
                "cash_sales_in": Decimal("0"),
                "card_sales_in": Decimal("0"),
                "returns_out": Decimal("0"),
                "expenses_out": Decimal("0"),
                "other_in": Decimal("0"),
                "other_out": Decimal("0"),
            }
        bucket = _bucket(direction, reason, method)
        per_user[key][bucket] += money.dec(amount)
        totals[bucket] += money.dec(amount)

    cashiers = []
    for key in sorted(per_user):
        row = per_user[key]
        net_cash = money.round2(
            row["opening_in"] + row["cash_sales_in"] - row["returns_out"] - row["expenses_out"]
        )
        cashiers.append(
            {
                "user_id": row["user_id"],
                "name": row["name"],
                "opening_in": money.format2(row["opening_in"]),
                "cash_sales_in": money.format2(row["cash_sales_in"]),
                "card_sales_in": money.format2(row["card_sales_in"]),
                "returns_out": money.format2(row["returns_out"]),
                "expenses_out": money.format2(row["expenses_out"]),
                "net_cash": money.format2(net_cash),
            }
        )

    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "cashiers": cashiers,
        "totals": {
            "opening_in": money.format2(totals["opening_in"]),
            "cash_sales_in": money.format2(totals["cash_sales_in"]),
            "card_sales_in": money.format2(totals["card_sales_in"]),
            "returns_out": money.format2(totals["returns_out"]),
            "expenses_out": money.format2(totals["expenses_out"]),
        },
    }


def _bucket(direction: str, reason: str, method: str) -> str:
    if direction == "in" and reason == "opening":
        return "opening_in"
    if direction == "in" and reason == "cash_sale" and method == "cash":
        return "cash_sales_in"
    if direction == "in" and reason == "cash_sale" and method == "network":
        return "card_sales_in"
    if direction == "out" and reason == "cash_return":
        return "returns_out"
    if direction == "out" and reason == "expense":
        return "expenses_out"
    if direction == "in":
        return "other_in"
    return "other_out"
