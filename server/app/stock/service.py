"""Write-path seam for a stock mutation (ticket #2 AC3/AC4).

`adjust_stock` is the canonical shape every money/stock mutation follows:
it runs inside `app.core.db.atomic()` so the branch_stock update, its
`audit_log` row and its `sync_log` outbox row commit or roll back together
(G12, plan/02 §4.1). Later tickets build sales/purchases/returns on this
same skeleton (branch_stock + stock_batches + journal + balances + audit +
outbox in one transaction).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_UPDATE, audit, enqueue_sync
from app.core.db import atomic
from app.models import BranchStock, Drug

STOCK_ENTITY = "branch_stock"


async def adjust_stock(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    drug_id: int,
    qty_delta: int,
    barcode: str = "",
    source_device_id: Optional[int] = None,
) -> BranchStock:
    """Adjust branch_stock by `qty_delta` (+in/-out), atomically auditing.

    Locks the branch_stock row (SELECT ... FOR UPDATE) so concurrent sales on
    the same drug serialize on the running total (plan/02 §4.1, O-9).
    """
    async with atomic(session):
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
            raise ValueError(f"no branch_stock row for branch={branch_id} drug={drug_id}")

        old_qty = row.qty
        row.qty = old_qty + qty_delta

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity=STOCK_ENTITY,
            entity_id=drug_id,
            field="qty",
            old_value=str(old_qty),
            new_value=str(row.qty),
            drug_id=drug_id,
            barcode=barcode,
            action=ACTION_UPDATE,
        )
        await enqueue_sync(
            session,
            branch_id=branch_id,
            entity=STOCK_ENTITY,
            entity_id=drug_id,
            action=ACTION_UPDATE,
            payload={
                "branch_id": branch_id,
                "drug_id": drug_id,
                "qty": str(row.qty),
            },
            source_device_id=source_device_id,
        )
        return row