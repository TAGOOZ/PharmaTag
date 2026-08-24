-- ============================================================================
-- PharmaTag — SQLite offline twin (desktop bundle, single self-contained file)
--
-- The CANONICAL SQLite twin is the versioned `server/sqlite/migrations/*.sql`
-- set (applied by server/sqlite/runner.py). This file merges rev 001 (core
-- schema), rev 002 (core seeds) and rev 005 (drug price levels + drugs.manage)
-- into ONE script the Tauri desktop bundles
-- (`apps/desktop/src/resources/schema_sqlite.sql`, Vite `?raw`) and applies on
-- first boot (`apps/desktop/src/db.ts` bootstrapSchema, guarded on the
-- `branches` table). `server/scripts/parity_check.py` asserts this file == the
-- merged migrations twin in CI, so the bundle cannot drift from the API.
--
-- MONEY TYPING (plan/01 §4.2): PG NUMERIC(n,s) <-> SQLite INTEGER storing
-- value × 10^s, so a double can never be inserted:
--   NUMERIC(18,2) <-> INTEGER ×100      NUMERIC(18,4) <-> INTEGER ×10000
--   NUMERIC(5,2)  <-> INTEGER ×100      NUMERIC(18,6) <-> INTEGER ×1000000
-- Timestamps: TEXT ISO-8601 UTC. JSONB: TEXT. Enums: TEXT + CHECK.
-- Booleans: INTEGER 0/1.
--
-- A08: only core [C] tables + the plugin host ship here; plugin tables live in
-- per-plugin ATTACHed SQLite files (p_<slug>_ prefix fallback).
--
-- The S0.3 drug-master rows are NOT embedded here — the desktop seeds them
-- separately (`apps/desktop/src/drugs.ts` seedDrugs, mirroring alembic rev 003
-- / `server/sqlite/migrations/003_drug_seeds.sql` in INTEGER minor units) so
-- the offline catalog stays identical to what the API serves.
-- ============================================================================

BEGIN;

PRAGMA foreign_keys = ON;

-- 1. branches (wzphar)
CREATE TABLE branches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacyid          TEXT NOT NULL,
    phar                TEXT DEFAULT '',
    mobile              TEXT NOT NULL,
    pharname            TEXT NOT NULL DEFAULT '',
    adress              TEXT DEFAULT '',
    governorate         TEXT DEFAULT '',
    district            TEXT DEFAULT '',
    country             TEXT DEFAULT '',
    currency            TEXT DEFAULT '',
    vat_default         INTEGER NOT NULL DEFAULT 1400,          -- 14.00 ×100
    vat_inclusive_prices INTEGER NOT NULL DEFAULT 1,
    is_main_device      INTEGER NOT NULL DEFAULT 0,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pharmacyid),
    UNIQUE (mobile)
);

-- 2. users / rbac
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    namee           TEXT NOT NULL DEFAULT '',
    mobile          TEXT DEFAULT '',
    pass_hash       TEXT DEFAULT '',
    permission_level INTEGER NOT NULL DEFAULT 1 CHECK (permission_level BETWEEN 1 AND 9),
    branch_id       INTEGER REFERENCES branches(id),
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT ''
);

CREATE TABLE permissions (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code    TEXT NOT NULL UNIQUE,
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

-- 3. drug master
CREATE TABLE drugs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    drugname     TEXT NOT NULL,
    drugnamear   TEXT NOT NULL DEFAULT '',
    generic      TEXT DEFAULT '',
    classy       TEXT DEFAULT '',
    pharmacology TEXT DEFAULT '',
    co           TEXT DEFAULT '',
    unitsclass   TEXT DEFAULT '',
    tax_type     TEXT NOT NULL DEFAULT 'exempt' CHECK (tax_type IN ('exempt','5%','14%')),
    vat          INTEGER NOT NULL DEFAULT 0,                    -- rate ×100
    units        INTEGER NOT NULL DEFAULT 0,
    unitsmall    INTEGER NOT NULL DEFAULT 0,
    price        INTEGER DEFAULT 0,                             -- ×10000
    price_now    INTEGER DEFAULT 0,
    disco        INTEGER DEFAULT 0,                             -- rate ×100
    pricechanged INTEGER DEFAULT 0,
    localimport  INTEGER DEFAULT 0,
    titanid      INTEGER DEFAULT 0,
    history      TEXT DEFAULT '',
    active       INTEGER NOT NULL DEFAULT 1,
    egs_code     TEXT,                                          -- ETA EGS code (#30; nullable until registered)
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    lastedit     TEXT
);
CREATE UNIQUE INDEX uq_drugs_drugname ON drugs (drugname) WHERE drugname <> '';

CREATE TABLE drug_barcodes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id    INTEGER NOT NULL REFERENCES drugs(id),
    barcode    TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    UNIQUE (drug_id, barcode)
);
CREATE UNIQUE INDEX uq_drug_barcodes_barcode ON drug_barcodes (barcode) WHERE barcode <> '';

