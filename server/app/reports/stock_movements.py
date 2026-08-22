"""Drug movement track (S3.3 #25): تتبع تغيير الرصيد (RPT-ST06).

Per-drug daily opening / purchases / sales / sales-returns /
purchase-returns / adjustments / closing over a date range, **derived on
read** (decision in #25: no persisted movements ledger this slice):

- `invoice_lines` grouped by parent `invoices.kind`
  (`purchase` +, `sale` −, `sale_return` +, `purchase_return` −),
- approved `stock_correction_requests` delta as adjustments
  (dated at the approval decision, falling back to the request date).

Days with no movement never appear; opening rolls from day to day. Over an
open-ended window (`date_from=None`) the first opening is 0 and the last
closing must equal `branch_stock.qty` — that reconciliation is a tested
invariant.

NOTE for future kinds: `invoice_kind_enum` also has `transfer` (S5.2,
inter-branch). It moves stock between branches, so when transfer writers
land they MUST be added to `_SIGNED`/`buckets` here or the closing==qty
invariant silently breaks.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.core.config import settings
from app.models import BranchStock, Drug, Invoice, InvoiceLine, StockCorrectionRequest

_ZERO = money.dec("0")


def _business_day(ts):
    """A timestamptz → its business-timezone date — the same day the
    correction's journal posts under (app/core/time.business_date rule),
    not the UTC date."""
    return cast(func.timezone(settings.timezone, ts), Date)

# signed per-kind quantity contribution to stock
_SIGNED = {
    "sale": -1,
    "sale_return": 1,
    "purchase": 1,
    "purchase_return": -1,
}


def _fmt(value) -> str:
    return format(money.round4(value), "f")


def _blank_day() -> dict[str, object]:
    return {
        "purchases": _ZERO,
        "sales": _ZERO,
        "sales_returns": _ZERO,
        "purchase_returns": _ZERO,
    }


async def _line_days(
    session: AsyncSession,
    *,
    branch_id: int,
    drug_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict[date, dict[str, object]]:
    """date → {purchases, sales, sales_returns, purchase_returns} qty sums."""
    where = [
        Invoice.branch_id == branch_id,
        InvoiceLine.drug_id == drug_id,
        Invoice.kind.in_(_SIGNED),
    ]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)

    rows = await session.execute(
        select(Invoice.datee, Invoice.kind, func.sum(InvoiceLine.qty))
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(*where)
        .group_by(Invoice.datee, Invoice.kind)
    )
    days: dict[date, dict[str, object]] = {}
    buckets = {
        "purchase": "purchases",
        "sale": "sales",
        "sale_return": "sales_returns",
        "purchase_return": "purchase_returns",
    }
    for day, kind, qty in rows:
        entry = days.setdefault(day, _blank_day())
        entry[buckets[kind]] += money.dec(qty or 0)  # type: ignore[operator]
    return days


async def _adjustment_days(
    session: AsyncSession,
    *,
    branch_id: int,
    drug_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict[date, object]:
    """date → Σ approved correction deltas decided on that day."""
    decided = _business_day(
        func.coalesce(
            StockCorrectionRequest.decided_at, StockCorrectionRequest.created_at
        )
    )
    where = [
        StockCorrectionRequest.branch_id == branch_id,
        StockCorrectionRequest.drug_id == drug_id,
        StockCorrectionRequest.status == "approved",
    ]
    if date_from is not None:
        where.append(decided >= date_from)
    if date_to is not None:
        where.append(decided <= date_to)
    rows = await session.execute(
        select(decided.label("day"), func.sum(StockCorrectionRequest.delta))
        .where(*where)
        .group_by(decided)
    )
    return {day: money.dec(delta or 0) for day, delta in rows.all()}


async def stock_movements_report(
    session: AsyncSession,
    *,
    branch_id: int,
    drug_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """The movement track for one drug; raises ValueError on unknown drugs."""
    drug = await session.get(Drug, drug_id)
    if drug is None:
        raise ValueError(f"unknown drug {drug_id}")

    line_days = await _line_days(
        session,
        branch_id=branch_id,
        drug_id=drug_id,
        date_from=date_from,
        date_to=date_to,
    )
    adj_days = await _adjustment_days(
        session,
        branch_id=branch_id,
        drug_id=drug_id,
        date_from=date_from,
        date_to=date_to,
    )

    all_days = sorted(set(line_days) | set(adj_days))

    opening = _ZERO
    if date_from is None:
        pass  # open start: history begins here
    else:
        pre_from = date_from - timedelta(days=1)
        line_rows = (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                *[
                                    (Invoice.kind == kind, InvoiceLine.qty * sign)
                                    for kind, sign in _SIGNED.items()
                                ],
                                else_=0,
                            )
                        ),
                        0,
                    )
                )
                .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                .where(
                    Invoice.branch_id == branch_id,
                    InvoiceLine.drug_id == drug_id,
                    Invoice.kind.in_(_SIGNED),
                    Invoice.datee <= pre_from,
                )
            )
        ).scalar_one()
        adj_row = (
            await session.execute(
                select(func.coalesce(func.sum(StockCorrectionRequest.delta), 0)).where(
                    StockCorrectionRequest.branch_id == branch_id,
                    StockCorrectionRequest.drug_id == drug_id,
                    StockCorrectionRequest.status == "approved",
                    _business_day(
                        func.coalesce(
                            StockCorrectionRequest.decided_at,
                            StockCorrectionRequest.created_at,
                        )
                    )
                    <= pre_from,
                )
            )
        ).scalar_one()
        opening = money.dec(line_rows) + money.dec(adj_row)

    running = opening
    days = []
    for day in all_days:
        moves = line_days.get(day)
        adjs = adj_days.get(day)
        purchases = money.dec(moves["purchases"]) if moves else _ZERO
        sales = money.dec(moves["sales"]) if moves else _ZERO
        sales_returns = money.dec(moves["sales_returns"]) if moves else _ZERO
        purchase_returns = money.dec(moves["purchase_returns"]) if moves else _ZERO
        adjustments = money.dec(adjs) if adjs is not None else _ZERO
        closing = (
            running + purchases - sales + sales_returns - purchase_returns + adjustments
        )
        days.append(
            {
                "datee": day.isoformat(),
                "opening": _fmt(running),
                "purchases": _fmt(purchases),
                "sales": _fmt(sales),
                "sales_returns": _fmt(sales_returns),
                "purchase_returns": _fmt(purchase_returns),
                "adjustments": _fmt(adjustments),
                "closing": _fmt(closing),
            }
        )
        running = closing

    stock = await session.get(BranchStock, (branch_id, drug_id))
    return {
        "branch_id": branch_id,
        "drug_id": drug_id,
        "drugname": drug.drugname,
        "current_qty": _fmt(stock.qty) if stock else "0.0000",
        "days": days,
    }
