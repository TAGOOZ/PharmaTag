"""core rev 034 — stock minimum permission + chain_stock report (ticket #35, S5.5)

* `stock.manage` — per-branch reorder point editing (minimum = reorder point).
  Granted to admin/pharmacist/manager (roles 1,2,5) with legacy floor 3 (stock
  area, like stock.adjust/transfers/needs).
* `chain_stock` — cross-branch stock snapshot (titanksastock → branch_stock
  projection, A06). Per-drug per-branch qty/minimum/shortage, regenerated from
  canonical branch_stock (read-only projection). Inert until views.py registers
  the engine, but the catalog row must exist for the report menu.
"""
from alembic import op
import sqlalchemy as sa

revision = "034_stock_chain_snapshot"
down_revision = "033_chain_sales_catalog"
branch_labels = None
depends_on = None

SEED_ROWS = [
    # code, category, title_ar, title_en, params, sort
    ("chain_stock", "chain", "مخزون السلسلة",
     "Chain Stock Snapshot", '[]', 210),
]


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('stock.manage', 'إدارة المخزون')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'stock.manage' AND r.id IN (1, 2, 5)
    """))
    for code, category, title_ar, title_en, params, sort in SEED_ROWS:
        op.execute(
            sa.text(
                "INSERT INTO report_catalog "
                "(code, category, title_ar, title_en, params, paper, sort) "
                "VALUES (:code, :category, :title_ar, :title_en, "
                "CAST(:params AS jsonb), 'A4', :sort)"
            ).bindparams(
                code=code,
                category=category,
                title_ar=title_ar,
                title_en=title_en,
                params=params,
                sort=sort,
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM report_catalog WHERE code = ANY(:codes)").bindparams(
            codes=[row[0] for row in SEED_ROWS]
        )
    )
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'stock.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'stock.manage'"))
