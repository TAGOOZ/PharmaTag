"""Chain-buy endpoints (ticket #36, S5.6).

Writes gated by `chain_buy.manage` (seeded admin/pharmacist/manager, legacy
floor 3 stock area). Reads open to any authenticated user but global chain view
(all branches). Caller must be branch-pinned for writes.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core.db import get_session
from app.models import User

from app.chain_buy import service

router = APIRouter(tags=["chain-buy"])

MANAGE = require_permission("chain_buy.manage")


class CreateChainBuyRequest(BaseModel):
    drug_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    sell_disc: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    expire: Optional[date] = None
    store_name: str = Field(default="", max_length=100)
    pharmacist_tel: str = Field(default="", max_length=15)
    requester_tel: str = Field(default="", max_length=15)
    tips: str = Field(default="", max_length=50)
    governorate: str = Field(default="", max_length=50)
    district: str = Field(default="", max_length=50)
    country: str = Field(default="", max_length=50)


class UpdateChainBuyRequest(BaseModel):
    qty: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=4)
    price: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    sell_disc: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    expire: Optional[date] = None
    store_name: Optional[str] = Field(default=None, max_length=100)
    pharmacist_tel: Optional[str] = Field(default=None, max_length=15)
    requester_tel: Optional[str] = Field(default=None, max_length=15)
    tips: Optional[str] = Field(default=None, max_length=50)
    governorate: Optional[str] = Field(default=None, max_length=50)
    district: Optional[str] = Field(default=None, max_length=50)
    country: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default=None, max_length=20)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chain_buy(
    body: CreateChainBuyRequest,
    caller: User = Depends(MANAGE),
    session: AsyncSession = Depends(get_session),
):
    order = await service.create_chain_buy(
        session,
        caller=caller,
        drug_id=body.drug_id,
        qty=body.qty,
        price=body.price,
        sell_disc=body.sell_disc,
        expire=body.expire,
        store_name=body.store_name,
        tips=body.tips,
        governorate=body.governorate,
        district=body.district,
        country=body.country,
        pharmacist_tel=body.pharmacist_tel,
        requester_tel=body.requester_tel,
    )
    return service.public_chain_buy(order)


@router.get("")
async def list_chain_buy(
    drug_id: Optional[int] = Query(default=None, gt=0),
    q: Optional[str] = Query(default=None, max_length=100),
    store_name: Optional[str] = Query(default=None, max_length=100),
    governorate: Optional[str] = Query(default=None, max_length=100),
    district: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    include_inactive: bool = Query(default=False),
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data = await service.list_chain_buy(
        session,
        caller,
        drug_id=drug_id,
        q=q,
        store_name=store_name,
        governorate=governorate,
        district=district,
        status_filter=status_filter,
        include_inactive=include_inactive,
    )
    # expose count/truncated + items; hide internal _orders
    return {
        "count": data["count"],
        "truncated": data["truncated"],
        "items": data["items"],
    }


@router.get("/{order_id}")
async def get_chain_buy(
    order_id: int,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = await service.get_chain_buy(session, order_id)
    return service.public_chain_buy(order)


@router.patch("/{order_id}")
async def update_chain_buy(
    order_id: int,
    body: UpdateChainBuyRequest,
    caller: User = Depends(MANAGE),
    session: AsyncSession = Depends(get_session),
):
    order = await service.get_chain_buy(session, order_id)
    # sentinel for expire: distinguish omitted vs explicit null
    expire_val = body.expire if "expire" in body.model_fields_set else ...
    updated = await service.update_chain_buy(
        session,
        caller=caller,
        order=order,
        qty=body.qty,
        price=body.price,
        sell_disc=body.sell_disc,
        expire=expire_val,  # type: ignore[arg-type]
        store_name=body.store_name,
        tips=body.tips,
        governorate=body.governorate,
        district=body.district,
        country=body.country,
        pharmacist_tel=body.pharmacist_tel,
        requester_tel=body.requester_tel,
        status=body.status,
    )
    return service.public_chain_buy(updated)


@router.post("/{order_id}/cancel")
async def cancel_chain_buy(
    order_id: int,
    caller: User = Depends(MANAGE),
    session: AsyncSession = Depends(get_session),
):
    order = await service.get_chain_buy(session, order_id)
    cancelled = await service.cancel_chain_buy(session, caller=caller, order=order)
    return service.public_chain_buy(cancelled)
