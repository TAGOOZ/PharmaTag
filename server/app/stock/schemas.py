"""Wire models for the S1.7 stock-count API (ticket #13).

The client sends the physical `counted` quantity the pharmacist observed; the
server derives the signed `delta` against the system balance and stores it
(feature_stock_counting §2.1 — "the system computes the correction"). All qty
values are 4dp exact decimals.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CountRequestCreate(BaseModel):
    drug_id: int = Field(gt=0)
    counted: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    reason: Optional[str] = Field(default=None, max_length=200)
    batch_id: Optional[int] = Field(default=None, gt=0)


class CountRequestOut(BaseModel):
    id: int
    branch_id: int
    drug_id: int
    batch_id: Optional[int] = None
    delta: str
    counted: Optional[str] = None
    system_qty: str
    reason: str = ""
    status: str
    requested_by: Optional[int] = None
    approved_by: Optional[int] = None
    rejected_by: Optional[int] = None
    decided_at: Optional[str] = None
    created_at: Optional[str] = None


class CountRequestListOut(BaseModel):
    requests: list[CountRequestOut] = []


class CurrentStockOut(BaseModel):
    branch_id: int
    drug_id: int
    drugname: str
    drugnamear: str = ""
    barcode: str = ""
    qty: str
    minimum: str
    price: str = "0.0000"
    batches: list[dict] = []


class CurrentStockListOut(BaseModel):
    items: list[CurrentStockOut] = []
    count: int | None = None
    truncated: bool | None = None


class MinimumSetRequest(BaseModel):
    drug_id: int = Field(gt=0)
    minimum: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class MinimumSetResponse(BaseModel):
    branch_id: int
    drug_id: int
    qty: str
    minimum: str
    silsilaid: str = ""
    classy: str = ""