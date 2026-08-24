-- PharmaTag core rev 029 — SQLite twin of alembic 029_stock_qty_backstops.py
-- Stock qty backstop (#57, from the #32 audit): CHECK (qty >= 0) on
-- stock_batches.qty + branch_stock.qty — the race backstop behind the app-level
-- FOR UPDATE guards (_decrement_source_batch / _adjust_branch_stock).
--
-- SQLite can't ALTER-add a CHECK to an existing column, so each table is
-- rebuilt in place (create-copy-drop-rename). Fresh installs get the CHECKs
-- directly from the desktop bundle's CREATE TABLE bodies; existing DBs run
-- THIS script via sqlite/runner.py.
--
-- PRAGMA foreign_keys toggling is safe here: runner.py executes each script
-- via executescript (autocommit), so the pragma takes effect; child rows are
-- carried over verbatim before the parent drop, so re-enabling never trips.

PRAGMA foreign_keys = OFF;

CREATE TABLE stock_batches_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    randomid     TEXT NOT NULL,
    qty          INTEGER NOT NULL DEFAULT 0 CONSTRAINT ck_stock_batches_qty_nonneg CHECK (qty >= 0),  -- ×10000
    expire       TEXT,
    cost         INTEGER NOT NULL DEFAULT 0,                     -- ×10000
    vat          INTEGER NOT NULL DEFAULT 0,                     -- rate ×100
    price        INTEGER NOT NULL DEFAULT 0,                     -- ×10000
    oldstock     INTEGER NOT NULL DEFAULT 0,                     -- ×10000
    typee        TEXT NOT NULL DEFAULT 'purchase' CHECK (typee IN ('purchase','sale','return','count','transfer_in','transfer_out','opening','correction')),
    vatvalue     INTEGER DEFAULT 0,                              -- ×100
    totalwithvat INTEGER DEFAULT 0,                              -- ×100
    writer       TEXT DEFAULT '',
    classy       TEXT DEFAULT '',
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, drug_id, randomid)
);
INSERT INTO stock_batches_new SELECT * FROM stock_batches;
DROP TABLE stock_batches;
ALTER TABLE stock_batches_new RENAME TO stock_batches;
CREATE INDEX ix_stock_batches_expiry ON stock_batches (branch_id, drug_id, expire);

CREATE TABLE branch_stock_new (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    drug_id   INTEGER NOT NULL REFERENCES drugs(id),
    qty       INTEGER NOT NULL DEFAULT 0 CONSTRAINT ck_branch_stock_qty_nonneg CHECK (qty >= 0),  -- ×10000
    minimum   INTEGER NOT NULL DEFAULT 0,
    silsilaid TEXT DEFAULT '',
    classy    TEXT DEFAULT '',
    price     INTEGER DEFAULT 0,                                 -- ×10000
    barcode   TEXT DEFAULT '',
    lastedit  TEXT,
    PRIMARY KEY (branch_id, drug_id)
);
INSERT INTO branch_stock_new SELECT * FROM branch_stock;
DROP TABLE branch_stock;
ALTER TABLE branch_stock_new RENAME TO branch_stock;

PRAGMA foreign_keys = ON;
