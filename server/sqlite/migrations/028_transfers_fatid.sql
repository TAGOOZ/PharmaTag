-- PharmaTag core rev 028 — SQLite twin of alembic 028_transfers_fatid.py
-- legacy_fatid ETL idempotency (ticket #56): partial unique index so a
-- re-imported FAT file converges on ONE transfer per source branch; NULL
-- fatid rows (interactive drafts) are exempt.

CREATE UNIQUE INDEX uq_transfers_source_fatid
    ON transfers (source_branch_id, legacy_fatid)
    WHERE legacy_fatid IS NOT NULL;
