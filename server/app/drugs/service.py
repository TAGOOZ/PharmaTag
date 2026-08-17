"""Drug-master service (ticket #8 / S1.2).

CRUD + search-as-you-type + CC0 catalog import over the global drug master
(wzdrugs). Reads are branch-scoped at the router seam only when the branch read
(#6) needs it; drugs themselves are global. Writes follow the AGENTS.md
discipline:
  * every mutation writes its `audit_log` row in the same transaction
    (plan/01 §5.4, G12) — one audit row per changed field, plus the legacy
    TitanUserAction shape (drug_id, barcode, action);
  * price changes additionally append a `price_change_log` row (storediscount
    lineage, plan/02 §4.6) in that same transaction;
  * duplicate drugname / duplicate barcode surface as 409 (partial-unique
    indexes in rev 001, plan/01 §1.3#4);
  * price levels are exact decimal, never negative (plan/01 §4.1), and float
    input is rejected (A05).
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import money
from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit
from app.models import Drug, DrugBarcode, PriceChangeLog, User

MAX_BARCODES = 6
TAX_TYPES = ("exempt", "5%", "14%")

_DUP_NAME = HTTPException(status.HTTP_409_CONFLICT, "drugname already exists")
_DUP_BARCODE = HTTPException(status.HTTP_409_CONFLICT, "barcode already in use")


def validate_price_levels(price, price_wholesale, price_cost) -> None:
    """Reject negative price levels; float input raises TypeError (money is
    exact decimal — A05, plan/00 G06)."""
    for label, value in (
        ("price", price),
        ("price_wholesale", price_wholesale),
        ("price_cost", price_cost),
    ):
        v = money.dec(value)
        if v < 0:
            raise ValueError(f"{label} must be >= 0")


def default_price_now(price_now, price) -> money.Decimal:
    """The legacy 'current price' tracks the public price unless explicitly set."""
    return money.dec(price) if price_now is None else money.dec(price_now)


def _clean_barcodes(barcodes: Optional[list[str]]) -> list[str]:
    """Strip/drop empty barcodes and enforce the ≤6 cap (wzdrugs barcode+5)."""
    if not barcodes:
        return []
    cleaned = [str(b).strip() for b in barcodes if str(b).strip()]
    if len(cleaned) > MAX_BARCODES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"a drug can have at most {MAX_BARCODES} barcodes",
        )
    return cleaned


async def _check_barcode_conflicts(
    session: AsyncSession, barcodes: list[str], *, exclude_drug_id: Optional[int] = None
) -> None:
    """409 when any barcode is already bound to another drug."""
    if not barcodes:
        return
    stmt = select(DrugBarcode).where(DrugBarcode.barcode.in_(barcodes))
    if exclude_drug_id is not None:
        stmt = stmt.where(DrugBarcode.drug_id != exclude_drug_id)
    rows = (await session.execute(stmt)).scalars().all()
    if rows:
        raise _DUP_BARCODE


async def _log_price_change(
    session: AsyncSession, *, branch_id: int, drug: Drug, changed_by: int
) -> None:
    """One price_change_log row (storediscount lineage) for the drug's prices."""
    session.add(
        PriceChangeLog(
            branch_id=branch_id,
            drug_id=drug.id,
            price=money.dec(drug.price or 0),
            disco=money.dec(drug.disco or 0),
            units=drug.units or 0,
            changed_by=changed_by,
        )
    )
    await session.flush()


async def _audit_field(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: int,
    drug: Drug,
    field: str,
    old_value: str,
    new_value: str,
    action: str,
) -> None:
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="drug",
        entity_id=drug.id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        drug_id=drug.id,
        action=action,
    )


def _barcodes_str(drug: Drug) -> str:
    return ",".join(b.barcode for b in sorted(drug.barcodes, key=lambda b: not b.is_primary))


