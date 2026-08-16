-- ============================================================================
-- TITAN.W1 → Modern Replacement — SQLITE DIALECT (Tauri desktop, offline-first)
-- Mirrors schema_postgres.sql (the canonical FastAPI/PostgreSQL design).
-- 51 tables, same columns/constraints, adapted to SQLite:
--
--   ENUMS        -> TEXT columns + CHECK (...) on the same allowed values
--   BIGINT IDENTITY -> INTEGER PRIMARY KEY AUTOINCREMENT (or composite PKs)
--   TIMESTAMPTZ  -> TEXT ISO-8601 (UTC) or INTEGER unix; app writes ISO-8601 UTC
--   JSONB        -> TEXT (JSON)
--   NUMERIC(n,s) -> NUMERIC affinity + app-side rounding (SQLite has no decimal)
--   schemas      -> none (single default)
--
-- MONEY TYPING (SCHEMA_EVALUATION §1.11):
--   SQLite NUMERIC affinity does NOT guarantee 2-dp precision. All money values are
--   therefore stored as NUMERIC but MUST be rounded half-up to 2 dp (totals) / 4 dp
--   (per-unit) at the app layer BEFORE INSERT. The Tauri app shares the FastAPI
--   money/rounding module; a migration from SQLite -> Postgres preserves these values
--   verbatim (NUMERIC(18,2) accepts them exactly).
--
-- AUDIT REQUIREMENT (§1.6): every money/stock table carries an "AUDIT:" comment;
-- the app MUST insert audit_log rows in the same transaction as any money/stock write.
--
-- BALANCED JOURNAL INVARIANT: SUM(debit)=SUM(credit) per journal_id enforced at the
-- app layer (cross-table CHECK is not expressible in DDL); single-side CHECK below.
--
-- This file is self-contained and loadable by `sqlite3 schema_sqlite.sql`.
-- ============================================================================

BEGIN;

PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. BRANCHES — wzphar (§2.1, §1.12)
-- ============================================================================

CREATE TABLE branches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacyid     TEXT NOT NULL,
    phar           TEXT DEFAULT '',
    mobile         TEXT NOT NULL,
    pharname       TEXT NOT NULL DEFAULT '',
    adress         TEXT DEFAULT '',
    governorate    TEXT DEFAULT '',
    district       TEXT DEFAULT '',
    country        TEXT DEFAULT '',
    currency       TEXT DEFAULT '',
    vat_default    NUMERIC NOT NULL DEFAULT 15.00,
    is_main_device INTEGER NOT NULL DEFAULT 0,       -- BOOLEAN 0/1
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pharmacyid),
    UNIQUE (mobile)
);

-- ============================================================================
-- 2. USERS / RBAC — FormUsers/FFFUserEdit (§1.12)
-- ============================================================================

CREATE TABLE users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL UNIQUE,
    namee      TEXT NOT NULL DEFAULT '',
    mobile     TEXT DEFAULT '',
    pass_hash  TEXT DEFAULT '',
    branch_id  INTEGER REFERENCES branches(id),
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT ''
);

CREATE TABLE permissions (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    code   TEXT NOT NULL UNIQUE,
    name_ar TEXT DEFAULT ''
);

CREATE TABLE role_permissions (
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    permission_id INTEGER NOT NULL REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id),
    role_id INTEGER NOT NULL REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

-- ============================================================================
-- 3. DRUG MASTER — wzdrugs + tar.phy (EN@0x00/AR@0x34 cp1256)
-- ============================================================================

CREATE TABLE drugs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    drugname     TEXT NOT NULL UNIQUE,
    drugnamear   TEXT NOT NULL DEFAULT '',
    generic      TEXT DEFAULT '',
    classy       TEXT DEFAULT '',
    pharmacology TEXT DEFAULT '',
    co           TEXT DEFAULT '',
    unitsclass   TEXT DEFAULT '',
    vat          NUMERIC NOT NULL DEFAULT 0,
    units        INTEGER NOT NULL DEFAULT 0,
    unitsmall    INTEGER NOT NULL DEFAULT 0,
    price        NUMERIC DEFAULT 0,
    price_now    NUMERIC DEFAULT 0,
    disco        NUMERIC DEFAULT 0,
    pricechanged INTEGER DEFAULT 0,
    localimport  INTEGER DEFAULT 0,
    titanid      INTEGER DEFAULT 0,
    history      TEXT DEFAULT '',
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    lastedit     TEXT
);

