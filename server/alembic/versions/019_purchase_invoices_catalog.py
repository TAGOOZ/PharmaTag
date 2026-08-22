"""core rev 019 — purchase invoice register catalog row (ticket #26, S3.4)

S3.4 adds the purchase-invoice register to the `report_catalog` table.
Engine registers in app/reports/views.py; this row is inert data until then.
"""
from alembic import op
import sqlalchemy as sa

revision = "019_purchase_invoices_catalog"
down_revision = "018_sales_reports_catalog"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    ("purchase_invoices", "sales", "فواتير المشتريات", "Purchase Invoices",
     '["date_from", "date_to"]', 100),
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
