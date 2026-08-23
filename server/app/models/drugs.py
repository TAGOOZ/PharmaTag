"""Drug master data models (drugs, barcodes, price-change log)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, tax_type_enum


class Drug(Base):
    """`drugs` (wzdrugs) — the drug master. `tax_type` is exempt/5%/14% and
    drives the per-line VAT split on sales/purchases (plan/00)."""

    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    drugname: Mapped[str] = mapped_column(String(100), nullable=False)
    drugnamear: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    generic: Mapped[Optional[str]] = mapped_column(String(120), server_default="")
    classy: Mapped[Optional[str]] = mapped_column(String(35), server_default="")
    pharmacology: Mapped[Optional[str]] = mapped_column(String(200), server_default="")
    co: Mapped[Optional[str]] = mapped_column(String(100), server_default="")
    unitsclass: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    tax_type: Mapped[str] = mapped_column(tax_type_enum, nullable=False, server_default="exempt")
    vat: Mapped[Optional[object]] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    units: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    unitsmall: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    price: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    price_wholesale: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    price_cost: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    price_now: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    disco: Mapped[Optional[object]] = mapped_column(Numeric(5, 2), server_default="0")
    pricechanged: Mapped[Optional[bool]] = mapped_column(Boolean, server_default="false")
    localimport: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    titanid: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    history: Mapped[Optional[str]] = mapped_column(Text(), server_default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # EGS code registered with ETA for this drug (#30): nullable until Ops
    # registers it; item coding prefers a GS1 GTIN barcode, then this.
    egs_code: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    lastedit: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    barcodes: Mapped[list["DrugBarcode"]] = relationship(
        back_populates="drug", cascade="all, delete-orphan"
    )


class DrugBarcode(Base):
    """`drug_barcodes` — a drug's up-to-6 codes (wzdrugs barcode + Barcode1..5).

    Partial-unique `barcode` (WHERE barcode <> '') prevents two drugs sharing a
    code without blocking the empty-string default rows (plan/01 §1.3#4).
    """

    __tablename__ = "drug_barcodes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    drug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("drugs.id"), nullable=False)
    barcode: Mapped[str] = mapped_column(String(16), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    drug: Mapped[Drug] = relationship(back_populates="barcodes")


class PriceChangeLog(Base):
    """`price_change_log` (storediscount lineage, plan/02 §4.6) — one row per
    price change on a drug, written in the same transaction as the drug write."""

    __tablename__ = "price_change_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("branches.id"))
    drug_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    barcode: Mapped[str] = mapped_column(String(16), server_default="")
    price: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    disco: Mapped[Optional[object]] = mapped_column(Numeric(5, 2), server_default="0")
    units: Mapped[int] = mapped_column(Integer, server_default="0")
    quant: Mapped[Optional[object]] = mapped_column(Numeric(18, 4), server_default="0")
    datee: Mapped[Optional[date]] = mapped_column(Date)
    tips: Mapped[str] = mapped_column(String(200), server_default="")
    country: Mapped[str] = mapped_column(String(50), server_default="")
    storename: Mapped[str] = mapped_column(String(100), server_default="")
    pharmacyname: Mapped[str] = mapped_column(String(100), server_default="")
    pharmacyname2: Mapped[str] = mapped_column(String(100), server_default="")
    titanver: Mapped[str] = mapped_column(String(20), server_default="")
    pricechanged: Mapped[Optional[bool]] = mapped_column(Boolean, server_default="false")
    localimport: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )