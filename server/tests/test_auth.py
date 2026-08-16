"""JWT auth scaffold (ticket #2 AC1): login, token verification, protected route."""
from app.auth import security


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