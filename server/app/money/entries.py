"""Manual journal entries (S2.2, ticket #17, FormAccAddQueed).

A manager posts a dated, described manual قيد whose lines balance exactly.
The entry rides the shared journal engine (`money.journal.post_journal`,
source `manual`) inside the branch advisory lock, so numbering is monotonic
per (branch, datee) and the write is atomic with its audit row (G12). A
`manual_journal_entries` reference row links the ledger workflow (the legacy
daily-manual.phy anchor); a posted entry can be reversed (A07-style) — the
reversal is a fresh opposite-signed balanced journal linked via
`reverses_entry_id`, never an edit or delete of the original.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import atomic
from app.core.money import dec, format2, round2
from app.money.journal import post_journal
from app.models import Account, Journal, JournalLine, ManualJournalEntry
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "manual journal entry not found")
UNBALANCED = HTTPException(
    status.HTTP_400_BAD_REQUEST, "journal is not balanced: SUM(debit) != SUM(credit)"
)
ALREADY_REVERSED = HTTPException(
    status.HTTP_409_CONFLICT, "a reversal entry cannot be reversed"
)


async def _resolve_account(
    session: AsyncSession, branch_id: int, code: str
) -> Account:
    """Resolve an active account for posting: the caller's branch chart, then
    the branch-1 inheritance chart (same rule as the journal engine). Unknown
    and deactivated accounts are client errors here — the caller picked the
    code — so they surface as 400, not the engine's internal 500."""
    account = (
        await session.execute(
            select(Account).where(
                Account.branch_id == branch_id, Account.code == code
            )
        )
    ).scalar_one_or_none()
    if account is None and branch_id != 1:
        account = (
            await session.execute(
                select(Account).where(
                    Account.branch_id == 1, Account.code == code
                )
            )
        ).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"account {code} is not in this branch's chart",
        )
    if not account.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"account {code} is deactivated and cannot be posted to",
        )
    return account


def _validated_entries(lines) -> list[tuple[str, object, object]]:
    """Round each line, enforce single-sidedness, and return (code, debit,
    credit) tuples. Zero, negative, and double-sided lines are 400."""
    entries: list[tuple[str, object, object]] = []
    for line in lines:
        debit = round2(dec(line.debit or 0))
        credit = round2(dec(line.credit or 0))
        if debit == 0 and credit == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"line {line.account_code}: amount must be greater than zero",
            )
        if debit > 0 and credit > 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"line {line.account_code}: a line can be debit OR credit, not both",
            )
        entries.append((line.account_code.strip(), debit, credit))
    if sum(dec(d) for _, d, _ in entries) != sum(
        dec(c) for _, _, c in entries
    ):
        raise UNBALANCED
    return entries


async def serialize_entry(
    session: AsyncSession, entry: ManualJournalEntry
) -> dict:
    """One entry with its journal lines (account code/name + sides), money as
    exact decimal strings."""
    journal = await session.get(Journal, entry.journal_id)
    lines = (
        await session.execute(
            select(JournalLine)
            .where(JournalLine.journal_id == journal.id)
            .order_by(JournalLine.id)
        )
    ).scalars().all()
    accounts = (
        await session.execute(
            select(Account).where(
                Account.id.in_({l.account_id for l in lines})
            )
        )
    ).scalars().all()
    by_id = {a.id: a for a in accounts}
    return {
        "id": entry.id,
        "journal_id": journal.id,
        "entry_no": journal.entry_no,
        "branch_id": entry.branch_id,
        "datee": journal.datee.isoformat(),
        "description": journal.description,
        "source": journal.source,
        "total": format2(entry.amount),
        "reverses_entry_id": entry.reverses_entry_id,
        "lines": [
            {
                "account_id": line.account_id,
                "account_code": by_id[line.account_id].code,
                "account_name": by_id[line.account_id].name_ar,
                "debit": format2(line.debit),
                "credit": format2(line.credit),
                "note": line.tips,
            }
            for line in lines
        ],
    }


async def post_manual_entry(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    datee: date,
    description: str,
    lines,
) -> ManualJournalEntry:
    """Post one balanced manual journal (journal + lines + balances + audit +
    manual_journal_entries reference) atomically under the branch lock."""
    description = description.strip()
    if not description:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "description cannot be blank"
        )
    entries = []
    for code, debit, credit in _validated_entries(lines):
        await _resolve_account(session, branch_id, code)
        entries.append((code, debit, credit))

    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        entry_no = await next_journal_entry_no(session, branch_id, datee)
        journal = await post_journal(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            entry_no=entry_no,
            description=description,
            source="manual",
            entries=entries,
        )
        total = sum(dec(d) for _, d, _ in entries)
        entry = ManualJournalEntry(
            branch_id=branch_id,
            datee=datee,
            amount=total,
            source_file="manual",
            journal_id=journal.id,
        )
        session.add(entry)
        await session.flush()
    return entry


async def reverse_manual_entry(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    entry_id: int,
) -> ManualJournalEntry:
    """Post the offsetting reversal of a posted manual entry (manager-only at
    the router, A07-style): sides swapped, same datee, linked via
    `reverses_entry_id`, own journal + audit."""
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        entry = await session.get(ManualJournalEntry, entry_id)
        if entry is None or entry.branch_id != branch_id:
            raise NOT_FOUND
        if entry.reverses_entry_id is not None:
            raise ALREADY_REVERSED
        journal = await session.get(Journal, entry.journal_id)
        if journal is None or journal.status != "posted":
            raise HTTPException(
                status.HTTP_409_CONFLICT, "entry is not posted and cannot be reversed"
            )
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        accounts = (
            await session.execute(
                select(Account).where(
                    Account.id.in_({l.account_id for l in lines})
                )
            )
        ).scalars().all()
        code_by_id = {a.id: a.code for a in accounts}
        reversed_entries = [
            (code_by_id[l.account_id], l.credit, l.debit) for l in lines
        ]
        entry_no = await next_journal_entry_no(session, branch_id, journal.datee)
        reversal = await post_journal(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=journal.datee,
            entry_no=entry_no,
            description=f"reversal of manual entry #{journal.entry_no}",
            source="manual",
            entries=reversed_entries,
        )
        row = ManualJournalEntry(
            branch_id=branch_id,
            datee=journal.datee,
            amount=entry.amount,
            source_file="manual",
            journal_id=reversal.id,
            reverses_entry_id=entry.id,
        )
        session.add(row)
        await session.flush()
    return row


async def list_manual_entries(
    session: AsyncSession, *, branch_id: int, limit: int = 50
) -> list[dict]:
    """Branch-scoped manual entries, newest (datee, entry_no) first."""
    rows = (
        await session.execute(
            select(ManualJournalEntry, Journal)
            .join(Journal, Journal.id == ManualJournalEntry.journal_id)
            .where(ManualJournalEntry.branch_id == branch_id)
            .order_by(Journal.datee.desc(), Journal.entry_no.desc(), ManualJournalEntry.id.desc())
            .limit(min(limit, 200) if limit > 0 else 0)
        )
    ).all()
    entries = [entry for entry, _ in rows]
    return [await serialize_entry(session, e) for e in entries]


async def get_manual_entry(
    session: AsyncSession, *, branch_id: int, entry_id: int
) -> dict:
    """One branch-scoped manual entry — a cross-branch entry is a 404."""
    entry = await session.get(ManualJournalEntry, entry_id)
    if entry is None or entry.branch_id != branch_id:
        raise NOT_FOUND
    return await serialize_entry(session, entry)