-- PharmaTag core rev 030 — SQLite twin of alembic 030_transfer_rev.py
-- transfers.rev version watermark (#55 gap fix): monotonic per-transfer
-- revision (draft=1, dispatched=2, received/cancelled=3) bumped in the same
-- transaction as the state flip. Ordering authority for versioned offline
-- replay — stale/duplicate/out-of-order copies are skipped, higher-rev
-- payloads fold the legal stage chain. Legacy rows default to rev=1.
--
-- Plain column add: SQLite ALTER TABLE ADD COLUMN supports NOT NULL DEFAULT.

ALTER TABLE transfers ADD COLUMN rev INTEGER NOT NULL DEFAULT 1;
