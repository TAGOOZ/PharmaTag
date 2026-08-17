"""S0.3 drug-master read slice (ticket #6): login → GET branch drug list.

The branch drug master is a read: no money/stock mutation, so no audit/outbox
rows are involved (AGENTS.md — reads follow plain read conventions). Branch
scope comes from the authenticated user's `branch_id` (seed admin → branch 1
MAIN); drugs are global (wzdrugs) so the read returns the active catalog for
that branch.
"""
async def test_login_then_get_drug_list_returns_seeded_drugs_for_branch(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    r = await client.get(
        "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()

    # branch scope resolves from the authenticated user (admin → MAIN, branch 1)
    assert body["branch"]["id"] == 1
    assert body["branch"]["pharname"] == "Main Pharmacy"

    # the seeded drug master for that branch (rev 003_drug_seeds)
    names = [d["drugname"] for d in body["drugs"]]
    assert "Panadol Extra" in names
    panadol = next(d for d in body["drugs"] if d["drugname"] == "Panadol Extra")
    assert panadol["drugnamear"] == "بانادول إكسترا"
    assert panadol["price"] == "12.50"
    assert panadol["tax_type"] == "exempt"


async def test_drug_list_requires_authentication(client):
    r = await client.get("/api/v1/drugs")
    assert r.status_code == 401


async def test_drugs_endpoint_allows_web_preflight(client):
    """The web app (localhost:300x) must be able to call the API cross-origin."""
    r = await client.options(
        "/api/v1/drugs",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3001"


# ---------------------------------------------------------------------------
# Edge-case pass (AGENTS.md — required before close): auth/scope failures,
# inactive rows, null optional fields. Tests create + clean up their own rows.
# ---------------------------------------------------------------------------
import secrets
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, text

from app.auth.security import create_access_token
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Branch, Drug, User


def _token_for(user_id: int, branch_id: int | None) -> str:
    return create_access_token(
        str(user_id), branch_id=branch_id or 0, roles=["admin"], permission_level=9
    )


async def _make_user(*, username: str, branch_id: int | None, active: bool = True) -> int:
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.username == username))
        user = User(
            username=username,
            pass_hash="x",
            permission_level=9,
            branch_id=branch_id,
            active=active,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _make_branch() -> int:
    """Create a branch with unique pharmacyid/mobile so leftover rows never collide."""
    async with SessionLocal() as session:
        branch = Branch(
            pharmacyid=f"__t2_{secrets.token_hex(4)}__",
            mobile=f"0{secrets.token_hex(4)}",
            pharname="Edge Branch",
        )
        session.add(branch)
        await session.flush()
        branch_id = branch.id
        await session.commit()
        return branch_id


async def _cleanup_users(*usernames: str) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.username.in_(usernames)))
        await session.commit()


async def test_drugs_reject_garbage_bearer(client):
    r = await client.get(
        "/api/v1/drugs", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert r.status_code == 401


async def test_drugs_reject_expired_token(client):
    expired = pyjwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = await client.get(
        "/api/v1/drugs", headers={"Authorization": f"Bearer {expired}"}
    )
    assert r.status_code == 401


async def test_drugs_reject_inactive_user(client):
    user_id = await _make_user(
        username="__t2_edge_inactive__", branch_id=1, active=False
    )
    try:
        r = await client.get(
            "/api/v1/drugs",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
        )
        assert r.status_code == 401
    finally:
        await _cleanup_users("__t2_edge_inactive__")


async def test_drugs_user_without_branch_is_rejected(client):
    user_id = await _make_user(username="__t2_edge_nobranch__", branch_id=None)
    try:
        r = await client.get(
            "/api/v1/drugs",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
        )
        assert r.status_code == 400
    finally:
        await _cleanup_users("__t2_edge_nobranch__")


async def test_drugs_second_branch_user_sees_own_branch_and_global_catalog(client):
    """Branch scope resolves from the token's user; drugs are global (wzdrugs),
    so branch 2 sees the same active catalog but its own branch metadata."""
    branch_id = await _make_branch()
    user_id = await _make_user(
        username="__t2_edge_branch2__", branch_id=branch_id
    )
    try:
        r = await client.get(
            "/api/v1/drugs",
            headers={"Authorization": f"Bearer {_token_for(user_id, branch_id)}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["branch"]["id"] == branch_id
        assert body["branch"]["pharname"] == "Edge Branch"
        names = [d["drugname"] for d in body["drugs"]]
        assert "Panadol Extra" in names, "global drug catalog visible to branch 2"
    finally:
        await _cleanup_users("__t2_edge_branch2__")
        async with SessionLocal() as session:
            await session.execute(delete(Branch).where(Branch.id == branch_id))
            await session.commit()


async def test_drugs_excludes_inactive_drugs(client):
    async with SessionLocal() as session:
        drug = Drug(
            drugname="__t2_edge_inactive_drug__",
            active=False,
        )
        session.add(drug)
        await session.commit()
        drug_id = drug.id
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
        )
        token = login.json()["access_token"]
        r = await client.get(
            "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        names = [d["drugname"] for d in r.json()["drugs"]]
        assert "__t2_edge_inactive_drug__" not in names
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Drug).where(Drug.id == drug_id))
            await session.commit()


async def test_drugs_null_optional_fields_normalized(client):
    """generic/classy/co None → '' ; null price/price_now → '0.00' (exact 2dp)."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname="__t2_edge_null_fields__",
            drugnamear="",
            generic=None,
            classy=None,
            co=None,
            price=None,
            price_now=None,
        )
        session.add(drug)
        await session.commit()
        drug_id = drug.id
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
        )
        token = login.json()["access_token"]
        r = await client.get(
            "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
        )
        body = r.json()
        row = next(d for d in body["drugs"] if d["id"] == drug_id)
        assert row["generic"] == ""
        assert row["classy"] == ""
        assert row["co"] == ""
        assert row["price"] == "0.00"
        assert row["price_now"] == "0.00"
        assert row["vat"] == "0.00"
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(Drug).where(Drug.id == drug_id))
            await session.commit()


# ---------------------------------------------------------------------------
# #6 edge-case pass — token subject integrity, branch lifecycle, pagination.
# ---------------------------------------------------------------------------
def _raw_token(payload: dict) -> str:
    return pyjwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


async def test_drugs_token_with_non_numeric_sub_is_401_not_500(client):
    """A tampered/foreign token whose sub is not a user id must 401, never 500."""
    token = _raw_token(
        {"sub": "not-a-number", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    )
    r = await client.get(
        "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_drugs_token_with_missing_sub_is_401_not_500(client):
    token = _raw_token(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    )
    r = await client.get(
        "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_drugs_branch_deleted_404(client):
    """User whose branch was deleted sees 404 (never a stray empty catalog).

    The schema's FK normally prevents deleting a referenced branch; the router
    still defends against the dangling-branch state, so we simulate it by
    dropping the constraint for this transaction only (restored in finally).
    """
    branch_id = await _make_branch()
    user_id = await _make_user(
        username="__t2_edge_deleted_branch__", branch_id=branch_id
    )
    try:
        async with SessionLocal() as session:
            await session.execute(
                text("ALTER TABLE users DROP CONSTRAINT users_branch_id_fkey")
            )
            await session.execute(delete(Branch).where(Branch.id == branch_id))
            await session.commit()
        r = await client.get(
            "/api/v1/drugs",
            headers={"Authorization": f"Bearer {_token_for(user_id, branch_id)}"},
        )
        assert r.status_code == 404
    finally:
        await _cleanup_users("__t2_edge_deleted_branch__")
        async with SessionLocal() as session:
            await session.execute(
                text(
                    "ALTER TABLE users ADD CONSTRAINT users_branch_id_fkey "
                    "FOREIGN KEY (branch_id) REFERENCES branches(id)"
                )
            )
            await session.commit()


async def test_drugs_branch_inactive_403(client):
    """An existing but deactivated branch denies reads (403), not 200."""
    branch_id = await _make_branch()
    user_id = await _make_user(
        username="__t2_edge_inactive_branch__", branch_id=branch_id
    )
    async with SessionLocal() as session:
        branch = await session.get(Branch, branch_id)
        branch.is_active = False
        await session.commit()
    try:
        r = await client.get(
            "/api/v1/drugs",
            headers={"Authorization": f"Bearer {_token_for(user_id, branch_id)}"},
        )
        assert r.status_code == 403
    finally:
        await _cleanup_users("__t2_edge_inactive_branch__")
        async with SessionLocal() as session:
            await session.execute(delete(Branch).where(Branch.id == branch_id))
            await session.commit()


async def test_drugs_pagination_applies_limit_and_offset(client):
    async with SessionLocal() as session:
        for i in range(3):
            session.add(
                Drug(drugname=f"__t2_pg_{i}__", active=True)
            )
        await session.commit()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
        )
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        page1 = (
            await client.get("/api/v1/drugs", params={"limit": 2, "offset": 0}, headers=auth)
        ).json()["drugs"]
        page2 = (
            await client.get("/api/v1/drugs", params={"limit": 2, "offset": 2}, headers=auth)
        ).json()["drugs"]
        assert len(page1) == 2
        assert len(page2) == 2
        assert not any(d["id"] in {p["id"] for p in page1} for d in page2)

        # offset past the catalog end → empty page
        past_end = (
            await client.get("/api/v1/drugs", params={"limit": 2, "offset": 10000}, headers=auth)
        ).json()["drugs"]
        assert past_end == []

        # the full window still returns everything (limit capped at 500)
        full = (
            await client.get("/api/v1/drugs", params={"limit": 500}, headers=auth)
        ).json()["drugs"]
        names = {d["drugname"] for d in full}
        assert {"__t2_pg_0__", "__t2_pg_1__", "__t2_pg_2__"} <= names
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(Drug).where(Drug.drugname.like("__t2_pg_%"))
            )
            await session.commit()


async def test_drugs_pagination_rejects_negative_params(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    token = login.json()["access_token"]
    for params in ({"limit": -1}, {"offset": -5}):
        r = await client.get(
            "/api/v1/drugs",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400, params


async def test_drugs_pagination_caps_limit_at_500(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    token = login.json()["access_token"]
    r = await client.get(
        "/api/v1/drugs",
        params={"limit": 10_000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["drugs"]) <= 500


async def test_drugs_ignores_branch_id_claim_tampering(client):
    """Branch scope resolves from the DB user row, not the token's branch_id claim."""
    user_id = await _make_user(username="__t2_edge_tamper__", branch_id=1)
    try:
        token = _token_for(user_id, branch_id=2)
        r = await client.get(
            "/api/v1/drugs", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        assert r.json()["branch"]["id"] == 1
    finally:
        await _cleanup_users("__t2_edge_tamper__")


async def test_login_preflight_allows_web_origin(client):
    r = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3001"