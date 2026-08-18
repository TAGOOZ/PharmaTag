"""Purchase-return write seam (S1.6, ticket #12).

`save_purchase_return` is the public entry point the router calls: one
`atomic()` transaction that takes the branch advisory lock, assigns the branch's
next invoice_no, and runs `_build_full_purchase_return` (validate original →
reverse stock → reverse money → balanced journal → audit + outbox +
invoice_versions).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import atomic
from app.models import Invoice
from app.purchases.returns.builder import _build_full_purchase_return
from app.sales.numbering import acquire_branch_lock, next_invoice_no


async def save_purchase_return(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    original_invoice_id: int,
    lines: list[Any],
    payments=None,
    datee: Optional[date] = None,
    invoice_no: Optional[str] = None,
) -> Invoice:
    """Record a purchase return: reversal of a saved purchase, all in one
    transaction."""
    datee = datee or date.today()
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        if invoice_no is None:
            invoice_no = await next_invoice_no(session, branch_id)
        invoice = await _build_full_purchase_return(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            datee=datee,
            original_id=original_invoice_id,
            lines=lines,
            payments=payments,
        )
        await session.flush()
        return invoice