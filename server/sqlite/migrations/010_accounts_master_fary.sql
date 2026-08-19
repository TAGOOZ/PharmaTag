-- PharmaTag core rev 010 — SQLite twin of alembic 010_accounts_master_fary.py
-- Backfill seeded accounts' master/fary (ticket #16 edge pass): fary = own
-- code, master = parent's code where a parent exists. Idempotent — only
-- touches empty/blank values. Pure data change; no table change.
UPDATE accounts SET fary = code WHERE fary IS NULL OR fary = '';
UPDATE accounts SET master = (SELECT p.code FROM accounts p WHERE p.id = accounts.parent_id)
WHERE parent_id IS NOT NULL AND (master IS NULL OR master = '');