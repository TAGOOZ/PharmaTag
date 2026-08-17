"""Users, roles and permissions (RBAC) models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Identity, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, user_roles_table


class Role(Base):
    """`roles` — named bundles of permissions (plan/00 G25, legacy floor 1)."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(200), server_default="")

    users: Mapped[list["User"]] = relationship(secondary=user_roles_table, back_populates="roles")


class Permission(Base):
    """`permissions` — one row per permission code (e.g. `users.manage`)."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name_ar: Mapped[str] = mapped_column(String(100), server_default="")


class User(Base):
    """`users` — login identity + legacy `permission_level` (1–9) plus
    granular role/permission rows (plan/00 G25)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    namee: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    mobile: Mapped[Optional[str]] = mapped_column(String(15), server_default="")
    pass_hash: Mapped[str] = mapped_column(String(255), server_default="")
    permission_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    branch_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("branches.id"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    roles: Mapped[list[Role]] = relationship(secondary=user_roles_table, back_populates="users")