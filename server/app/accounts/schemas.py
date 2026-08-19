"""Wire models for the S2.1 chart-of-accounts API (ticket #16).

Account rows are branch-scoped configuration; the client supplies the code,
bilingual names, account `type` (the legacy five-way hierarchy — asset /
liability / equity / income / expense), an optional `parent_id`, and an active
flag. Reads (list/tree/detail) are open to any authenticated user; writes are
gated by `accounts.manage` (legacy floor 7, accountant role).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

AccountType = Literal["asset", "liability", "equity", "income", "expense"]


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name_ar: str = Field(min_length=1, max_length=120)
    name_en: Optional[str] = Field(default=None, max_length=120)
    type: AccountType
    parent_id: Optional[int] = Field(default=None, gt=0)
    is_active: bool = True


class AccountUpdate(BaseModel):
    """Every field optional; `model_dump(exclude_unset=True)` distinguishes an
    explicit `parent_id: null` (clear the parent) from an omitted field."""

    code: Optional[str] = Field(default=None, min_length=1, max_length=30)
    name_ar: Optional[str] = Field(default=None, min_length=1, max_length=120)
    name_en: Optional[str] = Field(default=None, max_length=120)
    type: Optional[AccountType] = None
    parent_id: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None