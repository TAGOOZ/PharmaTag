"""core rev 011 — journals.manage + manual-journal reversal link (ticket #17)

S2.2 (plan/05 §S2.2, FormAccAddQueed) lets a manager post a balanced manual
journal through `/api/v1/journals/manual`. The journals/journal_lines/balances
tables and the `manual` journal_source enum already exist (rev 001); this
revision:

* seeds `journals.manage` (ترحيل قيود يدوية) — manual-journal posting is a
  ledger-area write, so the coarse floor is 7 (plan/02 §3 "balance edits"
  >= 7). The granular code is granted to the admin role (1), the accountant
  role (4), and the manager role (5) — posting a قيد is an accounting duty,
  and a pharmacy manager routinely records manual money.
* adds `manual_journal_entries.reverses_entry_id` — a posted manual journal
  can be reversed (A07-style: manager-only, offsetting entry + audit). The
  nullable self-FK keeps the reversal chain queryable instead of burying the
  link in a free-text description.

No column change touches the money-truth tables; parity stays intact.
"""
from alembic import op
import sqlalchemy as sa

revision = "011_manual_journal_entries"
down_revision = "010_accounts_master_fary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_journal_entries",
        sa.Column(
            "reverses_entry_id",
            sa.BigInteger(),
            sa.ForeignKey("manual_journal_entries.id"),
            nullable=True,
        ),
    )
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('journals.manage', 'ترحيل قيود يومية')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'journals.manage' AND r.id IN (1, 4, 5)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'journals.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'journals.manage'"))
    op.drop_constraint(
        "manual_journal_entries_reverses_entry_id_fkey", "manual_journal_entries"
    )
    op.drop_column("manual_journal_entries", "reverses_entry_id")