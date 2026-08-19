"""كشف حساب ledger + supplier payables (S2.3, issue #18).

The statement is built purely from `journal_lines` — never from the `balances`
table (it's keyed per account, not per party). A party's ledger is the set of
journal lines that (a) carry the party as their contra party and (b) sit on the
party's AR or AP account: customers run on the AR side (debit-positive),
suppliers on the AP side (credit-positive), and `kind='both'` defaults to AR
with an optional `side` override.

Opening balance = SUM(debit) − SUM(credit) of those lines before the period
start; closing = opening + the period's movement sum. Every movement carries a
running balance so the page reads like a physical ledger sheet.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.time import business_date
from app.models import Account, Journal, JournalLine, Party

DEFAULT_AR_CODE = "1100"
DEFAULT_AP_CODE = "2000"

_BAD_SIDE = HTTPException(status.HTTP_400_BAD_REQUEST, "side must be 'ar' or 'ap'")
_AMBIGUOUS_PERIOD = HTTPException(
    status.HTTP_400_BAD_REQUEST, "pass month/year OR a date range, not both"
)
_INVERTED_RANGE = HTTPException(
    status.HTTP_400_BAD_REQUEST, "date_from must not be after date_to"
)
_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "party not found")


async def _party_or_404(
    session: AsyncSession, branch_id: int, party_id: int
) -> Party:
    party = await session.get(Party, party_id)
    if party is None or party.branch_id != branch_id:
        raise _NOT_FOUND
    return party


async def _account_by_code(
    session: AsyncSession, branch_id: int, code: str
) -> Optional[int]:
    """Resolve an account id by code (own branch, then the branch-1 chart)."""
    row = (
        await session.execute(
            select(Account.id).where(
                Account.branch_id == branch_id, Account.code == code
            )
        )
    ).scalar_one_or_none()
    if row is None and branch_id != 1:
        row = (
            await session.execute(
                select(Account.id).where(
                    Account.branch_id == 1, Account.code == code
                )
            )
        ).scalar_one_or_none()
    return row


def _side_for(party: Party, side: Optional[str]) -> str:
    """Default side by party kind; explicit side applies to any kind."""
    if side is not None:
        if side not in ("ar", "ap"):
            raise _BAD_SIDE
        return side
    if party.kind == "supplier":
        return "ap"
    return "ar"


async def _side_account(
    session: AsyncSession, branch_id: int, party: Party, side: str
) -> int:
    """The party's ledger account for this side: its own mapping when set, else
    the branch (inherited) default AR/AP code."""
    if side == "ar":
        account_id = party.receivable_account_id or await _account_by_code(
            session, branch_id, DEFAULT_AR_CODE
        )
        fallback_code = DEFAULT_AR_CODE
    else:
        account_id = party.payable_account_id or await _account_by_code(
            session, branch_id, DEFAULT_AP_CODE
        )
        fallback_code = DEFAULT_AP_CODE
    if account_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no {fallback_code} account configured for this branch",
        )
    return account_id


def _signed(line, side: str):
    """The line's signed movement under the side's natural sign (AR debit-
    positive, AP credit-positive). Returns (signed, debit, credit)."""
    debit = money.dec(line.debit)
    credit = money.dec(line.credit)
    if side == "ar":
        return debit - credit, debit, credit
    return credit - debit, debit, credit


def _lines_query(branch_id: int, account_id: int, party_id: int):
    """Where criteria (and a row select) for lines that move this party's
    ledger account, joined to their journal (description) and account
    (code/name)."""
    criteria = [
        JournalLine.branch_id == branch_id,
        JournalLine.account_id == account_id,
        JournalLine.contra_party_id == party_id,
    ]
    stmt = (
        select(JournalLine, Journal, Account)
        .join(Journal, Journal.id == JournalLine.journal_id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(*criteria)
    )
    return stmt, criteria


async def _aggregate(session, criteria) -> tuple:
    """SUM(debit), SUM(credit) of the journal lines matching criteria."""
    return (
        await session.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            ).where(*criteria)
        )
    ).one()


async def get_statement(
    session: AsyncSession,
    *,
    branch_id: int,
    party_id: int,
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
    side: Optional[str] = None,
) -> dict:
    """A party's AR/AP ledger over a period.

    Period: month/year (canonical, like the legacy monthe/yearo) OR an inclusive
    date range; passing both is rejected as ambiguous. Movement rows are ordered
    chronologically (datee, entry_no, line id) with a running balance. Opening
    and movements come from ONE query (a window aggregate over the same rows),
    so opening + Σmovements == closing holds even under concurrent writes.
    """
    party = await _party_or_404(session, branch_id, party_id)
    side = _side_for(party, side)
    account_id = await _side_account(session, branch_id, party, side)
    account = await session.get(Account, account_id)

    if (month is not None or year is not None) and (
        date_from is not None or date_to is not None
    ):
        raise _AMBIGUOUS_PERIOD
    if date_from is not None and date_to is not None and date_from > date_to:
        raise _INVERTED_RANGE

    if month is not None or year is not None:
        today = business_date()
        m = month or today.month
        y = year or today.year
        period_month, period_year = m, y
        period_date_from = period_date_to = None
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
    elif date_from is not None or date_to is not None:
        period_month = period_year = None
        period_date_from = date_from
        period_date_to = date_to
        start = date_from or date(1900, 1, 1)
        end = date_to or date(9999, 12, 31)
    else:
        today = business_date()
        y = today.year
        m = today.month
        period_month, period_year = m, y
        period_date_from = period_date_to = None
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])

    opening_debit = func.coalesce(
        func.sum(JournalLine.debit).filter(JournalLine.datee < start).over(), 0
    )
    opening_credit = func.coalesce(
        func.sum(JournalLine.credit).filter(JournalLine.datee < start).over(), 0
    )
    rows = (
        await session.execute(
            select(JournalLine, Journal, Account, opening_debit, opening_credit)
            .join(Journal, Journal.id == JournalLine.journal_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(
                JournalLine.branch_id == branch_id,
                JournalLine.account_id == account_id,
                JournalLine.contra_party_id == party_id,
                (JournalLine.datee < start) | JournalLine.datee.between(start, end),
            )
            .order_by(JournalLine.datee, Journal.entry_no, JournalLine.id)
        )
    ).all()

    opening = money.dec("0")
    if rows:
        opening = money.dec(rows[0][3]) - money.dec(rows[0][4])
        if side == "ap":
            opening = -opening

    running = opening
    movements = []
    debit_total = money.dec("0")
    credit_total = money.dec("0")
    for line, journal, acct, _, _ in rows:
        if line.datee < start:
            continue  # prior-period lines feed the opening window only
        movement, debit, credit = _signed(line, side)
        running += movement
        movements.append(
            {
                "datee": line.datee.isoformat(),
                "description": journal.description,
                "account_code": acct.code,
                "account_name": acct.name_ar or "",
                "debit": money.format2(debit),
                "credit": money.format2(credit),
                "running_balance": money.format2(running),
            }
        )
        debit_total += debit
        credit_total += credit

    return {
        "party": {
            "id": party.id,
            "namee": party.namee,
            "name_ar": party.name_ar or "",
            "kind": party.kind,
        },
        "side": side,
        "account_code": account.code if account else "",
        "account_name": account.name_ar if account else "",
        "period": {
            "month": period_month,
            "year": period_year,
            "date_from": period_date_from.isoformat() if period_date_from else None,
            "date_to": period_date_to.isoformat() if period_date_to else None,
        },
        "opening_balance": money.format2(opening),
        "closing_balance": money.format2(running),
        "debit_total": money.format2(debit_total),
        "credit_total": money.format2(credit_total),
        "movements": movements,
    }


async def get_payables(
    session: AsyncSession, *, branch_id: int
) -> dict:
    """All active supplier/both parties with their all-time net AP balance,
    sorted descending (biggest payable first). The grand total counts only
    positive balances (what the branch actually owes); a supplier with a net
    credit (overpayment) still appears in the list, sorted last."""
    parties = (
        await session.execute(
            select(Party).where(
                Party.branch_id == branch_id,
                Party.active.is_(True),
                Party.kind.in_(("supplier", "both")),
            )
        )
    ).scalars().all()

    rows = []
    total = money.dec("0")
    for party in parties:
        account_id = party.payable_account_id or await _account_by_code(
            session, branch_id, DEFAULT_AP_CODE
        )
        if account_id is None:
            balance = money.dec("0")
        else:
            _, criteria = _lines_query(branch_id, account_id, party.id)
            agg = await _aggregate(session, criteria)
            balance = money.dec(agg[1]) - money.dec(agg[0])
        rows.append(
            {
                "party_id": party.id,
                "namee": party.namee,
                "name_ar": party.name_ar or "",
                "kind": party.kind,
                "balance": money.format2(balance),
            }
        )
        if balance > 0:
            total += balance

    rows.sort(key=lambda r: money.dec(r["balance"]), reverse=True)
    return {
        "branch_id": branch_id,
        "total": money.format2(total),
        "payables": rows,
    }