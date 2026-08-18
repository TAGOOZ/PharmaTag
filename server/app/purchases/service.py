"""Purchase use-case: save one purchase atomically (S1.4, ticket #10).

`save_purchase` opens the atomic() envelope (G12: audit + outbox + stock +
journal all land together or not at all), takes the branch advisory lock, and
hands the write to `_build_full_purchase`. `invoice_no` is server-issued from
the shared per-branch numbering sequence (next_invoice_no), shared with sales
so invoice numbers never collide across kinds on one branch.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import business_date

from app.core.db import atomic
from app.models import Invoice
from app.purchases.builder import _build_full_purchase
from app.sales.numbering import acquire_branch_lock, next_invoice_no


async def save_purchase(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    supplier_id: int,
    lines: list[Any],
    disc_percent=None,
    payments=None,
    invoice_no: Optional[str] = None,
    datee: Optional[date] = None,
) -> Invoice:
    """Save a purchase: new batches + stock-up + supplier payable + journal +
    audit + outbox, all in one transaction."""
    datee = datee or business_date()
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        if invoice_no is None:
            invoice_no = await next_invoice_no(session, branch_id)
        invoice = await _build_full_purchase(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            datee=datee,
            lines=lines,
            disc_percent=disc_percent,
            payments=payments,
            supplier_id=supplier_id,
        )
        await session.flush()
        return invoice
