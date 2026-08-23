-- PharmaTag core rev 023 — SQLite twin of alembic 023_einvoice_foundations.py
-- E-invoice foundations (S4.1, ticket #28; ADR-0002): every sales invoice
-- gains a tax-document record with an atomic per-device UUID/counter chain
-- and a consumer QR. payload_json is TEXT holding the document verbatim (PG
-- side uses `json`, NOT jsonb, so document key order survives for the
-- SHA-256 recompute).

CREATE TABLE einvoice_counters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id     INTEGER NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL CHECK (kind IN ('receipt','return_receipt','invoice','credit_note')),
    last_counter  INTEGER NOT NULL DEFAULT 0,
    last_uuid     TEXT NOT NULL DEFAULT '',
    device_serial TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, kind)
);

CREATE TABLE einvoice_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id     INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    kind           TEXT NOT NULL CHECK (kind IN ('receipt','return_receipt','invoice','credit_note')),
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','submitted','accepted','rejected','failed')),
    counter        INTEGER NOT NULL,
    uuid           TEXT NOT NULL DEFAULT '',
    previous_uuid  TEXT NOT NULL DEFAULT '',
    reference_uuid TEXT NOT NULL DEFAULT '',
    device_serial  TEXT,
    qr_data        TEXT NOT NULL DEFAULT '',
    payload_json   TEXT,                              -- JSON document text
    response       TEXT NOT NULL DEFAULT '',
    submitted_at   TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, kind, counter),
    UNIQUE (invoice_id)
);

CREATE INDEX ix_einvoice_log_status ON einvoice_log (status);

-- presence of a party tax registration number routes credit sales to the B2B
-- eInvoice regime instead of an eReceipt
ALTER TABLE parties ADD COLUMN tax_registration_no TEXT NOT NULL DEFAULT '';
