"""Month-close models: monthly_close + month_open_balances (S2.6, #21).

Mirrors `alembic/versions/013_month_close.py` exactly — no invented columns.
`monthly_close` archives the period (monthy\\moves); `month_open_balances`
seeds the next month's opening balances (monthy\\start-data).

Archive interpretation (S2.6): the archive IS the `monthly_close` row
(status closed/reopened) plus the `month_open_balances` snapshot for the
following month (monthy\\start-data). No separate `archive_imports` /
`archive_exports` row or `\\Files\\Archive\\Input`/`Output` file is created in
this slice — those tables live in the `tools` plugin per plan/01 §3.8 and
remain deferred, consistent with prior S2 slices (settlement_vouchers,
manual journals) that keep ledger tables in `public`.

Status default is 'open' (like `daily_close.status`), matching spec
plan/01 §3.5 `open/closed/reopened`. A month with no `monthly_close` row is
open (absent = open); the table materializes only closed/reopened states.
`server_default='open'` therefore never fires on the happy path
(`close_month` always writes status='closed' explicitly) but keeps the schema
consistent and makes an accidental bare INSERT produce an open month rather
than a phantom closed one.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, close_status_enum


class MonthlyClose(Base):
    """`monthly_close` — one row per (branch_id, year, month), status
    open/closed/reopened (spec plan/01 §3.5; A07 for reopen). `closed` freezes
    the month; `reopened` allows new posts again until re-closed. A month with
    no row is open (absent = open); the default 'open' is the conceptual state
    and the DDL default — close always writes 'closed' explicitly so the
    server_default never fires on the happy path, but the schema now mirrors
    `daily_close.status='open'` and the spec instead of a misleading
    'closed' default. The archive for S2.6 is this row plus the seeded
    `month_open_balances` snapshot for the following month."""

    __tablename__ = "monthly_close"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_monthly_close_month"),
    )

    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(close_status_enum, nullable=False, server_default="open")
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
