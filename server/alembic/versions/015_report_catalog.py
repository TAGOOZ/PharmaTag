"""core rev 015 — report catalog + print queue (ticket #23, S3.1)

S3.1 (plan/05) turns the hardcoded #15 catalog into the `report_catalog`
table — every later report slice (S3.2–S3.5) adds rows, not code: code,
category, bilingual titles, params, paper (A4/A5), sort, active. The four
v1 reports seed it. `print_jobs` is the durable print queue (ModPrint's
job side): a branch-scoped row per queued print/export with its params and
paper, flipped to done when the client confirms it printed.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015_report_catalog"
down_revision = "014_opening_balances"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    ("drawer_handover", "money", "تسليم الدرج", "Drawer Handover",
     '["date_from", "date_to"]', 10),
    ("day_profit", "money", "ربح اليوم", "Day Profit", '["datee"]', 20),
    ("period_totals", "money", "ملخص المبيعات والمشتريات", "Sales & Purchases Summary",
     '["date_from", "date_to"]', 30),
    ("stock_minimum", "stock", "النواقص (أقل من الحد الأدنى)", "Stock Below Minimum",
     "[]", 40),
]


def upgrade() -> None:
    op.create_table(
        "report_catalog",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title_ar", sa.String(200), nullable=False),
        sa.Column("title_en", sa.String(200), nullable=False),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "paper", sa.String(2), nullable=False, server_default="A4"
        ),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("paper IN ('A4', 'A5')", name="ck_report_catalog_paper"),
    )
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
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("report_code", sa.String(64), sa.ForeignKey("report_catalog.code"), nullable=False),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("paper", sa.String(2), nullable=False, server_default="A4"),
        sa.Column("status", sa.String(10), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("done_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("paper IN ('A4', 'A5')", name="ck_print_jobs_paper"),
        sa.CheckConstraint("status IN ('queued', 'done', 'failed')", name="ck_print_jobs_status"),
    )


def downgrade() -> None:
    op.drop_table("print_jobs")
    op.drop_table("report_catalog")
