"""The full sale write: resolve lines, allocate stock, write everything.

`_build_full_sale` is the heart of S1.3 (ticket #9): it runs inside one
`atomic()` transaction along with the header save, audit rows and outbox
enqueue (G12) — the mutation, its audit and its replication intent live or
die together.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit, enqueue_sync
from app.core.money import add, dec, format2, line_money, round2, round4, tax_rate
from app.drawer.movements import SALE, record_payment_splits
from app.einvoicing.service import einvoice_block, issue_for_invoice
from app.models import (
    Branch,
    Drug,
    DrugBarcode,
    Invoice,
    InvoiceLine,
    Party,
    PaymentSplit,
)
from app.sales.journal import post_sale_journal
from app.sales.numbering import next_journal_entry_no
from app.sales.payload import _sale_payload
from app.sales.payments import _resolve_payments
from app.sales.pricing import _price_for, _sale_totals
from app.sales.stock import allocate_expiry_fifo, decrement_allocations
from app.receivables.service import ensure_credit_ok


async def _primary_barcode(session: AsyncSession, drug_id: int) -> str:
    """The drug's primary barcode, used for audit/batch provenance."""
    row = (
        await session.execute(
            select(DrugBarcode).where(
                DrugBarcode.drug_id == drug_id,
                DrugBarcode.is_primary.is_(True),
            )
        )
    ).scalars().first()
    return row.barcode if row else ""


async def _build_full_sale(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    datee: date,
    lines: list[Any],
    disc_percent,
    payments,
    price_level: str,
    party_id: Optional[int] = None,
) -> Invoice:
    """The full sale: resolve lines, allocate stock, write header + lines +
    splits + journal + balances, audit everything, enqueue the outbox row."""
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found")
    inclusive = bool(branch.vat_inclusive_prices)

    customer: Optional[Party] = None
    if party_id is not None:
        customer = await session.get(Party, party_id)
        if customer is None or customer.branch_id != branch_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
        if customer.kind not in ("customer", "both"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "party is not a customer"
            )
        if not customer.active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "customer is inactive"
            )

    resolved: list[dict] = []
    cogs_total = Decimal("0")
    for line in lines:
        drug = await session.get(Drug, line.drug_id)
        if drug is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "drug not found")
        if not drug.active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "drug is inactive")
        level = getattr(line, "price_level", None) or price_level
        unit_price = _price_for(drug, level)
        lm = line_money(
            line.qty,
            unit_price,
            drug.tax_type,
            disc_percent=getattr(line, "disc_percent", None),
            inclusive=inclusive,
        )
        allocations = await allocate_expiry_fifo(
            session,
            branch_id=branch_id,
            drug_id=drug.id,
            qty=lm.qty,
        )
        line_cogs = await decrement_allocations(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=drug.id,
            allocations=allocations,
            barcode=await _primary_barcode(session, drug.id),
        )
        resolved.append(
            {"drug": drug, "lm": lm, "allocations": allocations, "cogs": line_cogs}
        )
        cogs_total += line_cogs

    totals = _sale_totals(resolved, disc_percent, inclusive=inclusive)
    payed, agel, splits = _resolve_payments(payments, totals["total"])

    if agel > 0 and customer is not None:
        # F11.3: a credit sale must not push the customer's AR debt past the
        # party's credit limit (0 = unlimited). Runs in this transaction so the
        # check and the posting can never race.
        await ensure_credit_ok(
            session, branch_id=branch_id, party=customer, new_agel=agel
        )

    invoice = Invoice(
        branch_id=branch_id,
        kind="sale",
        invoice_no=invoice_no,
        datee=datee,
        datetimee=datetime.now(timezone.utc),
        subtotal=totals["subtotal"],
        discount=totals["discount"],
        vat=totals["vat"],
        totalvalue=totals["total"],
        payed=payed,
        agel=agel,
        party_id=customer.id if customer else None,
        status="saved",
        created_by=user_id,
    )
    session.add(invoice)
    await session.flush()

    for item in resolved:
        drug = item["drug"]
        lm = item["lm"]
        allocations = item["allocations"]
        cogs = item["cogs"]
        line = InvoiceLine(
            invoice_id=invoice.id,
            branch_id=branch_id,
            drug_id=drug.id,
            batch_id=allocations[0].batch_id if allocations else None,
            qty=lm.qty,
            unit="pack",
            unit_price=lm.unit_price,
            cost=round4(cogs / lm.qty),
            disc=lm.discount,
            tax_type=lm.tax_type,
            vat=round2(tax_rate(lm.tax_type) * Decimal("100")),
            vat_amount=lm.vat,
            line_total=lm.line_total,
            expire=allocations[0].expire if allocations else None,
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
                f"qty={lm.qty} price={format2(lm.unit_price)} "
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
        direction="in",
        reason=SALE,
        splits=splits,
        ref_invoice_id=invoice.id,
    )

    entry_no = await next_journal_entry_no(session, branch_id, datee)
    entries: list[tuple[str, Decimal, Decimal]] = []
    if payed > 0:
        entries.append(("1000", payed, Decimal("0")))
    if agel > 0:
        entries.append(("1100", agel, Decimal("0")))
    if totals["net"] > 0:
        entries.append(("4000", Decimal("0"), totals["net"]))
    if totals["vat"] > 0:
        entries.append(("2100", Decimal("0"), totals["vat"]))
    if cogs_total > 0:
        entries.append(("6000", cogs_total, Decimal("0")))
        entries.append(("1200", Decimal("0"), cogs_total))
    await post_sale_journal(
        session,
        branch_id=branch_id,
        user_id=user_id,
        datee=datee,
        entry_no=entry_no,
        description=f"فاتورة بيع {invoice_no}",
        entries=entries,
        ref_invoice_id=invoice.id,
        contra_party_by_code={"1100": customer.id} if customer else None,
    )

    payload = _sale_payload(invoice, resolved, splits, entry_no, totals, inclusive)
    # S4.1 (#28): the tax document is written INSIDE the same transaction
    # (G12; STRICT per A09) and rides the outbox snapshot verbatim.
    log = await issue_for_invoice(
        session,
        invoice=invoice,
        branch=branch,
        lines=resolved,
        totals=totals,
        splits=splits,
        party=customer,
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