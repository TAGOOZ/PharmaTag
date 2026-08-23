"""E-invoice status + resubmission API (S4.2, #29).

Cashiers/owners see where each tax document stands; managers resubmit
rejected or failed documents. Resubmission requeues the SAME document —
counter/uuid/qr_data are frozen (A15) — by resetting only scheduling state.
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import caller_branch_id
from app.auth.rbac import require_permission
from app.core.audit import ACTION_UPDATE, audit
from app.core.db import get_session
from app.models import EInvoiceLog

router = APIRouter(tags=["einvoicing"])

VIEW = require_permission("einvoice.view")
SUBMIT = require_permission("einvoice.submit")


@router.get("/logs")
async def list_logs(
    status: str | None = None,
    limit: int = 100,
    user=Depends(VIEW),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    query = (
        select(EInvoiceLog)
        .where(EInvoiceLog.branch_id == branch_id)
        .order_by(EInvoiceLog.id.desc())
        .limit(max(1, min(limit, 500)))
    )
    if status:
        query = query.where(EInvoiceLog.status == status)
    rows = (await session.execute(query)).scalars().all()
    return [
        {
            "id": row.id,
            "invoice_id": row.invoice_id,
            "branch_id": row.branch_id,
            "kind": row.kind,
            "status": row.status,
            "counter": row.counter,
            "uuid": row.uuid,
            "device_serial": row.device_serial,
            "attempts": row.attempts,
            "next_attempt_at": row.next_attempt_at.isoformat() if row.next_attempt_at else None,
            "last_error": row.last_error,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        }
        for row in rows
    ]


@router.post("/logs/{log_id}/resubmit")
async def resubmit(
    log_id: int,
    user=Depends(SUBMIT),
    session: AsyncSession = Depends(get_session),
):
    log = (
        await session.execute(select(EInvoiceLog).where(EInvoiceLog.id == log_id))
    ).scalar_one_or_none()
    if log is None or log.branch_id != await caller_branch_id(user):
        # cross-branch documents are as invisible as missing ones
        raise HTTPException(404, "einvoice_log row not found")
    if log.status not in ("rejected", "failed"):
        raise HTTPException(409, f"only rejected/failed documents resubmit (status={log.status})")

    previous = log.status
    log.status = "pending"
    log.attempts = 0
    log.next_attempt_at = None
    log.last_error = ""
    log.submitted_at = None  # stale until the worker's next pass touches it
    await audit(
        session,
        branch_id=log.branch_id,
        user_id=user.id,
        entity="einvoice_log",
        entity_id=log.id,
        action=ACTION_UPDATE,
        new_value=f"resubmit from {previous} counter={log.counter}",
        typevalue=f"user={user.username}",
    )
    await session.commit()
    return {"id": log.id, "status": log.status}
