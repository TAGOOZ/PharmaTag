"""Users CRUD + permission gates (ticket #7 / plan/00 G08, plan/02 §3).

Managers (legacy level >= 6 = the users/permissions area, or the granular
`users.manage` permission) create/list/update users and assign roles. New users
get a bcrypt-hashed initial password behind the force-reset marker (P07); the
high-privilege rule — you cannot create/raise a user above your own legacy
level, so a >=7 target proves the balance-edit gate — and cross-branch
creation are both exercised here. All tests create + clean up their own rows;
the seeded admin (user 1) password is never changed.
"""
from sqlalchemy import delete, select

from app.auth import security
from app.core.db import SessionLocal
from app.models import Branch, User, user_roles_table


async def _admin_login(client):
    r = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert r.status_code == 200
    return r.json()["access_token"]


async def _create_via_admin(client, *, username: str, **overrides):
    body = {
        "username": username,
        "namee": "Test User",
        "permission_level": 1,
        "initial_password": "TempPass123",
        "roles": [],
        **overrides,
    }
    r = await client.post(
        "/api/v1/users",
        json=body,
        headers={"Authorization": f"Bearer {await _admin_login(client)}"},
    )
    return r


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


async def _cleanup(*usernames: str) -> None:
    async with SessionLocal() as session:
        ids = (
            await session.execute(select(User.id).where(User.username.in_(usernames)))
        ).scalars().all()
        if ids:
            await session.execute(
                delete(user_roles_table).where(user_roles_table.c.user_id.in_(ids))
            )
            await session.execute(delete(User).where(User.id.in_(ids)))
            await session.commit()


# ---------------------------------------------------------------------------
# access control: who may manage users at all
# ---------------------------------------------------------------------------
async def test_create_user_requires_authentication(client):
    r = await client.post(
        "/api/v1/users",
        json={
            "username": "__t7_noauth__",
            "permission_level": 1,
            "initial_password": "TempPass123",
        },
    )
    assert r.status_code == 401


async def test_level1_pharmacist_cannot_manage_users(client):
    r = await _create_via_admin(client, username="__t7_pharmacist__", permission_level=1, roles=["pharmacist"])
    assert r.status_code == 201
    created = r.json()
    try:
        login = await _login(client, "__t7_pharmacist__", "TempPass123")
        assert login.status_code == 200
        token = login.json()["access_token"]
        denied = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert denied.status_code == 403
    finally:
        await _cleanup("__t7_pharmacist__")


async def test_level6_manager_manages_users_via_legacy_floor(client):
    r = await _create_via_admin(client, username="__t7_mgr6__", permission_level=6)
    assert r.status_code == 201
    try:
        login = await _login(client, "__t7_mgr6__", "TempPass123")
        assert login.status_code == 200
        token = login.json()["access_token"]
        ok = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert ok.status_code == 200
    finally:
        await _cleanup("__t7_mgr6__")


# ---------------------------------------------------------------------------
# create: hashing, uniqueness, boundaries, roles, branch scope
# ---------------------------------------------------------------------------
async def test_admin_creates_user_with_hashed_force_reset_password(client):
    r = await _create_via_admin(client, username="__t7_cashier__", permission_level=1, roles=["cashier"], namee="Cashier One")
    assert r.status_code == 201
    body = r.json()
    try:
        assert body["username"] == "__t7_cashier__"
        assert body["permission_level"] == 1
        assert body["roles"] == ["cashier"]
        assert body["must_reset_password"] is True
        assert "pass_hash" not in body
        assert "initial_password" not in body

        # stored hash is bcrypt behind the force-reset marker (never plaintext)
        async with SessionLocal() as session:
            row = (
                await session.execute(select(User).where(User.username == "__t7_cashier__"))
            ).scalar_one()
            assert row.pass_hash.startswith(security.MUST_RESET_PREFIX)
            assert security.verify_password("TempPass123", row.pass_hash) == (True, True)

        # first login is flagged for forced reset
        login = await _login(client, "__t7_cashier__", "TempPass123")
        assert login.status_code == 200
        assert login.json()["must_reset_password"] is True
        assert login.json()["user"]["permission_level"] == 1
    finally:
        await _cleanup("__t7_cashier__")


async def test_duplicate_username_conflict(client):
    await _create_via_admin(client, username="__t7_dup__", permission_level=1)
    try:
        dup = await _create_via_admin(client, username="__t7_dup__", permission_level=2)
        assert dup.status_code == 409
    finally:
        await _cleanup("__t7_dup__")


