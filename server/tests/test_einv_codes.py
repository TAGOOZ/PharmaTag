"""S4.2 (#29) ETA tax-code table — ADR-0002: "wrong tax codes are ETA's #1
rejection reason". Maps PharmaTag line tax_type (plan/00: exempt / 5% / 14%)
to the official SDK codes (sdk.invoicing.eta.gov.eg/codes/tax-types).
"""
import pytest

from app.einvoicing.codes import tax_code


def test_standard_14pc_maps_to_T1_V009_general_item_sales():
    code = tax_code("14%")
    assert code.tax_type == "T1"
    assert code.sub_type == "V009"
    assert code.rate == "14"


def test_reduced_5pc_maps_to_T1_V010_other_rates():
    code = tax_code("5%")
    assert code.tax_type == "T1"
    assert code.sub_type == "V010"
    assert code.rate == "5"


def test_exempt_medicine_maps_to_T1_V003_exempted_good():
    code = tax_code("exempt")
    assert code.tax_type == "T1"
    assert code.sub_type == "V003"
    assert code.rate == "0"


def test_unknown_tax_type_refuses_instead_of_submitting_a_wrong_code():
    with pytest.raises(ValueError):
        tax_code("8%")


def test_every_table_row_pairs_subtype_with_its_own_tax_type():
    from app.einvoicing.codes import ALL_CODES

    for row in ALL_CODES:
        assert row.sub_type in {"V003", "V009", "V010"}


def test_document_lines_and_tax_totals_carry_the_table_codes():
    """The codes ETA actually receives: mixed basket of one exempt medicine
    line and one 14% line -> per-line taxableItems + aggregated taxTotals."""
    from decimal import Decimal
    from types import SimpleNamespace as NS

    from app.einvoicing.documents import build_document

    branch = NS(
        vat_inclusive_prices=True,
        currency="EGP",
        pharname="صيدلية",
        pharmacyid="BR1",
        country="EG",
        governorate="Giza",
        district="Dokki",
        adress="17 St",
    )
    invoice = NS(
        datetimee=None,
        invoice_no="INV-1",
        kind="sale",
        ref_invoice_id=None,
    )

    def line(tax_type, net, vat):
        net, vat = Decimal(net), Decimal(vat)
        return {
            "drug": NS(id=7, drugnamear="دواء", drugname=None),
            "lm": NS(
                line_total=net + vat,
                vat=vat,
                qty=1,
                unit_price=net + vat,
                discount=0,
                tax_type=tax_type,
            ),
        }

    doc = build_document(
        kind="receipt",
        invoice=invoice,
        branch=branch,
        party=None,
        lines=[line("14%", "100.00", "14.00"), line("exempt", "50.00", "0.00")],
        totals={"subtotal": "150.00", "discount": "0", "net": "150.00", "total": "164.00"},
        splits=[("cash", Decimal("164.00"))],
        seller={"rin": "200-173-707", "trade_name": "", "activity_code": ""},
        device_serial=None,
        counter=1,
        previous_uuid="",
    )

    assert [t["subType"] for t in doc["itemData"][0]["taxableItems"]] == ["V009"]
    assert [t["subType"] for t in doc["itemData"][1]["taxableItems"]] == ["V003"]
    assert [(t["subType"], t["amount"]) for t in doc["taxTotals"]] == [
        ("V003", "0.00"),
        ("V009", "14.00"),
    ]
