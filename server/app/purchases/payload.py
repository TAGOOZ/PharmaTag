"""Outbox/event payload builder for purchases (JSON primitives only — plan/08 §2.4.1).

The snapshot carries the exact batch each line created (randomid, net cost,
gross price, VAT) so the offline replay path re-creates the same batches — FIFO
is not involved on a purchase, the batch to add is explicit.
"""
from __future__ import annotations

from typing import Any

from app.core.money import round4
from app.models import Invoice


def _purchase_payload(
    invoice: Invoice,
    resolved: list[dict],
    splits: list[tuple[str, Any]],
    entry_no: int,
    totals: dict,
    inclusive: bool,
) -> dict[str, Any]:
    """Full outbox snapshot: every value a JSON primitive (strings/ints) so it
    survives wire transport and stays hashable. The dedupe key is
    (branch_id, invoice_no) — enforced by uq_invoices_branch_no."""
    lines = []
    for item in resolved:
        drug = item["drug"]
        lm = item["lm"]
        batch = item["batch"]
        lines.append(
            {
                "drug_id": drug.id,
                "qty": str(lm.qty),
                "unit_price": str(lm.unit_price),
                "unit_cost": str(round4(lm.net / lm.qty)),
                "discount": str(lm.discount),
                "tax_type": lm.tax_type,
                "vat_amount": str(lm.vat),
                "line_total": str(lm.line_total),
                "expire": batch.expire.isoformat() if batch.expire else None,
                "batch": {
                    "randomid": batch.randomid,
                    "cost": str(batch.cost),
                    "vat": str(batch.vat),
                    "price": str(batch.price),
                    "vatvalue": str(batch.vatvalue or 0),
                    "totalwithvat": str(batch.totalwithvat or 0),
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
        "writer": (invoice.writer or "").strip()[:50],
        "created_by": invoice.created_by,
        "journal": {"entry_no": entry_no, "source": "purchase"},
        "lines": lines,
        "payments": [{"method": m, "amount": str(a)} for m, a in splits],
    }
