"""Outbox/event payload builders for sales (JSON primitives only — plan/08 §2.4.1)."""
from __future__ import annotations

from typing import Any

from app.core.money import round4
from app.models import Invoice


def _ctx_payload(invoice: Invoice) -> dict[str, Any]:
    """Hashable event payload (JSON primitives only — plan/08 §2.4.1)."""
    return {
        "invoice_id": invoice.id,
        "branch_id": invoice.branch_id,
        "invoice_no": invoice.invoice_no,
        "datee": invoice.datee.isoformat(),
        "totalvalue": str(invoice.totalvalue),
        "payed": str(invoice.payed),
        "agel": str(invoice.agel),
        "writer": (invoice.writer or "").strip()[:50],
    }


def _sale_payload(
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
        allocations = item["allocations"]
        lines.append(
            {
                "drug_id": drug.id,
                "qty": str(lm.qty),
                "unit_price": str(lm.unit_price),
                "unit_cost": str(round4(item["cogs"] / lm.qty)),
                "discount": str(lm.discount),
                "tax_type": lm.tax_type,
                "vat_amount": str(lm.vat),
                "line_total": str(lm.line_total),
                "expire": (
                    allocations[0].expire.isoformat()
                    if allocations and allocations[0].expire
                    else None
                ),
                "allocations": [
                    {
                        "batch_id": a.batch_id,
                        "randomid": a.randomid,
                        "take": str(a.take),
                        "cost": str(a.cost),
                        "expire": a.expire.isoformat() if a.expire else None,
                    }
                    for a in allocations
                ],
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
        "journal": {"entry_no": entry_no, "source": "sale"},
        "lines": lines,
        "payments": [{"method": m, "amount": str(a)} for m, a in splits],
    }