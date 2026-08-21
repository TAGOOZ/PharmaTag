"""Wire models for the S2.7 opening-balances API (ticket #22).

An opening-balances entry is a balanced set of single-sided lines that seeds
the ledger at cutover: افتتاحي مدين/دائن per account. The client sends the
target month/year and the raw lines; the server owns rounding, validates the
balanced invariant, writes a balanced `journals` entry (source=opening) dated
the day before the opening month, plus a `month_open_balances` snapshot for
that month — both atomically with an audit row (G12).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class OpeningBalanceLine(BaseModel):
    account_code: str = Field(min_length=1, max_length=30)
    debit: Optional[Decimal] = Field(default=None, ge=0)
    credit: Optional[Decimal] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=50)


class OpeningBalancesCreate(BaseModel):
    description: Optional[str] = Field(default=None, max_length=200)
    lines: list[OpeningBalanceLine] = Field(min_length=2, max_length=100)
