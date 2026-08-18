"""Sales invoice models (header, lines, payment splits)."""
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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    invoice_kind_enum,
    invoice_status_enum,
    payment_method_enum,
    tax_type_enum,
)


class Invoice(Base):
    """`invoices` header (C-4). Columns mirror rev 001 EXACTLY — the sale slice
    (S1.3) owns the money/journal/stock logic; `save_sale` is the bus seam."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("branch_id", "invoice_no", name="uq_invoices_branch_no"),
        CheckConstraint("payed + agel = totalvalue", name="ck_invoice_payment"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    kind: Mapped[str] = mapped_column(invoice_kind_enum, nullable=False, server_default="sale")
    invoice_no: Mapped[str] = mapped_column(String(30), nullable=False)
    datee: Mapped[date] = mapped_column(Date, nullable=False)
    datetimee: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    silsilaid: Mapped[Optional[str]] = mapped_column(String(15), server_default="")
    party_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("parties.id"))
    ref_invoice_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("invoices.id"))
    subtotal: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    discount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    vat: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    totalvalue: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    payed: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    agel: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(invoice_status_enum, nullable=False, server_default="saved")
    writer: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    last_edited_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class InvoiceLine(Base):
    """`invoice_lines` — one row per sold line. `cost` is the weighted unit
    cost (4dp) of the batches consumed; per-batch allocations live in the
    outbox payload for exact replay."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_invoice_line_unit_price"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoices.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"), nullable=False)
    batch_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("stock_batches.id"))
    ref_invoice_line_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("invoice_lines.id"))
    qty: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    unit: Mapped[str] = mapped_column(String(20), server_default="pack")
    unit_price: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    cost: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    disc: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    tax_type: Mapped[str] = mapped_column(tax_type_enum, nullable=False, server_default="exempt")
    vat: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    vat_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    line_total: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    expire: Mapped[Optional[date]] = mapped_column(Date)
    minimum: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    tips: Mapped[str] = mapped_column(String(50), server_default="")
    iddatetime: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class PaymentSplit(Base):
    """`payment_splits` — how a sale was paid (cash/card/credit). The invoice
    CHECK `payed + agel = totalvalue` reconciles splits to the header."""

    __tablename__ = "payment_splits"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_split_amount"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoices.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    method: Mapped[str] = mapped_column(payment_method_enum, nullable=False, server_default="cash")
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))


class InvoiceVersion(Base):
    """`invoice_versions` — snapshot of an invoice when it is edited/returned
    (S1.5): the original sale's state is preserved before a return or edit, so
    the audit trail always shows what the document looked like before the
    change. `payload` mirrors the invoice header+lines (JSON primitives)."""

    __tablename__ = "invoice_versions"
    __table_args__ = (
        UniqueConstraint("invoice_id", "version_no", name="uq_invoice_versions"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoices.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), server_default="")
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )