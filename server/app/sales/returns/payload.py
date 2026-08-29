"""Outbox/event payload builder for a sales return (JSON primitives only)."""
from __future__ import annotations

from typing import Any

from app.core.money import round4
from app.models import Invoice


def _return_payload(
    invoice: Invoice,
    resolved: list[dict],
    splits: list[tuple[str, Any]],
    entry_no: int,
    totals: dict,
    inclusive: bool,
    original_id: int,
    original_no: str,
) -> dict[str, Any]:
    """Full outbox snapshot of the return invoice for offline replay.

    Each line carries its own return-batch shape (randomid/cost/expire) so the
    target store reproduces the exact batch; `original_invoice_no` lets replay
    re-link the return to the original sale (ids differ across stores).
    """
    lines = []
    for item in resolved:
        orig_line = item["orig_line"]
        lm = item["lm"]
        batch = item["batch"]
        entry: dict[str, Any] = {
            "drug_id": orig_line.drug_id,
            "qty": str(lm.qty),
            "unit_price": str(lm.unit_price),
            "unit_cost": str(round4(item["cogs"] / lm.qty)),
            "discount": str(lm.discount),
            "tax_type": lm.tax_type,
            "vat_amount": str(lm.vat),
            "line_total": str(lm.line_total),
            "expire": orig_line.expire.isoformat() if orig_line.expire else None,
            "ref_invoice_line_id": orig_line.id,
            "batch": {
                "randomid": batch.randomid,
                "cost": str(batch.cost),
                "expire": batch.expire.isoformat() if batch.expire else None,
            },
        }
        # #51: spillover restores carry per-lot shares so replay restores each
        # source lot instead of re-creating a single earliest-expiry batch.
        if "restored_batches" in item:
            entry["restored_batches"] = item["restored_batches"]
        lines.append(entry)
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
        "writer": (invoice.writer or "").strip()[:50],
        "created_by": invoice.created_by,
        "ref_invoice_id": original_id,
        "original_invoice_no": original_no,
        "journal": {"entry_no": entry_no, "source": "sale_return"},
        "lines": lines,
        "payments": [{"method": m, "amount": str(a)} for m, a in splits],
    }