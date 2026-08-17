"""Offline sync endpoints (ticket #9 AC4).

`POST /sync/replay` runs the outbox replay for the caller's branch. Gated by
`sale.create` (a cashier performing the sync must be a sale operator). The
client calls it on reconnect; it is idempotent and returns a per-row summary.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.sync.service import replay_pending

router = APIRouter()

SYNC = require_permission("sale.create")


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


@router.post("/replay")
async def replay(
    caller: User = Depends(SYNC),
    session: AsyncSession = Depends(get_session),
):
    branch_id = _caller_branch_id(caller)
    summary = await replay_pending(session, branch_id=branch_id, user_id=caller.id)
    return summary