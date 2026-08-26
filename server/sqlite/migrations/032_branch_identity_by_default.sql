-- PharmaTag core rev 032 — SQLite twin of alembic 032_branch_identity_by_default.py
-- No-op on the twin: SQLite INTEGER PRIMARY KEY AUTOINCREMENT already accepts
-- explicit ids, so the #34 chain replay inserts converge without a schema
-- change. Recorded only so the twin revision ladder stays aligned with PG.
SELECT 1;
