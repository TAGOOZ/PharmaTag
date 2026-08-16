"""Audit + outbox seams (plan/02 §Core foundations, G12).

`audit()` appends an `audit_log` row inside the CURRENT transaction and
`enqueue_sync()` appends a `sync_log` outbox row in that same transaction, so
every money/stock write carries its audit + replication intent atomically —
either the whole write commits (mutation + audit + outbox) or nothing does
(G12, plan/02 §4.1 step 6, §sync_log outbox).

These are pure append helpers: they never BEGIN or COMMIT a transaction. The
caller owns the boundary via `app.core.db.atomic(session)` (or an enclosing
request transaction). Both mirror the legacy audit shape — branch, user,
drug_id, barcode, action — so the old audit UX is reproducible (plan/02 §core).
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, SyncLog

# action vocabulary reused across the codebase (legacy TitanUserAction mapping)
ACTION_UPDATE = "update"
ACTION_INSERT = "insert"
ACTION_LOGIN = "login"
ACTION_LOGIN_FAILED = "login_failed"


async def audit(
    session: AsyncSession,
    *,
    branch_id: Optional[int],
    user_id: Optional[int],
    entity: str,
    entity_id: Optional[int] = None,
    field: str = "",
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    drug_id: Optional[int] = None,
    barcode: str = "",
    action: str = ACTION_UPDATE,
    namee: str = "",
    typevalue: str = "",
) -> AuditLog:
    """Append one audit_log row in the caller's transaction (never commits)."""
    row = AuditLog(
        branch_id=branch_id,
        user_id=user_id,
        entity=entity,
        entity_id=entity_id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        drug_id=drug_id,
        barcode=barcode,
        action=action,
        namee=namee,
        typevalue=typevalue,
    )
    session.add(row)
    await session.flush()
    return row


async def enqueue_sync(
    session: AsyncSession,
    *,
    branch_id: int,
    entity: str,
    entity_id: Optional[int] = None,
    action: str = ACTION_UPDATE,
    payload: Optional[dict[str, Any]] = None,
    source_device_id: Optional[int] = None,
) -> SyncLog:
    """Enqueue one sync_log outbox row in the caller's transaction (never commits)."""
    row = SyncLog(
        branch_id=branch_id,
        entity=entity,
        entity_id=entity_id,
        action=action,
        payload=payload,
        status="pending",
        source_device_id=source_device_id,
    )
    session.add(row)
    await session.flush()
    return row