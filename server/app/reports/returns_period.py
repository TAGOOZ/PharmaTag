"""Returns register (S3.4, ticket #26; RPT-S02 + purchase returns).

Lists sale and purchase RETURN invoices over a date range with the invoice
each one reverses (`ref_invoice_no`). Return values leave as NEGATIVE figures:
Egyptian VAT law treats credit notes as reducing the period's liability, so a
return is never positive income — the summary's figures equal minus
`period_totals`'s return kinds (tested).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core import money

from app.models import Invoice, Party

_MAX_ROWS = 1000


def _neg2(value) -> str:
    """Negated 2dp figure; a zero component stays '0.00', never '-0.00'."""
    dec = money.dec(value)
    return money.format2(-dec) if dec else "0.00"


async def returns_period_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Return invoices for (branch, date_from..date_to), oldest first.

    At most `_MAX_ROWS` rows render (`truncated` marks a cut list); `totals`
    are computed in SQL over EVERY matching return so the printed summary
    stays whole-period — it still equals minus `period_totals`'s return kinds
    when the page list is capped.
    """
    ref = aliased(Invoice)
    where = [
        Invoice.branch_id == branch_id,
        Invoice.kind.in_(("sale_return", "purchase_return")),
    ]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)

    count, s_sales, s_purch = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(
                        case(
                            (Invoice.kind == "sale_return", Invoice.totalvalue),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (Invoice.kind == "purchase_return", Invoice.totalvalue),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(*where)
        )
    ).one()

    rows = (
        await session.execute(
            select(
                Invoice.id,
                Invoice.invoice_no,
                Invoice.kind,
                Invoice.datee,
                Party.namee,
                ref.invoice_no,
                Invoice.subtotal,
                Invoice.discount,
                Invoice.vat,
                Invoice.totalvalue,
            )
            .join(ref, Invoice.ref_invoice_id == ref.id, isouter=True)
            .join(Party, Invoice.party_id == Party.id, isouter=True)
            .where(*where)
            .order_by(Invoice.datee.asc(), Invoice.id.asc())
            .limit(_MAX_ROWS)
        )
    ).all()

    out_rows = [
        {
            "id": id_,
            "invoice_no": invoice_no,
            "kind": kind,
            "datee": datee.isoformat(),
            "party_namee": party_namee,
            "ref_invoice_no": ref_invoice_no,
            "subtotal": _neg2(subtotal),
            "discount": _neg2(discount),
            "vat": _neg2(vat),
            "totalvalue": _neg2(totalvalue),
        }
        for (
            id_,
            invoice_no,
            kind,
            datee,
            party_namee,
            ref_invoice_no,
            subtotal,
            discount,
            vat,
            totalvalue,
        ) in rows
    ]

    sales_ret = -money.dec(s_sales)
    purch_ret = -money.dec(s_purch)
    totals = {
        "count": count,
        "sales_returns": money.format2(sales_ret),
        "purchase_returns": money.format2(purch_ret),
        "net": money.format2(sales_ret + purch_ret),
    }

    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "truncated": count > _MAX_ROWS,
        "rows": out_rows,
        "totals": totals,
    }
