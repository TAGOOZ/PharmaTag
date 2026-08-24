"""Tenant/branch + app config + audit/outbox plumbing models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Identity,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, sync_status_enum


class Branch(Base):
    """`branches` (wzphar) — mirrored from rev 001 so FKs resolve; used by
    branch-scoped write paths. Not a full domain object yet."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pharmacyid: Mapped[str] = mapped_column(String(15), nullable=False)
    phar: Mapped[str] = mapped_column(String(15), server_default="")
    mobile: Mapped[str] = mapped_column(String(15), nullable=False)
    pharname: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    adress: Mapped[Optional[str]] = mapped_column(String(200), server_default="")
    governorate: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    district: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    country: Mapped[Optional[str]] = mapped_column(String(50), server_default="")
    currency: Mapped[Optional[str]] = mapped_column(String(10), server_default="")
    vat_default: Mapped[object] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("14.00")
    )
    vat_inclusive_prices: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    is_main_device: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class BranchIdentity(Base):
    """`branch_identities` — alias map from a legacy natural key
    (table, column, value), e.g. (wzphar, pharmacyid, 'X'), to the one
    canonical branch id. Keeps ETL/chain replay from duplicating branches."""

    __tablename__ = "branch_identities"

    legacy_table: Mapped[str] = mapped_column(String(50), primary_key=True)
    legacy_column: Mapped[str] = mapped_column(String(50), primary_key=True)
    legacy_value: Mapped[str] = mapped_column(String(100), primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id"), nullable=False
    )


class AuditLog(Base):
    """`audit_log` — one row per audited mutation (G12), written in the same
    transaction as the mutation it records."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("branches.id"))
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    field: Mapped[str] = mapped_column(String(50), server_default="")
    old_value: Mapped[Optional[str]] = mapped_column(Text())
    new_value: Mapped[Optional[str]] = mapped_column(Text())
    drug_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("drugs.id"))
    barcode: Mapped[str] = mapped_column(String(16), server_default="")
    action: Mapped[str] = mapped_column(String(30), nullable=False, server_default="update")
    namee: Mapped[str] = mapped_column(String(100), server_default="")
    typevalue: Mapped[str] = mapped_column(String(100), server_default="")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class SyncLog(Base):
    """`sync_log` — transactional outbox (G12): one pending row per mutation,
    enqueued atomically with the mutation for offline replay."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), nullable=False)
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(30), nullable=False, server_default="update")
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    synced_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(sync_status_enum, nullable=False, server_default="pending")
    source_device_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("branches.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class AppConfig(Base):
    """`app_config` — key/value application config (incl. `plugins_enabled`)."""

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(50), server_default="")
    value_numeric: Mapped[Optional[object]] = mapped_column(Numeric(18, 4))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )