"""Month-close models: monthly_close + month_open_balances (S2.6, #21).

Mirrors `alembic/versions/013_month_close.py` exactly — no invented columns.
`monthly_close` archives the period (monthy\\moves); `month_open_balances`
seeds the next month's opening balances (monthy\\start-data).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, close_status_enum


class MonthlyClose(Base):
    """`monthly_close` — one row per (branch_id, year, month), status closed
    or reopened (A07). `closed` freezes the month; `reopened` allows new posts
    again until re-closed. The archive is the row itself plus the seeded
    month_open_balances for the following month."""

    __tablename__ = "monthly_close"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_monthly_close_month"),
    )

    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(close_status_enum, nullable=False, server_default="closed")
    closed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class MonthOpenBalance(Base):
    """`month_open_balances` — the opening ledger state for (branch, account,
    year, month), i.e. the cumulative debit/credit through the end of the
    preceding month. Seeded from the closing `journal_lines` when the previous
    month closes (monthy\\start-data)."""

    __tablename__ = "month_open_balances"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_month_open_month"),
    )

    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[int] = mapped_column(primary_key=True)
    debit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    credit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
