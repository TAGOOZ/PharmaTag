"""S4.1 e-invoice toolkit contract tests (ticket #28, ADR-0002).

The serializer is contract-pinned to the ETA official Integration Toolkit via
the SDK's own published sample pair (one-doc.json → one-doc-serialized.json.txt
from sdk.invoicing.eta.gov.eg/document-serialization-approach) — the serialized
string must reproduce byte-for-byte. UUID and QR follow the Receipt Issuance
FAQ procedures; the golden fixtures pin the outputs so any refactor that drifts
the chain turns red. Egypt is NOT ZATCA-TLV.
"""
import base64
import hashlib
import json
from pathlib import Path

import pytest

from app.einvoicing.toolkit import (
    PROD_PORTAL_URL,
    qr_png_data_uri,
    qr_string,
    receipt_uuid,
    serialize,
    sha256_hex,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "einvoicing"


def _load_doc():
    # parse_int/parse_float as str keeps every number token verbatim ("10.50"
    # stays "10.50") — values are hashed exactly as written in the document.
    return json.loads(
        (FIXTURES / "one-doc.json").read_text(encoding="utf-8"),
        parse_float=str,
        parse_int=str,
    )


def test_serialize_reproduces_official_sdk_sample_byte_for_byte():
    """Golden fixture straight from the official SDK serialization page."""
    expected = (FIXTURES / "one-doc-serialized.json.txt").read_text(
        encoding="utf-8"
    ).strip()
    assert serialize(_load_doc()) == expected


def test_serialize_array_name_repeats_per_element():
    doc = {"itemData": [{"totalSale": "94.5"}, {"totalSale": "13437.843"}]}
    assert (
        serialize(doc)
        == '"ITEMDATA""ITEMDATA""TOTALSALE""94.5""ITEMDATA""TOTALSALE""13437.843"'
    )


def test_serialize_uppercases_names_and_keeps_values_verbatim():
    doc = {"header": {"receiptNumber": "ZHFGG221", "exchangeRate": "0.12345"}}
    assert (
        serialize(doc)
        == '"HEADER""RECEIPTNUMBER""ZHFGG221""EXCHANGERATE""0.12345"'
    )


def test_serialize_skips_nulls_and_encodes_booleans_json_style():
    doc = {"a": None, "b": True, "c": False, "d": "x"}
    assert serialize(doc) == '"B""true""C""false""D""x"'


def test_receipt_uuid_is_sha256_over_base_with_empty_uuid():
    payload = {
        "header": {"receiptNumber": "R-1", "uuid": "", "previousUUID": ""},
        "totalAmount": "1000.000",
    }
    # an empty-string value serializes as "" (two quotes) after its name
    serialized = (
        '"HEADER""RECEIPTNUMBER""R-1"'
        '"UUID"""'
        '"PREVIOUSUUID"""'
        '"TOTALAMOUNT""1000.000"'
    )
    assert serialize(payload) == serialized
    assert receipt_uuid(payload) == hashlib.sha256(serialized.encode()).hexdigest()
    assert len(receipt_uuid(payload)) == 64


def test_receipt_uuid_ignores_any_uuid_already_present():
    payload = {"header": {"receiptNumber": "R-1", "uuid": "", "previousUUID": ""}}
    polluted = {
        "header": {
            "receiptNumber": "R-1",
            "uuid": "DEADBEEF",
            "previousUUID": "",
        }
    }
    assert receipt_uuid(payload) == receipt_uuid(polluted)


def test_receipt_uuid_changes_when_previous_uuid_changes():
    base = {"header": {"receiptNumber": "R-1", "previousUUID": ""}, "totalAmount": "10"}
    chained = {"header": {"receiptNumber": "R-1", "previousUUID": "abc"}, "totalAmount": "10"}
    assert receipt_uuid(base) != receipt_uuid(chained)


def test_sha256_hex_known_vector():
    assert sha256_hex("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_qr_string_matches_faq_template_example_exactly():
    """The literal example from sdk.invoicing.eta.gov.eg Receipt Issuance FAQ."""
    qr = qr_string(
        uuid="68e656b251e67e8358bef8483ab0d51c6619f3e7a1a9f0e75838d41ff368f320",
        datetime_issued_utc="2022-02-19T02:00Z",
        total="1000.000",
        issuer_rin="674859545",
        portal_url=PROD_PORTAL_URL,
    )
    assert qr == (
        "http://invoicing.eta.gov.eg/receipts/search/"
        "68e656b251e67e8358bef8483ab0d51c6619f3e7a1a9f0e75838d41ff368f320"
        "/share/2022-02-19T02:00Z#Total:1000.000,IssuerRIN:674859545"
    )


def test_qr_string_formats_datetime_to_minutes_utc():
    from datetime import datetime, timezone

    dt = datetime(2026, 8, 23, 5, 9, 12, tzinfo=timezone.utc)
    qr = qr_string(
        uuid="u", datetime_issued_utc=dt, total="10.00", issuer_rin="1"
    )
    assert "/share/2026-08-23T05:09Z#" in qr


def test_qr_string_normalizes_seconds_precision_iso_to_minutes():
    """The FAQ example carries minutes precision; a seconds-precision ISO
    stamp (as stored on the document header) must produce the same URL."""
    minutes = qr_string(
        uuid="u", datetime_issued_utc="2022-02-19T02:00Z", total="10.00",
        issuer_rin="1",
    )
    seconds = qr_string(
        uuid="u", datetime_issued_utc="2022-02-19T02:00:59Z", total="10.00",
        issuer_rin="1",
    )
    assert seconds == minutes


@pytest.mark.parametrize("portal", [PROD_PORTAL_URL, "https://preprod.invoicing.eta.gov.eg"])
def test_qr_png_data_uri_is_decodable_png(portal):
    qr = qr_string(
        uuid="68e656b251e67e8358bef8483ab0d51c6619f3e7a1a9f0e75838d41ff368f320",
        datetime_issued_utc="2022-02-19T02:00Z",
        total="1000.000",
        issuer_rin="674859545",
        portal_url=portal,
    )
    uri = qr_png_data_uri(qr)
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.removeprefix("data:image/png;base64,"))
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_golden_fixture_file_pins_a_full_receipt():
    """Receipt-shaped golden fixture: uuid + qr pinned; drift turns red.

    The fixtures were produced by this toolkit's documented-algorithm
    implementation; re-pinning against the official preprod toolkit binary is
    the release-gate step recorded in the ticket close comment.
    """
    fixtures = json.loads((FIXTURES / "receipt_fixtures.json").read_text())
    for case in fixtures["receipts"]:
        payload = case["payload"]
        assert receipt_uuid(payload) == case["expected_uuid"]
        qr = qr_string(
            uuid=receipt_uuid(payload),
            datetime_issued_utc=payload["header"]["dateTimeIssued"],
            total=payload["totalAmount"],
            issuer_rin=payload["seller"]["rin"],
            portal_url=case.get("portal_url", PROD_PORTAL_URL),
        )
        assert qr == case["expected_qr"]
