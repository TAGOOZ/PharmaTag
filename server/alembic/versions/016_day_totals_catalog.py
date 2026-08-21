"""core rev 016 — day totals money report + day_profit window (ticket #24, S3.2)

S3.2 completes the money-critical reports: `day_totals` (الإجماليات
اليومية) joins the catalog — one row per day over a range with the payment
splits (cash/network sales and returns, manual cash/card, expenses,
supplier payments, expected cash) plus the day's P&L columns — and
`day_profit` gains its across-periods window (datee OR date_from/date_to).
Catalog rows are data, not code: this slice adds a row and widens one,
not an endpoint.
"""
from alembic import op
import sqlalchemy as sa

revision = "016_day_totals_catalog"
down_revision = "015_report_catalog"
branch_labels = None
depends_on = None

ROW = (
    "day_totals",
    "money",
    "الإجماليات اليومية",
    "Day Totals",
    '["date_from", "date_to"]',
    25,
)

DAY_PROFIT_PARAMS = '["datee", "date_from", "date_to"]'


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO report_catalog "
            "(code, category, title_ar, title_en, params, paper, sort) "
            "VALUES (:code, :category, :title_ar, :title_en, "
            "CAST(:params AS jsonb), 'A4', :sort)"
        ).bindparams(
            code=ROW[0],
            category=ROW[1],
            title_ar=ROW[2],
            title_en=ROW[3],
            params=ROW[4],
            sort=ROW[5],
        )
    )
    op.execute(
        sa.text(
            "UPDATE report_catalog SET params = CAST(:params AS jsonb) "
            "WHERE code = 'day_profit'"
        ).bindparams(params=DAY_PROFIT_PARAMS)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE report_catalog SET params = CAST(:params AS jsonb) "
            "WHERE code = 'day_profit'"
        ).bindparams(params='["datee"]')
    )
    op.execute(sa.text("DELETE FROM report_catalog WHERE code = 'day_totals'"))