CREATE TABLE unit_conversions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id   INTEGER NOT NULL REFERENCES drugs(id),
    from_unit TEXT NOT NULL,
    to_unit   TEXT NOT NULL,
    factor    INTEGER NOT NULL,                                  -- ×1000000
    CHECK (factor > 0)
);

-- 4. accounts
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

-- 5. parties
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
    credit_limit          INTEGER NOT NULL DEFAULT 0,            -- ×100
    receivable_account_id INTEGER REFERENCES accounts(id),
    payable_account_id    INTEGER REFERENCES accounts(id),
    writer                TEXT DEFAULT '',
    randomid              TEXT DEFAULT '',
    datee                 TEXT,
    active                INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, randomid)
);

-- 6. drug_costs (global — correction §1.3#2)
CREATE TABLE drug_costs (
    drug_id   INTEGER PRIMARY KEY REFERENCES drugs(id),
    unitcost  INTEGER NOT NULL DEFAULT 0,                        -- ×10000
    costvalue INTEGER NOT NULL DEFAULT 0,
    expire    TEXT
);

-- 7. stock_batches
CREATE TABLE stock_batches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    randomid     TEXT NOT NULL,
    qty          INTEGER NOT NULL DEFAULT 0,                     -- ×10000
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
CREATE INDEX ix_stock_batches_expiry ON stock_batches (branch_id, drug_id, expire);

-- 8. work periods & shifts
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
    cash_start     INTEGER NOT NULL DEFAULT 0,                   -- ×100
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

-- 9. invoices + lines + versions + splits
CREATE TABLE invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    kind           TEXT NOT NULL DEFAULT 'sale' CHECK (kind IN ('sale','purchase','sale_return','purchase_return','transfer')),
    invoice_no     TEXT NOT NULL,
    datee          TEXT NOT NULL,
    datetimee      TEXT,
    silsilaid      TEXT DEFAULT '',
    party_id       INTEGER REFERENCES parties(id),
    ref_invoice_id INTEGER REFERENCES invoices(id),
    subtotal       INTEGER NOT NULL DEFAULT 0,                   -- ×100
    discount       INTEGER NOT NULL DEFAULT 0,
    vat            INTEGER NOT NULL DEFAULT 0,
    totalvalue     INTEGER NOT NULL DEFAULT 0,
    payed          INTEGER NOT NULL DEFAULT 0,
    agel           INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'saved' CHECK (status IN ('saved','unsaved','unsave','copy','transfer_to_sale_return','transfer_to_purchase','closed','archived','void')),
    writer         TEXT DEFAULT '',
    created_by     INTEGER REFERENCES users(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    last_edited_at TEXT,
    UNIQUE (branch_id, invoice_no),
    CHECK (payed + agel = totalvalue)
);
CREATE INDEX ix_invoices_branch_date ON invoices (branch_id, datee);
CREATE INDEX ix_invoices_branch_party ON invoices (branch_id, party_id);
CREATE INDEX ix_invoices_last_edited ON invoices (last_edited_at);
CREATE INDEX ix_invoices_ref_invoice ON invoices (ref_invoice_id);

CREATE TABLE invoice_lines (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    drug_id    INTEGER NOT NULL REFERENCES drugs(id),
    batch_id   INTEGER REFERENCES stock_batches(id),
    ref_invoice_line_id INTEGER REFERENCES invoice_lines(id),
    qty        INTEGER NOT NULL DEFAULT 0,                       -- ×10000
    unit       TEXT DEFAULT 'pack',
    unit_price INTEGER NOT NULL DEFAULT 0,                       -- ×10000
    cost       INTEGER NOT NULL DEFAULT 0,                       -- ×10000
    disc       INTEGER NOT NULL DEFAULT 0,                       -- rate ×100
    tax_type   TEXT NOT NULL DEFAULT 'exempt' CHECK (tax_type IN ('exempt','5%','14%')),
    vat        INTEGER NOT NULL DEFAULT 0,                       -- rate ×100
    vat_amount INTEGER NOT NULL DEFAULT 0,                       -- ×100
    line_total INTEGER NOT NULL DEFAULT 0,                       -- ×100
    expire     TEXT,
    minimum    INTEGER DEFAULT 0,                                -- ×10000
    tips       TEXT DEFAULT '',
    iddatetime TEXT,
    CHECK (unit_price >= 0)
);
CREATE INDEX ix_invoice_lines_invoice ON invoice_lines (invoice_id);
CREATE INDEX ix_invoice_lines_ref_line ON invoice_lines (ref_invoice_line_id);
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
    amount      INTEGER NOT NULL DEFAULT 0,                      -- ×100
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id     INTEGER REFERENCES users(id),
    CHECK (amount > 0)
);

