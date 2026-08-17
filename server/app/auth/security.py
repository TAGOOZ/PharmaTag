"""Password hashing + JWT issuance/verification (plan/02 §3).

The `must_reset_password` signal (P07) covers two shapes of stored hash:
  * legacy plaintext (pre-hash, e.g. the seeded admin `changeme`), and
  * a freshly-created user's initial password, stored as bcrypt behind the
    `MUST_RESET_PREFIX` marker so the login flow can flag a forced reset.
New/changed passwords are always plain bcrypt via passlib (no marker).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Seeded admin default (rev 002_seeds) — refused as a new password.
WEAK_DEFAULT_PASSWORD = "changeme"

# Marker prefix for a freshly-created user's initial password (must reset).
MUST_RESET_PREFIX = "mustreset:"


class InvalidTokenError(Exception):
    pass


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def hash_password_force_reset(plain: str) -> str:
    """Initial password for a freshly-created user: bcrypt + reset marker."""
    return MUST_RESET_PREFIX + pwd_context.hash(plain)


def is_force_reset(stored: str) -> bool:
    """True when the stored hash forces a password reset on next login
    (legacy plaintext, a marked initial password, or an empty hash)."""
    return not stored.startswith("$2")


def verify_password(plain: str, stored: str) -> tuple[bool, bool]:
    """Return (ok, must_reset). `must_reset`=True when the stored value is
    legacy plaintext or a force-reset-marked initial password (P07)."""
    if stored.startswith(MUST_RESET_PREFIX):
        return pwd_context.verify(plain, stored[len(MUST_RESET_PREFIX):]), True
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