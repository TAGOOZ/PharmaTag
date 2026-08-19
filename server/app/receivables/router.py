"""Settlement + receivables endpoints (S2.4, ticket #19).

Posting and reversal are gated by the granular `receivables.manage` permission
(legacy floor 7: ledger-area balance writes, plan/02 §3; granted to admin,
accountant, and manager roles). Reads (voucher list/detail, the receivables
register) are open to any authenticated user so the money screens and reports
can feed from them. Every write is branch-scoped to the caller and atomic with
its audit row (G12).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.service import caller_branch_id
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.receivables import print_html, service
from app.receivables.schemas import SettlementVoucherCreate

router = APIRouter()

RECEIVABLES_WRITE = require_permission("receivables.manage")


@router.post("/vouchers", status_code=status.HTTP_201_CREATED)
async def post_voucher(
    body: SettlementVoucherCreate,
    caller: User = Depends(RECEIVABLES_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    voucher = await service.post_voucher(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        voucher_type=body.voucher_type,
        party_id=body.party_id,
        datee=body.datee,
        method=body.method,
        amount=body.amount,
        description=body.description,
    )
    return await service.serialize_voucher(session, voucher)


@router.get("/vouchers")
async def list_vouchers(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return {
        "vouchers": await service.list_vouchers(
            session, branch_id=branch_id, limit=limit
        )
    }


@router.get("/vouchers/{voucher_id}")
async def get_voucher(
    voucher_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(user)
    return await service.get_voucher(
        session, branch_id=branch_id, voucher_id=voucher_id
    )


@router.post("/vouchers/{voucher_id}/reverse", status_code=status.HTTP_201_CREATED)
async def reverse_voucher(
    voucher_id: int,
    caller: User = Depends(RECEIVABLES_WRITE),
    session: AsyncSession = Depends(get_session),
):
    branch_id = await caller_branch_id(caller)
    voucher = await service.reverse_voucher(
        session, branch_id=branch_id, user_id=caller.id, voucher_id=voucher_id
    )
    return await service.serialize_voucher(session, voucher)


@router.get("")
async def get_receivables(
    format: Literal["json", "html"] = "json",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """أرصدة العملاء — every active customer/both party's all-time net AR."""
    branch_id = await caller_branch_id(user)
    payload = await service.get_receivables(session, branch_id=branch_id)
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_receivables(payload),
        status_code=status.HTTP_200_OK,
    )