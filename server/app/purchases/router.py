"""Purchases endpoints (S1.4, ticket #10).

Writes (POST) are gated by the legacy level-2 area المشتريات (plan/02 §3;
only admin level >= 2 may record purchases — buying is a senior action). Reads
are open to any authenticated user and are branch-scoped to the caller's
branch. Totals are exact decimal strings (plan/02 §2).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_level
from app.core import money
from app.core.db import get_session
from app.models import Drug, Invoice, InvoiceLine, Journal, JournalLine, PaymentSplit, User
from app.purchases.returns.schemas import ReturnCreateRequest
from app.purchases.returns.service import save_purchase_return
from app.purchases.schemas import PurchaseCreateRequest, PurchaseOut
from app.purchases.service import save_purchase

router = APIRouter()

CREATE_PURCHASE = require_level(2)


def _money(value) -> str:
    return money.format2(value)


def _qty(value) -> str:
    return format(money.round4(value), "f")


def _unit(value) -> str:
    """A 4dp unit amount (batch cost / unit price) as an exact string."""
    return format(money.round4(value), "f")


def _caller_branch_id(user: User) -> int:
    if user.branch_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user has no branch assigned")
    return user.branch_id


async def _invoice_or_404(session: AsyncSession, invoice_id: int, branch_id: int) -> Invoice:
    invoice = (
        await session.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.branch_id == branch_id)
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    return invoice


async def _serialize_purchase(
    session: AsyncSession, invoice: Invoice, user: User
) -> dict:
    rows = (
        await session.execute(
            select(InvoiceLine, Drug)
            .join(Drug, Drug.id == InvoiceLine.drug_id)
            .where(InvoiceLine.invoice_id == invoice.id)
            .order_by(InvoiceLine.id)
        )
    ).all()
    payments = (
        await session.execute(
            select(PaymentSplit)
            .where(PaymentSplit.invoice_id == invoice.id)
            .order_by(PaymentSplit.id)
        )
    ).scalars().all()
    journal = (
        await session.execute(
            select(Journal).where(Journal.ref_invoice_id == invoice.id)
        )
    ).scalars().first()
    journal_info: Optional[dict] = None
    if journal is not None:
        jlines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        debit_total = money.add(jl.debit for jl in jlines)
        credit_total = money.add(jl.credit for jl in jlines)
        journal_info = {
            "id": journal.id,
            "entry_no": journal.entry_no,
            "datee": journal.datee.isoformat(),
            "balanced": debit_total == credit_total,
            "debit_total": _money(debit_total),
            "credit_total": _money(credit_total),
        }

    net = money.round2(money.dec(invoice.totalvalue) - money.dec(invoice.vat))
    return PurchaseOut(
        id=invoice.id,
        branch_id=invoice.branch_id,
        kind=invoice.kind,
        invoice_no=invoice.invoice_no,
        datee=invoice.datee.isoformat(),
        silsilaid=invoice.silsilaid or "",
        status=invoice.status,
        party_id=invoice.party_id,
        ref_invoice_id=invoice.ref_invoice_id,
        subtotal=_money(invoice.subtotal),
        discount=_money(invoice.discount),
        vat=_money(invoice.vat),
        totalvalue=_money(invoice.totalvalue),
        net=_money(net),
        payed=_money(invoice.payed),
        agel=_money(invoice.agel),
        created_by=invoice.created_by,
        lines=[
            {
                "id": line.id,
                "drug_id": line.drug_id,
                "drugname": drug.drugname,
                "drugnamear": drug.drugnamear,
                "batch_id": line.batch_id,
                "ref_invoice_line_id": line.ref_invoice_line_id,
                "qty": _qty(line.qty),
                "unit": line.unit or "pack",
                "unit_price": _money(line.unit_price),
                "cost": _unit(line.cost),
                "tax_type": line.tax_type,
                "vat_amount": _money(line.vat_amount),
                "line_total": _money(line.line_total),
                "expire": line.expire.isoformat() if line.expire else None,
            }
            for line, drug in rows
        ],
        payments=[{"method": p.method, "amount": _money(p.amount)} for p in payments],
        journal=journal_info,
    ).model_dump()


@router.get("")
async def list_purchases(
    datee: Optional[date] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Recent purchases for the caller's branch (today by default)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(Invoice).where(
        Invoice.branch_id == branch_id, Invoice.kind == "purchase"
    )
    if datee is not None:
        q = q.where(Invoice.datee == datee)
    else:
        q = q.where(Invoice.datee == datetime.now().date())
    q = q.order_by(Invoice.id.desc()).limit(limit)
    invoices = (await session.execute(q)).scalars().all()
    return {
        "purchases": [
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "datee": inv.datee.isoformat(),
                "totalvalue": _money(inv.totalvalue),
                "payed": _money(inv.payed),
                "agel": _money(inv.agel),
                "status": inv.status,
                "party_id": inv.party_id,
            }
            for inv in invoices
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_purchase(
    body: PurchaseCreateRequest,
    caller: User = Depends(CREATE_PURCHASE),
    session: AsyncSession = Depends(get_session),
):
    """Record a purchase: new batches at net cost, stock-up, supplier payable,
    balanced journal, audit + outbox in one transaction."""
    branch_id = _caller_branch_id(caller)
    invoice = await save_purchase(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        supplier_id=body.supplier_id,
        datee=body.datee,
        lines=body.lines,
        disc_percent=body.disc_percent,
        payments=body.payments,
    )
    return await _serialize_purchase(session, invoice, caller)


@router.get("/returns")
async def list_purchases_returns(
    datee: Optional[date] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Recent purchase returns for the caller's branch (today by default)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(Invoice).where(
        Invoice.branch_id == branch_id, Invoice.kind == "purchase_return"
    )
    if datee is not None:
        q = q.where(Invoice.datee == datee)
    else:
        q = q.where(Invoice.datee == datetime.now().date())
    q = q.order_by(Invoice.id.desc()).limit(limit)
    invoices = (await session.execute(q)).scalars().all()
    return {
        "returns": [
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "ref_invoice_id": inv.ref_invoice_id,
                "datee": inv.datee.isoformat(),
                "totalvalue": _money(inv.totalvalue),
                "payed": _money(inv.payed),
                "agel": _money(inv.agel),
                "status": inv.status,
                "party_id": inv.party_id,
            }
            for inv in invoices
        ]
    }


@router.post("/{purchase_id}/return", status_code=status.HTTP_201_CREATED, response_model=PurchaseOut)
async def create_purchase_return(
    purchase_id: int,
    body: ReturnCreateRequest,
    caller: User = Depends(CREATE_PURCHASE),
    session: AsyncSession = Depends(get_session),
):
    """Record a purchase return: reverses the original purchase's stock +
    balances + money into a new purchase_return invoice (server-computed totals,
    balanced journal, audit + outbox + invoice_versions in one transaction)."""
    branch_id = _caller_branch_id(caller)
    invoice = await save_purchase_return(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        original_invoice_id=purchase_id,
        lines=body.lines,
        payments=body.payments,
        datee=body.datee,
    )
    return await _serialize_purchase(session, invoice, caller)


@router.get("/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = _caller_branch_id(user)
    invoice = await _invoice_or_404(session, purchase_id, branch_id)
    return await _serialize_purchase(session, invoice, user)