-- 10. journals + lines
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
    debit           INTEGER NOT NULL DEFAULT 0,                  -- ×100
    credit          INTEGER NOT NULL DEFAULT 0,
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

-- 11. balances
CREATE TABLE balances (
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    month      INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    year       INTEGER NOT NULL,
    debit      INTEGER NOT NULL DEFAULT 0,                       -- ×100
    credit     INTEGER NOT NULL DEFAULT 0,
    balance    INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (branch_id, account_id, month, year),
    CHECK (balance = debit - credit)
);

-- 12. drawer & day close
CREATE TABLE drawer_movements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(id),
    datee          TEXT NOT NULL,
    direction      TEXT NOT NULL DEFAULT 'in' CHECK (direction IN ('in','out')),
    reason         TEXT NOT NULL DEFAULT 'cash_sale' CHECK (reason IN ('cash_sale','cash_return','supplier_pay','customer_settlement','expense','transfer','opening','correction')),
    method         TEXT NOT NULL DEFAULT 'cash' CHECK (method IN ('cash','network')),
    amount         INTEGER NOT NULL DEFAULT 0,                   -- ×100
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
    drawer_start   INTEGER NOT NULL DEFAULT 0,                   -- ×100
    expected_cash  INTEGER NOT NULL DEFAULT 0,
    counted_cash   INTEGER NOT NULL DEFAULT 0,
    difference     INTEGER NOT NULL DEFAULT 0,
    manual_cash    INTEGER NOT NULL DEFAULT 0,
    manual_card    INTEGER NOT NULL DEFAULT 0,
    net_cash       INTEGER NOT NULL DEFAULT 0,
    net_network    INTEGER NOT NULL DEFAULT 0,
    purchases      INTEGER NOT NULL DEFAULT 0,
    expenses       INTEGER NOT NULL DEFAULT 0,
    cost_of_sales  INTEGER NOT NULL DEFAULT 0,
    net_profit     INTEGER NOT NULL DEFAULT 0,
    discounts      INTEGER NOT NULL DEFAULT 0,
    vat_sales      INTEGER NOT NULL DEFAULT 0,
    vat_purchases  INTEGER NOT NULL DEFAULT 0,
    vat_expenses   INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','reopened')),
    closed_by      INTEGER REFERENCES users(id),
    closed_at      TEXT,
    UNIQUE (branch_id, datee),
    CHECK (difference = counted_cash - expected_cash)
);

-- 13. branch_stock
CREATE TABLE branch_stock (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    drug_id   INTEGER NOT NULL REFERENCES drugs(id),
    qty       INTEGER NOT NULL DEFAULT 0,                        -- ×10000
    minimum   INTEGER NOT NULL DEFAULT 0,
    silsilaid TEXT DEFAULT '',
    classy    TEXT DEFAULT '',
    price     INTEGER DEFAULT 0,                                 -- ×10000
    barcode   TEXT DEFAULT '',
    lastedit  TEXT,
    PRIMARY KEY (branch_id, drug_id)
);

