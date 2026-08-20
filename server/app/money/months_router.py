"""Month-close endpoints (S2.6, issue #21).

Close/reopen are ledger-area writes (plan/02 4.5, G12) gated by the granular
`months.close` permission (legacy floor 7 — same as the other ledger slices;
granted to admin / accountant / manager). Reopen is the coarse level-7 gate
(A07: manager-only, writes reversal + audit). Reads (list/detail/open-balances)
are open to any authenticated user so reports and the trial balance can inspect
the archive; every endpoint is branch-scoped to the caller.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import caller_branch_id
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level, require_permission
from app.core.db import get_session
from app.models import User
from app.money import monthclose

router = APIRouter()

MONTHS_CLOSE = require_permission("months.close")
REOPEN = require_level(7)


@router.get("", status_code=status.HTTP_200_OK)
async def list_months(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return {"months": await monthclose.list_month_closes(session, branch_id=branch_id)}


@router.get("/{year}/{month}")
async def get_month(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return await monthclose.get_month_close(session, branch_id=branch_id, year=year, month=month)


@router.get("/{year}/{month}/open-balances")
async def get_open_balances(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return await monthclose.get_open_balances(session, branch_id=branch_id, year=year, month=month)


@router.post("/{year}/{month}/close", status_code=status.HTTP_200_OK)
async def close_month(
    year: int,
    month: int,
    caller: User = Depends(MONTHS_CLOSE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    return await monthclose.close_month(
        session, branch_id=branch_id, user_id=caller.id, year=year, month=month
    )


@router.post("/{year}/{month}/reopen", status_code=status.HTTP_200_OK)
async def reopen_month(
    year: int,
    month: int,
    caller: User = Depends(REOPEN),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    return await monthclose.reopen_month(
        session, branch_id=branch_id, user_id=caller.id, year=year, month=month
    )
