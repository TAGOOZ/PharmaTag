"""Shared balanced-journal posting (plan/02 §4.1 step 5, G12).

One balanced journal entry per money document (sale/purchase/return), written
inside the document's transaction. The sale slice's COGS shape and the
purchase slice's stock-up + AP/VAT shape are both just `entries` here; the
`source` distinguishes them in the `journal_source` enum.

`post_journal` is the generic writer: it creates the `journals` header, one
`journal_lines` row per side, upserts the `balances` rows per
(branch, account, month, year), and audits the journal — all in the caller's
transaction. The balanced-journal invariant (SUM(debit) == SUM(credit)) is
asserted by the test suite (the API layer guarantees it by construction).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.money import dec
from app.models import Account, Balance, Journal, JournalLine

DRAWER = "1000"
AR = "1100"
STOCK = "1200"
AP = "2000"
VAT_PAYABLE = "2100"
SALES = "4000"
COGS = "6000"

# The default sale chart (seeded per branch by rev 002). New branches inherit
# the seeded MAIN chart until they configure their own.
SALE_ACCOUNT_CODES = (DRAWER, AR, STOCK, VAT_PAYABLE, SALES, COGS)
# The default purchase chart: stock + input-VAT debited; drawer + AP credited.
PURCHASE_ACCOUNT_CODES = (STOCK, VAT_PAYABLE, DRAWER, AP)


async def account_ids_for_code(
    session: AsyncSession, branch_id: int, code: str
) -> list[int]:
    """Resolve every account row a (branch, code) maps to for READS.

    A branch that inherits the MAIN chart from branch 1 can later create its
    own account with the same code (create_account only checks per-branch
    duplicates), so `_account_id` (posting) and any by-code read start
    resolving to the branch's own account while the earlier journal lines stay
    on the inherited branch-1 account. Reads must aggregate BOTH rows or the
    party ledger silently loses the historical debt. Own-branch first, so a
    branch that configured its own account reads it as the primary one."""
    own = list(
        (
            await session.execute(
                select(Account.id).where(
                    Account.branch_id == branch_id, Account.code == code
                )
            )
        ).scalars().all()
    )
    inherited: list[int] = []
    if branch_id != 1:
        inherited = list(
            (
                await session.execute(
                    select(Account.id).where(
                        Account.branch_id == 1, Account.code == code
                    )
                )
            ).scalars().all()
        )
    return own + [i for i in inherited if i not in own]


async def _account_id(session: AsyncSession, branch_id: int, code: str) -> int:
    """Resolve the account for posting (own branch, then the branch-1
    inheritance chart). An account that EXISTS but is deactivated is a client
    error (400) — the caller picked a code it can see, so deactivation should
    surface as a readable 400, not the engine's internal 500 (this also closes
    the race where a concurrent deactivation lands between a caller's up-front
    account check and this re-resolve). A code that is not in the chart at all
    is an internal invariant violation (500) — the sale/purchase callers only
    ever post seeded codes."""
    account = (
        await session.execute(
            select(Account).where(
                Account.branch_id == branch_id,
                Account.code == code,
            )
        )
    ).scalar_one_or_none()
    if account is None and branch_id != 1:
        account = (
            await session.execute(
                select(Account).where(
                    Account.branch_id == 1,
                    Account.code == code,
                )
            )
        ).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"account {code} is not configured",
        )
    if not account.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"account {code} is deactivated and cannot be posted to",
        )
    return account.id


async def _touch_balance(
    session: AsyncSession,
    *,
    branch_id: int,
    account_id: int,
    month: int,
    year: int,
    debit,
    credit,
) -> None:
    balance = await session.get(
        Balance, (branch_id, account_id, month, year)
    )
    if balance is None:
        balance = Balance(
            branch_id=branch_id,
            account_id=account_id,
            month=month,
            year=year,
            debit=Decimal("0"),
            credit=Decimal("0"),
            balance=Decimal("0"),
        )
        session.add(balance)
        await session.flush()
    balance.debit = dec(balance.debit) + dec(debit)
    balance.credit = dec(balance.credit) + dec(credit)
    balance.balance = balance.debit - balance.credit


async def post_journal(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    datee: date,
    entry_no: int,
    description: str,
    source: str,
    entries: list[tuple[str, Decimal, Decimal]]
    | list[tuple[str, Decimal, Decimal, str]]
    | list[tuple[str, Decimal, Decimal, str, int]],
    ref_invoice_id: Optional[int] = None,
    contra_party_id: Optional[int] = None,
    contra_party_by_code: Optional[dict[str, int]] = None,
    contra_party_by_account_id: Optional[dict[int, int]] = None,
) -> Journal:
    """Post one balanced journal entry (entries = (account_code, debit, credit)
    or (account_code, debit, credit, note) — the optional 4th element lands on
    the line's `tips` column, used by the manual-journal slice). A 5th element
    pins the line to an already-resolved `account_id`, bypassing the by-code
    re-resolution — used by the manual-journal reversal so the offset always
    lands on the SAME account row the original touched, even if a new account
    later shadows its code.

    `contra_party_id` labels every credit line's contra party (the sale/purchase
    pattern). `contra_party_by_code` overrides it per account code for documents
    whose contra lands on a DEBIT line (e.g. a purchase return's AP debit), so a
    party-ledger always carries the party regardless of the side.
    `contra_party_by_account_id` overrides BOTH by the exact account row the
    line touches — used by the settlement reversal so its contra attaches to the
    pinned account the original touched (never re-derived from a code constant
    that could mismatch a party's mapped account).
    """
    # A closed (branch, month) rejects further journals (S2.6, #21, plan/02 4.5).
    # Inline here to avoid a circular import: monthclose imports nothing from
    # journal, so importing guard lazily is safe, but inlining the SELECT keeps
    # the engine thin and avoids the import entirely (the guard lives in the
    # monthclose module for reuse; the engine just enforces the invariant).
    from sqlalchemy import select as _select

    from app.models.ledger import MonthlyClose as _MonthlyClose

    _closed = (
        await session.execute(
            _select(_MonthlyClose.status).where(
                _MonthlyClose.branch_id == branch_id,
                _MonthlyClose.year == datee.year,
                _MonthlyClose.month == datee.month,
            )
        )
    ).scalar_one_or_none()
    if _closed == "closed":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "month is closed; reopen it before posting"
        )

    journal = Journal(
        branch_id=branch_id,
        datee=datee,
        entry_no=entry_no,
        description=description,
        source=source,
        status="posted",
        ref_invoice_id=ref_invoice_id,
        created_by=user_id,
    )
    session.add(journal)
    await session.flush()

    for entry in entries:
        code, debit, credit = entry[0], entry[1], entry[2]
        note = entry[3] if len(entry) > 3 else ""
        pinned_account_id = entry[4] if len(entry) > 4 else None
        debit = dec(debit)
        credit = dec(credit)
        account_id = (
            pinned_account_id
            if pinned_account_id is not None
            else await _account_id(session, branch_id, code)
        )
        if contra_party_by_account_id and account_id in contra_party_by_account_id:
            contra_party = contra_party_by_account_id[account_id]
        elif contra_party_by_code and code in contra_party_by_code:
            contra_party = contra_party_by_code[code]
        else:
            contra_party = contra_party_id if credit else None
        line = JournalLine(
            journal_id=journal.id,
            branch_id=branch_id,
            account_id=account_id,
            debit=debit,
            credit=credit,
            contra_party_id=contra_party,
            datee=datee,
            month=datee.month,
            year=datee.year,
            creditdebit="debit" if debit else "credit",
            tips=note,
        )
        session.add(line)
        await _touch_balance(
            session,
            branch_id=branch_id,
            account_id=account_id,
            month=datee.month,
            year=datee.year,
            debit=debit,
            credit=credit,
        )

    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="journals",
        entity_id=journal.id,
        action=ACTION_INSERT,
        new_value=description,
        typevalue=description,
    )
    return journal
