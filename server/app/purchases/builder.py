"""The full purchase write: resolve lines, stock up, write everything.

`_build_full_purchase` is the heart of S1.4 (ticket #10): it runs inside one
`atomic()` transaction along with the header save, audit rows and outbox
enqueue (G12). It mirrors the sale builder (same invoice/journal machinery per
the slicing plan), with the purchase sign: stock is RAISED as new batches, the
supplier payable (AP) posts for the credit portion, and input VAT offsets the
VAT payable account.

Journal shape (balanced by construction, net + vat = total = payed + agel):

  Dr 1200 stock  = net  (inventory at net cost)
  Dr 2100 VAT    = vat  (input VAT — offsets output VAT payable)
  Cr 1000 drawer = payed (paid now)
  Cr 2000 AP     = agel  (supplier payable, contra = the supplier party)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit, enqueue_sync
from app.core.money import add, format2, line_money, round2, round4, tax_rate
from app.drawer.movements import SUPPLIER_PAY, record_payment_splits
from app.models import Branch, Drug, Invoice, InvoiceLine, Party, PaymentSplit
from app.money.journal import post_journal
from app.purchases.payload import _purchase_payload
from app.purchases.stock import (
    _primary_barcode,
    create_purchase_batch,
    upsert_branch_stock,
)
from app.sales.numbering import next_journal_entry_no
from app.sales.payments import _resolve_payments
from app.sales.pricing import _sale_totals as _invoice_totals

NOT_A_SUPPLIER = HTTPException(
    status.HTTP_400_BAD_REQUEST, "party is not a supplier"
)
INACTIVE_SUPPLIER = HTTPException(
    status.HTTP_400_BAD_REQUEST, "supplier is inactive"
)


async def _supplier_or_404(
    session: AsyncSession, branch_id: int, supplier_id: int
) -> Party:
    supplier = await session.get(Party, supplier_id)
    if supplier is None or supplier.branch_id != branch_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "supplier not found")
    if supplier.kind not in ("supplier", "both"):
        raise NOT_A_SUPPLIER
    if not supplier.active:
        raise INACTIVE_SUPPLIER
    return supplier


async def _build_full_purchase(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    datee: date,
    lines: list[Any],
    disc_percent,
    payments,
    supplier_id: int,
) -> Invoice:
    """The full purchase: resolve lines, stock up batches, write header + lines
    + splits + journal + balances, audit everything, enqueue the outbox row."""
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found")
    # Egypt B2B supplier invoices itemize net + VAT (the ETA regime): a purchase
    # is ALWAYS VAT-exclusive regardless of the branch's RETAIL inclusive flag.
    inclusive = False
    supplier = await _supplier_or_404(session, branch_id, supplier_id)

    resolved: list[dict] = []
    for idx, line in enumerate(lines):
        drug = await session.get(Drug, line.drug_id)
        if drug is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "drug not found")
        if not drug.active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "drug is inactive")
        lm = line_money(
            line.qty,
            line.unit_cost,
            drug.tax_type,
            disc_percent=getattr(line, "disc_percent", None),
            inclusive=inclusive,
        )
        resolved.append({"drug": drug, "lm": lm, "idx": idx})

    # totals apportion any invoice-level discount into each line and re-split
    # the VAT on the discounted net; the batch must be created AFTER this so its
    # cost is the discounted net unit cost (finding: header discount ignored).
    totals = _invoice_totals(resolved, disc_percent, inclusive=inclusive)
    for item in resolved:
        drug = item["drug"]
        lm = item["lm"]
        net_unit = round4(lm.net / lm.qty)
        batch = await create_purchase_batch(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=drug.id,
            randomid=f"p-{invoice_no}-{item['idx']}",
            qty=lm.qty,
            cost=net_unit,
            price=lm.unit_price,
            vat_rate=round2(tax_rate(lm.tax_type) * Decimal("100")),
            vat_amount=lm.vat,
            total_with_vat=round2(lm.line_total + lm.vat),
            expire=getattr(lines[item["idx"]], "expire", None),
            barcode=await _primary_barcode(session, drug.id),
        )
        await upsert_branch_stock(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=drug.id,
            qty_delta=lm.qty,
            barcode=await _primary_barcode(session, drug.id),
        )
        item["batch"] = batch

    payed, agel, splits = _resolve_payments(payments, totals["total"])

    invoice = Invoice(
        branch_id=branch_id,
        kind="purchase",
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        party_id=supplier.id,
        subtotal=totals["subtotal"],
        discount=totals["discount"],
        vat=totals["vat"],
        totalvalue=totals["total"],
        payed=payed,
        agel=agel,
        status="saved",
        created_by=user_id,
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
            f"purchase {invoice_no} supplier={supplier.id} "
            f"total={format2(invoice.totalvalue)}"
        ),
        typevalue=invoice_no,
    )

    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="parties",
        entity_id=supplier.id,
        action=ACTION_INSERT,
        new_value=f"purchase invoice_no={invoice_no} total={format2(invoice.totalvalue)}",
        typevalue=invoice_no,
    )

    for item in resolved:
        drug = item["drug"]
        lm = item["lm"]
        batch = item["batch"]
        line = InvoiceLine(
            invoice_id=invoice.id,
            branch_id=branch_id,
            drug_id=drug.id,
            batch_id=batch.id,
            qty=lm.qty,
            unit="pack",
            unit_price=lm.unit_price,
            cost=batch.cost,
            disc=lm.discount,
            tax_type=lm.tax_type,
            vat=round2(tax_rate(lm.tax_type) * Decimal("100")),
            vat_amount=lm.vat,
            line_total=lm.line_total,
            expire=batch.expire,
        )
        session.add(line)
        await session.flush()
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="invoice_lines",
            entity_id=line.id,
            action=ACTION_INSERT,
            drug_id=drug.id,
            barcode=await _primary_barcode(session, drug.id),
            new_value=(
                f"qty={lm.qty} cost={format2(lm.unit_price)} "
                f"tax={lm.tax_type} total={format2(lm.line_total)}"
            ),
            typevalue=invoice_no,
        )

    for method, amount in splits:
        session.add(
            PaymentSplit(
                invoice_id=invoice.id,
                branch_id=branch_id,
                method=method,
                amount=amount,
                user_id=user_id,
            )
        )

    await record_payment_splits(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        direction="out",
        reason=SUPPLIER_PAY,
        splits=splits,
        ref_invoice_id=invoice.id,
    )

    entry_no = await next_journal_entry_no(session, branch_id, datee)
    entries: list[tuple[str, Decimal, Decimal]] = []
    if totals["net"] > 0:
        entries.append(("1200", totals["net"], Decimal("0")))
    if totals["vat"] > 0:
        entries.append(("2100", totals["vat"], Decimal("0")))
    if payed > 0:
        entries.append(("1000", Decimal("0"), payed))
    if agel > 0:
        entries.append(("2000", Decimal("0"), agel))
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
        contra_party_id=supplier.id,
    )

    payload = _purchase_payload(invoice, resolved, splits, entry_no, totals, inclusive)
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="invoice",
        entity_id=invoice.id,
        action="insert",
        payload=payload,
    )
    return invoice
