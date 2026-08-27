"""Chain stock snapshot (S5.5 #35) — titanksastock → branch_stock projection.

Legacy replicated a per-pharmacy stock snapshot between branches. Decision A06:
the snapshot is a read-only projection over canonical `branch_stock`, regenerated
on demand — never a synced table. This report is that projection: per-(drug,
branch) qty/minimum/shortage across every ACTIVE branch, sorted by shortage
desc, drugname asc, pharmacyid asc. Read-only: no journal, stock or outbox writes.

Money stays exact-decimal 4dp strings; truncated at _MAX_ROWS with whole-range
count in foot.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.models import Branch, BranchStock, Drug, DrugBarcode

_MAX_ROWS = 1000


async def query_chain_stock(
    session: AsyncSession,
    *,
    drug_id: Optional[int] = None,
    q: Optional[str] = None,
    only_shortage: bool = False,
    include_inactive: bool = False,
) -> dict:
    """Shared projection: `branch_stock ⨝ branches ⨝ drugs` with A06 filters.

    Single source of truth for both `chain_stock` report and
    `GET /stock/cross-branch` — prevents drift (review High/Medium).
    `include_inactive` toggles **both** `Branch.is_active` and `Drug.active`
    (audit opt-in). `q` is escaped for ``%_\\`` so ``%`` does not become a wildcard.
    """
    where: list = []
    if not include_inactive:
        where.append(Branch.is_active.is_(True))
        where.append(Drug.active.is_(True))
    if drug_id is not None:
        where.append(BranchStock.drug_id == drug_id)
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
    if only_shortage:
        where.append(BranchStock.qty < BranchStock.minimum)

    total = (
        await session.execute(
            select(func.count())
            .select_from(BranchStock)
            .join(Branch, Branch.id == BranchStock.branch_id)
            .join(Drug, Drug.id == BranchStock.drug_id)
            .where(*where)
        )
    ).scalar_one()

    shortage_expr = func.greatest(BranchStock.minimum - BranchStock.qty, Decimal("0"))
    rows = (
        await session.execute(
            select(BranchStock, Branch, Drug)
            .join(Branch, Branch.id == BranchStock.branch_id)
            .join(Drug, Drug.id == BranchStock.drug_id)
            .where(*where)
            .order_by(shortage_expr.desc(), Drug.drugname.asc(), Branch.pharmacyid.asc())
            .limit(_MAX_ROWS)
        )
    ).all()

    bar_map: dict[int, str] = {}
    if rows:
        drug_ids = {d.id for _, _, d in rows}
        bar_rows = (
            await session.execute(select(DrugBarcode).where(DrugBarcode.drug_id.in_(drug_ids)))
        ).scalars().all()
        grouped: dict[int, list[DrugBarcode]] = defaultdict(list)
        for b in bar_rows:
            grouped[b.drug_id].append(b)
        for did, lst in grouped.items():
            lst_sorted = sorted(lst, key=lambda x: not x.is_primary)
            bar_map[did] = lst_sorted[0].barcode if lst_sorted else ""

    items = []
    for stock, branch, drug in rows:
        shortage_dec = money.dec(stock.minimum) - money.dec(stock.qty)
        if shortage_dec < Decimal("0"):
            shortage_dec = Decimal("0")
        items.append(
            {
                "branch_id": branch.id,
                "pharmacyid": branch.pharmacyid,
                "pharname": branch.pharname or "",
                "drug_id": drug.id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear or "",
                "barcode": bar_map.get(drug.id, ""),
                "qty": money.format4(stock.qty),
                "minimum": money.format4(stock.minimum),
                "shortage": money.format4(shortage_dec),
                "silsilaid": stock.silsilaid or "",
                "classy": stock.classy or drug.classy or "",
                "lastedit": stock.lastedit.isoformat() if stock.lastedit else None,
            }
        )

    return {
        "count": int(total),
        "truncated": bool(total > _MAX_ROWS),
        "items": items,
    }


async def chain_stock_report(session: AsyncSession, *, branch_id: int) -> dict:
    """Per-(drug, branch) stock snapshot across all active branches.

    `branch_id` is the caller's branch (ignored — chain-wide by design, A06).
    """
    data = await query_chain_stock(session)
    return {"branch_id": branch_id, **data}
