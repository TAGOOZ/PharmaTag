"""Sales endpoints (S1.3, ticket #9).

Writes (POST) are gated by `sale.create` (legacy level-1 area المبيعات, plan/02
§3; admin/pharmacist/cashier roles cover it). Reads are open to any
authenticated user and are branch-scoped to the caller's branch. Totals are
exact decimal strings (plan/02 §2 — money never leaves as a float). The print
view is the 80mm/A5 brand receipt (plan/09 P06).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rbac import require_permission
from app.core import money
from app.core.db import get_session
from app.core.time import business_date
from app.einvoicing import print_templates
from app.einvoicing.service import seller_identity
from app.models import (
    Branch,
    Drug,
    EInvoiceLog,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    Party,
    PaymentSplit,
    User,
)
from app.sales import print_html
from app.sales.returns.schemas import ReturnCreateRequest
from app.sales.returns.service import save_sale_return
from app.sales.schemas import SaleCreateRequest, SaleOut
from app.sales.service import save_sale

router = APIRouter()

CREATE_SALE = require_permission("sale.create")


def _money(value) -> str:
    return money.format2(value)


def _qty(value) -> str:
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


async def _serialize_sale(
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
    lines = [inv_line for inv_line, _ in rows]
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

    net = money.round2(
        money.dec(invoice.totalvalue) - money.dec(invoice.vat)
    )
    return SaleOut(
        id=invoice.id,
        branch_id=invoice.branch_id,
        kind=invoice.kind,
        invoice_no=invoice.invoice_no,
        datee=invoice.datee.isoformat(),
        silsilaid=invoice.silsilaid or "",
        status=invoice.status,
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
                "unit_price": money.format2(line.unit_price),
                "cost": money.format2(line.cost),
                "tax_type": line.tax_type,
                "vat_amount": _money(line.vat_amount),
                "line_total": _money(line.line_total),
            }
            for line, drug in rows
        ],
        payments=[
            {"method": p.method, "amount": _money(p.amount)} for p in payments
        ],
        journal=journal_info,
    ).model_dump()


@router.get("")
async def list_sales(
    datee: Optional[date] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Recent sales for the caller's branch (today by default)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(Invoice).where(
        Invoice.branch_id == branch_id, Invoice.kind == "sale"
    )
    if datee is not None:
        q = q.where(Invoice.datee == datee)
    else:
        q = q.where(Invoice.datee == business_date())
    q = q.order_by(Invoice.id.desc()).limit(limit)
    invoices = (await session.execute(q)).scalars().all()
    return {
        "sales": [
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "datee": inv.datee.isoformat(),
                "totalvalue": _money(inv.totalvalue),
                "payed": _money(inv.payed),
                "agel": _money(inv.agel),
                "status": inv.status,
            }
            for inv in invoices
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SaleCreateRequest,
    caller: User = Depends(CREATE_SALE),
    session: AsyncSession = Depends(get_session),
):
    """Record a sale: server-resolved prices/VAT, expiry-FIFO stock, balanced
    journal, audit + outbox in one transaction."""
    branch_id = _caller_branch_id(caller)
    invoice = await save_sale(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        datee=body.datee,
        lines=body.lines,
        disc_percent=body.disc_percent,
        payments=body.payments,
        party_id=body.party_id,
    )
    return await _serialize_sale(session, invoice, caller)


@router.get("/returns")
async def list_sales_returns(
    datee: Optional[date] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Recent sales returns for the caller's branch (today by default)."""
    branch_id = _caller_branch_id(user)
    limit = max(1, min(limit, 200))
    q = select(Invoice).where(
        Invoice.branch_id == branch_id, Invoice.kind == "sale_return"
    )
    if datee is not None:
        q = q.where(Invoice.datee == datee)
    else:
        q = q.where(Invoice.datee == business_date())
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
            }
            for inv in invoices
        ]
    }


@router.post("/{sale_id}/return", status_code=status.HTTP_201_CREATED, response_model=SaleOut)
async def create_sale_return(
    sale_id: int,
    body: ReturnCreateRequest,
    caller: User = Depends(CREATE_SALE),
    session: AsyncSession = Depends(get_session),
):
    """Record a sales return: reverses the original sale's stock + balances +
    money into a new sale_return invoice (server-computed totals, balanced
    journal, audit + outbox + invoice_versions in one transaction)."""
    branch_id = _caller_branch_id(caller)
    invoice = await save_sale_return(
        session,
        branch_id=branch_id,
        user_id=caller.id,
        original_invoice_id=sale_id,
        lines=body.lines,
        payments=body.payments,
        datee=body.datee,
    )
    return await _serialize_sale(session, invoice, caller)


