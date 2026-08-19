"""core rev 010 — backfill seeded accounts' master/fary (ticket #16 edge pass)

Rev 002/007/009 seeded the chart WITHOUT the legacy linkage columns that
`create_account`/`update_account` populate (master = parent code, fary = own
code), so every seeded account exposed `master:""`/`fary:""` through the API
while API-created ones carried real values. Pure data backfill — no
table/column change:

* `fary` = the account's own code (rev 002's flat rows and the rev-009 tree
  nodes alike);
* `master` = the parent account's code where the row has a parent, else left
  empty (roots have no master).

Runs after rev 009 wired the tree, so parent_id is already set when this
migration backfills. Idempotent: `WHERE` only touches empty/blank values.

Revision ID: 010_accounts_master_fary
Revises: 009_accounts_tree
"""
from alembic import op
import sqlalchemy as sa

revision = "010_accounts_master_fary"
down_revision = "009_accounts_tree"
branch_labels = None
depends_on = None

# the 23 accounts seeded by rev 002/007/009 (downgrade target)
_SEEDED_CODES = (
    "'1000','1100','1200','1300','2000','2100','2110',"
    "'3000','4000','5000','6000','5900',"
    "'100','110','200','210','220','300','400','500',"
    "'1001','1010','1110'"
)


def upgrade() -> None:
    # fary = the account's own code
    op.execute(sa.text("""
        UPDATE accounts
        SET fary = code
        WHERE fary IS NULL OR fary = ''
    """))
    # master = the parent's code (children only; roots keep '').
    op.execute(sa.text("""
        UPDATE accounts
        SET master = (
            SELECT p.code FROM accounts p WHERE p.id = accounts.parent_id
        )
        WHERE parent_id IS NOT NULL AND (master IS NULL OR master = '')
    """))


def downgrade() -> None:
    # best-effort revert of exactly the seeded rows 010 backfilled
    op.execute(sa.text(f"""
        UPDATE accounts
        SET master = '', fary = ''
        WHERE fary = code AND code IN ({_SEEDED_CODES})
    """))