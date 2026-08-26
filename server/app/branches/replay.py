"""Versioned offline replay of the branch-registry outbox (#34, S5.4).

Applies `entity='branch'` and `entity='branch_identity'` fan-out copies so an
offline peer converges on the canonical registry (#31 deferred this consumer).
Both are non-money records: replay restores the RECORDED STATE VERBATIM — no
heuristics, no side effects beyond the rows themselves.

Ordering authority is the snapshot's `updated_at` watermark (plan/00 G10 LWW):
a payload older than or equal to the local row is stale/duplicate → skipped,
and the caller records WHY on the sync_log row. Identity mappings have no
natural timeline — their natural key (legacy_table, legacy_column,
legacy_value) IS the dedupe key, and a re-pointed mapping follows the last
delivery.

The single-main-device invariant survives replay through strict LWW alone:
a promote history arrives FIFO (demote-then-promote share one enqueue
transaction), and any stale re-delivery loses the updated_at comparison.

KNOWN LIMITATIONS (accepted for this slice):
* Identity mappings have no tombstone memory: if an INSERT fails transiently
  in one pass while its later _deleted tombstone applies, a pass-2 retry of
  the insert can resurrect the mapping on peers that already applied the
  delete. FIFO-within-a-pass is the only protection; revisit if transient
  identity failures become real.
* An identity whose parent branch row is MALFORMED (permanently unappliable)
  retries its FK violation each pass until the parent is fixed — downstream
  poisoning mirrors the parent's state by design.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_DELETE, ACTION_INSERT, ACTION_UPDATE, audit
from app.models import Branch, BranchIdentity
from app.needs.replay import _advance_identity_sequence

MALFORMED = HTTPException(status.HTTP_400_BAD_REQUEST, "malformed branch outbox row")
MALFORMED_IDENTITY = HTTPException(
    status.HTTP_400_BAD_REQUEST, "malformed branch_identity outbox row"
)

_TEXT_FIELDS = (
    "pharmacyid",
    "mobile",
    "phar",
    "pharname",
    "adress",
    "governorate",
    "district",
    "country",
    "currency",
)

# watermark for legacy (pre-#34) snapshots: deterministic across peers and
# guaranteed older than any real snapshot, so later deliveries always win
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _strict_int(value: object) -> int:
    """int() without the traps: rejects floats with a fractional part
    (`int(5.9)` would silently truncate) and numeric strings stay allowed."""
    if isinstance(value, bool):
        raise ValueError("bool is not an id")
    if isinstance(value, float):
        if value != int(value):
            raise ValueError("non-integral float")
        return int(value)
    if not isinstance(value, (int, str)):
        raise ValueError("unsupported id type")
    return int(value)


def _strict_bool(payload: dict, key: str, default: bool) -> bool:
    """Booleans without the `bool('false') is True` trap: JSON booleans pass;
    strings must be exactly 'true'/'false'."""
    raw = payload.get(key, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        if raw.lower() == "true":
            return True
        if raw.lower() == "false":
            return False
    raise MALFORMED


def _watermark_of(payload: dict) -> Optional[datetime]:
    raw = payload.get("updated_at")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        raise MALFORMED
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _local_watermark(local: Optional[Branch]) -> Optional[datetime]:
    if local is None or local.updated_at is None:
        return None
    ts = local.updated_at
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _fields_from_payload(payload: dict) -> dict[str, object]:
    try:
        kwargs: dict[str, object] = {
            f: str(payload.get(f) or "") for f in _TEXT_FIELDS
        }
    except Exception:
        raise MALFORMED
    if not kwargs["pharmacyid"] or not kwargs["mobile"]:
        raise MALFORMED
    try:
        kwargs["vat_default"] = Decimal(str(payload.get("vat_default", "14.00")))
        kwargs["vat_inclusive_prices"] = _strict_bool(
            payload, "vat_inclusive_prices", True
        )
        kwargs["is_main_device"] = _strict_bool(payload, "is_main_device", False)
        kwargs["is_active"] = _strict_bool(payload, "is_active", True)
    except MALFORMED:
        raise
    except Exception:
        raise MALFORMED
    return kwargs


def _identity_keys(payload: dict) -> tuple[str, str, str, int]:
    try:
        return (
            str(payload["legacy_table"]),
            str(payload["legacy_column"]),
            str(payload["legacy_value"]),
            _strict_int(payload["branch_id"]),
        )
    except (KeyError, TypeError, ValueError):
        raise MALFORMED_IDENTITY


async def apply_branch_versioned(
    session: AsyncSession,
    *,
    payload: dict,
    user_id: Optional[int],
) -> tuple[str, Optional[str]]:
    """Apply one branch snapshot; returns (outcome, skip_reason)."""
    try:
        branch_id = _strict_int(payload["id"])
    except (KeyError, TypeError, ValueError):
        raise MALFORMED
    ts = _watermark_of(payload)

    local = await session.get(Branch, branch_id)
    local_ts = _local_watermark(local)
    if ts is not None and local_ts is not None and local_ts >= ts:
        if local_ts == ts:
            return (
                "skipped",
                "duplicate delivery — identical watermark, LWW kept local state",
            )
        return (
            "skipped",
            f"stale snapshot (updated_at={ts.isoformat()}) — local row is newer "
            f"({local_ts.isoformat()}), LWW kept local state",
        )
    if ts is None and local_ts is not None:
        # legacy snapshot (no ordering authority) vs a locally-watermarked
        # row: LWW cannot order them — keep local, record why (G10)
        return (
            "skipped",
            "legacy snapshot without updated_at — cannot be ordered against "
            "the locally-watermarked row; LWW kept local state",
        )

    fields = _fields_from_payload(payload)
    # legacy rows apply with the EPOCH as watermark: deterministic across
    # peers (no per-peer clock fabrication → no divergence) and guaranteed
    # older than any real snapshot, so future deliveries always win
    applied_ts = ts if ts is not None else _EPOCH
    old_name = local.pharname if local is not None else None
    if local is None:
        session.add(Branch(id=branch_id, **fields, updated_at=applied_ts))
        await session.flush()
        await _advance_identity_sequence(session, "branches", branch_id)
        action = ACTION_INSERT
    else:
        for key, value in fields.items():
            setattr(local, key, value)
        local.updated_at = applied_ts
        action = ACTION_UPDATE
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="branch",
        entity_id=branch_id,
        field="snapshot",
        old_value=old_name,
        new_value=str(fields["pharname"]),
        action=action,
        namee=str(fields["pharmacyid"]),
    )
    return ("applied", None)


async def apply_identity_versioned(
    session: AsyncSession,
    *,
    payload: dict,
    user_id: Optional[int],
) -> tuple[str, Optional[str]]:
    """Apply one alias-mapping mutation; returns (outcome, skip_reason)."""
    legacy_table, legacy_column, legacy_value, branch_id = _identity_keys(payload)
    existing = (
        await session.execute(
            select(BranchIdentity).where(
                BranchIdentity.legacy_table == legacy_table,
                BranchIdentity.legacy_column == legacy_column,
                BranchIdentity.legacy_value == legacy_value,
            )
        )
    ).scalar_one_or_none()

    if payload.get("_deleted"):
        if existing is None:
            return ("skipped", "delete replayed — mapping already absent")
        await session.delete(existing)
        await session.flush()
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="branch_identity",
            field="legacy_value",
            old_value=f"{legacy_table}.{legacy_column}={legacy_value}",
            action=ACTION_DELETE,
        )
        return ("applied", None)

    if existing is not None and existing.branch_id == branch_id:
        return (
            "skipped",
            f"duplicate identity delivery — "
            f"{legacy_table}.{legacy_column}={legacy_value} already maps to "
            f"branch {branch_id}",
        )

    action = ACTION_INSERT if existing is None else ACTION_UPDATE
    # capture BEFORE the re-point overwrites it, or the audit row records
    # old == new and the previous mapping is lost
    previous_branch_id = existing.branch_id if existing is not None else None
    if existing is None:
        session.add(
            BranchIdentity(
                legacy_table=legacy_table,
                legacy_column=legacy_column,
                legacy_value=legacy_value,
                branch_id=branch_id,
            )
        )
    else:
        # same alias re-pointed: the LAST delivery wins (outbox order)
        existing.branch_id = branch_id
    await session.flush()
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="branch_identity",
        field="branch_id",
        old_value=None if previous_branch_id is None else str(previous_branch_id),
        new_value=str(branch_id),
        action=action,
    )
    return ("applied", None)