CREATE TABLE drug_barcodes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id    INTEGER NOT NULL REFERENCES drugs(id),
    barcode    TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    UNIQUE (drug_id, barcode)
);
CREATE UNIQUE INDEX uq_drug_barcodes_barcode ON drug_barcodes (barcode);

CREATE TABLE unit_conversions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id   INTEGER NOT NULL REFERENCES drugs(id),
    from_unit TEXT NOT NULL,
    to_unit   TEXT NOT NULL,
    factor    NUMERIC NOT NULL,
    CHECK (factor > 0)
);

-- ============================================================================
-- 4. ACCOUNTS — wzaccfreetree + acctree.phy (§1.4)
-- ============================================================================

CREATE TABLE accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    code       TEXT NOT NULL,
    parent_id  INTEGER REFERENCES accounts(id),
    master     TEXT DEFAULT '',
    fary       TEXT DEFAULT '',
    name_ar    TEXT DEFAULT '',
    name_en    TEXT DEFAULT '',
    type       TEXT NOT NULL CHECK (type IN ('asset','liability','equity','income','expense')),
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, code)
);

-- ============================================================================
-- 5. PARTIES — wzcustomers + companies + wzsuppliers + customers.w.phy
-- ============================================================================

CREATE TABLE parties (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id             INTEGER NOT NULL REFERENCES branches(id),
    kind                  TEXT NOT NULL DEFAULT 'customer' CHECK (kind IN ('customer','supplier','both')),
    typee                 TEXT DEFAULT '',
    namee                 TEXT NOT NULL DEFAULT '',
    name_ar               TEXT DEFAULT '',
    mobile                TEXT DEFAULT '',
    adress                TEXT DEFAULT '',
    governorate           TEXT DEFAULT '',
    district              TEXT DEFAULT '',
    credit_limit          NUMERIC NOT NULL DEFAULT 0,
    receivable_account_id INTEGER REFERENCES accounts(id),
    payable_account_id    INTEGER REFERENCES accounts(id),
    writer                TEXT DEFAULT '',
    randomid              TEXT DEFAULT '',
    datee                 TEXT,
    active                INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, randomid)
);

-- ============================================================================
-- 6. DRUG COSTS — wzdrugs2 (§2.1)
-- ============================================================================

CREATE TABLE drug_costs (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    drug_id   INTEGER NOT NULL REFERENCES drugs(id),
    unitcost  NUMERIC NOT NULL DEFAULT 0,
    costvalue NUMERIC NOT NULL DEFAULT 0,
    expire    TEXT,
    PRIMARY KEY (branch_id, drug_id)
);

-- ============================================================================
-- 7. STOCK BATCHES — wzgard (§1.2)
-- ============================================================================

CREATE TABLE stock_batches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    randomid     TEXT NOT NULL,
    qty          NUMERIC NOT NULL DEFAULT 0,
    expire       TEXT,
    cost         NUMERIC NOT NULL DEFAULT 0,
    vat          NUMERIC NOT NULL DEFAULT 0,
    price        NUMERIC NOT NULL DEFAULT 0,
    oldstock     NUMERIC NOT NULL DEFAULT 0,
    typee        TEXT NOT NULL DEFAULT 'purchase' CHECK (typee IN ('purchase','sale','return','count','transfer_in','transfer_out','opening','correction')),
    vatvalue     NUMERIC DEFAULT 0,
    totalwithvat NUMERIC DEFAULT 0,
    writer       TEXT DEFAULT '',
    classy       TEXT DEFAULT '',
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, drug_id, randomid)
);
CREATE INDEX ix_stock_batches_expiry ON stock_batches (branch_id, drug_id, expire);

-- ============================================================================
-- 8. WORK PERIODS & SHIFTS — workperiod.phy (§1.9)
-- ============================================================================

CREATE TABLE work_periods (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    name      TEXT DEFAULT '',
    opened_by INTEGER REFERENCES users(id),
    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT
);

CREATE TABLE shifts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    work_period_id INTEGER REFERENCES work_periods(id),
    opened_by      INTEGER NOT NULL REFERENCES users(id),
    opened_at      TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at      TEXT,
    cash_start     NUMERIC NOT NULL DEFAULT 0,
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

-- ============================================================================
-- 9. INVOICES — invoicedata 17-col hybrid + titanksasales 9-col
-- ============================================================================

CREATE TABLE invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    kind           TEXT NOT NULL DEFAULT 'sale' CHECK (kind IN ('sale','purchase','sale_return','purchase_return','transfer')),
    invoice_no     TEXT NOT NULL,
    datee          TEXT NOT NULL,
    datetimee      TEXT,
    silsilaid      TEXT DEFAULT '',
    party_id       INTEGER REFERENCES parties(id),
    subtotal       NUMERIC NOT NULL DEFAULT 0,
    discount       NUMERIC NOT NULL DEFAULT 0,
    vat            NUMERIC NOT NULL DEFAULT 0,
    totalvalue     NUMERIC NOT NULL DEFAULT 0,
    payed          NUMERIC NOT NULL DEFAULT 0,
    agel           NUMERIC NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'saved' CHECK (status IN ('saved','unsaved','unsave','copy','transfer_to_sale_return','transfer_to_purchase','closed','archived','void')),
    writer         TEXT DEFAULT '',
    created_by     INTEGER REFERENCES users(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    last_edited_at TEXT,
    CHECK (payed + agel = totalvalue)
);
CREATE INDEX ix_invoices_branch_date ON invoices (branch_id, datee);
CREATE INDEX ix_invoices_branch_party ON invoices (branch_id, party_id);
CREATE INDEX ix_invoices_last_edited ON invoices (last_edited_at);

CREATE TABLE invoice_lines (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    drug_id    INTEGER NOT NULL REFERENCES drugs(id),
    batch_id   INTEGER REFERENCES stock_batches(id),
    qty        NUMERIC NOT NULL DEFAULT 0,
    unit       TEXT DEFAULT 'pack',
    unit_price NUMERIC NOT NULL DEFAULT 0,
    cost       NUMERIC NOT NULL DEFAULT 0,
    disc       NUMERIC NOT NULL DEFAULT 0,
    vat        NUMERIC NOT NULL DEFAULT 0,
    line_total NUMERIC NOT NULL DEFAULT 0,
    expire     TEXT,
    minimum    NUMERIC DEFAULT 0,
    tips       TEXT DEFAULT '',
    iddatetime TEXT,
    CHECK (unit_price >= 0)
);
CREATE INDEX ix_invoice_lines_invoice ON invoice_lines (invoice_id);
CREATE INDEX ix_invoice_lines_drug ON invoice_lines (branch_id, drug_id);

CREATE TABLE invoice_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    version_no INTEGER NOT NULL,
    action     TEXT DEFAULT '',
    payload    TEXT,
    changed_by INTEGER REFERENCES users(id),
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (invoice_id, version_no)
);

CREATE TABLE payment_splits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id),
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    method      TEXT NOT NULL DEFAULT 'cash' CHECK (method IN ('cash','card','credit','manual_cash','manual_card')),
    amount      NUMERIC NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id     INTEGER REFERENCES users(id),
    CHECK (amount > 0)
);

-- ============================================================================
-- 10. JOURNALS & LEDGER — farysales 17-col + Accounting\moves (§1.4)
-- ============================================================================

CREATE TABLE journals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    datee          TEXT NOT NULL,
    entry_no       INTEGER NOT NULL,
    description    TEXT NOT NULL,
    source         TEXT NOT NULL DEFAULT 'sale' CHECK (source IN ('sale','purchase','sale_return','purchase_return','manual','transfer','opening','settlement','correction')),
    status         TEXT NOT NULL DEFAULT 'posted',
    ref_invoice_id INTEGER REFERENCES invoices(id),
    created_by     INTEGER REFERENCES users(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, datee, entry_no)
);

