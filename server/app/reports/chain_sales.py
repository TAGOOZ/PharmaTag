"""Chain sales summary (S5.4 #34) — the titanksasales projection (A06).

Legacy replicated a 9-col chain sales table between pharmacies with a GUID
insert loop. Decision A06 (plan/00): the chain summary is a PROJECTION over
canonical `invoices`, regenerated on demand — never a synced table. This
report is that projection: per-day × per-branch sale totals across every
ACTIVE branch in the registry (single-shared-PG topology, G09), so the owner
reconciles the whole صيدليات chain on one grid.

Money stays exact-decimal and renders as strings; totals are computed IN SQL
over every matching invoice so the foot stays whole-range even when the row
list hits the render cap (`truncated` marks a cut list). Read-only: no
journal, stock or outbox writes anywhere.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money

from app.models import Branch, Invoice

_MAX_ROWS = 1000


async def chain_sales_report(
    session: AsyncSession,
    *,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Per-(datee, branch) sale totals across all active branches.

    SEMANTICS (titanksasales parity, pinned by test): GROSS sales only —
    `kind == 'sale'`; returns are NOT netted here (see period_totals /
    vat_summary for net views). No status filter: no write path currently
    produces non-'saved' sale invoices; revisit if void/unsaved become real.
    """
    where = [
        Invoice.kind == "sale",
        Invoice.branch_id == Branch.id,
        Branch.is_active.is_(True),
    ]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)

    def _base():
        return (
            select(
                Invoice.datee,
                Branch.pharname,
                Branch.pharmacyid,
                func.count().label("invoice_count"),
                func.coalesce(func.sum(Invoice.totalvalue), 0).label("total"),
                func.coalesce(func.sum(Invoice.payed), 0).label("payed"),
                func.coalesce(func.sum(Invoice.agel), 0).label("agel"),
                func.coalesce(func.sum(Invoice.vat), 0).label("vat"),
            )
            .select_from(Invoice)
            .join(Branch, Invoice.branch_id == Branch.id)
            .where(*where)
        )

    rows = (
        await session.execute(
            _base()
            .group_by(Invoice.datee, Branch.pharname, Branch.pharmacyid)
            .order_by(Invoice.datee.desc(), Branch.pharmacyid)
            .limit(_MAX_ROWS + 1)
        )
    ).all()

    truncated = len(rows) > _MAX_ROWS
    rows = rows[:_MAX_ROWS]

    count, s_total, s_payed, s_agel, s_vat = (
        await session.execute(
            select(
                func.count(func.distinct(Invoice.id)),
                func.coalesce(func.sum(Invoice.totalvalue), 0),
                func.coalesce(func.sum(Invoice.payed), 0),
                func.coalesce(func.sum(Invoice.agel), 0),
                func.coalesce(func.sum(Invoice.vat), 0),
            )
            .select_from(Invoice)
            .join(Branch, Invoice.branch_id == Branch.id)
            .where(*where)
        )
    ).one()

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "rows": [
            {
                "datee": day.isoformat(),
                "branch": pharname or pharmacyid,
                "invoice_count": int(invoice_count),
                "total": money.format2(total),
                "payed": money.format2(payed),
                "agel": money.format2(agel),
                "vat": money.format2(vat),
            }
            for (
                day,
                pharname,
                pharmacyid,
                invoice_count,
                total,
                payed,
                agel,
                vat,
            ) in rows
        ],
        "truncated": truncated,
        "totals": {
            "invoice_count": int(count),
            "total": money.format2(s_total),
            "payed": money.format2(s_payed),
            "agel": money.format2(s_agel),
            "vat": money.format2(s_vat),
        },
    }