async def test_permission_level_boundaries_rejected(client):
    for bad in (0, 10, "abc"):
        r = await client.post(
            "/api/v1/users",
            json={
                "username": f"__t7_bad_{bad}__",
                "permission_level": bad,
                "initial_password": "TempPass123",
            },
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert r.status_code == 400, f"permission_level={bad!r} must be rejected"
        await _cleanup(f"__t7_bad_{bad}__")


async def test_create_user_defaults_to_callers_branch(client):
    r = await _create_via_admin(client, username="__t7_defaultbranch__")
    assert r.status_code == 201
    try:
        assert r.json()["branch_id"] == 1
    finally:
        await _cleanup("__t7_defaultbranch__")


async def test_cross_branch_creation_requires_level9(client):
    async with SessionLocal() as session:
        branch = Branch(pharmacyid="__t7_users_b2__", mobile="0", pharname="Users Branch 2")
        session.add(branch)
        await session.flush()
        branch_id = branch.id
        await session.commit()
    try:
        await _create_via_admin(client, username="__t7_mgr6b__", permission_level=6)
        mgr_login = await _login(client, "__t7_mgr6b__", "TempPass123")
        mgr_token = mgr_login.json()["access_token"]

        denied = await client.post(
            "/api/v1/users",
            json={
                "username": "__t7_cross_banned__",
                "permission_level": 1,
                "branch_id": branch_id,
                "initial_password": "TempPass123",
            },
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert denied.status_code == 403

        allowed = await client.post(
            "/api/v1/users",
            json={
                "username": "__t7_cross_ok__",
                "permission_level": 1,
                "branch_id": branch_id,
                "initial_password": "TempPass123",
            },
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert allowed.status_code == 201
        assert allowed.json()["branch_id"] == branch_id
    finally:
        await _cleanup("__t7_mgr6b__", "__t7_cross_banned__", "__t7_cross_ok__")
        async with SessionLocal() as session:
            await session.execute(delete(Branch).where(Branch.id == branch_id))
            await session.commit()


async def test_create_user_unknown_role_rejected(client):
    r = await client.post(
        "/api/v1/users",
        json={
            "username": "__t7_badrole__",
            "permission_level": 1,
            "initial_password": "TempPass123",
            "roles": ["super-saiyan"],
        },
        headers={"Authorization": f"Bearer {await _admin_login(client)}"},
    )
    assert r.status_code == 400
    await _cleanup("__t7_badrole__")


async def test_create_user_rejects_weak_initial_password(client):
    r = await client.post(
        "/api/v1/users",
        json={
            "username": "__t7_weakinit__",
            "permission_level": 1,
            "initial_password": "changeme",
        },
        headers={"Authorization": f"Bearer {await _admin_login(client)}"},
    )
    assert r.status_code == 400
    await _cleanup("__t7_weakinit__")


# ---------------------------------------------------------------------------
# the high-privilege rule proves the >=7 gate (plan/02 §3: balance-edit floor)
# ---------------------------------------------------------------------------
async def test_level6_cannot_create_level7_user(client):
    await _create_via_admin(client, username="__t7_lvl6__", permission_level=6)
    try:
        token = (await _login(client, "__t7_lvl6__", "TempPass123")).json()["access_token"]
        r = await client.post(
            "/api/v1/users",
            json={
                "username": "__t7_above__",
                "permission_level": 7,
                "initial_password": "TempPass123",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
    finally:
        await _cleanup("__t7_lvl6__", "__t7_above__")


async def test_level7_can_create_level7_user(client):
    await _create_via_admin(client, username="__t7_lvl7__", permission_level=7)
    try:
        token = (await _login(client, "__t7_lvl7__", "TempPass123")).json()["access_token"]
        r = await client.post(
            "/api/v1/users",
            json={
                "username": "__t7_at7__",
                "permission_level": 7,
                "initial_password": "TempPass123",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        assert r.json()["permission_level"] == 7
    finally:
        await _cleanup("__t7_lvl7__", "__t7_at7__")


# ---------------------------------------------------------------------------
# list / get / patch
# ---------------------------------------------------------------------------
async def test_list_users_shows_created_user_and_reset_flag(client):
    await _create_via_admin(client, username="__t7_list__", permission_level=2, roles=["pharmacist"])
    try:
        r = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {await _admin_login(client)}"}
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["users"], list)
        row = next(u for u in body["users"] if u["username"] == "__t7_list__")
        assert row["permission_level"] == 2
        assert row["roles"] == ["pharmacist"]
        assert row["must_reset_password"] is True
        assert "pass_hash" not in row
    finally:
        await _cleanup("__t7_list__")


async def test_get_user_returns_roles(client):
    await _create_via_admin(client, username="__t7_get__", permission_level=1, roles=["accountant"])
    try:
        listing = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {await _admin_login(client)}"}
        )
        user_id = next(u["id"] for u in listing.json()["users"] if u["username"] == "__t7_get__")
        r = await client.get(
            f"/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert r.status_code == 200
        assert r.json()["username"] == "__t7_get__"
        assert r.json()["roles"] == ["accountant"]
    finally:
        await _cleanup("__t7_get__")


async def test_get_unknown_user_404(client):
    r = await client.get(
        "/api/v1/users/999999",
        headers={"Authorization": f"Bearer {await _admin_login(client)}"},
    )
    assert r.status_code == 404


async def test_patch_updates_profile_and_activation(client):
    r = await _create_via_admin(client, username="__t7_patch__", permission_level=1)
    user_id = r.json()["id"]
    try:
        ok = await client.patch(
            f"/api/v1/users/{user_id}",
            json={"namee": "Renamed", "mobile": "01000000002"},
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert ok.status_code == 200
        assert ok.json()["namee"] == "Renamed"
        assert ok.json()["mobile"] == "01000000002"

        deactivate = await client.patch(
            f"/api/v1/users/{user_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert deactivate.status_code == 200
        assert deactivate.json()["active"] is False

        login = await _login(client, "__t7_patch__", "TempPass123")
        assert login.status_code == 401, "inactive user must be refused at login"
    finally:
        await _cleanup("__t7_patch__")


async def test_patch_cannot_raise_user_above_callers_level(client):
    await _create_via_admin(client, username="__t7_patch6__", permission_level=6)
    await _create_via_admin(client, username="__t7_patchvictim__", permission_level=1)
    try:
        listing = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {await _admin_login(client)}"}
        )
        victim_id = next(u["id"] for u in listing.json()["users"] if u["username"] == "__t7_patchvictim__")
        token = (await _login(client, "__t7_patch6__", "TempPass123")).json()["access_token"]
        r = await client.patch(
            f"/api/v1/users/{victim_id}",
            json={"permission_level": 7},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
    finally:
        await _cleanup("__t7_patch6__", "__t7_patchvictim__")


# ---------------------------------------------------------------------------
# granular permissions via role assignment
# ---------------------------------------------------------------------------
async def test_assign_roles_via_permissions_endpoint(client):
    r = await _create_via_admin(client, username="__t7_roles__", permission_level=1)
    user_id = r.json()["id"]
    try:
        ok = await client.post(
            f"/api/v1/users/{user_id}/permissions",
            json={"roles": ["manager"]},
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert ok.status_code == 200
        assert ok.json()["roles"] == ["manager"]

        get = await client.get(
            f"/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert get.json()["roles"] == ["manager"]

        # the manager role grants day.close granularly, but at level 1 it does
        # NOT grant users.manage (that needs the level >= 6 floor or the code)
        token = (await _login(client, "__t7_roles__", "TempPass123")).json()["access_token"]
        denied = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert denied.status_code == 403
    finally:
        await _cleanup("__t7_roles__")


async def test_granting_admin_role_requires_level7(client):
    await _create_via_admin(client, username="__t7_admin6__", permission_level=6)
    r = await _create_via_admin(client, username="__t7_admingrantee__", permission_level=1)
    grantee_id = r.json()["id"]
    try:
        token6 = (await _login(client, "__t7_admin6__", "TempPass123")).json()["access_token"]
        denied = await client.post(
            f"/api/v1/users/{grantee_id}/permissions",
            json={"roles": ["admin"]},
            headers={"Authorization": f"Bearer {token6}"},
        )
        assert denied.status_code == 403

        await _create_via_admin(client, username="__t7_admin7__", permission_level=7)
        token7 = (await _login(client, "__t7_admin7__", "TempPass123")).json()["access_token"]
        allowed = await client.post(
            f"/api/v1/users/{grantee_id}/permissions",
            json={"roles": ["admin"]},
            headers={"Authorization": f"Bearer {token7}"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["roles"] == ["admin"]
    finally:
        await _cleanup("__t7_admin6__", "__t7_admingrantee__", "__t7_admin7__")


# ---------------------------------------------------------------------------
# manager-initiated password reset
# ---------------------------------------------------------------------------
async def test_manager_resets_user_password_forces_next_reset(client):
    r = await _create_via_admin(client, username="__t7_mgrreset__", permission_level=1)
    user_id = r.json()["id"]
    try:
        reset = await client.post(
            f"/api/v1/users/{user_id}/reset-password",
            json={"new_password": "ResetByMgr123"},
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert reset.status_code == 200

        old = await _login(client, "__t7_mgrreset__", "TempPass123")
        assert old.status_code == 401, "old initial password must be gone"

        first = await _login(client, "__t7_mgrreset__", "ResetByMgr123")
        assert first.status_code == 200
        assert first.json()["must_reset_password"] is True, "manager reset re-arms forced reset"
    finally:
        await _cleanup("__t7_mgrreset__")


async def test_manager_reset_rejects_weak_default(client):
    r = await _create_via_admin(client, username="__t7_mgrresetweak__", permission_level=1)
    user_id = r.json()["id"]
    try:
        reset = await client.post(
            f"/api/v1/users/{user_id}/reset-password",
            json={"new_password": "changeme"},
            headers={"Authorization": f"Bearer {await _admin_login(client)}"},
        )
        assert reset.status_code == 400
    finally:
        await _cleanup("__t7_mgrresetweak__")


async def test_manager_reset_requires_user_management_permission(client):
    await _create_via_admin(client, username="__t7_resetdeny6__", permission_level=6)
    r = await _create_via_admin(client, username="__t7_resetvictim__", permission_level=1)
    victim_id = r.json()["id"]
    try:
        token = (await _login(client, "__t7_resetdeny6__", "TempPass123")).json()["access_token"]
        r = await client.post(
            f"/api/v1/users/{victim_id}/reset-password",
            json={"new_password": "Whatever123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, "level-6 floor grants users.manage"
    finally:
        await _cleanup("__t7_resetdeny6__", "__t7_resetvictim__")


# ---------------------------------------------------------------------------
# edge-case pass (AGENTS.md — required before close)
# ---------------------------------------------------------------------------
async def test_cannot_manage_user_above_your_level(client):
    await _create_via_admin(client, username="__t7_man6__", permission_level=6)
    try:
        listing = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {await _admin_login(client)}"}
        )
        admin_id = next(u["id"] for u in listing.json()["users"] if u["username"] == "admin")
        token = (await _login(client, "__t7_man6__", "TempPass123")).json()["access_token"]
        r = await client.patch(
            f"/api/v1/users/{admin_id}",
            json={"namee": "nope"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
    finally:
        await _cleanup("__t7_man6__")


async def test_admin_can_create_level9_user_boundary(client):
    r = await _create_via_admin(client, username="__t7_lvl9__", permission_level=9)
    assert r.status_code == 201
    try:
        assert r.json()["permission_level"] == 9
    finally:
        await _cleanup("__t7_lvl9__")


async def test_whitespace_username_rejected(client):
    r = await client.post(
        "/api/v1/users",
        json={
            "username": "   ",
            "permission_level": 1,
            "initial_password": "TempPass123",
        },
        headers={"Authorization": f"Bearer {await _admin_login(client)}"},
    )
    assert r.status_code == 400
    await _cleanup("   ")


async def test_missing_required_field_rejected(client):
    r = await client.post(
        "/api/v1/users",
        json={"username": "__t7_missing__", "permission_level": 1},
        headers={"Authorization": f"Bearer {await _admin_login(client)}"},
    )
    assert r.status_code == 400
    await _cleanup("__t7_missing__")


async def test_users_endpoint_rejects_garbage_token(client):
    r = await client.get(
        "/api/v1/users", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert r.status_code == 401


async def test_must_reset_flag_clears_in_listing_after_user_resets(client):
    r = await _create_via_admin(client, username="__t7_flagcycle__", permission_level=1)
    try:
        first = await _login(client, "__t7_flagcycle__", "TempPass123")
        assert first.json()["must_reset_password"] is True
        token = first.json()["access_token"]
        await client.post(
            "/api/v1/auth/reset-password",
            json={"old_password": "TempPass123", "new_password": "NewPass123!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        listing = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {await _admin_login(client)}"}
        )
        row = next(u for u in listing.json()["users"] if u["username"] == "__t7_flagcycle__")
        assert row["must_reset_password"] is False
    finally:
        await _cleanup("__t7_flagcycle__")


async def test_expired_token_rejected_on_users_api(client):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    from app.core.config import settings

    expired = pyjwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {expired}"}
    )
    assert r.status_code == 401