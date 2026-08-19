"""Sale pricing: price-level resolution and header money aggregation.

Canonical money lives in `app.core.money` (`line_money`, `add`, `round2`); this
module turns raw sale lines into resolved prices and header totals.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from app.core.money import add, apportion_discount, dec, round2
from app.models import Drug

DISCOUNT_OVERFLOW = HTTPException(
    status.HTTP_400_BAD_REQUEST, "discount exceeds sale total"
)


def _price_for(drug: Drug, price_level: str) -> Decimal:
    """Pick the drug's sale price from its three price levels (plan/00 G06)."""
    if price_level == "public":
        return dec(drug.price or 0)
    if price_level == "wholesale":
        return dec(drug.price_wholesale or 0)
    if price_level == "cost":
        return dec(drug.price_cost or 0)
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST, f"unknown price_level {price_level!r}"
    )


def _sale_totals(resolved, disc_percent, *, inclusive: bool) -> dict:
    """Header totals from per-line canonical money (mirrors money.invoice_money:
    subtotal = Σ gross, discount = line discounts + invoice-level percent,
    vat = Σ per-line VAT split on the DISCOUNTED totals, total/net per the
    inclusive flag).

    The invoice-level discount is apportioned to each line (item["lm"] is
    replaced with the apportioned LineMoney) before the VAT split, so the
    taxable base is the discounted price actually paid (Egypt Law 67/2016 arts.
    10-11). Callers MUST read item["lm"] after calling this.
    """
    subtotal = add(item["lm"].gross for item in resolved)
    line_disc = add(item["lm"].discount for item in resolved)
    invoice_disc = (
        round2(subtotal * dec(disc_percent) / Decimal("100"))
        if disc_percent is not None
        else Decimal("0")
    )
    discount = line_disc + invoice_disc
    if discount > subtotal:
        raise DISCOUNT_OVERFLOW
    for item, lm in zip(
        resolved,
        apportion_discount(
            [item["lm"] for item in resolved], invoice_disc, inclusive=inclusive
        ),
    ):
        item["lm"] = lm
    vat = add(item["lm"].vat for item in resolved)
    total = round2(subtotal - discount + (vat if not inclusive else Decimal("0")))
    if total < 0:
        raise DISCOUNT_OVERFLOW
    net = total - vat if inclusive else subtotal - discount
    return {
        "subtotal": subtotal,
        "discount": discount,
        "vat": vat,
        "total": total,
        "net": net,
    }