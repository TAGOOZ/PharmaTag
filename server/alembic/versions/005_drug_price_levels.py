"""core rev 005 — drug-master price levels + drugs.manage permission (ticket #8)

S1.2 (plan/05 §S1.2) adds 3 price levels (public / wholesale / cost — سعر
الجمهور / سعر الجملة / سعر الشراء-التكلفة, plan/04 F14.3) and the granular
permission that gates drug-master writes. The 3-tier pricing is carried on the
`drugs` master itself (public = `price`, wholesale/cost = the two new columns)
per the plan/01 table layout for the drug master; `drug_costs` remains the
wzdrugs2 legacy-migration mirror (plan/01 §1.3#2) and is not the CRUD surface.

* `drugs.price_wholesale` / `drugs.price_cost` — NUMERIC(18,4) per-unit price
  levels (plan/01 §4.1 per-unit class), server_default 0, and a CHECK that all
  three price levels are non-negative (reject negative prices at the DB too).
* Backfill: seeded medicines (rev 003) get `price_wholesale = price`; cost is
  unknown for the seeds so it stays at the default 0.
* `permissions` row `drugs.manage` (الأصناف والمخزون — the legacy level-3 area,
  plan/02 §3) + admin role grant. Uses a generated identity id (no
  OVERRIDING SYSTEM VALUE) so the sequence advances normally — the rev 004
  setval discipline still holds for any explicit seed.

Revision ID: 005_drug_price_levels
Revises: 004_fix_identity_sequences
"""
from alembic import op
import sqlalchemy as sa

revision = "005_drug_price_levels"
down_revision = "004_fix_identity_sequences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "drugs",
        sa.Column("price_wholesale", sa.Numeric(18, 4), server_default="0"),
    )
    op.add_column(
        "drugs",
        sa.Column("price_cost", sa.Numeric(18, 4), server_default="0"),
    )
    op.create_check_constraint(
        "ck_drugs_prices_nonneg",
        "drugs",
        "price >= 0 AND price_wholesale >= 0 AND price_cost >= 0",
    )
    # seeded medicines: wholesale == public price for now; cost stays default 0
    op.execute(sa.text(
        "UPDATE drugs SET price_wholesale = COALESCE(price, 0) "
        "WHERE price_wholesale = 0"
    ))
    # drugs.manage gates drug-master writes (legacy level-3 area الأصناف والمخزون)
    op.execute(sa.text(
        "INSERT INTO permissions (code, name_ar) "
        "VALUES ('drugs.manage', 'الأصناف والمخزون')"
    ))
    op.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT 1, id FROM permissions WHERE code = 'drugs.manage'"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'drugs.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'drugs.manage'"))
    op.drop_constraint("ck_drugs_prices_nonneg", "drugs", type_="check")
    op.drop_column("drugs", "price_cost")
    op.drop_column("drugs", "price_wholesale")