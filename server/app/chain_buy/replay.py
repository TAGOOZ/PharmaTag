"""Versioned (absolute LWW) offline replay for chain-buy orders (S5.6).

Chain-buy is non-money, absolute LWW: the last delivered snapshot overwrites
verbatim (no rev watermark, no stage folding). A replay that references a
missing drug is poisoned (409) — recorded as failed, retryable after the drug
is synced (G10).

Explicit-id inserts do NOT advance the PG identity sequence — bump it so a
later local create does not collide with an already-replayed id (needs 033
precedent). SQLite AUTOINCREMENT handles this natively.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit
from app.models import ChainBuyOrder, Drug

MALFORMED = HTTPException(status.HTTP_400_BAD_REQUEST, "malformed chain buy outbox row")


def _parse_date(raw) -> dt.date | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, dt.date) and not isinstance(raw, dt.datetime):
        return raw
    if isinstance(raw, dt.datetime):
        return raw.date()
    try:
        return dt.date.fromisoformat(str(raw))
    except ValueError:
        raise MALFORMED


def _parse_dt(raw) -> dt.datetime | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, dt.datetime):
        if raw.tzinfo is None:
            raw = raw.replace(tzinfo=dt.timezone.utc)
        return raw
    try:
        ts = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        return ts
    except ValueError:
        raise MALFORMED


def _dec(raw, _field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise MALFORMED


async def _advance_identity_sequence(session: AsyncSession, table: str, inserted_id: int) -> None:
    from sqlalchemy import text as _text

    bind = getattr(session.get_bind(), "dialect", None)
    if getattr(bind, "name", "") != "postgresql":
        return
    await session.execute(
        _text(
            f"SELECT setval("
            f" pg_get_serial_sequence('{table}', 'id'),"
            f" GREATEST((SELECT last_value FROM {table}_id_seq), :iid))"
        ),
        {"iid": inserted_id},
    )


async def apply_chain_buy_versioned(
    session: AsyncSession,
    *,
    payload: dict,
    peer_branch_id: int,  # kept for uniform sync/service.py signature; chain-buy is global (payload branch_id is owner, not peer)
    user_id: Optional[int] = None,
) -> str:
    """Absolute LWW apply of one chain-buy snapshot.

    * drug missing → 409 (poisoned row)
    * SELECT by id FOR UPDATE, if not exists create, else overwrite all fields
      verbatim from payload (no merge), set updated_at=now(). Idempotent: a
      re-delivery with identical snapshot silently re-overwrites to the same
      state (no rev check).
    * peer_branch_id is ignored — chain-buy board is global (all branches see all
      orders). Signature kept for uniform dispatch in sync/service.py.
    """
    _ = peer_branch_id
    try:
        order_id = int(payload["id"])
        branch_id = int(payload["branch_id"])
        drug_id = int(payload["drug_id"])
        status_str = str(payload["status"])
    except (KeyError, TypeError, ValueError):
        raise MALFORMED

    # drug must exist on target store (G10: poisoned if missing)
    drug = await session.get(Drug, drug_id)
    if drug is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"drug {drug_id} does not exist on this store"
        )

    if status_str not in {"created", "in_transit", "delivered", "received", "cancelled"}:
        raise MALFORMED

    # fields verbatim — strings default to "" when missing for leniency, but
    # required qty/price/sell_disc must be present
    try:
        qty = _dec(payload["qty"], "qty")
        price = _dec(payload.get("price", "0"), "price")
        sell_disc = _dec(payload.get("sell_disc", "0"), "sell_disc")
    except KeyError as exc:
        raise MALFORMED from exc

    store_name = str(payload.get("store_name", ""))
    pharmacist_tel = str(payload.get("pharmacist_tel", ""))
    requester_tel = str(payload.get("requester_tel", ""))
    tips = str(payload.get("tips", ""))
    governorate = str(payload.get("governorate", ""))
    district = str(payload.get("district", ""))
    country = str(payload.get("country", ""))
    expire = _parse_date(payload.get("expire"))
    iddatetime = _parse_dt(payload.get("iddatetime"))
    created_at = _parse_dt(payload.get("created_at"))

    # single SELECT FOR UPDATE — avoids extra round-trip and races get→lock window
    from sqlalchemy import select

    local = (
        await session.execute(
            select(ChainBuyOrder).where(ChainBuyOrder.id == order_id).with_for_update()
        )
    ).scalar_one_or_none()

    now = dt.datetime.now(dt.timezone.utc)
    fields = dict(
        branch_id=branch_id,
        drug_id=drug_id,
        store_name=store_name,
        pharmacist_tel=pharmacist_tel,
        requester_tel=requester_tel,
        qty=qty,
        price=price,
        sell_disc=sell_disc,
        expire=expire,
        tips=tips,
        governorate=governorate,
        district=district,
        country=country,
        iddatetime=iddatetime,
        status=status_str,
        updated_at=now,
    )

    # preserve created_at when present, else set to now
    fields_created = created_at if created_at is not None else now

    if local is None:
        session.add(
            ChainBuyOrder(
                id=order_id,
                **fields,
                created_at=fields_created,
            )
        )
        await _advance_identity_sequence(session, "chain_buy_orders", order_id)
        action = ACTION_INSERT
        old_status = None
    else:
        # capture old before mutate — else audit old_value == new_value
        old_status = local.status
        for k, v in fields.items():
            setattr(local, k, v)
        # keep original created_at unless payload overrides it explicitly
        if created_at is not None:
            local.created_at = created_at
        action = ACTION_UPDATE

    # flush so FK/CHECK violations surface inside the savepoint
    await session.flush()

    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="chain_buy_order",
        entity_id=order_id,
        field="status",
        old_value=old_status,
        new_value=status_str,
        drug_id=drug_id,
        barcode="",
        action=action,
    )
    return "applied"
