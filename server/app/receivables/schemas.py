"""Wire models for the S2.4 settlement API (ticket #19).

A settlement (سند قبض / سند صرف) is one dated amount against one party, paid by
cash or by the drawer's network split (`card` is accepted and normalized to the
drawer's `network` word). Money leaves as exact decimal strings (plan/02 §2).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SettlementVoucherCreate(BaseModel):
    voucher_type: Literal["receipt", "payment"]
    party_id: int
    datee: date
    method: Literal["cash", "network", "card"] = "cash"
    amount: Decimal = Field(gt=0)
    description: Optional[str] = Field(default=None, max_length=200)