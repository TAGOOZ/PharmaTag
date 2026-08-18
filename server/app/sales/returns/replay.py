"""Offline replay of a sales return (S1.5, ticket #11).

`apply_sale_return_payload` reconstructs the return invoice on the target store
from its outbox snapshot: it re-creates each NEW return batch (the payload's
explicit randomid/cost/expire), raises branch_stock, links the return to the
original sale (found by original_invoice_no on the target store), writes the
invoice + payment splits + the balanced `sale_return` journal, and snapshots the
original into invoice_versions — mirroring the source store's write.

Same discipline as sale/purchase replay: runs inside the caller's transaction
(sync.replay_pending owns commit + the (branch_id, invoice_no) dedupe); if the
original sale hasn't reached this store yet the row is marked failed (G10:
conflicts recorded, never lost), and once the sale arrives a later replay
retry succeeds.
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
from app.drawer.movements import SALE_RETURN, record_payment_splits
from app.models import BranchStock, Invoice, InvoiceLine, InvoiceVersion, PaymentSplit, StockBatch
from app.money.journal import post_journal
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

_ORIGINAL_MISSING = HTTPException(
    status.HTTP_409_CONFLICT,
    "original sale missing on target store — replay the sale first",
)
_BATCH_DUP = HTTPException(
    status.HTTP_409_CONFLICT,
    "return batch already exists on target store",
)


async def _find_original(
    session: AsyncSession, branch_id: int, original_no: str
) -> Optional[Invoice]:
    return (
        await session.execute(
            select(Invoice).where(
                Invoice.branch_id == branch_id,
                Invoice.invoice_no == original_no,
                Invoice.kind == "sale",
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


async def apply_sale_return_payload(
    session: AsyncSession,
    *,
    branch_id: int,
    payload: dict[str, Any],
    user_id: Optional[int] = None,
) -> Invoice:
    """Reconstruct a sales return from its outbox snapshot (offline replay path)."""
    await acquire_branch_lock(session, branch_id)
    invoice_no = payload["invoice_no"]
    datee = date.fromisoformat(payload["datee"])
    original = await _find_original(
        session, branch_id, payload.get("original_invoice_no", "")
    )
    if original is None:
        raise _ORIGINAL_MISSING

    line_batches: list[tuple[dict, StockBatch]] = []
    cogs_total = Decimal("0")
    for lp in payload["lines"]:
        b = lp["batch"]
        dup = (
            await session.execute(
                select(StockBatch.id).where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.drug_id == lp["drug_id"],
                    StockBatch.randomid == b["randomid"],
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise _BATCH_DUP
        batch = StockBatch(
            branch_id=branch_id,
            drug_id=lp["drug_id"],
            randomid=b["randomid"],
            qty=Decimal(lp["qty"]),
            expire=date.fromisoformat(b["expire"]) if b.get("expire") else None,
            cost=Decimal(b["cost"]),
            vat=round2(tax_rate(lp["tax_type"]) * Decimal("100")),
            price=Decimal(lp["unit_price"]),
            oldstock=Decimal("0"),
            typee="return",
            vatvalue=Decimal(lp["vat_amount"]),
            totalwithvat=Decimal(lp["line_total"]),
            created_by=user_id,
        )
        session.add(batch)
        await session.flush()
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="stock_batches",
            entity_id=batch.id,
            field="qty",
            old_value="0.0000",
            new_value=lp["qty"],
            drug_id=lp["drug_id"],
            action="return",
            typevalue=invoice_no,
        )
        row = (
            await session.execute(
                select(BranchStock)
                .where(
                    BranchStock.branch_id == branch_id,
                    BranchStock.drug_id == lp["drug_id"],
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            row = BranchStock(
                branch_id=branch_id,
                drug_id=lp["drug_id"],
                qty=Decimal("0"),
                minimum=Decimal("0"),
            )
            session.add(row)
            await session.flush()
        old_qty = Decimal(row.qty)
        new_qty = old_qty + Decimal(lp["qty"])
        row.qty = new_qty
        row.lastedit = datetime.now(timezone.utc)
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="branch_stock",
            entity_id=lp["drug_id"],
            field="qty",
            old_value=str(old_qty),
            new_value=str(new_qty),
            drug_id=lp["drug_id"],
            action="return",
            typevalue=invoice_no,
        )
        cogs_total += round2(dec(lp["qty"]) * dec(lp["unit_cost"]))
        line_batches.append((lp, batch))

    invoice = Invoice(
        branch_id=branch_id,
        kind="sale_return",
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        ref_invoice_id=original.id,
        subtotal=Decimal(payload["subtotal"]),
        discount=Decimal(payload["discount"]),
        vat=Decimal(payload["vat"]),
        totalvalue=Decimal(payload["totalvalue"]),
        payed=Decimal(payload["payed"]),
        agel=Decimal(payload["agel"]),
        status="saved",
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
            f"sale_return {invoice_no} ref={original.invoice_no} "
            f"total={format2(invoice.totalvalue)} (replay)"
        ),
        typevalue=invoice_no,
    )

    for lp, batch in line_batches:
        orig_line = (
            await session.execute(
                select(InvoiceLine).where(
                    InvoiceLine.invoice_id == original.id,
                    InvoiceLine.drug_id == lp["drug_id"],
                    InvoiceLine.qty == dec(lp["qty"]),
                )
            )
        ).scalars().first()
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
                expire=date.fromisoformat(lp["expire"]) if lp.get("expire") else None,
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

    payments = [(pm["method"], pm["amount"]) for pm in payload.get("payments", [])]
    if payments:
        await record_payment_splits(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            direction="out",
            reason=SALE_RETURN,
            splits=payments,
            ref_invoice_id=invoice.id,
        )

    net = Decimal(payload["net"])
    entries: list[tuple[str, Decimal, Decimal]] = []
    if Decimal(payload["payed"]) > 0:
        entries.append(("1000", Decimal("0"), Decimal(payload["payed"])))
    if Decimal(payload["agel"]) > 0:
        entries.append(("1100", Decimal("0"), Decimal(payload["agel"])))
    if net > 0:
        entries.append(("4000", net, Decimal("0")))
    if Decimal(payload["vat"]) > 0:
        entries.append(("2100", Decimal(payload["vat"]), Decimal("0")))
    if cogs_total > 0:
        entries.append(("6000", Decimal("0"), cogs_total))
        entries.append(("1200", cogs_total, Decimal("0")))
    entry_no = await next_journal_entry_no(session, branch_id, datee)
    await post_journal(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        entry_no=entry_no,
        description=f"مرتجع بيع {invoice_no}",
        source="sale_return",
        entries=entries,
        ref_invoice_id=invoice.id,
    )
    await _snapshot_original(session, original, action="sale_return", user_id=user_id)
    return invoice