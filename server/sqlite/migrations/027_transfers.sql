-- PharmaTag core rev 027 — SQLite twin of alembic 027_transfers.py
-- Inter-pharmacy transfers (S5.2, ticket #32; decisions T1–T7). State machine
-- draft → dispatched → received, cancelled only from draft (CHECK). Per-source
-- monotonic transfer_no with UNIQUE backstop; legacy_fatid ETL passthrough.
-- alloc_json is TEXT holding the dispatch batch allocations verbatim so the
-- desktop replay reproduces exact batches/costs. No GL posting in S5.2.

CREATE TABLE transfers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_branch_id INTEGER NOT NULL REFERENCES branches(id),
    target_branch_id INTEGER NOT NULL REFERENCES branches(id),
    transfer_no      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','dispatched','received','cancelled')),
    legacy_fatid     TEXT,
    note             TEXT NOT NULL DEFAULT '',
    created_by       INTEGER REFERENCES users(id),
    dispatched_by    INTEGER REFERENCES users(id),
    received_by      INTEGER REFERENCES users(id),
    cancelled_by     INTEGER REFERENCES users(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    dispatched_at    TEXT,
    received_at      TEXT,
    cancelled_at     TEXT,
    UNIQUE (source_branch_id, transfer_no),
    CHECK (source_branch_id <> target_branch_id)
);

CREATE INDEX ix_transfers_target ON transfers (target_branch_id);

CREATE TABLE transfer_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id  INTEGER NOT NULL REFERENCES transfers(id) ON DELETE CASCADE,
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    sent_qty     INTEGER NOT NULL CHECK (sent_qty > 0),  -- ×10000
    received_qty INTEGER,                                -- ×10000
    alloc_json   TEXT,                                   -- JSON allocations text
    UNIQUE (transfer_id, drug_id)
);

CREATE INDEX ix_transfer_lines_transfer ON transfer_lines (transfer_id);

-- T6: transfers.manage seeded to admin/pharmacist/manager, legacy floor 3
INSERT INTO permissions (code, name_ar)
VALUES ('transfers.manage', 'إدارة التحويلات بين الفروع');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE p.code = 'transfers.manage' AND r.id IN (1, 2, 5);
