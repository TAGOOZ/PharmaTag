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

from datetime import date, timedelta
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

_MAX_AMOUNT = dec("9999999999999999.99")
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
    od = first - timedelta(days=1)
    # Cutover cannot be the minimal year/month because the journal would be
    # outside the validated calendar (1899-12-31). Reject explicitly.
    if od.year < 1900:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "opening balances cannot be set for 1900-01 (journal would be 1899-12-31)")
    return od


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
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amount is too large")
        if debit > _MAX_AMOUNT or credit > _MAX_AMOUNT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amount is too large")
        if debit < 0 or credit < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amounts cannot be negative")
        if debit == 0 and credit == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: amount must be greater than zero")
        if debit > 0 and credit > 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"line {line.account_code}: a line can be debit OR credit, not both")
        entries.append((line.account_code.strip(), debit, credit, (line.note or "").strip()))
    if sum(dec(d) for _, d, _, _ in entries) != sum(dec(c) for _, _, c, _ in entries):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "journal is not balanced: SUM(debit) != SUM(credit)")
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


async def _check_month_not_closed(session: AsyncSession, branch_id: int, year: int, month: int, msg: str) -> None:
    row = (
        await session.execute(
            select(MonthlyClose.status).where(
                MonthlyClose.branch_id == branch_id, MonthlyClose.year == year, MonthlyClose.month == month
            )
        )
    ).scalar_one_or_none()
    if row == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, msg)


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
        await _check_month_not_closed(session, branch_id, year, month, "month is closed; reopen it before posting opening balances")
        # The journal's own date must also be open — otherwise we would mutate a frozen period.
        await _check_month_not_closed(
            session, branch_id, opening_date.year, opening_date.month, "previous month is closed; reopen it before posting opening balances"
        )
        # Next month must also be open — otherwise its seeded snapshot (monthy/start-data)
        # is already frozen and would diverge from the mizan after we mutate this month.
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
        await _check_month_not_closed(session, branch_id, ny, nm, "next month is closed; reopen it before posting opening balances")

        # No duplicate opening for the same branch+period — discriminator is
        # BOTH the opening journal and the month_open snapshot. month_open is
        # shared with month_close's auto-seeded next-month carryover (which has
        # no opening journal), and after a reversal the journal remains but the
        # snapshot is cleared — both cases must allow a new POST.
        existing_journal = (
            await session.execute(
                select(Journal.id)
                .where(
                    Journal.branch_id == branch_id,
                    Journal.datee == opening_date,
                    Journal.source == "opening",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        existing_snapshot = (
            await session.execute(
                select(MonthOpenBalance.branch_id)
                .where(
                    MonthOpenBalance.branch_id == branch_id,
                    MonthOpenBalance.year == year,
                    MonthOpenBalance.month == month,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_journal is not None and existing_snapshot is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "opening balances already exist for this period")
        # Avoid PK collision when overwriting a close-seeded snapshot (no journal)
        # or a reversed opening (journal kept, snapshot cleared) — delete any
        # existing snapshot rows for this period before inserting the new ones.
        if existing_snapshot is not None:
            await session.execute(
                delete(MonthOpenBalance).where(
                    MonthOpenBalance.branch_id == branch_id,
                    MonthOpenBalance.year == year,
                    MonthOpenBalance.month == month,
                )
            )
            await session.flush()

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
            select(Journal)
            .where(
                Journal.branch_id == branch_id,
                Journal.datee == opening_date,
                Journal.source == "opening",
            )
            .order_by(Journal.id.desc())
        )
    ).scalars().first()
    if journal is None:
        # No opening journal for this period — distinguish from month_close's
        # auto-seeded month_open_balances (which have no opening journal).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "opening balances not found")
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "opening balances not found")
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
            select(Journal)
            .where(Journal.branch_id == branch_id, Journal.source == "opening")
            .order_by(Journal.datee.desc(), Journal.id.desc())
        )
    ).scalars().all()
    if not journals:
        return []
    # Distinct target months (opening_date +1 day)
    distinct: set[tuple[int, int]] = set()
    for j in journals:
        target = j.datee + timedelta(days=1)
        distinct.add((target.year, target.month))
    # One-shot fetch of month_open rows for those distinct periods
    all_rows = (
        await session.execute(
            select(MonthOpenBalance).where(MonthOpenBalance.branch_id == branch_id)
        )
    ).scalars().all()
    rows_by_period: dict[tuple[int, int], list[MonthOpenBalance]] = {}
    for r in all_rows:
        key = (r.year, r.month)
        if key in distinct:
            rows_by_period.setdefault(key, []).append(r)
    # Batch load accounts
    all_ids = {r.account_id for rows in rows_by_period.values() for r in rows}
    accounts = (
        (await session.execute(select(Account).where(Account.id.in_(all_ids)))).scalars().all() if all_ids else []
    )
    by_id = {a.id: a for a in accounts}
    # Map each target to its latest journal (max id for that opening_date)
    journal_by_target: dict[int, Journal] = {}
    for j in journals:
        target = j.datee + timedelta(days=1)
        key_int = target.year * 100 + target.month
        # Keep the first encountered (newest due to order by datee desc, id desc)
        if key_int not in journal_by_target:
            journal_by_target[key_int] = j
    out: list[dict] = []
    for (year, month) in sorted(distinct, reverse=True):
        key_int = year * 100 + month
        journal = journal_by_target.get(key_int)
        if journal is None:
            continue
        rows = rows_by_period.get((year, month), [])
        if not rows:
            continue
        opening_date = _opening_date(year, month)
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
        out.append(
            {
                "branch_id": branch_id,
                "year": year,
                "month": month,
                "opening_date": opening_date.isoformat(),
                "journal_id": journal.id,
                "entry_no": journal.entry_no,
                "description": journal.description,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "rows": out_rows,
                "balanced": dec(total_debit) == dec(total_credit),
            }
        )
    return out


