"""core rev 029 — stock qty backstop CHECKs (#57, from the #32 audit)

CHECK (qty >= 0) on stock_batches.qty and branch_stock.qty: the app-level
guards (_decrement_source_batch / _adjust_branch_stock, SELECT ... FOR UPDATE)
hold today; this is the race BACKSTOP patterns.md demands — no code path,
replay bug or manual psql session can ever drive a quantity negative.
Defense-in-depth only: no known bug writes a negative row (fresh test DB
migrates clean).
"""
from alembic import op

revision = "029_stock_qty_backstops"
down_revision = "028_transfers_fatid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_stock_batches_qty_nonneg", "stock_batches", "qty >= 0"
    )
    op.create_check_constraint(
        "ck_branch_stock_qty_nonneg", "branch_stock", "qty >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_branch_stock_qty_nonneg", "branch_stock", type_="check")
    op.drop_constraint("ck_stock_batches_qty_nonneg", "stock_batches", type_="check")
