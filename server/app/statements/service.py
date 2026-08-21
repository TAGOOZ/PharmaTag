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
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.time import business_date
from app.money.journal import account_ids_for_code
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


async def _side_accounts(
    session: AsyncSession, branch_id: int, party: Party, side: str
) -> tuple[list[int], int]:
    """The party's ledger accounts for this side: the (branch, code) resolution
    — own account plus the inherited branch-1 account so a code shadowed after
    the branch posted history can't orphan those lines — with the party's own
    receivable/payable mapping (when set) pinned on top. Returns (account_ids,
    primary_account_id) where primary is what the posting engine resolves today
    (the header account)."""
    if side == "ar":
        code = DEFAULT_AR_CODE
        pinned = party.receivable_account_id
    else:
        code = DEFAULT_AP_CODE
        pinned = party.payable_account_id
    account_ids = await account_ids_for_code(session, branch_id, code)
    if pinned is not None:
        account_ids = list(dict.fromkeys([pinned, *account_ids]))
    if not account_ids:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"no {code} account configured for this branch",
        )
    return account_ids, account_ids[0]


def _side_for(party: Party, side: Optional[str]) -> str:
    """Default side by party kind; explicit side applies to any kind."""
    if side is not None:
        if side not in ("ar", "ap"):
            raise _BAD_SIDE
        return side
    if party.kind == "supplier":
        return "ap"
    return "ar"


def _signed(line, side: str):
    """The line's signed movement under the side's natural sign (AR debit-
    positive, AP credit-positive). Returns (signed, debit, credit)."""
    debit = money.dec(line.debit)
    credit = money.dec(line.credit)
    if side == "ar":
        return debit - credit, debit, credit
    return credit - debit, debit, credit


def _lines_query(branch_id: int, account_ids: list[int], party_id: int):
    """Where criteria (and a row select) for lines that move this party's
    ledger account(s), joined to their journal (description) and account
    (code/name)."""
    criteria = [
        JournalLine.branch_id == branch_id,
        JournalLine.account_id.in_(account_ids),
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
    account_ids, primary_account_id = await _side_accounts(
        session, branch_id, party, side
    )
    account = await session.get(Account, primary_account_id)

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
                JournalLine.account_id.in_(account_ids),
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
    if not parties:
        return {
            "branch_id": branch_id,
            "total": money.format2(total),
            "payables": rows,
        }

    # One GROUP BY across all parties — mirrors get_receivables, no N+1.
    account_ids = await account_ids_for_code(session, branch_id, DEFAULT_AP_CODE)
    conditions = []
    for party in parties:
        ids = list(dict.fromkeys([party.payable_account_id, *account_ids])) if party.payable_account_id is not None else account_ids
        if not ids:
            continue
        conditions.append(
            and_(
                JournalLine.contra_party_id == party.id,
                JournalLine.account_id.in_(ids),
            )
        )
    if conditions:
        grouped = (
            await session.execute(
                select(
                    JournalLine.contra_party_id,
                    func.coalesce(func.sum(JournalLine.debit), 0),
                    func.coalesce(func.sum(JournalLine.credit), 0),
                )
                .where(JournalLine.branch_id == branch_id, or_(*conditions))
                .group_by(JournalLine.contra_party_id)
            )
        ).all()
        sums = {pid: (money.dec(d), money.dec(c)) for pid, d, c in grouped}
    else:
        sums = {}

    for party in parties:
        if party.id in sums:
            debit, credit = sums[party.id]
            balance = money.dec(credit) - money.dec(debit)
        else:
            balance = money.dec("0")
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