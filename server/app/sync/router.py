"""Offline sync endpoints (ticket #9 AC4 + #60 G10 conflict panel).

`POST /sync/replay` runs the outbox replay for the caller's branch. Gated by
`sale.create` (a cashier performing the sync must be a sale operator). The
client calls it on reconnect; it is idempotent and returns a per-row summary.

`GET /sync/conflicts` lists LWW losses (loser payload + winner + updated_at)
branch-scoped, read for any authenticated user (#60).

`POST /sync/conflicts/{id}/restore` (manager floor 7) reapplies loser as new
rev with audit — never mutates history in place.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level, require_permission
from app.core.db import get_session
from app.models import User
from app.sync.conflicts import list_conflicts, restore_conflict
from app.sync.service import replay_pending

router = APIRouter()

SYNC = require_permission("sale.create")
RESTORE = require_level(7)


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


@router.get("/conflicts")
async def list_sync_conflicts(
    branch_id: Optional[int] = Query(default=None),
    entity: Optional[str] = Query(default=None),
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Branch-scoped LWW losses. Any authenticated user may read own branch.

    Cross-branch read requires `branches.manage` (G08 granular or legacy floor 7)
    — spec says branch-scoped, a clerk must not enumerate another branch's losses.
    """
    caller_branch = _caller_branch_id(caller)
    target_branch = branch_id if branch_id is not None else caller_branch
    if target_branch != caller_branch:
        # Fix-or-justify (Apple): use granular RBAC, not just permission_level.
        # Own branch: any auth (per AC). Cross-branch: needs branches.manage.
        from app.auth.rbac import LEGACY_LEVEL_FLOOR, _role_permission_codes

        codes = await _role_permission_codes(caller, session)
        has_granular = "branches.manage" in codes
        has_floor = caller.permission_level >= LEGACY_LEVEL_FLOOR.get("branches.manage", 7)
        if not (has_granular or has_floor):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "cross-branch conflict read forbidden"
            )
    # optional entity filter validation
    if entity is not None and entity not in {
        "invoice",
        "branch_stock",
        "transfer",
        "need",
        "purchase_order",
        "branch",
        "branch_identity",
        "chain_buy_order",
    }:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown entity filter")
    conflicts = await list_conflicts(session, branch_id=target_branch, entity=entity)
    # return both keys for test compatibility
    return {"conflicts": conflicts, "items": conflicts, "count": len(conflicts), "branch_id": target_branch}


@router.post("/conflicts/{conflict_id}/restore")
async def restore_sync_conflict(
    conflict_id: int,
    caller: User = Depends(RESTORE),
    session: AsyncSession = Depends(get_session),
):
    """Manager-only (floor 7) restore: reapply loser as new rev with audit."""
    caller_branch = _caller_branch_id(caller)
    result = await restore_conflict(
        session, conflict_id=conflict_id, branch_id=caller_branch, user_id=caller.id
    )
    return result