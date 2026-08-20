"""mizan - trial balance + balance sheet (S2.5, issue #20, FormMizan).

Both statements are built purely from `journal_lines` - the same source the
party kashf hasab uses (S2.3) - so a branch that posted history on the
inherited branch-1 chart and later created its own account for the same code
never loses that history from the mizan: every code aggregates the own-branch
account row PLUS the inherited branch-1 rows carrying this branch's lines (the
S2.3 code-shadowing rule), with the own-branch row as the display name/type.

* Trial balance (mizan al-muraja'a): per code - opening debit/credit, period
  debit/credit, closing debit/credit. The account list covers the whole branch
  chart (zero rows included), sorted by code; totals must satisfy
  SUM(debit) == SUM(credit) for opening, period, and closing.
* Balance sheet (balance 'umumiyya): the same closing balances grouped by
  account type - assets and liabilities on their natural sides, and equity
  plus the period's profit/loss (income - expenses) - with the identity
  total_assets == total_liabilities + total_equity checked live.
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
from app.models import Account, JournalLine

_AMBIGUOUS_PERIOD = HTTPException(
    status.HTTP_400_BAD_REQUEST, "pass month/year OR a date range, not both"
)
_INVERTED_RANGE = HTTPException(
    status.HTTP_400_BAD_REQUEST, "date_from must not be after date_to"
)

_ZERO = money.dec("0")


def _resolve_period(
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> tuple[dict, date, date]:
    """Resolve the report window: month/year (canonical) OR an inclusive date
    range OR the business month by default. Mixing the two forms is rejected as
    ambiguous; an inverted range is rejected up front."""
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
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
        return {"month": m, "year": y, "date_from": None, "date_to": None}, start, end
    if date_from is not None or date_to is not None:
        start = date_from or date(1900, 1, 1)
        end = date_to or date(9999, 12, 31)
        return (
            {"month": None, "year": None, "date_from": date_from, "date_to": date_to},
            start,
            end,
        )
    today = business_date()
    start = date(today.year, today.month, 1)
    end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    return (
        {"month": today.month, "year": today.year, "date_from": None, "date_to": None},
        start,
        end,
    )


async def _account_rows(
    session, branch_id: int
) -> tuple[dict[str, Account], dict[str, list[int]], list[int]]:
    """The code rows behind the mizan.

    Display accounts keyed by code (own-branch first, so a branch that
    configured its own account reads it as the primary one) plus every
    inherited branch-1 account carrying this branch's journal lines. Returns
    (display_by_code, account_ids_by_code, all_account_ids).
    """
    own = (
        await session.execute(select(Account).where(Account.branch_id == branch_id))
    ).scalars().all()
    used_inherited = (
        (
            await session.execute(
                select(Account).where(
                    Account.branch_id == 1,
                    Account.id.in_(
                        select(JournalLine.account_id).where(
                            JournalLine.branch_id == branch_id
                        )
                    ),
                )
            )
        ).scalars().all()
        if branch_id != 1
        else []
    )
    display: dict[str, Account] = {}
    ids_by_code: dict[str, list[int]] = {}
    account_ids: list[int] = []
    for account in [*own, *used_inherited]:
        display.setdefault(account.code, account)
        ids_by_code.setdefault(account.code, [])
        if account.id not in ids_by_code[account.code]:
            ids_by_code[account.code].append(account.id)
        if account.id not in account_ids:
            account_ids.append(account.id)
    return display, ids_by_code, account_ids


async def _aggregate(
    session, branch_id: int, account_ids: list[int], start: date, end: date
) -> dict[int, tuple]:
    """Per account_id: (opening_debit, opening_credit, period_debit,
    period_credit) from journal_lines - one GROUP BY, no per-account queries."""
    if not account_ids:
        return {}
    rows = (
        await session.execute(
            select(
                JournalLine.account_id,
                func.coalesce(
                    func.sum(JournalLine.debit).filter(JournalLine.datee < start), 0
                ),
                func.coalesce(
                    func.sum(JournalLine.credit).filter(JournalLine.datee < start), 0
                ),
                func.coalesce(
                    func.sum(JournalLine.debit).filter(
                        JournalLine.datee.between(start, end)
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(JournalLine.credit).filter(
                        JournalLine.datee.between(start, end)
                    ),
                    0,
                ),
            )
            .where(
                JournalLine.branch_id == branch_id,
                JournalLine.account_id.in_(account_ids),
            )
            .group_by(JournalLine.account_id)
        )
    ).all()
    return {
        account_id: (money.dec(od), money.dec(oc), money.dec(d), money.dec(c))
        for account_id, od, oc, d, c in rows
    }


def _code_row(
    account: Account, account_ids: list[int], sums: dict[int, tuple]
) -> dict:
    """One code row: opening/period/closing debit + credit (the classic mizan
    shape), money as exact decimal strings."""
    opening_debit = opening_credit = debit = credit = _ZERO
    for aid in account_ids:
        od, oc, d, c = sums.get(aid, (_ZERO, _ZERO, _ZERO, _ZERO))
        opening_debit += od
        opening_credit += oc
        debit += d
        credit += c
    closing_debit = opening_debit + debit
    closing_credit = opening_credit + credit
    return {
        "code": account.code,
        "name_ar": account.name_ar or "",
        "name_en": account.name_en or "",
        "type": account.type,
        "opening_debit": money.format2(opening_debit),
        "opening_credit": money.format2(opening_credit),
        "opening_balance": money.format2(opening_debit - opening_credit),
        "debit": money.format2(debit),
        "credit": money.format2(credit),
        "closing_debit": money.format2(closing_debit),
        "closing_credit": money.format2(closing_credit),
        "closing_balance": money.format2(closing_debit - closing_credit),
    }


def _sum_rows(rows: list[dict], field: str) -> str:
    return money.format2(sum((money.dec(r[field]) for r in rows), _ZERO))


async def get_trial_balance(
    session,
    *,
    branch_id: int,
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """mizan al-muraja'a: every chart code with opening/period/closing debit
    and credit, totals balanced (SUM(debit) == SUM(credit) on every column
    pair)."""
    period, start, end = _resolve_period(month, year, date_from, date_to)
    display, ids_by_code, account_ids = await _account_rows(session, branch_id)
    sums = await _aggregate(session, branch_id, account_ids, start, end)
    rows = [
        _code_row(display[code], ids_by_code[code], sums)
        for code in sorted(ids_by_code)
    ]
    totals = {
        "opening_debit": _sum_rows(rows, "opening_debit"),
        "opening_credit": _sum_rows(rows, "opening_credit"),
        "debit": _sum_rows(rows, "debit"),
        "credit": _sum_rows(rows, "credit"),
        "closing_debit": _sum_rows(rows, "closing_debit"),
        "closing_credit": _sum_rows(rows, "closing_credit"),
    }
    balanced = (
        money.dec(totals["opening_debit"]) == money.dec(totals["opening_credit"])
        and money.dec(totals["debit"]) == money.dec(totals["credit"])
        and money.dec(totals["closing_debit"]) == money.dec(totals["closing_credit"])
    )
    return {
        "branch_id": branch_id,
        "period": period,
        "accounts": rows,
        "totals": totals,
        "balanced": balanced,
    }


async def get_balance_sheet(
    session,
    *,
    branch_id: int,
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """The balance sheet (al-mizaniyya al-'umumiyya): the same per-code closing
    balances grouped by account type. Assets and liabilities keep their natural
    sides; equity adds the period's profit/loss (income - expenses) so the
    identity total_assets == total_liabilities + total_equity holds."""
    period, start, end = _resolve_period(month, year, date_from, date_to)
    display, ids_by_code, account_ids = await _account_rows(session, branch_id)
    sums = await _aggregate(session, branch_id, account_ids, start, end)
    rows = [
        _code_row(display[code], ids_by_code[code], sums)
        for code in sorted(ids_by_code)
    ]

    assets: list[dict] = []
    liabilities: list[dict] = []
    equity_accounts: list[dict] = []
    income_total = _ZERO
    expense_total = _ZERO
    for row in rows:
        balance = money.dec(row["closing_balance"])
        if balance == 0:
            continue
        typ = row["type"]
        if typ == "asset":
            assets.append(
                {
                    "code": row["code"],
                    "name_ar": row["name_ar"],
                    "name_en": row["name_en"],
                    "type": typ,
                    "side": "debit",
                    "amount": money.format2(balance),
                    "balance": row["closing_balance"],
                }
            )
        elif typ == "liability":
            liabilities.append(
                {
                    "code": row["code"],
                    "name_ar": row["name_ar"],
                    "name_en": row["name_en"],
                    "type": typ,
                    "side": "credit",
                    "amount": money.format2(-balance),
                    "balance": row["closing_balance"],
                }
            )
        elif typ == "equity":
            equity_accounts.append(
                {
                    "code": row["code"],
                    "name_ar": row["name_ar"],
                    "name_en": row["name_en"],
                    "type": typ,
                    "side": "credit",
                    "amount": money.format2(-balance),
                    "balance": row["closing_balance"],
                }
            )
        elif typ == "income":
            income_total += -balance
        elif typ == "expense":
            expense_total += balance

    net_income = money.round2(income_total - expense_total)
    if net_income != 0:
        equity_accounts.append(
            {
                "code": "__net_income__",
                "name_ar": "ارباح وخسائر",
                "name_en": "Profit & Loss",
                "type": "equity",
                "side": "credit" if net_income > 0 else "debit",
                "amount": money.format2(abs(net_income)),
                "balance": money.format2(-net_income),
            }
        )
        equity_accounts.sort(key=lambda e: e["code"])

    assets_total = sum((money.dec(a["balance"]) for a in assets), _ZERO)
    liabilities_total = -sum(
        (money.dec(l["balance"]) for l in liabilities), _ZERO
    )
    equity_total = money.round2(
        -sum((money.dec(e["balance"]) for e in equity_accounts), _ZERO)
    )
    total_assets = assets_total
    total_liabilities_equity = money.round2(liabilities_total + equity_total)

    return {
        "branch_id": branch_id,
        "period": period,
        "assets": {"total": money.format2(assets_total), "accounts": assets},
        "liabilities": {
            "total": money.format2(liabilities_total),
            "accounts": liabilities,
        },
        "equity": {"total": money.format2(equity_total), "accounts": equity_accounts},
        "net_income": money.format2(net_income),
        "total_assets": money.format2(total_assets),
        "total_liabilities_equity": money.format2(total_liabilities_equity),
        "balanced": total_assets == total_liabilities_equity,
    }