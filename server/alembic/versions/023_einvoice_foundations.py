"""core rev 023 — e-invoice foundations (ticket #28, S4.1; ADR-0002)

Every sales invoice gains a tax-document record with an atomic per-device
UUID/counter chain and a consumer QR (ETA eReceipt v1.2 / B2B v1.0 routing is
per document):

* `einvoice_log` — one row per invoice: regime `kind`, submission `status`
  (pending → submitted → accepted|rejected|failed), gapless per-(branch, kind)
  counter, uuid + previous_uuid + reference_uuid chain, device_serial,
  qr_data, payload_json. `payload_json` is PG `json` (NOT jsonb) on purpose:
  the UUID recomputes from a serialization that depends on document key
  order, and jsonb would silently reorder keys.
* `einvoice_counters` — DB-resident chain state keyed (branch_id, kind):
  last_counter (monotonic, gapless, never reset in fiscal year — A15) and
  last_uuid (the previousUUID for the next document). Nullable
  device_serial now so S5.1 multi-device needs no migration.
* `parties.tax_registration_no` — presence routes a credit sale to the B2B
  eInvoice regime instead of an eReceipt.

A08 reconciliation: einvoice_log/einvoice_counters were originally marked
plugin-owned [S], but ADR-0002 locks them into the core sale transaction
(G12 outbox atomicity, STRICT counters per A09) with SQLite-twin parity —
core tables, core migration; scripts/parity_check.py drops both from its
plugin-leak guard in this slice.

Revision ID: 023_einvoice_foundations
Revises: 022_accounting_reports_catalog
"""
from alembic import op
import sqlalchemy as sa

revision = "023_einvoice_foundations"
down_revision = "022_accounting_reports_catalog"
branch_labels = None
depends_on = None


def _identity() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    op.create_table(
        "einvoice_counters",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(),
                  sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("last_counter", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_uuid", sa.String(64), nullable=False, server_default=""),
        sa.Column("device_serial", sa.String(100)),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("branch_id", "kind", name="uq_einvoice_counters_branch_kind"),
        sa.CheckConstraint(
            "kind IN ('receipt', 'return_receipt', 'invoice', 'credit_note')",
            name="ck_einvoice_counters_kind",
        ),
    )
    op.create_table(
        "einvoice_log",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        # the tax document is a strict 1:1 child of its invoice — it dies with
        # it (ON DELETE CASCADE), so every invoice cleanup path stays safe
        sa.Column("invoice_id", sa.BigInteger(),
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("counter", sa.BigInteger(), nullable=False),
        sa.Column("uuid", sa.String(64), nullable=False, server_default=""),
        sa.Column("previous_uuid", sa.String(64), nullable=False, server_default=""),
        sa.Column("reference_uuid", sa.String(64), nullable=False, server_default=""),
        sa.Column("device_serial", sa.String(100)),
        sa.Column("qr_data", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("response", sa.Text(), nullable=False, server_default=""),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("branch_id", "kind", "counter", name="uq_einvoice_log_chain"),
        sa.UniqueConstraint("invoice_id", name="uq_einvoice_log_invoice"),
        sa.CheckConstraint(
            "kind IN ('receipt', 'return_receipt', 'invoice', 'credit_note')",
            name="ck_einvoice_log_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'accepted', 'rejected', 'failed')",
            name="ck_einvoice_log_status",
        ),
    )
    op.create_index(
        "ix_einvoice_log_status", "einvoice_log", ["status"]
    )
    op.add_column(
        "parties",
        sa.Column("tax_registration_no", sa.String(30), server_default=""),
    )


def downgrade() -> None:
    # WARNING: drops issued tax-document records (uuids, chain positions,
    # submission state). Irreversible by nature — fiscal documents cannot be
    # regenerated once counters advance. Only for dev/test environments.
    op.drop_column("parties", "tax_registration_no")
    op.drop_index("ix_einvoice_log_status", table_name="einvoice_log")
    op.drop_table("einvoice_log")
    op.drop_table("einvoice_counters")
