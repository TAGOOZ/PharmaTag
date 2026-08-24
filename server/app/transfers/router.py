"""Transfer endpoints (ticket #32, S5.2).

Writes are gated by `transfers.manage` (seeded to admin/pharmacist/manager,
legacy floor 3 — the stock area) AND the T7 branch authority: only the source
branch dispatches, only the target branch receives, either party cancels a
draft. Reads are open to any authenticated user but scoped to transfers the
caller's branch participates in.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.core.money import dec
from app.models import Transfer, User
from app.transfers import service

router = APIRouter()

MANAGE_TRANSFERS = require_permission("transfers.manage")

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "transfer not found")


class DraftLine(BaseModel):
    drug_id: int = Field(gt=0)
    # typed at the boundary (purchases pattern): "abc"/"NaN" die here with a
    # clean 400 via the app-wide RequestValidationError handler, never a 500
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class CreateTransferRequest(BaseModel):
    target_branch_id: int
    lines: list[DraftLine]
    legacy_fatid: Optional[str] = Field(default=None, max_length=50)
    note: str = Field(default="", max_length=200)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_transfer(
    body: CreateTransferRequest,
    response: Response,
    caller: User = Depends(MANAGE_TRANSFERS),
    session: AsyncSession = Depends(get_session),
):
    """Create a transfer draft (201) or replay an existing one (200).

    Idempotent ETL contract (#56): when `legacy_fatid` is provided, a
    re-import of the same legacy FAT row converges instead of minting a
    second transfer:

    * same (source, fatid, target) → the EXISTING transfer is returned with
      **200** and its current body, whatever its status;
    * same fatid bound to a DIFFERENT target branch → **409** conflict;
    * different source branches may reuse one fatid freely;
    * omitted/null fatid → plain create (201), unlimited drafts.
    """
    transfer, lines, replayed = await service.create_draft(
        session,
        caller=caller,
        target_branch_id=body.target_branch_id,
        lines=[line.model_dump() for line in body.lines],
        legacy_fatid=body.legacy_fatid,
        note=body.note,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return service.public_transfer(transfer, lines)


@router.get("")
async def list_transfers(
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Transfers the caller's branch participates in (outbound AND inbound)."""
    if caller.branch_id is None:
        return {"transfers": []}
    rows = (
        await session.execute(
            select(Transfer)
            .where(
                or_(
                    Transfer.source_branch_id == caller.branch_id,
                    Transfer.target_branch_id == caller.branch_id,
                )
            )
            .order_by(Transfer.id.desc())
        )
    ).scalars().all()
    result = []
    for transfer in rows:
        _, lines = await service.get_transfer(session, transfer.id)
        result.append(service.public_transfer(transfer, lines))
    return {"transfers": result}


@router.get("/{transfer_id}")
async def get_transfer(
    transfer_id: int,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    transfer, lines = await service.get_transfer(session, transfer_id)
    parties = {transfer.source_branch_id, transfer.target_branch_id}
    if caller.branch_id not in parties:
        raise NOT_FOUND  # existence of foreign transfers is not disclosed
    return service.public_transfer(transfer, lines)


class BatchTake(BaseModel):
    batch_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class DispatchLine(BaseModel):
    line_id: int
    allocations: Optional[list[BatchTake]] = None


class DispatchRequest(BaseModel):
    """`lines` omitted ⇒ server FEFO-suggests every line; when provided, every
    line must be covered (a line without allocations also gets FEFO)."""

    lines: list[DispatchLine] = []


@router.post("/{transfer_id}/dispatch")
async def dispatch_transfer(
    transfer_id: int,
    body: DispatchRequest,
    caller: User = Depends(MANAGE_TRANSFERS),
    session: AsyncSession = Depends(get_session),
):
    if body.lines and len(body.lines) != len({e.line_id for e in body.lines}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "duplicate line_id")
    transfer, _ = await service.get_transfer(session, transfer_id)
    explicit = (
        {
            entry.line_id: (
                [(take.batch_id, dec(take.qty)) for take in entry.allocations]
                if entry.allocations is not None
                else None
            )
            for entry in body.lines
        }
        if body.lines
        else None
    )
    lines = await service.dispatch(
        session, caller=caller, transfer=transfer, explicit=explicit
    )
    return service.public_transfer(transfer, lines)


class ReceiveLine(BaseModel):
    line_id: int
    # ge=0 on purpose: a fully-lost shipment receives zero and everything
    # auto-returns to the source; the ≤ sent_qty ceiling stays in the service
    received_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class ReceiveRequest(BaseModel):
    lines: list[ReceiveLine]


@router.post("/{transfer_id}/receive")
async def receive_transfer(
    transfer_id: int,
    body: ReceiveRequest,
    caller: User = Depends(MANAGE_TRANSFERS),
    session: AsyncSession = Depends(get_session),
):
    if len(body.lines) != len({e.line_id for e in body.lines}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "duplicate line_id")
    transfer, _ = await service.get_transfer(session, transfer_id)
    receipts = {entry.line_id: dec(entry.received_qty) for entry in body.lines}
    lines = await service.receive(
        session, caller=caller, transfer=transfer, receipts=receipts
    )
    return service.public_transfer(transfer, lines)


@router.post("/{transfer_id}/cancel")
async def cancel_transfer(
    transfer_id: int,
    caller: User = Depends(MANAGE_TRANSFERS),
    session: AsyncSession = Depends(get_session),
):
    transfer, _ = await service.get_transfer(session, transfer_id)
    lines = await service.cancel(session, caller=caller, transfer=transfer)
    return service.public_transfer(transfer, lines)
