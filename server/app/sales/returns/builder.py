"""The full sales-return write: validate the original, reverse everything.

`_build_full_return` is the heart of S1.5 (ticket #11): it runs inside one
`atomic()` transaction with the header save, audit rows and outbox enqueue
(G12). It reverses a saved sale into a NEW `sale_return` invoice:

* stock (#51): by default a NEW return batch (`typee='return'`, cost = the
  sold line's avg cost) + `branch_stock` back up; **FIFO-spillover lines**
  (`allocations` > 1) instead restore each ORIGINAL source lot proportionally
  (per-batch share of the returned qty, preserving expiry/cost/randomid) and
  fall back to the NEW batch only when the outbox allocations are missing;
* money: per-line totals recomputed at the ORIGINAL line's unit price/tax_type/
  discount for the returned qty, header discount reversed proportionally, and
  the refund split mirrored from the original payments (payed + agel == total);
* journal (source=`sale_return`, balanced by construction):
      Cr 1000 drawer = payed      (cash/card refunded)
      Cr 1100 AR     = agel       (credit refunded)
      Dr 4000 sales  = net
      Dr 2100 VAT    = vat
      Cr 6000 COGS   = cogs_total
      Dr 1200 stock  = cogs_total
* audit rows + outbox snapshot, and the ORIGINAL invoice snapshotted into
  `invoice_versions` (the AC2 "snapshot on edit" trail).

Partial-return rule: a line may return at most (original qty - already
returned). The branch advisory lock serializes concurrent returns on the same
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
    apportion_discount,
    dec,
    format2,
    round2,
    round4,
    split_vat,
    tax_rate,
)
from app.drawer.movements import SALE_RETURN, record_payment_splits
from app.einvoicing.service import einvoice_block, issue_for_invoice
from app.models import Branch, Drug, Invoice, InvoiceLine, InvoiceVersion, Party, PaymentSplit, User
from app.money.journal import post_journal
from app.sales.numbering import next_journal_entry_no
from app.sales.payments import _resolve_payments
from app.sales.pricing import DISCOUNT_OVERFLOW
from app.sales.returns.payload import _return_payload
from app.sales.returns.stock import (
    _primary_barcode,
    _split_return_shares,
    create_return_batch,
    raise_branch_stock,
    restore_return_allocations,
)

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
NOT_RETURNABLE = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "only a saved sale invoice can be returned",
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
    "cannot return more than the quantity sold",
)
CREDIT_OVERFLOW = HTTPException(
    status.HTTP_400_BAD_REQUEST,
    "credit refund exceeds the original sale's credit portion",
)


async def _allocations_for_line(
    session: AsyncSession,
    *,
    branch_id: int,
    original_id: int,
    orig_line_id: int,
) -> Optional[list[dict]]:
    """Fetch the original sale line's FIFO allocations from its outbox payload (#51).

    The sale write (S1.3) stores per-batch takes (batch_id/randomid/take/cost/expire)
    in the invoice outbox row's `payload.lines[].allocations`. That is the
    authoritative source for which expiry lots were consumed. We locate the
    matching payload line by index (invoice_lines ordered by id mirrors the
    resolved order) and, as a fallback, by drug_id+qty. If the outbox row is
    missing or has no allocations the caller falls back to the legacy single-batch
    path.
    """
    from app.models import SyncLog  # local import to avoid cycle

    row = (
        await session.execute(
            select(SyncLog)
            .where(
                SyncLog.branch_id == branch_id,
                SyncLog.entity == "invoice",
                SyncLog.entity_id == original_id,
            )
            .order_by(SyncLog.id.desc())
        )
    ).scalars().first()
    if row is None or not isinstance(row.payload, dict):
        return None
    payload_lines = row.payload.get("lines")
    if not isinstance(payload_lines, list):
        return None
    # Map by index using invoice_lines order
    orig_lines = (
        await session.execute(
            select(InvoiceLine)
            .where(InvoiceLine.invoice_id == original_id)
            .order_by(InvoiceLine.id)
        )
    ).scalars().all()
    try:
        idx = next(i for i, l in enumerate(orig_lines) if l.id == orig_line_id)
    except StopIteration:
        return None
    if 0 <= idx < len(payload_lines):
        allocs = payload_lines[idx].get("allocations")
        if isinstance(allocs, list) and allocs:
            return allocs
    # Fallback: try match by drug_id + qty (covers reordered payloads or manual edits)
    orig_line = next((l for l in orig_lines if l.id == orig_line_id), None)
    if orig_line is not None:
        for pl in payload_lines:
            if pl.get("drug_id") == orig_line.drug_id and isinstance(pl.get("allocations"), list) and pl.get("allocations"):
                try:
                    if dec(pl.get("qty", 0)) == dec(orig_line.qty):
                        return pl.get("allocations")
                except Exception:
                    continue
        for pl in payload_lines:
            if pl.get("drug_id") == orig_line.drug_id and isinstance(pl.get("allocations"), list) and pl.get("allocations"):
                return pl.get("allocations")
    return None


async def _already_returned(session: AsyncSession, original_line_id: int) -> Decimal:
    """Qty of this original line already returned by sale_return invoices."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(InvoiceLine.qty), 0))
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .where(
                InvoiceLine.ref_invoice_line_id == original_line_id,
                Invoice.kind == "sale_return",
            )
        )
    ).scalar_one()
    return dec(total)


