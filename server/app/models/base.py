"""Shared SQLAlchemy `Base`, DB enums, and association tables.

Enums mirror the types already created by alembic rev 001; they are wired to
model columns with `create_type=False` so we never re-create them.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# --- enums shared by model columns (already created by rev 001) ---
tax_type_enum = ENUM("exempt", "5%", "14%", name="tax_type", create_type=False)
batch_type_enum = ENUM(
    "purchase", "sale", "return", "count", "transfer_in", "transfer_out",
    "opening", "correction", name="batch_type", create_type=False,
)
sync_status_enum = ENUM(
    "pending", "applied", "failed", "skipped", name="sync_status", create_type=False,
)
invoice_kind_enum = ENUM(
    "sale", "purchase", "sale_return", "purchase_return", "transfer",
    name="invoice_kind", create_type=False,
)
invoice_status_enum = ENUM(
    "saved", "unsaved", "unsave", "copy", "transfer_to_sale_return",
    "transfer_to_purchase", "closed", "archived", "void", name="invoice_status",
    create_type=False,
)
account_type_enum = ENUM(
    "asset", "liability", "equity", "income", "expense", name="account_type",
    create_type=False,
)
journal_source_enum = ENUM(
    "sale", "purchase", "sale_return", "purchase_return", "manual",
    "transfer", "opening", "settlement", "correction", name="journal_source",
    create_type=False,
)
payment_method_enum = ENUM(
    "cash", "card", "credit", "manual_cash", "manual_card", name="payment_method",
    create_type=False,
)

user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id"), primary_key=True),
)

role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permissions.id"), primary_key=True),
)