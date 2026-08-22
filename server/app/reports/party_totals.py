"""Supplier/customer totals by period (S3.4, ticket #26; RPT-C01/SUP01/02).

Aggregates the party-tagged journal legs on AR (1100) and AP (2000) over a
date range: `period_debit`/`period_credit` inside the window and the all-time
`closing` balance per party. A party appears when it has in-window activity;
walk-in (party-less) documents never appear.

`closing` uses the same identity as the receivables/payables registers
(`/receivables`/`/payables`: Σdebit − Σcredit / Σcredit − Σdebit on the
party-tagged AR/AP lines including any per-party pinned account
`receivable_account_id`/`payable_account_id`), so the report's totals match
the balances by construction — tested on both sides.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money

from app.models import Journal, JournalLine, Party


async def _account_ids(session: AsyncSession, branch_id: int, code: str) -> list[int]:
    from app.money.journal import account_ids_for_code

    return list(await account_ids_for_code(session, branch_id, code))


def _window_bounds(date_from: Optional[date], date_to: Optional[date]) -> list:
    return [
        *([Journal.datee >= date_from] if date_from is not None else []),
        *([Journal.datee <= date_to] if date_to is not None else []),
    ]


async def _sums_by_party(
    session: AsyncSession,
    *,
    branch_id: int,
    parties: list[Party],
    base_account_ids: list[int],
    code: str,
    in_window_only: bool,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict[int, tuple]:
    """party_id → (Σdebit, Σcredit) on the per-party account sets.

    Mirrors the three sibling readers that union the party's own mapping:
    ``receivables/service.py:get_receivables`` (402-409),
    ``receivables/service.py:ensure_credit_ok`` (474-475) and
    ``statements/service.py:_side_accounts`` (62-68). Each party's legs are
    matched against ``[pinned, *base_ids]`` when the pin is set, otherwise
    just ``base_ids`` — otherwise a party pinned to a non-default account
    (e.g. 1199) would vanish from the report while still showing a balance in
    ``/receivables``.
    """
    if not parties or not base_account_ids and not any(
        (p.receivable_account_id if code == "1100" else p.payable_account_id)
        is not None
        for p in parties
    ):
        return {}
    conditions: list = []
    for party in parties:
        pin = (
            party.receivable_account_id
            if code == "1100"
            else party.payable_account_id
        )
        ids = (
            list(dict.fromkeys([pin, *base_account_ids]))
            if pin is not None
            else base_account_ids
        )
        if not ids:
            continue
        conditions.append(
            and_(
                JournalLine.contra_party_id == party.id,
                JournalLine.account_id.in_(ids),
            )
        )
    if not conditions:
        return {}
    query = select(
        JournalLine.contra_party_id,
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).where(
        JournalLine.branch_id == branch_id,
        or_(*conditions),
    )
    if in_window_only:
        query = query.join(Journal, JournalLine.journal_id == Journal.id).where(
            *_window_bounds(date_from, date_to)
        )
    rows = (
        await session.execute(query.group_by(JournalLine.contra_party_id))
    ).all()
    return {pid: (money.dec(dr), money.dec(cr)) for pid, dr, cr in rows}


async def _section(
    session: AsyncSession,
    *,
    branch_id: int,
    code: str,
    kinds: tuple[str, ...],
    flip_sign: bool,
    date_from: Optional[date],
    date_to: Optional[date],
) -> list[dict]:
    parties = (
        await session.execute(
            select(Party).where(
                Party.branch_id == branch_id,
                Party.active.is_(True),
                Party.kind.in_(kinds),
            )
        )
    ).scalars().all()
    base_ids = await _account_ids(session, branch_id, code)
    all_time = await _sums_by_party(
        session,
        branch_id=branch_id,
        parties=parties,
        base_account_ids=base_ids,
        code=code,
        in_window_only=False,
        date_from=None,
        date_to=None,
    )
    period = await _sums_by_party(
        session,
        branch_id=branch_id,
        parties=parties,
        base_account_ids=base_ids,
        code=code,
        in_window_only=True,
        date_from=date_from,
        date_to=date_to,
    )

    names = {p.id: p.namee for p in parties}
    kinds_by_id = {p.id: p.kind for p in parties}
    out = []
    # Sections follow each party's CURRENT kind: a party whose kind was edited
    # after posting keeps its old legs under the section it belongs to NOW
    # (same convention as /receivables and /payables). The snapshot race where
    # a party is created mid-report lands its id in the aggregate but not the
    # name map — fall back to an empty name rather than 500ing.
    for pid, (p_dr, p_cr) in period.items():
        a_dr, a_cr = all_time.get(pid, (money.dec("0"), money.dec("0")))
        closing = a_cr - a_dr if flip_sign else a_dr - a_cr
        out.append(
            {
                "party_id": pid,
                "namee": names.get(pid, ""),
                "kind": kinds_by_id.get(pid, ""),
                "period_debit": money.format2(p_dr),
                "period_credit": money.format2(p_cr),
                "closing": money.format2(money.round2(closing)),
            }
        )
    out.sort(key=lambda r: money.dec(r["closing"]), reverse=True)
    return out


async def party_totals_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Customer (AR) + supplier (AP) period legs and closings for a branch."""
    customers = await _section(
        session,
        branch_id=branch_id,
        code="1100",
        kinds=("customer", "both"),
        flip_sign=False,
        date_from=date_from,
        date_to=date_to,
    )
    suppliers = await _section(
        session,
        branch_id=branch_id,
        code="2000",
        kinds=("supplier", "both"),
        flip_sign=True,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "customers": customers,
        "suppliers": suppliers,
    }
