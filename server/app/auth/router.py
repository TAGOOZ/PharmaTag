"""Auth endpoints: login (token pair) + me (identity of the bearer token)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import security
from app.auth.dependencies import get_current_user
from app.core.db import get_session
from app.models import User

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "namee": user.namee,
        "permission_level": user.permission_level,
        "branch_id": user.branch_id,
    }


@router.post("/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(User)
        .where(User.username == body.username)
        .options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid username or password"
        )
    ok, legacy = security.verify_password(body.password, user.pass_hash)
    if not ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid username or password"
        )
    roles = [r.name for r in user.roles]
    branch_id = user.branch_id
    return {
        "access_token": security.create_access_token(
            str(user.id), branch_id=branch_id, roles=roles,
            permission_level=user.permission_level,
        ),
        "refresh_token": security.create_refresh_token(
            str(user.id), branch_id=branch_id
        ),
        "token_type": "bearer",
        "must_reset_password": legacy,
        "user": _public_user(user),
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return _public_user(user)