"""Purchase-order use-cases (#33): create, list, save, cancel.

Legacy `orders` semantics: status NULL=pending → 'pending'; 'saved' = the
order is finalized/sent to the distributor. `received` is deliberately
unreachable in this slice — it belongs to the purchases-receipt seam, which
is the only place stock/GL may move (N5). Every mutation writes its audit
row + `entity='purchase_order'` outbox rows atomically (G12); `rev` bumps per
transition (versioned replay ordering).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.core.money import dec, round4
from app.models import Drug, Party, PurchaseOrder, PurchaseOrderLine, User

ENTITY = "purchase_order"

# Strictly increasing ladder — save then cancel must yield rev 3 or a
# versioned peer would skip the cancel payload (rev <= local rev after save).
REV_CREATE = 1
REV_SAVED = 2
REV_CANCELLED = 3

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "purchase order not found")
NO_BRANCH = HTTPException(
    status.HTTP_403_FORBIDDEN, "caller is not pinned to a branch"
)
UNKNOWN_DRUG = HTTPException(status.HTTP_400_BAD_REQUEST, "unknown drug in lines")
UNKNOWN_PARTY = HTTPException(status.HTTP_400_BAD_REQUEST, "unknown supplier")
DUPLICATE_DRUG = HTTPException(
    status.HTTP_400_BAD_REQUEST, "duplicate drug in lines"
)
BAD_STATE = HTTPException(
    status.HTTP_409_CONFLICT, "purchase order state does not allow this"
)


def _qty4(value: Optional[Decimal]) -> Optional[str]:
    return None if value is None else format(round4(value), "f")


def public_po(po: PurchaseOrder, lines: list[PurchaseOrderLine]) -> dict:
    return {
        "id": po.id,
        "branch_id": po.branch_id,
        "party_id": po.party_id,
        "orderid": po.orderid,
        "orderdate": po.orderdate.isoformat() if po.orderdate else None,
        "datee": po.datee.isoformat() if po.datee else None,
        "status": po.status,
        "rev": int(po.rev or 1),
        "created_at": po.created_at.isoformat() if po.created_at else None,
        "saved_at": po.saved_at.isoformat() if po.saved_at else None,
        "cancelled_at": po.cancelled_at.isoformat() if po.cancelled_at else None,
        "lines": [
            {
                "id": line.id,
                "drug_id": line.drug_id,
                "qty": _qty4(line.qty),
                "unit_cost": _qty4(line.unit_cost),
                "received_qty": _qty4(line.received_qty),
            }
            for line in lines
        ],
    }


def snapshot_payload(po: PurchaseOrder, lines: list[PurchaseOrderLine]) -> dict:
    stamps = [
        ts for ts in (po.cancelled_at, po.saved_at, po.created_at) if ts is not None
    ]
    return {
        "kind": ENTITY,
        "id": po.id,
        "branch_id": po.branch_id,
        "party_id": po.party_id,
        "orderid": po.orderid,
        "orderdate": po.orderdate.isoformat() if po.orderdate else None,
        "datee": po.datee.isoformat() if po.datee else None,
        "status": po.status,
        "rev": int(po.rev or 1),
        "updated_at": max(stamps).isoformat() if stamps else None,
        "lines": [
            {
                "drug_id": line.drug_id,
                "qty": _qty4(line.qty),
                "unit_cost": _qty4(line.unit_cost),
            }
            for line in lines
        ],
    }


async def get_po(
    session: AsyncSession, po_id: int
) -> tuple[PurchaseOrder, list[PurchaseOrderLine]]:
    po = (await session.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    )).scalar_one_or_none()
    if po is None:
        raise NOT_FOUND
    lines = (
        await session.execute(
            select(PurchaseOrderLine)
            .where(PurchaseOrderLine.order_id == po.id)
            .order_by(PurchaseOrderLine.id)
        )
    ).scalars().all()
    return po, list(lines)


async def create_po(
    session: AsyncSession,
    *,
    caller: User,
    party_id: Optional[int],
    orderid: str,
    orderdate: Optional[date],
    datee: Optional[date],
    lines: list[dict],
) -> tuple[PurchaseOrder, list[PurchaseOrderLine]]:
    if caller.branch_id is None:
        raise NO_BRANCH
    if party_id is not None:
        known_party = (await session.execute(
            select(Party.id).where(Party.id == party_id)
        )).scalar_one_or_none()
        if known_party is None:
            raise UNKNOWN_PARTY
    drug_ids = [line["drug_id"] for line in lines]
    if len(drug_ids) != len(set(drug_ids)):
        raise DUPLICATE_DRUG
    known = {
        row
        for row in (
            await session.execute(select(Drug.id).where(Drug.id.in_(drug_ids)))
        ).scalars().all()
    }
    missing = set(drug_ids) - known
    if missing:
        raise UNKNOWN_DRUG

    async with atomic(session):
        po = PurchaseOrder(
            branch_id=caller.branch_id,
            party_id=party_id,
            orderid=orderid,
            orderdate=orderdate,
            datee=datee,
            status="pending",
            rev=REV_CREATE,
            created_by=caller.id,
        )
        session.add(po)
        await session.flush()
        po_lines = [
            PurchaseOrderLine(
                order_id=po.id,
                drug_id=line["drug_id"],
                qty=dec(line["qty"]),
                unit_cost=None if line.get("unit_cost") is None else dec(line["unit_cost"]),
            )
            for line in lines
        ]
        session.add_all(po_lines)
        await session.flush()

        await audit(
            session,
            branch_id=po.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=po.id,
            field="status",
            old_value=None,
            new_value=po.status,
            action=ACTION_INSERT,
        )
        payload = snapshot_payload(po, po_lines)
        await enqueue_sync(
            session,
            branch_id=po.branch_id,
            entity=ENTITY,
            entity_id=po.id,
            action=ACTION_INSERT,
            payload=payload,
        )
    return po, po_lines


async def list_pos(session: AsyncSession, caller: User) -> list[tuple]:
    """POs owned by the caller's branch (C9 scoping), newest first.
    Lines fetched in ONE query and grouped (no per-row N+1)."""
    if caller.branch_id is None:
        return []
    rows = (
        await session.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.branch_id == caller.branch_id)
            .order_by(PurchaseOrder.id.desc())
        )
    ).scalars().all()
    if not rows:
        return []
    all_lines = (
        await session.execute(
            select(PurchaseOrderLine)
            .where(
                PurchaseOrderLine.order_id.in_([po.id for po in rows])
            )
            .order_by(PurchaseOrderLine.id)
        )
    ).scalars().all()
    by_order: dict[int, list[PurchaseOrderLine]] = {}
    for line in all_lines:
        by_order.setdefault(line.order_id, []).append(line)
    return [(po, by_order.get(po.id, [])) for po in rows]


async def transition_po(
    session: AsyncSession,
    *,
    caller: User,
    po: PurchaseOrder,
    action: str,
) -> tuple[PurchaseOrder, list[PurchaseOrderLine]]:
    """pending → saved | cancelled; saved → cancelled; terminal otherwise."""
    if caller.branch_id != po.branch_id:
        raise NOT_FOUND  # existence of foreign POs is not disclosed

    transitions = {
        "save": {
            "pending": ("saved", "saved_at", REV_SAVED),
        },
        "cancel": {
            "pending": ("cancelled", "cancelled_at", REV_CANCELLED),
            "saved": ("cancelled", "cancelled_at", REV_CANCELLED),
        },
    }
    table = transitions[action]
    if po.status not in table:
        raise BAD_STATE
    new_status, stamp_field, new_rev = table[po.status]

    async with atomic(session):
        po, lines = await get_po(session, po.id)
        if po.status not in table:  # re-check under the write transaction
            raise BAD_STATE
        old_status = po.status
        setattr(po, stamp_field, datetime.now(timezone.utc))
        po.status = new_status
        po.rev = new_rev
        session.add(po)
        await audit(
            session,
            branch_id=po.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=po.id,
            field="status",
            old_value=old_status,
            new_value=po.status,
            action=ACTION_UPDATE,
        )
        payload = snapshot_payload(po, lines)
        await enqueue_sync(
            session,
            branch_id=po.branch_id,
            entity=ENTITY,
            entity_id=po.id,
            action=ACTION_UPDATE,
            payload=payload,
        )
    return po, lines
