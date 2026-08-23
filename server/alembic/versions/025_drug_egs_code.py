"""core rev 025 — drugs.egs_code (ticket #30, S4.3)

One nullable EGS code per drug for ETA item coding (plan/02 §6: GS1 or
Egyptian EGS product coding). Precedence at issue time (coding.py): a valid
GS1 GTIN from drug_barcodes wins; else this column; else the documented
EGS-{branchCode}-{drugId} fallback. Nullable — most pharmacy items carry no
registered EGS code yet, and bulk ETA registration is a later decision.

Revision ID: 025_drug_egs_code
Revises: 024_einvoice_submission_state
"""
from alembic import op
import sqlalchemy as sa

revision = "025_drug_egs_code"
down_revision = "024_einvoice_submission_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drugs", sa.Column("egs_code", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("drugs", "egs_code")
