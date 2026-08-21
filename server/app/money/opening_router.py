"""Opening balances endpoints (S2.7, issue #22).

POST /{year}/{month} creates balanced افتتاحي per account/branch — a
`journals` entry (source=opening, predated) + a `month_open_balances` snapshot
for that month — atomically with audit (G12) and the branch advisory lock.
GET returns the snapshot; listing returns every opening period for the branch.

Permission: `opening_balances.manage` (ledger area, floor 7 — admin/accountant/
manager per plan/02 §3). Reads are open to any authenticated, branch-scoped user
so the مزان and the `GET /months/.../open-balances` archival view can inspect
the opening without ledger rights.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import caller_branch_id
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.money import opening
from app.money.opening_schemas import OpeningBalancesCreate

router = APIRouter()

OPENING_WRITE = require_permission("opening_balances.manage")


@router.get("", status_code=status.HTTP_200_OK)
async def list_openings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return {"periods": await opening.list_opening_balances(session, branch_id=branch_id)}


@router.get("/{year}/{month}", status_code=status.HTTP_200_OK)
async def get_opening(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return await opening.get_opening_balances(session, branch_id=branch_id, year=year, month=month)


@router.post("/{year}/{month}", status_code=status.HTTP_201_CREATED)
async def post_opening(
    year: int,
    month: int,
    body: OpeningBalancesCreate,
    caller: User = Depends(OPENING_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    return await opening.post_opening_balances(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        year=year,
        month=month,
        description=body.description,
        lines=body.lines,
    )


@router.delete("/{year}/{month}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opening(
    year: int,
    month: int,
    caller: User = Depends(OPENING_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    await opening.delete_opening_balances(
        session, branch_id=branch_id, user_id=caller.id, year=year, month=month
    )
