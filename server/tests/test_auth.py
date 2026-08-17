"""JWT auth scaffold (ticket #2 AC1): login, token verification, protected route."""
import pytest
from sqlalchemy import delete, select

from app.auth import security
from app.core.db import SessionLocal
from app.models import User


async def test_login_seeded_admin_legacy_password_returns_tokens(client):
    r = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["must_reset_password"] is True
    assert body["user"]["username"] == "admin"


async def test_login_wrong_password_rejected(client):
    r = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert r.status_code == 401


async def test_login_unknown_user_rejected(client):
    r = await client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "x"}
    )
    assert r.status_code == 401


async def test_me_requires_bearer_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_rejects_garbage_token(client):
    r = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert r.status_code == 401


async def test_me_with_valid_token(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    token = login.json()["access_token"]
    r = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["permission_level"] == 9


def test_hash_password_is_bcrypt_and_verifies():
    hashed = security.hash_password("s3cret")
    assert hashed.startswith("$2")
    assert security.verify_password("s3cret", hashed) == (True, False)
    assert security.verify_password("wrong", hashed) == (False, False)


def test_verify_password_detects_legacy_plaintext():
    assert security.verify_password("changeme", "changeme") == (True, True)
    assert security.verify_password("nope", "changeme") == (False, True)


def test_access_token_roundtrip():
    token = security.create_access_token(
        "1", branch_id=1, roles=["admin"], permission_level=9
    )
    payload = security.decode_token(token)
    assert payload["sub"] == "1"
    assert payload["branch_id"] == 1
    assert payload["roles"] == ["admin"]
    assert payload["permission_level"] == 9


# --- edge cases (ticket #1/#2 edge pass) ---


async def _make_user(username: str, *, active: bool, branch_id) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            namee="Edge Tester",
            pass_hash=security.hash_password("EdgePass123"),
            permission_level=1,
            branch_id=branch_id,
            active=active,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _drop_user(username: str) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.username == username))
        await session.commit()


def test_refresh_token_carries_kind_and_roundtrips():
    token = security.create_refresh_token("1", branch_id=1)
    payload = security.decode_token(token)
    assert payload["sub"] == "1"
    assert payload["branch_id"] == 1
    assert payload["kind"] == "refresh"


def test_access_token_is_marked_access_not_refresh():
    token = security.create_access_token(
        "1", branch_id=1, roles=["admin"], permission_level=9
    )
    assert security.decode_token(token)["kind"] == "access"


async def test_me_rejects_refresh_token(client):
    """A refresh token (30-day lifetime) must never work as a bearer credential."""
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    refresh = login.json()["refresh_token"]
    r = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert r.status_code == 401


async def test_me_rejects_expired_token(client, monkeypatch):
    monkeypatch.setattr(security.settings, "access_token_expire_minutes", -1)
    token = security.create_access_token(
        "1", branch_id=1, roles=["admin"], permission_level=9
    )
    r = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_me_rejects_token_for_deleted_user(client):
    token = security.create_access_token(
        "999999", branch_id=1, roles=[], permission_level=1
    )
    r = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_me_rejects_inactive_user_token(client):
    user_id = await _make_user("__t2_inactive_me__", active=False, branch_id=1)
    try:
        token = security.create_access_token(
            str(user_id), branch_id=1, roles=[], permission_level=1
        )
        r = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401
    finally:
        await _drop_user("__t2_inactive_me__")


async def test_login_inactive_user_rejected(client):
    await _make_user("__t2_inactive_login__", active=False, branch_id=1)
    try:
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t2_inactive_login__", "password": "EdgePass123"},
        )
        assert r.status_code == 401
    finally:
        await _drop_user("__t2_inactive_login__")


async def test_login_branchless_user_ok(client):
    """A user with no branch still logs in; branch_id is simply null in the payload."""
    user_id = await _make_user("__t2_branchless__", active=True, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "__t2_branchless__", "password": "EdgePass123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["branch_id"] is None
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["branch_id"] is None
    finally:
        await _drop_user("__t2_branchless__")


async def test_login_empty_and_whitespace_password_rejected(client):
    for bad in ("", "   "):
        r = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": bad}
        )
        assert r.status_code == 401, bad


async def test_login_very_long_password_rejected_without_error(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "x" * 200},
    )
    assert r.status_code == 401