"""core rev 028 — legacy_fatid ETL idempotency (ticket #56)

Partial unique index UNIQUE(source_branch_id, legacy_fatid) WHERE
legacy_fatid IS NOT NULL: re-importing the same legacy Titan FAT file must
converge on ONE transfer per source branch instead of minting a second one
with a fresh transfer_no (dispatching both would double-move stock). NULL
fatid rows are exempt — interactive drafts stay unlimited.

The dedupe itself lives in create_draft (#56): same source+fatid+target
replays the EXISTING transfer, a different target is a 409 conflict.
"""
from alembic import op
import sqlalchemy as sa

revision = "028_transfers_fatid"
down_revision = "027_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_transfers_source_fatid",
        "transfers",
        ["source_branch_id", "legacy_fatid"],
        unique=True,
        postgresql_where=sa.text("legacy_fatid IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transfers_source_fatid", table_name="transfers")
