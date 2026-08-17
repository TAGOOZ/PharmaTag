"""Drug-master read endpoints (ticket #6 / S0.3).

Authenticated GET /api/v1/drugs returns the branch drug master: the branch
resolves from the bearer token's user (admin → MAIN, branch 1), and the drug
catalog is the active global drug set visible to that branch. A read — no
audit/outbox rows (money/stock mutations only).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_session
from app.drugs.service import list_branch_drugs
from app.models import Branch, Drug, User

router = APIRouter()


def _money(value) -> str:
    """Exact-decimal money as a 2-dp string (server owns money math, plan/02 O-1)."""
    if value is None:
        value = Decimal("0")
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


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
        "price_now": _money(drug.price_now),
        "tax_type": drug.tax_type,
        "vat": _money(drug.vat),
        "active": drug.active,
    }


@router.get("")
async def list_drugs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.branch_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "user has no branch assigned"
        )
    branch = await session.get(Branch, user.branch_id)
    drugs = await list_branch_drugs(session, user.branch_id)
    return {
        "branch": {
            "id": branch.id,
            "pharmacyid": branch.pharmacyid,
            "pharname": branch.pharname,
        },
        "drugs": [_public_drug(d) for d in drugs],
    }