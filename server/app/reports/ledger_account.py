"""Ledger by account — دفتر الأستاذ لحساب (S3.5, ticket #27; RPT-F03).

ONE chart account over ONE period, built purely from `journal_lines` with the
statements window-aggregate pattern: opening = Σ(debit − credit) before the
window, movements ordered (datee, entry_no, line id) each carrying a running
balance, closing = opening + the window's movement sum.

Opening and movements come from ONE query on purpose: a single statement sees
a single snapshot, so opening + Σmovements == closing holds even under
concurrent writes (the statements-service guarantee). The cost — pre-window
lines are scanned to build the opening window aggregate — is accepted for
that atomicity; this is an accountant-facing report, not a hot path.

A code resolves to EVERY account row it maps to for this branch (own row plus
the inherited branch-1 rows carrying this branch's postings — the S2.3
code-shadowing rule, via `account_ids_for_code`), so history posted before a
shadow account was created never falls off the ledger. A code in neither the
branch chart nor the inherited chart is a 404. AR/AP movements carry طرف —
the tagged contra party — whenever one rides the line.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.models import Account, Journal, JournalLine, Party
from app.money.journal import account_ids_for_code

from app.reports.period_window import iso, resolve_period

_NOT_FOUND = HTTPException(
    status.HTTP_404_NOT_FOUND, "account not found in this branch's chart"
)


async def _display_account(
    session: AsyncSession, branch_id: int, account_ids: list[int]
) -> Account:
    """The row that names the ledger: this branch's own account for the code,
    else the inherited branch-1 row (same precedence as the id resolution)."""
    own = (
        await session.execute(
            select(Account)
            .where(
                Account.id.in_(account_ids),
                Account.branch_id == branch_id,
            )
            .order_by(Account.id)
        )
    ).scalars().first()
    if own is not None:
        return own
    inherited = (
        await session.execute(
            select(Account)
            .where(Account.id.in_(account_ids))
            .order_by(Account.branch_id, Account.id)
        )
    ).scalars().first()
    if inherited is None:
        raise _NOT_FOUND
    return inherited


async def ledger_account_report(
    session: AsyncSession,
    *,
    branch_id: int,
    account_code: str,
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """The chronological ledger of ONE chart code over the resolved window."""
    period, start, end = resolve_period(month, year, date_from, date_to)

    account_ids = await account_ids_for_code(session, branch_id, account_code)
    if not account_ids:
        raise _NOT_FOUND
    account = await _display_account(session, branch_id, account_ids)

    # ONE query feeds both the opening and the movements (window aggregate),
    # so opening + Σmovements == closing holds even under concurrent writes.
    opening_debit = func.coalesce(
        func.sum(JournalLine.debit).filter(JournalLine.datee < start).over(), 0
    )
    opening_credit = func.coalesce(
        func.sum(JournalLine.credit).filter(JournalLine.datee < start).over(), 0
    )
    rows = (
        await session.execute(
            select(JournalLine, Journal, Party, opening_debit, opening_credit)
            .join(Journal, Journal.id == JournalLine.journal_id)
            .outerjoin(Party, Party.id == JournalLine.contra_party_id)
            .where(
                JournalLine.branch_id == branch_id,
                JournalLine.account_id.in_(account_ids),
                (JournalLine.datee < start) | JournalLine.datee.between(start, end),
            )
            .order_by(JournalLine.datee, Journal.entry_no, JournalLine.id)
        )
    ).all()

    opening = money.dec("0")
    if rows:
        opening = money.dec(rows[0][3]) - money.dec(rows[0][4])

    running = opening
    debit_total = money.dec("0")
    credit_total = money.dec("0")
    movements: list[dict] = []
    for line, journal, party, _, _ in rows:
        if line.datee < start:
            continue  # prior-window lines feed the opening only
        debit = money.dec(line.debit)
        credit = money.dec(line.credit)
        running += debit - credit
        movements.append(
            {
                "datee": line.datee.isoformat(),
                "entry_no": journal.entry_no,
                "description": journal.description,
                "party": party.namee if party else None,
                "debit": money.format2(debit),
                "credit": money.format2(credit),
                "running_balance": money.format2(running),
            }
        )
        debit_total += debit
        credit_total += credit

    return {
        "branch_id": branch_id,
        "account": {
            "code": account.code,
            "name_ar": account.name_ar or "",
            "name_en": account.name_en or "",
            "type": account.type,
        },
        "period": {
            "month": period["month"],
            "year": period["year"],
            "date_from": iso(period["date_from"]),
            "date_to": iso(period["date_to"]),
        },
        "opening_balance": money.format2(opening),
        "debit_total": money.format2(debit_total),
        "credit_total": money.format2(credit_total),
        "closing_balance": money.format2(running),
        "movements": movements,
    }
