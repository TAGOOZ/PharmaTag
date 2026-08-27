-- PharmaTag core rev 034 — SQLite twin of alembic 034_stock_chain_snapshot.py
-- Stock minimum permission + chain_stock report (ticket #35, S5.5): titanksastock
-- → branch_stock projection (A06), per-(drug, branch) qty/minimum/shortage,
-- regenerated from canonical branch_stock, read-only projection.

INSERT INTO permissions (code, name_ar)
VALUES ('stock.manage', 'إدارة المخزون');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE p.code = 'stock.manage' AND r.id IN (1, 2, 5);

INSERT INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('chain_stock', 'chain', 'مخزون السلسلة', 'Chain Stock Snapshot', '[]', 'A4', 210);
