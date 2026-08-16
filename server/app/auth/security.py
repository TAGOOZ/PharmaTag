"""Password hashing + JWT issuance/verification (plan/02 §3).

Legacy plaintext hashes are detected (P07: force password reset on first
login); a `legacy` flag tells the client the stored hash predates the
bcrypt migration. New hashes are always bcrypt via passlib.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidTokenError(Exception):
    pass


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, stored: str) -> tuple[bool, bool]:
    """Return (ok, legacy). `legacy`=True when the stored value is pre-hash
    plaintext; such a login must be forced to reset (P07)."""
    if stored.startswith("$2"):
        return pwd_context.verify(plain, stored), False
    return plain == stored, True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any], expires_minutes: int) -> str:
    now = _now()
    payload = dict(payload)
    payload["iat"] = now
    payload["exp"] = now + timedelta(minutes=expires_minutes)
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    subject: str,
    *,
    branch_id: int,
    roles: list[str],
    permission_level: int,
) -> str:
    return _encode(
        {
            "sub": subject,
            "branch_id": branch_id,
            "roles": roles,
            "permission_level": permission_level,
        },
        settings.access_token_expire_minutes,
    )


def create_refresh_token(subject: str, *, branch_id: int) -> str:
    return _encode(
        {"sub": subject, "branch_id": branch_id, "kind": "refresh"},
        settings.refresh_token_expire_days * 24 * 60,
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return pyjwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except pyjwt.PyJWTError as exc:
        raise InvalidTokenError from exc