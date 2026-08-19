"""Shared helpers for the S2.1 chart-of-accounts test themes (ticket #16).

Reuses the purchase helpers for login/users/branches; adds account-specific
cleanup. Accounts are branch-scoped config rows: cleanup removes the audit row
then the account itself, and if a test posted journal_lines against the account
those lines + journals + balances are removed first (FK order).
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    Account,
    AuditLog,
    Balance,
    Journal,
    JournalLine,
    Party,
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


async def _cleanup_accounts(ids: list[int], branch_id: int = BRANCH_ID) -> None:
    """Remove throwaway accounts (journal lines/balances first if posted)."""
    async with SessionLocal() as session:
        jids = (
            await session.execute(
                select(JournalLine.journal_id).where(
                    JournalLine.account_id.in_(ids) if ids else False
                )
            )
        ).scalars().all()
        if jids:
            await session.execute(
                delete(JournalLine).where(JournalLine.journal_id.in_(jids))
            )
            await session.execute(delete(Journal).where(Journal.id.in_(jids)))
        await session.execute(
            delete(Balance).where(
                Balance.account_id.in_(ids) if ids else False
            )
        )
        await session.execute(
            delete(AuditLog).where(
                AuditLog.entity == "accounts",
                AuditLog.entity_id.in_(ids) if ids else False,
            )
        )
        await session.execute(
            delete(Account).where(Account.id.in_(ids) if ids else False)
        )
        await session.commit()


async def _account_id(code: str, branch_id: int = BRANCH_ID) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Account.id).where(
                    Account.branch_id == branch_id, Account.code == code
                )
            )
        ).scalar_one()


async def _party_ref_accounts() -> list[int]:
    """Account ids referenced by any party's receivable/payable columns."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Party.receivable_account_id, Party.payable_account_id)
            )
        ).all()
        return sorted(
            {r[0] for r in rows if r[0]} | {r[1] for r in rows if r[1]}
        )