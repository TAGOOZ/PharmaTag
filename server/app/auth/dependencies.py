"""FastAPI dependencies: current-user resolution from the Bearer token."""
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import security
from app.core.db import get_session
from app.models import User


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = security.decode_token(token)
    except security.InvalidTokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token"
        ) from None
    if payload.get("kind") == "refresh":
        # a refresh token is only usable by the (future) refresh flow, never
        # as a bearer credential for protected endpoints (30-day lifetime)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token"
        )
    user = await session.get(User, int(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token"
        )
    return user