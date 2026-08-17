"""Offline outbox replay (ticket #9 AC4, plan/02 §sync_log outbox, G10).

`replay_pending` applies pending sale outbox rows for a branch in FIFO order.
The natural dedupe key is (branch_id, invoice_no), enforced by
uq_invoices_branch_no: re-applying an already-applied invoice is a no-op
(marked applied). Conflicts (missing/insufficient stock, missing batch) are
recorded on the row as status='failed' with the reason appended to the payload —
they are never silently dropped (G10: conflicts are LWW + recorded, never lost).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import atomic
from app.models import Invoice, SyncLog
from app.sales.numbering import acquire_branch_lock


async def _apply_row(
    session: AsyncSession, *, branch_id: int, payload: dict, user_id: Optional[int]
) -> None:
    """Dispatch a pending invoice row to its kind's replay (sale or purchase)."""
    kind = payload.get("kind", "sale")
    if kind == "purchase":
        from app.purchases.replay import apply_purchase_payload

        await apply_purchase_payload(
            session, branch_id=branch_id, payload=payload, user_id=user_id
        )
    else:
        from app.sales.replay import apply_sale_payload

        await apply_sale_payload(
            session, branch_id=branch_id, payload=payload, user_id=user_id
        )


async def _invoice_exists(
    session: AsyncSession, branch_id: int, invoice_no: str
) -> bool:
    row = (
        await session.execute(
            select(Invoice.id).where(
                Invoice.branch_id == branch_id,
                Invoice.invoice_no == invoice_no,
            )
        )
    ).scalars().first()
    return row is not None


async def replay_pending(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int] = None,
) -> dict:
    """Apply all pending invoice outbox rows for a branch; return a summary.

    Idempotent: an invoice that already exists (from a prior online write or a
    prior replay) is skipped and marked applied. Runs in ONE transaction — a
    failure on one row marks only that row failed and does not roll back the
    others.
    """
    summary: dict = {"applied": 0, "skipped": 0, "failed": 0, "failures": []}
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        rows = (
            await session.execute(
                select(SyncLog)
                .where(
                    SyncLog.branch_id == branch_id,
                    SyncLog.entity == "invoice",
                    SyncLog.status == "pending",
                )
                .order_by(SyncLog.id)
                .with_for_update()
            )
        ).scalars().all()

        for row in rows:
            payload = dict(row.payload or {})
            invoice_no = payload.get("invoice_no", "")
            if await _invoice_exists(session, branch_id, invoice_no):
                row.status = "applied"
                row.synced_at = datetime.now(timezone.utc)
                summary["skipped"] += 1
                continue
            try:
                await _apply_row(
                    session,
                    branch_id=branch_id,
                    payload=payload,
                    user_id=user_id,
                )
                row.status = "applied"
                row.synced_at = datetime.now(timezone.utc)
                summary["applied"] += 1
            except HTTPException as exc:
                failure = exc.detail
                row.status = "failed"
                row.payload = {**payload, "failure": str(failure)}
                summary["failed"] += 1
                summary["failures"].append(
                    {"id": row.id, "invoice_no": invoice_no, "error": failure}
                )
    return summary