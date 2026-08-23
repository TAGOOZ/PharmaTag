"""Canonical tax-document builder + per-document regime routing (S4.1, #28).

ADR-0002: regime routing is PER DOCUMENT — retail/walk-in and customer sales
issue an eReceipt v1.2 (``receipt``), their returns a return receipt
(``return_receipt``, receiptType 'r'); credit sales whose party carries a tax
registration number issue a B2B eInvoice v1.0 (``invoice``, documentType 'I')
and their returns a credit note (``credit_note``, 'C'). Deferred payment
(أجل) is a payment TERM, never a document type.

The returned dict is PharmaTag's canonical hash-base for the UUID chain —
JSON primitives only (strings/ints) so it survives JSON round-trips and the
SHA-256 recompute is byte-stable. The official submission serializer shapes
(eReceipt v1.2 / Invoice v1.0 field-perfect) are S4.2/S4.3 work on top of this.

Provisional code tables (payment method C=cash / V=card / O=other, largest
split wins). Tax codes (T1/subtypes) come from the tested table in
`codes.py` (#29).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.core.money import dec, round2, round4
from app.einvoicing.codes import tax_code
from app.models import Branch, EInvoiceLog, Invoice, Party
from app.models.einvoicing import (
    KIND_CREDIT_NOTE,
    KIND_INVOICE,
    KIND_RECEIPT,
    KIND_RETURN_RECEIPT,
)

RECEIPT_TYPE_VERSION = "1.2"
INVOICE_TYPE_VERSION = "1.0"


def route_kind(
    invoice: Invoice,
    party: Optional[Party],
    original_log: Optional[EInvoiceLog] = None,
) -> str:
    """Which regime kind this invoice issues (ADR-0002 decision 1).

    Returns follow the ORIGINAL document's regime — a credit note may only
    correct a B2B invoice, a return receipt only a receipt — never the party's
    current tax-registration state (which can change between sale and return).
    """
    if invoice.kind == "sale_return":
        if original_log is not None and original_log.kind == KIND_INVOICE:
            return KIND_CREDIT_NOTE
        return KIND_RETURN_RECEIPT
    if (
        invoice.kind == "sale"
        and party is not None
        and (party.tax_registration_no or "").strip()
        and invoice.agel is not None
        and invoice.agel > 0
    ):
        return KIND_INVOICE
    return KIND_RECEIPT


def _payment_method(splits: list[tuple[str, Any]]) -> str:
    best_method, best_amount = "cash", None
    for method, amount in splits or []:
        value = abs(amount) if amount is not None else 0
        if best_amount is None or value > best_amount:
            best_method, best_amount = method, value
    return {"cash": "C", "card": "V"}.get(best_method, "O")


def _line_view(item: dict, *, inclusive: bool) -> dict:
    drug = item["drug"]
    lm = item["lm"]
    # ETA receipt base structure: netSale = post-discount PRE-tax base,
    # total = netSale + taxes. On inclusive branches line_total carries the
    # VAT inside; on exclusive branches it is already ex-VAT.
    if inclusive:
        net_sale = dec(lm.line_total) - dec(lm.vat)
        total = dec(lm.line_total)
    else:
        net_sale = dec(lm.line_total)
        total = dec(lm.line_total) + dec(lm.vat)
    return {
        "internalCode": str(drug.id),
        "description": drug.drugnamear or drug.drugname or str(drug.id),
        "itemCode": f"EG-PH-{drug.id}",
        "quantity": lm.qty,
        "unitPrice": lm.unit_price,
        "discount": lm.discount,
        "netSale": round2(net_sale),
        "total": round2(total),
        "vat": lm.vat,
        "tax_type": lm.tax_type,
    }


def build_document(
    *,
    kind: str,
    invoice: Invoice,
    branch: Branch,
    party: Optional[Party],
    lines: list[dict],
    totals: dict,
    splits: list[tuple[str, Any]],
    seller: dict,
    device_serial: Optional[str],
    counter: int,
    previous_uuid: str,
    reference_uuid: str = "",
    original_buyer: Optional[dict] = None,
) -> dict:
    """Build the canonical document (hash base). All money values are exact
    decimal STRINGS; names follow the receipt base structure so receipts hash
    exactly like the official toolkit expects."""
    inclusive = bool(branch.vat_inclusive_prices)
    items = [_receipt_line(_line_view(l, inclusive=inclusive)) for l in lines]
    doc: dict[str, Any] = {
        "header": {
            "dateTimeIssued": _iso_z(invoice.datetimee),
            "receiptNumber": invoice.invoice_no,
            "uuid": "",
            "previousUUID": previous_uuid,
            "referenceUUID": reference_uuid,
            "currency": (branch.currency or "EGP").strip() or "EGP",
        },
        "documentType": _document_type(kind),
        "seller": {
            "rin": seller.get("rin", ""),
            "companyTradeName": seller.get("trade_name", "") or branch.pharname,
            "branchCode": branch.pharmacyid,
            "deviceSerialNumber": device_serial or "",
            "activityCode": seller.get("activity_code", ""),
            "branchAddress": {
                "country": (branch.country or "EG").strip() or "EG",
                "governate": branch.governorate or "",
                "regionCity": branch.district or "",
                "street": branch.adress or "",
                "buildingNumber": "",
            },
        },
        "buyer": _buyer(kind, party, original_buyer=original_buyer),
        "itemData": items,
        "totalSales": str(totals["subtotal"]),
        "totalCommercialDiscount": str(totals["discount"]),
        "netAmount": str(totals["net"]),
        "totalAmount": str(totals["total"]),
        "taxTotals": _tax_totals(lines),
        "paymentMethod": _payment_method(splits),
        "counter": counter,
    }
    return doc


def _receipt_line(view: dict) -> dict:
    quantity = round4(Decimal(str(view["quantity"])))
    gross = round4(quantity * Decimal(str(view["unitPrice"])))
    discount = round2(view["discount"] or 0)
    return {
        "internalCode": view["internalCode"],
        "description": view["description"],
        "itemType": "EGS",
        "itemCode": view["itemCode"],
        "unitType": "EA",
        "quantity": str(quantity),
        "unitPrice": str(view["unitPrice"]),
        "totalSale": str(gross),
        "commercialDiscountData": (
            [{"amount": str(discount), "description": "خصم"}]
            if discount != 0
            else []
        ),
        "netSale": str(view["netSale"]),
        "total": str(view["total"]),
        "taxableItems": [
            {
                "taxType": (code := tax_code(view["tax_type"])).tax_type,
                "subType": code.sub_type,
                "amount": str(view["vat"]),
                "rate": code.rate,
            }
        ],
    }


def _tax_totals(lines: list[dict]) -> list[dict]:
    buckets: dict[str, Any] = {}
    for item in lines:
        key = item["lm"].tax_type
        buckets[key] = buckets.get(key, Decimal("0")) + item["lm"].vat
    order = {k: tax_code(k).rate for k in buckets}
    return [
        {
            "taxType": (code := tax_code(k)).tax_type,
            "subType": code.sub_type,
            "amount": str(v),
            "rate": code.rate,
        }
        for k, v in sorted(buckets.items(), key=lambda kv: Decimal(order[kv[0]]))
    ]


def _document_type(kind: str) -> dict | str:
    if kind == KIND_RECEIPT:
        return {"receiptType": "s", "typeVersion": RECEIPT_TYPE_VERSION}
    if kind == KIND_RETURN_RECEIPT:
        return {"receiptType": "r", "typeVersion": RECEIPT_TYPE_VERSION}
    if kind == KIND_INVOICE:
        return {"documentType": "I", "typeVersion": INVOICE_TYPE_VERSION}
    if kind == KIND_CREDIT_NOTE:
        return {"documentType": "C", "typeVersion": INVOICE_TYPE_VERSION}
    raise ValueError(f"unknown einvoice kind {kind!r}")


def _buyer(
    kind: str,
    party: Optional[Party],
    original_buyer: Optional[dict] = None,
) -> dict:
    """A return/correction mirrors the ORIGINAL document's buyer verbatim —
    ETA pairs C→I / r→s by buyer + referenceUUID, and the party's live row
    may have been corrected since the original was issued."""
    if kind in (KIND_RETURN_RECEIPT, KIND_CREDIT_NOTE) and original_buyer:
        return dict(original_buyer)
    if kind in (KIND_INVOICE, KIND_CREDIT_NOTE):
        return {
            "type": "B",
            "id": (party.tax_registration_no or "").strip() if party else "",
            "name": (party.namee or "") if party else "",
        }
    buyer = {"type": "P"}
    if party is not None:
        buyer["id"] = (party.tax_registration_no or "").strip()
        buyer["name"] = party.namee or ""
    return buyer


def canonical(value: Any) -> Any:
    """Rebuild a document with object keys in PG jsonb's storage order
    (length, then bytewise), recursively.

    The UUID hashes SERIALIZE(canonical(doc)). sync_log.payload is JSONB,
    which reorders keys exactly this way — canonicalizing at the issue seam
    makes every later transport (json log column, JSONB outbox, replay)
    reproduce the same key order, so the SHA-256 recompute is byte-stable
    everywhere while ``serialize`` itself stays pure document-order (the
    official-toolkit contract).
    """
    if isinstance(value, dict):
        return {
            key: canonical(value[key])
            for key in sorted(value, key=lambda k: (len(k), k.encode("utf-8")))
        }
    if isinstance(value, list):
        return [canonical(item) for item in value]
    return value


def _iso_z(value) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
