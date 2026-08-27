"""Chain-buy use-cases (ticket #36, S5.6).

Legacy ChainBuyStore / ChainBuyUsers 12-col merged into `chain_buy_orders`
(plan/01 §3.6). Each order is a branch's bulk-buy request published to the
whole chain for discovery — no stock or GL moves, just a shared board.

Every mutation writes its audit row and one `entity='chain_buy_order'` outbox
row atomically (G12) so offline peers converge. chain-buy is non-money, but
the G12 pattern still applies (A08 logistics-core precedent).

Listing is global chain view: ALL branches' orders (no branch scoping), sorted
by `iddatetime DESC`, capped at 1000 with total count. Search `q` scans drug
names/generic/barcodes (S5.5 Q6 pattern). Branch/drug activity filters apply
unless `include_inactive`.

Numbering: no per-branch monotonic number — the `id` identity is the handle.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.core import money
from app.models import Branch, ChainBuyOrder, Drug, DrugBarcode, User

ENTITY = "chain_buy_order"
_LOCK_NAMESPACE = "pharmatag:branch-chain-buy"
_MAX_ROWS = 1000

ALLOWED_STATUSES = {"created", "in_transit", "delivered", "received", "cancelled"}

NOT_FOUND = HTTPException(http_status.HTTP_404_NOT_FOUND, "chain buy order not found")
NO_BRANCH = HTTPException(http_status.HTTP_400_BAD_REQUEST, "caller has no branch assigned")
UNKNOWN_DRUG = HTTPException(http_status.HTTP_404_NOT_FOUND, "drug not found")


def _is_sqlite(session: AsyncSession) -> bool:
    try:
        bind = session.get_bind()
    except Exception:
        return False
    return getattr(getattr(bind, "dialect", None), "name", "") == "sqlite"


async def acquire_branch_lock(session: AsyncSession, branch_id: int) -> None:
    if _is_sqlite(session):
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:ns), :branch_id)"),
        {"ns": _LOCK_NAMESPACE, "branch_id": branch_id},
    )


# ---------------------------------------------------------------------------
# validation helpers (S5.5 Q2 pattern)
# ---------------------------------------------------------------------------

def _str_field(value: Optional[str], max_len: int, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, f"invalid {field}")
    trimmed = value.strip()
    if len(trimmed) > max_len:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, f"{field} too long")
    return trimmed


def _dec_or_400(raw, field: str) -> Decimal:
    try:
        v = money.dec(raw)
    except (InvalidOperation, TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, f"invalid {field}") from exc
    # NaN / Infinity must be rejected before any comparison
    try:
        if v.is_nan() or v.is_infinite():
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, f"invalid {field}")
    except AttributeError:
        pass
    return v


def _validate_qty(raw) -> Decimal:
    v = _dec_or_400(raw, "qty")
    v = money.round4(v)
    if v <= 0:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "qty must be > 0")
    if v >= Decimal("100000000000000"):
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "qty overflow")
    return v


def _validate_price(raw) -> Decimal:
    if raw is None:
        raw = Decimal("0")
    v = _dec_or_400(raw, "price")
    v = money.round4(v)
    if v < 0:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "price must be >= 0")
    if v >= Decimal("100000000000000"):
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "price overflow")
    return v


def _validate_sell_disc(raw) -> Decimal:
    if raw is None:
        raw = Decimal("0")
    v = _dec_or_400(raw, "sell_disc")
    # reject NaN/Inf already done
    if v < 0 or v > Decimal("100"):
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "sell_disc must be 0-100")
    # canonical 2dp
    v = money.round2(v)
    return v


def _validate_expire(raw: Optional[date]) -> Optional[date]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "invalid expire")
    raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "invalid expire")


def _qty4(value) -> str:
    return format(money.round4(value), "f")


def _price4(value) -> str:
    return format(money.round4(value), "f")


def _disc_str(value) -> str:
    # sell_disc is (5,2) -> 2dp wire
    return format(money.round2(value), "f")


# ---------------------------------------------------------------------------
# public / snapshot
# ---------------------------------------------------------------------------

def public_chain_buy(order: ChainBuyOrder) -> dict:
    return {
        "id": order.id,
        "branch_id": order.branch_id,
        "drug_id": order.drug_id,
        "store_name": order.store_name or "",
        "pharmacist_tel": order.pharmacist_tel or "",
        "requester_tel": order.requester_tel or "",
        "qty": _qty4(order.qty),
        "price": _price4(order.price),
        "sell_disc": _disc_str(order.sell_disc),
        "expire": order.expire.isoformat() if order.expire else None,
        "tips": order.tips or "",
        "governorate": order.governorate or "",
        "district": order.district or "",
        "country": order.country or "",
        "iddatetime": order.iddatetime.isoformat() if order.iddatetime else None,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


def snapshot_payload(order: ChainBuyOrder) -> dict:
    return {
        "kind": ENTITY,
        "id": order.id,
        "branch_id": order.branch_id,
        "drug_id": order.drug_id,
        "store_name": order.store_name or "",
        "pharmacist_tel": order.pharmacist_tel or "",
        "requester_tel": order.requester_tel or "",
        "qty": _qty4(order.qty),
        "price": _price4(order.price),
        "sell_disc": _disc_str(order.sell_disc),
        "expire": order.expire.isoformat() if order.expire else None,
        "tips": order.tips or "",
        "governorate": order.governorate or "",
        "district": order.district or "",
        "country": order.country or "",
        "iddatetime": order.iddatetime.isoformat() if order.iddatetime else None,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

async def create_chain_buy(
    session: AsyncSession,
    *,
    caller: User,
    drug_id: int,
    qty,
    price=None,
    sell_disc=None,
    expire: Optional[date] = None,
    store_name: str = "",
    tips: str = "",
    governorate: str = "",
    district: str = "",
    country: str = "",
    pharmacist_tel: str = "",
    requester_tel: str = "",
) -> ChainBuyOrder:
    if caller.branch_id is None:
        raise NO_BRANCH

    # validate strings (trim + length)
    store_name_v = _str_field(store_name, 100, "store_name")
    pharmacist_tel_v = _str_field(pharmacist_tel, 15, "pharmacist_tel")
    requester_tel_v = _str_field(requester_tel, 15, "requester_tel")
    tips_v = _str_field(tips, 50, "tips")
    governorate_v = _str_field(governorate, 50, "governorate")
    district_v = _str_field(district, 50, "district")
    country_v = _str_field(country, 50, "country")

    qty_v = _validate_qty(qty)
    price_v = _validate_price(price if price is not None else Decimal("0"))
    sell_disc_v = _validate_sell_disc(sell_disc if sell_disc is not None else Decimal("0"))
    expire_v = _validate_expire(expire)

    drug = await session.get(Drug, int(drug_id))
    if drug is None:
        raise UNKNOWN_DRUG

    async with atomic(session):
        await acquire_branch_lock(session, caller.branch_id)
        now = datetime.now(timezone.utc)
        order = ChainBuyOrder(
            branch_id=caller.branch_id,
            drug_id=int(drug_id),
            store_name=store_name_v,
            pharmacist_tel=pharmacist_tel_v,
            requester_tel=requester_tel_v,
            qty=qty_v,
            price=price_v,
            sell_disc=sell_disc_v,
            expire=expire_v,
            tips=tips_v,
            governorate=governorate_v,
            district=district_v,
            country=country_v,
            iddatetime=now,
            status="created",
            created_at=now,
        )
        session.add(order)
        await session.flush()

        await audit(
            session,
            branch_id=order.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=order.id,
            field="",
            old_value="",
            new_value=str(drug_id),
            drug_id=int(drug_id),
            barcode="",
            action=ACTION_INSERT,
        )
        payload = snapshot_payload(order)
        await enqueue_sync(
            session,
            branch_id=order.branch_id,
            entity=ENTITY,
            entity_id=order.id,
            action=ACTION_INSERT,
            payload=payload,
            source_device_id=caller.branch_id,
        )
    return order


# ---------------------------------------------------------------------------
# get / list
# ---------------------------------------------------------------------------

async def get_chain_buy(session: AsyncSession, order_id: int) -> ChainBuyOrder:
    order = await session.get(ChainBuyOrder, int(order_id))
    if order is None:
        raise NOT_FOUND
    return order


async def list_chain_buy(
    session: AsyncSession,
    caller: User,
    *,
    drug_id: Optional[int] = None,
    q: Optional[str] = None,
    store_name: Optional[str] = None,
    governorate: Optional[str] = None,
    district: Optional[str] = None,
    status_filter: Optional[str] = None,
    include_inactive: bool = False,
) -> dict:
    where: list = []

    if not include_inactive:
        where.append(Branch.is_active.is_(True))
        where.append(Drug.active.is_(True))

    if drug_id is not None:
        try:
            did = int(drug_id)
        except (TypeError, ValueError):
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "invalid drug_id")
        where.append(ChainBuyOrder.drug_id == did)

    if status_filter is not None:
        if status_filter not in ALLOWED_STATUSES:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "invalid status filter")
        where.append(ChainBuyOrder.status == status_filter)

    if store_name is not None and store_name.strip():
        raw = store_name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{raw}%"
        where.append(ChainBuyOrder.store_name.ilike(like, escape="\\"))

    if governorate is not None and governorate.strip():
        raw = governorate.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{raw}%"
        where.append(ChainBuyOrder.governorate.ilike(like, escape="\\"))

    if district is not None and district.strip():
        raw = district.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{raw}%"
        where.append(ChainBuyOrder.district.ilike(like, escape="\\"))

    if q is not None and q.strip():
        raw = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{raw}%"
        barcode_ids = select(DrugBarcode.drug_id).where(DrugBarcode.barcode.ilike(like, escape="\\"))
        where.append(
            or_(
                Drug.drugname.ilike(like, escape="\\"),
                Drug.drugnamear.ilike(like, escape="\\"),
                Drug.generic.ilike(like, escape="\\"),
                Drug.id.in_(barcode_ids),
            )
        )

    # total count before truncation
    total = (
        await session.execute(
            select(func.count())
            .select_from(ChainBuyOrder)
            .join(Branch, Branch.id == ChainBuyOrder.branch_id)
            .join(Drug, Drug.id == ChainBuyOrder.drug_id)
            .where(*where)
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(ChainBuyOrder)
            .join(Branch, Branch.id == ChainBuyOrder.branch_id)
            .join(Drug, Drug.id == ChainBuyOrder.drug_id)
            .where(*where)
            .order_by(ChainBuyOrder.iddatetime.desc().nulls_last(), ChainBuyOrder.id.desc())
            .limit(_MAX_ROWS)
        )
    ).scalars().all()

    return {
        "count": int(total),
        "truncated": bool(total > _MAX_ROWS),
        "items": [public_chain_buy(o) for o in rows],
        # also expose raw orders for internal callers that need objects
        "_orders": list(rows),
    }


# ---------------------------------------------------------------------------
# update / cancel
# ---------------------------------------------------------------------------

async def update_chain_buy(
    session: AsyncSession,
    *,
    caller: User,
    order: ChainBuyOrder,
    qty=None,
    price=None,
    sell_disc=None,
    expire: Optional[date] | object = ...,
    store_name: Optional[str] = None,
    tips: Optional[str] = None,
    governorate: Optional[str] = None,
    district: Optional[str] = None,
    country: Optional[str] = None,
    pharmacist_tel: Optional[str] = None,
    requester_tel: Optional[str] = None,
    status: Optional[str] = None,
) -> ChainBuyOrder:
    if caller.branch_id is None:
        raise NO_BRANCH
    if int(caller.branch_id) != int(order.branch_id):
        raise HTTPException(http_status.HTTP_403_FORBIDDEN, "caller is not owner of this order")

    # validate supplied fields
    updates: dict = {}

    if qty is not None:
        updates["qty"] = _validate_qty(qty)
    if price is not None:
        updates["price"] = _validate_price(price)
    if sell_disc is not None:
        updates["sell_disc"] = _validate_sell_disc(sell_disc)
    if expire is not ...:
        updates["expire"] = _validate_expire(expire)  # type: ignore[arg-type]
    if store_name is not None:
        updates["store_name"] = _str_field(store_name, 100, "store_name")
    if tips is not None:
        updates["tips"] = _str_field(tips, 50, "tips")
    if governorate is not None:
        updates["governorate"] = _str_field(governorate, 50, "governorate")
    if district is not None:
        updates["district"] = _str_field(district, 50, "district")
    if country is not None:
        updates["country"] = _str_field(country, 50, "country")
    if pharmacist_tel is not None:
        updates["pharmacist_tel"] = _str_field(pharmacist_tel, 15, "pharmacist_tel")
    if requester_tel is not None:
        updates["requester_tel"] = _str_field(requester_tel, 15, "requester_tel")
    if status is not None:
        if status not in ALLOWED_STATUSES:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "invalid status")
        # cancel is dedicated; prevent creating cancelled via generic patch
        # but allow other lifecycle steps (in_transit/delivered/received)
        if status == "cancelled":
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "use cancel endpoint for cancellation")
        updates["status"] = status

    if not updates:
        return order

    async with atomic(session):
        await acquire_branch_lock(session, caller.branch_id)
        # re-read under lock for concurrency safety
        fresh = await session.get(ChainBuyOrder, order.id)
        if fresh is None:
            raise NOT_FOUND
        if fresh.status == "cancelled":
            raise HTTPException(http_status.HTTP_409_CONFLICT, "order is cancelled")
        old_status = fresh.status
        for k, v in updates.items():
            setattr(fresh, k, v)
        fresh.updated_at = datetime.now(timezone.utc)
        session.add(fresh)
        await session.flush()

        await audit(
            session,
            branch_id=fresh.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=fresh.id,
            field="",
            old_value=old_status,
            new_value=fresh.status,
            drug_id=fresh.drug_id,
            barcode="",
            action=ACTION_UPDATE,
        )
        payload = snapshot_payload(fresh)
        await enqueue_sync(
            session,
            branch_id=fresh.branch_id,
            entity=ENTITY,
            entity_id=fresh.id,
            action=ACTION_UPDATE,
            payload=payload,
            source_device_id=caller.branch_id,
        )
        return fresh


async def cancel_chain_buy(
    session: AsyncSession,
    *,
    caller: User,
    order: ChainBuyOrder,
) -> ChainBuyOrder:
    if caller.branch_id is None:
        raise NO_BRANCH
    if int(caller.branch_id) != int(order.branch_id):
        raise HTTPException(http_status.HTTP_403_FORBIDDEN, "caller is not owner of this order")
    if order.status == "cancelled":
        raise HTTPException(http_status.HTTP_409_CONFLICT, "order already cancelled")

    async with atomic(session):
        await acquire_branch_lock(session, caller.branch_id)
        fresh = (
            await session.execute(
                select(ChainBuyOrder)
                .where(ChainBuyOrder.id == order.id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if fresh is None:
            raise NOT_FOUND
        if fresh.status == "cancelled":
            raise HTTPException(http_status.HTTP_409_CONFLICT, "order already cancelled")
        old = fresh.status
        fresh.status = "cancelled"
        fresh.updated_at = datetime.now(timezone.utc)
        session.add(fresh)
        await session.flush()

        await audit(
            session,
            branch_id=fresh.branch_id,
            user_id=caller.id,
            entity=ENTITY,
            entity_id=fresh.id,
            field="status",
            old_value=old,
            new_value=fresh.status,
            drug_id=fresh.drug_id,
            barcode="",
            action=ACTION_UPDATE,
        )
        payload = snapshot_payload(fresh)
        await enqueue_sync(
            session,
            branch_id=fresh.branch_id,
            entity=ENTITY,
            entity_id=fresh.id,
            action=ACTION_UPDATE,
            payload=payload,
            source_device_id=caller.branch_id,
        )
        return fresh
