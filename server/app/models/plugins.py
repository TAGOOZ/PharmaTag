"""Plugin registry models (C-13)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Identity, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppPlugin(Base):
    """`app_plugins` — installed plugin registry rows (core rev 001, C-13)."""

    __tablename__ = "app_plugins"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    core_requires: Mapped[str] = mapped_column(String(60), nullable=False)
    sdk_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="installed")
    license_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unlicensed")
    license_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    installed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class PluginDependencyRow(Base):
    """`plugin_dependencies` — one row per declared dependency (C-13)."""

    __tablename__ = "plugin_dependencies"

    plugin_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_plugins.id"), primary_key=True
    )
    depends_on: Mapped[str] = mapped_column(String(60), primary_key=True)
    min_version: Mapped[str] = mapped_column(String(20), nullable=False)
    max_version: Mapped[Optional[str]] = mapped_column(String(20))


class PluginBranchGrant(Base):
    """`plugin_branch_grants` — per-branch enablement (C-13, plan/08 §4.3)."""

    __tablename__ = "plugin_branch_grants"

    plugin_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_plugins.id"), primary_key=True
    )
    branch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("branches.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class PluginSettings(Base):
    """`plugin_settings` — per (branch, plugin, key) JSON settings (C-13)."""

    __tablename__ = "plugin_settings"

    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id"), primary_key=True
    )
    plugin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_plugins.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Optional[dict]] = mapped_column(JSONB)
    encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )