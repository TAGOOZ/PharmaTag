"""core rev 004 — realign identity sequences after OVERRIDING SYSTEM VALUE seeds

rev 002/003 seeded rows with explicit IDs via `OVERRIDING SYSTEM VALUE`, which
does NOT advance the column's identity sequence. On a fresh database the next
ordinary insert would collide with a seed row (e.g. a new branch → id 1 →
conflict with MAIN). `setval(seq, max(id), true)` makes the next generated id
`max(id) + 1` for every table the seeds wrote explicitly.

Discovered by the #6 edge-case pass (AGENTS.md — edge-case pass before close).
SQLite is unaffected (AUTOINCREMENT advances with explicit IDs).

Revision ID: 004_fix_identity_sequences
Revises: 003_drug_seeds
"""
from alembic import op
import sqlalchemy as sa

revision = "004_fix_identity_sequences"
down_revision = "003_drug_seeds"
branch_labels = None
depends_on = None

# tables whose seeds used OVERRIDING SYSTEM VALUE with explicit IDs (rev 002/003)
_SEEDED_TABLES = [
    "branches",
    "permissions",
    "roles",
    "accounts",
    "app_plugins",
    "users",
    "drugs",
]


def upgrade() -> None:
    for table in _SEEDED_TABLES:
        op.execute(sa.text(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                false
            )
        """))


def downgrade() -> None:
    # No-op: the sequences are derived state; the seed data is removed by
    # downgrading 002/003, and sequence realignment is recalculated on upgrade.
    pass