-- 15. shortages + corrections
CREATE TABLE shortage_flags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    drug_id     INTEGER NOT NULL REFERENCES drugs(id),
    current_qty INTEGER NOT NULL DEFAULT 0,                      -- ×10000
    minimum     INTEGER NOT NULL DEFAULT 0,
    method      TEXT NOT NULL DEFAULT 'manual' CHECK (method IN ('manual','half_auto','sales_rate')),
    flagged_at  TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by INTEGER REFERENCES users(id)
);

CREATE TABLE stock_correction_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(id),
    batch_id     INTEGER REFERENCES stock_batches(id),
    delta        INTEGER NOT NULL,                               -- ×10000
    counted      INTEGER,                                        -- ×10000
    reason       TEXT DEFAULT '',
    requested_by INTEGER NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    approved_by  INTEGER REFERENCES users(id),
    rejected_by  INTEGER REFERENCES users(id),
    decided_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((status = 'pending') = (decided_at IS NULL))
);

-- 18. audit + sync (core outbox seam)
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

CREATE TABLE branch_identities (
    legacy_table  TEXT NOT NULL,
    legacy_column TEXT NOT NULL,
    legacy_value  TEXT NOT NULL,
    branch_id     INTEGER NOT NULL REFERENCES branches(id),
    PRIMARY KEY (legacy_table, legacy_column, legacy_value)
);

-- 19. ops/config
CREATE TABLE integration_config (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id  INTEGER REFERENCES branches(id),
    key        TEXT NOT NULL,
    value      TEXT DEFAULT '',
    config     TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, key)
);

CREATE TABLE price_change_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id     INTEGER REFERENCES branches(id),
    drug_id       INTEGER REFERENCES drugs(id),
    barcode       TEXT DEFAULT '',
    price         INTEGER DEFAULT 0,                             -- ×10000
    disco         INTEGER DEFAULT 0,                             -- rate ×100
    units         INTEGER DEFAULT 0,
    quant         INTEGER DEFAULT 0,                             -- ×10000
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
    amount      INTEGER NOT NULL DEFAULT 0,                      -- ×100
    source_file TEXT DEFAULT 'daily-manual.phy',
    journal_id  INTEGER REFERENCES journals(id),
    reverses_entry_id INTEGER REFERENCES manual_journal_entries(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE settlement_vouchers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    voucher_no  INTEGER NOT NULL,
    voucher_type TEXT NOT NULL CHECK (voucher_type IN ('receipt','payment')),
    party_id    INTEGER NOT NULL REFERENCES parties(id),
    datee       TEXT NOT NULL,
    method      TEXT NOT NULL CHECK (method IN ('cash','network')),
    amount      INTEGER NOT NULL DEFAULT 0 CHECK (amount > 0),   -- ×100
    journal_id  INTEGER NOT NULL REFERENCES journals(id),
    description TEXT DEFAULT '',
    reverses_voucher_id INTEGER REFERENCES settlement_vouchers(id),
    created_by  INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, voucher_no)
);