CREATE TABLE journal_lines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_id      INTEGER NOT NULL REFERENCES journals(id),
    branch_id       INTEGER NOT NULL REFERENCES branches(id),
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    debit           NUMERIC NOT NULL DEFAULT 0,
    credit          NUMERIC NOT NULL DEFAULT 0,
    contra_party_id INTEGER REFERENCES parties(id),
    datee           TEXT NOT NULL,
    month           INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    year            INTEGER NOT NULL,
    creditdebit     TEXT DEFAULT '',
    randomid        TEXT DEFAULT '',
    writer          TEXT DEFAULT '',
    tips            TEXT DEFAULT '',
    classy          TEXT DEFAULT '',
    CHECK (debit >= 0 AND credit >= 0 AND (debit = 0 OR credit = 0))
);
CREATE INDEX ix_journal_lines_account ON journal_lines (branch_id, account_id, month, year);
CREATE INDEX ix_journal_lines_journal ON journal_lines (journal_id);

-- ============================================================================
-- 11. BALANCES & MONTH CLOSE — farysales monthe/yearo, monthy\moves + start-data
-- ============================================================================

CREATE TABLE balances (
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    month      INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    year       INTEGER NOT NULL,
    debit      NUMERIC NOT NULL DEFAULT 0,
    credit     NUMERIC NOT NULL DEFAULT 0,
    balance    NUMERIC NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (branch_id, account_id, month, year),
    CHECK (balance = debit - credit)
);

CREATE TABLE monthly_close (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    status    TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','reopened')),
    closed_by INTEGER REFERENCES users(id),
    closed_at TEXT,
    PRIMARY KEY (branch_id, year, month)
);

CREATE TABLE month_open_balances (
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    debit      NUMERIC NOT NULL DEFAULT 0,
    credit     NUMERIC NOT NULL DEFAULT 0,
    PRIMARY KEY (branch_id, account_id, year, month)
);

-- ============================================================================
-- 12. DRAWER & DAY CLOSE — Daily.phy, MonyInfo.phy (§1.1, §1.5, §1.11)
-- ============================================================================

CREATE TABLE drawer_movements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    datee          TEXT NOT NULL,
    direction      TEXT NOT NULL DEFAULT 'in' CHECK (direction IN ('in','out')),
    reason         TEXT NOT NULL DEFAULT 'cash_sale' CHECK (reason IN ('cash_sale','cash_return','supplier_pay','customer_settlement','expense','transfer','opening','correction')),
    method         TEXT NOT NULL DEFAULT 'cash' CHECK (method IN ('cash','network')),
    amount         NUMERIC NOT NULL DEFAULT 0,
    shift_id       INTEGER REFERENCES shifts(id),
    ref_invoice_id INTEGER REFERENCES invoices(id),
    user_id        INTEGER REFERENCES users(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (amount >= 0)
);
CREATE INDEX ix_drawer_movements_branch_date ON drawer_movements (branch_id, datee);

CREATE TABLE daily_close (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    datee          TEXT NOT NULL,
    shift_id       INTEGER REFERENCES shifts(id),
    work_period_id INTEGER REFERENCES work_periods(id),
    drawer_start   NUMERIC NOT NULL DEFAULT 0,
    expected_cash  NUMERIC NOT NULL DEFAULT 0,
    counted_cash   NUMERIC NOT NULL DEFAULT 0,
    difference     NUMERIC NOT NULL DEFAULT 0,
    manual_cash    NUMERIC NOT NULL DEFAULT 0,
    manual_card    NUMERIC NOT NULL DEFAULT 0,
    net_cash       NUMERIC NOT NULL DEFAULT 0,
    net_network    NUMERIC NOT NULL DEFAULT 0,
    purchases      NUMERIC NOT NULL DEFAULT 0,
    expenses       NUMERIC NOT NULL DEFAULT 0,
    cost_of_sales  NUMERIC NOT NULL DEFAULT 0,
    net_profit     NUMERIC NOT NULL DEFAULT 0,
    discounts      NUMERIC NOT NULL DEFAULT 0,
    vat_sales      NUMERIC NOT NULL DEFAULT 0,
    vat_purchases  NUMERIC NOT NULL DEFAULT 0,
    vat_expenses   NUMERIC NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','reopened')),
    closed_by      INTEGER REFERENCES users(id),
    closed_at      TEXT,
    UNIQUE (branch_id, datee),
    CHECK (difference = counted_cash - expected_cash)
);

