"""core rev 027 — inter-pharmacy transfers (ticket #32, S5.2; decisions T1–T7)

`transfers` + `transfer_lines` ship in CORE (T1, ADR-0002 precedent): the
chain plugin scaffold + per-plugin migration machinery is deferred until a
second plugin needs it, and legacy `titaninn.itemsasstring` is dead code in
the binary (0 p-code refs) so `transfer_lines` is designed fresh.

* `transfers` — one stock transfer between two branches. State machine
  `draft → dispatched → received`, `cancelled` reachable only from draft (T2;
  delivery.phy never tracked transfers — the machine is invented, not
  inherited). Numbering: per-SOURCE-branch monotonic `transfer_no`,
  UNIQUE backstop (T5, G07 pattern). `legacy_fatid` nullable passthrough for
  ETL idempotency.
* `transfer_lines` — per-drug sent/received quantities. `alloc_json` snapshots
  the explicit batch allocations taken at dispatch (batch_id/randomid/qty/
  cost/expire per take) so receive creates target batches at preserved cost/
  expire verbatim (EDA traceability) and a shortfall auto-returns to the exact
  source batches (T2/T4).

Status is TEXT + CHECK (rev 023 pattern), not a native ENUM: portable plain
Postgres and a trivial SQLite twin. No GL posting in this slice (T3).
scripts/parity_check.py drops both tables from its plugin-leak skip list in
this slice.
"""
from alembic import op
import sqlalchemy as sa

revision = "027_transfers"
down_revision = "026_branch_permissions"
branch_labels = None
depends_on = None


def _identity() -> sa.Identity:
    return sa.Identity(always=True)


def upgrade() -> None:
    op.create_table(
        "transfers",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("source_branch_id", sa.BigInteger(),
                  sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("target_branch_id", sa.BigInteger(),
                  sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("transfer_no", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("legacy_fatid", sa.String(50)),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("dispatched_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("received_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("dispatched_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("source_branch_id", "transfer_no",
                            name="uq_transfers_branch_no"),
        sa.CheckConstraint("source_branch_id <> target_branch_id",
                           name="ck_transfers_distinct_branches"),
        sa.CheckConstraint(
            "status IN ('draft', 'dispatched', 'received', 'cancelled')",
            name="ck_transfers_status",
        ),
    )
    op.create_index("ix_transfers_target", "transfers", ["target_branch_id"])

    op.create_table(
        "transfer_lines",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("transfer_id", sa.BigInteger(),
                  sa.ForeignKey("transfers.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("drug_id", sa.BigInteger(),
                  sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("sent_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("received_qty", sa.Numeric(18, 4)),
        sa.Column("alloc_json", sa.JSON()),
        sa.CheckConstraint("sent_qty > 0", name="ck_transfer_lines_sent_positive"),
        sa.UniqueConstraint("transfer_id", "drug_id",
                            name="uq_transfer_lines_transfer_drug"),
    )
    op.create_index("ix_transfer_lines_transfer", "transfer_lines", ["transfer_id"])

    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('transfers.manage', 'إدارة التحويلات بين الفروع')
    """))
    # T6: admin / pharmacist / manager; legacy floor 3 (stock area)
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'transfers.manage' AND r.id IN (1, 2, 5)
    """))


def downgrade() -> None:
    op.drop_index("ix_transfer_lines_transfer", table_name="transfer_lines")
    op.drop_table("transfer_lines")
    op.drop_index("ix_transfers_target", table_name="transfers")
    op.drop_table("transfers")
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'transfers.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'transfers.manage'"))
