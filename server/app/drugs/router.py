"""Drug-master endpoints (ticket #8 / S1.2).

Reads (GET list, GET by id, search) are open to any authenticated user — as #6
did. Writes (POST / PATCH / import) are gated by `drugs.manage` (legacy level-3
area الأصناف والمخزون, plan/02 §3; admin role covers it). Prices are exact
decimal strings (plan/02 §2 — money never leaves as a float).
"""
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core import money
from app.core.db import get_session
from app.drugs import importer, service
from app.models import Branch, Drug, User

router = APIRouter()

MANAGE_DRUGS = require_permission("drugs.manage")


def _money(value) -> str:
    """Exact-decimal money as a 2-dp string (half-up — plan/01 §4.1)."""
    return money.format2(value)


def _public_drug(drug: Drug) -> dict:
    return {
        "id": drug.id,
        "drugname": drug.drugname,
        "drugnamear": drug.drugnamear,
        "generic": drug.generic or "",
        "classy": drug.classy or "",
        "co": drug.co or "",
        "units": drug.units,
        "unitsmall": drug.unitsmall,
        "price": _money(drug.price),
        "price_wholesale": _money(drug.price_wholesale),
        "price_cost": _money(drug.price_cost),
        "price_now": _money(drug.price_now),
        "tax_type": drug.tax_type,
        "vat": _money(drug.vat),
        "barcodes": [b.barcode for b in sorted(drug.barcodes, key=lambda b: not b.is_primary)],
        "active": drug.active,
    }


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


class DrugCreateRequest(BaseModel):
    drugname: str = Field(min_length=1, max_length=100)
    drugnamear: str = Field(default="", max_length=100)
    generic: Optional[str] = Field(default=None, max_length=120)
    classy: Optional[str] = Field(default=None, max_length=35)
    pharmacology: Optional[str] = Field(default=None, max_length=200)
    co: Optional[str] = Field(default=None, max_length=100)
    unitsclass: Optional[str] = Field(default=None, max_length=50)
    tax_type: Literal["exempt", "5%", "14%"] = "exempt"
    units: int = Field(default=0, ge=0)
    unitsmall: int = Field(default=0, ge=0)
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    price_wholesale: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    price_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    price_now: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    barcodes: list[str] = Field(default_factory=list, max_length=6)
    active: bool = True


class DrugUpdateRequest(BaseModel):
    drugname: Optional[str] = Field(default=None, min_length=1, max_length=100)
    drugnamear: Optional[str] = Field(default=None, max_length=100)
    generic: Optional[str] = Field(default=None, max_length=120)
    classy: Optional[str] = Field(default=None, max_length=35)
    pharmacology: Optional[str] = Field(default=None, max_length=200)
    co: Optional[str] = Field(default=None, max_length=100)
    unitsclass: Optional[str] = Field(default=None, max_length=50)
    tax_type: Optional[Literal["exempt", "5%", "14%"]] = None
    units: Optional[int] = Field(default=None, ge=0)
    unitsmall: Optional[int] = Field(default=None, ge=0)
    price: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    price_wholesale: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    price_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    price_now: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    barcodes: Optional[list[str]] = Field(default=None, max_length=6)
    active: Optional[bool] = None


@router.get("")
async def list_drugs(
    limit: int = 200,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if limit < 0 or offset < 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "limit and offset must be non-negative"
        )
    limit = min(limit, 500)  # cap: the CC0 catalog can reach 24k+ rows
    branch_id = _caller_branch_id(user)
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found for user")
    if not branch.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "branch is inactive")
    drugs = await service.list_branch_drugs(
        session, branch_id, limit=limit, offset=offset
    )
    return {
        "branch": {
            "id": branch.id,
            "pharmacyid": branch.pharmacyid,
            "pharname": branch.pharname,
        },
        "drugs": [_public_drug(d) for d in drugs],
    }


@router.get("/search")
async def search_drugs(
    q: str = "",
    limit: int = 25,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Search-as-you-type: active drugs by name AR/EN (ILIKE) or barcode prefix."""
    limit = max(1, min(limit, 200))
    drugs = await service.search_drugs(session, q, limit=limit)
    return {"query": q, "drugs": [_public_drug(d) for d in drugs]}


async def _get_or_404(session: AsyncSession, drug_id: int) -> Drug:
    drug = await service.get_drug(session, drug_id)
    if drug is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "drug not found")
    return drug


@router.get("/{drug_id}")
async def get_drug(
    drug_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    drug = await _get_or_404(session, drug_id)
    return _public_drug(drug)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_drug(
    body: DrugCreateRequest,
    caller: User = Depends(MANAGE_DRUGS),
    session: AsyncSession = Depends(get_session),
):
    branch_id = _caller_branch_id(caller)
    drug = await service.create_drug(
        session,
        caller=caller,
        branch_id=branch_id,
        drugname=body.drugname,
        drugnamear=body.drugnamear,
        generic=body.generic or "",
        classy=body.classy or "",
        pharmacology=body.pharmacology or "",
        co=body.co or "",
        unitsclass=body.unitsclass or "",
        tax_type=body.tax_type,
        units=body.units,
        unitsmall=body.unitsmall,
        price=body.price,
        price_wholesale=body.price_wholesale,
        price_cost=body.price_cost,
        price_now=body.price_now,
        barcodes=body.barcodes,
        active=body.active,
    )
    return _public_drug(drug)


@router.patch("/{drug_id}")
async def update_drug(
    drug_id: int,
    body: DrugUpdateRequest,
    caller: User = Depends(MANAGE_DRUGS),
    session: AsyncSession = Depends(get_session),
):
    branch_id = _caller_branch_id(caller)
    drug = await _get_or_404(session, drug_id)
    drug = await service.update_drug(
        session,
        caller=caller,
        branch_id=branch_id,
        drug=drug,
        drugname=body.drugname,
        drugnamear=body.drugnamear,
        generic=body.generic,
        classy=body.classy,
        pharmacology=body.pharmacology,
        co=body.co,
        unitsclass=body.unitsclass,
        tax_type=body.tax_type,
        units=body.units,
        unitsmall=body.unitsmall,
        price=body.price,
        price_wholesale=body.price_wholesale,
        price_cost=body.price_cost,
        price_now=body.price_now,
        barcodes=body.barcodes,
        active=body.active,
    )
    return _public_drug(drug)


@router.post("/import")
async def import_catalog(
    csv_text: str = Body(..., media_type="text/csv"),
    caller: User = Depends(MANAGE_DRUGS),
    session: AsyncSession = Depends(get_session),
):
    """CC0 catalog import (G03): idempotent, de-dupes against the master."""
    branch_id = _caller_branch_id(caller)
    try:
        report = await importer.import_catalog_csv(
            session, caller=caller, branch_id=branch_id, csv_text=csv_text
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {
        "inserted": report.inserted,
        "skipped_duplicate_barcode": report.skipped_duplicate_barcode,
        "skipped_duplicate_name": report.skipped_duplicate_name,
        "skipped_malformed": report.skipped_malformed,
        "errors": report.errors,
        "inserted_names": report.inserted_names,
    }