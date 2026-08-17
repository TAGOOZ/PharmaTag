"""Stock models: expiry-tracked batches and per-branch running balances."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, batch_type_enum


class StockBatch(Base):
    """`stock_batches` — one expiry-tracked lot per (branch, drug, randomid);
    consumed FIFO by expiry on sales."""

    __tablename__ = "stock_batches"
    __table_args__ = (
        UniqueConstraint("branch_id", "drug_id", "randomid", name="uq_stock_batches"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"), nullable=False)
    randomid: Mapped[str] = mapped_column(String(50), nullable=False)
    qty: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    expire: Mapped[Optional[date]] = mapped_column(Date)
    cost: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    vat: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    price: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    oldstock: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    typee: Mapped[str] = mapped_column(batch_type_enum, nullable=False, server_default="purchase")
    vatvalue: Mapped[Optional[object]] = mapped_column(Numeric(18, 2), server_default="0")
    totalwithvat: Mapped[Optional[object]] = mapped_column(Numeric(18, 2), server_default="0")
    writer: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    classy: Mapped[Optional[str]] = mapped_column(String(35), server_default="")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class BranchStock(Base):
    """`branch_stock` — per (branch, drug) running quantity + reorder point."""

    __tablename__ = "branch_stock"

    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), primary_key=True)
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"), primary_key=True)
    qty: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    minimum: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    silsilaid: Mapped[Optional[str]] = mapped_column(String(15), server_default="")
    classy: Mapped[Optional[str]] = mapped_column(String(35), server_default="")
    price: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    barcode: Mapped[Optional[str]] = mapped_column(String(16), server_default="")
    lastedit: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))