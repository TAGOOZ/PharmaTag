"""E-invoice models (S4.1, ticket #28; ADR-0002)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# regime kinds (ADR-0002): retail/walk-in + customer sales issue eReceipt v1.2
# ('receipt'), their returns a return receipt ('r'); credit sales to
# tax-registered parties issue B2B eInvoice v1.0 ('invoice') and their returns
# a credit note ('credit_note').
KIND_RECEIPT = "receipt"
KIND_RETURN_RECEIPT = "return_receipt"
KIND_INVOICE = "invoice"
KIND_CREDIT_NOTE = "credit_note"

# submission status chain (ADR-0002): offline rows stay pending and submit on
# reconnect within ETA's 24-hour window (S4.2 owns the worker).
STATUS_PENDING = "pending"
STATUS_SUBMITTED = "submitted"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"


class EInvoiceCounter(Base):
    """`einvoice_counters` — DB-resident chain state keyed (branch_id, kind).

    `last_uuid` is the previousUUID the next document chains from; counters
    are monotonic, gapless, never reset in fiscal year (A15).
    `device_serial` is nullable in v1 (single unnamed drawer per branch) so
    S5.1 multi-device needs no migration.
    """

    __tablename__ = "einvoice_counters"
    __table_args__ = (
        UniqueConstraint("branch_id", "kind", name="uq_einvoice_counters_branch_kind"),
        CheckConstraint(
            "kind IN ('receipt', 'return_receipt', 'invoice', 'credit_note')",
            name="ck_einvoice_counters_kind",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    last_counter: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    last_uuid: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    device_serial: Mapped[Optional[str]] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.now(timezone.utc),
    )


class EInvoiceLog(Base):
    """`einvoice_log` — one tax document per sales invoice.

    `payload_json` uses PG `json` (NOT jsonb): the receipt UUID recomputes
    from the serialized document whose key ORDER matters, and jsonb would
    reorder keys and break verification.
    """

    __tablename__ = "einvoice_log"
    __table_args__ = (
        UniqueConstraint("branch_id", "kind", "counter", name="uq_einvoice_log_chain"),
        UniqueConstraint("invoice_id", name="uq_einvoice_log_invoice"),
        CheckConstraint(
            "kind IN ('receipt', 'return_receipt', 'invoice', 'credit_note')",
            name="ck_einvoice_log_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'submitted', 'accepted', 'rejected', 'failed')",
            name="ck_einvoice_log_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="pending")
    counter: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uuid: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    previous_uuid: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    reference_uuid: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    device_serial: Mapped[Optional[str]] = mapped_column(String(100))
    qr_data: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON)
    response: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
