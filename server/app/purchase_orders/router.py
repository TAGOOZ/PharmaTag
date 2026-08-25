"""Purchase-order endpoints (ticket #33, S5.3).

Writes gated by `needs.manage` (same stock-area permission as needs, seeded
admin/pharmacist/manager, legacy floor 3). Reads scoped to the caller's
branch; foreign POs 404.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.purchase_orders import service

router = APIRouter()

MANAGE_NEEDS = require_permission("needs.manage")


class POLine(BaseModel):
    drug_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_cost: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )


class CreatePORequest(BaseModel):
    party_id: Optional[int] = None
    orderid: str = Field(default="", max_length=50)
    orderdate: Optional[date] = None
    datee: Optional[date] = None
    lines: list[POLine] = Field(min_length=1)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_po(
    body: CreatePORequest,
    caller: User = Depends(MANAGE_NEEDS),
    session: AsyncSession = Depends(get_session),
):
    po, lines = await service.create_po(
        session,
        caller=caller,
        party_id=body.party_id,
        orderid=body.orderid,
        orderdate=body.orderdate,
        datee=body.datee,
        lines=[line.model_dump() for line in body.lines],
    )
    return service.public_po(po, lines)


@router.get("")
async def list_pos(
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await service.list_pos(session, caller)
    return {
        "purchase_orders": [service.public_po(po, lines) for po, lines in rows]
    }


@router.get("/{po_id}")
async def get_po(
    po_id: int,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    po, lines = await service.get_po(session, po_id)
    if caller.branch_id != po.branch_id:
        raise service.NOT_FOUND
    return service.public_po(po, lines)


@router.post("/{po_id}/save")
async def save_po(
    po_id: int,
    caller: User = Depends(MANAGE_NEEDS),
    session: AsyncSession = Depends(get_session),
):
    po, _ = await service.get_po(session, po_id)
    po, lines = await service.transition_po(
        session, caller=caller, po=po, action="save"
    )
    return service.public_po(po, lines)


@router.post("/{po_id}/cancel")
async def cancel_po(
    po_id: int,
    caller: User = Depends(MANAGE_NEEDS),
    session: AsyncSession = Depends(get_session),
):
    po, _ = await service.get_po(session, po_id)
    po, lines = await service.transition_po(
        session, caller=caller, po=po, action="cancel"
    )
    return service.public_po(po, lines)