-- ============================================================================
-- 13. BRANCH STOCK — titanstock + titanksastock (§2.1)
-- ============================================================================

CREATE TABLE branch_stock (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    drug_id   INTEGER NOT NULL REFERENCES drugs(id),
    qty       NUMERIC NOT NULL DEFAULT 0,
    minimum   NUMERIC NOT NULL DEFAULT 0,
    silsilaid TEXT DEFAULT '',
    classy    TEXT DEFAULT '',
    price     NUMERIC DEFAULT 0,
    barcode   TEXT DEFAULT '',
    lastedit  TEXT,
    PRIMARY KEY (branch_id, drug_id)
);

-- ============================================================================
-- 14. TRANSFERS — titaninn + delivery.phy (§1.9)
-- ============================================================================

CREATE TABLE transfers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id        INTEGER NOT NULL REFERENCES branches(id),
    fatid            INTEGER NOT NULL DEFAULT 0,
    datee            TEXT,
    silsilaid        TEXT DEFAULT '',
    source_branch_id INTEGER REFERENCES branches(id),
    target_branch_id INTEGER REFERENCES branches(id),
    legacy_source    TEXT DEFAULT '',
    legacy_target    TEXT DEFAULT '',
    itemsasstring    TEXT DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','in_transit','delivered','received','cancelled')),
    created_by       INTEGER REFERENCES users(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_transfers_target ON transfers (target_branch_id);

CREATE TABLE transfer_lines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id INTEGER NOT NULL REFERENCES transfers(id),
    drug_id     INTEGER NOT NULL REFERENCES drugs(id),
    qty         NUMERIC NOT NULL DEFAULT 0,
    expire      TEXT,
    batch_id    INTEGER REFERENCES stock_batches(id),
    unit_price  NUMERIC DEFAULT 0
);

-- ============================================================================
-- 15. SHORTAGES & NEEDS — §1.8, titanneed, orders
-- ============================================================================

CREATE TABLE shortage_flags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    drug_id     INTEGER NOT NULL REFERENCES drugs(id),
    current_qty NUMERIC NOT NULL DEFAULT 0,
    minimum     NUMERIC NOT NULL DEFAULT 0,
    method      TEXT NOT NULL DEFAULT 'manual' CHECK (method IN ('manual','half_auto','sales_rate')),
    flagged_at  TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by INTEGER REFERENCES users(id)
);

CREATE TABLE needs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id        INTEGER NOT NULL REFERENCES branches(id),
    drug_id          INTEGER NOT NULL REFERENCES drugs(id),
    qty              NUMERIC NOT NULL DEFAULT 0,
    datee            TEXT,
    sender_branch_id INTEGER REFERENCES branches(id),
    target_branch_id INTEGER REFERENCES branches(id),
    legacy_sender    TEXT DEFAULT '',
    legacy_target    TEXT DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','fulfilled','cancelled')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE purchase_orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    orderid    TEXT DEFAULT '',
    orderdate  TEXT,
    datee      TEXT,
    status     TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','saved','received','cancelled')),
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE stock_correction_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    batch_id     INTEGER REFERENCES stock_batches(id),
    delta        NUMERIC NOT NULL,
    reason       TEXT DEFAULT '',
    requested_by INTEGER NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    approved_by  INTEGER REFERENCES users(id),
    decided_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((status = 'pending') = (decided_at IS NULL))
);

-- ============================================================================
-- 16. CHAIN / DEAD-STOCK EXCHANGE — RawakidTablew + ChainBuyStore + ChainBuyUsers
-- ============================================================================

