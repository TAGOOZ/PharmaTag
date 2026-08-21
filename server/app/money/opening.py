"""Opening balances (S2.7, issue #22) — افتتاحي مدين/دائن per account/branch.

Seeds opening cash, stock at cost, receivables and payables at cutover
(idx 8482-8485). One balanced entry per (branch, year, month): a `journals`
row (source=opening) dated the day before the opening month so the مزان's
opening aggregation (journal_lines.datee < start) naturally includes it, plus a
`month_open_balances` snapshot for that month itself so GET /months/.../open-
balances and GET /opening-balances/... return the same افتتاحي totals without a
date trick. Both sides ride the branch advisory lock and the atomic G12
audit+balances write.

Permission: `opening_balances.manage` (ledger area, floor 7 — admin/accountant/
manager). A target month that is already `closed` (monthly_close.status=closed)
rejects 409, as does a second POST for the same (branch, year, month) — use
DELETE first. Reads are open to any authenticated, branch-scoped user.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.db import atomic
from app.core.money import dec, format2, round2
from app.models import Account, Balance, Journal, JournalLine, MonthOpenBalance, MonthlyClose
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

ALREADY_EXISTS = HTTPException(status.HTTP_409_CONFLICT, "opening balances already exist for this period")
MONTH_CLOSED = HTTPException(status.HTTP_409_CONFLICT, "month is closed; reopen it before posting opening balances")
NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "opening balances not found")
UNBALANCED = HTTPException(status.HTTP_400_BAD_REQUEST, "journal is not balanced: SUM(debit) != SUM(credit)")
MAX_AMOUNT = dec("9999999999999999.99")
_ZERO = Decimal("0")


def _audit_id(branch_id: int, year: int, month: int) -> int:
    return branch_id * 1_000_000 + year * 100 + month


def _validate_year(year: int) -> None:
    if not 1900 <= year <= 9999:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "year must be between 1900 and 9999")


def _validate_month(month: int) -> None:
    if not 1 <= month <= 12:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "month must be between 1 and 12")


def _opening_date(year: int, month: int) -> date:
    """The journal date for (year, month): the day before the opening month.

    Using the previous month's last day means the journal is strictly before the
    مزان window `datee < start` for that opening month, so it appears as
    افتتاحي for that month and for every later month (cumulative), but never as
    period movement for the opening month itself.
    """
    first = date(year, month, 1)
    return first - timedelta(days=1)


async def _resolve_account(session: AsyncSession, branch_id: int, code: str) -> Account:
    code = code.strip()
    if not code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "account_code cannot be blank")
    account = (
        await session.execute(select(Account).where(Account.branch_id == branch_id, Account.code == code))
    ).scalar_one_or_none()
    if account is None and branch_id != 1:
        account = (
            await session.execute(select(Account).where(Account.branch_id == 1, Account.code == code))
        ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"account {code} is not in this branch's chart")
    if not account.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"account {code} is deactivated and cannot be posted to")
    return account


def _validated_entries(lines) -> list[tuple[str, Decimal, Decimal, str]]:
    entries: list[tuple[str, Decimal, Decimal, str]] = []
    for line in lines:
        try:
            debit = round2(dec(line.debit or 0))
            credit = round2(dec(line.credit or 0))
        except InvalidOperation:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amount is too large")
        if debit > MAX_AMOUNT or credit > MAX_AMOUNT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amount is too large")
        if debit < 0 or credit < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amounts cannot be negative")
        if debit == 0 and credit == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amount must be greater than zero")
        if debit > 0 and credit > 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: a line can be debit OR credit, not both")
        entries.append((line.account_code.strip(), debit, credit, (line.note or "").strip()))
    if sum(dec(d) for _, d, _, _ in entries) != sum(dec(c) for _, _, c, _ in entries):
        raise UNBALANCED
    return entries


async def _touch_balance(
    session: AsyncSession, *, branch_id: int, account_id: int, month: int, year: int, debit: Decimal, credit: Decimal
) -> None:
    balance = await session.get(Balance, (branch_id, account_id, month, year))
    if balance is None:
        balance = Balance(branch_id=branch_id, account_id=account_id, month=month, year=year, debit=_ZERO, credit=_ZERO, balance=_ZERO)
        session.add(balance)
        await session.flush()
    balance.debit = dec(balance.debit) + dec(debit)
    balance.credit = dec(balance.credit) + dec(credit)
    balance.balance = balance.debit - balance.credit


async def post_opening_balances(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    year: int,
    month: int,
    description: Optional[str],
    lines,
) -> dict:
    """Create opening balances for (branch, year, month). Balanced, atomic, audited.

    Creates a `journals` entry (source=opening) dated the day before the opening
    month plus a `month_open_balances` snapshot for (branch, account, year, month)
    so the archive (monthy\\start-data) is queryable directly. Rejects 409 if the
    opening already exists or the target month is closed.
    """
    _validate_year(year)
    _validate_month(month)
    desc = (description or f"opening balances {year}-{month:02d}").strip()
    if not desc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "description cannot be blank")
    entries = _validated_entries(lines)

    # Resolve every account up front (client errors outside the lock).
    account_by_code: dict[str, Account] = {}
    for code, _, _, _ in entries:
        if code not in account_by_code:
            account_by_code[code] = await _resolve_account(session, branch_id, code)

    opening_date = _opening_date(year, month)

    async with atomic(session):
        await acquire_branch_lock(session, branch_id)

        # Target month must be open; a closed month never takes new postings (S2.6).
        target = (
            await session.execute(
                select(MonthlyClose.status).where(
                    MonthlyClose.branch_id == branch_id, MonthlyClose.year == year, MonthlyClose.month == month
                )
            )
        ).scalar_one_or_none()
        if target == "closed":
            raise MONTH_CLOSED

        # No duplicate opening for the same branch+period.
        existing = (
            await session.execute(
                select(MonthOpenBalance).where(
                    MonthOpenBalance.branch_id == branch_id,
                    MonthOpenBalance.year == year,
                    MonthOpenBalance.month == month,
                )
            )
        ).scalars().all()
        if existing:
            raise ALREADY_EXISTS

        # Allocate monotonic entry_no for the opening journal's date.
        entry_no = await next_journal_entry_no(session, branch_id, opening_date)

        journal = Journal(
            branch_id=branch_id,
            datee=opening_date,
            entry_no=entry_no,
            description=desc,
            source="opening",
            status="posted",
            created_by=user_id,
        )
        session.add(journal)
        await session.flush()

        # Per-account opening sums for the month_open_balances snapshot.
        per_account: dict[int, tuple[Decimal, Decimal]] = {}
        for code, debit, credit, note in entries:
            account = account_by_code[code]
            # Journal line (single-sided) + balance for the opening_date's month.
            jl = JournalLine(
                journal_id=journal.id,
                branch_id=branch_id,
                account_id=account.id,
                debit=debit,
                credit=credit,
                datee=opening_date,
                month=opening_date.month,
                year=opening_date.year,
                creditdebit="debit" if debit else "credit",
                tips=note,
            )
            session.add(jl)
            await _touch_balance(
                session,
                branch_id=branch_id,
                account_id=account.id,
                month=opening_date.month,
                year=opening_date.year,
                debit=debit,
                credit=credit,
            )
            # Accumulate per-account for month_open_balances (target month).
            d, c = per_account.get(account.id, (_ZERO, _ZERO))
            per_account[account.id] = (d + debit, c + credit)

        # Seed month_open_balances for the target month (archive start-data).
        for account_id, (d, c) in per_account.items():
            if d == _ZERO and c == _ZERO:
                continue
            session.add(
                MonthOpenBalance(branch_id=branch_id, account_id=account_id, year=year, month=month, debit=d, credit=c)
            )
        await session.flush()

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="opening_balances",
            entity_id=_audit_id(branch_id, year, month),
            action="create",
            new_value=desc,
            typevalue=f"{year}-{month:02d}",
        )
        # The journal itself also audits via the journal path — but opening rides a
        # direct insert (not post_journal) so we audit it explicitly as journals too.
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="journals",
            entity_id=journal.id,
            action="insert",
            new_value=desc,
            typevalue=desc,
        )

    return await get_opening_balances(session, branch_id=branch_id, year=year, month=month)


async def get_opening_balances(session: AsyncSession, *, branch_id: int, year: int, month: int) -> dict:
    """One branch-scoped opening period (month_open_balances + its opening journal)."""
    _validate_year(year)
    _validate_month(month)
    opening_date = _opening_date(year, month)
    journal = (
        await session.execute(
            select(Journal).where(
                Journal.branch_id == branch_id,
                Journal.datee == opening_date,
                Journal.source == "opening",
            )
        )
    ).scalars().first()
    if journal is None:
        # No opening journal for this period — distinguish from month_close's
        # auto-seeded month_open_balances (which have no opening journal).
        raise NOT_FOUND
    rows = (
        await session.execute(
            select(MonthOpenBalance).where(
                MonthOpenBalance.branch_id == branch_id,
                MonthOpenBalance.year == year,
                MonthOpenBalance.month == month,
            )
        )
    ).scalars().all()
    if not rows:
        raise NOT_FOUND
    ids = {r.account_id for r in rows}
    accounts = (
        (await session.execute(select(Account).where(Account.id.in_(ids)))).scalars().all() if ids else []
    )
    by_id = {a.id: a for a in accounts}
    journal_id = journal.id
    entry_no = journal.entry_no
    description = journal.description

    out_rows = []
    for r in sorted(rows, key=lambda r: by_id.get(r.account_id).code if r.account_id in by_id else str(r.account_id)):
        acct = by_id.get(r.account_id)
        out_rows.append(
            {
                "account_id": r.account_id,
                "account_code": acct.code if acct else "",
                "account_name": acct.name_ar if acct else "",
                "type": acct.type if acct else "",
                "debit": format2(r.debit),
                "credit": format2(r.credit),
                "balance": format2(dec(r.debit) - dec(r.credit)),
            }
        )
    total_debit = format2(sum((dec(r.debit) for r in rows), _ZERO))
    total_credit = format2(sum((dec(r.credit) for r in rows), _ZERO))
    return {
        "branch_id": branch_id,
        "year": year,
        "month": month,
        "opening_date": opening_date.isoformat(),
        "journal_id": journal_id,
        "entry_no": entry_no,
        "description": description,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "rows": out_rows,
        "balanced": dec(total_debit) == dec(total_credit),
    }


async def list_opening_balances(session: AsyncSession, *, branch_id: int) -> list[dict]:
    """Every distinct (year, month) where this branch has opening balances (via an
    opening journal). Excludes month_close's auto-seeded next-month openings
    which share the same table but have no opening journal."""
    journals = (
        await session.execute(
            select(Journal).where(Journal.branch_id == branch_id, Journal.source == "opening").order_by(Journal.datee.desc())
        )
    ).scalars().all()
    out = []
    seen: set[tuple[int, int]] = set()
    for j in journals:
        # Opening journal's date is prev-month-end; target month is next day.
        target = j.datee + timedelta(days=1)
        key = (target.year, target.month)
        if key in seen:
            continue
        seen.add(key)
        try:
            out.append(await get_opening_balances(session, branch_id=branch_id, year=key[0], month=key[1]))
        except HTTPException:
            continue
    # Deterministic ordering newest first (same as month_close list)
    out.sort(key=lambda p: (p["year"], p["month"]), reverse=True)
    return out


async def delete_opening_balances(session: AsyncSession, *, branch_id: int, user_id: Optional[int], year: int, month: int) -> None:
    """Delete the opening snapshot + its journal (manager-only at router).

    Fails 409 if the target month is closed; 404 if no opening exists.
    """
    _validate_year(year)
    _validate_month(month)
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        target = (
            await session.execute(
                select(MonthlyClose.status).where(
                    MonthlyClose.branch_id == branch_id, MonthlyClose.year == year, MonthlyClose.month == month
                )
            )
        ).scalar_one_or_none()
        if target == "closed":
            raise MONTH_CLOSED
        rows = (
            await session.execute(
                select(MonthOpenBalance).where(
                    MonthOpenBalance.branch_id == branch_id,
                    MonthOpenBalance.year == year,
                    MonthOpenBalance.month == month,
                )
            )
        ).scalars().all()
        if not rows:
            raise NOT_FOUND
        opening_date = _opening_date(year, month)
        journals = (
            await session.execute(
                select(Journal).where(
                    Journal.branch_id == branch_id,
                    Journal.datee == opening_date,
                    Journal.source == "opening",
                )
            )
        ).scalars().all()
        # Reverse the balances touched by those journals (opening_date's month).
        for j in journals:
            lines = (
                await session.execute(select(JournalLine).where(JournalLine.journal_id == j.id))
            ).scalars().all()
            for l in lines:
                bal = await session.get(Balance, (branch_id, l.account_id, l.month, l.year))
                if bal is not None:
                    bal.debit = dec(bal.debit) - dec(l.debit)
                    bal.credit = dec(bal.credit) - dec(l.credit)
                    bal.balance = bal.debit - bal.credit
                    if bal.debit == 0 and bal.credit == 0:
                        await session.delete(bal)
            await session.execute(delete(JournalLine).where(JournalLine.journal_id == j.id))
            # Audit trail for reversal (journals) — keep the opening_balances audit.
            await session.execute(delete(Journal).where(Journal.id == j.id))
        await session.execute(
            delete(MonthOpenBalance).where(
                MonthOpenBalance.branch_id == branch_id,
                MonthOpenBalance.year == year,
                MonthOpenBalance.month == month,
            )
        )
        await session.flush()
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="opening_balances",
            entity_id=_audit_id(branch_id, year, month),
            action="delete",
            old_value=f"year={year} month={month}",
            typevalue=f"{year}-{month:02d}",
        )
