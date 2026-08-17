"""Sale journal posting (plan/02 §4.1 step 5, G12).

One balanced journal entry per sale, written inside the sale's transaction:

  Dr 1000 drawer/cash = payed      (cash + card received)
  Dr 1100 AR          = agel       (credit sales)
  Cr 4000 sales       = net        (total - vat)
  Cr 2100 VAT payable = vat
  Dr 6000 COGS        = cogs_total
  Cr 1200 stock       = cogs_total

Balanced by construction: debits = payed + agel + cogs = total + cogs and
credits = net + vat + cogs = total + cogs (net = total - vat). `balances` rows
are upserted per (branch, account, month, year) so running totals reconcile to
the journal (feature_balances).
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
VAT_PAYABLE = "2100"
SALES = "4000"
COGS = "6000"

# The default sale chart (seeded per branch by rev 002). New branches inherit
# the seeded MAIN chart until they configure their own.
SALE_ACCOUNT_CODES = (DRAWER, AR, STOCK, VAT_PAYABLE, SALES, COGS)


async def _account_id(session: AsyncSession, branch_id: int, code: str) -> int:
    account = (
        await session.execute(
            select(Account).where(
                Account.branch_id == branch_id, Account.code == code
            )
        )
    ).scalar_one_or_none()
    if account is None:
        account = (
            await session.execute(
                select(Account).where(
                    Account.branch_id == 1, Account.code == code
                )
            )
        ).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"sale account {code} is not configured",
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


async def post_sale_journal(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    datee: date,
    entry_no: int,
    description: str,
    entries: list[tuple[str, Decimal, Decimal]],
    ref_invoice_id: Optional[int] = None,
) -> Journal:
    """Post one balanced journal entry for a sale and touch the balances."""
    journal = Journal(
        branch_id=branch_id,
        datee=datee,
        entry_no=entry_no,
        description=description,
        source="sale",
        status="posted",
        ref_invoice_id=ref_invoice_id,
        created_by=user_id,
    )
    session.add(journal)
    await session.flush()

    for code, debit, credit in entries:
        debit = dec(debit)
        credit = dec(credit)
        account_id = await _account_id(session, branch_id, code)
        line = JournalLine(
            journal_id=journal.id,
            branch_id=branch_id,
            account_id=account_id,
            debit=debit,
            credit=credit,
            datee=datee,
            month=datee.month,
            year=datee.year,
            creditdebit="debit" if debit else "credit",
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