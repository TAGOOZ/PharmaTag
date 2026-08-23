-- PharmaTag core rev 025 — SQLite twin of alembic 025_drug_egs_code.py
-- Nullable EGS code per drug for ETA item coding (S4.3, ticket #30):
-- precedence at issue time is GTIN barcode -> this column -> EGS-{branch}-{id}.

ALTER TABLE drugs ADD COLUMN egs_code TEXT;
