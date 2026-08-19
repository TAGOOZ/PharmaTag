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
    # the invoice discount is apportioned per line (21/121 → 2.10, remainder
    # 10.00), and each line's VAT re-splits on the discounted total, so VAT
    # reflects the price actually paid.
    assert inv.subtotal == D("121.00")
    assert inv.discount == D("12.10")
    assert inv.total == D("108.90")
    assert inv.net == D("106.58")
    assert inv.vat == D("2.32")


def test_invoice_money_invariant_total_minus_discount_and_net_minus_vat():
    inv = money.invoice_money(
        [(D("2"), D("10.50"), "14%"), (D("1"), D("100.00"), "exempt")],
        disc_percent=D("10"),
        inclusive=True,
    )
    assert inv.total == inv.subtotal - inv.discount
    assert inv.net == inv.total - inv.vat
    assert inv.total == inv.net + inv.vat


def test_invoice_money_exclusive_totals():
    inv = money.invoice_money(
        [(D("2"), D("10.50"), "14%")],
        inclusive=False,
    )
    assert inv.subtotal == D("21.00")
    assert inv.vat == money.round2(D("21.00") * money.tax_rate("14%"))
    assert inv.total == inv.subtotal + inv.vat


# --- edge cases (ticket #1/#2 edge pass) ---


def test_round_half_up_never_bankers_nor_truncates():
    assert money.round2(D("2.675")) == D("2.68")  # classic half-up boundary
    assert money.round2(D("2.685")) == D("2.69")  # half-up (banker's would be 2.68)
    assert money.round2(D("0.005")) == D("0.01")
    assert money.round2(D("0.015")) == D("0.02")
    assert money.round2(D("-0.005")) == D("-0.01")
    assert money.round2(D("-0.004")) == D("-0.00")


def test_round_half_up_large_values():
    assert money.round2(D("9999999999999999.994")) == D("9999999999999999.99")
    assert money.round2(D("9999999999999999.995")) == D("10000000000000000.00")
    assert money.round4(D("0.00005")) == D("0.0001")
    assert money.round4(D("0.00004")) == D("0.0000")


def test_round_half_up_zero():
    assert money.round2(D("0")) == D("0.00")
    assert money.round2(D("0.004")) == D("0.00")


def test_format2_surfaces_half_up_2dp_strings():
    assert money.format2(D("12.345")) == "12.35"  # not banker's 12.34
    assert money.format2(D("12.344")) == "12.34"
    assert money.format2(D("0")) == "0.00"
    assert money.format2(D("-1.005")) == "-1.01"


def test_split_vat_repeating_decimal_5_percent():
    s = money.split_vat(D("1.00"), "5%", inclusive=True)
    assert s.net == D("0.95")
    assert s.vat == D("0.05")
    assert s.gross == s.net + s.vat


def test_split_vat_zero_total():
    for tax in ("exempt", "5%", "14%"):
        s = money.split_vat(D("0"), tax, inclusive=True)
        assert s.gross == s.net == s.vat == D("0.00")


def test_split_vat_negative_total_keeps_invariant():
    s = money.split_vat(D("-1.00"), "14%", inclusive=True)
    assert s.gross == s.net + s.vat
    assert s.net < D("0")
    assert s.vat < D("0")


def test_split_vat_rejects_missing_and_malformed_tax_type():
    with pytest.raises(ValueError):
        money.split_vat(D("1.00"), None)
    with pytest.raises(ValueError):
        money.split_vat(D("1.00"), "14")  # missing %
    with pytest.raises(ValueError):
        money.line_money(D("1"), D("1.00"), "7%")


def test_line_money_zero_qty_and_zero_price():
    line = money.line_money(D("0"), D("10.50"), "14%", inclusive=True)
    assert line.gross == line.line_total == line.net == line.vat == D("0.00")
    line = money.line_money(D("3"), D("0"), "14%", inclusive=True)
    assert line.gross == line.line_total == line.net == line.vat == D("0.00")


def test_invoice_money_vat_is_per_line_never_aggregate():
    """G06 canonical: VAT is split per line and summed — the aggregate split
    (round2(subtotal/1.14)) differs by a piastre here and is NOT used."""
    lines = [(D("1"), D("1.00"), "14%"), (D("1"), D("1.00"), "14%")]
    inv = money.invoice_money(lines, inclusive=True)
    per_line = money.add(
        money.line_money(q, p, t, inclusive=True).vat for q, p, t in lines
    )
    aggregate = money.split_vat(inv.subtotal, "14%", inclusive=True).vat
    assert inv.vat == per_line == D("0.24")
    assert aggregate == D("0.25")  # the alternative that must NOT win
    assert inv.total == inv.net + inv.vat


def test_invoice_money_empty_lines_all_zero():
    inv = money.invoice_money([], inclusive=True)
    assert inv.subtotal == inv.discount == inv.vat == inv.total == inv.net == D("0.00")


def test_add_empty_and_iterable():
    assert money.add() == D("0")
    assert money.add([]) == D("0")
    assert money.add(["0.10", "0.20"]) == D("0.30")


# --- apportionment: invoice discount reduces the VAT base (Egypt Law arts. 10-11) ---


def test_apportion_single_line_takes_whole_discount():
    lines = [money.line_money(D("1"), D("100.00"), "14%", inclusive=True)]
    out = money.apportion_discount(lines, D("10.00"), inclusive=True)
    assert out[0].line_total == D("90.00")
    assert out[0].net == D("78.95")  # round2(90 / 1.14)
    assert out[0].vat == D("11.05")  # 90 - 78.95, never 12.28 on the gross
    assert out[0].discount == D("0.00")  # line-discount field stays line-only


def test_apportion_sum_invariant_and_no_negative_lines():
    lines = [
        money.line_money(D("2"), D("10.50"), "14%", inclusive=True),
        money.line_money(D("1"), D("100.00"), "exempt", inclusive=True),
    ]
    out = money.apportion_discount(lines, D("12.10"), inclusive=True)
    assert money.add(l.line_total for l in out) == money.add(
        l.line_total for l in lines
    ) - D("12.10")
    assert money.add(l.vat for l in out) == D("2.32")
    assert all(l.line_total >= 0 for l in out)


def test_apportion_zero_or_empty_returns_lines_unchanged():
    lines = [money.line_money(D("1"), D("10.00"), "14%", inclusive=True)]
    assert money.apportion_discount(lines, D("0"), inclusive=True) == lines
    assert money.apportion_discount(lines, D("5.00"), inclusive=True)[0] is not lines[0]


def test_apportion_removes_the_piastre_from_vat():
    """Canonical (test_invoice_money_vat_is_per_line_never_aggregate) with a
    discount: the aggregate split on the discounted total still must NOT win."""
    lines = [(D("1"), D("1.00"), "14%"), (D("1"), D("1.00"), "14%")]
    inv = money.invoice_money(lines, disc_percent=D("10"), inclusive=True)
    assert inv.subtotal == D("2.00")
    assert inv.discount == D("0.20")
    assert inv.total == D("1.80")
    assert inv.vat == D("0.22")  # 2 x round2(0.90/1.14) = 2 x 0.11
    aggregate = money.split_vat(inv.total, "14%", inclusive=True).vat
    assert aggregate == D("0.22")  # happens to agree here, still per-line below
    assert inv.net == D("1.58")


def test_apportion_exclusive_splits_vat_on_discounted_net():
    lines = [money.line_money(D("1"), D("100.00"), "14%", inclusive=False)]
    out = money.apportion_discount(lines, D("10.00"), inclusive=False)
    assert out[0].line_total == D("90.00")  # discounted net base
    assert out[0].net == D("90.00")
    assert out[0].vat == D("12.60")  # 14% on the discounted net


def test_apportion_last_line_absorbs_remainder():
    lines = [
        money.line_money(D("1"), D("1.00"), "exempt", inclusive=True),
        money.line_money(D("1"), D("1.00"), "exempt", inclusive=True),
        money.line_money(D("1"), D("1.00"), "exempt", inclusive=True),
    ]
    out = money.apportion_discount(lines, D("1.00"), inclusive=True)
    assert [l.line_total for l in out] == [D("0.67"), D("0.67"), D("0.66")]
    assert money.add(l.line_total for l in out) == D("2.00")