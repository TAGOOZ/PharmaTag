"""core rev 036 — branch settings (ticket #59)

Extends `branches` with settings surfaced by
GET/PATCH /api/v1/branches/{id}/settings (AC #59):

* `tax_id` — branch legal tax identifier (Egypt ETA, 5-30 chars when present)
* `treasury_enabled` — A19 single-drawer → treasury toggle (P1 drawer vs خزينة)
* `printer_config` — per-purpose printer defaults for PrintService
  (plan/03 §5.5, F20.3 — 5 roles: receipt/report/barcode/invoice/A4)

All three ship on the canonical `branches` row so the existing
entity='branch' outbox snapshot (rev 001 + replay #34) carries them to
offline peers without a new entity — the patch just bumps `updated_at`
and fans out the full branch payload like every other branch mutation
(G12 atomic audit + sync_log per ACTIVE branch).

SQLite twin: server/sqlite/migrations/036_branch_settings.sql
(TEXT/CJS booleans → INTEGER 0/1, JSONB → TEXT).
Desktop bundle: schema/schema_sqlite.sql mirrors the twin so
parity_check stays green.

Revision ID: 036_branch_settings
Revises: 035_chain_buy
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "036_branch_settings"
down_revision = "035_chain_buy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "tax_id",
            sa.String(30),
            server_default="",
            nullable=False,
        ),
    )
    op.add_column(
        "branches",
        sa.Column(
            "treasury_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "branches",
        sa.Column(
            "printer_config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "printer_config")
    op.drop_column("branches", "treasury_enabled")
    op.drop_column("branches", "tax_id")