async def _already_credited(session: AsyncSession, original_id: int) -> Decimal:
    """Credit (agel) already refunded for this sale by prior sale_return
    invoices. An explicit credit refund must stay within the original sale's
    credit portion (an AR credit must be backed by an AR debit): refunding a
    cash sale — which never posted an AR line — as credit would leave the
    customer's ledger with a negative AR and no preceding debit."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Invoice.agel), 0)).where(
                Invoice.ref_invoice_id == original_id,
                Invoice.kind == "sale_return",
                Invoice.status == "saved",
            )
        )
    ).scalar_one()
    return dec(total)


def _return_line_money(
    qty, unit_price, tax_type: str, *, line_disc_amount, inclusive: bool
) -> LineMoney:
    """Return-line money at the ORIGINAL unit price, with the original line's
    discount reversed proportionally (as an AMOUNT — the sale stored the line
    discount as money, not a percent, so feeding it back as a percent would be
    wrong). The VAT split works on the discounted total, exactly like the sale's
    per-line engine."""
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
    """Refund split mirroring the original sale's payment methods, scaled to
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
    share of the original's HEADER-ONLY discount (total discount minus the line
    discounts, so a line-discounted sale isn't double-counted). The header share
    is apportioned per returned line and each line's VAT re-splits on the
    discounted total (item["lm"] is replaced), mirroring the original sale's
    engine so the reversal nets 1:1."""
    subtotal = add(item["lm"].gross for item in resolved)
    line_disc = add(item["lm"].discount for item in resolved)
    invoice_disc = (
        round2(header_only_disc * subtotal / dec(original.subtotal))
        if dec(original.subtotal) > 0
        else Decimal("0")
    )
    discount = line_disc + invoice_disc
    if discount > subtotal:
        raise DISCOUNT_OVERFLOW
    try:
        apportioned = apportion_discount(
            [item["lm"] for item in resolved], invoice_disc, inclusive=inclusive
        )
    except ValueError:
        raise DISCOUNT_OVERFLOW
    for item, lm in zip(resolved, apportioned):
        item["lm"] = lm
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


async def _build_full_return(
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
    """Validate the original sale, reverse stock + money + journal, audit and
    enqueue the outbox row — all in the caller's transaction."""
    original = await session.get(Invoice, original_id)
    if original is None or original.branch_id != branch_id:
        raise NOT_FOUND
    if original.kind != "sale" or original.status != "saved":
        raise NOT_RETURNABLE
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise NOT_FOUND
    inclusive = bool(branch.vat_inclusive_prices)

    # W1 fail-fast: missing user → 404 (avoid silent FK 500)
    writer = ""
    if user_id is not None:
        u = await session.get(User, user_id)
        if u is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        writer = (u.username or "").strip()[:50]

    resolved: list[dict] = []
    cogs_total = Decimal("0")
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
        drug = await session.get(Drug, orig_line.drug_id)
        if drug is None:
            raise NOT_FOUND
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
        await raise_branch_stock(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=orig_line.drug_id,
            qty_delta=lm.qty,
            barcode=barcode,
        )
        line_cogs = round2(lm.qty * dec(orig_line.cost))
        resolved.append(
            {
                "drug": drug,
                "orig_line": orig_line,
                "lm": lm,
                "idx": idx,
                "barcode": barcode,
                "cogs": line_cogs,
            }
        )
        cogs_total += line_cogs

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
    for item in resolved:
        orig_line = item["orig_line"]
        lm = item["lm"]
        allocs = await _allocations_for_line(
            session,
            branch_id=branch_id,
            original_id=original.id,
            orig_line_id=orig_line.id,
        )
        # #51: FIFO-spillover lines must restore each source lot proportionally,
        # not re-create a single earliest-expiry batch. We only take the restore
        # path when the sale actually spilled over (allocs > 1); single-lot
        # sales keep the legacy synthetic batch so existing tests stay green and
        # the non-spillover path remains the documented fallback.
        if allocs is not None and len(allocs) > 1:
            restored = await restore_return_allocations(
                session,
                branch_id=branch_id,
                user_id=user_id,
                invoice_no=invoice_no,
                drug_id=orig_line.drug_id,
                allocations=allocs,
                returned_qty=lm.qty,
                barcode=item["barcode"],
                vat_rate=round2(tax_rate(lm.tax_type) * Decimal("100")),
                price=orig_line.unit_price,
                vat_amount=lm.vat,
                total_with_vat=lm.line_total,
            )
            if restored:
                item["batch"] = restored[0]
                # Build payload restores from the allocations + computed shares
                # so the offline replay can reproduce the exact per-lot restores.
                shares = _split_return_shares(allocs, lm.qty)
                # restored order matches allocs order (zero-shares skipped);
                # zip them to emit a faithful payload
                payload_restores: list[dict] = []
                r_idx = 0
                for alloc, sh in zip(allocs, shares):
                    if dec(sh) <= 0:
                        continue
                    # restored[r_idx] corresponds to this alloc's share
                    b = restored[r_idx] if r_idx < len(restored) else restored[0]
                    r_idx += 1
                    cost_raw = alloc.get("cost")
                    expire_raw = alloc.get("expire")
                    payload_restores.append(
                        {
                            "batch_id": b.id,
                            "randomid": b.randomid,
                            "expire": expire_raw if expire_raw is not None else (b.expire.isoformat() if b.expire else None),
                            "cost": str(cost_raw) if cost_raw not in (None, "") else str(b.cost),
                            "qty": str(sh),
                        }
                    )
                item["restored_batches"] = payload_restores
                continue
        # Legacy single-batch fallback (also used when allocations missing)
        item["batch"] = await create_return_batch(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            idx=item["idx"],
            drug_id=orig_line.drug_id,
            qty=lm.qty,
            cost=round4(orig_line.cost),
            price=orig_line.unit_price,
            vat_rate=round2(tax_rate(lm.tax_type) * Decimal("100")),
            vat_amount=lm.vat,
            total_with_vat=lm.line_total,
            expire=orig_line.expire,
            barcode=item["barcode"],
        )
    if payments is not None:
        payed, agel, splits = _resolve_payments(payments, totals["total"])
    else:
        payed, agel, splits = await _mirror_refund(session, original, totals["total"])
    if agel > dec(original.agel) - await _already_credited(session, original.id):
        raise CREDIT_OVERFLOW

    invoice = Invoice(
        branch_id=branch_id,
        kind="sale_return",
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        ref_invoice_id=original.id,
        subtotal=totals["subtotal"],
        discount=totals["discount"],
        vat=totals["vat"],
        totalvalue=totals["total"],
        payed=payed,
        agel=agel,
        party_id=original.party_id,
        status="saved",
        writer=writer,
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
            f"sale_return {invoice_no} ref={original.invoice_no} "
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
        action="sale_return",
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
            cost=round4(item["cogs"] / lm.qty),
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

    await record_payment_splits(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        direction="out",
        reason=SALE_RETURN,
        splits=splits,
        ref_invoice_id=invoice.id,
    )

    entry_no = await next_journal_entry_no(session, branch_id, datee)
    entries: list[tuple[str, Decimal, Decimal]] = []
    if payed > 0:
        entries.append(("1000", Decimal("0"), payed))
    if agel > 0:
        entries.append(("1100", Decimal("0"), agel))
    if totals["net"] > 0:
        entries.append(("4000", totals["net"], Decimal("0")))
    if totals["vat"] > 0:
        entries.append(("2100", totals["vat"], Decimal("0")))
    if cogs_total > 0:
        entries.append(("6000", Decimal("0"), cogs_total))
        entries.append(("1200", cogs_total, Decimal("0")))
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
        contra_party_by_code={"1100": original.party_id} if original.party_id else None,
    )

    await _snapshot_invoice(session, original, action="sale_return", user_id=user_id)

    payload = _return_payload(
        invoice,
        resolved,
        splits,
        entry_no,
        totals,
        inclusive,
        original.id,
        original.invoice_no,
    )
    # S4.1 (#28): the return's tax document (receipt 'r' / credit note 'C')
    # references the original and is written in the SAME transaction (G12).
    log = await issue_for_invoice(
        session,
        invoice=invoice,
        branch=branch,
        lines=resolved,
        totals=totals,
        splits=splits,
        party=None if original.party_id is None else await session.get(
            Party, original.party_id
        ),
    )
    payload["einvoice"] = einvoice_block(log)
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="invoice",
        entity_id=invoice.id,
        action="insert",
        payload=payload,
    )
    return invoice