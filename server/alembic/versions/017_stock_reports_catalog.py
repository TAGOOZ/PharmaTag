"""core rev 017 — stock report catalog rows (ticket #25, S3.3)

S3.3 adds the four stock reports to the `report_catalog` table seeded by
revs 015+016: current stock, drug movement track, expired/expiring stock,
and minimum-based needs. Engines register in app/reports/views.py; these
rows are inert data until then (the dispatcher 404s unknown codes).
"""
from alembic import op
import sqlalchemy as sa

revision = "017_stock_reports_catalog"
down_revision = "016_day_totals_catalog"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    ("stock_current", "stock", "رصيد الأصناف", "Current Stock", "[]", 50),
    ("stock_movements", "stock", "تتبع تغيير الرصيد", "Drug Movement Track",
     '["drug_id", "date_from", "date_to"]', 60),
    ("stock_expired", "stock", "الادوية منتهية الصلاحية", "Expired / Expiring Stock",
     '["datee", "horizon_days"]', 70),
    ("stock_needs", "stock", "احتياجات الطلب (الحد الأدنى)", "Order Needs (Minimum-Based)",
     "[]", 80),
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
