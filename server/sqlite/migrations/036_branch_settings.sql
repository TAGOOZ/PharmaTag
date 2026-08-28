-- PharmaTag core rev 036 — SQLite twin of alembic 036_branch_settings.py
-- Branch settings (ticket #59): tax_id, treasury_enabled, printer_config
-- Mirrors PG DDL: TEXT DEFAULT '' for tax_id, INTEGER 0/1 for treasury_enabled,
-- TEXT JSON '{}' for printer_config. Desktop bundle mirrors this file.

ALTER TABLE branches ADD COLUMN tax_id TEXT NOT NULL DEFAULT '';
ALTER TABLE branches ADD COLUMN treasury_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE branches ADD COLUMN printer_config TEXT NOT NULL DEFAULT '{}';
