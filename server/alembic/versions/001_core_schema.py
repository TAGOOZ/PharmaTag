"""core rev 001 — core truth tables + plugin host (schema `public`)

Hand-written to match schema/schema_postgres.sql exactly, applying the 8
surgical corrections (plan/01 §1.3), G06 (tax_type, vat_inclusive_prices),
G07 (UNIQUE branch_id+invoice_no), G08 (users.permission_level), and A08
scoping: only [C] tier tables + the plugin host ship here. Plugin-owned [S]
tables (einvoice_log/counters, monthly_close/month_open_balances, transfers/
needs, chain tables, drug_interactions, external_drug_catalog, archive_*,
user_drawer_money, drug_sync_outbox, purchase_orders, branch_registry) ship
in their owning plugin's schema/migration — NOT in core rev 001.

Revision ID: 001_core
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_core"
down_revision = None
branch_labels = None
depends_on = None


def _identity() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    # --- enums used by core tables (SQLite twin: TEXT + CHECK) ---
    # postgresql.ENUM (not sa.Enum): generic Enum in SQLAlchemy 2.0 silently
    # ignores create_type, so every column re-emits CREATE TYPE. Native
    # postgresql.ENUM honours create_type=False; types are created explicitly
    # below so tax_type (shared by drugs + invoice_lines) is emitted only once.
    party_kind = postgresql.ENUM("customer", "supplier", "both", name="party_kind", create_type=False)
    account_type = postgresql.ENUM("asset", "liability", "equity", "income", "expense", name="account_type", create_type=False)
    journal_source = postgresql.ENUM(
        "sale", "purchase", "sale_return", "purchase_return", "manual",
        "transfer", "opening", "settlement", "correction", name="journal_source",
        create_type=False,
    )
    invoice_kind = postgresql.ENUM(
        "sale", "purchase", "sale_return", "purchase_return", "transfer",
        name="invoice_kind", create_type=False,
    )
    invoice_status = postgresql.ENUM(
        "saved", "unsaved", "unsave", "copy", "transfer_to_sale_return",
        "transfer_to_purchase", "closed", "archived", "void", name="invoice_status",
        create_type=False,
    )
    payment_method = postgresql.ENUM(
        "cash", "card", "credit", "manual_cash", "manual_card", name="payment_method",
        create_type=False,
    )
    batch_type = postgresql.ENUM(
        "purchase", "sale", "return", "count", "transfer_in", "transfer_out",
        "opening", "correction", name="batch_type",
        create_type=False,
    )
    drawer_direction = postgresql.ENUM("in", "out", name="drawer_direction", create_type=False)
    drawer_method = postgresql.ENUM("cash", "network", name="drawer_method", create_type=False)
    drawer_reason = postgresql.ENUM(
        "cash_sale", "cash_return", "supplier_pay", "customer_settlement",
        "expense", "transfer", "opening", "correction", name="drawer_reason",
        create_type=False,
    )
    close_status = postgresql.ENUM("open", "closed", "reopened", name="close_status", create_type=False)
    shortage_method = postgresql.ENUM("manual", "half_auto", "sales_rate", name="shortage_method", create_type=False)
    correction_status = postgresql.ENUM("pending", "approved", "rejected", name="correction_status", create_type=False)
    sync_status = postgresql.ENUM("pending", "applied", "failed", "skipped", name="sync_status", create_type=False)
    tax_class = postgresql.ENUM("exempt", "5%", "14%", name="tax_type", create_type=False)

    party_kind.create(op.get_bind(), checkfirst=True)
    account_type.create(op.get_bind(), checkfirst=True)
    journal_source.create(op.get_bind(), checkfirst=True)
    invoice_kind.create(op.get_bind(), checkfirst=True)
    invoice_status.create(op.get_bind(), checkfirst=True)
    payment_method.create(op.get_bind(), checkfirst=True)
    batch_type.create(op.get_bind(), checkfirst=True)
    drawer_direction.create(op.get_bind(), checkfirst=True)
    drawer_method.create(op.get_bind(), checkfirst=True)
    drawer_reason.create(op.get_bind(), checkfirst=True)
    close_status.create(op.get_bind(), checkfirst=True)
    shortage_method.create(op.get_bind(), checkfirst=True)
    correction_status.create(op.get_bind(), checkfirst=True)
    sync_status.create(op.get_bind(), checkfirst=True)
    tax_class.create(op.get_bind(), checkfirst=True)

    tz = sa.TIMESTAMP(timezone=True)
    now = sa.text("now()")

    # --- 1. branches (wzphar) ---
    op.create_table(
        "branches",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("pharmacyid", sa.String(15), nullable=False),
        sa.Column("phar", sa.String(15), server_default=""),
        sa.Column("mobile", sa.String(15), nullable=False),
        sa.Column("pharname", sa.String(100), nullable=False, server_default=""),
        sa.Column("adress", sa.String(200), server_default=""),
        sa.Column("governorate", sa.String(50), server_default=""),
        sa.Column("district", sa.String(50), server_default=""),
        sa.Column("country", sa.String(50), server_default=""),
        sa.Column("currency", sa.String(10), server_default=""),
        sa.Column("vat_default", sa.Numeric(5, 2), nullable=False, server_default=sa.text("14.00")),
        sa.Column("vat_inclusive_prices", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_main_device", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("pharmacyid", name="uq_branches_pharmacyid"),
        sa.UniqueConstraint("mobile", name="uq_branches_mobile"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("namee", sa.String(100), nullable=False, server_default=""),
        sa.Column("mobile", sa.String(15), server_default=""),
        sa.Column("pass_hash", sa.String(255), server_default=""),
        sa.Column("permission_level", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(200), server_default=""),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(100), server_default=""),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", sa.BigInteger(), sa.ForeignKey("permissions.id"), primary_key=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id"), primary_key=True),
    )

    # --- 3. drug master (wzdrugs + tar.phy) ---
    op.create_table(
        "drugs",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("drugname", sa.String(100), nullable=False),
        sa.Column("drugnamear", sa.String(100), nullable=False, server_default=""),
        sa.Column("generic", sa.String(120), server_default=""),
        sa.Column("classy", sa.String(35), server_default=""),
        sa.Column("pharmacology", sa.String(200), server_default=""),
        sa.Column("co", sa.String(100), server_default=""),
        sa.Column("unitsclass", sa.String(50), server_default=""),
        sa.Column("tax_type", tax_class, nullable=False, server_default="exempt"),
        sa.Column("vat", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unitsmall", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(18, 4), server_default="0"),
        sa.Column("price_now", sa.Numeric(18, 4), server_default="0"),
        sa.Column("disco", sa.Numeric(5, 2), server_default="0"),
        sa.Column("pricechanged", sa.Boolean(), server_default="false"),
        sa.Column("localimport", sa.Integer(), server_default="0"),
        sa.Column("titanid", sa.Integer(), server_default="0"),
        sa.Column("history", sa.Text(), server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
        sa.Column("lastedit", tz),
    )
    op.create_table(
        "drug_barcodes",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("barcode", sa.String(16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("drug_id", "barcode", name="uq_drug_barcodes"),
    )
    op.create_table(
        "unit_conversions",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("from_unit", sa.String(20), nullable=False),
        sa.Column("to_unit", sa.String(20), nullable=False),
        sa.Column("factor", sa.Numeric(18, 6), nullable=False),
        sa.CheckConstraint("factor > 0", name="ck_unit_conversions_factor"),
    )

    # --- 4. accounts (wzaccfreetree) ---
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("accounts.id")),
        sa.Column("master", sa.String(100), server_default=""),
        sa.Column("fary", sa.String(100), server_default=""),
        sa.Column("name_ar", sa.String(120), server_default=""),
        sa.Column("name_en", sa.String(120), server_default=""),
        sa.Column("type", account_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("branch_id", "code", name="uq_accounts_branch_code"),
    )

    # --- 5. parties (wzcustomers + companies) ---
    op.create_table(
        "parties",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("kind", party_kind, nullable=False, server_default="customer"),
        sa.Column("typee", sa.String(50), server_default=""),
        sa.Column("namee", sa.String(100), nullable=False, server_default=""),
        sa.Column("name_ar", sa.String(100), server_default=""),
        sa.Column("mobile", sa.String(15), server_default=""),
        sa.Column("adress", sa.String(200), server_default=""),
        sa.Column("governorate", sa.String(50), server_default=""),
        sa.Column("district", sa.String(50), server_default=""),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("receivable_account_id", sa.BigInteger(), sa.ForeignKey("accounts.id")),
        sa.Column("payable_account_id", sa.BigInteger(), sa.ForeignKey("accounts.id")),
        sa.Column("writer", sa.String(50), server_default=""),
        sa.Column("randomid", sa.String(50), server_default=""),
        sa.Column("datee", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("branch_id", "randomid", name="uq_parties_branch_randomid"),
    )

    # --- 6. drug_costs (wzdrugs2) — correction §1.3#2: global, no branch ---
    op.create_table(
        "drug_costs",
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), primary_key=True),
        sa.Column("unitcost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("costvalue", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("expire", sa.Date()),
    )

    # --- 7. stock_batches (wzgard) ---
    op.create_table(
        "stock_batches",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("randomid", sa.String(50), nullable=False),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("expire", sa.Date()),
        sa.Column("cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("vat", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("oldstock", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("typee", batch_type, nullable=False, server_default="purchase"),
        sa.Column("vatvalue", sa.Numeric(18, 2), server_default="0"),
        sa.Column("totalwithvat", sa.Numeric(18, 2), server_default="0"),
        sa.Column("writer", sa.String(50), server_default=""),
        sa.Column("classy", sa.String(35), server_default=""),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("branch_id", "drug_id", "randomid", name="uq_stock_batches"),
    )

    # --- 8. work periods & shifts (workperiod.phy) ---
    op.create_table(
        "work_periods",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("name", sa.String(50), server_default=""),
        sa.Column("opened_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("opened_at", tz, nullable=False, server_default=now),
        sa.Column("closed_at", tz),
    )
    op.create_table(
        "shifts",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("work_period_id", sa.BigInteger(), sa.ForeignKey("work_periods.id")),
        sa.Column("opened_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("opened_at", tz, nullable=False, server_default=now),
        sa.Column("closed_at", tz),
        sa.Column("cash_start", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= opened_at", name="ck_shifts_times"
        ),
    )

    # --- 9. invoices + lines + versions + payment_splits ---
    op.create_table(
        "invoices",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("kind", invoice_kind, nullable=False, server_default="sale"),
        sa.Column("invoice_no", sa.String(30), nullable=False),
        sa.Column("datee", sa.Date(), nullable=False),
        sa.Column("datetimee", tz),
        sa.Column("silsilaid", sa.String(15), server_default=""),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id")),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("totalvalue", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("payed", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("agel", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", invoice_status, nullable=False, server_default="saved"),
        sa.Column("writer", sa.String(50), server_default=""),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
        sa.Column("last_edited_at", tz),
        sa.CheckConstraint("payed + agel = totalvalue", name="ck_invoice_payment"),
        sa.UniqueConstraint("branch_id", "invoice_no", name="uq_invoices_branch_no"),
    )
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("stock_batches.id")),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(20), server_default="pack"),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("disc", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("tax_type", tax_class, nullable=False, server_default="exempt"),
        sa.Column("vat", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("expire", sa.Date()),
        sa.Column("minimum", sa.Numeric(18, 4), server_default="0"),
        sa.Column("tips", sa.String(50), server_default=""),
        sa.Column("iddatetime", tz),
        sa.CheckConstraint("unit_price >= 0", name="ck_invoice_line_unit_price"),
    )
    op.create_table(
        "invoice_versions",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(30), server_default=""),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("changed_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("changed_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("invoice_id", "version_no", name="uq_invoice_versions"),
    )
    op.create_table(
        "payment_splits",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("method", payment_method, nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("received_at", tz, nullable=False, server_default=now),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.CheckConstraint("amount > 0", name="ck_payment_split_amount"),
    )

    # --- 10. journals + journal_lines (farysales) ---
    op.create_table(
        "journals",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("datee", sa.Date(), nullable=False),
        sa.Column("entry_no", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("source", journal_source, nullable=False, server_default="sale"),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("ref_invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("branch_id", "datee", "entry_no", name="uq_journals_entry"),
    )
    op.create_table(
        "journal_lines",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("journal_id", sa.BigInteger(), sa.ForeignKey("journals.id"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("contra_party_id", sa.BigInteger(), sa.ForeignKey("parties.id")),
        sa.Column("datee", sa.Date(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("creditdebit", sa.String(20), server_default=""),
        sa.Column("randomid", sa.String(50), server_default=""),
        sa.Column("writer", sa.String(50), server_default=""),
        sa.Column("tips", sa.String(50), server_default=""),
        sa.Column("classy", sa.String(35), server_default=""),
        sa.CheckConstraint(
            "debit >= 0 AND credit >= 0 AND (debit = 0 OR credit = 0)",
            name="ck_journal_line_single_side",
        ),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_journal_line_month"),
    )

    # --- 11. balances (farysales monthe/yearo) ---
    op.create_table(
        "balances",
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("month", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_balances_month"),
        sa.CheckConstraint("balance = debit - credit", name="ck_balances_identity"),
    )

    # --- 12. drawer & day close ---
    op.create_table(
        "drawer_movements",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("datee", sa.Date(), nullable=False),
        sa.Column("direction", drawer_direction, nullable=False, server_default="in"),
        sa.Column("reason", drawer_reason, nullable=False, server_default="cash_sale"),
        sa.Column("method", drawer_method, nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("shift_id", sa.BigInteger(), sa.ForeignKey("shifts.id")),
        sa.Column("ref_invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.CheckConstraint("amount >= 0", name="ck_drawer_amount"),
    )
    op.create_table(
        "daily_close",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("datee", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.BigInteger(), sa.ForeignKey("shifts.id")),
        sa.Column("work_period_id", sa.BigInteger(), sa.ForeignKey("work_periods.id")),
        sa.Column("drawer_start", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("expected_cash", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("difference", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("manual_cash", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("manual_card", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_cash", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_network", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("purchases", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("expenses", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cost_of_sales", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_profit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discounts", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_sales", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_purchases", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_expenses", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", close_status, nullable=False, server_default="open"),
        sa.Column("closed_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("closed_at", tz),
        sa.UniqueConstraint("branch_id", "datee", name="uq_daily_close"),
        sa.CheckConstraint(
            "difference = counted_cash - expected_cash", name="ck_daily_close_diff"
        ),
    )

    # --- 13. branch_stock (titanstock) ---
    op.create_table(
        "branch_stock",
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), primary_key=True),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("minimum", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("silsilaid", sa.String(15), server_default=""),
        sa.Column("classy", sa.String(35), server_default=""),
        sa.Column("price", sa.Numeric(18, 4), server_default="0"),
        sa.Column("barcode", sa.String(16), server_default=""),
        sa.Column("lastedit", tz),
    )

    # --- 15. shortages + corrections (intra-branch, core) ---
    op.create_table(
        "shortage_flags",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("current_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("minimum", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("method", shortage_method, nullable=False, server_default="manual"),
        sa.Column("flagged_at", tz, nullable=False, server_default=now),
        sa.Column("resolved_at", tz),
        sa.Column("resolved_by", sa.BigInteger(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "stock_correction_requests",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), sa.ForeignKey("stock_batches.id")),
        sa.Column("delta", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason", sa.String(200), server_default=""),
        sa.Column("requested_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", correction_status, nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("decided_at", tz),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.CheckConstraint(
            "(status = 'pending') = (decided_at IS NULL)", name="ck_correction_decision"
        ),
    )

    # --- 18. audit + sync (core outbox seam) ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("entity", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.BigInteger()),
        sa.Column("field", sa.String(50), server_default=""),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id")),
        sa.Column("barcode", sa.String(16), server_default=""),
        sa.Column("action", sa.String(30), nullable=False, server_default="update"),
        sa.Column("namee", sa.String(100), server_default=""),
        sa.Column("typevalue", sa.String(100), server_default=""),
        sa.Column("created_at", tz, nullable=False, server_default=now),
    )
    op.create_table(
        "sync_log",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("entity", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.BigInteger()),
        sa.Column("action", sa.String(30), nullable=False, server_default="update"),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("synced_at", tz),
        sa.Column("status", sync_status, nullable=False, server_default="pending"),
        sa.Column("source_device_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
    )
    op.create_table(
        "branch_identities",
        sa.Column("legacy_table", sa.String(50), primary_key=True),
        sa.Column("legacy_column", sa.String(50), primary_key=True),
        sa.Column("legacy_value", sa.String(100), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
    )

    # --- 19. ops/config ---
    op.create_table(
        "integration_config",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("value", sa.Text(), server_default=""),
        sa.Column("config", postgresql.JSONB()),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
        sa.UniqueConstraint("branch_id", "key", name="uq_integration_config"),
    )
    op.create_table(
        "price_change_log",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id")),
        sa.Column("barcode", sa.String(16), server_default=""),
        sa.Column("price", sa.Numeric(18, 4), server_default="0"),
        sa.Column("disco", sa.Numeric(5, 2), server_default="0"),
        sa.Column("units", sa.Integer(), server_default="0"),
        sa.Column("quant", sa.Numeric(18, 4), server_default="0"),
        sa.Column("datee", sa.Date()),
        sa.Column("tips", sa.String(50), server_default=""),
        sa.Column("country", sa.String(50), server_default=""),
        sa.Column("storename", sa.String(100), server_default=""),
        sa.Column("pharmacyname", sa.String(100), server_default=""),
        sa.Column("pharmacyname2", sa.String(100), server_default=""),
        sa.Column("titanver", sa.String(50), server_default=""),
        sa.Column("pricechanged", sa.Boolean(), server_default="false"),
        sa.Column("localimport", sa.Integer(), server_default="0"),
        sa.Column("changed_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
    )
    op.create_table(
        "manual_journal_entries",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("record_no", sa.Integer()),
        sa.Column("datee", sa.Date()),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("source_file", sa.String(50), server_default="daily-manual.phy"),
        sa.Column("journal_id", sa.BigInteger(), sa.ForeignKey("journals.id")),
        sa.Column("created_at", tz, nullable=False, server_default=now),
    )
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.Text(), server_default=""),
        sa.Column("value_numeric", sa.Numeric(18, 4)),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
    )

    # --- plugin host (plan/08 §2.2.1) ---
    op.create_table(
        "app_plugins",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("core_requires", sa.String(60), nullable=False),
        sa.Column("sdk_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="installed"),
        sa.Column("license_status", sa.String(20), nullable=False, server_default="unlicensed"),
        sa.Column("license_expires_at", tz),
        sa.Column("installed_at", tz, nullable=False, server_default=now),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
        sa.CheckConstraint(
            "status IN ('installed','enabled','disabled','error')",
            name="ck_app_plugins_status",
        ),
        sa.CheckConstraint(
            "license_status IN ('unlicensed','trial','licensed','expired')",
            name="ck_app_plugins_license",
        ),
    )
    op.create_table(
        "plugin_dependencies",
        sa.Column("plugin_id", sa.BigInteger(), sa.ForeignKey("app_plugins.id"), primary_key=True),
        sa.Column("depends_on", sa.String(60), primary_key=True),
        sa.Column("min_version", sa.String(20), nullable=False),
        sa.Column("max_version", sa.String(20)),
    )
    op.create_table(
        "plugin_branch_grants",
        sa.Column("plugin_id", sa.BigInteger(), sa.ForeignKey("app_plugins.id"), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_table(
        "plugin_settings",
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("plugin_id", sa.BigInteger(), sa.ForeignKey("app_plugins.id"), primary_key=True),
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", postgresql.JSONB()),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", tz, nullable=False, server_default=now),
    )

    # --- indexes (plan/01 §5.3, corrected §1.3#4) ---
    op.create_index("ix_stock_batches_expiry", "stock_batches", ["branch_id", "drug_id", "expire"])
    op.create_index("ix_invoices_branch_date", "invoices", ["branch_id", "datee"])
    op.create_index("ix_invoices_branch_party", "invoices", ["branch_id", "party_id"])
    op.create_index("ix_invoices_last_edited", "invoices", ["last_edited_at"])
    op.create_index("ix_invoice_lines_invoice", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_drug", "invoice_lines", ["branch_id", "drug_id"])
    op.create_index("ix_journal_lines_account", "journal_lines", ["branch_id", "account_id", "month", "year"])
    op.create_index("ix_journal_lines_journal", "journal_lines", ["journal_id"])
    op.create_index("ix_drawer_movements_branch_date", "drawer_movements", ["branch_id", "datee"])
    op.create_index("ix_audit_entity", "audit_log", ["entity", "entity_id"])
    op.create_index("ix_audit_drug", "audit_log", ["drug_id"])
    op.create_index("ix_audit_created", "audit_log", ["created_at"])
    op.create_index("ix_sync_log_status", "sync_log", ["branch_id", "status"])
    op.create_index("ix_price_change_log_drug", "price_change_log", ["branch_id", "drug_id"])
    # partial unique indexes — correction §1.3#4 (empty-string collision safe)
    op.create_index(
        "uq_drug_barcodes_barcode", "drug_barcodes", ["barcode"],
        unique=True, postgresql_where=sa.text("barcode <> ''"),
    )
    op.create_index(
        "uq_drugs_drugname", "drugs", ["drugname"],
        unique=True, postgresql_where=sa.text("drugname <> ''"),
    )


def downgrade() -> None:
    # drop indexes
    for name, table in [
        ("uq_drugs_drugname", "drugs"),
        ("uq_drug_barcodes_barcode", "drug_barcodes"),
        ("ix_price_change_log_drug", "price_change_log"),
        ("ix_sync_log_status", "sync_log"),
        ("ix_audit_created", "audit_log"),
        ("ix_audit_drug", "audit_log"),
        ("ix_audit_entity", "audit_log"),
        ("ix_drawer_movements_branch_date", "drawer_movements"),
        ("ix_journal_lines_journal", "journal_lines"),
        ("ix_journal_lines_account", "journal_lines"),
        ("ix_invoice_lines_drug", "invoice_lines"),
        ("ix_invoice_lines_invoice", "invoice_lines"),
        ("ix_invoices_last_edited", "invoices"),
        ("ix_invoices_branch_party", "invoices"),
        ("ix_invoices_branch_date", "invoices"),
        ("ix_stock_batches_expiry", "stock_batches"),
    ]:
        op.drop_index(name, table_name=table)

    for table in [
        "plugin_settings", "plugin_branch_grants", "plugin_dependencies", "app_plugins",
        "app_config", "manual_journal_entries", "price_change_log", "integration_config",
        "branch_identities", "sync_log", "audit_log", "stock_correction_requests",
        "shortage_flags", "branch_stock", "daily_close", "drawer_movements", "balances",
        "journal_lines", "journals", "payment_splits", "invoice_versions", "invoice_lines",
        "invoices", "shifts", "work_periods", "stock_batches", "drug_costs", "parties",
        "accounts", "unit_conversions", "drug_barcodes", "drugs", "user_roles",
        "role_permissions", "permissions", "roles", "users", "branches",
    ]:
        op.drop_table(table)

    for enum in [
        "tax_type", "sync_status", "correction_status", "shortage_method", "close_status",
        "drawer_reason", "drawer_method", "drawer_direction", "batch_type", "payment_method",
        "invoice_status", "invoice_kind", "journal_source", "account_type", "party_kind",
    ]:
        op.execute(f'DROP TYPE IF EXISTS "{enum}"')