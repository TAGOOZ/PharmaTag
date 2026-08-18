"""core rev 007 — corrections chart account (S1.7, ticket #13)

S1.7 stock count + correction re-books inventory value when an approved
correction is applied (plan/02 §4.4 "journal correction source"). The default
chart (rev 002) has no dedicated contra for a count adjustment: an overage
(Debit inventory) or deficit (Credit inventory) needs a single account that
nets the two sides. This adds `5900 مصروفات.جرد وتعديل الارصدة` (expense) to
the seeded MAIN branch; new branches inherit it once branch-create tooling
lands (S5.1). No table/column change — a pure seed row, so the SQLite twin's
007 mirrors the INSERT and the desktop bundle seed gains the same row.

Revision ID: 007_stock_corrections
Revises: 006_sale_returns
"""
from alembic import op
import sqlalchemy as sa

revision = "007_stock_corrections"
down_revision = "006_sale_returns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO accounts (branch_id, code, name_ar, type, is_active)
        VALUES (1, '5900', 'مصروفات.جرد وتعديل الارصدة', 'expense', true)
    """))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM accounts WHERE branch_id = 1 AND code = '5900'"))