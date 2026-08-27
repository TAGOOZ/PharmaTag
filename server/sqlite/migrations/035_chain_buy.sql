-- PharmaTag core rev 035 — SQLite twin of alembic 035_chain_buy.py
-- Chain buy (S5.6, #36; T1 CORE — ADR-0002 precedent): ChainBuyStore +
-- ChainBuyUsers 12-col merged into chain_buy_orders + dead_stock_exchange
-- (RawakidTablew / رواكد). Mirrors PG DDL with INTEGER minor units per
-- plan/01 §4.2: NUMERIC(18,4) qty/price ×10000, NUMERIC(5,2) sell_disc ×100;
-- TEXT + CHECK for transfer_status; same FKs, defaults, CHECKs, indexes and
-- chain_buy.manage seed as PG so parity_check stays green.

-- dead_stock_exchange — رواكد (RawakidTablew 615-633)
CREATE TABLE IF NOT EXISTS dead_stock_exchange (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id             INTEGER NOT NULL REFERENCES branches(id),
    drug_id               INTEGER NOT NULL REFERENCES drugs(id),
    qty                   INTEGER NOT NULL CHECK (qty > 0),   -- ×10000, no DEFAULT (dead default violates CHECK)
    expire                TEXT,
    price                 INTEGER DEFAULT 0 CHECK (price >= 0),          -- ×10000
    sell_disc             INTEGER DEFAULT 0,                             -- rate ×100
    tips                  TEXT DEFAULT '',
    governorate           TEXT DEFAULT '',
    district              TEXT DEFAULT '',
    source_pharmacist_tel TEXT DEFAULT '',
    requester_tel         TEXT DEFAULT '',
    source_iddatetime     TEXT,                                          -- ISO-8601
    country               TEXT DEFAULT '',
    status                TEXT NOT NULL DEFAULT 'created'
                           CHECK (status IN ('created','in_transit','delivered','received','cancelled')),
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_dead_stock_branch ON dead_stock_exchange (branch_id);
CREATE INDEX IF NOT EXISTS ix_dead_stock_drug ON dead_stock_exchange (drug_id);

-- chain_buy_orders — ChainBuyStore + ChainBuyUsers merged 12-col (635-654)
CREATE TABLE IF NOT EXISTS chain_buy_orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    drug_id        INTEGER NOT NULL REFERENCES drugs(id),
    store_name     TEXT DEFAULT '',
    pharmacist_tel TEXT DEFAULT '',
    requester_tel  TEXT DEFAULT '',
    qty            INTEGER NOT NULL CHECK (qty > 0),          -- ×10000, no DEFAULT (violates CHECK)
    price          INTEGER DEFAULT 0 CHECK (price >= 0),                 -- ×10000
    sell_disc      INTEGER DEFAULT 0,                                    -- rate ×100
    expire         TEXT,
    tips           TEXT DEFAULT '',
    governorate    TEXT DEFAULT '',
    district       TEXT DEFAULT '',
    country        TEXT DEFAULT '',
    iddatetime     TEXT DEFAULT (datetime('now')),
    status         TEXT NOT NULL DEFAULT 'created'
                   CHECK (status IN ('created','in_transit','delivered','received','cancelled')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_chain_buy_branch ON chain_buy_orders (branch_id);
CREATE INDEX IF NOT EXISTS ix_chain_buy_drug ON chain_buy_orders (drug_id);
CREATE INDEX IF NOT EXISTS ix_chain_buy_store ON chain_buy_orders (store_name);
CREATE INDEX IF NOT EXISTS ix_chain_buy_governorate ON chain_buy_orders (governorate, district);

-- permission — chain_buy.manage (إدارة الشراء الجماعي), floor 3 stock area
INSERT INTO permissions (code, name_ar)
VALUES ('chain_buy.manage', 'إدارة الشراء الجماعي');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE p.code = 'chain_buy.manage' AND r.id IN (1, 2, 5);
