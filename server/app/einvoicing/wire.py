"""Provisional submission-wire adapter (S4.2, #29; replaced by #30).

S4.1's canonical document already follows the receipt base-structure field
names, so v1 passes it through as the eReceipt submission body. #30 replaces
this module with the field-perfect eReceipt v1.2 / Invoice v1.0 serializer +
CAdES-BES signature attachment; the worker only knows this seam.
"""
from __future__ import annotations

from typing import Any


def receipt_document(log) -> dict[str, Any]:
    """The wire body for one einvoice_log row (provisional passthrough)."""
    return dict(log.payload_json or {})
