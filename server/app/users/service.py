"""Users management service (ticket #7 / plan/00 G08, plan/02 §3).

Legacy `permission_level` 1-9 is a coarse power floor; granular permissions
flow through user_roles -> role_permissions. Creation rules (all enforced here,
so the HTTP seam stays thin):

* new users always get a bcrypt initial password behind the force-reset marker
  (P07) — never plaintext, never reusable after first login;
* username uniqueness (409 on dup);
* a user can only be created/raised up to the caller's own permission level
  (so granting >= 7 proves the plan/02 §3 balance-edit floor: level-6 is
  denied, level-7 is allowed);
* the `admin` role (which owns every permission) may only be granted by a
  >= 7 caller;
* users are branch-scoped; cross-branch creation needs permission_level 9.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import security
from app.models import Role, User


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "namee": user.namee,
        "mobile": user.mobile or "",
        "permission_level": user.permission_level,
        "branch_id": user.branch_id,
        "active": user.active,
        "roles": sorted(r.name for r in user.roles),
        "must_reset_password": security.is_force_reset(user.pass_hash),
    }


async def _resolve_roles(session: AsyncSession, names: list[str]) -> list[Role]:
    if not names:
        return []
    result = await session.execute(select(Role).where(Role.name.in_(names)))
    rows = result.scalars().all()
    by_name = {r.name: r for r in rows}
    missing = set(names) - set(by_name)
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown role(s): {sorted(missing)}",
        )
    return [by_name[n] for n in names]


def _check_admin_role_grant(caller: User, role_names: list[str]) -> None:
    if "admin" in role_names and caller.permission_level < 7:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "granting the admin role requires permission_level 7",
        )


async def create_user(
    session: AsyncSession,
    *,
    caller: User,
    username: str,
    namee: str,
    mobile: Optional[str],
    permission_level: int,
    branch_id: Optional[int],
    initial_password: str,
    roles: list[str],
) -> User:
    username = username.strip()
    if not username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "username is required")
    if permission_level < 1 or permission_level > 9:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "permission_level must be between 1 and 9"
        )
    if permission_level > caller.permission_level:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "cannot create a user with a higher permission level than your own",
        )
    if not initial_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "initial_password is required"
        )
    if initial_password == security.WEAK_DEFAULT_PASSWORD:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "initial password must differ from the weak default",
        )
    if branch_id is None:
        branch_id = caller.branch_id
    if branch_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "user has no branch assigned"
        )
    if branch_id != caller.branch_id and caller.permission_level < 9:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "cross-branch user creation requires permission_level 9",
        )
    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "username already exists"
        )
    role_rows = await _resolve_roles(session, roles)
    _check_admin_role_grant(caller, roles)
    user = User(
        username=username,
        namee=namee,
        mobile=mobile,
        pass_hash=security.hash_password_force_reset(initial_password),
        permission_level=permission_level,
        branch_id=branch_id,
        active=True,
        roles=role_rows,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "username already exists"
        ) from exc
    return user


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).options(selectinload(User.roles)).order_by(User.username)
    )
    return list(result.scalars().all())


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()


async def update_user(
    session: AsyncSession,
    *,
    caller: User,
    user: User,
    namee: Optional[str],
    mobile: Optional[str],
    active: Optional[bool],
    permission_level: Optional[int],
) -> User:
    if user.permission_level > caller.permission_level:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "cannot manage a user with a higher permission level than your own",
        )
    if permission_level is not None:
        if permission_level < 1 or permission_level > 9:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "permission_level must be between 1 and 9"
            )
        if permission_level > caller.permission_level:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "cannot raise a user above your own permission level",
            )
    if namee is not None:
        user.namee = namee
    if mobile is not None:
        user.mobile = mobile
    if active is not None:
        user.active = active
    if permission_level is not None:
        user.permission_level = permission_level
    session.add(user)
    await session.commit()
    return user


async def set_user_roles(
    session: AsyncSession,
    *,
    caller: User,
    user: User,
    roles: list[str],
) -> User:
    role_rows = await _resolve_roles(session, roles)
    _check_admin_role_grant(caller, roles)
    user.roles = role_rows
    session.add(user)
    await session.commit()
    return user


async def manager_reset_password(
    session: AsyncSession,
    *,
    user: User,
    new_password: str,
) -> User:
    if not new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "new_password is required")
    if new_password == security.WEAK_DEFAULT_PASSWORD:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "new password must differ from the weak default",
        )
    user.pass_hash = security.hash_password_force_reset(new_password)
    session.add(user)
    await session.commit()
    return user