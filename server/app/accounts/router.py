"""Chart-of-accounts endpoints (S2.1, ticket #16) + the ميزان (S2.5, #20).

Reads (list/tree/detail/trial-balance/balance-sheet) are open to any
authenticated user so the tree can drive journal-posting pickers; writes
(create/update/delete) are gated by the granular `accounts.manage` permission
(legacy level >= 7 floor, or the accountant role). Every write carries its
audit row (G12). The tree is branch-scoped: a caller only ever sees/mutates
their own branch's chart.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import print_html, service
from app.accounts.mizan import get_balance_sheet, get_trial_balance
from app.accounts.schemas import AccountCreate, AccountUpdate
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User

router = APIRouter()

ACCOUNTS_WRITE = require_permission("accounts.manage")


@router.get("")
async def list_accounts(
    type: Optional[str] = None,
    parent_id: Optional[int] = None,
    search: Optional[str] = None,
    active_only: bool = False,
    limit: int = 200,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Flat, branch-scoped account list (filters + code-ordered)."""
    branch_id = await service.caller_branch_id(user)
    return {
        "accounts": await service.list_accounts(
            session,
            branch_id=branch_id,
            type=type,
            parent_id=parent_id,
            search=search,
            active_only=active_only,
            limit=limit,
        )
    }


@router.get("/tree")
async def tree_accounts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """The hierarchical chart (roots → children), sorted by code."""
    branch_id = await service.caller_branch_id(user)
    return {"tree": await service.account_tree(session, branch_id=branch_id)}


@router.get("/trial-balance")
async def trial_balance(
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: Literal["json", "html"] = "json",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """ميزان المراجعة — per-account-code debit/credit/balance for a period."""
    branch_id = await service.caller_branch_id(user)
    payload = await get_trial_balance(
        session,
        branch_id=branch_id,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
    )
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_trial_balance(payload),
        status_code=status.HTTP_200_OK,
    )


@router.get("/balance-sheet")
async def balance_sheet(
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: Literal["json", "html"] = "json",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """ميزانية عمومية — assets / liabilities / equity (incl. P&L) for a period."""
    branch_id = await service.caller_branch_id(user)
    payload = await get_balance_sheet(
        session,
        branch_id=branch_id,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
    )
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_balance_sheet(payload),
        status_code=status.HTTP_200_OK,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    caller: User = Depends(ACCOUNTS_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await service.caller_branch_id(caller)
    account = await service.create_account(
        session, branch_id=branch_id, user_id=caller.id, body=body
    )
    return service.serialize_account(account, has_children=False, used=False)


@router.get("/{account_id}")
async def get_account(
    account_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """One account + its direct children (for pickers/detail)."""
    branch_id = await service.caller_branch_id(user)
    account = await service.get_account(session, branch_id, account_id)
    children = (
        await service.list_accounts(
            session, branch_id=branch_id, parent_id=account_id, limit=500
        )
    )
    used = account_id in await service.used_account_ids(session, branch_id)
    body = service.serialize_account(
        account, has_children=bool(children), used=used
    )
    body["children"] = children
    return body


@router.patch("/{account_id}")
async def update_account(
    account_id: int,
    body: AccountUpdate,
    caller: User = Depends(ACCOUNTS_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await service.caller_branch_id(caller)
    account = await service.update_account(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        account_id=account_id,
        data=body.model_dump(exclude_unset=True),
    )
    used = account_id in await service.used_account_ids(session, branch_id)
    return service.serialize_account(
        account,
        has_children=await service.account_has_children(
            session, branch_id, account_id
        ),
        used=used,
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    caller: User = Depends(ACCOUNTS_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await service.caller_branch_id(caller)
    await service.delete_account(
        session, branch_id=branch_id, user_id=caller.id, account_id=account_id
    )