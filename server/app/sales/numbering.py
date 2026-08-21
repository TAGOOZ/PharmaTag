"""Server-owned sale numbering (plan/02 G07: per-branch monotonic, no reuse).

invoice_no is the per-branch source of truth and is assigned by the server, not
the client. A per-branch advisory xact lock serializes numbering inside each
sale's transaction so two concurrent sales can never derive the same MAX+1; the
UNIQUE(branch_id, invoice_no) constraint stays as the backstop. Journals use the
same pattern per (branch_id, datee, entry_no).

Advisory locks are plain Postgres (no extensions), matching the "portable plain
Postgres" constraint — the SQLite twin never runs this server code.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Integer, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, Journal

_LOCK_NAMESPACE = "pharmatag:branch-sales"


async def acquire_branch_lock(session: AsyncSession, branch_id: int) -> None:
    """Serialize all sale writes for a branch (int8 advisory xact lock).

    Released automatically when the enclosing transaction commits or rolls
    back. Keeps invoice numbering and journal entry_no collision-free without a
    retry loop on the unique constraints.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:ns), :branch_id)"),
        {"ns": _LOCK_NAMESPACE, "branch_id": branch_id},
    )


async def next_invoice_no(session: AsyncSession, branch_id: int) -> str:
    """Next monotonic invoice_no for the branch (call under the branch lock)."""
    current = (
        await session.execute(
            select(func.max(func.cast(Invoice.invoice_no, Integer))).where(
                Invoice.branch_id == branch_id
            )
        )
    ).scalar_one()
    current_no = int(current) if current is not None else 0
    return str(current_no + 1)


async def next_journal_entry_no(
    session: AsyncSession, branch_id: int, datee: date
) -> int:
    """Next journal entry_no for (branch_id, datee) — safe under the branch lock."""
    current = (
        await session.execute(
            select(func.max(Journal.entry_no)).where(
                Journal.branch_id == branch_id, Journal.datee == datee
            )
        )
    ).scalar_one()
    return (current or 0) + 1
