"""Offline replay of a sale from its outbox snapshot.

`apply_sale_payload` reconstructs the same sale using the payload's explicit
batch allocations — FIFO is NOT re-run — so the target store reproduces the
exact batches, costs and journal, and stays idempotent through the
UNIQUE(branch_id, invoice_no) dedupe key.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit
from app.core.money import dec, format2, round2, tax_rate
from app.drawer.movements import SALE, record_payment_splits
from app.einvoicing.service import apply_einvoice_block
from app.models import Invoice, InvoiceLine, Party, PaymentSplit, StockBatch
from app.receivables.service import ensure_credit_ok
from app.sales.journal import post_sale_journal
from app.sales.numbering import acquire_branch_lock, next_journal_entry_no
from app.sales.stock import Allocation, decrement_allocations


async def apply_sale_payload(
    session: AsyncSession,
    *,
    branch_id: int,
    payload: dict[str, Any],
    user_id: Optional[int] = None,
) -> Invoice:
    """Reconstruct a sale from its outbox snapshot (offline replay path).

    Uses the payload's explicit batch allocations — FIFO is NOT re-run — so the
    target store reproduces the exact batches, costs and journal. The caller
    (sync.replay_pending) owns dedupe via uq_invoices_branch_no and the
    status/failure transitions. Assumes it runs inside the caller's transaction.
    """
    await acquire_branch_lock(session, branch_id)
    invoice_no = payload["invoice_no"]
    datee = date.fromisoformat(payload["datee"])
    customer: Optional[Party] = None
    party_id = payload.get("party_id")
    if party_id is not None:
        customer = await session.get(Party, party_id)
        if customer is None or customer.branch_id != branch_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"party {party_id} missing on target store",
            )
        if customer.kind not in ("customer", "both"):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"party {party_id} is not a customer on target store",
            )
        if not customer.active:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"party {party_id} is inactive on target store",
            )
        if dec(payload.get("agel", 0)) > 0:
            # F11.3: replay re-runs the credit-limit guard exactly like the live
            # builder — the target store may hold debt the offline source never
            # saw, so the check must run HERE, in the same transaction, before
            # any stock or journal write touches this row.
            await ensure_credit_ok(
                session,
                branch_id=branch_id,
                party=customer,
                new_agel=dec(payload.get("agel", 0)),
            )

    resolved: list[tuple[dict, list[Allocation]]] = []
    cogs_total = Decimal("0")
    for lp in payload["lines"]:
        allocations: list[Allocation] = []
        for a in lp["allocations"]:
            batch = await session.get(StockBatch, a["batch_id"])
            if batch is None:
                batch = (
                    await session.execute(
                        select(StockBatch).where(
                            StockBatch.branch_id == branch_id,
                            StockBatch.drug_id == lp["drug_id"],
                            StockBatch.randomid == a["randomid"],
                        )
                    )
                ).scalar_one_or_none()
            if batch is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"stock batch {a['batch_id']} missing on target store",
                )
            if dec(batch.qty) < dec(a["take"]):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"stock batch {batch.id} has insufficient qty on target store",
                )
            allocations.append(
                Allocation(
                    batch_id=batch.id,
                    randomid=batch.randomid,
                    take=dec(a["take"]),
                    cost=dec(a["cost"]),
                    expire=batch.expire,
                )
            )
        line_cogs = await decrement_allocations(
            session,
            branch_id=branch_id,
            user_id=user_id,
            invoice_no=invoice_no,
            drug_id=lp["drug_id"],
            allocations=allocations,
            barcode="",
        )
        resolved.append((lp, allocations))
        cogs_total += line_cogs

    invoice = Invoice(
        branch_id=branch_id,
        kind=payload.get("kind", "sale"),
        invoice_no=invoice_no,
        datee=datee,
        silsilaid=payload.get("silsilaid", ""),
        subtotal=dec(payload["subtotal"]),
        discount=dec(payload["discount"]),
        vat=dec(payload["vat"]),
        totalvalue=dec(payload["totalvalue"]),
        payed=dec(payload["payed"]),
        agel=dec(payload["agel"]),
        party_id=customer.id if customer else None,
        status=payload.get("status", "saved"),
        created_by=payload.get("created_by") or user_id,
    )
    session.add(invoice)
    await session.flush()

    for lp, allocations in resolved:
        line = InvoiceLine(
            invoice_id=invoice.id,
            branch_id=branch_id,
            drug_id=lp["drug_id"],
            batch_id=allocations[0].batch_id if allocations else None,
            qty=dec(lp["qty"]),
            unit="pack",
            unit_price=dec(lp["unit_price"]),
            cost=dec(lp["unit_cost"]),
            disc=dec(lp.get("discount", 0)),
            tax_type=lp["tax_type"],
            vat=round2(tax_rate(lp["tax_type"]) * Decimal("100")),
            vat_amount=dec(lp["vat_amount"]),
            line_total=dec(lp["line_total"]),
            expire=(
                date.fromisoformat(lp["expire"]) if lp.get("expire") else None
            ),
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
            drug_id=lp["drug_id"],
            new_value=(
                f"qty={lp['qty']} price={lp['unit_price']} "
                f"tax={lp['tax_type']} total={lp['line_total']} (replay)"
            ),
            typevalue=invoice_no,
        )

    for p in payload.get("payments", []):
        session.add(
            PaymentSplit(
                invoice_id=invoice.id,
                branch_id=branch_id,
                method=p["method"],
                amount=dec(p["amount"]),
                user_id=user_id,
            )
        )
    await session.flush()

    payments = [(p["method"], p["amount"]) for p in payload.get("payments", [])]
    if payments:
        await record_payment_splits(
            session,
            branch_id=branch_id,
            user_id=user_id,
            datee=datee,
            direction="in",
            reason=SALE,
            splits=payments,
            ref_invoice_id=invoice.id,
        )

    net = dec(payload.get("net", dec(payload["totalvalue"]) - dec(payload["vat"])))
    entries: list[tuple[str, Decimal, Decimal]] = []
    if dec(payload["payed"]) > 0:
        entries.append(("1000", dec(payload["payed"]), Decimal("0")))
    if dec(payload["agel"]) > 0:
        entries.append(("1100", dec(payload["agel"]), Decimal("0")))
    if net > 0:
        entries.append(("4000", Decimal("0"), net))
    if dec(payload["vat"]) > 0:
        entries.append(("2100", Decimal("0"), dec(payload["vat"])))
    if cogs_total > 0:
        entries.append(("6000", cogs_total, Decimal("0")))
        entries.append(("1200", Decimal("0"), cogs_total))
    entry_no = await next_journal_entry_no(session, branch_id, datee)
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
    await audit(
        session,
        branch_id=branch_id,
        user_id=user_id,
        entity="invoices",
        entity_id=invoice.id,
        action=ACTION_INSERT,
        new_value=f"invoice_no={invoice_no} total={format2(invoice.totalvalue)} (replay)",
        typevalue=invoice_no,
    )
    # S4.1 (#28): re-attach the tax document from the snapshot VERBATIM —
    # same counter/uuid chain position, never re-generated (idempotent).
    block = payload.get("einvoice")
    if block:
        await apply_einvoice_block(
            session, branch_id=branch_id, invoice_id=invoice.id, block=block
        )
    return invoice