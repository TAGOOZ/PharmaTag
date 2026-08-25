"""Versioned offline replay of `entity='purchase_order'` outbox rows (#33).

POs are non-money until the purchases receipt links up (N5) — replay restores
header + lines VERBATIM from the snapshot. Ordering authority is the monotonic
`rev` watermark (pending=1, saved/cancelled=2); rev <= local rev → skipped.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit
from app.models import PurchaseOrder, PurchaseOrderLine

REV_BY_STATUS = {"pending": 1, "saved": 2, "cancelled": 3}

MALFORMED = HTTPException(
    status.HTTP_400_BAD_REQUEST, "malformed purchase order outbox row"
)


def _parse_date(raw) -> dt.date | None:
    if raw is None:
        return None
    try:
        return dt.date.fromisoformat(str(raw))
    except ValueError:
        raise MALFORMED


def _dec4(raw):
    try:
        return None if raw is None else Decimal(str(raw))
    except InvalidOperation:
        raise MALFORMED


def _rev_of(payload: dict) -> int:
    raw = payload.get("rev")
    if raw is None:
        return REV_BY_STATUS.get(str(payload.get("status")), 1)
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise MALFORMED


async def apply_po_versioned(
    session: AsyncSession,
    *,
    payload: dict,
    user_id: int | None,
) -> str:
    try:
        po_id = int(payload["id"])
        branch_id = int(payload["branch_id"])
        status_str = str(payload["status"])
        lines = payload["lines"]
    except (KeyError, TypeError, ValueError):
        raise MALFORMED
    if not isinstance(lines, list):
        raise MALFORMED

    local = await session.get(PurchaseOrder, po_id)
    rev = _rev_of(payload)
    if local is not None and int(local.rev or 1) >= rev:
        return "skipped"

    old_status = local.status if local is not None else None
    party_id = payload.get("party_id")
    fields = dict(
        branch_id=branch_id,
        party_id=int(party_id) if party_id is not None else None,
        orderid=str(payload.get("orderid", "")),
        orderdate=_parse_date(payload.get("orderdate")),
        datee=_parse_date(payload.get("datee")),
        status=status_str,
        rev=rev,
    )

    # lines: verbatim replace (replay never merges — the snapshot is truth)
    await session.execute(
        delete(PurchaseOrderLine).where(PurchaseOrderLine.order_id == po_id)
    )
    for line in lines:
        try:
            drug_id = int(line["drug_id"])
            qty = Decimal(str(line["qty"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise MALFORMED
        row = PurchaseOrderLine(
            order_id=po_id,
            drug_id=drug_id,
            qty=qty,
            unit_cost=_dec4(line.get("unit_cost")),
        )
        session.add(row)

    if local is None:
        session.add(PurchaseOrder(id=po_id, **fields))
        from app.needs.replay import _advance_identity_sequence

        await _advance_identity_sequence(session, "purchase_orders", po_id)
        action = ACTION_INSERT
    else:
        for key, value in fields.items():
            setattr(local, key, value)
        action = ACTION_UPDATE
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="purchase_order",
        entity_id=po_id,
        field="status",
        old_value=old_status,
        new_value=status_str,
        action=action,
    )
    return "applied"
