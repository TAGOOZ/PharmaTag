"""Day close + guarded reopen (S1.8, ticket #14, A07).

`close_day` snapshots the drawer equation into `daily_close` for a
(branch, datee) — the row is locked by `uq_daily_close`, so a date closes once
per branch (409 on a second close). Reopen is manager-only (perm >= 7, enforced
at the router) and always writes a reversal (the close flips to `reopened`) +
an audit row, so the closed day is never silently re-opened; a reopened day can
accept new movements and be closed again.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import atomic
from app.core.money import dec, format2
from app.drawer.movements import day_ledger
from app.models import DailyClose
from app.sales.numbering import acquire_branch_lock

ALREADY_CLOSED = HTTPException(
    status.HTTP_409_CONFLICT, "this day is already closed"
)
NOT_CLOSED = HTTPException(
    status.HTTP_409_CONFLICT, "only a closed day can be reopened"
)


async def _find_close(
    session: AsyncSession, *, branch_id: int, datee: date
) -> Optional[DailyClose]:
    return (
        await session.execute(
            select(DailyClose).where(
                DailyClose.branch_id == branch_id, DailyClose.datee == datee
            )
        )
    ).scalar_one_or_none()


async def close_day(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: int,
    datee: date,
    counted_cash,
) -> DailyClose:
    """Compute the drawer equation + day totals and lock the day as closed."""
    counted = dec(counted_cash)
    if counted < 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "counted_cash cannot be negative"
        )
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        existing = await _find_close(session, branch_id=branch_id, datee=datee)
        if existing is not None and existing.status == "closed":
            raise ALREADY_CLOSED

        ledger = await day_ledger(session, branch_id=branch_id, datee=datee)
        difference = round(dec(counted) - dec(ledger["expected_cash"]), 2)
        if existing is not None:
            row = existing  # reopened -> close again
        else:
            row = DailyClose(
                branch_id=branch_id, datee=datee, drawer_start=ledger["drawer_start"]
            )
            session.add(row)
        row.expected_cash = ledger["expected_cash"]
        row.counted_cash = counted
        row.difference = difference
        row.net_cash = ledger["net_cash"]
        row.net_network = ledger["net_network"]
        row.manual_cash = ledger["manual_cash"]
        row.manual_card = ledger["manual_card"]
        row.purchases = ledger["purchases"]
        row.expenses = ledger["expenses"]
        row.cost_of_sales = ledger["cost_of_sales"]
        row.net_profit = ledger["net_profit"]
        row.discounts = ledger["discounts"]
        row.vat_sales = ledger["vat_sales"]
        row.vat_purchases = ledger["vat_purchases"]
        row.vat_expenses = ledger["vat_expenses"]
        row.status = "closed"
        row.closed_by = user_id
        row.closed_at = datetime.now(timezone.utc)
        await session.flush()

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="daily_close",
            entity_id=row.id,
            action="close",
            new_value=(
                f"datee={datee} expected={format2(row.expected_cash)} "
                f"counted={format2(row.counted_cash)} "
                f"difference={format2(row.difference)}"
            ),
            typevalue=datee.isoformat(),
        )
    return row


async def reopen_day(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: int,
    daily_close_id: int,
) -> DailyClose:
    """Manager-only reopen: reverses the close (status -> reopened) + audit."""
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        row = await session.get(DailyClose, daily_close_id)
        if row is None or row.branch_id != branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "day close not found")
        if row.status != "closed":
            raise NOT_CLOSED
        row.status = "reopened"
        row.closed_by = None
        row.closed_at = None
        await session.flush()

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="daily_close",
            entity_id=row.id,
            action="reopen",
            old_value="closed",
            new_value="reopened — reversal of the day close",
            typevalue=row.datee.isoformat(),
        )
    return row