"""The `sale.saved` seam + the S1.3 sale write entry point (ticket #9).

`save_sale` is the single entry point for a sale write. Called with no lines it
keeps the ORIGINAL seam behavior (header-only invoice + `sale.saved` in both
phases, ticket #3) so the plugin-host tests stay green. Called with lines it
runs the full sale via `app.sales.builder._build_full_sale`: per-line price
resolution (G06 tax_type), canonical per-line money, expiry-FIFO batch
allocation, the balanced journal, account balances, audit rows and the outbox
snapshot — all inside ONE atomic() so the mutation, its audit and its
replication intent live or die together (G12).

`apply_sale_payload` (re-exported from `app.sales.replay`) reconstructs the
same sale from an outbox snapshot (explicit batch allocations — FIFO is NOT
re-run) so the offline replay path reproduces the exact batches, costs and
journal and stays idempotent through the UNIQUE(branch_id, invoice_no) dedupe
key.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import business_date

from app.core.audit import ACTION_INSERT, audit
from app.core.db import atomic
from app.core.events import (
    AFTER_COMMIT,
    IN_TXN,
    SALE_SAVED,
    EventBus,
    SaleContext,
    bus,
)
from app.core.money import format2
from app.models import Invoice
from app.sales.builder import _build_full_sale
from app.sales.numbering import acquire_branch_lock, next_invoice_no
from app.sales.payload import _ctx_payload
from app.sales.replay import apply_sale_payload  # noqa: F401  (public replay seam)

__all__ = ["apply_sale_payload", "save_sale"]


async def _save_header_only(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    datee: date,
) -> Invoice:
    """The original seam behavior: header-only invoice, zero totals."""
    invoice = Invoice(
        branch_id=branch_id,
        kind="sale",
        invoice_no=invoice_no,
        datee=datee,
        status="saved",
        subtotal=0,
        discount=0,
        vat=0,
        totalvalue=0,
        payed=0,
        agel=0,
        created_by=user_id,
    )
    session.add(invoice)
    await session.flush()
    return invoice


async def save_sale(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: Optional[str] = None,
    datee: Optional[date] = None,
    lines: Optional[list[Any]] = None,
    disc_percent: Optional[Any] = None,
    payments: Optional[list[Any]] = None,
    price_level: str = "public",
    bus: EventBus = bus,
) -> Invoice:
    """Save a sale, emitting `sale.saved` in both phases.

    With `lines` empty/None this keeps the ORIGINAL seam contract (header-only
    invoice). With lines it runs the full money/stock/journal write. The branch
    advisory lock serializes numbering; the whole write is one transaction.
    """
    datee = datee or business_date()
    async with atomic(session) as committed:
        await acquire_branch_lock(session, branch_id)
        if invoice_no is None:
            invoice_no = await next_invoice_no(session, branch_id)
        if lines is None or not lines:
            invoice = await _save_header_only(
                session,
                branch_id=branch_id,
                user_id=user_id,
                invoice_no=invoice_no,
                datee=datee,
            )
        else:
            invoice = await _build_full_sale(
                session,
                branch_id=branch_id,
                user_id=user_id,
                invoice_no=invoice_no,
                datee=datee,
                lines=lines,
                disc_percent=disc_percent,
                payments=payments,
                price_level=price_level,
            )
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="invoices",
            entity_id=invoice.id,
            action=ACTION_INSERT,
            new_value=f"invoice_no={invoice_no} total={format2(invoice.totalvalue)}",
            typevalue=invoice_no,
        )
        await session.flush()
        ctx = SaleContext(
            session=session,
            branch_id=branch_id,
            user_id=user_id,
            sale=invoice,
            payload=_ctx_payload(invoice),
        )
        await bus.emit(SALE_SAVED, ctx, phase=IN_TXN)
    if committed:
        await bus.emit(SALE_SAVED, ctx, phase=AFTER_COMMIT)
    return invoice