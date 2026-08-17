"""Offline replay of a purchase (S1.4, ticket #10): re-create the exact batch
rows and supplier invoice on the target store from the outbox snapshot.

Same discipline as the sale replay: runs inside the caller's transaction
(sync.replay_pending owns commit + the (branch_id, invoice_no) dedupe); FIFO is
not re-run — the payload's explicit batch (randomid, net cost, gross price, VAT)
is reproduced exactly, so replay is deterministic and a repeated replay is a
no-op through the invoice dedupe. `entry_no` is recomputed store-side (payload
entry_no is source metadata, not data to be reproduced).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.money import format2
from app.models import (
    BranchStock,
    Invoice,
    InvoiceLine,
    Party,
    PaymentSplit,
    StockBatch,
)
from app.money.journal import post_journal
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no

_PARTY_MISSING = HTTPException(
    status.HTTP_409_CONFLICT,
    "supplier party missing on target store — create the supplier first",
)


async def _ensure_party(
    session: AsyncSession, branch_id: int, party_id: Optional[int]
) -> Optional[Party]:
    if party_id is None:
        return None
    party = await session.get(Party, party_id)
    if party is None or party.branch_id != branch_id:
        raise _PARTY_MISSING
    return party


async def apply_purchase_payload(
    session: AsyncSession,
    *,
    branch_id: int,
    payload: dict[str, Any],
    user_id: Optional[int] = None,
) -> Invoice:
    """Reconstruct a purchase from its outbox snapshot (offline replay path).

    Re-creates each line's NEW batch (branch, drug, randomid), raises
    branch_stock by the line qty, writes the supplier invoice, payment splits
    and the balanced purchase journal. The caller (sync.replay_pending) owns the
    (branch_id, invoice_no) dedupe and the status/failure transitions. Runs
    inside the caller's transaction.
    """
    await acquire_branch_lock(session, branch_id)
    invoice_no = payload["invoice_no"]
    datee = date.fromisoformat(payload["datee"])
    supplier = await _ensure_party(session, branch_id, payload.get("party_id"))

    line_batches: list[tuple[dict, StockBatch]] = []
    for lp in payload["lines"]:
        randomid = lp["batch"]["randomid"]
        dup = (
            await session.execute(
                select(StockBatch.id).where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.drug_id == lp["drug_id"],
                    StockBatch.randomid == randomid,
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"purchase batch {randomid} already exists on target store",
            )
        batch = StockBatch(
            branch_id=branch_id,
            drug_id=lp["drug_id"],
            randomid=randomid,
            qty=Decimal(lp["qty"]),
            expire=date.fromisoformat(lp["expire"]) if lp.get("expire") else None,
            cost=Decimal(lp["batch"]["cost"]),
            vat=Decimal(lp["batch"]["vat"]),
            price=Decimal(lp["batch"]["price"]),
            oldstock=Decimal("0"),
            typee="purchase",
            vatvalue=Decimal(lp["batch"]["vatvalue"]),
            totalwithvat=Decimal(lp["batch"]["totalwithvat"]),
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
            action="purchase",
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
            action="purchase",
            typevalue=invoice_no,
        )
        line_batches.append((lp, batch))

    invoice = Invoice(
        branch_id=branch_id,
        kind=payload.get("kind", "purchase"),
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        party_id=supplier.id if supplier else None,
        silsilaid=payload.get("silsilaid") or "",
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
            f"purchase {invoice_no} total={format2(invoice.totalvalue)} (replay)"
        ),
        typevalue=invoice_no,
    )

    for lp, batch in line_batches:
        session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                branch_id=branch_id,
                drug_id=lp["drug_id"],
                batch_id=batch.id,
                qty=Decimal(lp["qty"]),
                unit="pack",
                unit_price=Decimal(lp["unit_price"]),
                cost=Decimal(lp["batch"]["cost"]),
                disc=Decimal(lp.get("discount", "0")),
                tax_type=lp["tax_type"],
                vat=Decimal(lp["batch"]["vat"]),
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

    net = Decimal(payload["net"])
    entries: list[tuple[str, Decimal, Decimal]] = []
    if net > 0:
        entries.append(("1200", net, Decimal("0")))
    if Decimal(payload["vat"]) > 0:
        entries.append(("2100", Decimal(payload["vat"]), Decimal("0")))
    if Decimal(payload["payed"]) > 0:
        entries.append(("1000", Decimal("0"), Decimal(payload["payed"])))
    if Decimal(payload["agel"]) > 0:
        entries.append(("2000", Decimal("0"), Decimal(payload["agel"])))
    entry_no = await next_journal_entry_no(session, branch_id, datee)
    await post_journal(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        entry_no=entry_no,
        description=f"فاتورة مشتريات {invoice_no}",
        source="purchase",
        entries=entries,
        ref_invoice_id=invoice.id,
        contra_party_id=supplier.id if supplier else None,
    )
    return invoice
