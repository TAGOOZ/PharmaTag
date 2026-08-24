"""Batch-level stock operations for transfers (#32, T2/T4).

Dispatch decrements the source branch's batches + branch_stock under
SELECT ... FOR UPDATE (concurrent sales/dispatches can never oversell),
writing `oldstock` snapshots and `transfer_out` audits. Receive walks the
stored allocations FEFO, creates/adds target batches with cost/expire/vat/
price preserved VERBATIM (`typee='transfer_in'`, EDA traceability) and
auto-returns any shortfall to the exact source batches
(`transfer_shortage_return`). All writes run inside the caller's transaction;
the caller owns the G12 boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.money import dec, format2, format4
from app.models import BranchStock, StockBatch

INSUFFICIENT_STOCK = HTTPException(status.HTTP_409_CONFLICT, "insufficient stock")
NO_STOCK = HTTPException(status.HTTP_409_CONFLICT, "no stock registered for this drug")
MISSING_BATCH = HTTPException(status.HTTP_409_CONFLICT, "stock batch missing")


@dataclass(frozen=True)
class Allocation:
    """One batch's share of a transfer line (snapshot for replay)."""

    batch_id: int
    randomid: str
    take: Decimal
    cost: Decimal
    expire: Optional[date]
    vat: Decimal
    price: Decimal

    def to_json(self) -> dict:
        """Canonical wire form (#57): qty/cost/price exactly-4dp strings,
        vat exactly-2dp (slabs exempt/5%/14% -> '0.00'/'5.00'/'14.00'),
        expire ISO date or None — never raw str(Decimal) scale leakage.
        from_json still parses legacy rows of any scale."""
        return {
            "batch_id": self.batch_id,
            "randomid": self.randomid,
            "qty": format4(self.take),
            "cost": format4(self.cost),
            "expire": self.expire.isoformat() if self.expire else None,
            "vat": format2(self.vat),
            "price": format4(self.price),
        }

    @staticmethod
    def from_json(raw: dict) -> "Allocation":
        return Allocation(
            batch_id=int(raw["batch_id"]),
            randomid=str(raw["randomid"]),
            take=dec(raw["qty"]),
            cost=dec(raw["cost"]),
            expire=date.fromisoformat(raw["expire"]) if raw.get("expire") else None,
            vat=dec(raw["vat"]),
            price=dec(raw["price"]),
        )


