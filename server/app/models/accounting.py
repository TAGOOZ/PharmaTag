"""Accounting models: parties, chart of accounts, journals and balances."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import ENUM, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    account_type_enum,
    journal_source_enum,
)


class Party(Base):
    """`parties` (wzcustomers + companies) — mirrored so Invoice FKs resolve."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    kind: Mapped[str] = mapped_column(
        ENUM("customer", "supplier", "both", name="party_kind", create_type=False),
        nullable=False,
        server_default="customer",
    )
    typee: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    namee: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    name_ar: Mapped[Optional[str]] = mapped_column(String(100), server_default="")
    mobile: Mapped[Optional[str]] = mapped_column(String(15), server_default="")
    adress: Mapped[Optional[str]] = mapped_column(String(200), server_default="")
    governorate: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    district: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    credit_limit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    receivable_account_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    payable_account_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    writer: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    randomid: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    datee: Mapped[Optional[date]] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class Account(Base):
    """`accounts` (wzaccfreetree) — chart of accounts. Seeded by rev 002;
    used by the sale slice's journal/balances posting."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("branch_id", "code", name="uq_accounts_branch_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    master: Mapped[str] = mapped_column(String(100), server_default="")
    fary: Mapped[str] = mapped_column(String(100), server_default="")
    name_ar: Mapped[str] = mapped_column(String(120), server_default="")
    name_en: Mapped[str] = mapped_column(String(120), server_default="")
    type: Mapped[str] = mapped_column(account_type_enum, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class Journal(Base):
    """`journals` (farysales) — one balanced entry per sale."""

    __tablename__ = "journals"
    __table_args__ = (
        UniqueConstraint("branch_id", "datee", "entry_no", name="uq_journals_entry"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    datee: Mapped[date] = mapped_column(Date, nullable=False)
    entry_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(journal_source_enum, nullable=False, server_default="sale")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="posted")
    ref_invoice_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("invoices.id"))
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class JournalLine(Base):
    """`journal_lines` — one side per account; a journal is balanced iff
    SUM(debit) == SUM(credit)."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint(
            "debit >= 0 AND credit >= 0 AND (debit = 0 OR credit = 0)",
            name="ck_journal_line_single_side",
        ),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_journal_line_month"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    journal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("journals.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), nullable=False)
    debit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    credit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    contra_party_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("parties.id"))
    datee: Mapped[date] = mapped_column(Date, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    creditdebit: Mapped[str] = mapped_column(String(20), server_default="")
    randomid: Mapped[str] = mapped_column(String(50), server_default="")
    writer: Mapped[str] = mapped_column(String(50), server_default="")
    tips: Mapped[str] = mapped_column(String(50), server_default="")
    classy: Mapped[str] = mapped_column(String(35), server_default="")


class Balance(Base):
    """`balances` (farysales monthe/yearo) — per (branch, account, month, year)
    running debit/credit totals. CHECK keeps `balance = debit - credit`."""

    __tablename__ = "balances"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_balances_month"),
        CheckConstraint("balance = debit - credit", name="ck_balances_identity"),
    )

    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), primary_key=True)
    month: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    debit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    credit: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    balance: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class ManualJournalEntry(Base):
    """`manual_journal_entries` (daily-manual.phy) — the ledger's reference row
    for a posted manual journal (القيود اليدوية). `journal_id` links the
    balanced `journals` entry this manual entry produced; `reverses_entry_id`
    links a reversal back to the entry it offset (S2.2, ticket #17)."""

    __tablename__ = "manual_journal_entries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    record_no: Mapped[Optional[int]] = mapped_column(Integer)
    datee: Mapped[Optional[date]] = mapped_column(Date)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    source_file: Mapped[str] = mapped_column(String(50), server_default="daily-manual.phy")
    journal_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("journals.id"))
    reverses_entry_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("manual_journal_entries.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )