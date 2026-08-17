"""Drug-master pricing & tax unit tests (ticket #8 AC3).

Pure-Decimal, no DB: drives the shared money module (A05 — the single rounding
authority) plus the drug-master price-level helpers in `app.drugs.service`
(`validate_price_levels`, `default_price_now`). Coverage per the acceptance
criteria: tax_type exempt/5%/14% selection, VAT-inclusive net = total ÷ 1.14
per line, price-level half-up 2dp rounding, zero/negative price rejection,
price_now vs price, and the money-never-float rule.
"""
from decimal import Decimal

import pytest

from app.core import money
from app.drugs import service

D = Decimal


# ---------------------------------------------------------------------------
# tax_type selection: each class resolves to its G06 rate
# ---------------------------------------------------------------------------
def test_tax_type_selection_maps_each_class_to_its_rate():
    assert money.tax_rate("exempt") == D("0")
    assert money.tax_rate("5%") == D("0.05")
    assert money.tax_rate("14%") == D("0.14")


def test_tax_type_selection_rejects_unknown_class():
    with pytest.raises(ValueError):
        money.tax_rate("20%")


# ---------------------------------------------------------------------------
# VAT-inclusive retail: taxable net = total ÷ 1.14, per line (G06)
# ---------------------------------------------------------------------------
def test_public_price_net_is_total_divided_by_1_14():
    split = money.split_vat(D("114.00"), "14%", inclusive=True)
    assert split.net == D("100.00") == D("114.00") / D("1.14")
    assert split.vat == D("14.00")
    assert split.gross == split.net + split.vat


def test_public_price_split_rounds_half_up_to_2dp():
    split = money.split_vat(D("1.00"), "14%", inclusive=True)
    assert split.net == D("0.88")
    assert split.vat == D("0.12")


def test_exempt_drug_price_has_no_vat_share():
    split = money.split_vat(D("114.00"), "exempt", inclusive=True)
    assert split.net == D("114.00")
    assert split.vat == D("0.00")


def test_5_percent_device_price_split():
    split = money.split_vat(D("105.00"), "5%", inclusive=True)
    assert split.net == D("100.00")
    assert split.vat == D("5.00")


# ---------------------------------------------------------------------------
# price-level rounding: half-up at 2dp when a 4dp price is displayed (plan/01)
# ---------------------------------------------------------------------------
def test_format2_rounds_half_up():
    assert money.format2(D("12.345")) == "12.35"
    assert money.format2(D("12.344")) == "12.34"
    assert money.format2(D("12.3455")) == "12.35"
    assert money.format2(D("0")) == "0.00"


def test_price_level_rounding_is_never_half_even():
    # half-even would give 12.34 for 12.345; the standard mandates half-up
    assert money.format2(D("12.345")) == "12.35"


def test_round_half_up_2dp_for_price_levels():
    assert money.round_half_up(D("1.005"), 2) == D("1.01")
    assert money.round_half_up(D("1.004"), 2) == D("1.00")


# ---------------------------------------------------------------------------
# zero/negative price rejection (validation, no floats)
# ---------------------------------------------------------------------------
def test_zero_price_is_allowed_at_boundary():
    assert service.validate_price_levels(D("0"), D("0"), D("0")) is None


def test_negative_public_price_rejected():
    with pytest.raises(ValueError):
        service.validate_price_levels(D("-0.01"), D("0"), D("0"))


def test_negative_wholesale_price_rejected():
    with pytest.raises(ValueError):
        service.validate_price_levels(D("10"), D("-1"), D("0"))


def test_negative_cost_price_rejected():
    with pytest.raises(ValueError):
        service.validate_price_levels(D("10"), D("8"), D("-2"))


def test_float_price_input_rejected_money_never_float():
    with pytest.raises(TypeError):
        service.validate_price_levels(12.34, D("0"), D("0"))
    with pytest.raises(TypeError):
        money.dec(1.25)


# ---------------------------------------------------------------------------
# price_now vs price: current price defaults to the public price on create
# ---------------------------------------------------------------------------
def test_price_now_defaults_to_public_price():
    assert service.default_price_now(None, D("12.50")) == D("12.50")


def test_price_now_passed_through_when_given():
    assert service.default_price_now(D("11.00"), D("12.50")) == D("11.00")