"""Branch registry endpoints (ticket #31, S5.1).

Reads are open to any authenticated user (pickers/settings screens); writes
require the `branches.manage` permission (seeded to admin+manager, legacy
floor 7 — the same tier as day-close reopen). Main-device role changes add a
`require_level(7)` gate in the service.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_permission
from app.auth.dependencies import get_current_user
from app.core.db import get_session
from app.models import Branch, User
from app.branches import service

router = APIRouter()

MANAGE_BRANCHES = require_permission("branches.manage")


class CreateBranchRequest(BaseModel):
    pharmacyid: str = Field(min_length=1, max_length=15)
    mobile: str = Field(min_length=1, max_length=15)
    pharname: str = Field(default="", max_length=100)
    phar: str = Field(default="", max_length=15)
    adress: str = Field(default="", max_length=200)
    governorate: str = Field(default="", max_length=50)
    district: str = Field(default="", max_length=50)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: CreateBranchRequest,
    caller: User = Depends(MANAGE_BRANCHES),
    session: AsyncSession = Depends(get_session),
):
    branch = await service.create_branch(
        session,
        caller_id=caller.id,
        pharmacyid=body.pharmacyid,
        mobile=body.mobile,
        pharname=body.pharname,
        phar=body.phar,
        adress=body.adress,
        governorate=body.governorate,
        district=body.district,
    )
    return service.public_branch(branch)


@router.get("")
async def list_branches(
    active: Optional[bool] = None,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """`?active=true|false` filters for picker screens; omit for the full
    registry (admin/settings view)."""
    query = select(Branch).order_by(Branch.id)
    if active is not None:
        query = query.where(Branch.is_active.is_(active))
    result = await session.execute(query)
    return {"branches": [service.public_branch(b) for b in result.scalars().all()]}


class UpdateBranchRequest(BaseModel):
    pharname: Optional[str] = Field(default=None, max_length=100)
    phar: Optional[str] = Field(default=None, max_length=15)
    mobile: Optional[str] = Field(default=None, max_length=15)
    adress: Optional[str] = Field(default=None, max_length=200)
    governorate: Optional[str] = Field(default=None, max_length=50)
    district: Optional[str] = Field(default=None, max_length=50)


async def _get_or_404(session: AsyncSession, branch_id: int) -> Branch:
    branch = await service.get_branch(session, branch_id)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found")
    return branch


@router.patch("/{branch_id}")
async def update_branch(
    branch_id: int,
    body: UpdateBranchRequest,
    caller: User = Depends(MANAGE_BRANCHES),
    session: AsyncSession = Depends(get_session),
):
    branch = await _get_or_404(session, branch_id)
    branch = await service.update_branch(
        session,
        caller_id=caller.id,
        branch=branch,
        pharname=body.pharname,
        phar=body.phar,
        mobile=body.mobile,
        adress=body.adress,
        governorate=body.governorate,
        district=body.district,
    )
    return service.public_branch(branch)


@router.delete("/{branch_id}")
async def deactivate_branch(
    branch_id: int,
    caller: User = Depends(MANAGE_BRANCHES),
    session: AsyncSession = Depends(get_session),
):
    branch = await _get_or_404(session, branch_id)
    branch = await service.deactivate_branch(
        session, caller_id=caller.id, branch=branch
    )
    return service.public_branch(branch)


@router.post("/{branch_id}/promote")
async def promote_main(
    branch_id: int,
    caller: User = Depends(MANAGE_BRANCHES),
    session: AsyncSession = Depends(get_session),
):
    branch = await _get_or_404(session, branch_id)
    branch = await service.transfer_main(
        session, caller_id=caller.id,
        caller_level=caller.permission_level, target=branch
    )
    return service.public_branch(branch)


class AttachIdentityRequest(BaseModel):
    legacy_table: str = Field(min_length=1, max_length=50)
    legacy_column: str = Field(min_length=1, max_length=50)
    legacy_value: str = Field(min_length=1, max_length=100)


@router.post("/{branch_id}/identities", status_code=status.HTTP_201_CREATED)
async def attach_identity(
    branch_id: int,
    body: AttachIdentityRequest,
    caller: User = Depends(MANAGE_BRANCHES),
    session: AsyncSession = Depends(get_session),
):
    branch = await _get_or_404(session, branch_id)
    identity = await service.attach_identity(
        session,
        caller_id=caller.id,
        branch=branch,
        legacy_table=body.legacy_table,
        legacy_column=body.legacy_column,
        legacy_value=body.legacy_value,
    )
    return service.public_identity(identity)


@router.get("/{branch_id}/identities")
async def list_identities(
    branch_id: int,
    caller: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch = await _get_or_404(session, branch_id)
    identities = await service.list_identities(session, branch=branch)
    return {"identities": [service.public_identity(i) for i in identities]}


@router.delete(
    "/{branch_id}/identities/{legacy_table}/{legacy_column}/{legacy_value}"
)
async def detach_identity(
    branch_id: int,
    legacy_table: str,
    legacy_column: str,
    legacy_value: str,
    caller: User = Depends(MANAGE_BRANCHES),
    session: AsyncSession = Depends(get_session),
):
    # Note: legacy keys containing "/" cannot be addressed by this path-style
    # URL — legacy natural keys (pharmacyid/mobile) never contain one. Such a
    # mapping can only be removed at the DB/ETL layer.
    branch = await _get_or_404(session, branch_id)
    detached = await service.detach_identity(
        session,
        caller_id=caller.id,
        branch=branch,
        legacy_table=legacy_table,
        legacy_column=legacy_column,
        legacy_value=legacy_value,
    )
    # same convention as DELETE /branches/{id}: echo the removed row
    return service.public_identity(detached)
