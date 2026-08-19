"""Statement + payables endpoints (S2.3, issue #18).

Read-only, branch-scoped to the caller (reads are open to any authenticated
user, same posture as journal/account reads). `GET /parties/{id}/statement`
renders a party's AR/AP كشف حساب as JSON or an A4 HTML page (`format=html`);
`GET /parties/payables` lists every active supplier/both party with its
all-time net AP balance. Money leaves as exact decimal strings (plan/02 §2).
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_session
from app.models import User
from app.statements import print_html, service

router = APIRouter()


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


@router.get("/{party_id}/statement")
async def get_statement(
    party_id: int,
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    side: Optional[str] = None,
    format: Literal["json", "html"] = "json",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """كشف حساب — a party's AR/AP ledger with opening/movements/closing."""
    branch_id = _caller_branch_id(user)
    payload = await service.get_statement(
        session,
        branch_id=branch_id,
        party_id=party_id,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
        side=side,
    )
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_statement(payload),
        status_code=status.HTTP_200_OK,
    )


@router.get("/payables")
async def get_payables(
    format: Literal["json", "html"] = "json",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """أرصدة الموردين — every active supplier/both party's all-time net AP."""
    branch_id = _caller_branch_id(user)
    payload = await service.get_payables(session, branch_id=branch_id)
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_payables(payload),
        status_code=status.HTTP_200_OK,
    )