"""Offline replay of a purchase return (S1.6, ticket #12).

`apply_purchase_return_payload` reconstructs the return invoice on the target
store from its outbox snapshot: it finds the ORIGINAL purchase (by
original_invoice_no) and the purchase batch each line returned (by the payload's
explicit batch randomid), DECREMENTS that batch + branch_stock, links the return
to the original, writes the invoice + payment splits + the balanced
`purchase_return` journal, and snapshots the original into invoice_versions —
mirroring the source store's write.

Same discipline as sale/purchase replay: runs inside the caller's transaction
(sync.replay_pending owns commit + the (branch_id, invoice_no) dedupe); if the
original purchase or its batch hasn't reached this store yet the row is marked
failed (G10: conflicts recorded, never lost), and once the purchase arrives a
later replay retry succeeds.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.money import dec, format2, round2, tax_rate
from app.models import Invoice, InvoiceLine, InvoiceVersion, PaymentSplit, StockBatch
from app.money.journal import post_journal
from app.purchases.returns.stock import (
    decrease_branch_stock,
    decrement_purchase_batch,
)
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

_ORIGINAL_MISSING = HTTPException(
    status.HTTP_409_CONFLICT,
    "original purchase missing on target store — replay the purchase first",
)


async def _find_original(
    session: AsyncSession, branch_id: int, original_no: str
) -> Optional[Invoice]:
    return (
        await session.execute(
            select(Invoice).where(
                Invoice.branch_id == branch_id,
                Invoice.invoice_no == original_no,
                Invoice.kind == "purchase",
            )
        )
    ).scalars().first()


async def _snapshot_original(
    session: AsyncSession,
    original: Invoice,
    *,
    action: str,
    user_id: Optional[int],
) -> None:
    """Mirror the source store's invoice_versions snapshot on the target."""
    version_no = (
        await session.execute(
            select(func.coalesce(func.max(InvoiceVersion.version_no), 0)).where(
                InvoiceVersion.invoice_id == original.id
            )
        )
    ).scalar_one() + 1
    session.add(
        InvoiceVersion(
            invoice_id=original.id,
            version_no=version_no,
            action=action,
            changed_by=user_id,
            payload={"action": action, "invoice_no": original.invoice_no},
        )
    )
    await session.flush()


async def apply_purchase_return_payload(
    session: AsyncSession,
    *,
    branch_id: int,
    payload: dict[str, Any],
    user_id: Optional[int] = None,
) -> Invoice:
    """Reconstruct a purchase return from its outbox snapshot (offline replay
    path)."""
    await acquire_branch_lock(session, branch_id)
    invoice_no = payload["invoice_no"]
    datee = date.fromisoformat(payload["datee"])
    original = await _find_original(
        session, branch_id, payload.get("original_invoice_no", "")
    )
    if original is None:
        raise _ORIGINAL_MISSING

    resolved: list[dict] = []
    for lp in payload["lines"]:
        barcode = ""
        randomid = lp["batch"]["randomid"]
        batch = (
            await session.execute(
                select(StockBatch)
                .where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.drug_id == lp["drug_id"],
                    StockBatch.randomid == randomid,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if batch is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "purchase batch missing on target store — replay the purchase first",
            )
        batch = await decrement_purchase_batch(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            batch_id=batch.id,
            drug_id=lp["drug_id"],
            qty=lp["qty"],
            barcode=barcode,
        )
        await decrease_branch_stock(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=lp["drug_id"],
            qty_delta=lp["qty"],
            barcode=barcode,
        )
        orig_line = (
            await session.execute(
                select(InvoiceLine).where(
                    InvoiceLine.invoice_id == original.id,
                    InvoiceLine.batch_id == batch.id,
                )
            )
        ).scalars().first()
        resolved.append({"line": lp, "batch": batch, "orig_line": orig_line})

    invoice = Invoice(
        branch_id=branch_id,
        kind="purchase_return",
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        ref_invoice_id=original.id,
        party_id=original.party_id,
        status=payload.get("status", "saved"),
        subtotal=Decimal(payload["subtotal"]),
        discount=Decimal(payload["discount"]),
        vat=Decimal(payload["vat"]),
        totalvalue=Decimal(payload["totalvalue"]),
        payed=Decimal(payload["payed"]),
        agel=Decimal(payload["agel"]),
        created_by=payload.get("created_by") or user_id,
    )
    session.add(invoice)
    await session.flush()
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="invoices",
        entity_id=invoice.id,
        action=ACTION_INSERT,
        new_value=(
            f"purchase_return {invoice_no} ref={original.invoice_no} "
            f"total={format2(invoice.totalvalue)} (replay)"
        ),
        typevalue=invoice_no,
    )

    for item in resolved:
        lp = item["line"]
        batch = item["batch"]
        orig_line = item["orig_line"]
        session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                branch_id=branch_id,
                drug_id=lp["drug_id"],
                batch_id=batch.id,
                ref_invoice_line_id=orig_line.id if orig_line else None,
                qty=Decimal(lp["qty"]),
                unit="pack",
                unit_price=Decimal(lp["unit_price"]),
                cost=Decimal(lp["unit_cost"]),
                disc=Decimal(lp.get("discount", "0")),
                tax_type=lp["tax_type"],
                vat=round2(tax_rate(lp["tax_type"]) * Decimal("100")),
                vat_amount=Decimal(lp["vat_amount"]),
                line_total=Decimal(lp["line_total"]),
                expire=(
                    date.fromisoformat(lp["expire"]) if lp.get("expire") else None
                ),
            )
        )

    for pm in payload.get("payments", []):
        session.add(
            PaymentSplit(
                invoice_id=invoice.id,
                branch_id=branch_id,
                method=pm["method"],
                amount=Decimal(pm["amount"]),
                user_id=user_id,
            )
        )

    entries: list[tuple[str, Decimal, Decimal]] = []
    if Decimal(payload["payed"]) > 0:
        entries.append(("1000", Decimal(payload["payed"]), Decimal("0")))
    if Decimal(payload["agel"]) > 0:
        entries.append(("2000", Decimal(payload["agel"]), Decimal("0")))
    if Decimal(payload["net"]) > 0:
        entries.append(("1200", Decimal("0"), Decimal(payload["net"])))
    if Decimal(payload["vat"]) > 0:
        entries.append(("2100", Decimal("0"), Decimal(payload["vat"])))
    if entries:
        entry_no = await next_journal_entry_no(session, branch_id, datee)
        await post_journal(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            entry_no=entry_no,
            description=f"مرتجع مشتريات {invoice_no}",
            source="purchase_return",
            entries=entries,
            ref_invoice_id=invoice.id,
            contra_party_by_code={"2000": original.party_id} if original.party_id else None,
        )
    await _snapshot_original(session, original, action="purchase_return", user_id=user_id)
    return invoice