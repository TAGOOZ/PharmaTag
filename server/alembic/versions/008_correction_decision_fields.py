"""core rev 008 — correction decision fields (S1.7 edge pass, ticket #13)

Two columns make the approval flow race-free and auditable:

* `counted` — the physical qty the pharmacist observed at submit time, stored
  so approval can verify the balance did not drift: the applied `delta` is only
  valid while `system_now + delta == counted`. Without it, an approval silently
  over/under-corrects when stock moved between submit and decide.
* `rejected_by` — the manager who rejected a request. The shared
  `approved_by` column is only meaningful for approvals; a rejection must not
  masquerade as one.

Both are nullable: they are app-managed audit fields, not legacy-imported.
"""
from alembic import op
import sqlalchemy as sa

revision = "008_correction_decision_fields"
down_revision = "007_stock_corrections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_correction_requests",
        sa.Column("counted", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "stock_correction_requests",
        sa.Column("rejected_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_correction_requests", "rejected_by")
    op.drop_column("stock_correction_requests", "counted")