"""The full purchase-return write: validate the original, reverse everything.

`_build_full_purchase_return` is the heart of S1.6 (ticket #12): it runs inside
one `atomic()` transaction with the header save, audit rows and outbox enqueue
(G12). It reverses a saved purchase into a NEW `purchase_return` invoice:

* stock: the original purchase line's batch is DECREMENTED by the returned qty
  and `branch_stock` goes back down (the reverse of a purchase — no new batch);
* money: per-line totals recomputed at the ORIGINAL line's unit price/tax_type
  for the returned qty, the line's original discount reversed proportionally,
  the header discount reversed proportionally, and the refund split mirrored
  from the original payments (payed + agel == total);
* journal (source=`purchase_return`, balanced by construction, the exact mirror
  of the purchase journal):
      Dr 1000 drawer = payed  (refund received from the supplier)
      Dr 2000 AP     = agel   (supplier payable reduced, contra = the supplier)
      Cr 1200 stock  = net    (inventory down at net cost)
      Cr 2100 VAT    = vat    (input VAT reversed)
* audit rows + outbox snapshot, and the ORIGINAL purchase snapshotted into
  `invoice_versions` (the AC2 "snapshot on edit" trail).

Partial-return rule: a line may return at most (original qty - already
returned), and at most the batch's current qty (the batch may already be partly
sold). The branch advisory lock serializes concurrent returns on the same
branch so the already-returned sum can never race.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit, enqueue_sync
from app.core.money import (
    LineMoney,
    add,
    dec,
    format2,
    round2,
    round4,
    split_vat,
    tax_rate,
)
from app.models import Branch, Invoice, InvoiceLine, InvoiceVersion, PaymentSplit
from app.money.journal import post_journal
from app.purchases.returns.payload import _purchase_return_payload
from app.purchases.returns.stock import (
    _primary_barcode,
    decrease_branch_stock,
    decrement_purchase_batch,
)
from app.sales.numbering import next_journal_entry_no
from app.sales.payments import _resolve_payments
from app.sales.pricing import DISCOUNT_OVERFLOW

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
EMPTY_LINES = HTTPException(
    status.HTTP_400_BAD_REQUEST, "at least one return line is required"
)
NOT_RETURNABLE = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "only a saved purchase invoice can be returned",
)
LINE_NOT_IN_ORIGINAL = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "return line does not reference a line of the original invoice",
)
ZERO_QTY = HTTPException(
    status.HTTP_400_BAD_REQUEST, "qty must be positive"
)
OVER_RETURN = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "cannot return more than the quantity purchased",
)


async def _already_returned(session: AsyncSession, original_line_id: int) -> Decimal:
    """Qty of this original line already returned by purchase_return invoices."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(InvoiceLine.qty), 0))
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .where(
                InvoiceLine.ref_invoice_line_id == original_line_id,
                Invoice.kind == "purchase_return",
            )
        )
    ).scalar_one()
    return dec(total)


def _return_line_money(
    qty, unit_price, tax_type: str, *, line_disc_amount, inclusive: bool
) -> LineMoney:
    """Return-line money at the ORIGINAL unit price, with the original line's
    discount reversed proportionally (as an AMOUNT, mirroring how the purchase
    stored it). The VAT split works on the discounted total, exactly like the
    purchase's per-line engine."""
    qty_r = round4(dec(qty))
    price = dec(unit_price)
    gross = round2(qty_r * price)
    discount = round2(dec(line_disc_amount))
    line_total = gross - discount
    split = split_vat(line_total, tax_type, inclusive=inclusive)
    return LineMoney(
        qty=qty_r,
        unit_price=price,
        tax_type=tax_type,
        gross=gross,
        discount=discount,
        line_total=line_total,
        net=split.net,
        vat=split.vat,
    )


