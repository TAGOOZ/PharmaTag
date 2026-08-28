"""Return stock-up: restore original expiry lots + branch_stock raise (plan/05 §S1.5).

A sales return historically created a NEW `stock_batches` row (`typee='return'`,
randomid `r-<invoice_no>-<idx>`) with the line's stored (earliest) expiry.
That path is now the FALLBACK. The primary path (#51) restores the ORIGINAL
consumed lots proportionally: each source batch (identified by the sale's
outbox allocations) is incremented by its share of the returned qty, preserving
its expiry/cost/randomid. This fixes the FIFO-spillover mislabeling where a
4-unit return of a 2+2 spillover was stamped entirely with the earliest expiry
and fixes batch fragmentation (repeated sell→return cycles no longer spawn
synthetic r-* batches). Branch-stock is always raised by the full returned qty;
per-batch restores are audited inside the caller's transaction (G12).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.audit import ACTION_INSERT, audit, enqueue_sync
from app.core.money import dec, round4
from app.models import BranchStock, DrugBarcode, StockBatch

BATCH_DUP = HTTPException(
    status.HTTP_409_CONFLICT, "a batch with this reference already exists"
)


def _split_return_shares(
    allocations: list[dict], returned_qty
) -> list[Decimal]:
    """Split `returned_qty` proportionally across original allocations (#51).

    Each allocation dict carries the original `take` (str/Decimal). The share
    for every allocation except the last is round4(take * returned / total);
    the last absorbs the remainder so SUM(shares) == returned exactly (4dp).
    Returns a list of Decimals parallel to allocations.
    """
    if not allocations:
        return []
    total = sum(dec(a.get("take", 0)) for a in allocations)
    if total <= 0:
        return [Decimal("0") for _ in allocations]
    ret = dec(returned_qty)
    shares: list[Decimal] = []
    sum_prev = Decimal("0")
    for i, alloc in enumerate(allocations):
        if i == len(allocations) - 1:
            shares.append(round4(ret - sum_prev))
        else:
            share = round4(dec(alloc.get("take", 0)) * ret / total)
            # clamp to remaining (guards tiny rounding overshoot)
            remaining = ret - sum_prev
            if share > remaining:
                share = round4(remaining)
            if share < 0:
                share = Decimal("0.0000")
            shares.append(share)
            sum_prev += share
    return shares


async def restore_return_allocations(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    allocations: list[dict],
    returned_qty,
    barcode: str = "",
    vat_rate: Decimal | None = None,
    price: Decimal | None = None,
    vat_amount: Decimal | None = None,
    total_with_vat: Decimal | None = None,
) -> list[StockBatch]:
    """Restore each source lot by its proportional share of `returned_qty` (#51).

    For every allocation (batch_id/randomid/take/cost/expire) the proportional
    share is computed via `_split_return_shares`. An existing `StockBatch`
    matching (branch, drug, randomid) is locked FOR UPDATE and incremented;
    if none exists the batch is looked up by batch_id as a secondary key. When
    the source lot is gone a NEW `return`-type batch is created with the
    original allocation's expiry/cost/randomid (or a synthetic fallback randomid)
    so the lot's expiry is still preserved. Each mutation is audited.

    Returns the list of restored/created batches parallel to the filtered shares
    (zero-share allocations are skipped). Caller still raises branch_stock.
    """
    if not allocations:
        return []
    shares = _split_return_shares(allocations, returned_qty)
    restored: list[StockBatch] = []
    for alloc, share in zip(allocations, shares):
        if dec(share) <= 0:
            continue
        share_d = dec(share)
        randomid = alloc.get("randomid")
        batch_id = alloc.get("batch_id")
        expire_raw = alloc.get("expire")
        cost_raw = alloc.get("cost")
        expire = None
        if expire_raw:
            try:
                expire = date.fromisoformat(str(expire_raw))
            except Exception:
                expire = None
        # Try find existing batch by randomid (primary key for lots)
        batch = None
        if randomid:
            batch = (
                await session.execute(
                    select(StockBatch)
                    .where(
                        StockBatch.branch_id == branch_id,
                        StockBatch.drug_id == drug_id,
                        StockBatch.randomid == randomid,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
        # Secondary lookup by batch_id (covers randomid-less allocations) — single FOR UPDATE query
        if batch is None and batch_id is not None:
            try:
                bid = int(batch_id)
            except Exception:
                bid = None
            if bid is not None:
                batch = (
                    await session.execute(
                        select(StockBatch)
                        .where(
                            StockBatch.id == bid,
                            StockBatch.branch_id == branch_id,
                            StockBatch.drug_id == drug_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
        if batch is not None:
            old = dec(batch.qty)
            new = old + share_d
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
                barcode=barcode,
                action="return",
                typevalue=invoice_no,
            )
            restored.append(batch)
        else:
            # Source lot gone — create a new batch preserving its lot identity
            # Prefer the original randomid so expiry stays correct and future
            # returns can still find it; synthetic fallback only if randomid missing
            # or already taken.
            if randomid:
                # check duplicate
                dup = (
                    await session.execute(
                        select(StockBatch.id).where(
                            StockBatch.branch_id == branch_id,
                            StockBatch.drug_id == drug_id,
                            StockBatch.randomid == randomid,
                        )
                    )
                ).scalar_one_or_none()
                new_randomid = randomid if dup is None else f"r-{invoice_no}-{drug_id}-{len(restored)}"
            else:
                new_randomid = f"r-{invoice_no}-{drug_id}-{len(restored)}"
            cost = dec(cost_raw) if cost_raw is not None else Decimal("0")
            cost = round4(cost)
            vat = dec(vat_rate) if vat_rate is not None else Decimal("0")
            p = dec(price) if price is not None else cost
            vval = dec(vat_amount) if vat_amount is not None else Decimal("0")
            twv = dec(total_with_vat) if total_with_vat is not None else Decimal("0")
            batch = StockBatch(
                branch_id=branch_id,
                drug_id=drug_id,
                randomid=new_randomid,
                qty=share_d,
                expire=expire,
                cost=cost,
                vat=vat,
                price=p,
                oldstock=Decimal("0"),
                typee="return",
                vatvalue=vval,
                totalwithvat=twv,
                created_by=user_id,
            )
            session.add(batch)
            await session.flush()
            await audit(
                session,
                branch_id=branch_id,
                user_id=user_id,
                entity="stock_batches",
                entity_id=batch.id,
                field="qty",
                old_value="0.0000",
                new_value=str(share_d),
                drug_id=drug_id,
                barcode=barcode,
                action="return",
                typevalue=invoice_no,
            )
            restored.append(batch)
    return restored


async def _primary_barcode(session: AsyncSession, drug_id: int) -> str:
    """The drug's primary barcode, used for audit/batch provenance."""
    row = (
        await session.execute(
            select(DrugBarcode).where(
                DrugBarcode.drug_id == drug_id,
                DrugBarcode.is_primary.is_(True),
            )
        )
    ).scalars().first()
    return row.barcode if row else ""


async def create_return_batch(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    idx: int,
    drug_id: int,
    qty,
    cost: Decimal,
    price: Decimal,
    vat_rate: Decimal,
    vat_amount,
    total_with_vat,
    expire,
    barcode: str = "",
) -> StockBatch:
    """Create one NEW return batch (randomid r-<invoice_no>-<idx>); rejects dup."""
    randomid = f"r-{invoice_no}-{idx}"
    existing = (
        await session.execute(
            select(StockBatch.id).where(
                StockBatch.branch_id == branch_id,
                StockBatch.drug_id == drug_id,
                StockBatch.randomid == randomid,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise BATCH_DUP
    batch = StockBatch(
        branch_id=branch_id,
        drug_id=drug_id,
        randomid=randomid,
        qty=Decimal(qty),
        expire=expire,
        cost=Decimal(cost),
        vat=Decimal(vat_rate),
        price=Decimal(price),
        oldstock=Decimal("0"),
        typee="return",
        vatvalue=Decimal(vat_amount),
        totalwithvat=Decimal(total_with_vat),
        created_by=user_id,
    )
    session.add(batch)
    await session.flush()
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="stock_batches",
        entity_id=batch.id,
        field="qty",
        old_value="0.0000",
        new_value=str(qty),
        drug_id=drug_id,
        barcode=barcode,
        action="return",
        typevalue=invoice_no,
    )
    return batch


async def raise_branch_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    drug_id: int,
    qty_delta,
    barcode: str = "",
) -> BranchStock:
    """Add `qty_delta` back to the drug's branch_stock (locking FOR UPDATE)."""
    row = (
        await session.execute(
            select(BranchStock)
            .where(
                BranchStock.branch_id == branch_id,
                BranchStock.drug_id == drug_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        row = BranchStock(
            branch_id=branch_id,
            drug_id=drug_id,
            qty=Decimal("0"),
            minimum=Decimal("0"),
        )
        session.add(row)
        await session.flush()
    old = Decimal(row.qty)
    new = old + Decimal(qty_delta)
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
        barcode=barcode,
        action="return",
        typevalue=invoice_no,
    )
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="branch_stock",
        entity_id=drug_id,
        action="return",
        payload={
            "branch_id": branch_id,
            "drug_id": drug_id,
            "qty": format(money.round4(new), "f"),
            "minimum": format(money.round4(row.minimum or 0), "f"),
            "silsilaid": row.silsilaid or "",
            "classy": row.classy or "",
        },
    )
    return row