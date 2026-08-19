"""Reports endpoints (S1.9, ticket #15).

Read-only, branch-scoped, gated by the seeded `reports` permission (admin
level-9 floor or the accountant role). Money leaves as exact decimal strings
(plan/02 §2). Each report answers as JSON by default and as a black-on-white
A4 page when `format=html` (plan/09 P06) — the same print convention as the
sales receipt.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User
from app.reports import print_html
from app.reports.catalog import get_catalog
from app.reports.day_profit import day_profit_report
from app.reports.drawer_handover import drawer_handover_report
from app.reports.period_totals import period_totals_report
from app.reports.stock_minimum import stock_minimum_report

router = APIRouter()

REPORTS = require_permission("reports")


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


@router.get("")
async def list_reports(
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """The report catalog (codes + bilingual titles + params) for a screen menu."""
    return {"reports": get_catalog()}


@router.get("/day-profit")
async def report_day_profit(
    datee: Optional[date] = None,
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """ربح اليوم: net revenue, COGS, expenses, net profit, VAT, discounts."""
    branch_id = _caller_branch_id(caller)
    payload = await day_profit_report(session, branch_id=branch_id, datee=datee)
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_day_profit(payload),
        status_code=status.HTTP_200_OK,
    )


@router.get("/period-totals")
async def report_period_totals(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """ملخص المبيعات والمشتريات: counts + totals per kind over a date range."""
    branch_id = _caller_branch_id(caller)
    payload = await period_totals_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_period_totals(payload),
        status_code=status.HTTP_200_OK,
    )


@router.get("/stock-minimum")
async def report_stock_minimum(
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """النواقص: branch drugs whose qty is below the reorder point (RPT-ST01)."""
    branch_id = _caller_branch_id(caller)
    payload = await stock_minimum_report(session, branch_id=branch_id)
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_stock_minimum(payload),
        status_code=status.HTTP_200_OK,
    )


@router.get("/drawer-handover")
async def report_drawer_handover(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    format: str = "json",
    caller: User = Depends(REPORTS),
    session: AsyncSession = Depends(get_session),
):
    """تسليم الدرج: per-cashier cash/network in-out totals over a period."""
    branch_id = _caller_branch_id(caller)
    payload = await drawer_handover_report(
        session, branch_id=branch_id, date_from=date_from, date_to=date_to
    )
    if format != "html":
        return payload
    return HTMLResponse(
        content=print_html.render_drawer_handover(payload),
        status_code=status.HTTP_200_OK,
    )
