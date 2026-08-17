"""Users management endpoints (ticket #7 / plan/00 G08).

Every route is gated by `users.manage` — granted either granularly via a role
(admin) or by the legacy floor (permission_level >= 6, the legacy
"users/permissions" area). Create/update enforce the high-privilege rule in the
service: nobody creates/raises a user above their own permission_level, so a
level-7 target proves the plan/02 §3 balance-edit gate end-to-end.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.users import service

router = APIRouter()

MANAGE_USERS = require_permission("users.manage")


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    namee: str = Field(default="", max_length=100)
    mobile: Optional[str] = Field(default=None, max_length=15)
    permission_level: int = Field(ge=1, le=9)
    branch_id: Optional[int] = None
    initial_password: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=list)


class UpdateUserRequest(BaseModel):
    namee: Optional[str] = Field(default=None, max_length=100)
    mobile: Optional[str] = Field(default=None, max_length=15)
    active: Optional[bool] = None
    permission_level: Optional[int] = Field(default=None, ge=1, le=9)


class SetRolesRequest(BaseModel):
    roles: list[str]


class ManagerResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    caller: User = Depends(MANAGE_USERS),
    session: AsyncSession = Depends(get_session),
):
    user = await service.create_user(
        session,
        caller=caller,
        username=body.username,
        namee=body.namee,
        mobile=body.mobile,
        permission_level=body.permission_level,
        branch_id=body.branch_id,
        initial_password=body.initial_password,
        roles=body.roles,
    )
    return service.public_user(user)


@router.get("")
async def list_users(
    caller: User = Depends(MANAGE_USERS),
    session: AsyncSession = Depends(get_session),
):
    users = await service.list_users(session)
    return {"users": [service.public_user(u) for u in users]}


async def _get_or_404(session: AsyncSession, user_id: int) -> User:
    user = await service.get_user(session, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    caller: User = Depends(MANAGE_USERS),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_or_404(session, user_id)
    return service.public_user(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    caller: User = Depends(MANAGE_USERS),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_or_404(session, user_id)
    user = await service.update_user(
        session,
        caller=caller,
        user=user,
        namee=body.namee,
        mobile=body.mobile,
        active=body.active,
        permission_level=body.permission_level,
    )
    return service.public_user(user)


@router.post("/{user_id}/permissions")
async def set_user_permissions(
    user_id: int,
    body: SetRolesRequest,
    caller: User = Depends(MANAGE_USERS),
    session: AsyncSession = Depends(get_session),
):
    """Assign granular permissions by replacing the user's roles
    (user_roles -> role_permissions; the model that exists in rev 001)."""
    user = await _get_or_404(session, user_id)
    user = await service.set_user_roles(
        session, caller=caller, user=user, roles=body.roles
    )
    return service.public_user(user)


@router.post("/{user_id}/reset-password")
async def manager_reset_password(
    user_id: int,
    body: ManagerResetPasswordRequest,
    caller: User = Depends(MANAGE_USERS),
    session: AsyncSession = Depends(get_session),
):
    """Manager sets a new initial password for a user; the user is forced to
    reset it on their next login (P07)."""
    user = await _get_or_404(session, user_id)
    await service.manager_reset_password(
        session, user=user, new_password=body.new_password
    )
    return {"ok": True}