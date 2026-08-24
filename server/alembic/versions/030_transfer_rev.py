"""core rev 030 — transfers.rev version watermark (#55 gap fix)

Monotonic per-transfer revision: draft=1, dispatched=2, received/cancelled=3,
bumped IN the same transaction as the state flip (G12). It is the ordering
authority for VERSIONED offline replay: a peer compares the payload's rev to
its local row and skips stale/duplicate/out-of-order copies or folds the
legal stage chain forward — replacing the binary exists-skip that could never
converge a peer offline for a whole flow. `updated_at` stays diagnostics-only.
Legacy rows keep rev=1 (default); their status still resolves via the legal
stage chain on the first upgrade.
"""
import sqlalchemy as sa
from alembic import op

revision = "030_transfer_rev"
down_revision = "029_stock_qty_backstops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transfers",
        sa.Column("rev", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("transfers", "rev")
