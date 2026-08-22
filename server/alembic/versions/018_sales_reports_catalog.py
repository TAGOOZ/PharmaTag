"""core rev 018 — sales/purchase report catalog rows (ticket #26, S3.4)

S3.4 adds the sales-invoice register to the `report_catalog` table seeded
by revs 015–017. Engines register in app/reports/views.py; this row is
inert data until then (the dispatcher 404s unknown codes).
"""
from alembic import op
import sqlalchemy as sa

revision = "018_sales_reports_catalog"
down_revision = "017_stock_reports_catalog"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    ("sales_invoices", "sales", "فواتير المبيعات", "Sales Invoices",
     '["date_from", "date_to"]', 90),
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
