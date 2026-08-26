"""core rev 033 — chain_sales catalog row (ticket #34, S5.4)

The titanksasales projection (A06) lands as a report: per-day × per-branch
sale totals across all active branches, regenerated from canonical invoices.
Engine registers in app/reports/views.py; this row is inert data until then.
"""
from alembic import op
import sqlalchemy as sa

revision = "033_chain_sales_catalog"
down_revision = "032_branch_identity_by_default"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    ("chain_sales", "chain", "مبيعات السلسلة",
     "Chain Sales Summary", '["date_from", "date_to"]', 200),
]


def upgrade() -> None:
    for code, category, title_ar, title_en, params, sort in SEED_ROWS:
        op.execute(
            sa.text(
                "INSERT INTO report_catalog "
                "(code, category, title_ar, title_en, params, paper, sort) "
                "VALUES (:code, :category, :title_ar, :title_en, "
                "CAST(:params AS jsonb), 'A4', :sort)"
            ).bindparams(
                code=code,
                category=category,
                title_ar=title_ar,
                title_en=title_en,
                params=params,
                sort=sort,
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM report_catalog WHERE code = ANY(:codes)").bindparams(
            codes=[row[0] for row in SEED_ROWS]
        )
    )
