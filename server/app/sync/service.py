"""Offline outbox replay (ticket #9 AC4, plan/02 §sync_log outbox, G10).

`replay_pending` applies pending outbox rows for a branch in FIFO order. Two
entities replay:

* `invoice` — the natural dedupe key is (branch_id, invoice_no), enforced by
  uq_invoices_branch_no: re-applying an already-applied invoice is a no-op
  (marked applied). Conflicts (missing/insufficient stock, missing batch) are
  recorded on the row as status='failed' with the reason appended to the
  payload — never silently dropped (G10).
* `branch_stock` (S1.7, ticket #13) — the payload carries the absolute balance
  (`qty`), so LWW is trivially idempotent. A drug that no longer exists on the
  target store is recorded failed, never lost.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.db import atomic
from app.models import BranchStock, Drug, Invoice, SyncLog
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
    elif kind == "sale_return":
        from app.sales.returns.replay import apply_sale_return_payload

        await apply_sale_return_payload(
            session, branch_id=branch_id, payload=payload, user_id=user_id
        )
    elif kind == "purchase_return":
        from app.purchases.returns.replay import apply_purchase_return_payload

        await apply_purchase_return_payload(
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


async def _apply_branch_stock(
    session: AsyncSession, *, branch_id: int, payload: dict
) -> None:
    """Apply a `branch_stock` outbox row (S1.7, ticket #13 edge pass #5).

    The payload carries the ABSOLUTE balance (`qty`), so LWW is trivially
    idempotent: whichever write lands last is the truth, and re-applying an
    already-applied row is a no-op. A drug that no longer exists on the target
    store is a recorded failure, never silently dropped (G10)."""
    drug_id = payload.get("drug_id")
    qty = payload.get("qty")
    if drug_id is None or qty is None:
        raise HTTPException(
            status_code=400, detail="malformed branch_stock outbox row"
        )
    drug = await session.get(Drug, drug_id)
    if drug is None:
        raise HTTPException(
            status_code=409, detail=f"drug {drug_id} does not exist on this store"
        )
    row = (
        await session.execute(
            select(BranchStock)
            .where(BranchStock.branch_id == branch_id, BranchStock.drug_id == drug_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = BranchStock(
            branch_id=branch_id,
            drug_id=drug_id,
            qty=money.dec("0"),
            minimum=money.dec("0"),
        )
        session.add(row)
    row.qty = money.dec(qty)
    row.lastedit = datetime.now(timezone.utc)
    session.add(row)


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
                    SyncLog.entity.in_(("invoice", "branch_stock")),
                    SyncLog.status == "pending",
                )
                .order_by(SyncLog.id)
                .with_for_update()
            )
        ).scalars().all()

        for row in rows:
            payload = dict(row.payload or {})
            if row.entity == "branch_stock":
                try:
                    await _apply_branch_stock(
                        session, branch_id=branch_id, payload=payload
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
                        {
                            "id": row.id,
                            "entity": row.entity,
                            "entity_id": row.entity_id,
                            "error": failure,
                        }
                    )
                continue

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