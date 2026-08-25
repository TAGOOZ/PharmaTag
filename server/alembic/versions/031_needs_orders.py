"""core rev 031 — needs + purchase orders (ticket #33, S5.3; decisions N1–N6)

Ships in CORE (ADR-0002 precedent, same call as transfers rev 027): the
needs→transfer handoff writes a `transfers` row and the G12 audit+outbox
atomicity is core machinery; the chain-plugin migration machinery stays
deferred until a second plugin actually needs it.

* `needs` — inter-pharmacy stock request (titanneed 6-col ground truth:
  drugname/quant/datee/sender/target). `branch_id` = requesting branch (C9);
  `sender_branch_id` nullable = open request for any sister branch when NULL.
  Status pending → fulfilled | cancelled. `transfer_id` links the transfer
  created by the needs→transfer handoff (auto-fulfilled on receive);
  `rev` is the monotonic version watermark for versioned offline replay
  (#55 pattern).
* `purchase_orders` — legacy `orders` header (orderid/orderdate/datee,
  status NULL=pending → 'pending'; 'saved'=done) + optional `party_id`
  supplier (Egypt market: POs go to distributors as آجل accounts; legacy
  never structured it but the wire always had one).
* `purchase_order_lines` — INVENTED (legacy kept order contents unstructured):
  per-drug qty + unit-cost snapshot so auto-order suggestions attach to a
  real order. No money mutation until the purchases receipt posts.

Status is TEXT + CHECK (rev 023 pattern), not a native ENUM: portable plain
Postgres and a trivial SQLite twin. No GL posting in this slice (N5).
scripts/parity_check.py drops all three tables from its plugin-leak skip
list in this slice.
"""
from alembic import op
import sqlalchemy as sa

revision = "031_needs_orders"
down_revision = "030_transfer_rev"
branch_labels = None
depends_on = None


def _identity() -> sa.Identity:
    # BY DEFAULT (not ALWAYS): offline-peer replay (#33) inserts rows with the
    # OUTBOX payload's id so every peer converges on one shared entity id;
    # needs/POs have no natural key to dedupe on (transfers had transfer_no).
    return sa.Identity(always=False)


def upgrade() -> None:
    op.create_table(
        "needs",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(),
                  sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(),
                  sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("datee", sa.Date()),
        sa.Column("sender_branch_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("target_branch_id", sa.BigInteger(), sa.ForeignKey("branches.id")),
        sa.Column("legacy_sender", sa.String(20), server_default=""),
        sa.Column("legacy_target", sa.String(20), server_default=""),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("transfer_id", sa.BigInteger(),
                  sa.ForeignKey("transfers.id", use_alter=True)),
        sa.Column("rev", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("fulfilled_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'fulfilled', 'cancelled')",
            name="ck_needs_status",
        ),
    )
    op.create_index("ix_needs_sender", "needs", ["sender_branch_id", "status"])
    op.create_index("ix_needs_target", "needs", ["target_branch_id", "status"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(),
                  sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id")),
        sa.Column("orderid", sa.String(50), server_default=""),
        sa.Column("orderdate", sa.Date()),
        sa.Column("datee", sa.Date()),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("rev", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("saved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'saved', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
    )
    op.create_index("ix_purchase_orders_branch", "purchase_orders", ["branch_id"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(),
                  sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("drug_id", sa.BigInteger(),
                  sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4)),
        sa.Column("received_qty", sa.Numeric(18, 4)),
        sa.CheckConstraint("qty > 0", name="ck_po_lines_qty_positive"),
        sa.UniqueConstraint("order_id", "drug_id",
                            name="uq_po_lines_order_drug"),
    )
    op.create_index("ix_po_lines_order", "purchase_order_lines", ["order_id"])

    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('needs.manage', 'إدارة النواقص والطلبات')
    """))
    # admin / pharmacist / manager; legacy floor 3 (stock area, like transfers)
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'needs.manage' AND r.id IN (1, 2, 5)
    """))


def downgrade() -> None:
    op.drop_index("ix_po_lines_order", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_branch", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_needs_target", table_name="needs")
    op.drop_index("ix_needs_sender", table_name="needs")
    op.drop_table("needs")
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'needs.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'needs.manage'"))

# NOTE: needs/purchase_orders(_lines) use GENERATED BY DEFAULT identities —
# replay inserts carry the source id explicitly (see _identity above).