@router.get("/{sale_id}", response_model=SaleOut)
async def get_sale(
    sale_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    branch_id = _caller_branch_id(user)
    invoice = await _invoice_or_404(session, sale_id, branch_id)
    return await _serialize_sale(session, invoice, user)


@router.get("/{sale_id}/tax-document/print", response_class=HTMLResponse)
async def print_tax_document(
    sale_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Printable tax document (S4.1, #28): ضريبية / مبسطة / أجل / مرتجع —
    variant auto-routed from the invoice + its einvoice_log regime kind,
    with QR, RIN block and VAT-by-rate breakdown."""
    branch_id = _caller_branch_id(user)
    invoice = await _invoice_or_404(session, sale_id, branch_id)
    log = (
        await session.execute(
            select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice.id)
        )
    ).scalar_one_or_none()
    if log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tax document not found")
    branch = await session.get(Branch, branch_id)
    party = (
        await session.get(Party, invoice.party_id)
        if invoice.party_id is not None
        else None
    )
    lines = (
        await session.execute(
            select(InvoiceLine, Drug)
            .join(Drug, Drug.id == InvoiceLine.drug_id)
            .where(InvoiceLine.invoice_id == invoice.id)
            .order_by(InvoiceLine.id)
        )
    ).all()
    cashier = ""
    if invoice.created_by is not None:
        cashier_row = await session.get(User, invoice.created_by)
        if cashier_row is not None:
            cashier = cashier_row.namee or cashier_row.username
    seller = await seller_identity(session)
    # exclusive-VAT branches store line_total ALREADY ex-VAT — only inclusive
    # lines need VAT subtracted to recover the taxable net
    vat_inclusive = bool(branch.vat_inclusive_prices) if branch else True
    reference_invoice_no = ""
    if invoice.ref_invoice_id is not None:
        original = await session.get(Invoice, invoice.ref_invoice_id)
        if original is not None:
            reference_invoice_no = original.invoice_no

    def _net(line: InvoiceLine) -> str:
        total = money.dec(line.line_total)
        if vat_inclusive:
            total -= money.dec(line.vat_amount)
        return money.format2(total)

    html_body = print_templates.render_tax_document(
        branch_name=branch.pharname if branch else "",
        invoice_no=invoice.invoice_no,
        datee=invoice.datee,
        cashier=cashier,
        variant=print_templates.route_variant(invoice, log),
        counter=int(log.counter),
        status=log.status,
        qr_data=log.qr_data or "",
        seller_rin=seller["rin"],
        seller_trade_name=seller["trade_name"],
        branch_code=branch.pharmacyid if branch else "",
        device_serial=log.device_serial or "",
        buyer_name=party.namee if party else "",
        buyer_tax_registration_no=(
            (party.tax_registration_no or "") if party else ""
        ),
        reference_invoice_no=reference_invoice_no,
        lines=[
            {
                "description": drug.drugnamear or drug.drugname,
                "qty": _qty(line.qty),
                "unit_price": money.format2(line.unit_price),
                "vat_amount": _money(line.vat_amount),
                "net": _net(line),
                "line_total": _money(line.line_total),
                "tax_type": line.tax_type,
            }
            for line, drug in lines
        ],
        subtotal=invoice.subtotal,
        discount=invoice.discount,
        vat=invoice.vat,
        totalvalue=invoice.totalvalue,
        payed=invoice.payed,
        agel=invoice.agel,
    )
    return HTMLResponse(content=html_body, status_code=status.HTTP_200_OK)


@router.get("/{sale_id}/print", response_class=HTMLResponse)
async def print_sale(
    sale_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """80mm / A5 printable receipt (RTL, brand accent, black-on-white print)."""
    branch_id = _caller_branch_id(user)
    invoice = await _invoice_or_404(session, sale_id, branch_id)
    branch = await session.get(Branch, branch_id)
    lines = (
        await session.execute(
            select(InvoiceLine, Drug)
            .join(Drug, Drug.id == InvoiceLine.drug_id)
            .where(InvoiceLine.invoice_id == invoice.id)
            .order_by(InvoiceLine.id)
        )
    ).all()
    cashier = ""
    if invoice.created_by is not None:
        cashier_row = await session.get(User, invoice.created_by)
        if cashier_row is not None:
            cashier = cashier_row.namee or cashier_row.username
    html_body = print_html.render_invoice_print(
        branch_name=branch.pharname if branch else "",
        invoice_no=invoice.invoice_no,
        datee=invoice.datee,
        cashier=cashier,
        lines=[
            {
                "drugname": drug.drugname,
                "qty": _qty(line.qty),
                "unit_price": money.format2(line.unit_price),
                "line_total": _money(line.line_total),
            }
            for line, drug in lines
        ],
        subtotal=_money(invoice.subtotal),
        discount=_money(invoice.discount),
        vat=_money(invoice.vat),
        totalvalue=_money(invoice.totalvalue),
        payed=_money(invoice.payed),
        agel=_money(invoice.agel),
        status=invoice.status,
    )
    return HTMLResponse(content=html_body, status_code=status.HTTP_200_OK)