async def _replace_barcodes(
    session: AsyncSession, drug: Drug, barcodes: list[str]
) -> None:
    """Replace a drug's barcodes through the in-memory collection (delete-orphan).

    The collection is loaded asynchronously first (`session.refresh`) so the
    later clear/append never triggers a sync lazy-load (MissingGreenlet) and
    the delete-orphan cascade removes old rows cleanly. Reads elsewhere use
    selectinload (`get_drug`).
    """
    await session.refresh(drug, ["barcodes"])
    drug.barcodes.clear()
    for i, barcode in enumerate(barcodes):
        drug.barcodes.append(
            DrugBarcode(barcode=barcode, is_primary=(i == 0))
        )
    await session.flush()


async def create_drug(
    session: AsyncSession,
    *,
    caller: User,
    branch_id: int,
    drugname: str,
    drugnamear: str,
    generic: str,
    classy: str,
    pharmacology: str,
    co: str,
    unitsclass: str,
    tax_type: str,
    units: int,
    unitsmall: int,
    price,
    price_wholesale,
    price_cost,
    price_now,
    barcodes: list[str],
    active: bool,
    localimport: int = 0,
) -> Drug:
    drugname = (drugname or "").strip()
    if not drugname:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "drugname is required")
    validate_price_levels(price, price_wholesale, price_cost)
    barcodes = _clean_barcodes(barcodes)
    existing = await session.execute(select(Drug).where(Drug.drugname == drugname))
    if existing.scalar_one_or_none() is not None:
        raise _DUP_NAME
    await _check_barcode_conflicts(session, barcodes)
    drug = Drug(
        drugname=drugname,
        drugnamear=drugnamear or "",
        generic=generic or "",
        classy=classy or "",
        pharmacology=pharmacology or "",
        co=co or "",
        unitsclass=unitsclass or "",
        tax_type=tax_type,
        units=units or 0,
        unitsmall=unitsmall or 0,
        price=money.dec(price),
        price_wholesale=money.dec(price_wholesale),
        price_cost=money.dec(price_cost),
        price_now=default_price_now(price_now, price),
        active=active,
        localimport=localimport,
    )
    session.add(drug)
    try:
        await session.flush()
        await _replace_barcodes(session, drug, barcodes)
        await _audit_field(
            session,
            branch_id=branch_id,
            user_id=caller.id,
            drug=drug,
            field="drugname",
            old_value="",
            new_value=drug.drugname,
            action=ACTION_INSERT,
        )
        await _log_price_change(session, branch_id=branch_id, drug=drug, changed_by=caller.id)
        drug_id = drug.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _DUP_NAME from exc
    return await get_drug(session, drug_id)


async def get_drug(session: AsyncSession, drug_id: int) -> Optional[Drug]:
    result = await session.execute(
        select(Drug)
        .where(Drug.id == drug_id)
        .options(selectinload(Drug.barcodes))
    )
    return result.scalar_one_or_none()


async def list_branch_drugs(
    session: AsyncSession, branch_id: int, *, limit: int = 200, offset: int = 0
) -> list[Drug]:
    """Active drug catalog visible to `branch_id` (global drugs, active only),
    paginated so a 24k+ row catalog never comes back in one response."""
    result = await session.execute(
        select(Drug)
        .where(Drug.active.is_(True))
        .order_by(Drug.drugname, Drug.id)
        .offset(offset)
        .limit(limit)
        .options(selectinload(Drug.barcodes))
    )
    return list(result.scalars().all())


