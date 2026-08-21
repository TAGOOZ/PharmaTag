"""core rev 014 — opening balances (ticket #22, S2.7)

S2.7 seeds opening cash, stock at cost, receivables and payables at cutover.
Opening balances are a balanced journal (source=opening) dated the day before
the opening month so the trial balance (which sums journal_lines before start as
opening) shows them as افتتاحي, plus a `month_open_balances` snapshot for the
opening month itself (monthy\\start-data) so GET /months/{y}/{m}/open-balances
and the new opening-balances API reflect the same totals.

This revision only seeds the granular permission that gates the opening API.
The journals / month_open_balances tables already exist (001/013); the opening
journal_source enum value `opening` already exists (001). No schema change,
only the permission row + role grants (admin/accountant/manager — ledger area,
floor 7 per plan/02 §3).
"""
from alembic import op
import sqlalchemy as sa

revision = "014_opening_balances"
down_revision = "013_month_close"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('opening_balances.manage', 'الأرصدة الافتتاحية')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'opening_balances.manage' AND r.id IN (1, 4, 5)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'opening_balances.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'opening_balances.manage'"))
