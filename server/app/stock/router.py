"""Stock endpoints (S1.7, ticket #13).

Count flow: any authenticated staff user submits a physical `counted` qty
(`POST /count-requests`); a manager (perm >= 7) approves or rejects it. The
approval applies the correction atomically (G12) — see app/stock/counting.py.
`GET /current` is the counting sheet: every branch drug with its system qty
and expiry batches (feature_stock_counting §2.1, §7).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level
from app.core import money
from app.core.db import get_session
from app.models import BranchStock, Drug, StockBatch, StockCorrectionRequest, User
from app.stock.counting import (
    approve_count_request,
    reject_count_request,
    submit_count_request,
)
from app.stock.schemas import (
    CountRequestCreate,
    CountRequestOut,
    CurrentStockListOut,
)

router = APIRouter()

APPROVE_CORRECTION = require_level(7)


def _qty(value) -> str:
    return format(money.round4(value), "f")


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


async def _live_system_qty(session: AsyncSession, branch_id: int, drug_id: int) -> str:
    row = (
        await session.execute(
            select(BranchStock.qty).where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
        )
    ).scalar_one_or_none()
    return _qty(row if row is not None else 0)


def _serialize(
    request: StockCorrectionRequest,
    *,
    system_qty: str,
    counted: Optional[str] = None,
) -> CountRequestOut:
    return CountRequestOut(
        id=request.id,
        branch_id=request.branch_id,
        drug_id=request.drug_id,
        batch_id=request.batch_id,
        delta=_qty(request.delta),
        counted=counted,
        system_qty=system_qty,
        reason=request.reason or "",
        status=request.status,
        requested_by=request.requested_by,
        decided_at=request.decided_at.isoformat() if request.decided_at else None,
        created_at=request.created_at.isoformat() if request.created_at else None,
    )


@router.get("/current", response_model=CurrentStockListOut)
async def current_stock(
    q: str = "",
    limit: int = 200,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Counting sheet: branch drugs with system qty + expiry batches."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 500))
    stmt = (
        select(BranchStock, Drug)
        .join(Drug, Drug.id == BranchStock.drug_id)
        .where(BranchStock.branch_id == branch_id)
        .options(selectinload(Drug.barcodes))
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            Drug.drugname.ilike(like)
            | Drug.drugnamear.ilike(like)
            | Drug.generic.ilike(like)
        )
    stmt = stmt.order_by(Drug.drugname).limit(limit)
    rows = (await session.execute(stmt)).all()

    items = []
    for stock, drug in rows:
        batches = (
            await session.execute(
                select(StockBatch)
                .where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.drug_id == drug.id,
                    StockBatch.qty > 0,
                )
                .order_by(StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id)
            )
        ).scalars().all()
        primary = next((b.barcode for b in sorted(drug.barcodes, key=lambda b: not b.is_primary)), "")
        items.append(
            {
                "branch_id": branch_id,
                "drug_id": drug.id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear or "",
                "barcode": primary,
                "qty": _qty(stock.qty),
                "minimum": _qty(stock.minimum),
                "price": format(money.round4(drug.price), "f"),
                "batches": [
                    {
                        "batch_id": b.id,
                        "randomid": b.randomid,
                        "qty": _qty(b.qty),
                        "cost": format(money.round4(b.cost), "f"),
                        "expire": b.expire.isoformat() if b.expire else None,
                    }
                    for b in batches
                ],
            }
        )
    return CurrentStockListOut(items=items)


@router.get("/count-requests")
async def list_count_requests(
    status_filter: Optional[str] = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Recent count requests for the caller's branch (optionally by status)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(StockCorrectionRequest).where(
        StockCorrectionRequest.branch_id == branch_id
    )
    if status_filter in ("pending", "approved", "rejected"):
        q = q.where(StockCorrectionRequest.status == status_filter)
    elif status_filter:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid status filter")
    q = q.order_by(StockCorrectionRequest.id.desc()).limit(limit)
    requests = (await session.execute(q)).scalars().all()
    return {
        "requests": [
            _serialize(
                request,
                system_qty=await _live_system_qty(
                    session, branch_id, request.drug_id
                ),
            )
            for request in requests
        ]
    }


@router.post("/count-requests", status_code=status.HTTP_201_CREATED)
async def create_count_request(
    body: CountRequestCreate,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Submit a physical count; the server derives the signed delta and stores
    a pending correction request for manager approval."""
    branch_id = _caller_branch_id(caller)
    request = await submit_count_request(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        drug_id=body.drug_id,
        counted=body.counted,
        reason=body.reason or "",
        batch_id=body.batch_id,
    )
    system_qty = await _live_system_qty(session, branch_id, request.drug_id)
    return _serialize(
        request,
        system_qty=system_qty,
        counted=_qty(money.dec(system_qty) + money.dec(request.delta)),
    )


@router.post("/count-requests/{request_id}/approve")
async def approve_request(
    request_id: int,
    caller: User = Depends(APPROVE_CORRECTION),
    session: AsyncSession = Depends(get_session),
):
    """Manager approval: apply the correction atomically (G12)."""
    branch_id = _caller_branch_id(caller)
    request = await approve_count_request(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        request_id=request_id,
    )
    return _serialize(
        request,
        system_qty=await _live_system_qty(session, branch_id, request.drug_id),
    )


@router.post("/count-requests/{request_id}/reject")
async def reject_request(
    request_id: int,
    caller: User = Depends(APPROVE_CORRECTION),
    session: AsyncSession = Depends(get_session),
):
    """Manager rejection: mark rejected; no stock is touched."""
    branch_id = _caller_branch_id(caller)
    request = await reject_count_request(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        request_id=request_id,
    )
    return _serialize(
        request,
        system_qty=await _live_system_qty(session, branch_id, request.drug_id),
    )