async def update_drug(
    session: AsyncSession,
    *,
    caller: User,
    branch_id: int,
    drug: Drug,
    drugname: Optional[str],
    drugnamear: Optional[str],
    generic: Optional[str],
    classy: Optional[str],
    pharmacology: Optional[str],
    co: Optional[str],
    unitsclass: Optional[str],
    tax_type: Optional[str],
    units: Optional[int],
    unitsmall: Optional[int],
    price,
    price_wholesale,
    price_cost,
    price_now,
    barcodes: Optional[list[str]],
    active: Optional[bool],
) -> Drug:
    price_touched = any(
        v is not None
        for v in (price, price_wholesale, price_cost, price_now)
    )
    if price_touched:
        validate_price_levels(
            price if price is not None else (drug.price or 0),
            price_wholesale if price_wholesale is not None else (drug.price_wholesale or 0),
            price_cost if price_cost is not None else (drug.price_cost or 0),
        )
    if barcodes is not None:
        barcodes = _clean_barcodes(barcodes)
        await _check_barcode_conflicts(session, barcodes, exclude_drug_id=drug.id)

    scalar_changes = []
    if drugname is not None:
        drugname = drugname.strip()
        if not drugname:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "drugname is required")
        if drugname != drug.drugname:
            existing = await session.execute(
                select(Drug).where(Drug.drugname == drugname, Drug.id != drug.id)
            )
            if existing.scalar_one_or_none() is not None:
                raise _DUP_NAME
            scalar_changes.append(("drugname", drug.drugname, drugname))
            drug.drugname = drugname
    for attr, value in (
        ("drugnamear", drugnamear),
        ("generic", generic),
        ("classy", classy),
        ("pharmacology", pharmacology),
        ("co", co),
        ("unitsclass", unitsclass),
    ):
        if value is not None and value != getattr(drug, attr):
            scalar_changes.append((attr, getattr(drug, attr) or "", value))
            setattr(drug, attr, value)
    if tax_type is not None and tax_type != drug.tax_type:
        scalar_changes.append(("tax_type", drug.tax_type, tax_type))
        drug.tax_type = tax_type
    if units is not None and units != drug.units:
        scalar_changes.append(("units", str(drug.units), str(units)))
        drug.units = units
    if unitsmall is not None and unitsmall != drug.unitsmall:
        scalar_changes.append(("unitsmall", str(drug.unitsmall), str(unitsmall)))
        drug.unitsmall = unitsmall

    price_changes = []
    for attr, value in (
        ("price", price),
        ("price_wholesale", price_wholesale),
        ("price_cost", price_cost),
    ):
        if value is None:
            continue
        dec = money.dec(value)
        if dec != money.dec(getattr(drug, attr) or 0):
            price_changes.append((attr, getattr(drug, attr) or 0, dec))
            setattr(drug, attr, dec)
    if price_now is not None:
        dec_now = money.dec(price_now)
        if dec_now != money.dec(drug.price_now or 0):
            price_changes.append(("price_now", drug.price_now or 0, dec_now))
            drug.price_now = dec_now
    if active is not None and active != drug.active:
        scalar_changes.append(("active", str(drug.active), str(active)))
        drug.active = active

    if barcodes is not None:
        current = _barcodes_str(drug)
        await _replace_barcodes(session, drug, barcodes)
        new_str = ",".join(barcodes)
        if current != new_str:
            scalar_changes.append(("barcodes", current, new_str))

    session.add(drug)
    try:
        await session.flush()
        for field, old, new in scalar_changes:
            await _audit_field(
                session,
                branch_id=branch_id,
                user_id=caller.id,
                drug=drug,
                field=field,
                old_value=str(old),
                new_value=str(new),
                action=ACTION_UPDATE,
            )
        if price_changes:
            await _log_price_change(session, branch_id=branch_id, drug=drug, changed_by=caller.id)
        drug_id = drug.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _DUP_NAME from exc
    return await get_drug(session, drug_id)


async def search_drugs(session: AsyncSession, q: str, limit: int = 25) -> list[Drug]:
    """Search-as-you-type over active drugs: name AR/EN (ILIKE) or barcode prefix.

    Empty query returns [] (the caller's list endpoints serve the full catalog);
    no matches returns []. ILIKE wildcards in user input are escaped so `%`/`_`
    are matched literally.
    """
    q = (q or "").strip()
    if not q:
        return []
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like_pattern = f"%{escaped}%"
    barcode_ids = select(DrugBarcode.drug_id).where(
        DrugBarcode.barcode.like(f"{escaped}%", escape="\\")
    )
    result = await session.execute(
        select(Drug)
        .where(Drug.active.is_(True))
        .where(
            or_(
                Drug.drugname.ilike(like_pattern, escape="\\"),
                Drug.drugnamear.ilike(like_pattern, escape="\\"),
                Drug.id.in_(barcode_ids),
            )
        )
        .order_by(Drug.drugname, Drug.id)
        .limit(limit)
        .options(selectinload(Drug.barcodes))
    )
    return list(result.scalars().all())