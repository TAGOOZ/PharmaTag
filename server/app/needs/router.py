"""Need endpoints (ticket #33, S5.3).

Writes are gated by `needs.manage` (seeded to admin/pharmacist/manager,
legacy floor 3 — stock area). Reads are open to any authenticated user but
scoped to needs the caller's branch participates in. The caller's branch is
always the requesting side; `sender_branch_id` optionally pins one fulfilling
branch.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.needs import service

router = APIRouter()

MANAGE_NEEDS = require_permission("needs.manage")


class CreateNeedRequest(BaseModel):
    drug_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    sender_branch_id: Optional[int] = None
    datee: Optional[date] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_need(
    body: CreateNeedRequest,
    caller: User = Depends(MANAGE_NEEDS),
    session: AsyncSession = Depends(get_session),
):
    need = await service.create_need(
        session,
        caller=caller,
        drug_id=body.drug_id,
        qty=body.qty,
        sender_branch_id=body.sender_branch_id,
        datee=body.datee,
    )
    return service.public_need(need)


@router.get("")
async def list_needs(
    status_filter: Optional[str] = None,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await service.list_needs(session, caller, status_filter=status_filter)
    return {"needs": [service.public_need(need) for need in rows]}


@router.get("/suggestions")
async def suggestions(
    mode: str,
    window_days: Annotated[int, Field(ge=1, le=365)] = 14,
    coverage_days: Annotated[int, Field(ge=1, le=365)] = 7,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Auto-order suggestions for the caller's branch (read-only advice).

    `mode=minimum` — half-auto (stock < minimum, top-up to par);
    `mode=sales_rate` — velocity over `window_days` × `coverage_days` minus
    on-hand. Egypt daily-replenishment defaults: 14 / 7.
    """
    from app.needs import suggestions as engine

    if caller.branch_id is None:
        raise service.NO_BRANCH
    try:
        rows = await engine.suggest(
            session,
            branch_id=caller.branch_id,
            mode=mode,
            window_days=window_days,
            coverage_days=coverage_days,
        )
    except engine.UnknownMode:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown suggestion mode")
    return {"suggestions": rows}


@router.get("/{need_id}")
async def get_need(
    need_id: int,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    need = await service.get_need(session, need_id)
    parties = {need.branch_id, need.sender_branch_id} - {None}
    if caller.branch_id not in parties:
        raise service.NOT_FOUND  # existence of foreign needs is not disclosed
    return service.public_need(need)


@router.post("/{need_id}/cancel")
async def cancel_need(
    need_id: int,
    caller: User = Depends(MANAGE_NEEDS),
    session: AsyncSession = Depends(get_session),
):
    need = await service.get_need(session, need_id)
    await service.cancel_need(session, caller=caller, need=need)
    return service.public_need(need)


@router.post("/{need_id}/transfer", status_code=status.HTTP_201_CREATED)
async def handoff_need_to_transfer(
    need_id: int,
    response: Response,
    caller: User = Depends(MANAGE_NEEDS),
    session: AsyncSession = Depends(get_session),
):
    """Sender picks up a pending need → transfer draft sender→requester.

    201 = fresh draft; 200 = the need's existing live draft is replayed
    (idempotent double-click / retry contract).
    """
    from app.transfers import service as tservice

    # no router-level party guard here: eligibility (pinned sender vs open-
    # request volunteers) is decided inside the service UNDER the handoff lock,
    # where a racing pickup's committed state is visible.
    need = await service.get_need(session, need_id)
    transfer, created = await service.create_handoff_transfer(
        session, caller=caller, need=need
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    _, lines = await tservice.get_transfer(session, transfer.id)
    return tservice.public_transfer(transfer, lines)


