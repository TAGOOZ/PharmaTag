"""Permission gate machinery (ticket #7 / plan/00 G08, plan/02 §3).

`require_permission(code)` grants a granular permission either through the
user's roles (role_permissions) or through the legacy 1-9 power floor
(LEGACY_LEVEL_FLOOR). `require_level(min)` is the coarse floor gate — plan/02 §3
pins balance edits / stock-correction approval / day-close reopen at >= 7 (the
#14 day-close slice reuses this same gate). These unit tests drive the gate
dependencies directly; the HTTP-level proof (level-6 denied / level-7 allowed)
lives in test_users.py via the user-management high-privilege rule.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.auth import rbac
from app.core.db import SessionLocal
from app.models import Role, User, user_roles_table


async def _make_user(
    username: str, *, permission_level: int, roles: list[str] | None = None
) -> int:
    async with SessionLocal() as session:
        role_rows = []
        if roles:
            result = await session.execute(select(Role).where(Role.name.in_(roles)))
            role_rows = list(result.scalars().all())
        user = User(
            username=username,
            pass_hash="x",
            permission_level=permission_level,
            branch_id=1,
            active=True,
            roles=role_rows,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


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


async def _load_user(user_id: int) -> User:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.roles))
        )
        user = result.scalar_one()
        session.expunge(user)
        return user


# ---------------------------------------------------------------------------
# require_level: the coarse >= N floor (plan/02 §3: balance-edit / day-close 7)
# ---------------------------------------------------------------------------
class _FakeUser:
    def __init__(self, level: int):
        self.permission_level = level


async def test_require_level_denies_below_floor():
    dep = rbac.require_level(7)(_FakeUser(6))
    with pytest.raises(HTTPException) as exc:
        await dep
    assert exc.value.status_code == 403


async def test_require_level_allows_at_floor():
    dep = rbac.require_level(7)(_FakeUser(7))
    user = await dep
    assert user.permission_level == 7


async def test_require_level_allows_above_floor():
    dep = rbac.require_level(7)(_FakeUser(9))
    user = await dep
    assert user.permission_level == 9


# ---------------------------------------------------------------------------
# require_permission: granular via roles OR legacy 1-9 power floor
# ---------------------------------------------------------------------------
async def test_permission_granted_via_role():
    user_id = await _make_user("__t7_gate_role__", permission_level=5, roles=["manager"])
    try:
        user = await _load_user(user_id)
        async with SessionLocal() as session:
            dep = rbac.require_permission("day.close")(user, session)
            granted = await dep
        assert granted is user
    finally:
        await _cleanup("__t7_gate_role__")


async def test_permission_granted_via_legacy_floor():
    # permission_level 6 is the legacy 'users/permissions' floor -> users.manage
    user_id = await _make_user("__t7_gate_floor__", permission_level=6)
    try:
        user = await _load_user(user_id)
        async with SessionLocal() as session:
            dep = rbac.require_permission("users.manage")(user, session)
            granted = await dep
        assert granted is user
    finally:
        await _cleanup("__t7_gate_floor__")


async def test_permission_denied_without_role_or_floor():
    user_id = await _make_user("__t7_gate_denied__", permission_level=5)
    try:
        user = await _load_user(user_id)
        async with SessionLocal() as session:
            dep = rbac.require_permission("users.manage")(user, session)
            with pytest.raises(HTTPException) as exc:
                await dep
        assert exc.value.status_code == 403
    finally:
        await _cleanup("__t7_gate_denied__")


async def test_admin_role_grants_every_permission():
    user_id = await _make_user("__t7_gate_admin__", permission_level=9, roles=["admin"])
    try:
        user = await _load_user(user_id)
        async with SessionLocal() as session:
            dep = rbac.require_permission("users.manage")(user, session)
            granted = await dep
            dep = rbac.require_permission("reports")(user, session)
            granted = await dep
        assert granted is user
    finally:
        await _cleanup("__t7_gate_admin__")