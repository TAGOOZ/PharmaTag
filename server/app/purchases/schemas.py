"""Wire models for the purchases API (S1.4, ticket #10).

Clients send only quantities + identifiers — never computed totals (plan/02 §2:
money is server-authoritative, resolved through the money engine). `qty` and
`unit_cost` are 4dp, money fields 2dp, both as exact decimals. The purchase
unit cost is the amount charged by the supplier (VAT-inclusive per the branch
flag); the server derives the net (inventory) cost and input VAT per line.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field

from app.sales.schemas import PaymentSplitIn


class PurchaseLineIn(BaseModel):
    drug_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    # S5.5: accept legacy wire aliases so replay/older clients sending
    # ``cost``/``price`` (titanksastock legacy, test_stock_cross_branch) remain
    # green — ``unit_cost`` is canonical, the two aliases are compat-only.
    unit_cost: Decimal = Field(
        validation_alias=AliasChoices("unit_cost", "cost", "price"),
        ge=0,
        max_digits=18,
        decimal_places=4,
    )
    expire: Optional[date] = None
    disc_percent: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )


class PurchaseCreateRequest(BaseModel):
    supplier_id: int = Field(gt=0)
    lines: list[PurchaseLineIn] = Field(min_length=1)
    disc_percent: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    payments: Optional[list[PaymentSplitIn]] = None
    datee: Optional[date] = None


class PurchaseLineOut(BaseModel):
    id: int
    drug_id: int
    drugname: str
    drugnamear: str = ""
    batch_id: Optional[int] = None
    ref_invoice_line_id: Optional[int] = None
    qty: str
    unit: str = "pack"
    unit_price: str
    cost: str
    tax_type: str
    vat_amount: str
    line_total: str
    expire: Optional[str] = None


class PaymentSplitOut(BaseModel):
    method: str
    amount: str


class PurchaseOut(BaseModel):
    id: int
    branch_id: int
    kind: str
    invoice_no: str
    datee: str
    silsilaid: str = ""
    status: str
    party_id: Optional[int] = None
    ref_invoice_id: Optional[int] = None
    subtotal: str
    discount: str
    vat: str
    totalvalue: str
    net: str
    payed: str
    agel: str
    created_by: Optional[int] = None
    lines: list[PurchaseLineOut] = []
    payments: list[PaymentSplitOut] = []
    journal: Optional[dict] = None
