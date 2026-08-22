"""Sales-invoice register (S3.4, ticket #26; RPT-S01).

Lists every `sale` invoice in a branch over a date range with its header
figures: invoice number, date, customer (walk-ins stay party-less), gross
total, paid, credit (agel), VAT and the writer. Read-only over `invoices`;
money as exact decimal strings.

The summary ties the register to the ledger of record: `totals.total` equals
the journal's drawer (1000) + AR (1100) debit legs for source=sale, and the
`period_totals` report's `sale` kind — both asserted by tests. At most 1000
rows render (`truncated` marks a cut list); totals are computed in SQL over
every matching invoice so they stay whole-period.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money

from app.models import Invoice, Party, User

_MAX_ROWS = 1000


async def sales_invoices_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Sales invoices for (branch, date_from..date_to), oldest first.

    At most `_MAX_ROWS` header rows render (`truncated` marks a cut list);
    `totals` are computed in SQL over EVERY matching invoice, so the printed
    summary stays whole-period — it still foots to `period_totals` and to the
    journal when the page list is capped.
    """
    where = [Invoice.branch_id == branch_id, Invoice.kind == "sale"]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)

    count, s_total, s_payed, s_agel, s_vat = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Invoice.totalvalue), 0),
                func.coalesce(func.sum(Invoice.payed), 0),
                func.coalesce(func.sum(Invoice.agel), 0),
                func.coalesce(func.sum(Invoice.vat), 0),
            ).where(*where)
        )
    ).one()

    rows = (
        await session.execute(
            select(
                Invoice.id,
                Invoice.invoice_no,
                Invoice.datee,
                Invoice.party_id,
                Party.namee,
                Invoice.subtotal,
                Invoice.discount,
                Invoice.vat,
                Invoice.totalvalue,
                Invoice.payed,
                Invoice.agel,
                User.username,
            )
            .join(Party, Invoice.party_id == Party.id, isouter=True)
            .join(User, Invoice.created_by == User.id, isouter=True)
            .where(*where)
            .order_by(Invoice.datee.asc(), Invoice.id.asc())
            .limit(_MAX_ROWS)
        )
    ).all()

    out_rows = [
        {
            "id": id_,
            "invoice_no": invoice_no,
            "datee": datee.isoformat(),
            "party_id": party_id,
            "party_namee": party_namee,
            "subtotal": money.format2(subtotal),
            "discount": money.format2(discount),
            "vat": money.format2(vat),
            "totalvalue": money.format2(totalvalue),
            "payed": money.format2(payed),
            "agel": money.format2(agel),
            "writer": writer or "",
        }
        for (
            id_,
            invoice_no,
            datee,
            party_id,
            party_namee,
            subtotal,
            discount,
            vat,
            totalvalue,
            payed,
            agel,
            writer,
        ) in rows
    ]

    totals = {
        "count": count,
        "total": money.format2(s_total),
        "payed": money.format2(s_payed),
        "agel": money.format2(s_agel),
        "vat": money.format2(s_vat),
    }

    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "truncated": count > _MAX_ROWS,
        "rows": out_rows,
        "totals": totals,
    }
