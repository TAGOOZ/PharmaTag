"""core rev 035 — chain buy orders (ticket #36, S5.6)

Merge legacy 12-col ChainBuyStore/ChainBuyUsers into single table
`chain_buy_orders` per plan/01_db_plan.md §3.6 and schema/schema_postgres.sql
:635-654. Also ensures `dead_stock_exchange` (RawakidTablew, رواكد) exists
per schema_postgres.sql:615-633 — both were S→logistics per A08 but ship now
in CORE rev (ADR-0002 T1 precedent, same call as rev 027 transfers / 031
needs: chain machinery deferred, G12 atomicity is core).

* `dead_stock_exchange` — dead-stock exchange offers (RawakidTablew 12-col
  variant, SourceIdDateTime, both tels, Mohafaza/Markaz/country, transfer_status).
  Created IF NOT EXISTS so the migration is idempotent against a partial
  logistics plugin install.

* `chain_buy_orders` — chain buy orders (ChainBuyStore + ChainBuyUsers 12-col,
  StoreName, IdDateTime, both tels, Mohafaza/Markaz/country, transfer_status).
  Columns mirror schema_postgres.sql:635-654 verbatim plus CHECKs and FKs;
  `updated_at` tracks edits (no trigger, app stamps it).

* Indexes: ix_chain_buy_branch (branch_id), ix_chain_buy_drug (drug_id),
  ix_chain_buy_store (store_name), ix_chain_buy_governorate (governorate, district)

* Permission `chain_buy.manage` (إدارة الشراء الجماعي) seeded to
  admin(1)/pharmacist(2)/manager(5) — legacy floor 3 stock area, like
  stock.manage / transfers.manage / needs.manage.

SQLite twin: server/sqlite/migrations/035_chain_buy.sql (INTEGER minor units
×10000 for qty/price, ×100 for sell_disc; TEXT + CHECK for status; same
indexes and permission seeds). Desktop bundle schema/schema_sqlite.sql
mirrors the twin so parity_check stays green.

Revision ID: 035_chain_buy
Revises: 034_stock_chain_snapshot
"""
from alembic import op
import sqlalchemy as sa

revision = "035_chain_buy"
down_revision = "034_stock_chain_snapshot"
branch_labels = None
depends_on = None


def _identity() -> sa.Identity:
    # BY DEFAULT so offline replay can insert explicit ids (needs 031 precedent);
    # chain_buy has no natural key to dedupe on (like needs).
    return sa.Identity(always=False)


def upgrade() -> None:
    tz = sa.TIMESTAMP(timezone=True)
    now = sa.text("now()")

    # ------------------------------------------------------------------
    # dead_stock_exchange — RawakidTablew (رواكد) — S→logistics, shipped CORE
    # ------------------------------------------------------------------
    # IF NOT EXISTS so re-running against a DB that already has the logistics
    # plugin tables (future) is a no-op — same idiom as 027/031 tables.
    op.create_table(
        "dead_stock_exchange",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("expire", sa.Date()),
        sa.Column("price", sa.Numeric(18, 4), server_default="0"),
        sa.Column("sell_disc", sa.Numeric(5, 2), server_default="0"),
        sa.Column("tips", sa.String(50), server_default=""),
        sa.Column("governorate", sa.String(50), server_default=""),
        sa.Column("district", sa.String(50), server_default=""),
        sa.Column("source_pharmacist_tel", sa.String(15), server_default=""),
        sa.Column("requester_tel", sa.String(15), server_default=""),
        sa.Column("source_iddatetime", tz),
        sa.Column("country", sa.String(50), server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.CheckConstraint("qty > 0", name="ck_dead_stock_qty_positive"),
        sa.CheckConstraint("price >= 0", name="ck_dead_stock_price_nonneg"),
        sa.CheckConstraint(
            "status IN ('created', 'in_transit', 'delivered', 'received', 'cancelled')",
            name="ck_dead_stock_status",
        ),
        if_not_exists=True,
    )

    # ------------------------------------------------------------------
    # chain_buy_orders — ChainBuyStore + ChainBuyUsers merged 12-col
    # ------------------------------------------------------------------
    op.create_table(
        "chain_buy_orders",
        sa.Column("id", sa.BigInteger(), _identity(), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("drug_id", sa.BigInteger(), sa.ForeignKey("drugs.id"), nullable=False),
        sa.Column("store_name", sa.String(100), server_default=""),
        sa.Column("pharmacist_tel", sa.String(15), server_default=""),
        sa.Column("requester_tel", sa.String(15), server_default=""),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), server_default="0"),
        sa.Column("sell_disc", sa.Numeric(5, 2), server_default="0"),
        sa.Column("expire", sa.Date()),
        sa.Column("tips", sa.String(50), server_default=""),
        sa.Column("governorate", sa.String(50), server_default=""),
        sa.Column("district", sa.String(50), server_default=""),
        sa.Column("country", sa.String(50), server_default=""),
        sa.Column("iddatetime", tz, server_default=now),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("created_at", tz, nullable=False, server_default=now),
        sa.Column("updated_at", tz),
        sa.CheckConstraint("qty > 0", name="ck_chain_buy_qty_positive"),
        sa.CheckConstraint("price >= 0", name="ck_chain_buy_price_nonneg"),
        sa.CheckConstraint(
            "status IN ('created', 'in_transit', 'delivered', 'received', 'cancelled')",
            name="ck_chain_buy_status",
        ),
        if_not_exists=True,
    )

    op.create_index("ix_chain_buy_branch", "chain_buy_orders", ["branch_id"], if_not_exists=True)
    op.create_index("ix_chain_buy_drug", "chain_buy_orders", ["drug_id"], if_not_exists=True)
    op.create_index("ix_chain_buy_store", "chain_buy_orders", ["store_name"], if_not_exists=True)
    op.create_index(
        "ix_chain_buy_governorate", "chain_buy_orders", ["governorate", "district"], if_not_exists=True
    )
    # helpful for dead_stock lookups as well (not required by ticket but cheap)
    op.create_index(
        "ix_dead_stock_branch", "dead_stock_exchange", ["branch_id"], if_not_exists=True
    )
    op.create_index(
        "ix_dead_stock_drug", "dead_stock_exchange", ["drug_id"], if_not_exists=True
    )

    # permission — chain_buy.manage (إدارة الشراء الجماعي), floor 3 stock area
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('chain_buy.manage', 'إدارة الشراء الجماعي')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'chain_buy.manage' AND r.id IN (1, 2, 5)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'chain_buy.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'chain_buy.manage'"))

    op.drop_index("ix_dead_stock_drug", table_name="dead_stock_exchange")
    op.drop_index("ix_dead_stock_branch", table_name="dead_stock_exchange")
    op.drop_index("ix_chain_buy_governorate", table_name="chain_buy_orders")
    op.drop_index("ix_chain_buy_store", table_name="chain_buy_orders")
    op.drop_index("ix_chain_buy_drug", table_name="chain_buy_orders")
    op.drop_index("ix_chain_buy_branch", table_name="chain_buy_orders")
    op.drop_table("chain_buy_orders")
    op.drop_table("dead_stock_exchange")
