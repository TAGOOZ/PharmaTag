"""core rev 012 — settlement vouchers + receivables.manage (ticket #19, S2.4)

S2.4 (plan/05 §S2.4) manages the credit-sale (أجل) receivable: a collection
سند قبض (receipt) and a payment سند صرف (payment voucher) post to the shared
journal engine (source `settlement`), update balances, and record the drawer
movement — the two document shapes the legacy money screens produce
(feature_receivables_mrd, feature_purchases.md §2.5).

This revision:

* creates `settlement_vouchers` — the ledger reference row for every posted
  settlement. One row per voucher: branch-scoped, per-branch monotonic
  `voucher_no`, the party it moves, the drawer method, the exact amount, and
  the `journals` entry it produced. `reverses_voucher_id` links an A07-style
  reversal back to the voucher it offsets (never an edit/delete of the
  original). `voucher_type` is receipt (قبض) or payment (صرف).
* seeds `receivables.manage` (تحصيل وسداد الآجل) — settlement posting is a
  ledger-area balance write, so the coarse floor is 7 (plan/02 §3). The
  granular code is granted to the admin role (1), the accountant role (4),
  and the manager role (5), matching the journals.manage seeding (rev 011).

No column change touches the money-truth tables; the enum `journal_source`
already carries `settlement` (rev 001).
"""
from alembic import op
import sqlalchemy as sa

revision = "012_settlement_vouchers"
down_revision = "011_manual_journal_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settlement_vouchers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False
        ),
        sa.Column("voucher_no", sa.Integer(), nullable=False),
        sa.Column("voucher_type", sa.Text(), nullable=False),
        sa.Column(
            "party_id", sa.BigInteger(), sa.ForeignKey("parties.id"), nullable=False
        ),
        sa.Column("datee", sa.Date(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column(
            "journal_id", sa.BigInteger(), sa.ForeignKey("journals.id"), nullable=False
        ),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column(
            "reverses_voucher_id",
            sa.BigInteger(),
            sa.ForeignKey("settlement_vouchers.id"),
            nullable=True,
        ),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "voucher_type IN ('receipt', 'payment')", name="ck_settlement_voucher_type"
        ),
        sa.CheckConstraint(
            "method IN ('cash', 'network')", name="ck_settlement_voucher_method"
        ),
        sa.CheckConstraint("amount > 0", name="ck_settlement_voucher_amount"),
        sa.UniqueConstraint(
            "branch_id", "voucher_no", name="uq_settlement_vouchers_branch_no"
        ),
    )
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('receivables.manage', 'تحصيل وسداد الآجل')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'receivables.manage' AND r.id IN (1, 4, 5)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'receivables.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'receivables.manage'"))
    op.drop_table("settlement_vouchers")