async def _mirror_refund(
    session: AsyncSession, original: Invoice, total: Decimal
) -> tuple[Decimal, Decimal, list[tuple[str, Decimal]]]:
    """Refund split mirroring the original purchase's payment methods, scaled to
    the returned total. Snaps the last split so payed + agel == total exactly."""
    rows = (
        await session.execute(
            select(PaymentSplit)
            .where(
                PaymentSplit.invoice_id == original.id,
                PaymentSplit.amount > 0,
            )
            .order_by(PaymentSplit.id)
        )
    ).scalars().all()
    orig_splits = [(p.method, dec(p.amount)) for p in rows]
    if not orig_splits:
        orig_splits = [("cash", dec(original.payed))]
    scale = (
        total / dec(original.totalvalue)
        if dec(original.totalvalue) > 0
        else Decimal("0")
    )
    refunds: list[tuple[str, Decimal]] = []
    for method, amount in orig_splits:
        refund = round2(amount * scale)
        if refund > 0:
            refunds.append((method, refund))
    diff = round2(total - add(a for _, a in refunds))
    if refunds and diff != 0:
        method, last = refunds[-1]
        refunds[-1] = (method, round2(last + diff))
    payed = round2(add(a for m, a in refunds if m != "credit"))
    agel = round2(add(a for m, a in refunds if m == "credit"))
    return payed, agel, refunds


async def _snapshot_invoice(
    session: AsyncSession,
    invoice: Invoice,
    *,
    action: str,
    user_id: Optional[int],
) -> None:
    """Snapshot the given invoice into invoice_versions (AC2 trail)."""
    lines = (
        await session.execute(
            select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        )
    ).scalars().all()
    version_no = (
        await session.execute(
            select(func.coalesce(func.max(InvoiceVersion.version_no), 0)).where(
                InvoiceVersion.invoice_id == invoice.id
            )
        )
    ).scalar_one() + 1
    session.add(
        InvoiceVersion(
            invoice_id=invoice.id,
            version_no=version_no,
            action=action,
            changed_by=user_id,
            payload={
                "invoice_no": invoice.invoice_no,
                "datee": invoice.datee.isoformat(),
                "status": invoice.status,
                "subtotal": str(invoice.subtotal),
                "discount": str(invoice.discount),
                "vat": str(invoice.vat),
                "totalvalue": str(invoice.totalvalue),
                "payed": str(invoice.payed),
                "agel": str(invoice.agel),
                "lines": [
                    {
                        "drug_id": line.drug_id,
                        "qty": str(line.qty),
                        "unit_price": str(line.unit_price),
                        "line_total": str(line.line_total),
                        "tax_type": line.tax_type,
                    }
                    for line in lines
                ],
            },
        )
    )
    await session.flush()


def _return_totals(
    resolved: list[dict],
    original: Invoice,
    *,
    header_only_disc: Decimal,
    inclusive: bool,
) -> dict:
    """Return header totals: per-line money at original prices + a PROPORTIONAL
    share of the original's HEADER-ONLY discount (total discount minus the
    line discounts, so a line-discounted purchase isn't double-counted)."""
    subtotal = add(item["lm"].gross for item in resolved)
    line_disc = add(item["lm"].discount for item in resolved)
    invoice_disc = (
        round2(header_only_disc * subtotal / dec(original.subtotal))
        if dec(original.subtotal) > 0
        else Decimal("0")
    )
    discount = line_disc + invoice_disc
    vat = add(item["lm"].vat for item in resolved)
    total = round2(
        subtotal - discount + (vat if not inclusive else Decimal("0"))
    )
    if total < 0:
        raise DISCOUNT_OVERFLOW
    net = total - vat if inclusive else subtotal - discount
    return {
        "subtotal": subtotal,
        "discount": discount,
        "vat": vat,
        "total": total,
        "net": net,
    }


