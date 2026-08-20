"""Month close + reopen + month-open-balances (S2.6, issue #21).

A branch closes a month: the `monthly_close` row archives the period (status
closed — the month snapshot, mirrors `\\Files\\Archive\\monthy\\moves`) and
`month_open_balances` seeds the following month's opening balances (mirrors
`\\Files\\Archive\\monthy\\start-data`) from the branch's closing ledger state
(cumulative debit/credit per account through the end of the closed month).

A closed month rejects further journal posts: `post_journal` (the shared engine
used by sales / purchases / returns / settlements / manual journals / stock
corrections) calls `guard_open_month` so the ledger can never be mutated after
the period freezes. Reopen is manager-only (perm >= 7, A07), flips status to
`reopened` + audit and reopens the period; re-close regenerates the start-data.

All writes ride the branch advisory lock (plan/02 monotonic entry numbers) so
close / post / reopen never race.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import atomic
from app.core.money import dec, format2
from app.models import Account, JournalLine, MonthOpenBalance, MonthlyClose
from app.sales.numbering import acquire_branch_lock

ALREADY_CLOSED = HTTPException(status.HTTP_409_CONFLICT, "month is already closed")
NOT_CLOSED = HTTPException(status.HTTP_409_CONFLICT, "only a closed month can be reopened")
CLOSED_GUARD = HTTPException(status.HTTP_409_CONFLICT, "month is closed; reopen it before posting")
_ZERO = Decimal("0")


def _validate_month(month: int) -> None:
    if not 1 <= month <= 12:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "month must be between 1 and 12")


def _end_of(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month, 1).replace(day=calendar.monthrange(year, month)[1])


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


async def guard_open_month(session: AsyncSession, *, branch_id: int, datee: date) -> None:
    """Raise 409 if (branch, datee.year, datee.month) monthly_close.status is
    closed — a closed month takes no new journals. Reopened (or absent) allows
    posting. Acquires the branch advisory lock so the check is atomic with the
    close (idempotent re-acquisition in the caller's transaction)."""
    await acquire_branch_lock(session, branch_id)
    row = (
        await session.execute(
            select(MonthlyClose.status).where(
                MonthlyClose.branch_id == branch_id,
                MonthlyClose.year == datee.year,
                MonthlyClose.month == datee.month,
            )
        )
    ).scalar_one_or_none()
    if row == "closed":
        raise CLOSED_GUARD


async def _closing_per_account(
    session: AsyncSession, *, branch_id: int, year: int, month: int
) -> dict[int, tuple[Decimal, Decimal]]:
    """Cumulative debit/credit per account_id through the end of (year, month)
    from `journal_lines` — the closing state of the month."""
    end = _end_of(year, month)
    rows = (
        await session.execute(
            select(
                JournalLine.account_id,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .where(JournalLine.branch_id == branch_id, JournalLine.datee <= end)
            .group_by(JournalLine.account_id)
        )
    ).all()
    return {aid: (dec(d), dec(c)) for aid, d, c in rows}


def _serialize_close(
    row: MonthlyClose, open_rows: list[MonthOpenBalance], account_by_id: dict[int, Account]
) -> dict:
    ny, nm = _next_month(row.year, row.month)
    next_rows = [
        {
            "account_id": r.account_id,
            "code": account_by_id.get(r.account_id).code if r.account_id in account_by_id else "",
            "name_ar": account_by_id.get(r.account_id).name_ar if r.account_id in account_by_id else "",
            "name_en": account_by_id.get(r.account_id).name_en if r.account_id in account_by_id else "",
            "debit": format2(r.debit),
            "credit": format2(r.credit),
        }
        for r in sorted(open_rows, key=lambda r: account_by_id.get(r.account_id).code if r.account_id in account_by_id else str(r.account_id))
    ]
    return {
        "branch_id": row.branch_id,
        "year": row.year,
        "month": row.month,
        "status": row.status,
        "closed_by": row.closed_by,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "next_open_balances": {
            "year": ny,
            "month": nm,
            "rows": next_rows,
            "total_debit": format2(sum((dec(r["debit"]) for r in next_rows), _ZERO)),
            "total_credit": format2(sum((dec(r["credit"]) for r in next_rows), _ZERO)),
        },
    }


async def _load_next_balances(
    session: AsyncSession, *, branch_id: int, year: int, month: int
) -> tuple[list[MonthOpenBalance], dict[int, Account]]:
    ny, nm = _next_month(year, month)
    rows = (
        await session.execute(
            select(MonthOpenBalance).where(
                MonthOpenBalance.branch_id == branch_id,
                MonthOpenBalance.year == ny,
                MonthOpenBalance.month == nm,
            )
        )
    ).scalars().all()
    ids = {r.account_id for r in rows}
    accounts = (
        (await session.execute(select(Account).where(Account.id.in_(ids)))).scalars().all()
        if ids
        else []
    )
    return list(rows), {a.id: a for a in accounts}


def _serialize_simple(row: MonthlyClose) -> dict:
    return {
        "branch_id": row.branch_id,
        "year": row.year,
        "month": row.month,
        "status": row.status,
        "closed_by": row.closed_by,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


async def close_month(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: int,
    year: int,
    month: int,
) -> dict:
    """Close (branch, year, month): write monthly_close + seed next month's
    month_open_balances from the closing ledger state, atomically under the
    branch lock with an audit row (G12). 409 if already closed."""
    _validate_month(month)
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        existing = (
            await session.execute(
                select(MonthlyClose).where(
                    MonthlyClose.branch_id == branch_id,
                    MonthlyClose.year == year,
                    MonthlyClose.month == month,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and existing.status == "closed":
            raise ALREADY_CLOSED

        closing = await _closing_per_account(session, branch_id=branch_id, year=year, month=month)
        ny, nm = _next_month(year, month)

        # regenerate the next month's start-data: delete + re-insert so a
        # re-close after reopen (where new postings changed the closing state)
        # never leaves stale zero rows.
        old = (
            await session.execute(
                select(MonthOpenBalance).where(
                    MonthOpenBalance.branch_id == branch_id,
                    MonthOpenBalance.year == ny,
                    MonthOpenBalance.month == nm,
                )
            )
        ).scalars().all()
        for r in old:
            await session.delete(r)
        await session.flush()

        for account_id, (debit, credit) in closing.items():
            if debit == _ZERO and credit == _ZERO:
                continue
            session.add(
                MonthOpenBalance(
                    branch_id=branch_id,
                    account_id=account_id,
                    year=ny,
                    month=nm,
                    debit=debit,
                    credit=credit,
                )
            )
        await session.flush()

        if existing is not None:
            row = existing  # reopened -> close again
        else:
            row = MonthlyClose(branch_id=branch_id, year=year, month=month)
            session.add(row)
        row.status = "closed"
        row.closed_by = user_id
        row.closed_at = datetime.now(timezone.utc)
        await session.flush()

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="monthly_close",
            entity_id=row.branch_id,
            action="close",
            new_value=f"year={year} month={month} status=closed",
            typevalue=f"{year}-{month:02d}",
        )

        open_rows, by_id = await _load_next_balances(session, branch_id=branch_id, year=year, month=month)
        return _serialize_close(row, open_rows, by_id)


async def reopen_month(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: int,
    year: int,
    month: int,
) -> dict:
    """Manager-only reopen (A07): flip a closed month to reopened + audit so
    the period can accept new postings and be re-closed."""
    _validate_month(month)
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        row = (
            await session.execute(
                select(MonthlyClose).where(
                    MonthlyClose.branch_id == branch_id,
                    MonthlyClose.year == year,
                    MonthlyClose.month == month,
                )
            )
        ).scalar_one_or_none()
        if row is None or row.status != "closed":
            raise NOT_CLOSED
        row.status = "reopened"
        row.closed_by = None
        row.closed_at = None
        await session.flush()

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="monthly_close",
            entity_id=row.branch_id,
            action="reopen",
            old_value="closed",
            new_value="reopened — reversal of the month close",
            typevalue=f"{year}-{month:02d}",
        )
        return _serialize_simple(row)


async def get_month_close(
    session: AsyncSession, *, branch_id: int, year: int, month: int
) -> dict:
    _validate_month(month)
    row = (
        await session.execute(
            select(MonthlyClose).where(
                MonthlyClose.branch_id == branch_id,
                MonthlyClose.year == year,
                MonthlyClose.month == month,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "month close not found")
    open_rows, by_id = await _load_next_balances(session, branch_id=branch_id, year=year, month=month)
    return _serialize_close(row, open_rows, by_id)


async def list_month_closes(session: AsyncSession, *, branch_id: int) -> list[dict]:
    rows = (
        await session.execute(
            select(MonthlyClose)
            .where(MonthlyClose.branch_id == branch_id)
            .order_by(MonthlyClose.year.desc(), MonthlyClose.month.desc())
        )
    ).scalars().all()
    return [_serialize_simple(r) for r in rows]


async def get_open_balances(
    session: AsyncSession, *, branch_id: int, year: int, month: int
) -> dict:
    """The opening balances FOR (year, month) — i.e. month_open_balances rows
    for that month (seeded when the preceding month closed)."""
    _validate_month(month)
    rows = (
        await session.execute(
            select(MonthOpenBalance).where(
                MonthOpenBalance.branch_id == branch_id,
                MonthOpenBalance.year == year,
                MonthOpenBalance.month == month,
            )
        )
    ).scalars().all()
    ids = {r.account_id for r in rows}
    accounts = (
        (await session.execute(select(Account).where(Account.id.in_(ids)))).scalars().all()
        if ids
        else []
    )
    by_id = {a.id: a for a in accounts}
    out = [
        {
            "account_id": r.account_id,
            "code": by_id.get(r.account_id).code if r.account_id in by_id else "",
            "name_ar": by_id.get(r.account_id).name_ar if r.account_id in by_id else "",
            "name_en": by_id.get(r.account_id).name_en if r.account_id in by_id else "",
            "debit": format2(r.debit),
            "credit": format2(r.credit),
        }
        for r in sorted(rows, key=lambda r: by_id.get(r.account_id).code if r.account_id in by_id else str(r.account_id))
    ]
    return {
        "branch_id": branch_id,
        "year": year,
        "month": month,
        "rows": out,
        "total_debit": format2(sum((dec(r["debit"]) for r in out), _ZERO)),
        "total_credit": format2(sum((dec(r["credit"]) for r in out), _ZERO)),
    }
