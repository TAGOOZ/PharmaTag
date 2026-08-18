"""Drawer + day-close endpoints (S1.8, ticket #14, A07).

Manual movements are gated by `drawer.manage` (legacy level-3 area, plan/02 §3,
customizable via granular role permissions). Day close sits on `day.close`
(level 7); reopen is the coarse level-7 gate with the reversal + audit (A07).
Reads are branch-scoped to the caller. All money leaves as exact decimal
strings (plan/02 §2).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level, require_permission
from app.core import money
from app.core.db import atomic, get_session
from app.core.time import business_date
from app.drawer import schemas
from app.drawer.close import close_day, reopen_day
from app.drawer.movements import record_movement
from app.models import DailyClose, DrawerMovement, User

router = APIRouter()

MANAGE_DRAWER = require_permission("drawer.manage")
DAY_CLOSE = require_permission("day.close")
REOPEN = require_level(7)


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


def _money(value) -> str:
    return money.format2(value)


def _serialize_movement(row: DrawerMovement) -> dict:
    return schemas.MovementOut(
        id=row.id,
        branch_id=row.branch_id,
        datee=row.datee.isoformat(),
        direction=row.direction,
        reason=row.reason,
        method=row.method,
        amount=_money(row.amount),
        user_id=row.user_id,
        ref_invoice_id=row.ref_invoice_id,
        created_at=row.created_at.isoformat() if row.created_at else "",
    ).model_dump()


def _serialize_close(row: DailyClose) -> dict:
    return schemas.DayCloseOut(
        id=row.id,
        branch_id=row.branch_id,
        datee=row.datee.isoformat(),
        drawer_start=_money(row.drawer_start),
        expected_cash=_money(row.expected_cash),
        counted_cash=_money(row.counted_cash),
        difference=_money(row.difference),
        net_cash=_money(row.net_cash),
        net_network=_money(row.net_network),
        manual_cash=_money(row.manual_cash),
        manual_card=_money(row.manual_card),
        purchases=_money(row.purchases),
        expenses=_money(row.expenses),
        cost_of_sales=_money(row.cost_of_sales),
        net_profit=_money(row.net_profit),
        discounts=_money(row.discounts),
        vat_sales=_money(row.vat_sales),
        vat_purchases=_money(row.vat_purchases),
        vat_expenses=_money(row.vat_expenses),
        status=row.status,
        closed_by=row.closed_by,
        closed_at=row.closed_at.isoformat() if row.closed_at else None,
    ).model_dump()


@router.get("/movements")
async def list_movements(
    datee: Optional[date] = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Drawer movements for the caller's branch (today by default)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 500))
    q = select(DrawerMovement).where(DrawerMovement.branch_id == branch_id)
    if datee is not None:
        q = q.where(DrawerMovement.datee == datee)
    else:
        q = q.where(DrawerMovement.datee == business_date())
    q = q.order_by(DrawerMovement.id.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return {"movements": [_serialize_movement(r) for r in rows]}


@router.post("/movements", status_code=status.HTTP_201_CREATED)
async def create_movement(
    body: schemas.MovementCreate,
    caller: User = Depends(MANAGE_DRAWER),
    session: AsyncSession = Depends(get_session),
):
    """Record one manual drawer movement (opening/expense/transfer/correction/
    supplier pay/customer settlement) with its audit; rejects a closed day and
    a ref_invoice_id from another branch (both checked under the branch lock
    inside `record_movement`)."""
    branch_id = _caller_branch_id(caller)
    async with atomic(session):
        row = await record_movement(
            session,
            branch_id=branch_id,
            user_id=caller.id,
            datee=body.datee or business_date(),
            direction=body.direction,
            reason=body.reason,
            method=body.method,
            amount=body.amount,
            ref_invoice_id=body.ref_invoice_id,
        )
    return _serialize_movement(row)


@router.get("/day-close")
async def list_day_close(
    datee: Optional[date] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Day-close snapshots for the caller's branch (today by default)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(DailyClose).where(DailyClose.branch_id == branch_id)
    if datee is not None:
        q = q.where(DailyClose.datee == datee)
    else:
        q = q.where(DailyClose.datee == business_date())
    q = q.order_by(DailyClose.id.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return {"day_closes": [_serialize_close(r) for r in rows]}


@router.post("/day-close", status_code=status.HTTP_200_OK)
async def create_day_close(
    body: schemas.DayCloseCreate,
    caller: User = Depends(DAY_CLOSE),
    session: AsyncSession = Depends(get_session),
):
    """Compute the drawer equation and lock the day as closed (409 if already
    closed); reopening a closed day must go through the reopen endpoint."""
    branch_id = _caller_branch_id(caller)
    row = await close_day(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        datee=body.datee or business_date(),
        counted_cash=body.counted_cash,
    )
    return _serialize_close(row)


@router.post("/day-close/{close_id}/reopen", status_code=status.HTTP_200_OK)
async def reopen_day_close(
    close_id: int,
    caller: User = Depends(REOPEN),
    session: AsyncSession = Depends(get_session),
):
    """Reopen a closed day (perm >= 7): the close flips to `reopened` + audit
    reversal, so the day can take new movements and be closed again."""
    branch_id = _caller_branch_id(caller)
    row = await reopen_day(
        session, branch_id=branch_id, user_id=caller.id, daily_close_id=close_id
    )
    return _serialize_close(row)