"""Parties endpoints — the supplier seam for S1.4 (ticket #10).

A purchase needs a supplier party; this router provides the minimal
create/list surface (legacy area '4' العملاء والموردين, plan/02 §3 → gate
`require_level(4)`). Party rows are branch-scoped: a caller only ever creates
or lists within their own branch, so a cross-branch supplier is invisible and
a purchase against it 404s. Each create writes its audit row (G12).
"""
from __future__ import annotations

import secrets
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level
from app.core.audit import ACTION_INSERT, audit
from app.core.db import atomic, get_session
from app.models import Party, User

router = APIRouter()

PARTY_WRITE = require_level(4)


class PartyCreate(BaseModel):
    kind: Literal["customer", "supplier", "both"] = "supplier"
    namee: str = Field(min_length=1, max_length=100)
    name_ar: Optional[str] = Field(default=None, max_length=100)
    mobile: Optional[str] = Field(default=None, max_length=15)
    adress: Optional[str] = Field(default=None, max_length=200)
    governorate: Optional[str] = Field(default=None, max_length=50)
    district: Optional[str] = Field(default=None, max_length=50)
    credit_limit: Optional[object] = Field(default=None, ge=0, max_digits=18, decimal_places=2)


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


def _serialize(p: Party) -> dict:
    return {
        "id": p.id,
        "branch_id": p.branch_id,
        "kind": p.kind,
        "typee": p.typee or "",
        "namee": p.namee,
        "name_ar": p.name_ar or "",
        "mobile": p.mobile or "",
        "adress": p.adress or "",
        "governorate": p.governorate or "",
        "district": p.district or "",
        "credit_limit": str(p.credit_limit or 0),
        "active": bool(p.active),
    }


@router.get("")
async def list_parties(
    kind: Optional[Literal["customer", "supplier", "both"]] = None,
    search: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Parties for the caller's branch, optionally filtered by kind/name."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(Party).where(Party.branch_id == branch_id, Party.active.is_(True))
    if kind is not None:
        q = q.where(Party.kind == kind)
    if search:
        like = f"%{search}%"
        q = q.where(Party.namee.ilike(like) | Party.name_ar.ilike(like))
    q = q.order_by(Party.namee).limit(limit)
    parties = (await session.execute(q)).scalars().all()
    return {"parties": [_serialize(p) for p in parties]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_party(
    body: PartyCreate,
    caller: User = Depends(PARTY_WRITE),
    session: AsyncSession = Depends(get_session),
):
    """Create a party (supplier/customer/both) in the caller's branch."""
    branch_id = _caller_branch_id(caller)
    party = Party(
        branch_id=branch_id,
        kind=body.kind,
        typee="supplier" if body.kind == "supplier" else "",
        namee=body.namee,
        name_ar=body.name_ar,
        mobile=body.mobile,
        adress=body.adress,
        governorate=body.governorate,
        district=body.district,
        credit_limit=body.credit_limit or 0,
        randomid=f"pty-{secrets.token_hex(6)}",
        active=True,
    )
    session.add(party)
    async with atomic(session):
        await session.flush()
        await audit(
            session,
            branch_id=branch_id,
            user_id=caller.id,
            entity="parties",
            entity_id=party.id,
            action=ACTION_INSERT,
            new_value=f"kind={party.kind} name={party.namee}",
            typevalue=party.namee,
        )
    return _serialize(party)
