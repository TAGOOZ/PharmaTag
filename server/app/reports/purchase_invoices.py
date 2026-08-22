"""Purchase-invoice register (S3.4, ticket #26; RPT-P01).

Lists purchase LINES over a date range — invoice number, date, supplier,
drug, qty, discounted net unit cost, VAT amount, line total, and the created
batch's randomid + expiry (the EDTS/EDA traceability columns). Read-only over
`invoices` × `invoice_lines`; money as exact decimal strings.

The summary ties the register to the ledger of record: `totals.total` equals
the journal's stock (1200) + input-VAT (2100) debit legs for source=purchase,
and the `period_totals` report's `purchase` kind — both tested.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money

from app.models import Drug, Invoice, InvoiceLine, Party, StockBatch

LINE_DP = 4
_MAX_ROWS = 1000


def _fmt4(value) -> str:
    return f"{money.dec(value):.{LINE_DP}f}"


async def purchase_invoices_report(
    session: AsyncSession,
    *,
    branch_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Purchase lines for (branch, date_from..date_to), oldest first.

    At most `_MAX_ROWS` line rows render (`truncated` marks a cut list);
    `totals` are computed in SQL over EVERY matching line so the printed
    summary stays whole-period — it still foots to `period_totals` and to the
    journal when the page list is capped.
    """
    where = [Invoice.branch_id == branch_id, Invoice.kind == "purchase"]
    if date_from is not None:
        where.append(Invoice.datee >= date_from)
    if date_to is not None:
        where.append(Invoice.datee <= date_to)

    line_count, invoice_count, s_net, s_vat = (
        await session.execute(
            select(
                func.count(),
                func.count(func.distinct(Invoice.id)),
                func.coalesce(func.sum(InvoiceLine.line_total), 0),
                func.coalesce(func.sum(InvoiceLine.vat_amount), 0),
            )
            .select_from(Invoice)
            .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
            .where(*where)
        )
    ).one()

    rows = (
        await session.execute(
            select(
                Invoice.id,
                Invoice.invoice_no,
                Invoice.datee,
                Party.namee,
                Drug.drugname,
                InvoiceLine.qty,
                InvoiceLine.cost,
                InvoiceLine.vat_amount,
                InvoiceLine.line_total,
                InvoiceLine.expire,
                StockBatch.randomid,
            )
            .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
            .join(Party, Invoice.party_id == Party.id, isouter=True)
            .join(Drug, InvoiceLine.drug_id == Drug.id)
            .join(StockBatch, InvoiceLine.batch_id == StockBatch.id, isouter=True)
            .where(*where)
            .order_by(Invoice.datee.asc(), Invoice.id.asc(), InvoiceLine.id.asc())
            .limit(_MAX_ROWS)
        )
    ).all()

    out_rows = [
        {
            "invoice_id": invoice_id,
            "invoice_no": invoice_no,
            "datee": datee.isoformat(),
            "supplier_namee": supplier_namee,
            "drugname": drugname,
            "qty": _fmt4(qty),
            "unit_cost": _fmt4(cost),
            "vat_amount": money.format2(vat_amount),
            "line_total": money.format2(line_total),
            "expire": expire.isoformat() if expire else None,
            "batch_randomid": batch_randomid or "",
        }
        for (
            invoice_id,
            invoice_no,
            datee,
            supplier_namee,
            drugname,
            qty,
            cost,
            vat_amount,
            line_total,
            expire,
            batch_randomid,
        ) in rows
    ]

    totals = {
        "line_count": line_count,
        "invoice_count": invoice_count,
        # G14: purchases are B2B VAT-EXCLUSIVE — the gross is net + VAT,
        # which is what reconciles to period_totals and the journal
        "net": money.format2(s_net),
        "total": money.format2(s_net + s_vat),
        "vat": money.format2(s_vat),
    }

    return {
        "branch_id": branch_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "truncated": line_count > _MAX_ROWS,
        "rows": out_rows,
        "totals": totals,
    }
