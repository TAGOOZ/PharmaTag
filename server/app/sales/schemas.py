"""Wire models for the sales API (S1.3, ticket #9).

Clients send only quantities + identifiers — never computed totals (plan/02 §2:
money is server-authoritative, resolved through the money engine). `qty` is
4dp, money fields 2dp, both as exact decimals.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

PriceLevel = Literal["public", "wholesale", "cost"]
PaymentMethod = Literal["cash", "card", "credit", "manual_cash", "manual_card"]


class SaleLineIn(BaseModel):
    drug_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    price_level: Optional[PriceLevel] = None
    disc_percent: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )


class PaymentSplitIn(BaseModel):
    method: PaymentMethod = "cash"
    amount: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )


class SaleCreateRequest(BaseModel):
    lines: list[SaleLineIn] = Field(min_length=1)
    disc_percent: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    payments: Optional[list[PaymentSplitIn]] = None
    datee: Optional[date] = None


class SaleLineOut(BaseModel):
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


class PaymentSplitOut(BaseModel):
    method: str
    amount: str


class SaleOut(BaseModel):
    id: int
    branch_id: int
    kind: str
    invoice_no: str
    datee: str
    silsilaid: str = ""
    status: str
    ref_invoice_id: Optional[int] = None
    subtotal: str
    discount: str
    vat: str
    totalvalue: str
    net: str
    payed: str
    agel: str
    created_by: Optional[int] = None
    lines: list[SaleLineOut] = []
    payments: list[PaymentSplitOut] = []
    journal: Optional[dict] = None