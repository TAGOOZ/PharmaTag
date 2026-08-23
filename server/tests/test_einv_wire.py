"""S4.3 submission-wire contract tests (ticket #30).

``wire.submission_document`` turns the stored canonical hash-base into the
field-perfect wire document ETA expects per regime (ADR-0002):

* eReceipt v1.2 / return receipts — the receipt base structure with
  ``header.uuid`` filled from the log's computed UUID
* B2B Invoice/CreditNote v1.0 — issuer/receiver/invoiceLines naming per the
  official SDK Invoice v1.0 structure and the SDK postman collection's
  authoritative field order

Golden fixtures are hand-written FROM THE SPEC (postman Submit Export
Invoice v1.0 sample + Receipt v1.2 structure page), so any mapper drift from
the official names/order/values turns red. Serialization itself stays
toolkit-owned (test_einv_toolkit pins that contract separately).
"""
import json
from pathlib import Path

import pytest
from types import SimpleNamespace

from app.einvoicing.toolkit import serialize
from app.einvoicing.wire import signature_entry, submission_document

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "einvoicing"

RECEIPT_FIXTURE = json.loads((FIXTURES / "receipt_fixtures.json").read_text())[
    "receipts"
][0]


def _log(kind: str, payload: dict, uuid: str = "u" * 64) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, payload_json=payload, uuid=uuid)


# ---------------------------------------------------------------- eReceipt


def test_receipt_wire_fills_header_uuid_from_log():
    log = _log("receipt", RECEIPT_FIXTURE["payload"], uuid="ab" * 32)
    doc = submission_document(log)
    assert doc["header"]["uuid"] == "ab" * 32
    # everything else passes through verbatim (hash base untouched)
    assert doc["header"]["receiptNumber"] == RECEIPT_FIXTURE["payload"]["header"]["receiptNumber"]
    assert doc["totalAmount"] == RECEIPT_FIXTURE["payload"]["totalAmount"]


def test_return_receipt_wire_keeps_chain_fields():
    payload = json.loads(json.dumps(RECEIPT_FIXTURE["payload"]))
    payload["header"]["previousUUID"] = "cd" * 32
    payload["header"]["referenceUUID"] = "ef" * 32
    payload["documentType"] = {"receiptType": "r", "typeVersion": "1.2"}
    doc = submission_document(_log("return_receipt", payload))
    assert doc["documentType"] == {"receiptType": "r", "typeVersion": "1.2"}
    assert doc["header"]["referenceUUID"] == "ef" * 32
    assert doc["header"]["uuid"] == "u" * 64


def test_receipt_serialization_is_toolkit_stable_after_uuid_fill():
    """Signing hashes the serialized wire doc; filling uuid must not disturb
    anything else on the wire."""
    log = _log("receipt", RECEIPT_FIXTURE["payload"], uuid="ab" * 32)
    doc = submission_document(log)
    expected = json.loads(json.dumps(RECEIPT_FIXTURE["payload"]))
    expected["header"]["uuid"] = "ab" * 32
    assert serialize(doc) == serialize(expected)


def test_signature_entry_uses_official_property_names():
    """Postman collection + submit-receipt API page: signatureType/value."""
    assert signature_entry("QQ==") == {"signatureType": "I", "value": "QQ=="}


# ------------------------------------------------------- B2B Invoice v1.0

INVOICE_FIXTURE = json.loads(
    (FIXTURES / "invoice_v10_fixture.json").read_text(encoding="utf-8")
)


def test_invoice_wire_maps_canonical_to_official_v10_shape():
    """Field names, values and ORDER per the SDK Invoice v1.0 structure +
    postman v1.0 sample: issuer/receiver, invoiceLines, flat totals."""
    log = _log("invoice", INVOICE_FIXTURE["canonical"])
    doc = submission_document(log)
    expected = INVOICE_FIXTURE["wire_expected"]
    assert list(doc) == list(expected), "top-level field order must match the spec"
    assert doc == expected
    # serialization (what gets signed) is byte-identical incl. key order
    assert serialize(doc) == serialize(expected)


def test_credit_note_wire_flips_document_type_only():
    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    payload["documentType"] = {"documentType": "C", "typeVersion": "1.0"}
    log = _log("credit_note", payload)
    doc = submission_document(log)
    assert doc["documentType"] == "C"
    assert doc["documentTypeVersion"] == "1.0"
    assert doc["internalID"] == "2026-000512"


def test_invoice_wire_requires_tax_registered_buyer_fields():
    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    del payload["buyer"]["id"]
    with pytest.raises(ValueError):
        submission_document(_log("invoice", payload))


def test_unknown_kind_and_broken_payloads_are_rejected():
    with pytest.raises(ValueError):
        submission_document(_log("mystery", {}))
    with pytest.raises(ValueError):
        submission_document(_log("receipt", {"header": {}}))
    with pytest.raises(ValueError):
        submission_document(_log("receipt", "not-a-dict"))


def test_corrupted_payloads_normalize_to_value_error():
    """Mapping defects (missing keys, malformed money) must surface as
    ValueError — the submitter's permanent-fail guard — never KeyError or
    TypeError that would escape it and stall the worker pass."""
    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    del payload["itemData"][0]["taxableItems"][0]["taxType"]      # KeyError
    with pytest.raises(ValueError):
        submission_document(_log("invoice", payload))

    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    payload["itemData"][0]["commercialDiscountData"] = [{"amount": None}]  # TypeError
    with pytest.raises(ValueError):
        submission_document(_log("invoice", payload))

    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    payload["itemData"][0]["commercialDiscountData"] = [{"amount": "abc"}]  # InvalidOperation
    with pytest.raises(ValueError):
        submission_document(_log("invoice", payload))


def test_scalar_item_data_normalizes_to_value_error():
    """Non-list itemData reaches .get() on a scalar — AttributeError must be
    normalized like every other mapping defect."""
    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    payload["itemData"] = "corrupted"
    with pytest.raises(ValueError):
        submission_document(_log("invoice", payload))


def test_discount_amounts_format_half_up():
    """Money formatting rides money.py's half-up authority: 0.125 → '0.13'
    (quantize's default half-even would print '0.12')."""
    payload = json.loads(json.dumps(INVOICE_FIXTURE["canonical"]))
    payload["itemData"][0]["commercialDiscountData"] = [{"amount": "0.125"}]
    doc = submission_document(_log("invoice", payload))
    assert doc["invoiceLines"][0]["discount"]["amount"] == "0.13"
