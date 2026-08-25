"""Versioned offline replay of `entity='need'` outbox rows (#33).

Needs are non-money records — replay restores the RECORDED STATE VERBATIM
(no heuristics, no side effects beyond the row itself). Ordering authority is
the monotonic `rev` watermark (pending=1, fulfilled/cancelled=2); a payload
whose rev <= local rev is stale/duplicate → skipped.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit
from app.models import Need

REV_BY_STATUS = {"pending": 1, "fulfilled": 3, "cancelled": 3}

MALFORMED = HTTPException(status.HTTP_400_BAD_REQUEST, "malformed need outbox row")


def _parse_date(raw: Any) -> dt.date | None:
    if raw is None:
        return None
    try:
        return dt.date.fromisoformat(str(raw))
    except ValueError:
        raise MALFORMED


def _rev_of(payload: dict) -> int:
    raw = payload.get("rev")
    if raw is None:
        return REV_BY_STATUS.get(str(payload.get("status")), 1)
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise MALFORMED


def _need_from_payload(payload: dict, *, with_id: bool) -> dict:
    try:
        kwargs = dict(
            branch_id=int(payload["branch_id"]),
            drug_id=int(payload["drug_id"]),
            status=str(payload["status"]),
        )
    except (KeyError, TypeError, ValueError):
        raise MALFORMED
    qty = payload.get("qty")
    try:
        from decimal import Decimal

        kwargs["qty"] = Decimal(str(qty))
    except Exception:
        raise MALFORMED
    kwargs["datee"] = _parse_date(payload.get("datee"))
    sender = payload.get("sender_branch_id")
    target = payload.get("target_branch_id")
    transfer = payload.get("transfer_id")
    kwargs["sender_branch_id"] = int(sender) if sender is not None else None
    kwargs["target_branch_id"] = int(target) if target is not None else None
    kwargs["transfer_id"] = int(transfer) if transfer is not None else None
    kwargs["rev"] = _rev_of(payload)
    if with_id:
        try:
            kwargs["id"] = int(payload["id"])
        except (KeyError, TypeError, ValueError):
            raise MALFORMED
    return kwargs


async def apply_need_versioned(
    session: AsyncSession,
    *,
    payload: dict,
    user_id: int | None,
) -> str:
    need_id_raw = payload.get("id")
    try:
        need_id = int(need_id_raw)
    except (TypeError, ValueError):
        raise MALFORMED

    local = await session.get(Need, need_id)
    rev = _rev_of(payload)
    if local is not None and int(local.rev or 1) >= rev:
        return "skipped"

    fields = _need_from_payload(payload, with_id=False)
    old_status = local.status if local is not None else None
    if local is None:
        session.add(Need(id=need_id, **fields))
        await _advance_identity_sequence(session, "needs", need_id)
        action = ACTION_INSERT
    else:
        for key, value in fields.items():
            setattr(local, key, value)
        action = ACTION_UPDATE
    await audit(
        session,
        branch_id=fields["branch_id"],
        user_id=user_id,
        entity="need",
        entity_id=need_id,
        field="status",
        old_value=old_status,
        new_value=fields["status"],
        action=action,
    )
    return "applied"


async def _advance_identity_sequence(
    session: AsyncSession, table: str, inserted_id: int
) -> None:
    """Explicit-id replay inserts do NOT advance the PG identity sequence —
    a later LOCAL create could collide with an already-replayed id. Bump the
    sequence past it. SQLite AUTOINCREMENT handles this natively."""
    from sqlalchemy import text as _text

    bind = getattr(session.get_bind(), "dialect", None)
    if getattr(bind, "name", "") != "postgresql":
        return
    # table is a code-owned constant (never user input) — safe to interpolate;
    # PG identifiers cannot be bind params
    await session.execute(
        _text(
            f"SELECT setval("
            f" pg_get_serial_sequence('{table}', 'id'),"
            f" GREATEST((SELECT last_value FROM {table}_id_seq), :iid))"
        ),
        {"iid": inserted_id},
    )