CREATE TABLE app_config (
    key           TEXT PRIMARY KEY,
    value         TEXT DEFAULT '',
    value_numeric INTEGER,                                       -- ×10000
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- plugin host (plan/08 §2.2.1)
CREATE TABLE app_plugins (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    slug               TEXT NOT NULL UNIQUE,
    name_ar            TEXT NOT NULL,
    name_en            TEXT NOT NULL,
    version            TEXT NOT NULL,
    core_requires      TEXT NOT NULL,
    sdk_version        TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'installed' CHECK (status IN ('installed','enabled','disabled','error')),
    license_status     TEXT NOT NULL DEFAULT 'unlicensed' CHECK (license_status IN ('unlicensed','trial','licensed','expired')),
    license_expires_at TEXT,
    installed_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE plugin_dependencies (
    plugin_id   INTEGER NOT NULL REFERENCES app_plugins(id),
    depends_on  TEXT NOT NULL,
    min_version TEXT NOT NULL,
    max_version TEXT,
    PRIMARY KEY (plugin_id, depends_on)
);

CREATE TABLE plugin_branch_grants (
    plugin_id INTEGER NOT NULL REFERENCES app_plugins(id),
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    enabled   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (plugin_id, branch_id)
);

CREATE TABLE plugin_settings (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    plugin_id INTEGER NOT NULL REFERENCES app_plugins(id),
    key       TEXT NOT NULL,
    value     TEXT,
    encrypted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (branch_id, plugin_id, key)
);

-- rev 002 seeds (mirrors sqlite/migrations/002_seeds.sql).
-- app_config: EG/EGP/14% (correction §1.3#5); values in minor units.
INSERT INTO app_config (key, value, value_numeric) VALUES
    ('country', 'EG', NULL),
    ('currency', 'EGP', NULL),
    ('vat_default_rate', NULL, 140000),   -- 14.00 ×10000
    ('rounding', 'half-up-2dp', NULL),
    ('vat_inclusive_prices', 'true', NULL),
    ('plugins_enabled', 'true', NULL);

INSERT INTO branches
    (pharmacyid, phar, mobile, pharname, vat_default, vat_inclusive_prices, is_main_device, is_active)
VALUES
    ('MAIN', 'MAIN', '01000000000', 'Main Pharmacy', 1400, 1, 1, 1);

INSERT INTO permissions (code, name_ar) VALUES
    ('1', 'المبيعات'), ('2', 'المشتريات'), ('3', 'الأصناف والمخزون'),
    ('4', 'العملاء والموردين'), ('5', 'الخزينة والأمانات'), ('6', 'الصلاحيات والمستخدمين'),
    ('7', 'إغلاق اليوم'), ('8', 'تعديل الفواتير'), ('9', 'التقارير'),
    ('sale.create', 'بيع'), ('sale.edit_invoice', 'تعديل فاتورة'),
    ('day.close', 'إغلاق اليوم'), ('stock.adjust', 'تعديل رصيد'),
    ('approvals', 'الموافقات'), ('reports', 'التقارير'), ('users.manage', 'إدارة المستخدمين');

INSERT INTO roles (name) VALUES
    ('admin'), ('pharmacist'), ('cashier'), ('accountant'), ('manager');

-- admin -> all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'admin';
-- manager -> operational subset
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'manager' AND p.code IN
    ('sale.create','sale.edit_invoice','day.close','stock.adjust','approvals','reports');
-- accountant -> reports/approvals
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'accountant' AND p.code IN ('reports','approvals');
-- pharmacist/cashier -> sale.create
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name IN ('pharmacist','cashier') AND p.code = 'sale.create';

INSERT INTO users (username, namee, pass_hash, permission_level, branch_id, active)
VALUES ('admin', 'Administrator', 'changeme', 9, 1, 1);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.username = 'admin' AND r.name = 'admin';

-- default chart of accounts (per-branch template; rev 009 hierarchical legacy tree)
INSERT INTO accounts (branch_id, code, name_ar, name_en, type, is_active) VALUES
    (1, '100',  'اصول',                          'Assets',                'asset', 1),
    (1, '110',  'اصول.متداولة',                  'Current Assets',        'asset', 1),
    (1, '200',  'خصوم',                          'Liabilities',           'liability', 1),
    (1, '210',  'خصوم.متداولة',                  'Current Liabilities',   'liability', 1),
    (1, '220',  'خصوم.ثابتة',                    'Fixed Liabilities',     'liability', 1),
    (1, '300',  'حقوق ملكية',                    'Equity',                'equity', 1),
    (1, '400',  'ايرادات',                       'Revenue',               'income', 1),
    (1, '500',  'مصروفات',                       'Expenses',              'expense', 1),
    (1, '1000', 'اصول.متداولة.خزينة/درج',       'Cash Drawer',           'asset', 1),
    (1, '1001', 'اصول.متداولة.نقدية.شبكة',      'Network Cash',          'asset', 1),
    (1, '1010', 'اصول.متداولة.بنوك',            'Banks',                 'asset', 1),
    (1, '1100', 'اصول.متداولة.عملاء',           'Customers (AR)',        'asset', 1),
    (1, '1110', 'اصول.متداولة.ضريبة.قيمة مضافة','Input VAT',             'asset', 1),
    (1, '1200', 'اصول.متداولة.مخزون',           'Inventory',             'asset', 1),
    (1, '1300', 'اصول.ثابتة',                   'Fixed Assets',          'asset', 1),
    (1, '2000', 'خصوم.متداولة.موردين',          'Suppliers (AP)',        'liability', 1),
    (1, '2100', 'خصوم.ضريبة.مبيعات',            'Output VAT (Sales)',    'liability', 1),
    (1, '2110', 'خصوم.ضريبة.مشتريات',           'Output VAT (Purchases)','liability', 1),
    (1, '3000', 'حقوق ملكية.راس المال',         'Capital',               'equity', 1),
    (1, '4000', 'ايرادات.مبيعات',               'Sales Revenue',         'income', 1),
    (1, '5000', 'مصروفات',                      'Expenses',              'expense', 1),
    (1, '5900', 'مصروفات.جرد وتعديل الارصدة',  'Stock Corrections',     'expense', 1),
    (1, '6000', 'تكلفة المبيعات',               'Cost of Goods Sold',    'expense', 1);

-- parent wiring by code (rev 009)
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '100') WHERE branch_id = 1 AND code IN ('110','1300');
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code IN ('1000','1001','1010','1100','1110','1200');
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '200') WHERE branch_id = 1 AND code IN ('210','220');
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '210') WHERE branch_id = 1 AND code IN ('2000','2100','2110');
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '300') WHERE branch_id = 1 AND code = '3000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '400') WHERE branch_id = 1 AND code = '4000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '500') WHERE branch_id = 1 AND code IN ('5000','5900','6000');

