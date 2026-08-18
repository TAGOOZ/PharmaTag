"""Wire models for the sales-return API (S1.5, ticket #11).

The client sends only the ORIGINAL invoice line ids + returned quantities —
never computed totals (money is server-authoritative). `qty` is 4dp as exact
decimal. `payments` is optional: when absent the server mirrors the original
sale's payment methods proportionally; when present it must reconcile to the
return total like a sale.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.sales.schemas import PaymentSplitIn


class ReturnLineIn(BaseModel):
    ref_invoice_line_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class ReturnCreateRequest(BaseModel):
    lines: list[ReturnLineIn] = Field(min_length=1)
    payments: Optional[list[PaymentSplitIn]] = None
    datee: Optional[date] = None