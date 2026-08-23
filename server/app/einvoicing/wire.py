"""Submission-wire serializer (S4.3, #30) — replaces #29's passthrough.

Turns the stored canonical hash-base (``einvoice_log.payload_json``) into the
field-perfect wire document ETA expects per regime (ADR-0002):

* ``receipt`` / ``return_receipt`` → eReceipt v1.2: the receipt base
  structure itself, with ``header.uuid`` filled from the computed UUID.
* ``invoice`` / ``credit_note`` → B2B Invoice v1.0 / credit note 'C':
  issuer/receiver/invoiceLines naming per the official SDK Invoice v1.0
  structure and the postman collection's authoritative field order.

Money values travel as exact decimal STRINGS verbatim (plan/00): ETA's
serialization hashes values as-written anyway, and strings survive the
JSONB outbox byte-stably.

The submission envelope carries the CAdES-BES signature entry
(``signatureType`` "I" + base64 value) produced by :mod:`app.einvoicing.signer`
at submit time — never at issuance, so rows issued before the eSeal cert
arrives still submit once signing is configured.

Transport note: this slice ships the serializer + signature attachment for
both regimes on #29's receipt-submission chain; routing B2B documents to the
eInvoicing API host (documentsubmissions + taxpayer OAuth) is deliberately
deferred behind the cert-gated sandbox checkbox (#30 close comment).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.money import dec, format2
from app.einvoicing.documents import INVOICE_TYPE_VERSION


def signature_entry(value: str) -> dict[str, str]:
    """One Signature element per the official property names."""
    return {"signatureType": "I", "value": value}


def submission_document(log) -> dict[str, Any]:
    """The wire document for one einvoice_log row, ready to POST.

    Any payload this module cannot map (missing fields, malformed money
    values, unknown kind) raises ValueError — the submitter's permanent-
    fail guard — never KeyError/TypeError, which would escape that guard
    and stall the whole worker pass on a poisoned row.
    """
    try:
        return _submission_document(log)
    except ValueError:
        raise
    except (KeyError, TypeError, AttributeError, ArithmeticError) as exc:
        raise ValueError(f"unmappable einvoice payload: {exc}") from exc


def _submission_document(log) -> dict[str, Any]:
    payload = log.payload_json or {}
    if not isinstance(payload, dict):
        raise ValueError("einvoice payload_json must be a JSON object")
    kind = log.kind
    if kind in ("receipt", "return_receipt"):
        return _receipt_document(payload, uuid=log.uuid)
    if kind in ("invoice", "credit_note"):
        return _invoice_document(payload)
    raise ValueError(f"unknown einvoice kind {kind!r}")


def _receipt_document(payload: dict, *, uuid: str) -> dict[str, Any]:
    document = _deep_copy(payload)
    header = document.get("header")
    if not isinstance(header, dict) or not header.get("receiptNumber"):
        raise ValueError("receipt payload missing header.receiptNumber")
    header["uuid"] = uuid
    return document


def _invoice_document(payload: dict) -> dict[str, Any]:
    """B2B Invoice/CreditNote v1.0 wire document.

    Field names and order follow the SDK Invoice v1.0 structure page and its
    authoritative postman samples (Submit Export Invoice v1.0). The canonical
    hash-base keeps receipt-base-structure names, so this is a real mapping,
    not a rename: seller→issuer, buyer→receiver, itemData→invoiceLines,
    salesTotal←totalSale, netTotal←netSale, flat documentType string, and
    taxTotals reduced to {taxType, amount} (no subType/rate on invoices).
    """
    header = payload.get("header") or {}
    seller = payload.get("seller") or {}
    buyer = payload.get("buyer") or {}
    doc_type = payload.get("documentType") or {}

    if not str(buyer.get("id", "")).strip():
        raise ValueError("B2B invoice wire requires the receiver's tax registration id")
    if not header.get("receiptNumber"):
        raise ValueError("invoice payload missing header.receiptNumber")

    address = seller.get("branchAddress") or {}
    currency = header.get("currency") or "EGP"

    return {
        "issuer": {
            "address": {
                "branchID": _text(seller.get("branchCode")),
                "country": _text(address.get("country")) or "EG",
                "governate": _text(address.get("governate")),
                "regionCity": _text(address.get("regionCity")),
                "street": _text(address.get("street")),
                "buildingNumber": _text(address.get("buildingNumber")),
            },
            "type": "B",
            "id": _text(seller.get("rin")),
            "name": _text(seller.get("companyTradeName")),
        },
        # PharmaTag captures no party addresses yet — send EG + empty optionals
        # until the party data model grows one (see #30 close comment).
        "receiver": {
            "address": {"country": "EG", "governate": "", "regionCity": "", "street": "", "buildingNumber": ""},
            "type": _text(buyer.get("type")) or "B",
            "id": _text(buyer.get("id")),
            "name": _text(buyer.get("name")),
        },
        "documentType": _text(doc_type.get("documentType")),
        "documentTypeVersion": INVOICE_TYPE_VERSION,
        "dateTimeIssued": _text(header.get("dateTimeIssued")),
        "taxpayerActivityCode": _text(seller.get("activityCode")),
        "internalID": _text(header.get("receiptNumber")),
        "invoiceLines": [
            _invoice_line(item, currency=currency)
            for item in payload.get("itemData") or []
        ],
        "totalDiscountAmount": _text(payload.get("totalCommercialDiscount")),
        "totalSalesAmount": _text(payload.get("totalSales")),
        "netAmount": _text(payload.get("netAmount")),
        "taxTotals": [
            {"taxType": t["taxType"], "amount": _text(t.get("amount"))}
            for t in payload.get("taxTotals") or []
        ],
        "totalAmount": _text(payload.get("totalAmount")),
        "extraDiscountAmount": "0",
        "totalItemsDiscountAmount": "0",
    }


def _invoice_line(item: dict, *, currency: str) -> dict[str, Any]:
    discounts = item.get("commercialDiscountData") or []
    line: dict[str, Any] = {
        "description": _text(item.get("description")),
        "itemType": _text(item.get("itemType")),
        "itemCode": _text(item.get("itemCode")),
        "unitType": _text(item.get("unitType")),
        "quantity": _text(item.get("quantity")),
        "internalCode": _text(item.get("internalCode")),
        "salesTotal": _text(item.get("totalSale")),
        "total": _text(item.get("total")),
        "valueDifference": "0",
        "totalTaxableFees": "0",
        "netTotal": _text(item.get("netSale")),
        "itemsDiscount": "0",
        "unitValue": {
            "currencySold": currency,
            "amountEGP": _text(item.get("unitPrice")),
        },
    }
    total_discount = sum((dec(d.get("amount")) for d in discounts), Decimal("0"))
    if total_discount != 0:
        line["discount"] = {"amount": format2(total_discount)}
    line["taxableItems"] = [
        {
            "taxType": t["taxType"],
            "subType": _text(t.get("subType")),
            "amount": _text(t.get("amount")),
            "rate": _text(t.get("rate")),
        }
        for t in item.get("taxableItems") or []
    ]
    return line


def _text(value: Any) -> str:
    """Verbatim text of a stored JSON primitive (never reformatted)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)



def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value
