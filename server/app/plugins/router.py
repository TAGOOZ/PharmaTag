"""Plugin registry management API (plan/08 §2.1, ticket #3 AC1).

Endpoints: GET list (per branch), POST enable/disable per branch. All audited
(action plugin_enable / plugin_disable). `GET` reflects the live registry
(DB-backed, refreshed on each call); enable/disable write the DB first, then
refresh the in-process registry.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_session
from app.models import User
from app.plugins.registry import registry

router = APIRouter()


class BranchRequest(BaseModel):
    branch_id: int = Field(gt=0)


@router.get("")
async def list_plugins(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    await registry.load(session)
    return {"plugins": registry.list_for(branch_id=user.branch_id)}


@router.post("/{slug}/enable")
async def enable_plugin(
    slug: str,
    body: BranchRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        await registry.enable(session, slug, branch_id=body.branch_id, user_id=user.id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"plugin {slug!r} is not installed")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return {"slug": slug, "branch_id": body.branch_id, "enabled": True}


@router.post("/{slug}/disable")
async def disable_plugin(
    slug: str,
    body: BranchRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        await registry.disable(session, slug, branch_id=body.branch_id, user_id=user.id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"plugin {slug!r} is not installed")
    return {"slug": slug, "branch_id": body.branch_id, "enabled": False}