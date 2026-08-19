"""Shared helpers for the S2.2 manual-journal test themes (ticket #17).

Reuses the purchase helpers for login/users/branches; adds manual-journal
cleanup. Every posted manual entry produces a `journals` row + lines + balances
+ audit + a `manual_journal_entries` reference row; cleanup walks that chain in
FK order and is scoped by the test's distinctive description tag so it never
touches rows owned by other slices.
"""
from datetime import date

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    Journal,
    JournalLine,
    ManualJournalEntry,
)

BRANCH_ID = 1

from tests.purchase_test_utils import (  # noqa: E402  (re-exported helpers)
    _delete_other_branch,
    _delete_users,
    _login_token,
    _make_other_branch,
    _make_user,
    _token_for,
    _uniq,
)


async def _cleanup_journals(tag: str) -> None:
    """Remove every manual entry whose description carries `tag` (journal +
    lines + balances + audit + manual_journal_entries) in FK order, plus any
    reversal journals linked to them via reverses_entry_id."""
    async with SessionLocal() as session:
        jids = (
            await session.execute(
                select(Journal.id).where(Journal.description.like(f"%{tag}%"))
            )
        ).scalars().all()
        if not jids:
            await session.commit()
            return
        # include the journals of reversals pointing at the tagged entries so
        # the reverses_entry_id FK (and the reversal's own journal) are handled
        tagged_entries = (
            await session.execute(
                select(ManualJournalEntry.id).where(
                    ManualJournalEntry.journal_id.in_(jids)
                )
            )
        ).scalars().all()
        reversal_jids = (
            await session.execute(
                select(ManualJournalEntry.journal_id).where(
                    ManualJournalEntry.reverses_entry_id.in_(tagged_entries)
                )
            )
        ).scalars().all()
        jids = list(dict.fromkeys([*jids, *reversal_jids]))
        # the balance rows a journal touched: (branch, month, year, account)
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id.in_(jids))
            )
        ).scalars().all()
        balance_keys = {
            (l.branch_id, l.month, l.year, l.account_id) for l in lines
        }
        for branch_id, month, year, account_id in balance_keys:
            await session.execute(
                delete(Balance).where(
                    Balance.branch_id == branch_id,
                    Balance.month == month,
                    Balance.year == year,
                    Balance.account_id == account_id,
                )
            )
        await session.execute(
            delete(JournalLine).where(JournalLine.journal_id.in_(jids))
        )
        await session.execute(
            delete(AuditLog).where(
                AuditLog.entity == "journals",
                AuditLog.entity_id.in_(jids),
            )
        )
        await session.execute(
            delete(ManualJournalEntry).where(
                ManualJournalEntry.journal_id.in_(jids)
            )
        )
        await session.execute(delete(Journal).where(Journal.id.in_(jids)))
        await session.commit()


def _entry_date() -> str:
    return date.today().isoformat()