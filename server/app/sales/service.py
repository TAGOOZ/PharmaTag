"""The `sale.saved` seam + the real S1.3 sale write (ticket #9).

`save_sale` is the single entry point for a sale write. Called with no lines it
keeps the ORIGINAL seam behavior (header-only invoice + `sale.saved` in both
phases, ticket #3) so the plugin-host tests stay green. Called with lines it
runs the full sale: per-line price resolution (G06 tax_type), canonical per-line
money, expiry-FIFO batch allocation, the balanced journal, account balances,
audit rows and the outbox snapshot — all inside ONE atomic() so the mutation,
its audit and its replication intent live or die together (G12).

`apply_sale_payload` reconstructs the same sale from an outbox snapshot
(explicit batch allocations — FIFO is NOT re-run) so the offline replay path
reproduces the exact batches, costs and journal and stays idempotent through the
UNIQUE(branch_id, invoice_no) dedupe key.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import ACTION_INSERT, audit, enqueue_sync
from app.core.db import atomic
from app.core.events import (
    AFTER_COMMIT,
    IN_TXN,
    SALE_SAVED,
    EventBus,
    SaleContext,
    bus,
)
from app.core.money import add, dec, format2, line_money, round2, round4, tax_rate
from app.models import (
    Branch,
    Drug,
    DrugBarcode,
    Invoice,
    InvoiceLine,
    PaymentSplit,
    StockBatch,
)
from app.sales.journal import post_sale_journal
from app.sales.numbering import (
    acquire_branch_lock,
    next_invoice_no,
    next_journal_entry_no,
)
from app.sales.stock import Allocation, allocate_expiry_fifo, decrement_allocations

PRICE_MISMATCH = HTTPException(
    status.HTTP_400_BAD_REQUEST, "payment total does not match sale total"
)
DISCOUNT_OVERFLOW = HTTPException(
    status.HTTP_400_BAD_REQUEST, "discount exceeds sale total"
)


def _price_for(drug: Drug, price_level: str) -> Decimal:
    if price_level == "public":
        return dec(drug.price or 0)
    if price_level == "wholesale":
        return dec(drug.price_wholesale or 0)
    if price_level == "cost":
        return dec(drug.price_cost or 0)
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST, f"unknown price_level {price_level!r}"
    )


def _sale_totals(resolved, disc_percent, *, inclusive: bool) -> dict:
    """Header totals from per-line canonical money (mirrors money.invoice_money:
    subtotal = Σ gross, discount = line discounts + invoice-level percent,
    vat = Σ per-line VAT, total/net per the inclusive flag)."""
    subtotal = add(item["lm"].gross for item in resolved)
    line_disc = add(item["lm"].discount for item in resolved)
    invoice_disc = (
        round2(subtotal * dec(disc_percent) / Decimal("100"))
        if disc_percent is not None
        else Decimal("0")
    )
    discount = line_disc + invoice_disc
    vat = add(item["lm"].vat for item in resolved)
    total = round2(subtotal - discount + (vat if not inclusive else Decimal("0")))
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
    }


async def _primary_barcode(session: AsyncSession, drug_id: int) -> str:
    row = (
        await session.execute(
            select(DrugBarcode).where(
                DrugBarcode.drug_id == drug_id,
                DrugBarcode.is_primary.is_(True),
            )
        )
    ).scalars().first()
    return row.barcode if row else ""


async def _save_header_only(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: str,
    datee: date,
) -> Invoice:
    """The original seam behavior: header-only invoice, zero totals."""
    invoice = Invoice(
        branch_id=branch_id,
        kind="sale",
        invoice_no=invoice_no,
        datee=datee,
        status="saved",
        subtotal=0,
        discount=0,
        vat=0,
        totalvalue=0,
        payed=0,
        agel=0,
        created_by=user_id,
    )
    session.add(invoice)
    await session.flush()
    return invoice


def _resolve_payments(
    payments, total: Decimal
) -> tuple[Decimal, Decimal, list[tuple[str, Decimal]]]:
    """Resolve payment splits; payed (cash/card) + agel (credit) == total."""
    total = round2(total)
    if payments is None or not payments:
        payments = [_Payment(cash=total)]
    paid_sum = Decimal("0")
    credit_sum = Decimal("0")
    splits: list[tuple[str, Decimal]] = []
    for p in payments:
        method = getattr(p, "method", "cash")
        amount = getattr(p, "amount", None)
        if amount is None:
            amount = round2(total - paid_sum - credit_sum)
        else:
            amount = round2(amount)
        if amount > 0:
            splits.append((method, amount))
        if method == "credit":
            credit_sum += amount
        else:
            paid_sum += amount
    payed = round2(paid_sum)
    agel = round2(credit_sum)
    if round2(payed + agel) != total:
        raise PRICE_MISMATCH
    return payed, agel, splits


class _Payment:
    """Minimal payment duck-type (pydantic models or this default)."""

    def __init__(self, *, cash: Decimal) -> None:
        self.method = "cash"
        self.amount = cash


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
) -> Invoice:
    """The full sale: resolve lines, allocate stock, write header + lines +
    splits + journal + balances, audit everything, enqueue the outbox row."""
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "branch not found")
    inclusive = bool(branch.vat_inclusive_prices)

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
    )

    payload = _sale_payload(invoice, resolved, splits, entry_no, totals, inclusive)
    await enqueue_sync(
        session,
        branch_id=branch_id,
        entity="invoice",
        entity_id=invoice.id,
        action="insert",
        payload=payload,
    )
    return invoice


def _sale_payload(
    invoice: Invoice,
    resolved: list[dict],
    splits: list[tuple[str, Decimal]],
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
        "created_by": invoice.created_by,
        "journal": {"entry_no": entry_no, "source": "sale"},
        "lines": lines,
        "payments": [{"method": m, "amount": str(a)} for m, a in splits],
    }


async def save_sale(
    session: AsyncSession,
    *,
    branch_id: int,
    user_id: Optional[int],
    invoice_no: Optional[str] = None,
    datee: Optional[date] = None,
    lines: Optional[list[Any]] = None,
    disc_percent: Optional[Any] = None,
    payments: Optional[list[Any]] = None,
    price_level: str = "public",
    bus: EventBus = bus,
) -> Invoice:
    """Save a sale, emitting `sale.saved` in both phases.

    With `lines` empty/None this keeps the ORIGINAL seam contract (header-only
    invoice). With lines it runs the full money/stock/journal write. The branch
    advisory lock serializes numbering; the whole write is one transaction.
    """
    datee = datee or date.today()
    async with atomic(session) as committed:
        await acquire_branch_lock(session, branch_id)
        if invoice_no is None:
            invoice_no = await next_invoice_no(session, branch_id)
        if lines is None or not lines:
            invoice = await _save_header_only(
                session,
                branch_id=branch_id,
                user_id=user_id,
                invoice_no=invoice_no,
                datee=datee,
            )
        else:
            invoice = await _build_full_sale(
                session,
                branch_id=branch_id,
                user_id=user_id,
                invoice_no=invoice_no,
                datee=datee,
                lines=lines,
                disc_percent=disc_percent,
                payments=payments,
                price_level=price_level,
            )
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="invoices",
            entity_id=invoice.id,
            action=ACTION_INSERT,
            new_value=f"invoice_no={invoice_no} total={format2(invoice.totalvalue)}",
            typevalue=invoice_no,
        )
        await session.flush()
        ctx = SaleContext(
            session=session,
            branch_id=branch_id,
            user_id=user_id,
            sale=invoice,
            payload=_ctx_payload(invoice),
        )
        await bus.emit(SALE_SAVED, ctx, phase=IN_TXN)
    if committed:
        await bus.emit(SALE_SAVED, ctx, phase=AFTER_COMMIT)
    return invoice


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
    return invoice