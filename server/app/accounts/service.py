"""Chart-of-accounts service (S2.1, ticket #16).

Per-branch account CRUD + the legacy tree (wzaccfreetree master/fary →
parent_id). The two safety invariants that keep the chart "usable by journal
posting":

* **Referenced accounts are immutable in shape** — an account with
  `journal_lines`/`balances` history or a party receivable/payable link cannot
  be renamed, re-typed, deactivated, or deleted (409; history stays
  addressable). Deactivation is also refused while the account still has
  active children.
* **No orphan wiring / no cycles** — a parent must live in the same branch, and
  reparenting can never make an account its own ancestor.

Every write runs under `atomic()` with its `audit_log` row (G12). No sync
outbox: the chart is branch-local configuration (same treatment as parties and
drawer movements); offline COA replication is a later-chain concern.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_DELETE, ACTION_INSERT, ACTION_UPDATE, audit
from app.core.db import atomic
from app.models import Account, Balance, JournalLine, Party

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "account not found")


async def caller_branch_id(user) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


async def get_account(session: AsyncSession, branch_id: int, account_id: int) -> Account:
    """Branch-scoped fetch — a cross-branch account is as invisible as a
    missing one (404)."""
    account = await session.get(Account, account_id)
    if account is None or account.branch_id != branch_id:
        raise NOT_FOUND
    return account


async def used_account_ids(session: AsyncSession, branch_id: int) -> set[int]:
    """Account ids with posting history or a party receivable/payable link.

    Referenced means referenced from anywhere: a journal line or balance row
    that points at the account counts even when the posting came from another
    branch (the journal engine inherits branch-1's chart for chart-less
    branches, so a branch-2 posting can reference a branch-1 account). Those
    cross-branch references must still pin the account's shape, otherwise a
    rename/delete would strand the history.
    """
    ids = set(
        (await session.execute(select(JournalLine.account_id))).scalars().all()
    )
    ids.update((await session.execute(select(Balance.account_id))).scalars().all())
    parties = await session.execute(
        select(Party.receivable_account_id, Party.payable_account_id).where(
            Party.branch_id == branch_id
        )
    )
    for receivable_id, payable_id in parties.all():
        if receivable_id is not None:
            ids.add(receivable_id)
        if payable_id is not None:
            ids.add(payable_id)
    return ids


async def account_has_children(
    session: AsyncSession, branch_id: int, account_id: int
) -> bool:
    row = (
        await session.execute(
            select(Account.id)
            .where(Account.parent_id == account_id, Account.branch_id == branch_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


async def _has_active_children(
    session: AsyncSession, branch_id: int, account_id: int
) -> bool:
    row = (
        await session.execute(
            select(Account.id)
            .where(
                Account.parent_id == account_id,
                Account.branch_id == branch_id,
                Account.is_active.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


async def _would_cycle(
    session: AsyncSession, branch_id: int, parent_id: int, account_id: int
) -> bool:
    """True if `parent_id` is `account_id` or one of its descendants."""
    if parent_id == account_id:
        return True
    seen: set[int] = set()
    current: Optional[int] = parent_id
    while current is not None and current not in seen:
        if current == account_id:
            return True
        seen.add(current)
        account = await session.get(Account, current)
        if account is None or account.branch_id != branch_id:
            return False
        current = account.parent_id
    return False


def serialize_account(account: Account, *, has_children: bool, used: bool) -> dict:
    return {
        "id": account.id,
        "branch_id": account.branch_id,
        "code": account.code,
        "parent_id": account.parent_id,
        "master": account.master or "",
        "fary": account.fary or "",
        "name_ar": account.name_ar or "",
        "name_en": account.name_en or "",
        "type": account.type,
        "is_active": bool(account.is_active),
        "has_children": has_children,
        "used": used,
    }


async def list_accounts(
    session: AsyncSession,
    *,
    branch_id: int,
    type: Optional[str] = None,
    parent_id: Optional[int] = None,
    search: Optional[str] = None,
    active_only: bool = False,
    limit: int = 200,
) -> list[dict]:
    accounts = (
        await session.execute(
            select(Account).where(Account.branch_id == branch_id)
        )
    ).scalars().all()
    child_ids = {a.parent_id for a in accounts if a.parent_id is not None}
    used = await used_account_ids(session, branch_id)
    rows = []
    for a in accounts:
        if type is not None and a.type != type:
            continue
        if parent_id is not None and a.parent_id != parent_id:
            continue
        if search:
            needle = search.lower()
            if not (
                a.name_ar and needle in a.name_ar.lower()
                or a.name_en and needle in a.name_en.lower()
                or a.code and needle in a.code.lower()
            ):
                continue
        if active_only and not a.is_active:
            continue
        rows.append(
            serialize_account(a, has_children=a.id in child_ids, used=a.id in used)
        )
    rows.sort(key=lambda r: r["code"])
    return rows[: min(limit, 500) if limit > 0 else 0]


async def account_tree(session: AsyncSession, *, branch_id: int) -> list[dict]:
    """Nested roots→children tree, both levels sorted by code. Orphaned rows
    (parent missing from the branch) surface as roots so nothing disappears."""
    accounts = (
        await session.execute(
            select(Account).where(Account.branch_id == branch_id)
        )
    ).scalars().all()
    used = await used_account_ids(session, branch_id)
    nodes: dict[int, dict] = {}
    for a in accounts:
        nodes[a.id] = serialize_account(
            a, has_children=False, used=a.id in used
        )
    for a in accounts:
        node = nodes[a.id]
        node["children"] = []
    roots: list[dict] = []
    for a in accounts:
        node = nodes[a.id]
        parent = nodes.get(a.parent_id) if a.parent_id is not None else None
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
            parent["has_children"] = True
    for node in nodes.values():
        node["children"].sort(key=lambda n: n["code"])
    roots.sort(key=lambda n: n["code"])
    return roots


async def create_account(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    body,
) -> Account:
    code = body.code.strip()
    name_ar = body.name_ar.strip()
    name_en = (body.name_en or "").strip()
    if not code or not name_ar:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "code and name cannot be blank"
        )
    duplicate = (
        await session.execute(
            select(Account.id).where(
                Account.branch_id == branch_id, Account.code == code
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "account code already exists in this branch",
        )
    parent: Optional[Account] = None
    if body.parent_id is not None:
        parent = await get_account(session, branch_id, body.parent_id)
    account = Account(
        branch_id=branch_id,
        code=code,
        name_ar=name_ar,
        name_en=name_en,
        type=body.type,
        parent_id=parent.id if parent else None,
        master=parent.code if parent else "",
        fary=code,
        is_active=body.is_active,
    )
    session.add(account)
    try:
        async with atomic(session):
            await session.flush()
            await audit(
                session,
                branch_id=branch_id,
                user_id=user_id,
                entity="accounts",
                entity_id=account.id,
                action=ACTION_INSERT,
                new_value=f"code={account.code} type={account.type} name={account.name_ar}",
                typevalue=account.name_ar,
            )
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "account code already exists in this branch",
        )
    return account


async def update_account(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    account_id: int,
    data: dict,
) -> Account:
    """`data` = body.model_dump(exclude_unset=True); `parent_id: None` present
    in data means "clear the parent"."""
    data = {
        k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()
    }
    account = await get_account(session, branch_id, account_id)
    used = account_id in await used_account_ids(session, branch_id)

    if "code" in data and data["code"] != account.code:
        if used:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "cannot rename a referenced account (it has postings, parties, or children)",
            )
        if await account_has_children(session, branch_id, account_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "cannot rename an account that has children",
            )
        if not data["code"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "code cannot be blank"
            )
        duplicate = (
            await session.execute(
                select(Account.id).where(
                    Account.branch_id == branch_id,
                    Account.code == data["code"],
                    Account.id != account_id,
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "account code already exists in this branch",
            )
    renamed = (
        ("name_ar" in data and data["name_ar"] != account.name_ar)
        or ("name_en" in data and data["name_en"] != account.name_en)
    )
    if renamed and used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "cannot rename a referenced account (postings/parties)",
        )
    if (
        "name_ar" in data
        and data["name_ar"].strip() == ""
        and data["name_ar"] != account.name_ar
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "name cannot be blank"
        )
    if "type" in data and data["type"] != account.type and used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "cannot change the type of a referenced account",
        )

    parent_changed = "parent_id" in data and data["parent_id"] != account.parent_id
    new_parent: Optional[Account] = None
    if parent_changed:
        if data["parent_id"] is not None:
            new_parent = await get_account(session, branch_id, data["parent_id"])
            if await _would_cycle(session, branch_id, new_parent.id, account.id):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "cannot make an account a child of its own descendant",
                )

    deactivating = (
        "is_active" in data
        and data["is_active"] is False
        and account.is_active
    )
    if deactivating:
        if used:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "cannot deactivate a referenced account (postings/parties)",
            )
        if await _has_active_children(session, branch_id, account.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "cannot deactivate an account with active children",
            )

    old_value = f"code={account.code} name={account.name_ar} type={account.type}"
    if "code" in data:
        account.code = data["code"]
    if "name_ar" in data:
        account.name_ar = data["name_ar"]
    if "name_en" in data:
        account.name_en = data["name_en"] or ""
    if "type" in data:
        account.type = data["type"]
    if "is_active" in data:
        account.is_active = data["is_active"]
    if parent_changed:
        account.parent_id = new_parent.id if new_parent else None
    if "code" in data or parent_changed:
        account.master = new_parent.code if new_parent else ""
        account.fary = account.code

    try:
        async with atomic(session):
            await audit(
                session,
                branch_id=branch_id,
                user_id=user_id,
                entity="accounts",
                entity_id=account.id,
                action=ACTION_UPDATE,
                old_value=old_value,
                new_value=(
                    f"code={account.code} name={account.name_ar} "
                    f"type={account.type} parent_id={account.parent_id} "
                    f"active={account.is_active}"
                ),
                typevalue=account.name_ar,
            )
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "account code already exists in this branch",
        )
    return account


async def delete_account(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    account_id: int,
) -> None:
    account = await get_account(session, branch_id, account_id)
    used = account_id in await used_account_ids(session, branch_id)
    has_children = (
        await session.execute(
            select(Account.id)
            .where(Account.parent_id == account_id, Account.branch_id == branch_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if used or has_children is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "cannot delete a referenced account (postings/parties/children) — deactivate it instead",
        )
    try:
        async with atomic(session):
            await audit(
                session,
                branch_id=branch_id,
                user_id=user_id,
                entity="accounts",
                entity_id=account.id,
                action=ACTION_DELETE,
                old_value=f"code={account.code} name={account.name_ar}",
                typevalue=account.name_ar,
            )
            await session.delete(account)
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "cannot delete a referenced account (postings/parties/children) — deactivate it instead",
        )