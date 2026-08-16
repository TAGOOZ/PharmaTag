"""The `sale.saved` emission seam (plan/08 §2.4.1, ticket #3 AC3).

This is deliberately a THIN stub of the future S1.3 sale slice: it stages a
minimal invoice header and emits `sale.saved` through the two-phase bus —
`in_txn` inside the atomic transaction, `after_commit` only after it commits.
The money/journal/stock/credit logic that makes a real sale lives in S1.3 and
plugs into the same seam without touching the bus contract.

The plugin host MUST NOT break the atomic-write invariant: plugin `in_txn`
handlers run inside `atomic(session)` and share the sale's fate.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.db import atomic
from app.core.events import AFTER_COMMIT, IN_TXN, SALE_SAVED, EventBus, SaleContext, bus
from app.models import Invoice


async def save_sale(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    datee: Optional[date] = None,
    bus: EventBus = bus,
) -> Invoice:
    """Save a sale header, emitting `sale.saved` in both phases.

    in_txn handlers see the uncommitted invoice (flushed, id assigned); if any
    strict handler raises, the whole write (invoice + core audit + plugin rows)
    rolls back. after_commit handlers run only if the transaction committed.
    """
    datee = datee or date.today()
    async with atomic(session):
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
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="invoices",
            entity_id=invoice.id,
            action=ACTION_INSERT,
            new_value=f"invoice_no={invoice_no}",
        )
        ctx = SaleContext(
            session=session,
            branch_id=branch_id,
            user_id=user_id,
            sale=invoice,
        )
        await bus.emit(SALE_SAVED, ctx, phase=IN_TXN)
    await bus.emit(SALE_SAVED, ctx, phase=AFTER_COMMIT)
    return invoice