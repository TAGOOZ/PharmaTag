"""Stock endpoints (S1.7, ticket #13).

Count flow: any authenticated staff user submits a physical `counted` qty
(`POST /count-requests`); a manager (perm >= 7) approves or rejects it. The
approval applies the correction atomically (G12) — see app/stock/counting.py.
`GET /current` is the counting sheet: every branch drug with its system qty
and expiry batches (feature_stock_counting §2.1, §7).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level, require_permission
from app.core import money
from app.core.db import get_session
from app.models import BranchStock, Drug, DrugBarcode, StockBatch, StockCorrectionRequest, User
from app.reports.chain_stock import query_chain_stock
from app.stock.counting import (
    approve_count_request,
    reject_count_request,
    submit_count_request,
)
from app.stock.schemas import (
    CountRequestCreate,
    CountRequestOut,
    CurrentStockListOut,
    MinimumSetRequest,
    MinimumSetResponse,
)
from app.stock.service import set_minimum as svc_set_minimum

router = APIRouter()

APPROVE_CORRECTION = require_level(7)
STOCK_MANAGE = require_permission("stock.manage")


def _qty(value) -> str:
    if value is None or value == "":
        value = 0
    try:
        return format(money.round4(value), "f")
    except Exception:
        return format(money.round4(0), "f")


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
) -> CountRequestOut:
    return CountRequestOut(
        id=request.id,
        branch_id=request.branch_id,
        drug_id=request.drug_id,
        batch_id=request.batch_id,
        delta=_qty(request.delta),
        counted=_qty(request.counted) if request.counted is not None else None,
        system_qty=system_qty,
        reason=request.reason or "",
        status=request.status,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        rejected_by=request.rejected_by,
        decided_at=request.decided_at.isoformat() if request.decided_at else None,
        created_at=request.created_at.isoformat() if request.created_at else None,
    )


@router.get("/current", response_model=CurrentStockListOut)
async def current_stock(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=200),
    only_shortage: bool = Query(default=False),
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
        raw = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{raw}%"
        barcode_ids = select(DrugBarcode.drug_id).where(DrugBarcode.barcode.ilike(like, escape="\\"))
        stmt = stmt.where(
            Drug.drugname.ilike(like, escape="\\")
            | Drug.drugnamear.ilike(like, escape="\\")
            | Drug.generic.ilike(like, escape="\\")
            | Drug.id.in_(barcode_ids)
        )
    if only_shortage:
        # NULL-safe: coalesce so null minimum/qty not hidden (pre-017 rows)
        stmt = stmt.where(func.coalesce(BranchStock.qty, 0) < func.coalesce(BranchStock.minimum, 0))
    # shortage DESC secondary sort requires fetching shortage expression; we order by shortage then name
    # NULL-safe: coalesce to 0, GREATEST(null,0) is null on PG
    shortage_expr = func.greatest(func.coalesce(BranchStock.minimum, 0) - func.coalesce(BranchStock.qty, 0), Decimal("0"))
    # count before limit for truncated detection (M7)
    count_stmt = select(func.count()).select_from(BranchStock).join(Drug, Drug.id == BranchStock.drug_id).where(BranchStock.branch_id == branch_id)
    if q and q.strip():
        # reuse same where as stmt (branch_id already, plus q)
        raw = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{raw}%"
        barcode_ids = select(DrugBarcode.drug_id).where(DrugBarcode.barcode.ilike(like, escape="\\"))
        count_stmt = count_stmt.where(
            or_(
                Drug.drugname.ilike(like, escape="\\"),
                Drug.drugnamear.ilike(like, escape="\\"),
                Drug.generic.ilike(like, escape="\\"),
                Drug.id.in_(barcode_ids),
            )
        )
    if only_shortage:
        count_stmt = count_stmt.where(func.coalesce(BranchStock.qty, 0) < func.coalesce(BranchStock.minimum, 0))
    total = (await session.execute(count_stmt)).scalar_one()
    truncated = total > limit
    stmt = stmt.order_by(shortage_expr.desc(), Drug.drugname.asc()).limit(limit)
    rows = (await session.execute(stmt)).all()

    # batch Fetch N+1 fix: single query for all drug batches (like chain_stock.py:87)
    batch_map: dict[int, list[StockBatch]] = {}
    if rows:
        drug_ids = [drug.id for _, drug in rows]
        all_batches = (
            await session.execute(
                select(StockBatch)
                .where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.drug_id.in_(drug_ids),
                    StockBatch.qty > 0,
                )
                .order_by(StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id)
            )
        ).scalars().all()
        for b in all_batches:
            batch_map.setdefault(b.drug_id, []).append(b)

    items = []
    for stock, drug in rows:
        batches = batch_map.get(drug.id, [])
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
                "price": _qty(drug.price),
                "batches": [
                    {
                        "batch_id": b.id,
                        "randomid": b.randomid,
                        "qty": _qty(b.qty),
                        "cost": _qty(b.cost),
                        "expire": b.expire.isoformat() if b.expire else None,
                    }
                    for b in batches
                ],
            }
        )
    return CurrentStockListOut(items=items, count=int(total), truncated=bool(truncated))


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
    return _serialize(request, system_qty=system_qty)


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


@router.patch("/minimum", response_model=MinimumSetResponse)
async def set_minimum_endpoint(
    body: MinimumSetRequest,
    caller: User = Depends(STOCK_MANAGE),
    session: AsyncSession = Depends(get_session),
):
    """Set per-branch reorder point (minimum) — creates BranchStock if missing."""
    if caller.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    branch_id = caller.branch_id
    row = await svc_set_minimum(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        drug_id=body.drug_id,
        minimum=body.minimum,
    )
    return MinimumSetResponse(
        branch_id=branch_id,
        drug_id=body.drug_id,
        qty=_qty(row.qty),
        minimum=_qty(row.minimum),
        silsilaid=row.silsilaid or "",
        classy=row.classy or "",
    )


@router.get("/cross-branch")
async def cross_branch_stock(
    drug_id: Optional[int] = Query(default=None, gt=0),
    q: Optional[str] = Query(default=None, max_length=100),
    only_shortage: bool = Query(default=False),
    include_inactive: bool = Query(default=False),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Cross-branch stock snapshot (S5.5 #35): per-(branch,drug) qty/minimum/shortage.

    Read-only projection over canonical `branch_stock` (A06). Any authenticated
    user may read (no permission gate). Delegates to shared ``query_chain_stock``
    so report + API never drift (review Medium).
    """
    data = await query_chain_stock(
        session,
        drug_id=drug_id,
        q=q,
        only_shortage=only_shortage,
        include_inactive=include_inactive,
    )
    resp: dict = {"count": data["count"], "truncated": data["truncated"], "items": data["items"]}
    if drug_id is not None:
        resp["drug_id"] = drug_id
    return resp