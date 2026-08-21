-- PharmaTag core rev 014 — SQLite twin of alembic 014_opening_balances.py
-- Opening balances (S2.7, ticket #22): seed opening cash/stock/receivables/payables.
-- Journals / month_open_balances tables already exist; this only seeds the permission.

INSERT INTO permissions (code, name_ar) VALUES ('opening_balances.manage', 'الأرصدة الافتتاحية');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'opening_balances.manage' AND r.id IN (1, 4, 5);
