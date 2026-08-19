"""Permission gate dependencies (plan/00 G08, plan/02 §3).

Two reusable gates, usable on any protected endpoint:

* `require_permission(code)` — grants a granular permission either through the
  user's roles (role_permissions rows) or through the legacy 1-9 power floor:
  a user with `permission_level >= N` counts as having the seeded legacy
  permission code `'N'` (G08, plan/02 §3 "coarse power floor"). The
  `LEGACY_LEVEL_FLOOR` table maps each granular code to the legacy level that
  covers its area (users.manage -> 6, day.close -> 7, sale.edit_invoice -> 8,
  reports -> 9, ...).
* `require_level(min)` — the coarse numeric floor. plan/02 §3 pins balance
  edits / stock-correction approval / day-close reopen at >= 7; the #14
  day-close slice reuses this exact gate (A07).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_session
from app.models import Permission, User, role_permissions_table, user_roles_table

FORBIDDEN = HTTPException(status.HTTP_403_FORBIDDEN, "insufficient permission")

# granular permission code -> minimum legacy permission_level that covers its area
LEGACY_LEVEL_FLOOR = {
    "sale.create": 1,
    "sale.edit_invoice": 8,
    "day.close": 7,
    "stock.adjust": 3,
    "drugs.manage": 3,  # الأصناف والمخزون (drug master + stock module, plan/02 §3)
    "drawer.manage": 3,  # manual cash-drawer movements (S1.8, ticket #14)
    "accounts.manage": 7,  # chart-of-accounts edits (S2.1, ticket #16 — ledger area, plan/02 §3 ≥7)
    "approvals": 5,
    "reports": 9,
    "users.manage": 6,
}


async def _role_permission_codes(user: User, session: AsyncSession) -> set[str]:
    """Granular permission codes the user holds via user_roles -> role_permissions.

    Queries the join tables directly (not the ORM relationship) so the gate
    never triggers an async lazy-load of `user.roles`.
    """
    result = await session.execute(
        select(Permission.code)
        .join(
            role_permissions_table,
            role_permissions_table.c.permission_id == Permission.id,
        )
        .join(
            user_roles_table,
            user_roles_table.c.role_id == role_permissions_table.c.role_id,
        )
        .where(user_roles_table.c.user_id == user.id)
    )
    return set(result.scalars().all())


def require_permission(code: str):
    """Dependency: the caller must hold `code` (via role OR legacy floor)."""

    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        codes = await _role_permission_codes(user, session)
        if code in codes:
            return user
        floor = LEGACY_LEVEL_FLOOR.get(code)
        if floor is not None and user.permission_level >= floor:
            return user
        raise FORBIDDEN

    return dependency


def require_level(min_level: int):
    """Dependency: the caller's legacy permission_level must be >= `min_level`."""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.permission_level < min_level:
            raise FORBIDDEN
        return user

    return dependency