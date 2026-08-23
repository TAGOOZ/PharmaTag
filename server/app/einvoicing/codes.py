"""ETA tax-code table (S4.2, #29; ADR-0002 consequence: "tax-code mapping
becomes a tested table — wrong tax codes are ETA's #1 rejection reason").

Maps PharmaTag line tax_type (plan/00: exempt medicines / 5% devices /
14% standard) to codes from the official SDK tax-types table
(https://sdk.invoicing.eta.gov.eg/codes/tax-types/):

  14%    -> T1/V009  General Item sales (سلع عامة)
  5%     -> T1/V010  Other Rates        (نسب ضريبة أخرى)
  exempt -> T1/V003  Exempted good      (سلعة أو خدمة معفاة)

The provisional S4.1 code emitted V001 (= Export) everywhere; this table is
the corrected, tested source both line taxableItems and taxTotals build from.
"""
from __future__ import annotations

from typing import NamedTuple


class TaxCode(NamedTuple):
    tax_type: str
    sub_type: str
    rate: str


ALL_CODES: tuple[TaxCode, ...] = (
    TaxCode(tax_type="T1", sub_type="V009", rate="14"),
    TaxCode(tax_type="T1", sub_type="V010", rate="5"),
    TaxCode(tax_type="T1", sub_type="V003", rate="0"),
)

_TABLE: dict[str, TaxCode] = {
    "14%": ALL_CODES[0],
    "5%": ALL_CODES[1],
    "exempt": ALL_CODES[2],
}


def tax_code(line_tax_type: str) -> TaxCode:
    try:
        return _TABLE[line_tax_type]
    except KeyError:
        raise ValueError(
            f"no ETA tax code for line tax_type {line_tax_type!r}; "
            "refusing to submit a wrong code"
        ) from None