async def delete_opening_balances(session: AsyncSession, *, branch_id: int, user_id: Optional[int], year: int, month: int) -> None:
    """Reverse the opening (append-only) — posts an opposite journal and clears
    the month_open snapshot. Original journal and audits are kept per G12.

    Fails 409 if the target month is closed; 404 if no opening exists.
    """
    _validate_year(year)
    _validate_month(month)
    opening_date = _opening_date(year, month)
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        await _check_month_not_closed(session, branch_id, year, month, "month is closed; reopen it before deleting opening balances")
        await _check_month_not_closed(
            session, branch_id, opening_date.year, opening_date.month, "previous month is closed; reopen it before deleting opening balances"
        )
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
        await _check_month_not_closed(session, branch_id, ny, nm, "next month is closed; reopen it before deleting opening balances")
        # Must be an opening-created period, not a bare month_close carryover
        journal = (
            await session.execute(
                select(Journal)
                .where(
                    Journal.branch_id == branch_id,
                    Journal.datee == opening_date,
                    Journal.source == "opening",
                )
                .order_by(Journal.id.desc())
            )
        ).scalars().first()
        if journal is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "opening balances not found")
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, "opening balances not found")

        # Post a reversal journal on the same opening_date (swapped sides) to
        # keep the ledger append-only. The original opening remains for audit.
        lines = (
            await session.execute(select(JournalLine).where(JournalLine.journal_id == journal.id))
        ).scalars().all()
        reversal_no = await next_journal_entry_no(session, branch_id, opening_date)
        reversal = Journal(
            branch_id=branch_id,
            datee=opening_date,
            entry_no=reversal_no,
            description=f"reversal of opening balances {year}-{month:02d}",
            source="opening",
            status="posted",
            created_by=user_id,
        )
        session.add(reversal)
        await session.flush()
        for line in lines:
            rev = JournalLine(
                journal_id=reversal.id,
                branch_id=branch_id,
                account_id=line.account_id,
                debit=line.credit,
                credit=line.debit,
                datee=opening_date,
                month=opening_date.month,
                year=opening_date.year,
                creditdebit="debit" if line.credit else "credit",
                tips=line.tips,
            )
            session.add(rev)
            await _touch_balance(
                session,
                branch_id=branch_id,
                account_id=line.account_id,
                month=opening_date.month,
                year=opening_date.year,
                debit=line.credit,
                credit=line.debit,
            )
        # Clear the month_open snapshot for the target month
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
            action="reverse",
            old_value=f"year={year} month={month}",
            new_value=f"reversal journal {reversal.id}",
            typevalue=f"{year}-{month:02d}",
        )
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="journals",
            entity_id=reversal.id,
            action="insert",
            new_value=reversal.description,
            typevalue=reversal.description,
        )
