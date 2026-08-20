"""core rev 013 — month close + month_open_balances (ticket #21, S2.6)

S2.6 (plan/05) closes a branch month: a `monthly_close` row archives the
period (status closed/open/reopened, mirrors `monthy\\moves`) and
`month_open_balances` seeds the next month's opening balances (mirrors
`monthy\\start-data`) from the branch's closing ledger state (cumulative
debit/credit per account). A closed month rejects further journal posts
(plan/02 4.5); reopen (manager >= 7, A07) flips status to reopened + audit.
"""
from alembic import op
import sqlalchemy as sa

revision = "013_month_close"
down_revision = "012_settlement_vouchers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monthly_close",
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="closed"),
        sa.Column("closed_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("branch_id", "year", "month"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_monthly_close_month"),
    )
    op.create_table(
        "month_open_balances",
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("branch_id", "account_id", "year", "month"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_month_open_month"),
    )
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('months.close', 'تقفيل الشهر')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'months.close' AND r.id IN (1, 4, 5)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'months.close')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'months.close'"))
    op.drop_table("month_open_balances")
    op.drop_table("monthly_close")
