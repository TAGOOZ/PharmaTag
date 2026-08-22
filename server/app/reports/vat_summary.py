"""VAT/tax summary — ملخص ضريبة القيمة المضافة (S3.5, ticket #27; ADR-0001).

The Egyptian monthly-return mirror (Form 10 / نموذج 10 ق.ض.ق.م): output
(ضريبة المخرجات) and input (ضريبة المدخلات) sections × rate buckets
(exempt / 5% / 14%), each row carrying the taxable net and the VAT.

Direction derives from the document KIND — which is exactly the journal
source the posting engine stamps (ADR-0001): `sale`/`sale_return` legs are
output, `purchase`/`purchase_return` legs are input; returns net NEGATIVE
inside their bucket. Rate splits come from `invoice_lines.tax_type`, never
from the chart.

Per-line taxable net follows each side's price model (plan/00 G06/G14):
sales/returns are VAT-INCLUSIVE so net = line_total − vat_amount; purchases/
returns are VAT-EXCLUSIVE so the base IS line_total. The reconciliation tests
prove Σvat(lines) == Δ journal(2100) restricted to those sources.

Foot: output VAT − input VAT = صافي الضريبة المستحقة; a negative result is a
credit carried forward (رصيد دائن). Input-VAT apportionment against exempt
output is deliberately NOT automatic — it is the accountant's call.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import money
from app.models import Invoice, InvoiceLine

from app.reports.period_window import iso, resolve_period

_RATE_ORDER = ("exempt", "5%", "14%")
_OUTPUT_KINDS = ("sale", "sale_return")
_RETURN_KINDS = ("sale_return", "purchase_return")


def _section(rates: dict[str, tuple[Decimal, Decimal]]) -> dict:
    zero = money.dec("0")
    ordered = [
        {
            "tax_type": rate,
            "net": money.format2(rates.get(rate, (zero, zero))[0]),
            "vat": money.format2(rates.get(rate, (zero, zero))[1]),
        }
        for rate in _RATE_ORDER
    ]
    total_net = sum((n for n, _ in rates.values()), money.dec("0"))
    total_vat = sum((v for _, v in rates.values()), money.dec("0"))
    return {
        "rates": ordered,
        "total_net": money.format2(total_net),
        "total_vat": money.format2(total_vat),
    }


async def vat_summary_report(
    session: AsyncSession,
    *,
    branch_id: int,
    month: Optional[int],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """Output/input rate buckets over the resolved window."""
    period, start, end = resolve_period(month, year, date_from, date_to)

    sale_side = Invoice.kind.in_(_OUTPUT_KINDS)
    sign = case(
        (Invoice.kind.in_(_RETURN_KINDS), -1),
        else_=1,
    )
    line_net = case(
        (sale_side, InvoiceLine.line_total - InvoiceLine.vat_amount),
        else_=InvoiceLine.line_total,
    )
    direction = case((sale_side, "output"), else_="input")

    rows = (
        await session.execute(
            select(
                direction,
                InvoiceLine.tax_type,
                func.coalesce(func.sum(sign * line_net), 0),
                func.coalesce(func.sum(sign * InvoiceLine.vat_amount), 0),
            )
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .where(
                InvoiceLine.branch_id == branch_id,
                Invoice.kind.in_(("sale", "sale_return", "purchase", "purchase_return")),
                # NO status filter — deliberately identical population to
                # period_totals (which also reads every invoice row), so the
                # AC reconciliation between the two can never silently
                # diverge on a legacy non-saved row
                Invoice.datee >= start,
                Invoice.datee <= end,
            )
            .group_by(direction, InvoiceLine.tax_type)
        )
    ).all()

    output_rates: dict[str, tuple] = {}
    input_rates: dict[str, tuple] = {}
    for dirn, tax_type, net, vat in rows:
        bucket = output_rates if dirn == "output" else input_rates
        bucket[tax_type] = (money.dec(net), money.dec(vat))

    output = _section(output_rates)
    inp = _section(input_rates)

    net_vat = money.dec(output["total_vat"]) - money.dec(inp["total_vat"])
    return {
        "branch_id": branch_id,
        "period": {
            "month": period["month"],
            "year": period["year"],
            "date_from": iso(period["date_from"]),
            "date_to": iso(period["date_to"]),
        },
        "output": output,
        "input": inp,
        "net_vat_payable": money.format2(net_vat),
        "credit_balance": net_vat < 0,
    }
