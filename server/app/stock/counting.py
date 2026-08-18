"""Stock-count use-cases (S1.7, ticket #13).

Two-phase approval flow (feature_stock_counting §2.4, plan/02 §4.4):

* `submit_count_request` — a staff user records the physical counted qty; the
  server derives the signed delta vs the system balance and stores a `pending`
  `stock_correction_requests` row (with the `counted` snapshot). No stock is
  touched yet. One pending request per (branch, drug) — two undecided deltas
  would compound.
* `approve_count_request` — a manager (perm >= 7) applies the delta atomically
  (G12): batches + branch_stock, audit (`count`/`correction`), sync outbox,
  a balanced `correction` journal re-booking inventory value, and a
  `price_change_log` row capturing the corrected units at unit cost. The
  journal is valued at the cost of the units ACTUALLY moved (FIFO take x cost,
  or the target batch's cost), never at a book average, so account 1200 always
  equals the inventory ledger.
* `reject_count_request` — a manager marks the request rejected; stock
  untouched. Locked FOR UPDATE under the branch advisory lock so it can never
  race an approval.

The delta is applied only while still valid: the stored `counted` snapshot
means approval re-checks `balance_now + delta == counted` (a deficit can never
take more than exists, an overage can never overshoot the observed qty — the
request goes stale if stock moved meanwhile, feature §2.4 'cannot accept after
change'). A batch_id-scoped request may never drive that batch below zero.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.audit import audit, enqueue_sync
from app.core.db import atomic
from app.core.time import business_date
from app.money.journal import post_journal
from app.models import (
    BranchStock,
    Drug,
    DrugBarcode,
    PriceChangeLog,
    StockBatch,
    StockCorrectionRequest,
)
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

REQUEST_ENTITY = "stock_correction_requests"
STOCK_ENTITY = "branch_stock"
BATCH_ENTITY = "stock_batches"

NOT_PENDING = HTTPException(status.HTTP_409_CONFLICT, "request is not pending")
STALE_REQUEST = HTTPException(
    status.HTTP_409_CONFLICT,
    "stock balance changed since the request was submitted",
)
BATCH_NOT_FOUND = HTTPException(
    status.HTTP_400_BAD_REQUEST, "batch does not belong to this drug/branch"
)
NO_COST = HTTPException(
    status.HTTP_409_CONFLICT,
    "no stock cost to value the correction (enter the pharmacy's balances "
    "as purchase invoices first)",
)


async def _system_qty(session: AsyncSession, branch_id: int, drug_id: int) -> Decimal:
    row = (
        await session.execute(
            select(BranchStock.qty).where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
        )
    ).scalar_one_or_none()
    return money.dec(row) if row is not None else Decimal("0")


async def _primary_barcode(session: AsyncSession, drug_id: int) -> str:
    row = (
        await session.execute(
            select(DrugBarcode).where(
                DrugBarcode.drug_id == drug_id,
                DrugBarcode.is_primary.is_(True),
            )
        )
    ).scalars().first()
    return row.barcode if row else ""


async def submit_count_request(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    counted,
    reason: str = "",
    batch_id: Optional[int] = None,
) -> StockCorrectionRequest:
    """Record a pending correction request; derives delta = counted - system."""
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        drug = await session.get(Drug, drug_id)
        if drug is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "drug not found")
        if not drug.active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "drug is inactive")

        counted = money.dec(counted)
        if counted < 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "counted qty must be >= 0"
            )

        if batch_id is not None:
            batch = await session.get(StockBatch, batch_id)
            if (
                batch is None
                or batch.branch_id != branch_id
                or batch.drug_id != drug_id
            ):
                raise BATCH_NOT_FOUND

        # one pending request per (branch, drug) — two undecided deltas would
        # compound and neither final balance would match its counted qty
        pending = (
            await session.execute(
                select(StockCorrectionRequest.id)
                .where(
                    StockCorrectionRequest.branch_id == branch_id,
                    StockCorrectionRequest.drug_id == drug_id,
                    StockCorrectionRequest.status == "pending",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if pending is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "a count request is already pending for this drug",
            )

        system = await _system_qty(session, branch_id, drug_id)
        delta = money.round4(counted - system)
        if delta == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "counted qty matches the system balance; nothing to correct",
            )

        request = StockCorrectionRequest(
            branch_id=branch_id,
            drug_id=drug_id,
            batch_id=batch_id,
            delta=delta,
            counted=counted,
            reason=reason or "",
            requested_by=user_id,
            status="pending",
        )
        session.add(request)
        await session.flush()
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=REQUEST_ENTITY,
            entity_id=request.id,
            field="status",
            old_value="",
            new_value="pending",
            drug_id=drug_id,
            action="count",
        )
        return request


async def _weighted_avg_cost(
    session: AsyncSession,
    branch_id: int,
    drug_id: int,
    fallback_cost=None,
) -> tuple[Decimal, bool]:
    """Weighted-average unit cost across the drug's positive batches, locked.

    Returns `(cost, has_positive_batches)`. With no positive-qty batch it falls
    back to the drug master's cost price (feature §2.3 — opening at cost excl.
    VAT); `has_positive_batches=False` lets the caller refuse a correction that
    has NO cost basis at all (no batches AND no master cost).
    """
    rows = (
        await session.execute(
            select(StockBatch)
            .where(
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == drug_id,
                StockBatch.qty > 0,
            )
            .with_for_update()
        )
    ).scalars().all()
    total_qty = sum((money.dec(b.qty) for b in rows), Decimal("0"))
    if total_qty == 0:
        cost = money.round4(money.dec(fallback_cost) if fallback_cost is not None else 0)
        return cost, False
    total_value = sum((money.dec(b.qty) * money.dec(b.cost) for b in rows), Decimal("0"))
    return money.round4(total_value / total_qty), True


async def _audit_batch(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    batch: StockBatch,
    old,
    new,
    drug_id: int,
    barcode: str,
    request_id: int,
) -> None:
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity=BATCH_ENTITY,
        entity_id=batch.id,
        field="qty",
        old_value=str(old),
        new_value=str(new),
        drug_id=drug_id,
        barcode=barcode,
        action="correction",
        typevalue=f"count#{request_id}",
    )


async def _apply_deficit(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    request: StockCorrectionRequest,
    deficit: Decimal,
    barcode: str,
) -> Decimal:
    """Decrement batches FIFO by expiry until `deficit` is met (plan/02 §4.1);
    returns the total COST VALUE of the units actually removed."""
    batches = (
        await session.execute(
            select(StockBatch)
            .where(
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == request.drug_id,
                StockBatch.qty > 0,
            )
            .order_by(StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id)
            .with_for_update()
        )
    ).scalars().all()

    remaining = deficit
    moved_value = Decimal("0")
    for batch in batches:
        if remaining <= 0:
            break
        take = min(money.dec(batch.qty), remaining)
        old = money.dec(batch.qty)
        new = old - take
        batch.qty = new
        batch.oldstock = old
        session.add(batch)
        await _audit_batch(
            session,
            branch_id=branch_id,
            user_id=user_id,
            batch=batch,
            old=old,
            new=new,
            drug_id=request.drug_id,
            barcode=barcode,
            request_id=request.id,
        )
        moved_value += take * money.dec(batch.cost)
        remaining -= take
    if remaining > 0:
        raise STALE_REQUEST
    return moved_value


async def _apply_overage(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    request: StockCorrectionRequest,
    overage: Decimal,
    unit_cost: Decimal,
    barcode: str,
) -> StockBatch:
    """Create a NEW `correction` batch for the overage (feature §2.2: a wzgard
    correction row with a dedicated typee)."""
    batch = StockBatch(
        branch_id=branch_id,
        drug_id=request.drug_id,
        randomid=f"count-{request.id}",
        qty=overage,
        expire=None,
        cost=unit_cost,
        oldstock=Decimal("0"),
        typee="correction",
        created_by=user_id,
    )
    session.add(batch)
    await session.flush()
    await _audit_batch(
        session,
        branch_id=branch_id,
        user_id=user_id,
        batch=batch,
        old=Decimal("0"),
        new=overage,
        drug_id=request.drug_id,
        barcode=barcode,
        request_id=request.id,
    )
    return batch


async def _upsert_branch_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    qty_delta,
    barcode: str,
    typevalue: str,
) -> BranchStock:
    row = (
        await session.execute(
            select(BranchStock)
            .where(BranchStock.branch_id == branch_id, BranchStock.drug_id == drug_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = BranchStock(
            branch_id=branch_id, drug_id=drug_id, qty=Decimal("0"), minimum=Decimal("0")
        )
        session.add(row)
        await session.flush()
    old = money.dec(row.qty)
    new = old + money.dec(qty_delta)
    row.qty = new
    row.lastedit = datetime.now(timezone.utc)
    session.add(row)
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity=STOCK_ENTITY,
        entity_id=drug_id,
        field="qty",
        old_value=str(old),
        new_value=str(new),
        drug_id=drug_id,
        barcode=barcode,
        action="correction",
        typevalue=typevalue,
    )
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity=STOCK_ENTITY,
        entity_id=drug_id,
        action="correction",
        payload={"branch_id": branch_id, "drug_id": drug_id, "qty": str(new)},
    )
    return row


async def approve_count_request(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    request_id: int,
) -> StockCorrectionRequest:
    """Apply an approved correction atomically (G12) or reject it as stale."""
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        request = (
            await session.execute(
                select(StockCorrectionRequest)
                .where(StockCorrectionRequest.id == request_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if request is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
        if request.branch_id != branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
        if request.status != "pending":
            raise NOT_PENDING

        drug = await session.get(Drug, request.drug_id)
        if drug is None or not drug.active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "drug is missing or inactive"
            )

        barcode = await _primary_barcode(session, request.drug_id)
        delta = money.dec(request.delta)
        counted = money.dec(request.counted) if request.counted is not None else None

        if request.batch_id is not None:
            batch = (
                await session.execute(
                    select(StockBatch)
                    .where(StockBatch.id == request.batch_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if (
                batch is None
                or batch.branch_id != branch_id
                or batch.drug_id != request.drug_id
            ):
                raise BATCH_NOT_FOUND
            # staleness is judged on the drug TOTAL (the observed `counted` is
            # the drug's physical qty; the named batch absorbs the delta)
            system = await _system_qty(session, branch_id, request.drug_id)
            if counted is not None and system + delta != counted:
                raise STALE_REQUEST
            deficit = -delta if delta < 0 else Decimal("0")
            if deficit and money.dec(batch.qty) < deficit:
                raise STALE_REQUEST

            # batch-scoped: value at the TARGET batch's cost (the units really move)
            price = money.dec(batch.cost)
            value = money.round2(abs(delta) * price)
            if delta > 0:
                old = money.dec(batch.qty)
                batch.qty = old + delta
                batch.oldstock = old
                session.add(batch)
                await _audit_batch(
                    session,
                    branch_id=branch_id,
                    user_id=user_id,
                    batch=batch,
                    old=old,
                    new=batch.qty,
                    drug_id=request.drug_id,
                    barcode=barcode,
                    request_id=request.id,
                )
            else:
                old = money.dec(batch.qty)
                new = old - deficit
                batch.qty = new
                batch.oldstock = old
                session.add(batch)
                await _audit_batch(
                    session,
                    branch_id=branch_id,
                    user_id=user_id,
                    batch=batch,
                    old=old,
                    new=new,
                    drug_id=request.drug_id,
                    barcode=barcode,
                    request_id=request.id,
                )
        else:
            system = await _system_qty(session, branch_id, request.drug_id)
            if counted is not None and system + delta != counted:
                raise STALE_REQUEST
            if delta < 0 and system < -delta:
                raise STALE_REQUEST  # NULL-counted legacy rows still safe

            if delta > 0:
                unit_cost, has_positive = await _weighted_avg_cost(
                    session, branch_id, request.drug_id, fallback_cost=drug.price_cost
                )
                # a brand-new overage with NO cost basis (no batches and no
                # master cost) cannot be put on the books at any value
                if not has_positive and not money.dec(drug.price_cost):
                    raise NO_COST
                price = unit_cost
                value = money.round2(delta * unit_cost)
                await _apply_overage(
                    session,
                    branch_id=branch_id,
                    user_id=user_id,
                    request=request,
                    overage=delta,
                    unit_cost=unit_cost,
                    barcode=barcode,
                )
            else:
                deficit = -delta
                moved_value = await _apply_deficit(
                    session,
                    branch_id=branch_id,
                    user_id=user_id,
                    request=request,
                    deficit=deficit,
                    barcode=barcode,
                )
                # value by what actually LEFT inventory (Σ take x cost)
                value = money.round2(moved_value)
                price = money.round4(moved_value / deficit) if deficit else Decimal("0")

        await _upsert_branch_stock(
            session,
            branch_id=branch_id,
            user_id=user_id,
            drug_id=request.drug_id,
            qty_delta=delta,
            barcode=barcode,
            typevalue=f"count#{request.id}",
        )

        request.status = "approved"
        request.approved_by = user_id
        request.decided_at = datetime.now(timezone.utc)
        session.add(request)

        datee = business_date(request.decided_at)
        if value > 0:
            await _post_correction_journal(
                session,
                branch_id=branch_id,
                user_id=user_id,
                request=request,
                value=value,
                datee=datee,
            )
        await _log_price_change(
            session,
            branch_id=branch_id,
            user_id=user_id,
            request=request,
            unit_cost=price,
            barcode=barcode,
            datee=datee,
        )
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=REQUEST_ENTITY,
            entity_id=request.id,
            field="status",
            old_value="pending",
            new_value="approved",
            drug_id=request.drug_id,
            barcode=barcode,
            action="count",
        )
        return request


async def reject_count_request(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    request_id: int,
) -> StockCorrectionRequest:
    """Mark a pending request rejected; no stock is touched.

    Takes the branch advisory lock and row-locks FOR UPDATE, so a concurrent
    approval can never have its decision overwritten by this rejection (or
    vice-versa): whichever grabs the lock first decides, the other sees a
    non-pending request and 409s."""
    async with atomic(session):
        await acquire_branch_lock(session, branch_id)
        request = (
            await session.execute(
                select(StockCorrectionRequest)
                .where(StockCorrectionRequest.id == request_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if request is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
        if request.branch_id != branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found")
        if request.status != "pending":
            raise NOT_PENDING
        request.status = "rejected"
        request.rejected_by = user_id
        request.decided_at = datetime.now(timezone.utc)
        session.add(request)
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=REQUEST_ENTITY,
            entity_id=request.id,
            field="status",
            old_value="pending",
            new_value="rejected",
            drug_id=request.drug_id,
            action="count",
        )
        return request


async def _post_correction_journal(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    request: StockCorrectionRequest,
    value: Decimal,
    datee,
) -> None:
    """Balanced correction journal: Dr/Cr 1200 stock vs 5900 corrections.

    5900 is an expense: a DEFICIT debits it (stock loss hits the P&L as a cost);
    an OVERAGE credits it (a count gain nets down the expense contra). The
    balance is always zero-sum on each side."""
    entry_no = await next_journal_entry_no(session, branch_id, datee)
    entries = [
        ("1200", money.dec(value), money.dec("0")),
        ("5900", money.dec("0"), money.dec(value)),
    ]
    if request.delta < 0:
        entries = [
            ("5900", money.dec(value), money.dec("0")),
            ("1200", money.dec("0"), money.dec(value)),
        ]
    await post_journal(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        entry_no=entry_no,
        description=f"stock correction count#{request.id}",
        source="correction",
        entries=entries,
    )


async def _log_price_change(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    request: StockCorrectionRequest,
    unit_cost: Decimal,
    barcode: str,
    datee,
) -> None:
    """One price_change_log row per approved correction (ticket #13 AC): the
    corrected units at the unit cost that actually moved — the value history
    the legacy kept in storediscount (quant + price + tips)."""
    row = PriceChangeLog(
        branch_id=branch_id,
        drug_id=request.drug_id,
        barcode=barcode,
        price=unit_cost,
        quant=request.delta,
        datee=datee,
        tips=f"stock count correction #{request.id}",
        changed_by=user_id,
    )
    session.add(row)
    await session.flush()