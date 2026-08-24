"""Offline outbox replay (ticket #9 AC4, plan/02 §sync_log outbox, G10).

`replay_pending` applies pending outbox rows for a branch in FIFO order. Two
entities replay:

* `invoice` — the natural dedupe key is (branch_id, invoice_no), enforced by
  uq_invoices_branch_no: re-applying an already-applied invoice is a no-op
  (marked applied). Conflicts (missing/insufficient stock, missing batch,
  closed day) are recorded on the row as status='failed' with the reason
  appended to the payload — never silently dropped (G10), and never partially
  applied: each row runs in its own SAVEPOINT, so a failed row rolls back every
  write it started (invoice, stock, journal, drawer movements) and the sync row
  stays pending-capable (reset to 'pending' after the blocker is cleared).
* `branch_stock` (S1.7, ticket #13) — the payload carries the absolute balance
  (`qty`), so LWW is trivially idempotent. A drug that no longer exists on the
  target store is recorded failed, never lost.
* `transfer` (#55, versioned since the gap fix) — dedupe keys on the SOURCE
  namespace UNIQUE(source_branch_id, transfer_no) because BOTH branches
  receive the same payload copy; ordering authority is the monotonic `rev`
  watermark: stale/duplicate/out-of-order copies (rev <= local) are skipped,
  higher-rev payloads upgrade by folding the legal stage chain with effects
  BRANCH-FILTERED to this peer's copy (sync_log.branch_id). Effects are
  applied verbatim from the snapshot's allocations (lot-exact, no FEFO
  re-run). A failing transfer row stays PENDING with the failure recorded in
  its payload — retryable on a later pass, never silently dropped (G10).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.db import atomic
from app.einvoicing.service import apply_einvoice_block
from app.models import BranchStock, Drug, EInvoiceLog, Invoice, SyncLog
from app.sales.numbering import acquire_branch_lock
from app.transfers.replay import apply_transfer_versioned


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
    others; each row applies inside its own SAVEPOINT, so a failed row's own
    partial writes (if a guard fires mid-apply, e.g. a closed day) are rolled
    back atomically instead of leaking into the committed result.
    """
    summary: dict = {"applied": 0, "skipped": 0, "failed": 0, "failures": []}
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        rows = (
            await session.execute(
                select(SyncLog)
                .where(
                    SyncLog.branch_id == branch_id,
                    SyncLog.entity.in_(("invoice", "branch_stock", "transfer")),
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
                    async with session.begin_nested():
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

            if row.entity == "transfer":
                # VERSIONED apply (#55 gap fix): ordering authority is the
                # payload's `rev` watermark against the local row — stale/
                # duplicate/out-of-order copies (rev <= local) are skipped,
                # higher-rev payloads fold the legal stage chain with effects
                # BRANCH-FILTERED to this peer (row.branch_id). Dedupe still
                # keys on the SOURCE namespace inside the applier.
                try:
                    async with session.begin_nested():
                        outcome = await apply_transfer_versioned(
                            session,
                            payload=payload,
                            peer_branch_id=row.branch_id,
                            user_id=user_id,
                        )
                    row.status = "applied"
                    row.synced_at = datetime.now(timezone.utc)
                    summary["applied" if outcome == "applied" else "skipped"] += 1
                except Exception as exc:
                    # a poisoned/blocked row fails ALONE (its savepoint rolled
                    # back) and stays pending for a later pass — recorded in
                    # the payload, never silently dropped (G10)
                    failure = (
                        exc.detail
                        if isinstance(exc, HTTPException)
                        else f"{type(exc).__name__}: {exc}"
                    )
                    row.payload = {**payload, "failure": str(failure)}
                    summary["failed"] += 1
                    summary["failures"].append(
                        {
                            "id": row.id,
                            "entity": "transfer",
                            "entity_id": row.entity_id,
                            "error": failure,
                        }
                    )
                continue

            invoice_no = payload.get("invoice_no", "")
            if await _invoice_exists(session, branch_id, invoice_no):
                # S4.1 repair seam (#28): the invoice is synced, but its TAX
                # DOCUMENT may be missing (partial restore / manual surgery).
                # Rebuild it verbatim from the snapshot instead of skipping —
                # an invoice without its document must not stay unrepaired.
                block = payload.get("einvoice")
                if block and row.entity_id is not None:
                    doc_exists = (
                        await session.execute(
                            select(EInvoiceLog.id).where(
                                EInvoiceLog.invoice_id == row.entity_id
                            )
                        )
                    ).first()
                    if doc_exists is None:
                        try:
                            async with session.begin_nested():
                                await apply_einvoice_block(
                                    session,
                                    branch_id=branch_id,
                                    invoice_id=row.entity_id,
                                    block=block,
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
                row.status = "applied"
                row.synced_at = datetime.now(timezone.utc)
                summary["skipped"] += 1
                continue
            try:
                async with session.begin_nested():
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