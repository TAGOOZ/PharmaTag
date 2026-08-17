"""Forced password reset on first login (ticket #7 / plan/00 P07).

P07: legacy plaintext hashes (the seeded admin) AND freshly-created users'
initial passwords are force-reset on first login. The login response carries
`must_reset_password`; the authenticated user sets a new password via
POST /api/v1/auth/reset-password and the flag clears, so the next login is a
normal one. A stored hash that is plain bcrypt (no marker) is never flagged.

Tests create their own throwaway users and NEVER touch the seeded admin's
password (test_auth.py still depends on admin/changeme).
"""
from sqlalchemy import delete, select

from app.auth import security
from app.auth.security import create_access_token
from app.core.db import SessionLocal
from app.models import User, user_roles_table

NEW_PASS = "NewPass123!"
WEAK = security.WEAK_DEFAULT_PASSWORD


async def _make_user(username: str, *, pass_hash: str) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            namee="Reset Tester",
            pass_hash=pass_hash,
            permission_level=1,
            branch_id=1,
            active=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _cleanup(username: str) -> None:
    async with SessionLocal() as session:
        user_id = (
            await session.execute(select(User.id).where(User.username == username))
        ).scalar_one_or_none()
        if user_id is not None:
            await session.execute(
                delete(user_roles_table).where(user_roles_table.c.user_id == user_id)
            )
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


def test_hash_password_force_reset_marks_and_verifies():
    stored = security.hash_password_force_reset("TempPass123")
    assert stored.startswith(security.MUST_RESET_PREFIX)
    assert security.verify_password("TempPass123", stored) == (True, True)
    assert security.verify_password("wrong", stored) == (False, True)
    assert security.is_force_reset(stored) is True


async def test_first_login_flags_reset_then_clears_after_change(client):
    await _make_user(
        "__t7_reset_flow__", pass_hash=security.hash_password_force_reset("TempPass123")
    )
    try:
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t7_reset_flow__", "password": "TempPass123"},
        )
        assert r.status_code == 200
        assert r.json()["must_reset_password"] is True

        token = r.json()["access_token"]
        reset = await client.post(
            "/api/v1/auth/reset-password",
            json={"old_password": "TempPass123", "new_password": NEW_PASS},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reset.status_code == 200

        after = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t7_reset_flow__", "password": NEW_PASS},
        )
        assert after.status_code == 200
        assert after.json()["must_reset_password"] is False

        old = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t7_reset_flow__", "password": "TempPass123"},
        )
        assert old.status_code == 401

        # stored hash is now plain bcrypt, no reset marker, old password gone
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(User).where(User.username == "__t7_reset_flow__")
                )
            ).scalar_one()
            assert row.pass_hash.startswith("$2")
            assert not row.pass_hash.startswith(security.MUST_RESET_PREFIX)
            assert security.is_force_reset(row.pass_hash) is False
            assert security.verify_password(NEW_PASS, row.pass_hash) == (True, False)
            assert security.verify_password("TempPass123", row.pass_hash) == (False, False)
    finally:
        await _cleanup("__t7_reset_flow__")


async def test_legacy_plaintext_user_must_reset_like_marked(client):
    await _make_user("__t7_legacy_flow__", pass_hash=WEAK)
    try:
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t7_legacy_flow__", "password": WEAK},
        )
        assert r.status_code == 200
        assert r.json()["must_reset_password"] is True

        token = r.json()["access_token"]
        reset = await client.post(
            "/api/v1/auth/reset-password",
            json={"old_password": WEAK, "new_password": NEW_PASS},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reset.status_code == 200

        after = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t7_legacy_flow__", "password": NEW_PASS},
        )
        assert after.status_code == 200
        assert after.json()["must_reset_password"] is False
    finally:
        await _cleanup("__t7_legacy_flow__")


async def test_reset_rejects_wrong_old_password(client):
    user_id = await _make_user(
        "__t7_wrong_old__", pass_hash=security.hash_password_force_reset("TempPass123")
    )
    try:
        token = create_access_token(
            str(user_id), branch_id=1, roles=[], permission_level=1
        )
        r = await client.post(
            "/api/v1/auth/reset-password",
            json={"old_password": "nope", "new_password": NEW_PASS},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401
    finally:
        await _cleanup("__t7_wrong_old__")


async def test_reset_rejects_weak_default_password(client):
    user_id = await _make_user(
        "__t7_weak__", pass_hash=security.hash_password_force_reset("TempPass123")
    )
    try:
        token = create_access_token(
            str(user_id), branch_id=1, roles=[], permission_level=1
        )
        r = await client.post(
            "/api/v1/auth/reset-password",
            json={"old_password": "TempPass123", "new_password": WEAK},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        # nothing changed: the flagged hash is still flagged
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(User).where(User.username == "__t7_weak__")
                )
            ).scalar_one()
            assert security.is_force_reset(row.pass_hash) is True
    finally:
        await _cleanup("__t7_weak__")


async def test_reset_requires_authentication(client):
    r = await client.post(
        "/api/v1/auth/reset-password",
        json={"old_password": "x", "new_password": NEW_PASS},
    )
    assert r.status_code == 401