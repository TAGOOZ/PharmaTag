-- PharmaTag core rev 011 — SQLite twin of alembic 011_manual_journal_entries.py
-- Manual journal entries (S2.2, ticket #17): a posted manual قيد can be
-- reversed — the reversal is a fresh opposite-signed journal linked via
-- reverses_entry_id (A07-style), never an edit/delete of the original.
ALTER TABLE manual_journal_entries
    ADD COLUMN reverses_entry_id INTEGER REFERENCES manual_journal_entries(id);

-- journals.manage gates manual-journal posting + reversal (admin role 1,
-- accountant role 4, manager role 5; legacy floor 7)
INSERT INTO permissions (code, name_ar) VALUES ('journals.manage', 'ترحيل قيود يومية');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'journals.manage' AND r.id IN (1, 4, 5);