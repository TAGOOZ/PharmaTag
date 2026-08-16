"""money.py — the single rounding authority (A05), unit-tested.

Spec source: plan/02 §Cross-cutting foundations + G06 (per-line tax_type,
VAT-inclusive retail). All assertions are pure-Decimal; no floats anywhere.
"""
from decimal import Decimal

import pytest

from app.core import money

D = Decimal


def test_dec_rejects_floats():
    with pytest.raises(TypeError):
        money.dec(1.25)


def test_dec_accepts_int_str_and_decimal():
    assert money.dec(2) == D("2")
    assert money.dec("2.50") == D("2.50")
    assert money.dec(D("2.50")) == D("2.50")


def test_add_is_exact_decimal_sum():
    assert money.add("0.10", "0.20") == D("0.30")


def test_round_half_up_two_places():
    assert money.round_half_up(D("1.005"), 2) == D("1.01")
    assert money.round_half_up(D("1.004"), 2) == D("1.00")
    assert money.round_half_up(D("-1.005"), 2) == D("-1.01")


def test_round_half_up_four_places():
    assert money.round_half_up(D("1.00005"), 4) == D("1.0001")
    assert money.round_half_up(D("1.00004"), 4) == D("1.0000")


def test_round2_and_round4_helpers():
    assert money.round2(D("1.005")) == D("1.01")
    assert money.round4(D("1.00005")) == D("1.0001")


def test_tax_rate_mapping():
    assert money.tax_rate("exempt") == D("0")
    assert money.tax_rate("5%") == D("0.05")
    assert money.tax_rate("14%") == D("0.14")


def test_tax_rate_unknown_raises():
    with pytest.raises(ValueError):
        money.tax_rate("99%")


def test_split_vat_inclusive_14_percent():
    s = money.split_vat(D("114.00"), "14%", inclusive=True)
    assert s.net == D("100.00")
    assert s.vat == D("14.00")
    assert s.gross == D("114.00")


def test_split_vat_inclusive_exempt():
    s = money.split_vat(D("114.00"), "exempt", inclusive=True)
    assert s.net == D("114.00")
    assert s.vat == D("0.00")
    assert s.gross == D("114.00")


def test_split_vat_inclusive_5_percent():
    s = money.split_vat(D("105.00"), "5%", inclusive=True)
    assert s.net == D("100.00")
    assert s.vat == D("5.00")


def test_split_vat_inclusive_rounds_half_up():
    s = money.split_vat(D("1.00"), "14%", inclusive=True)
    assert s.net == D("0.88")
    assert s.vat == D("0.12")


def test_split_vat_exclusive_14_percent():
    s = money.split_vat(D("100.00"), "14%", inclusive=False)
    assert s.net == D("100.00")
    assert s.vat == D("14.00")
    assert s.gross == D("114.00")


def test_split_vat_invariant_gross_equals_net_plus_vat():
    for total, tax in [(D("114.00"), "14%"), (D("1.00"), "14%"), (D("7.50"), "5%")]:
        for inclusive in (True, False):
            s = money.split_vat(total, tax, inclusive=inclusive)
            assert s.gross == s.net + s.vat, (total, tax, inclusive, s)


def test_line_money_inclusive_split():
    line = money.line_money(D("2"), D("10.50"), "14%", inclusive=True)
    assert line.gross == D("21.00")
    assert line.line_total == D("21.00")
    assert line.net == D("18.42")
    assert line.vat == D("2.58")


def test_line_money_exempt_no_vat():
    line = money.line_money(D("3"), D("5.00"), "exempt", inclusive=True)
    assert line.line_total == D("15.00")
    assert line.vat == D("0.00")
    assert line.net == D("15.00")


def test_line_money_with_line_discount():
    line = money.line_money(D("2"), D("10.50"), "14%", disc_percent=D("10"), inclusive=True)
    assert line.gross == D("21.00")
    assert line.discount == D("2.10")
    assert line.line_total == D("18.90")
    assert line.net == D("16.58")
    assert line.vat == D("2.32")


def test_line_money_rounds_qty_to_four_places():
    line = money.line_money(D("2.34567"), D("10.00"), "exempt", inclusive=True)
    assert line.gross == D("23.46")


def test_line_money_invariant_line_total_equals_net_plus_vat():
    line = money.line_money(D("2"), D("10.50"), "14%", disc_percent=D("10"), inclusive=True)
    assert line.line_total == line.net + line.vat


def test_invoice_money_inclusive_totals():
    inv = money.invoice_money(
        [(D("2"), D("10.50"), "14%"), (D("1"), D("100.00"), "exempt")],
        inclusive=True,
    )
    assert inv.subtotal == D("121.00")
    assert inv.discount == D("0.00")
    assert inv.total == D("121.00")
    assert inv.vat == D("2.58")
    assert inv.net == D("118.42")


def test_invoice_money_inclusive_with_discount():
    inv = money.invoice_money(
        [(D("2"), D("10.50"), "14%"), (D("1"), D("100.00"), "exempt")],
        disc_percent=D("10"),
        inclusive=True,
    )
    assert inv.subtotal == D("121.00")
    assert inv.discount == D("12.10")
    assert inv.total == D("108.90")
    assert inv.net == D("106.32")


def test_invoice_money_invariant_total_minus_discount_and_net_minus_vat():
    inv = money.invoice_money(
        [(D("2"), D("10.50"), "14%"), (D("1"), D("100.00"), "exempt")],
        disc_percent=D("10"),
        inclusive=True,
    )
    assert inv.total == inv.subtotal - inv.discount
    assert inv.net == inv.total - inv.vat


def test_invoice_money_exclusive_totals():
    inv = money.invoice_money(
        [(D("2"), D("10.50"), "14%")],
        inclusive=False,
    )
    assert inv.subtotal == D("21.00")
    assert inv.vat == money.round2(D("21.00") * money.tax_rate("14%"))
    assert inv.total == inv.subtotal + inv.vat