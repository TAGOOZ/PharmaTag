"""Wire models for the S2.2 manual-journal API (ticket #17).

A manual entry (قيد يومي) is a dated, described set of single-sided lines that
must balance exactly: SUM(debit) == SUM(credit) after round-half-up-2dp. The
client sends raw amounts; the server owns rounding and the balanced check.
Money leaves as exact decimal strings (plan/02 §2).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ManualJournalLine(BaseModel):
    account_code: str = Field(min_length=1, max_length=30)
    debit: Optional[Decimal] = Field(default=None, ge=0)
    credit: Optional[Decimal] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=50)


class ManualJournalCreate(BaseModel):
    datee: date
    description: str = Field(min_length=1, max_length=200)
    lines: list[ManualJournalLine] = Field(min_length=2, max_length=50)