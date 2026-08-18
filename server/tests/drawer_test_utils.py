"""Shared helpers for the S1.8 drawer + day-close test themes (ticket #14).

Drawer tests drive the same branch-1 admin/sales fixtures as the money slices
and additionally clean up the drawer_movements / daily_close rows a close
writes. `_CLOSED_DATES` accumulates every datee a test closes so cleanup stays
in lockstep even when a mid-suite failure skips an explicit delete.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import AuditLog, DailyClose, DrawerMovement, User

BRANCH_ID = 1

_CLOSED_DATES: list[date] = []


def _closed_dates() -> list[date]:
    return list(_CLOSED_DATES)


def _mark_closed(datee: str) -> date:
    d = date.fromisoformat(datee)
    _CLOSED_DATES.append(d)
    return d


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _close_day(client, token: str, *, datee: str, counted_cash: str):
    r = await client.post(
        "/api/v1/drawer/day-close",
        headers={"Authorization": f"Bearer {token}"},
        json={"datee": datee, "counted_cash": counted_cash},
    )
    return r


async def _movements(client, token: str, *, datee: str) -> list[dict]:
    r = await client.get(
        "/api/v1/drawer/movements",
        params={"datee": datee},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["movements"]


async def _day_rows(datee: str) -> list[DailyClose]:
    d = date.fromisoformat(datee)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(DailyClose)
                .where(DailyClose.branch_id == BRANCH_ID, DailyClose.datee == d)
                .order_by(DailyClose.id)
            )
        ).scalars().all()
        return list(rows)


async def _movement_rows(datee: str) -> list[DrawerMovement]:
    d = date.fromisoformat(datee)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(DrawerMovement)
                .where(DrawerMovement.branch_id == BRANCH_ID, DrawerMovement.datee == d)
                .order_by(DrawerMovement.id)
            )
        ).scalars().all()
        return list(rows)


async def _cleanup_drawer() -> None:
    async with SessionLocal() as session:
        for d in _CLOSED_DATES:
            await session.execute(
                delete(DrawerMovement).where(
                    DrawerMovement.branch_id == BRANCH_ID, DrawerMovement.datee == d
                )
            )
            await session.execute(
                delete(DailyClose).where(
                    DailyClose.branch_id == BRANCH_ID, DailyClose.datee == d
                )
            )
        await session.commit()
    _CLOSED_DATES.clear()


async def _delete_users(usernames: list[str]) -> None:
    """Remove throwaway users + every row that references them."""
    async with SessionLocal() as session:
        user_ids = list(
            (
                await session.execute(
                    select(User.id).where(User.username.in_(usernames))
                )
            ).scalars().all()
        )
        if user_ids:
            await session.execute(
                delete(AuditLog).where(AuditLog.user_id.in_(user_ids))
            )
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.user_id.in_(user_ids))
            )
            await session.execute(
                delete(DailyClose).where(DailyClose.closed_by.in_(user_ids))
            )
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


async def _make_user(client, username: str, permission_level: int, branch_id=None) -> str:
    """Create a user via the API (branch defaults to the admin's branch);
    returns the user's login token."""
    body = {
        "username": username,
        "permission_level": permission_level,
        "initial_password": "Drw#Str0ng#2026",
    }
    if branch_id is not None:
        body["branch_id"] = branch_id
    r = await client.post(
        "/api/v1/users",
        headers={
            "Authorization": f"Bearer {await _login_token(client)}",
        },
        json=body,
    )
    assert r.status_code == 201, r.text
    login = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Drw#Str0ng#2026"}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]
