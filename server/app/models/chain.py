"""Needs + purchase-order models (ticket #33, S5.3; decisions N1–N6).

`needs` — inter-pharmacy stock request (titanneed 6-col): a branch asks a
sister branch for stock. `sender_branch_id` NULL = open request any sister
can pick up. `transfer_id` links the handoff transfer (auto-fulfilled on
receive). `rev` = monotonic version watermark for versioned offline replay.

`purchase_orders` / `purchase_order_lines` — supplier orders. Legacy `orders`
was header-only ('saved' = done); lines are invented so auto-order output and
distributor item lists have somewhere to live. No money mutation until the
purchases receipt posts.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Need(Base):
    """`needs` — نواقص: one drug request from one branch to another."""

    __tablename__ = "needs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'fulfilled', 'cancelled')", name="ck_needs_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id"), nullable=False
    )
    drug_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("drugs.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="0"
    )
    datee: Mapped[Optional[date]] = mapped_column(Date)
    sender_branch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("branches.id")
    )
    target_branch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("branches.id")
    )
    legacy_sender: Mapped[str] = mapped_column(String(20), server_default="")
    legacy_target: Mapped[str] = mapped_column(String(20), server_default="")
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="pending"
    )
    transfer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("transfers.id", use_alter=True)
    )
    # version watermark for replay ordering (#55 pattern); bumped IN the
    # transition transaction (G12)
    rev: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class PurchaseOrder(Base):
    """`purchase_orders` — header (legacy `orders`: NULL=pending → 'pending')."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'saved', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id"), nullable=False
    )
    party_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("parties.id")
    )
    orderid: Mapped[str] = mapped_column(String(50), server_default="")
    orderdate: Mapped[Optional[date]] = mapped_column(Date)
    datee: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="pending"
    )
    rev: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    saved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    received_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class PurchaseOrderLine(Base):
    """`purchase_order_lines` — invented (legacy kept contents unstructured)."""

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "drug_id", name="uq_po_lines_order_drug"),
        CheckConstraint("qty > 0", name="ck_po_lines_qty_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    drug_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("drugs.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    received_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
