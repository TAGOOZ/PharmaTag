"""Drawer & day-close models: drawer_movements, daily_close.

Mirror `alembic/versions/001_core_schema.py` sections 8 + 12 exactly — no
invented columns (ticket #2 constraint). The drawer equation lives in
`app/drawer/close.py`; these rows are the ledger the close snapshots.
(`work_periods`/`shifts` exist in the schema but are not ORM-mapped — no slice
drives them yet, ticket #14 keeps the drawer per-cashier via `user_id`.)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    close_status_enum,
    drawer_direction_enum,
    drawer_method_enum,
    drawer_reason_enum,
)


class DrawerMovement(Base):
    """`drawer_movements` (Daily.phy) — one cash-in/cash-out event.

    `reason` tells what kind of flow it is (sale, return, supplier payment,
    expense, opening, ...); `method` splits cash vs network so the day's
    totals (net_cash/net_network/manual_cash/manual_card) are computable.
    """

    __tablename__ = "drawer_movements"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_drawer_amount"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    datee: Mapped[date] = mapped_column(Date, nullable=False)
    direction: Mapped[str] = mapped_column(
        drawer_direction_enum, nullable=False, server_default="in"
    )
    reason: Mapped[str] = mapped_column(
        drawer_reason_enum, nullable=False, server_default="cash_sale"
    )
    method: Mapped[str] = mapped_column(
        drawer_method_enum, nullable=False, server_default="cash"
    )
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    ref_invoice_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("invoices.id"))
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class DailyClose(Base):
    """`daily_close` (MonyInfo.phy) — the drawer equation snapshot per
    (branch_id, datee), locked by `uq_daily_close`. status closed/reopened.

    `difference = counted_cash - expected_cash` is the deficit/surplus of the
    day (surplus when positive).
    """

    __tablename__ = "daily_close"
    __table_args__ = (
        UniqueConstraint("branch_id", "datee", name="uq_daily_close"),
        CheckConstraint(
            "difference = counted_cash - expected_cash", name="ck_daily_close_diff"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    datee: Mapped[date] = mapped_column(Date, nullable=False)
    drawer_start: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    expected_cash: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    counted_cash: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    difference: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    manual_cash: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    manual_card: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    net_cash: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    net_network: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    purchases: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    expenses: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    cost_of_sales: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    net_profit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    discounts: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    vat_sales: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    vat_purchases: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    vat_expenses: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(close_status_enum, nullable=False, server_default="open")
    closed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))