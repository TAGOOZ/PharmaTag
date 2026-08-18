"""Outbox/event payload builder for a purchase return (JSON primitives only).

The snapshot carries each line's ORIGINAL purchase batch randomid (the batch to
DECREMENT on the target store) and `original_invoice_no` so replay re-links the
return to the original purchase (ids differ across stores).
"""
from __future__ import annotations

from typing import Any

from app.models import Invoice


def _purchase_return_payload(
    invoice: Invoice,
    resolved: list[dict],
    splits: list[tuple[str, Any]],
    entry_no: int,
    totals: dict,
    inclusive: bool,
    original_id: int,
    original_no: str,
) -> dict[str, Any]:
    """Full outbox snapshot of the return invoice for offline replay."""
    lines = []
    for item in resolved:
        orig_line = item["orig_line"]
        lm = item["lm"]
        batch = item["batch"]
        lines.append(
            {
                "drug_id": orig_line.drug_id,
                "qty": str(lm.qty),
                "unit_price": str(lm.unit_price),
                "unit_cost": str(orig_line.cost),
                "discount": str(lm.discount),
                "tax_type": lm.tax_type,
                "vat_amount": str(lm.vat),
                "line_total": str(lm.line_total),
                "expire": orig_line.expire.isoformat() if orig_line.expire else None,
                "ref_invoice_line_id": orig_line.id,
                "batch": {
                    "randomid": batch.randomid,
                    "cost": str(batch.cost),
                },
            }
        )
    return {
        "branch_id": invoice.branch_id,
        "kind": invoice.kind,
        "invoice_no": invoice.invoice_no,
        "datee": invoice.datee.isoformat(),
        "party_id": invoice.party_id,
        "silsilaid": invoice.silsilaid or "",
        "status": invoice.status,
        "subtotal": str(invoice.subtotal),
        "discount": str(invoice.discount),
        "vat": str(invoice.vat),
        "totalvalue": str(invoice.totalvalue),
        "net": str(totals["net"]),
        "payed": str(invoice.payed),
        "agel": str(invoice.agel),
        "inclusive": inclusive,
        "created_by": invoice.created_by,
        "ref_invoice_id": original_id,
        "original_invoice_no": original_no,
        "journal": {"entry_no": entry_no, "source": "purchase_return"},
        "lines": lines,
        "payments": [{"method": m, "amount": str(a)} for m, a in splits],
    }