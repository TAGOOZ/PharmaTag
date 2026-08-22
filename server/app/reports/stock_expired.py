"""Expired/expiring stock report (S3.3 #25): الادوية منتهية الصلاحية.

RPT-D01 + RPT-EXP01 merged, batch-level over `stock_batches`: lots with
`qty > 0` whose expiry has passed (status `expired`, `expire ≤ as-of`) or
lands within a warning horizon (default 30 days, status `warning`). The
boundary is inclusive — a pack expiring ON the as-of day is expired.
Zero-qty batches never appear; value is qty × batch cost.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import money
from app.core.time import business_date
from app.models import Drug, StockBatch

_DEFAULT_HORIZON_DAYS = 30
_MAX_ITEMS = 1000


def _fmt4(value) -> str:
    return format(money.round4(value), "f")


async def stock_expired_report(
    session: AsyncSession,
    *,
    branch_id: int,
    datee: Optional[date] = None,
    horizon_days: int = _DEFAULT_HORIZON_DAYS,
) -> dict:
    """Expired + expiring-within-horizon batches for the branch."""
    as_of = datee or business_date()
    if horizon_days < 0:
        raise ValueError("horizon_days must not be negative")
    horizon_end = date.fromordinal(as_of.toordinal() + horizon_days)

    where = [
        StockBatch.branch_id == branch_id,
        StockBatch.qty > 0,
        StockBatch.expire.is_not(None),
        StockBatch.expire <= horizon_end,
    ]

    total = (
        await session.execute(
            select(func.count()).select_from(StockBatch).where(*where)
        )
    ).scalar_one()
    total_value = (
        await session.execute(
            select(func.coalesce(func.sum(StockBatch.qty * StockBatch.cost), 0)).where(
                *where
            )
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(StockBatch, Drug)
            .join(Drug, Drug.id == StockBatch.drug_id)
            .where(*where)
            .options(selectinload(Drug.barcodes))
            .order_by(StockBatch.expire, Drug.drugname)
            .limit(_MAX_ITEMS)
        )
    ).all()

    items = []
    for batch, drug in rows:
        days_to_expiry = batch.expire.toordinal() - as_of.toordinal()
        status = "expired" if batch.expire <= as_of else "warning"
        value = money.dec(batch.qty) * money.dec(batch.cost)
        primary = next(
            (
                b.barcode
                for b in sorted(drug.barcodes, key=lambda b: not b.is_primary)
            ),
            "",
        )
        items.append(
            {
                "drug_id": drug.id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear or "",
                "barcode": primary,
                "batch_id": batch.id,
                "randomid": batch.randomid,
                "expire": batch.expire.isoformat(),
                "days_to_expiry": str(days_to_expiry),
                "qty": _fmt4(batch.qty),
                "cost": _fmt4(batch.cost),
                "value": format(money.round2(value), "f"),
                "status": status,
            }
        )

    return {
        "branch_id": branch_id,
        "datee": as_of.isoformat(),
        "horizon_days": horizon_days,
        "count": total,
        "truncated": total > _MAX_ITEMS,
        # whole-branch affected value in SQL — correct even when truncated
        "total_value": format(money.round2(total_value), "f"),
        "items": items,
    }
