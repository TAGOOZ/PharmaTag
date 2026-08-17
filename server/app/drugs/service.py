"""Drug-master read seam (ticket #6 / S0.3).

`list_branch_drugs` is a plain read: drugs are global (wzdrugs) and the read
is scoped by the caller's branch — the branch context comes from the
authenticated user, not from a drug column. No money/stock mutation, so no
audit/outbox rows (AGENTS.md — reads follow plain read conventions).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Drug


async def list_branch_drugs(session: AsyncSession, branch_id: int) -> list[Drug]:
    """Active drug catalog visible to `branch_id` (global drugs, active only)."""
    result = await session.execute(
        select(Drug)
        .where(Drug.active.is_(True))
        .order_by(Drug.drugname, Drug.id)
    )
    return list(result.scalars().all())