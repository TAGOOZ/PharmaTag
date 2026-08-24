"""core rev 026 — branches.manage permission (ticket #31, S5.1)

Branch registry writes are gated by a new granular `branches.manage` code,
seeded to admin + manager and covered by the legacy floor (permission_level
>= 7 — the same tier as day-close reopen / ledger edits). Reads stay open to
any authenticated user. No table changes: `branches` + `branch_identities`
have existed since rev 001.
"""
from alembic import op
import sqlalchemy as sa

revision = "026_branch_permissions"
down_revision = "025_drug_egs_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('branches.manage', 'إدارة الفروع والأجهزة')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'branches.manage' AND r.id IN (1, 5)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'branches.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'branches.manage'"))
