"""Sale journal posting (plan/02 §4.1 step 5, G12).

The mechanics live in the shared `app.money.journal` module; this file keeps
the sale-specific entry shape (Dr drawer/AR, Cr sales/VAT, Dr COGS/Cr stock)
and the sale source tag for callers of the S1.3 slice:

  Dr 1000 drawer/cash = payed      (cash + card received)
  Dr 1100 AR          = agel       (credit sales)
  Cr 4000 sales       = net        (total - vat)
  Cr 2100 VAT payable = vat
  Dr 6000 COGS        = cogs_total
  Cr 1200 stock       = cogs_total

Balanced by construction: debits = payed + agel + cogs = total + cogs and
credits = net + vat + cogs = total + cogs (net = total - vat).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.money.journal import (
    SALE_ACCOUNT_CODES,  # noqa: F401  (re-exported for callers)
    post_journal,
)

__all__ = ["SALE_ACCOUNT_CODES", "post_sale_journal"]


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
    contra_party_by_code: Optional[dict[str, int]] = None,
) -> object:
    """Post one balanced journal entry for a sale and touch the balances."""
    return await post_journal(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        entry_no=entry_no,
        description=description,
        source="sale",
        entries=entries,
        ref_invoice_id=ref_invoice_id,
        contra_party_by_code=contra_party_by_code,
    )
