-- PharmaTag core rev 031 — SQLite twin of alembic 031_needs_orders.py
-- Needs + purchase orders (S5.3, ticket #33; decisions N1–N6). needs =
-- titanneed inter-pharmacy request (pending→fulfilled|cancelled) with
-- transfer_id handoff link; purchase_orders = legacy `orders` header
-- ('saved'=done) + invented itemized lines. Identities are BY DEFAULT so
-- replay can insert rows carrying the outbox payload's id (no natural key).

CREATE TABLE needs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id        INTEGER NOT NULL REFERENCES branches(id),
    drug_id          INTEGER NOT NULL REFERENCES drugs(id),
    qty              INTEGER NOT NULL DEFAULT 0,      -- ×10000
    datee            TEXT,
    sender_branch_id INTEGER REFERENCES branches(id),
    target_branch_id INTEGER REFERENCES branches(id),
    legacy_sender    TEXT NOT NULL DEFAULT '',
    legacy_target    TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','fulfilled','cancelled')),
    transfer_id      INTEGER REFERENCES transfers(id),
    rev              INTEGER NOT NULL DEFAULT 1,
    created_by       INTEGER REFERENCES users(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    fulfilled_at     TEXT
);

CREATE INDEX ix_needs_sender ON needs (sender_branch_id, status);
CREATE INDEX ix_needs_target ON needs (target_branch_id, status);

CREATE TABLE purchase_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    party_id     INTEGER REFERENCES parties(id),
    orderid      TEXT NOT NULL DEFAULT '',
    orderdate    TEXT,
    datee        TEXT,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','saved','received','cancelled')),
    rev          INTEGER NOT NULL DEFAULT 1,
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    saved_at     TEXT,
    received_at  TEXT,
    cancelled_at TEXT
);

CREATE INDEX ix_purchase_orders_branch ON purchase_orders (branch_id);

CREATE TABLE purchase_order_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    qty          INTEGER NOT NULL CHECK (qty > 0),   -- ×10000
    unit_cost    INTEGER,                            -- ×10000
    received_qty INTEGER,                            -- ×10000
    UNIQUE (order_id, drug_id)
);

CREATE INDEX ix_po_lines_order ON purchase_order_lines (order_id);

-- needs.manage seeded to admin/pharmacist/manager, legacy floor 3 (stock area)
INSERT INTO permissions (code, name_ar)
VALUES ('needs.manage', 'إدارة النواقص والطلبات');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE p.code = 'needs.manage' AND r.id IN (1, 2, 5);
