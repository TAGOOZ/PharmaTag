"""Wire models for the drawer + day-close API (S1.8, ticket #14).

Manual movements carry the direction/reason/method the drawer_movements enum
allows; `amount` is exact decimal (money never floats, plan/02 §2). Day close
takes the physically counted cash and the server computes the equation.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

DrawerDirection = Literal["in", "out"]
DrawerMethod = Literal["cash", "network"]
DrawerReason = Literal[
    "cash_sale", "cash_return", "supplier_pay", "customer_settlement",
    "expense", "transfer", "opening", "correction",
]


class MovementCreate(BaseModel):
    datee: Optional[date] = None
    direction: DrawerDirection
    reason: DrawerReason
    method: DrawerMethod
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    ref_invoice_id: Optional[int] = None


class MovementOut(BaseModel):
    id: int
    branch_id: int
    datee: str
    direction: str
    reason: str
    method: str
    amount: str
    user_id: Optional[int] = None
    ref_invoice_id: Optional[int] = None
    created_at: str


class DayCloseCreate(BaseModel):
    datee: Optional[date] = None
    counted_cash: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class DayCloseOut(BaseModel):
    id: int
    branch_id: int
    datee: str
    drawer_start: str
    expected_cash: str
    counted_cash: str
    difference: str
    net_cash: str
    net_network: str
    manual_cash: str
    manual_card: str
    supplier_payments: str
    purchases: str
    expenses: str
    cost_of_sales: str
    net_profit: str
    discounts: str
    vat_sales: str
    vat_purchases: str
    vat_expenses: str
    status: str
    closed_by: Optional[int] = None
    closed_at: Optional[str] = None