-- pilot plugins registered (A10), disabled until the plugin ships
INSERT INTO app_plugins (slug, name_ar, name_en, version, core_requires, sdk_version, status)
VALUES
    ('pharmatag-eta', 'الفوترة الإلكترونية', 'E-invoicing (ETA)', '0.0.0', '>=0.1.0,<1.0.0', '0.1.0', 'installed'),
    ('pharmatag-ledger', 'المحاسبة', 'Accounting & Ledger', '0.0.0', '>=0.1.0,<1.0.0', '0.1.0', 'installed');

INSERT INTO plugin_branch_grants (plugin_id, branch_id, enabled)
SELECT id, 1, 0 FROM app_plugins;

-- rev 005: drug-master price levels (mirrors sqlite/migrations/005_drug_price_levels.sql).
-- Runs AFTER the rev 002 seeds so the drugs.manage role link can resolve roles/permissions.
-- NUMERIC(18,4) <-> INTEGER ×10000; column-level CHECKs (SQLite can't ALTER table-level).
ALTER TABLE drugs ADD COLUMN price_wholesale INTEGER DEFAULT 0 CHECK (price_wholesale >= 0);
ALTER TABLE drugs ADD COLUMN price_cost     INTEGER DEFAULT 0 CHECK (price_cost >= 0);

-- Seeded medicines (rev 003): wholesale == public price (same backfill as PG).
-- The desktop seeds 003 rows at runtime (apps/desktop/src/drugs.ts seedDrugs), which
-- supplies price_wholesale/price_cost directly; this UPDATE is the twin-equivalent backfill.
UPDATE drugs SET price_wholesale = price WHERE price_wholesale = 0;

-- drugs.manage gates drug-master writes (legacy level-3 area الأصناف والمخزون).
INSERT INTO permissions (code, name_ar) VALUES ('drugs.manage', 'الأصناف والمخزون');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT 1, id FROM permissions WHERE code = 'drugs.manage';

-- rev 009: accounts.manage gates chart-of-accounts writes (admin + accountant).
INSERT INTO permissions (code, name_ar) VALUES ('accounts.manage', 'إدارة شجرة الحسابات');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'accounts.manage' AND r.id IN (1, 4);

-- rev 011: journals.manage gates manual-journal posting (admin + accountant + manager).
INSERT INTO permissions (code, name_ar) VALUES ('journals.manage', 'ترحيل قيود يومية');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'journals.manage' AND r.id IN (1, 4, 5);

-- rev 012: receivables.manage gates settlements (admin + accountant + manager).
INSERT INTO permissions (code, name_ar) VALUES ('receivables.manage', 'تحصيل وسداد الآجل');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'receivables.manage' AND r.id IN (1, 4, 5);

-- rev 013: monthly_close + month_open_balances (S2.6, #21) — monthy\moves + start-data.
-- status default 'open' mirrors daily_close and spec plan/01 §3.5; absent row = open
CREATE TABLE monthly_close (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    status    TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','reopened')),
    closed_by INTEGER REFERENCES users(id),
    closed_at TEXT,
    PRIMARY KEY (branch_id, year, month),
    CHECK (month BETWEEN 1 AND 12)
);

CREATE TABLE month_open_balances (
    branch_id  INTEGER NOT NULL REFERENCES branches(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    debit      INTEGER NOT NULL DEFAULT 0 CHECK (1=1),
    credit     INTEGER NOT NULL DEFAULT 0 CHECK (1=1),
    PRIMARY KEY (branch_id, account_id, year, month),
    CHECK (month BETWEEN 1 AND 12)
);

INSERT INTO permissions (code, name_ar) VALUES ('months.close', 'تقفيل الشهر');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'months.close' AND r.id IN (1, 4, 5);

-- rev 015: report_catalog + print_jobs (S3.1, #23) — RPT menu/dispatch key +
-- durable print queue; seeds mirror alembic 015.
CREATE TABLE report_catalog (
    code     TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title_ar TEXT NOT NULL,
    title_en TEXT NOT NULL,
    params   TEXT NOT NULL DEFAULT '[]',           -- JSON array of param names
    paper    TEXT NOT NULL DEFAULT 'A4' CHECK (paper IN ('A4', 'A5')),
    sort     INTEGER NOT NULL DEFAULT 0,
    active   INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE print_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER NOT NULL REFERENCES branches(id),
    user_id     INTEGER REFERENCES users(id),
    report_code TEXT NOT NULL REFERENCES report_catalog(code),
    params      TEXT NOT NULL DEFAULT '{}',          -- JSON object snapshot
    paper       TEXT NOT NULL DEFAULT 'A4' CHECK (paper IN ('A4', 'A5')),
    status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'done', 'failed')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    done_at     TEXT
);

INSERT INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('drawer_handover', 'money', 'تسليم الدرج', 'Drawer Handover', '["date_from", "date_to"]', 'A4', 10),
    ('day_profit', 'money', 'ربح اليوم', 'Day Profit', '["datee"]', 'A4', 20),
    ('period_totals', 'money', 'ملخص المبيعات والمشتريات', 'Sales & Purchases Summary', '["date_from", "date_to"]', 'A4', 30),
    ('stock_minimum', 'stock', 'النواقص (أقل من الحد الأدنى)', 'Stock Below Minimum', '[]', 'A4', 40);

-- rev 023: einvoice foundations (S4.1, #28; ADR-0002) — per-device UUID/counter
-- chain + tax-document log; payload_json TEXT keeps document key order verbatim
-- (PG side uses `json`, NOT jsonb) so the receipt UUID recomputes identically.
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
    attempts       INTEGER NOT NULL DEFAULT 0,      -- S4.2 retry bookkeeping
    next_attempt_at TEXT,                            -- backoff gate; NULL = due now
    last_error     TEXT NOT NULL DEFAULT '',        -- last transport/ETA error
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (branch_id, kind, counter),
    UNIQUE (invoice_id)
);

CREATE INDEX ix_einvoice_log_status ON einvoice_log (status);

ALTER TABLE parties ADD COLUMN tax_registration_no TEXT NOT NULL DEFAULT '';

-- rev 027: inter-pharmacy transfers (S5.2, #32; T1–T7) — state machine
-- draft → dispatched → received, cancelled only from draft; per-source
-- monotonic transfer_no with UNIQUE backstop; alloc_json TEXT holds the
-- dispatch batch allocations verbatim so replays reproduce exact batches/costs.
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

COMMIT;