async def suggest_fefo(
    session: AsyncSession, *, branch_id: int, drug_id: int, qty: Decimal
) -> list[Allocation]:
    """Lock the drug's branch_stock + batches and propose a FEFO split of
    `qty`. Raises 409 when stock is missing/insufficient. The suggestion is
    validated again at apply time under the same locks."""
    branch = (
        await session.execute(
            select(BranchStock)
            .where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if branch is None:
        raise NO_STOCK
    if branch.qty < qty:
        raise INSUFFICIENT_STOCK

    rows = (
        await session.execute(
            select(StockBatch)
            .where(
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == drug_id,
                StockBatch.qty > 0,
            )
            .order_by(StockBatch.expire.is_(None), StockBatch.expire, StockBatch.id)
            .with_for_update()
        )
    ).scalars().all()

    remaining = qty
    allocations: list[Allocation] = []
    for batch in rows:
        if remaining <= 0:
            break
        take = min(batch.qty, remaining)
        allocations.append(
            Allocation(
                batch_id=batch.id,
                randomid=batch.randomid,
                take=take,
                cost=dec(batch.cost),
                expire=batch.expire,
                vat=dec(batch.vat),
                price=dec(batch.price),
            )
        )
        remaining -= take
    if remaining > 0:
        raise INSUFFICIENT_STOCK
    return allocations


async def _decrement_source_batch(
    session: AsyncSession,
    *,
    batch_id: int,
    take: Decimal,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    action: str,
    transfer_no: str,
) -> StockBatch:
    batch = (
        await session.execute(
            select(StockBatch).where(StockBatch.id == batch_id).with_for_update()
        )
    ).scalar_one_or_none()
    if batch is None:
        raise MISSING_BATCH
    old = dec(batch.qty)
    if old < take:
        raise INSUFFICIENT_STOCK
    new = old - take
    batch.qty = new
    batch.oldstock = old
    session.add(batch)
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="stock_batches",
        entity_id=batch.id,
        field="qty",
        old_value=str(old),
        new_value=str(new),
        drug_id=drug_id,
        action=action,
        typevalue=transfer_no,
    )
    return batch


async def _adjust_branch_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    delta: Decimal,
    action: str,
    transfer_no: str,
) -> None:
    row = (
        await session.execute(
            select(BranchStock)
            .where(BranchStock.branch_id == branch_id, BranchStock.drug_id == drug_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    old = dec(row.qty) if row is not None else Decimal("0")
    new = old + delta
    if row is None:
        row = BranchStock(branch_id=branch_id, drug_id=drug_id, qty=new, minimum=0)
    else:
        row.qty = new
        row.lastedit = datetime.now(timezone.utc)
    session.add(row)
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="branch_stock",
        entity_id=drug_id,
        field="qty",
        old_value=str(old),
        new_value=str(new),
        drug_id=drug_id,
        action=action,
        typevalue=transfer_no,
    )


def allocations_from_json(raw: Optional[list]) -> list[Allocation]:
    return [Allocation.from_json(item) for item in (raw or [])]


async def validate_explicit(
    session: AsyncSession,
    *,
    branch_id: int,
    drug_id: int,
    takes: list[tuple[int, Decimal]],
) -> list[Allocation]:
    """Resolve client-nominated (batch_id, qty) takes into full allocations.

    Locks the drug's branch_stock and every referenced batch FOR UPDATE and
    verifies each batch belongs to this branch+drug and covers its take
    (server-validated explicit dispatch — never trust the payload blindly).
    """
    total = sum((qty for _, qty in takes), Decimal("0"))
    seen: set[int] = set()
    for batch_id, qty in takes:
        # a non-positive take would mint phantom units on a batch (e.g.
        # [(real, +20), (empty, -10)] sums correctly but fabricates stock)
        if qty <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "allocation qty must be positive"
            )
        if batch_id in seen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "duplicate batch allocation"
            )
        seen.add(batch_id)
    branch = (
        await session.execute(
            select(BranchStock)
            .where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if branch is None:
        raise NO_STOCK
    if branch.qty < total:
        raise INSUFFICIENT_STOCK

    allocations: list[Allocation] = []
    for batch_id, qty in takes:
        batch = (
            await session.execute(
                select(StockBatch).where(StockBatch.id == batch_id).with_for_update()
            )
        ).scalar_one_or_none()
        if (
            batch is None
            or batch.branch_id != branch_id
            or batch.drug_id != drug_id
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "allocation batch does not belong to this line",
            )
        if dec(batch.qty) < qty:
            raise INSUFFICIENT_STOCK
        allocations.append(
            Allocation(
                batch_id=batch.id,
                randomid=batch.randomid,
                take=qty,
                cost=dec(batch.cost),
                expire=batch.expire,
                vat=dec(batch.vat),
                price=dec(batch.price),
            )
        )
    return allocations


async def dispatch_line(
    session: AsyncSession,
    *,
    source_branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    allocations: list[Allocation],
    transfer_no: str,
) -> None:
    """Apply one line's allocations: decrement each source batch + branch_stock."""
    for alloc in allocations:
        await _decrement_source_batch(
            session,
            batch_id=alloc.batch_id,
            take=alloc.take,
            branch_id=source_branch_id,
            user_id=user_id,
            drug_id=drug_id,
            action="transfer_out",
            transfer_no=transfer_no,
        )
    await _adjust_branch_stock(
        session,
        branch_id=source_branch_id,
        user_id=user_id,
        drug_id=drug_id,
        delta=-sum((a.take for a in allocations), Decimal("0")),
        action="transfer_out",
        transfer_no=transfer_no,
    )


async def receive_line(
    session: AsyncSession,
    *,
    source_branch_id: int,
    target_branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    allocations: list[Allocation],
    received_qty: Decimal,
    transfer_no: str,
) -> Decimal:
    """Land `received_qty` on the target branch; auto-return the shortfall to
    the source batches. Returns the received quantity."""
    remaining = received_qty
    for alloc in allocations:
        if remaining <= 0:
            break
        take = min(alloc.take, remaining)
        remaining -= take
        existing = (
            await session.execute(
                select(StockBatch)
                .where(
                    StockBatch.branch_id == target_branch_id,
                    StockBatch.drug_id == drug_id,
                    StockBatch.randomid == alloc.randomid,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if existing is not None:
            # merge into the lot already on the shelf — never re-cost a mixed lot
            old = dec(existing.qty)
            existing.qty = old + take
            existing.oldstock = old
            session.add(existing)
            batch_id, new_qty = existing.id, dec(existing.qty)
        else:
            batch = StockBatch(
                branch_id=target_branch_id,
                drug_id=drug_id,
                randomid=alloc.randomid,
                qty=take,
                expire=alloc.expire,
                cost=alloc.cost,
                vat=alloc.vat,
                price=alloc.price,
                oldstock=Decimal("0"),
                typee="transfer_in",
                created_by=user_id,
            )
            session.add(batch)
            await session.flush()
            batch_id, new_qty = batch.id, take
        await audit(
            session,
            branch_id=target_branch_id,
            user_id=user_id,
            entity="stock_batches",
            entity_id=batch_id,
            field="qty",
            old_value=str(new_qty - take),
            new_value=str(new_qty),
            drug_id=drug_id,
            action="transfer_in",
            typevalue=transfer_no,
        )

    await _adjust_branch_stock(
        session,
        branch_id=target_branch_id,
        user_id=user_id,
        drug_id=drug_id,
        delta=received_qty,
        action="transfer_in",
        transfer_no=transfer_no,
    )

    # shortfall auto-returns to the source batches ("the driver brings it back")
    shortfall = sum((a.take for a in allocations), Decimal("0")) - received_qty
    if shortfall > 0:
        rest = shortfall
        for alloc in allocations:
            if rest <= 0:
                break
            give_back = min(alloc.take, rest)
            rest -= give_back
            batch = (
                await session.execute(
                    select(StockBatch)
                    .where(StockBatch.id == alloc.batch_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if batch is None:
                raise MISSING_BATCH
            old = dec(batch.qty)
            batch.qty = old + give_back
            batch.oldstock = old
            session.add(batch)
            await audit(
                session,
                branch_id=source_branch_id,
                user_id=user_id,
                entity="stock_batches",
                entity_id=batch.id,
                field="qty",
                old_value=str(old),
                new_value=str(old + give_back),
                drug_id=drug_id,
                action="transfer_shortage_return",
                typevalue=transfer_no,
            )
        await _adjust_branch_stock(
            session,
            branch_id=source_branch_id,
            user_id=user_id,
            drug_id=drug_id,
            delta=shortfall,
            action="transfer_shortage_return",
            transfer_no=transfer_no,
        )
    return received_qty
