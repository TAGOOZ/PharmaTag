"""core rev 024 — einvoice submission retry bookkeeping (ticket #29, S4.2)

`einvoice_log` gains the worker's retry state so submission survives offline
days and ETA transient errors without ever touching the chain identity:

* `attempts`        — submissions/polls attempted (monotonic)
* `next_attempt_at` — backoff gate; NULL means due immediately
* `last_error`      — last transport/ETA error text, for the status API

Resubmission reuses counter/uuid/qr_data verbatim (A15 idempotency); these
columns carry only scheduling state.

Revision ID: 024_einvoice_submission_state
Revises: 023_einvoice_foundations
"""
from alembic import op
import sqlalchemy as sa

revision = "024_einvoice_submission_state"
down_revision = "023_einvoice_foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "einvoice_log",
        sa.Column("attempts", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "einvoice_log",
        sa.Column("next_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "einvoice_log",
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("einvoice_log", "last_error")
    op.drop_column("einvoice_log", "next_attempt_at")
    op.drop_column("einvoice_log", "attempts")