async def _build_full_purchase_return(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    datee: date,
    original_id: int,
    lines: list[Any],
    payments,
) -> Invoice:
    """Validate the original purchase, reverse stock + money + journal, audit
    and enqueue the outbox row — all in the caller's transaction."""
    if not lines:
        raise EMPTY_LINES
    original = await session.get(Invoice, original_id)
    if original is None or original.branch_id != branch_id:
        raise NOT_FOUND
    if original.kind != "purchase" or original.status != "saved":
        raise NOT_RETURNABLE
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise NOT_FOUND
    inclusive = bool(branch.vat_inclusive_prices)

    resolved: list[dict] = []
    for idx, line in enumerate(lines):
        orig_line = await session.get(InvoiceLine, line.ref_invoice_line_id)
        if orig_line is None or orig_line.invoice_id != original.id:
            raise LINE_NOT_IN_ORIGINAL
        qty = round4(dec(line.qty))
        if qty <= 0:
            raise ZERO_QTY
        already = await _already_returned(session, orig_line.id)
        if qty > dec(orig_line.qty) - already:
            raise OVER_RETURN
        line_disc = (
            round2(dec(orig_line.disc) * qty / dec(orig_line.qty))
            if dec(orig_line.qty) > 0
            else Decimal("0")
        )
        lm = _return_line_money(
            qty,
            orig_line.unit_price,
            orig_line.tax_type,
            line_disc_amount=line_disc,
            inclusive=inclusive,
        )
        barcode = await _primary_barcode(session, orig_line.drug_id)
        batch = await decrement_purchase_batch(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            batch_id=orig_line.batch_id,
            drug_id=orig_line.drug_id,
            qty=lm.qty,
            barcode=barcode,
        )
        await decrease_branch_stock(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=orig_line.drug_id,
            qty_delta=lm.qty,
            barcode=barcode,
        )
        resolved.append(
            {
                "orig_line": orig_line,
                "lm": lm,
                "batch": batch,
            }
        )

    orig_all_lines = (
        await session.execute(
            select(InvoiceLine).where(InvoiceLine.invoice_id == original.id)
        )
    ).scalars().all()
    header_only_disc = dec(original.discount) - add(
        dec(l.disc) for l in orig_all_lines
    )
    totals = _return_totals(
        resolved, original, header_only_disc=header_only_disc, inclusive=inclusive
    )
    if payments is not None:
        payed, agel, splits = _resolve_payments(payments, totals["total"])
    else:
        payed, agel, splits = await _mirror_refund(session, original, totals["total"])

    invoice = Invoice(
        branch_id=branch_id,
        kind="purchase_return",
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        ref_invoice_id=original.id,
        party_id=original.party_id,
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
            f"purchase_return {invoice_no} ref={original.invoice_no} "
            f"total={format2(invoice.totalvalue)}"
        ),
        typevalue=invoice_no,
    )
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="invoices",
        entity_id=original.id,
        action="purchase_return",
        new_value=f"returned by invoice_no={invoice_no}",
        typevalue=original.invoice_no,
    )

    for item in resolved:
        orig_line = item["orig_line"]
        lm = item["lm"]
        batch = item["batch"]
        line = InvoiceLine(
            invoice_id=invoice.id,
            branch_id=branch_id,
            drug_id=orig_line.drug_id,
            batch_id=batch.id,
            ref_invoice_line_id=orig_line.id,
            qty=lm.qty,
            unit="pack",
            unit_price=lm.unit_price,
            cost=round4(orig_line.cost),
            disc=lm.discount,
            tax_type=lm.tax_type,
            vat=round2(tax_rate(lm.tax_type) * Decimal("100")),
            vat_amount=lm.vat,
            line_total=lm.line_total,
            expire=orig_line.expire,
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
            drug_id=orig_line.drug_id,
            barcode=await _primary_barcode(session, orig_line.drug_id),
            new_value=(
                f"return qty={lm.qty} price={format2(lm.unit_price)} "
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

    entry_no = await next_journal_entry_no(session, branch_id, datee)
    entries: list[tuple[str, Decimal, Decimal]] = []
    if payed > 0:
        entries.append(("1000", payed, Decimal("0")))
    if agel > 0:
        entries.append(("2000", agel, Decimal("0")))
    if totals["net"] > 0:
        entries.append(("1200", Decimal("0"), totals["net"]))
    if totals["vat"] > 0:
        entries.append(("2100", Decimal("0"), totals["vat"]))
    if entries:
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

    await _snapshot_invoice(session, original, action="purchase_return", user_id=user_id)

    payload = _purchase_return_payload(
        invoice,
        resolved,
        splits,
        entry_no,
        totals,
        inclusive,
        original.id,
        original.invoice_no,
    )
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="invoice",
        entity_id=invoice.id,
        action="insert",
        payload=payload,
    )
    return invoice