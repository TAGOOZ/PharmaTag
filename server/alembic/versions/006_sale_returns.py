"""core rev 006 — sales-return links (ticket #11, S1.5)

S1.5 (plan/05 §S1.5) reverses a saved sale into a NEW return invoice with its
own number. The return needs two links back to the original so partial returns
are tracked per line and the money/stock/journal reversal is auditable:

* `invoices.ref_invoice_id` — the return invoice references the original sale
  it reverses (NULL for ordinary sale/purchase invoices).
* `invoice_lines.ref_invoice_line_id` — each return line references the exact
  original line it returns (return qty <= original qty - already returned).

Both are nullable self-FKs; no data backfill is needed — new invoices leave
them NULL until a return is created.

Revision ID: 006_sale_returns
Revises: 005_drug_price_levels
"""
from alembic import op
import sqlalchemy as sa

revision = "006_sale_returns"
down_revision = "005_drug_price_levels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("ref_invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id")),
    )
    op.add_column(
        "invoice_lines",
        sa.Column(
            "ref_invoice_line_id",
            sa.BigInteger(),
            sa.ForeignKey("invoice_lines.id"),
        ),
    )
    op.create_index(
        "ix_invoices_ref_invoice", "invoices", ["ref_invoice_id"]
    )
    op.create_index(
        "ix_invoice_lines_ref_line", "invoice_lines", ["ref_invoice_line_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_ref_invoice", table_name="invoices")
    op.drop_index("ix_invoice_lines_ref_line", table_name="invoice_lines")
    op.drop_column("invoice_lines", "ref_invoice_line_id")
    op.drop_column("invoices", "ref_invoice_id")