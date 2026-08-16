"""money.py — the single rounding authority (plan/02 A05).

Every money value in PharmaTag passes through this module. It is a DEEP module:
a small public interface that absorbs all the rounding and VAT-split logic so no
other layer ever touches a float or re-derives a rate.

Invariants (each guaranteed by construction, asserted in tests):
  * gross = net + vat                    — for every VAT split
  * line_total = net + vat = gross - discount — for every invoice line
  * total = subtotal - discount          — VAT-inclusive invoices
  * net = total - vat                    — invoice taxable base

Rules locked from plan/00 + plan/02:
  * Money is exact Decimal; float input is rejected outright (TypeError).
  * Rounding is round-half-up: 2dp for money, 4dp for per-unit qty/price.
  * Per-line tax engine (G06): each line resolves its own tax_type
    (exempt / 5% / 14%). Egypt retail is VAT-INCLUSIVE: for taxable lines the
    net is derived per line as gross / (1 + rate), never double-taxed.
    Discount is taken off the inclusive gross and does not retroactively
    re-apportion VAT (the per-line split is computed on the discounted total).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

__all__ = [
    "VatSplit",
    "LineMoney",
    "InvoiceMoney",
    "dec",
    "add",
    "round_half_up",
    "round2",
    "round4",
    "tax_rate",
    "split_vat",
    "line_money",
    "invoice_money",
]

TAX_RATES: dict[str, Decimal] = {
    "exempt": Decimal("0"),
    "5%": Decimal("0.05"),
    "14%": Decimal("0.14"),
}


def dec(value) -> Decimal:
    """Coerce int/str/Decimal to Decimal. Floats are rejected — never float."""
    if isinstance(value, float):
        raise TypeError("money must be exact decimal; float input is rejected")
    return Decimal(value)


def add(*values) -> Decimal:
    """Exact decimal sum of the given money values (no float drift).

    Accepts varargs (`add("0.10", "0.20")`) or a single iterable
    (`add(line.gross for line in lines)`).
    """
    if len(values) == 1 and not isinstance(values[0], (Decimal, int, str)):
        values = tuple(values[0])
    return sum((dec(v) for v in values), Decimal("0"))


def round_half_up(value, places: int = 2) -> Decimal:
    """Round-half-up at `places` decimal places (0.01 for money, 0.0001 for units)."""
    quantum = Decimal(1).scaleb(-places)
    return dec(value).quantize(quantum, rounding=ROUND_HALF_UP)


def round2(value) -> Decimal:
    return round_half_up(value, 2)


def round4(value) -> Decimal:
    return round_half_up(value, 4)


def tax_rate(tax_type: str) -> Decimal:
    """Resolve a line's tax_type to its decimal rate (G06)."""
    try:
        return TAX_RATES[tax_type]
    except KeyError:
        raise ValueError(f"unknown tax_type {tax_type!r}") from None


@dataclass(frozen=True)
class VatSplit:
    """A VAT split. `gross` is the amount charged, `net` the taxable base."""

    gross: Decimal
    net: Decimal
    vat: Decimal


def split_vat(total, tax_type: str, *, inclusive: bool = True) -> VatSplit:
    """Split a total into net (taxable base) + vat for the line's tax_type.

    inclusive=True  (Egypt retail): total is gross-inclusive; net = total/(1+r).
    inclusive=False (wholesale):    total is the net base; vat added on top.
    """
    gross = dec(total)
    rate = tax_rate(tax_type)
    if inclusive:
        net = round2(gross / (Decimal("1") + rate))
        return VatSplit(gross=gross, net=net, vat=gross - net)
    net = gross
    vat = round2(net * rate)
    return VatSplit(gross=net + vat, net=net, vat=vat)


@dataclass(frozen=True)
class LineMoney:
    """Money resolved for one invoice line (plan/02 §16.4 canonical order)."""

    qty: Decimal
    unit_price: Decimal
    tax_type: str
    gross: Decimal  # line total before discount
    discount: Decimal
    line_total: Decimal  # gross - discount
    net: Decimal  # taxable base inside line_total
    vat: Decimal


def line_money(qty, unit_price, tax_type: str, *, disc_percent=None,
               inclusive: bool = True) -> LineMoney:
    """Compute a single line: line_total = round2(round4(qty) x unit_price).

    An optional line discount (percent, 10 = 10%) is applied to the gross before
    the VAT split; the split then works on the discounted total.
    """
    qty_r = round4(dec(qty))
    price = dec(unit_price)
    gross = round2(qty_r * price)
    discount = (
        round2(gross * dec(disc_percent) / Decimal("100"))
        if disc_percent is not None
        else Decimal("0")
    )
    line_total = gross - discount
    split = split_vat(line_total, tax_type, inclusive=inclusive)
    return LineMoney(
        qty=qty_r,
        unit_price=price,
        tax_type=tax_type,
        gross=gross,
        discount=discount,
        line_total=line_total,
        net=split.net,
        vat=split.vat,
    )


@dataclass(frozen=True)
class InvoiceMoney:
    """Header totals for an invoice (plan/02 §16.4).

    VAT-inclusive (Egypt): total = subtotal - discount, net = total - vat.
    VAT-exclusive:         total = subtotal - discount + vat.
    """

    subtotal: Decimal
    discount: Decimal
    vat: Decimal
    total: Decimal
    net: Decimal


def invoice_money(lines, disc_percent=None, *, inclusive: bool = True) -> InvoiceMoney:
    """Resolve a whole invoice from raw (qty, unit_price, tax_type) lines.

    Subtotal sums the per-line gross totals; a single invoice-level percent
    discount is applied to the subtotal; VAT is the sum of per-line VAT splits
    (per-line rounding is canonical, G06).
    """
    resolved = [line_money(qty, price, tax, inclusive=inclusive)
                for qty, price, tax in lines]
    subtotal = add(l.gross for l in resolved)
    discount = (
        round2(subtotal * dec(disc_percent) / Decimal("100"))
        if disc_percent is not None
        else Decimal("0")
    )
    total = round2(subtotal - discount + (Decimal("0") if inclusive else add(l.vat for l in resolved)))
    vat = add(l.vat for l in resolved)
    return InvoiceMoney(
        subtotal=subtotal,
        discount=discount,
        vat=vat,
        total=total,
        net=total - vat if inclusive else subtotal - discount,
    )