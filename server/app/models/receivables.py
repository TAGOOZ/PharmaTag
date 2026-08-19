"""Receivables models: settlement vouchers (S2.4, ticket #19)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SettlementVoucher(Base):
    """`settlement_vouchers` — the ledger reference row for a سند قبض/سند صرف.

    One row per posted settlement: branch-scoped, per-branch monotonic
    `voucher_no`, the party it moves (customer for a receipt, supplier for a
    payment voucher), the drawer method, the exact amount, and the `journals`
    entry it produced (source `settlement`). `reverses_voucher_id` links an
    A07-style reversal back to the voucher it offsets — never an edit/delete
    of the original.
    """

    __tablename__ = "settlement_vouchers"
    __table_args__ = (
        CheckConstraint(
            "voucher_type IN ('receipt', 'payment')",
            name="ck_settlement_voucher_type",
        ),
        CheckConstraint(
            "method IN ('cash', 'network')", name="ck_settlement_voucher_method"
        ),
        CheckConstraint("amount > 0", name="ck_settlement_voucher_amount"),
        UniqueConstraint("branch_id", "voucher_no", name="uq_settlement_vouchers_branch_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    voucher_no: Mapped[int] = mapped_column(Integer, nullable=False)
    voucher_type: Mapped[str] = mapped_column(String(20), nullable=False)
    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parties.id"), nullable=False)
    datee: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    journal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("journals.id"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, server_default="")
    reverses_voucher_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("settlement_vouchers.id")
    )
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )