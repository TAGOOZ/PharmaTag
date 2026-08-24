"""Inter-pharmacy transfer models (ticket #32, S5.2; decisions T1–T7).

`transfers` — one stock movement between two branches with delivery-state
tracking: `draft → dispatched → received`, `cancelled` only from draft.
`transfer_lines.alloc_json` snapshots the explicit batch allocations taken at
dispatch so receive creates target batches at preserved cost/expire verbatim
and a shortfall auto-returns to the exact source batches (replay-safe).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Transfer(Base):
    """`transfers` — header: source/target branches + delivery state."""

    __tablename__ = "transfers"
    __table_args__ = (
        UniqueConstraint("source_branch_id", "transfer_no", name="uq_transfers_branch_no"),
        CheckConstraint(
            "source_branch_id <> target_branch_id", name="ck_transfers_distinct_branches"
        ),
        CheckConstraint(
            "status IN ('draft', 'dispatched', 'received', 'cancelled')",
            name="ck_transfers_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    source_branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id"), nullable=False
    )
    target_branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id"), nullable=False
    )
    transfer_no: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="draft")
    legacy_fatid: Mapped[Optional[str]] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    dispatched_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    received_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    cancelled_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    received_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class TransferLine(Base):
    """`transfer_lines` — per-drug quantities; `alloc_json` written at dispatch."""

    __tablename__ = "transfer_lines"
    __table_args__ = (
        UniqueConstraint("transfer_id", "drug_id", name="uq_transfer_lines_transfer_drug"),
        CheckConstraint("sent_qty > 0", name="ck_transfer_lines_sent_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    transfer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transfers.id", ondelete="CASCADE"), nullable=False
    )
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"), nullable=False)
    sent_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    alloc_json: Mapped[Optional[list]] = mapped_column(JSON)
