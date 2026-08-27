-- PharmaTag core rev 026 — SQLite twin of alembic 026_branch_permissions.py
-- Branch registry permission (S5.1, ticket #31): branches.manage gated to admin+manager.
INSERT OR IGNORE INTO permissions (code, name_ar) VALUES ('branches.manage', 'إدارة الفروع والأجهزة');
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE p.code = 'branches.manage' AND r.id IN (1, 5);
