"""core rev 022 — accounting reports catalog rows (ticket #27, S3.5)

S3.5 adds the ledger-by-account and VAT-summary reports to `report_catalog`.
Engines register in app/reports/views.py; these rows are inert data until then.
"""
from alembic import op
import sqlalchemy as sa

revision = "022_accounting_reports_catalog"
down_revision = "021_party_totals_catalog"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    (
        "ledger_account",
        "accounting",
        "دفتر الأستاذ لحساب",
        "Ledger by Account",
        '["account_code", "month", "year", "date_from", "date_to"]',
        130,
    ),
    (
        "vat_summary",
        "accounting",
        "ملخص ضريبة القيمة المضافة",
        "VAT Summary (Form 10)",
        '["month", "year", "date_from", "date_to"]',
        140,
    ),
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