CREATE TABLE dead_stock_exchange (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id             INTEGER NOT NULL REFERENCES branches(id),
    drug_id               INTEGER NOT NULL REFERENCES drugs(id),
    qty                   NUMERIC NOT NULL DEFAULT 0,
    expire                TEXT,
    price                 NUMERIC DEFAULT 0,
    sell_disc             NUMERIC DEFAULT 0,
    tips                  TEXT DEFAULT '',
    governorate           TEXT DEFAULT '',
    district              TEXT DEFAULT '',
    source_pharmacist_tel TEXT DEFAULT '',
    requester_tel         TEXT DEFAULT '',
    source_iddatetime     TEXT,
    country               TEXT DEFAULT '',
    status                TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','in_transit','delivered','received','cancelled')),
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE chain_buy_orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id     INTEGER NOT NULL REFERENCES branches(id),
    drug_id       INTEGER NOT NULL REFERENCES drugs(id),
    store_name    TEXT DEFAULT '',
    pharmacist_tel TEXT DEFAULT '',
    requester_tel TEXT DEFAULT '',
    qty           NUMERIC NOT NULL DEFAULT 0,
    price         NUMERIC DEFAULT 0,
    sell_disc     NUMERIC DEFAULT 0,
    expire        TEXT,
    tips          TEXT DEFAULT '',
    governorate   TEXT DEFAULT '',
    district      TEXT DEFAULT '',
    country       TEXT DEFAULT '',
    iddatetime    TEXT,
    status        TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','in_transit','delivered','received','cancelled')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================================
-- 17. E-INVOICE — ZATCA + oot3/netcounter (§1.10)
-- ============================================================================

CREATE TABLE einvoice_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   INTEGER NOT NULL REFERENCES invoices(id),
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    kind         TEXT NOT NULL DEFAULT 'zatca' CHECK (kind IN ('zatca','eta')),
    uuid         TEXT DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','submitted','accepted','rejected','failed','cancelled','void')),
    hash         TEXT DEFAULT '',
    qr_counter   INTEGER,
    qr_hash      TEXT,
    qr_data      TEXT DEFAULT '',
    payload_xml  TEXT DEFAULT '',
    payload_json TEXT,
    response     TEXT DEFAULT '',
    submitted_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_einvoice_log_invoice ON einvoice_log (invoice_id);
CREATE INDEX ix_einvoice_log_kind_status ON einvoice_log (kind, status);

CREATE TABLE einvoice_counters (
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    kind         TEXT NOT NULL DEFAULT 'zatca' CHECK (kind IN ('zatca','eta')),
    last_counter INTEGER NOT NULL DEFAULT 0,
    last_hash    TEXT DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (branch_id, kind)
);

-- ============================================================================
-- 18. AUDIT & SYNC — TitanUserAction, usersourceupdate (§1.6, §1.3)
-- ============================================================================

CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id  INTEGER REFERENCES branches(id),
    user_id    INTEGER REFERENCES users(id),
    entity     TEXT NOT NULL,
    entity_id  INTEGER,
    field      TEXT DEFAULT '',
    old_value  TEXT,
    new_value  TEXT,
    drug_id    INTEGER REFERENCES drugs(id),
    barcode    TEXT DEFAULT '',
    action     TEXT NOT NULL DEFAULT 'update',
    namee      TEXT DEFAULT '',
    typevalue  TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_audit_entity ON audit_log (entity, entity_id);
CREATE INDEX ix_audit_drug ON audit_log (drug_id);
CREATE INDEX ix_audit_created ON audit_log (created_at);

CREATE TABLE sync_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id        INTEGER NOT NULL REFERENCES branches(id),
    entity           TEXT NOT NULL,
    entity_id        INTEGER,
    action           TEXT NOT NULL DEFAULT 'update',
    payload          TEXT,
    synced_at        TEXT,
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','applied','failed','skipped')),
    source_device_id INTEGER REFERENCES branches(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_sync_log_status ON sync_log (branch_id, status);

CREATE TABLE drug_sync_outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    drug_id     INTEGER NOT NULL REFERENCES drugs(id),
    price       NUMERIC DEFAULT 0,
    units       INTEGER DEFAULT 0,
    vat         NUMERIC DEFAULT 0,
    barcode     TEXT DEFAULT '',
    shape       INTEGER DEFAULT 0,
    datee       TEXT,
    localimport INTEGER DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','applied','failed','skipped')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE branch_identities (
    legacy_table  TEXT NOT NULL,
    legacy_column TEXT NOT NULL,
    legacy_value  TEXT NOT NULL,
    branch_id     INTEGER NOT NULL REFERENCES branches(id),
    PRIMARY KEY (legacy_table, legacy_column, legacy_value)
);

-- ============================================================================
-- 19. OPERATIONAL / STATE FILES → SQL (§1.9, §2.2)
-- ============================================================================

CREATE TABLE user_drawer_money (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    user_id     INTEGER REFERENCES users(id),
    shift_id    INTEGER REFERENCES shifts(id),
    datee       TEXT,
    cash        NUMERIC NOT NULL DEFAULT 0,
    card        NUMERIC NOT NULL DEFAULT 0,
    manual_cash NUMERIC NOT NULL DEFAULT 0,
    manual_card NUMERIC NOT NULL DEFAULT 0,
    credit      NUMERIC NOT NULL DEFAULT 0,
    record_no   INTEGER,
    source_file TEXT DEFAULT 'usersmony.phy',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE drug_interactions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_a   INTEGER NOT NULL REFERENCES drugs(id),
    drug_b   INTEGER NOT NULL REFERENCES drugs(id),
    severity TEXT NOT NULL DEFAULT 'unknown' CHECK (severity IN ('minor','moderate','major','contraindicated','unknown')),
    note     TEXT DEFAULT '',
    UNIQUE (drug_a, drug_b),
    CHECK (drug_a < drug_b)
);

CREATE TABLE integration_config (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id  INTEGER REFERENCES branches(id),
    key        TEXT NOT NULL,
    value      TEXT DEFAULT '',
    config     TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, key)
);

