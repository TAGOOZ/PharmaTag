"""Pure-Python replication of the ETA Integration Toolkit (S4.1, #28).

Egypt is NOT ZATCA-TLV. Everything here replicates the official Egyptian Tax
Authority SDK algorithms (sdk.invoicing.eta.gov.eg, re-verified 2026-08-23):

* ``serialize`` — the document serialization approach (document-serialization-
  approach page): recursive walk from the document root, property names
  culture-invariant UPPERCASE, values verbatim (never reformatted), every name
  and simple value wrapped in double quotes; JSON arrays repeat the property
  name before EVERY element after an initial prefix. Contract-pinned
  byte-for-byte against the SDK's published sample pair in
  ``tests/fixtures/einvoicing/one-doc*.json*``.

* ``receipt_uuid`` — Receipt Issuance FAQ "How to generate receipt UUID": the
  receipt base structure with an EMPTY uuid, previousUUID included (empty
  string for the first receipt of the POS device), referenceUUID included for
  returns → SHA-256 → 64-char lowercase hex.

* ``qr_string`` — the consumer QR: a URL to the receipt details page in the
  e-receipt portal plus total and issuer RIN, per the FAQ template
  ``{URL}#Total:{Total},IssuerRIN:{Registration Number}``.

No network, no dependencies beyond ``segno`` for PNG rendering.
"""
from __future__ import annotations

import base64
import hashlib
import io
from datetime import datetime, timezone
from typing import Any

import segno

PROD_PORTAL_URL = "http://invoicing.eta.gov.eg"
PREPROD_PORTAL_URL = "https://preprod.invoicing.eta.gov.eg"

__all__ = [
    "PROD_PORTAL_URL",
    "PREPROD_PORTAL_URL",
    "qr_png_data_uri",
    "qr_string",
    "receipt_uuid",
    "serialize",
    "sha256_hex",
]


def _simple(value: Any) -> str:
    """Verbatim text of a simple JSON value (names/values are never altered)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _serialize_property(name: str, value: Any, out: list[str]) -> None:
    upper = name.upper()
    out.append(f'"{upper}"')
    if isinstance(value, list):
        for element in value:
            out.append(f'"{upper}"')
            _serialize_value(element, out)
    else:
        _serialize_value(value, out)


def _serialize_value(value: Any, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if item is None:
                continue
            _serialize_property(key, item, out)
    elif isinstance(value, list):  # bare nested array (not in ETA documents)
        for element in value:
            _serialize_value(element, out)
    else:
        out.append(f'"{_simple(value)}"')


def serialize(document: dict) -> str:
    """Serialize one document root to the canonical one-line quoted string."""
    out: list[str] = []
    _serialize_value(document, out)
    return "".join(out)


def sha256_hex(text: str) -> str:
    """SHA-256 of UTF-8 text as the 64-char lowercase hex string ETA expects."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _with_empty_uuid(value: Any) -> Any:
    """Copy of the document with every ``uuid`` key emptied for hashing."""
    if isinstance(value, dict):
        return {
            key: ("" if key == "uuid" else _with_empty_uuid(item))
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_with_empty_uuid(item) for item in value]
    return value


def receipt_uuid(payload: dict) -> str:
    """The receipt UUID: SHA-256 over the serialized base structure.

    The payload must already carry ``previousUUID`` (empty string when this is
    the first receipt of its POS device) and, for returns, ``referenceUUID``
    (both live on ``header`` per the receipt base structure). Any ``uuid``
    present anywhere in the payload is ignored — the procedure requires it
    empty while hashing.
    """
    return sha256_hex(serialize(_with_empty_uuid(payload)))


def _share_stamp(value: "datetime | str") -> str:
    """The issuance instant as ``YYYY-MM-DDTHH:MMZ`` (FAQ example precision).

    Accepts a datetime (converted to UTC) or an ISO string; a seconds-
    precision ISO string is truncated to minutes so the share URL matches
    the documented template regardless of header storage format.
    """
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    except ValueError:
        return text


def qr_string(
    *,
    uuid: str,
    datetime_issued_utc: "datetime | str",
    total: Any,
    issuer_rin: str,
    portal_url: str = PROD_PORTAL_URL,
) -> str:
    """Consumer QR content per the Receipt Issuance FAQ template.

    ``datetime_issued_utc`` is the issuance instant in UTC — a datetime or an
    ISO string (normalized to minutes precision for the share URL).
    """
    stamp = _share_stamp(datetime_issued_utc)
    url = f"{portal_url}/receipts/search/{uuid}/share/{stamp}"
    return f"{url}#Total:{_simple(total)},IssuerRIN:{issuer_rin}"


def qr_png_data_uri(qr_text: str, *, scale: int = 3) -> str:
    """Render QR content to a PNG data URI for embedding in print templates."""
    png = segno.make(qr_text, error="m")
    buffer = io.BytesIO()
    png.save(buffer, kind="png", scale=scale, border=2, dark="#000", light="#fff")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