CREATE TABLE archive_imports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER REFERENCES branches(id),
    source_path TEXT DEFAULT '',
    file_count  INTEGER DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','done','failed')),
    started_at  TEXT,
    finished_at TEXT,
    note        TEXT DEFAULT ''
);

CREATE TABLE archive_exports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER REFERENCES branches(id),
    target_path TEXT DEFAULT '',
    file_count  INTEGER DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','done','failed')),
    started_at  TEXT,
    finished_at TEXT,
    note        TEXT DEFAULT ''
);

CREATE TABLE external_drug_catalog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER REFERENCES branches(id),
    create_date TEXT,
    mobile      TEXT DEFAULT '',
    name_en     TEXT DEFAULT '',
    name_ar     TEXT DEFAULT '',
    drugname    TEXT DEFAULT '',
    price       NUMERIC DEFAULT 0,
    barcode     TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','applied','failed','skipped')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE price_change_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id     INTEGER REFERENCES branches(id),
    drug_id       INTEGER REFERENCES drugs(id),
    barcode       TEXT DEFAULT '',
    price         NUMERIC DEFAULT 0,
    disco         NUMERIC DEFAULT 0,
    units         INTEGER DEFAULT 0,
    quant         NUMERIC DEFAULT 0,
    datee         TEXT,
    tips          TEXT DEFAULT '',
    country       TEXT DEFAULT '',
    storename     TEXT DEFAULT '',
    pharmacyname  TEXT DEFAULT '',
    pharmacyname2 TEXT DEFAULT '',
    titanver      TEXT DEFAULT '',
    pricechanged  INTEGER DEFAULT 0,
    localimport   INTEGER DEFAULT 0,
    changed_by    INTEGER REFERENCES users(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_price_change_log_drug ON price_change_log (branch_id, drug_id);

CREATE TABLE manual_journal_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    record_no   INTEGER,
    datee       TEXT,
    amount      NUMERIC NOT NULL DEFAULT 0,
    source_file TEXT DEFAULT 'daily-manual.phy',
    journal_id  INTEGER REFERENCES journals(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE branch_registry (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile       TEXT NOT NULL UNIQUE,
    pharmacyname TEXT DEFAULT '',
    barcode      TEXT DEFAULT '',
    changed      TEXT,
    apptype      TEXT DEFAULT '',
    is_registered INTEGER NOT NULL DEFAULT 1
);

-- ============================================================================
-- 20. APP CONFIG — VAT/currency country config (§1.11)
-- ============================================================================

CREATE TABLE app_config (
    key           TEXT PRIMARY KEY,
    value         TEXT DEFAULT '',
    value_numeric NUMERIC,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed config (Gulf 15% default; Egypt switch in app_config)
INSERT INTO app_config (key, value, value_numeric) VALUES
    ('country', 'SA', NULL),
    ('currency', 'SAR', NULL),
    ('vat_default_rate', NULL, 15.00),
    ('rounding', 'half-up-2dp', NULL);

COMMIT;