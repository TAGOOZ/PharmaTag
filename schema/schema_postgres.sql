-- ============================================================================
-- TITAN.W1 → Modern Replacement — CANONICAL POSTGRESQL SCHEMA
-- FastAPI backend (canonical), Next.js web reads/writes via the API.
-- Design: schema_design.md. Sources: SCHEMA_EVALUATION.md (§1.1-§1.12, §2, §3),
-- SCHEMA_RESOLVED.md (11 adjudicated contradictions), schema_complete.sql (28 tables),
-- PHY_MIGRATION.md (.phy record layouts).
--
-- MONEY TYPING (SCHEMA_EVALUATION §1.11, §3.3):
--   - ALL money is NUMERIC. Never REAL/float/double.
--   - NUMERIC(18,2)  = monetary totals, balances, amounts.
--   - NUMERIC(18,4)  = per-unit cost/price and quantities.
--   - NUMERIC(5,2)   = VAT/discount RATES (percent).
--   - ROUNDING RULE: round-half-up to 2 dp at every line-total and payment boundary;
--     per-unit prices/costs keep 4 dp and are rounded only when multiplied into a total.
--   - Legacy VB6 Single/Double money fields are rounded ONCE to 4 dp at import;
--     historical totals are NEVER re-summed from floats.
--
-- AUDIT REQUIREMENT (SCHEMA_EVALUATION §1.6): every money/stock table below carries a
-- comment of the form "AUDIT: ...". Every write to that table MUST also insert a row into
-- audit_log in the SAME transaction.
--
-- BALANCED JOURNAL INVARIANT (feature_balances.md:328; SCHEMA_EVALUATION §1.11):
-- SUM(journal_lines.debit) = SUM(journal_lines.credit) per journal_id is enforced in the
-- API transaction that writes journals+journal_lines atomically (a cross-table CHECK is not
-- expressible in plain DDL). journal_lines carries a single-side CHECK instead.
--
-- This file is self-contained: every FK target is declared before use.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 0. ENUMS
-- ============================================================================

CREATE TYPE party_kind AS ENUM ('customer','supplier','both');          -- wzcustomers.typee discriminator
CREATE TYPE account_type AS ENUM ('asset','liability','equity','income','expense');
CREATE TYPE journal_source AS ENUM ('sale','purchase','sale_return','purchase_return','manual','transfer','opening','settlement','correction');
CREATE TYPE invoice_kind AS ENUM ('sale','purchase','sale_return','purchase_return','transfer');
-- Legacy states incl. Saved/Unsaved/"Un save"/Copy/transfer states (feature_sales_invoices.md:3)
CREATE TYPE invoice_status AS ENUM ('saved','unsaved','unsave','copy','transfer_to_sale_return','transfer_to_purchase','closed','archived','void');
CREATE TYPE payment_method AS ENUM ('cash','card','credit','manual_cash','manual_card');   -- §1.11
CREATE TYPE batch_type AS ENUM ('purchase','sale','return','count','transfer_in','transfer_out','opening','correction'); -- wzgard.typee
CREATE TYPE drawer_direction AS ENUM ('in','out');
CREATE TYPE drawer_method AS ENUM ('cash','network');                                      -- شبكة
CREATE TYPE drawer_reason AS ENUM ('cash_sale','cash_return','supplier_pay','customer_settlement','expense','transfer','opening','correction');
CREATE TYPE close_status AS ENUM ('open','closed','reopened');
CREATE TYPE transfer_status AS ENUM ('created','in_transit','delivered','received','cancelled'); -- delivery.phy
CREATE TYPE shortage_method AS ENUM ('manual','half_auto','sales_rate');
CREATE TYPE need_status AS ENUM ('pending','fulfilled','cancelled');
CREATE TYPE purchase_order_status AS ENUM ('pending','saved','received','cancelled');      -- legacy NULL=pending
CREATE TYPE correction_status AS ENUM ('pending','approved','rejected');                    -- §1.7
CREATE TYPE einvoice_kind AS ENUM ('zatca','eta');
CREATE TYPE einvoice_status AS ENUM ('pending','submitted','accepted','rejected','failed','cancelled','void');
CREATE TYPE sync_status AS ENUM ('pending','applied','failed','skipped');
CREATE TYPE interaction_severity AS ENUM ('minor','moderate','major','contraindicated','unknown');
CREATE TYPE archive_status AS ENUM ('pending','running','done','failed');

-- ============================================================================
-- 1. BRANCHES — wzphar (§2.1, §1.12). Legacy natural keys pharmacyid/phar/mobile kept.
-- ============================================================================

CREATE TABLE branches (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pharmacyid    VARCHAR(15)  NOT NULL,              -- legacy wzphar.pharmacyid
    phar          VARCHAR(15)  DEFAULT '',            -- legacy alias (wzgard.phar, farysales.phar)
    mobile        VARCHAR(15)  NOT NULL,              -- legacy branch key (farysales.mobile ...)
    pharname      VARCHAR(100) NOT NULL DEFAULT '',   -- wzphar.pharname (NOT pharmacyname — that is storediscount/titanpharmalist, SCHEMA_RESOLVED §8)
    adress        VARCHAR(200) DEFAULT '',
    governorate   VARCHAR(50)  DEFAULT '',            -- Mohafaza
    district      VARCHAR(50)  DEFAULT '',            -- Markaz
    country       VARCHAR(50)  DEFAULT '',
    currency      VARCHAR(10)  DEFAULT '',
    vat_default   NUMERIC(5,2) NOT NULL DEFAULT 15.00,-- Gulf 15% vs Egypt 14% (storediscount.country, §1.11)
    is_main_device BOOLEAN     NOT NULL DEFAULT FALSE,-- ismaster.txt
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_branches_pharmacyid UNIQUE (pharmacyid),
    CONSTRAINT uq_branches_mobile UNIQUE (mobile)
);
COMMENT ON TABLE branches IS 'Branch hub (←wzphar). Natural keys pharmacyid/phar/mobile for migration. AUDIT: structural only.';

-- ============================================================================
-- 2. USERS / RBAC — FormUsers/FFFUserEdit (§1.12). ShogUser.phy → users log.
-- ============================================================================

CREATE TABLE users (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username   VARCHAR(50) NOT NULL UNIQUE,
    namee      VARCHAR(100) NOT NULL DEFAULT '',
    mobile     VARCHAR(15) DEFAULT '',                -- legacy usersmony.phy linkage
    pass_hash  VARCHAR(255) DEFAULT '',
    branch_id  BIGINT REFERENCES branches(id),
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roles (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200) DEFAULT ''
);

CREATE TABLE permissions (
    id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code   VARCHAR(50) NOT NULL UNIQUE,
    name_ar VARCHAR(100) DEFAULT ''
);
-- legacy الصلاحية 1-9 (feature_users_permissions_menus.md) seeded as rows in migration.

CREATE TABLE role_permissions (
    role_id       BIGINT NOT NULL REFERENCES roles(id),
    permission_id BIGINT NOT NULL REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES users(id),
    role_id BIGINT NOT NULL REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

-- ============================================================================
-- 3. DRUG MASTER — wzdrugs + tar.phy (VERIFIED EN@0x00/AR@0x34 cp1256)
-- ============================================================================

CREATE TABLE drugs (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drugname     VARCHAR(100) NOT NULL UNIQUE,        -- legacy PK (wzdrugs.drugname) + tar.phy EN name
    drugnamear   VARCHAR(100) NOT NULL DEFAULT '',    -- wzdrugs.drugnamear / tar.phy Arabic name
    generic      VARCHAR(120) DEFAULT '',
    classy       VARCHAR(35)  DEFAULT '',
    pharmacology VARCHAR(200) DEFAULT '',
    co           VARCHAR(100) DEFAULT '',
    unitsclass   VARCHAR(50)  DEFAULT '',
    vat          NUMERIC(5,2) NOT NULL DEFAULT 0,     -- VAT rate %
    units        INTEGER      NOT NULL DEFAULT 0,     -- pack size (wzdrugs.units)
    unitsmall    INTEGER      NOT NULL DEFAULT 0,     -- small units (wzdrugs.Unitsmall)
    price        NUMERIC(18,4) DEFAULT 0,             -- selling price (4 dp)
    price_now    NUMERIC(18,4) DEFAULT 0,             -- wzdrugs.PriceNow
    disco        NUMERIC(5,2)  DEFAULT 0,
    pricechanged BOOLEAN      DEFAULT FALSE,
    localimport  INTEGER      DEFAULT 0,
    titanid      INTEGER      DEFAULT 0,              -- chain sync id
    history      TEXT         DEFAULT '',             -- wzdrugs.history
    active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    lastedit     TIMESTAMPTZ                          -- wzdrugs.lastedit
);
COMMENT ON TABLE drugs IS 'Drug master (←wzdrugs + tar.phy). AUDIT: price/master edits write audit_log (drug_id).';

CREATE TABLE drug_barcodes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drug_id    BIGINT NOT NULL REFERENCES drugs(id),
    barcode    VARCHAR(16) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,        -- wzdrugs.barcode = primary, Barcode1..5 = alternates
    CONSTRAINT uq_drug_barcodes UNIQUE (drug_id, barcode)
);
CREATE UNIQUE INDEX uq_drug_barcodes_barcode ON drug_barcodes (barcode);  -- lookup by ANY of the 6 codes (§1.11)

CREATE TABLE unit_conversions (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drug_id   BIGINT NOT NULL REFERENCES drugs(id),
    from_unit VARCHAR(20) NOT NULL,                   -- 'pack' | 'small' | custom (wzdrugs.units/Unitsmall)
    to_unit   VARCHAR(20) NOT NULL,
    factor    NUMERIC(18,6) NOT NULL,
    CONSTRAINT ck_unit_conversions_factor CHECK (factor > 0)
);

-- ============================================================================
-- 4. ACCOUNTS — wzaccfreetree + acctree.phy (§1.4, §2.1)
-- ============================================================================

CREATE TABLE accounts (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id  BIGINT NOT NULL REFERENCES branches(id),  -- per-branch chart (§1.4)
    code       VARCHAR(30) NOT NULL,
    parent_id  BIGINT REFERENCES accounts(id),           -- master/fary tree
    master     VARCHAR(100) DEFAULT '',                  -- wzaccfreetree.master
    fary       VARCHAR(100) DEFAULT '',                  -- wzaccfreetree.fary
    name_ar    VARCHAR(120) DEFAULT '',
    name_en    VARCHAR(120) DEFAULT '',
    type       account_type NOT NULL,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_accounts_branch_code UNIQUE (branch_id, code)
);
-- NOTE: parent_id must reference an account of the SAME branch_id; enforced by the API layer.

-- ============================================================================
-- 5. PARTIES — wzcustomers + companies + wzsuppliers + customers.w.phy (§1.11, §2.1)
-- ============================================================================

CREATE TABLE parties (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id             BIGINT NOT NULL REFERENCES branches(id),   -- branch-scoped (wzcustomers.phar)
    kind                  party_kind NOT NULL DEFAULT 'customer',    -- customer|supplier|both (dual-identity merge)
    typee                 VARCHAR(50) DEFAULT '',                    -- wzcustomers.typee discriminator
    namee                 VARCHAR(100) NOT NULL DEFAULT '',
    name_ar               VARCHAR(100) DEFAULT '',
    mobile                VARCHAR(15) DEFAULT '',                    -- companies.mobile (supplier phone) merged here
    adress                VARCHAR(200) DEFAULT '',
    governorate           VARCHAR(50) DEFAULT '',
    district              VARCHAR(50) DEFAULT '',
    credit_limit          NUMERIC(18,2) NOT NULL DEFAULT 0,          -- wzcustomers.creditlimit
    receivable_account_id BIGINT REFERENCES accounts(id),            -- default AR (اجل العملاء)
    payable_account_id    BIGINT REFERENCES accounts(id),            -- default AP (موردين)
    writer                VARCHAR(50) DEFAULT '',                    -- wzcustomers.writer
    randomid              VARCHAR(50) DEFAULT '',                    -- legacy natural key (wzcustomers.randomid)
    datee                 DATE,
    active                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_parties_branch_randomid UNIQUE (branch_id, randomid)
);
-- AUDIT: balance-relevant party changes (credit_limit) write audit_log.

-- ============================================================================
-- 6. DRUG COSTS — wzdrugs2 (§2.1)
-- ============================================================================

CREATE TABLE drug_costs (
    branch_id BIGINT NOT NULL REFERENCES branches(id),
    drug_id   BIGINT NOT NULL REFERENCES drugs(id),
    unitcost  NUMERIC(18,4) NOT NULL DEFAULT 0,        -- unit cost (4 dp)
    costvalue NUMERIC(18,4) NOT NULL DEFAULT 0,        -- wzdrugs2.costvalue
    expire    DATE,                                    -- wzdrugs2.expire (VB6 serial converted)
    PRIMARY KEY (branch_id, drug_id)
);
COMMENT ON TABLE drug_costs IS 'Per-branch cost extension (←wzdrugs2). AUDIT: cost changes write audit_log.';

-- ============================================================================
-- 7. STOCK BATCHES — wzgard (§1.2). Per-branch batch/expiry inventory.
-- ============================================================================

CREATE TABLE stock_batches (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id    BIGINT NOT NULL REFERENCES branches(id),   -- wzgard.phar
    drug_id      BIGINT NOT NULL REFERENCES drugs(id),      -- wzgard.drugname
    randomid     VARCHAR(50) NOT NULL,                      -- wzgard.randomid (batch identity)
    qty          NUMERIC(18,4) NOT NULL DEFAULT 0,          -- wzgard.quant (4 dp)
    expire       DATE,                                      -- wzgard.expire
    cost         NUMERIC(18,4) NOT NULL DEFAULT 0,          -- wzgard.costvalue → COGS / ربح اليوم
    vat          NUMERIC(5,2)  NOT NULL DEFAULT 0,          -- VAT rate %
    price        NUMERIC(18,4) NOT NULL DEFAULT 0,          -- wzgard.price
    oldstock     NUMERIC(18,4) NOT NULL DEFAULT 0,          -- wzgard.oldstock (audit trail per movement)
    typee        batch_type NOT NULL DEFAULT 'purchase',    -- wzgard.typee: sale|purchase|return|count (+ transfers/opening)
    vatvalue     NUMERIC(18,2) DEFAULT 0,                   -- wzgard.vatvalue
    totalwithvat NUMERIC(18,2) DEFAULT 0,                   -- wzgard.totalwithvat
    writer       VARCHAR(50) DEFAULT '',                    -- wzgard.writer
    classy       VARCHAR(35) DEFAULT '',                    -- wzgard.classy
    created_by   BIGINT REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_batches UNIQUE (branch_id, drug_id, randomid)
);
CREATE INDEX ix_stock_batches_expiry ON stock_batches (branch_id, drug_id, expire);  -- FIFO/expiry sale selection
COMMENT ON TABLE stock_batches IS 'Batch/expiry stock (←wzgard). AUDIT: every batch movement (qty/cost/typee) writes audit_log atomically (drug_id, barcode).';

-- ============================================================================
-- 8. WORK PERIODS & SHIFTS — workperiod.phy (§1.9)
-- ============================================================================

CREATE TABLE work_periods (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id),
    name      VARCHAR(50) DEFAULT '',
    opened_by BIGINT REFERENCES users(id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
);

CREATE TABLE shifts (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id      BIGINT NOT NULL REFERENCES branches(id),
    work_period_id BIGINT REFERENCES work_periods(id),
    opened_by      BIGINT NOT NULL REFERENCES users(id),
    opened_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at      TIMESTAMPTZ,
    cash_start     NUMERIC(18,2) NOT NULL DEFAULT 0,    -- drawer @ start (تسليم الدرج RPT-A04)
    CONSTRAINT ck_shifts_times CHECK (closed_at IS NULL OR closed_at >= opened_at)
);
COMMENT ON TABLE shifts IS 'Shift handover (←workperiod.phy). AUDIT: drawer money per shift writes audit_log.';

-- ============================================================================
-- 9. INVOICES — invoicedata 17-col hybrid header + titanksasales 9-col (§2.1, §1.11)
-- ============================================================================

CREATE TABLE invoices (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id      BIGINT NOT NULL REFERENCES branches(id),     -- invoicedata.pharmacyid / titanksasales.pharmacyid
    kind           invoice_kind NOT NULL DEFAULT 'sale',
    invoice_no     VARCHAR(30) NOT NULL,                        -- legacy invoiceid
    datee          DATE NOT NULL,                               -- legacy datee (VB6 serial converted)
    datetimee      TIMESTAMPTZ,
    silsilaid      VARCHAR(15) DEFAULT '',                      -- chain/series id
    party_id       BIGINT REFERENCES parties(id),
    subtotal       NUMERIC(18,2) NOT NULL DEFAULT 0,
    discount       NUMERIC(18,2) NOT NULL DEFAULT 0,
    vat            NUMERIC(18,2) NOT NULL DEFAULT 0,
    totalvalue     NUMERIC(18,2) NOT NULL DEFAULT 0,            -- legacy totalvalue
    payed          NUMERIC(18,2) NOT NULL DEFAULT 0,            -- legacy payed (cash+card)
    agel           NUMERIC(18,2) NOT NULL DEFAULT 0,            -- legacy agel (أجل / credit)
    status         invoice_status NOT NULL DEFAULT 'saved',     -- Saved/Unsaved/Un save/Copy/transfer states
    writer         VARCHAR(50) DEFAULT '',
    created_by     BIGINT REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_edited_at TIMESTAMPTZ,                                 -- LastEdited.phy index
    CONSTRAINT ck_invoice_payment CHECK (payed + agel = totalvalue)   -- legacy split identity (connections_overview.html:418)
);
CREATE INDEX ix_invoices_branch_date ON invoices (branch_id, datee);
CREATE INDEX ix_invoices_branch_party ON invoices (branch_id, party_id);
CREATE INDEX ix_invoices_last_edited ON invoices (last_edited_at);
COMMENT ON TABLE invoices IS 'Invoice header (←invoicedata header cols, titanksasales). AUDIT: money-affecting create/edit/void writes audit_log + invoice_versions snapshot; ZATCA/ETA resubmit on edit (§1.10).';

CREATE TABLE invoice_lines (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id),
    branch_id  BIGINT NOT NULL REFERENCES branches(id),         -- §1.1 branch dimension
    drug_id    BIGINT NOT NULL REFERENCES drugs(id),            -- invoicedata.DrugName
    batch_id   BIGINT REFERENCES stock_batches(id),             -- §1.2 (now resolves)
    qty        NUMERIC(18,4) NOT NULL DEFAULT 0,                -- invoicedata.Quant
    unit       VARCHAR(20) DEFAULT 'pack',                      -- unit_conversions key (pack/small)
    unit_price NUMERIC(18,4) NOT NULL DEFAULT 0,                -- invoicedata.price (4 dp)
    cost       NUMERIC(18,4) NOT NULL DEFAULT 0,                -- batch cost for COGS
    disc       NUMERIC(5,2)  NOT NULL DEFAULT 0,                -- invoicedata.SellDisc
    vat        NUMERIC(5,2)  NOT NULL DEFAULT 0,
    line_total NUMERIC(18,2) NOT NULL DEFAULT 0,                -- rounded half-up to 2 dp
    expire     DATE,                                            -- invoicedata.Expire
    minimum    NUMERIC(18,4) DEFAULT 0,                         -- invoicedata.Minimum
    tips       VARCHAR(50) DEFAULT '',                          -- invoicedata.Tips
    iddatetime TIMESTAMPTZ,                                     -- invoicedata.IdDateTime
    CONSTRAINT ck_invoice_line_unit_price CHECK (unit_price >= 0)
);
CREATE INDEX ix_invoice_lines_invoice ON invoice_lines (invoice_id);
CREATE INDEX ix_invoice_lines_drug ON invoice_lines (branch_id, drug_id);
COMMENT ON TABLE invoice_lines IS 'Invoice line items (←invoicedata line cols). AUDIT: line writes write audit_log with drug_id.';

CREATE TABLE invoice_versions (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id),
    version_no INTEGER NOT NULL,
    action     VARCHAR(30) DEFAULT '',                           -- create|edit|reversal|transfer (تعديل فواتير)
    payload    JSONB,                                            -- full header+lines snapshot pre-edit
    changed_by BIGINT REFERENCES users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_invoice_versions UNIQUE (invoice_id, version_no)
);
COMMENT ON TABLE invoice_versions IS 'Edit-reversal versions (§1.6). Writes journal reversal + re-apply rows traceable here.';

CREATE TABLE payment_splits (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id  BIGINT NOT NULL REFERENCES invoices(id),
    branch_id   BIGINT NOT NULL REFERENCES branches(id),         -- §1.1
    method      payment_method NOT NULL DEFAULT 'cash',          -- cash|card|credit|manual_cash|manual_card (§1.11)
    amount      NUMERIC(18,2) NOT NULL DEFAULT 0,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id     BIGINT REFERENCES users(id),
    CONSTRAINT ck_payment_split_amount CHECK (amount > 0)
);
COMMENT ON TABLE payment_splits IS 'Payment split (←payed/agel). AUDIT: money write → audit_log.';

-- ============================================================================
-- 10. JOURNALS & LEDGER — farysales 17-col LIVE ledger + Accounting\moves (§1.4)
-- ============================================================================

CREATE TABLE journals (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id     BIGINT NOT NULL REFERENCES branches(id),
    datee         DATE NOT NULL,
    entry_no      INTEGER NOT NULL,                              -- unique entry seq per (branch_id, date) (§1.11)
    description   VARCHAR(200) NOT NULL,                         -- REQUIRED (feature_balances.md:301)
    source        journal_source NOT NULL DEFAULT 'sale',
    status        VARCHAR(20) NOT NULL DEFAULT 'posted',
    ref_invoice_id BIGINT REFERENCES invoices(id),
    created_by    BIGINT REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_journals_entry UNIQUE (branch_id, datee, entry_no)
);
-- INVARIANT: SUM(journal_lines.debit) = SUM(journal_lines.credit) per journal — enforced in
-- the API transaction (see file header). journal_lines single-side CHECK enforces the rest.
COMMENT ON TABLE journals IS 'Journal header (feature_balances / farysales). AUDIT: journal writes write audit_log.';

CREATE TABLE journal_lines (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    journal_id     BIGINT NOT NULL REFERENCES journals(id),
    branch_id      BIGINT NOT NULL REFERENCES branches(id),      -- §1.1 (farysales.mobile/phar)
    account_id     BIGINT NOT NULL REFERENCES accounts(id),      -- father/son → accounts
    debit          NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit         NUMERIC(18,2) NOT NULL DEFAULT 0,
    contra_party_id BIGINT REFERENCES parties(id),               -- كشف حساب per customer/supplier
    datee          DATE NOT NULL,
    month          INTEGER NOT NULL,                             -- farysales.monthe
    year           INTEGER NOT NULL,                             -- farysales.yearo
    creditdebit    VARCHAR(20) DEFAULT '',                       -- farysales.creditdebit (SCHEMA_RESOLVED §11)
    randomid       VARCHAR(50) DEFAULT '',                       -- farysales.randomid
    writer         VARCHAR(50) DEFAULT '',                       -- farysales.writer
    tips           VARCHAR(50) DEFAULT '',                       -- farysales.tips
    classy         VARCHAR(35) DEFAULT '',                       -- farysales.classy
    CONSTRAINT ck_journal_line_single_side CHECK ((debit >= 0) AND (credit >= 0) AND (debit = 0 OR credit = 0)),
    CONSTRAINT ck_journal_line_month CHECK (month BETWEEN 1 AND 12)
);
CREATE INDEX ix_journal_lines_account ON journal_lines (branch_id, account_id, month, year);
CREATE INDEX ix_journal_lines_journal ON journal_lines (journal_id);
COMMENT ON TABLE journal_lines IS 'Ledger rows (←farysales LIVE 17-col + Accounting\moves). AUDIT: money write → audit_log (entity=journal, entity_id=id).';

-- ============================================================================
-- 11. BALANCES & MONTH CLOSE — farysales monthe/yearo, monthy\moves + start-data (§1.1, §1.4)
-- ============================================================================

CREATE TABLE balances (
    branch_id  BIGINT NOT NULL REFERENCES branches(id),
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    month      INTEGER NOT NULL,
    year       INTEGER NOT NULL,
    debit      NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit     NUMERIC(18,2) NOT NULL DEFAULT 0,
    balance    NUMERIC(18,2) NOT NULL DEFAULT 0,      -- balance = debit - credit (ميزان / كشف حساب)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (branch_id, account_id, month, year),
    CONSTRAINT ck_balances_month CHECK (month BETWEEN 1 AND 12),
    CONSTRAINT ck_balances_identity CHECK (balance = debit - credit)
);
COMMENT ON TABLE balances IS 'Per-branch per-month balances (←farysales monthe/yearo). AUDIT: balance recompute on journal posting writes audit_log.';

CREATE TABLE monthly_close (
    branch_id BIGINT NOT NULL REFERENCES branches(id),
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    status    close_status NOT NULL DEFAULT 'open',
    closed_by BIGINT REFERENCES users(id),
    closed_at TIMESTAMPTZ,
    PRIMARY KEY (branch_id, year, month),
    CONSTRAINT ck_monthly_close_month CHECK (month BETWEEN 1 AND 12)
);
COMMENT ON TABLE monthly_close IS 'Per-branch month close (←monthy\moves). AUDIT: close action writes audit_log.';

CREATE TABLE month_open_balances (
    branch_id  BIGINT NOT NULL REFERENCES branches(id),
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    debit      NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit     NUMERIC(18,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (branch_id, account_id, year, month),
    CONSTRAINT ck_month_open_month CHECK (month BETWEEN 1 AND 12)
);
COMMENT ON TABLE month_open_balances IS 'Opening balances per branch/account/month (←monthy\start-data; §1.11 replaces start_balances_json). Seeded from opening stock/receivables/payables/drawer (idx 8482-8485). AUDIT: seeds write audit_log.';

-- ============================================================================
-- 12. DRAWER & DAY CLOSE — Daily.phy, MonyInfo.phy (§1.1, §1.5, §1.11)
-- ============================================================================

CREATE TABLE drawer_movements (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id      BIGINT NOT NULL REFERENCES branches(id),
    datee          DATE NOT NULL,
    direction      drawer_direction NOT NULL DEFAULT 'in',
    reason         drawer_reason NOT NULL DEFAULT 'cash_sale',
    method         drawer_method NOT NULL DEFAULT 'cash',        -- cash|network (كاش/شبكة)
    amount         NUMERIC(18,2) NOT NULL DEFAULT 0,
    shift_id       BIGINT REFERENCES shifts(id),                 -- §1.9 (now resolves)
    ref_invoice_id BIGINT REFERENCES invoices(id),
    user_id        BIGINT REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_drawer_amount CHECK (amount >= 0)
);
CREATE INDEX ix_drawer_movements_branch_date ON drawer_movements (branch_id, datee);
COMMENT ON TABLE drawer_movements IS 'Drawer register (←Daily.phy 614 B, حركة مالية). AUDIT: every drawer movement writes audit_log atomically.';

CREATE TABLE daily_close (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id     BIGINT NOT NULL REFERENCES branches(id),
    datee         DATE NOT NULL,
    shift_id      BIGINT REFERENCES shifts(id),                  -- §1.11
    work_period_id BIGINT REFERENCES work_periods(id),           -- §1.11
    drawer_start  NUMERIC(18,2) NOT NULL DEFAULT 0,              -- drawer @ start-of-period
    expected_cash NUMERIC(18,2) NOT NULL DEFAULT 0,
    counted_cash  NUMERIC(18,2) NOT NULL DEFAULT 0,
    difference    NUMERIC(18,2) NOT NULL DEFAULT 0,
    manual_cash   NUMERIC(18,2) NOT NULL DEFAULT 0,              -- كاش يدوي (§1.11)
    manual_card   NUMERIC(18,2) NOT NULL DEFAULT 0,              -- شبكة يدوي (§1.11)
    net_cash      NUMERIC(18,2) NOT NULL DEFAULT 0,
    net_network   NUMERIC(18,2) NOT NULL DEFAULT 0,              -- شبكة
    purchases     NUMERIC(18,2) NOT NULL DEFAULT 0,
    expenses      NUMERIC(18,2) NOT NULL DEFAULT 0,
    cost_of_sales NUMERIC(18,2) NOT NULL DEFAULT 0,              -- تكلفة مبيعات اليوم (COGS)
    net_profit    NUMERIC(18,2) NOT NULL DEFAULT 0,              -- ربح اليوم
    discounts     NUMERIC(18,2) NOT NULL DEFAULT 0,              -- خصومات اليوم
    vat_sales     NUMERIC(18,2) NOT NULL DEFAULT 0,
    vat_purchases NUMERIC(18,2) NOT NULL DEFAULT 0,
    vat_expenses  NUMERIC(18,2) NOT NULL DEFAULT 0,
    status        close_status NOT NULL DEFAULT 'open',
    closed_by     BIGINT REFERENCES users(id),
    closed_at     TIMESTAMPTZ,
    CONSTRAINT uq_daily_close UNIQUE (branch_id, datee),          -- locks a date per branch
    CONSTRAINT ck_daily_close_diff CHECK (difference = counted_cash - expected_cash)
);
COMMENT ON TABLE daily_close IS 'Immutable day-close snapshot (←MonyInfo.phy + Daily.phy totals, idx 9883). AUDIT: close writes audit_log; reopening writes reversal.';

-- ============================================================================
-- 13. BRANCH STOCK — titanstock + titanksastock (§2.1)
-- ============================================================================

CREATE TABLE branch_stock (
    branch_id BIGINT NOT NULL REFERENCES branches(id),
    drug_id   BIGINT NOT NULL REFERENCES drugs(id),
    qty       NUMERIC(18,4) NOT NULL DEFAULT 0,       -- titanstock.stock / titanksastock.stock
    minimum   NUMERIC(18,4) NOT NULL DEFAULT 0,       -- titanksastock.minimum (نواقص threshold)
    silsilaid VARCHAR(15) DEFAULT '',                 -- titanksastock.silsilaid
    classy    VARCHAR(35) DEFAULT '',
    price     NUMERIC(18,4) DEFAULT 0,                -- titanstock.price
    barcode   VARCHAR(16) DEFAULT '',                 -- titanstock.barcode
    lastedit  TIMESTAMPTZ,                            -- titanstock.lastedit
    PRIMARY KEY (branch_id, drug_id)
);
COMMENT ON TABLE branch_stock IS 'Per-branch drug levels (←titanstock/titanksastock). AUDIT: every stock change (incl. negative-balance repair) writes audit_log.';

-- ============================================================================
-- 14. TRANSFERS — titaninn + delivery.phy (§1.9, §2.1, SCHEMA_RESOLVED §10)
-- ============================================================================

CREATE TABLE transfers (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id       BIGINT NOT NULL REFERENCES branches(id),     -- originating branch
    fatid           INTEGER NOT NULL DEFAULT 0,                  -- titaninn.fatid
    datee           DATE,
    silsilaid       VARCHAR(15) DEFAULT '',
    source_branch_id BIGINT REFERENCES branches(id),             -- typed FK
    target_branch_id BIGINT REFERENCES branches(id),             -- typed FK
    legacy_source   VARCHAR(100) DEFAULT '',                     -- titaninn.source free text
    legacy_target   VARCHAR(100) DEFAULT '',                     -- titaninn.target free text
    itemsasstring   TEXT DEFAULT '',                             -- titaninn.itemsasstring (serialized lines)
    status          transfer_status NOT NULL DEFAULT 'created',  -- delivery.phy
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_transfers_target ON transfers (target_branch_id);
COMMENT ON TABLE transfers IS 'Inter-pharmacy transfers (←titaninn, status ←delivery.phy). AUDIT: transfer lifecycle writes audit_log.';

CREATE TABLE transfer_lines (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transfer_id BIGINT NOT NULL REFERENCES transfers(id),
    drug_id    BIGINT NOT NULL REFERENCES drugs(id),
    qty        NUMERIC(18,4) NOT NULL DEFAULT 0,
    expire     DATE,
    batch_id   BIGINT REFERENCES stock_batches(id),
    unit_price NUMERIC(18,4) DEFAULT 0
);
COMMENT ON TABLE transfer_lines IS 'Transfer line items (←titaninn itemsasstring parse). AUDIT: line writes write audit_log.';

-- ============================================================================
-- 15. SHORTAGES & NEEDS — §1.8, titanneed, orders
-- ============================================================================

CREATE TABLE shortage_flags (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT NOT NULL REFERENCES branches(id),
    drug_id     BIGINT NOT NULL REFERENCES drugs(id),
    current_qty NUMERIC(18,4) NOT NULL DEFAULT 0,
    minimum     NUMERIC(18,4) NOT NULL DEFAULT 0,
    method      shortage_method NOT NULL DEFAULT 'manual',       -- manual / half-auto / sales-rate
    flagged_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by BIGINT REFERENCES users(id)
);
COMMENT ON TABLE shortage_flags IS 'Shortage flags (نواقص, §1.8). Non-money; feeds needs/POs.';

CREATE TABLE needs (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id        BIGINT NOT NULL REFERENCES branches(id),
    drug_id          BIGINT NOT NULL REFERENCES drugs(id),      -- titanneed.drugname
    qty              NUMERIC(18,4) NOT NULL DEFAULT 0,          -- titanneed.quant
    datee            DATE,                                      -- titanneed.datee
    sender_branch_id BIGINT REFERENCES branches(id),
    target_branch_id BIGINT REFERENCES branches(id),
    legacy_sender    VARCHAR(20) DEFAULT '',                    -- titanneed.sender
    legacy_target    VARCHAR(20) DEFAULT '',                    -- titanneed.target
    status           need_status NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE purchase_orders (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id  BIGINT NOT NULL REFERENCES branches(id),         -- orders.pharmacyid
    orderid    VARCHAR(50) DEFAULT '',                          -- orders.orderid
    orderdate  DATE,                                            -- orders.orderdate
    datee      DATE,                                            -- orders.datee
    status     purchase_order_status NOT NULL DEFAULT 'pending',-- legacy NULL=pending, 'saved'=done
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stock_correction_requests (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id    BIGINT NOT NULL REFERENCES branches(id),
    drug_id      BIGINT NOT NULL REFERENCES drugs(id),
    batch_id     BIGINT REFERENCES stock_batches(id),
    delta        NUMERIC(18,4) NOT NULL,                        -- positive=بالزيادة, negative=بالعجز
    reason       VARCHAR(200) DEFAULT '',
    requested_by BIGINT NOT NULL REFERENCES users(id),          -- staff
    status       correction_status NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
    approved_by  BIGINT REFERENCES users(id),                   -- manager
    decided_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_correction_decision CHECK ((status = 'pending') = (decided_at IS NULL))
);
COMMENT ON TABLE stock_correction_requests IS 'Approval workflow (←RasidCorrect.phy, §1.7). The stock_batches/branch_stock change is applied ONLY on approval, in the same transaction as audit_log.';

-- ============================================================================
-- 16. CHAIN / DEAD-STOCK EXCHANGE — RawakidTablew + ChainBuyStore + ChainBuyUsers
-- ============================================================================

CREATE TABLE dead_stock_exchange (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id             BIGINT NOT NULL REFERENCES branches(id),
    drug_id               BIGINT NOT NULL REFERENCES drugs(id),     -- RawakidTablew.DrugName
    qty                   NUMERIC(18,4) NOT NULL DEFAULT 0,         -- Quant
    expire                DATE,                                     -- Expire
    price                 NUMERIC(18,4) DEFAULT 0,                  -- price
    sell_disc             NUMERIC(5,2)  DEFAULT 0,                  -- SellDisc
    tips                  VARCHAR(50) DEFAULT '',                   -- Tips
    governorate           VARCHAR(50) DEFAULT '',                   -- Mohafaza
    district              VARCHAR(50) DEFAULT '',                   -- Markaz
    source_pharmacist_tel VARCHAR(15) DEFAULT '',                   -- PharmacistTel
    requester_tel         VARCHAR(15) DEFAULT '',                   -- RequisterTel
    source_iddatetime     TIMESTAMPTZ,                              -- SourceIdDateTime
    country               VARCHAR(50) DEFAULT '',
    status                transfer_status NOT NULL DEFAULT 'created',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE dead_stock_exchange IS 'Dead-stock exchange offers (رواكد, ←RawakidTablew, §1.9).';

CREATE TABLE chain_buy_orders (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id     BIGINT NOT NULL REFERENCES branches(id),
    drug_id       BIGINT NOT NULL REFERENCES drugs(id),          -- DrugName
    store_name    VARCHAR(100) DEFAULT '',                       -- ChainBuyStore.StoreName
    pharmacist_tel VARCHAR(15) DEFAULT '',                       -- PharmacistTel
    requester_tel VARCHAR(15) DEFAULT '',                        -- RequisterTel
    qty           NUMERIC(18,4) NOT NULL DEFAULT 0,              -- Quant
    price         NUMERIC(18,4) DEFAULT 0,                       -- price
    sell_disc     NUMERIC(5,2)  DEFAULT 0,                       -- SellDisc
    expire        DATE,                                          -- Expire
    tips          VARCHAR(50) DEFAULT '',                        -- Tips
    governorate   VARCHAR(50) DEFAULT '',                        -- Mohafaza
    district      VARCHAR(50) DEFAULT '',                        -- Markaz
    country       VARCHAR(50) DEFAULT '',
    iddatetime    TIMESTAMPTZ,                                   -- IdDateTime
    status        transfer_status NOT NULL DEFAULT 'created',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE chain_buy_orders IS 'Chain buy orders (←ChainBuyStore + ChainBuyUsers, §2.1, §1.11 region).';

-- ============================================================================
-- 17. E-INVOICE — ZATCA + oot3/netcounter (§1.10, §1.9)
-- ============================================================================

CREATE TABLE einvoice_log (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id   BIGINT NOT NULL REFERENCES invoices(id),        -- legacy ZATCA.invoiceid
    branch_id    BIGINT NOT NULL REFERENCES branches(id),        -- legacy ZATCA.pharmacyid
    kind         einvoice_kind NOT NULL DEFAULT 'zatca',         -- zatca | eta
    uuid         VARCHAR(100) DEFAULT '',                        -- ZATCA.uuid / ETA "uuid"
    status       einvoice_status NOT NULL DEFAULT 'pending',
    hash         VARCHAR(200) DEFAULT '',                        -- ZATCA.hash
    qr_counter   INTEGER,                                        -- oot3.phy / counter.txt
    qr_hash      VARCHAR(200),                                   -- netcounter.phy / hash.txt
    qr_data      TEXT DEFAULT '',                                -- QR payload string for generation
    payload_xml  TEXT DEFAULT '',                                -- ZATCA.xml
    payload_json JSONB,                                          -- ETA JSON (idx 228-267 shapes)
    response     TEXT DEFAULT '',                                -- ZATCA.response
    submitted_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_einvoice_log_invoice ON einvoice_log (invoice_id);
CREATE INDEX ix_einvoice_log_kind_status ON einvoice_log (kind, status);
COMMENT ON TABLE einvoice_log IS 'E-invoice log (←ZATCA). Resubmission workflow; QR generation supported (qr_data/qr_hash/qr_counter). No network submission to the dead Saudi/Egypt URLs (EGYPT_ETA_DECOMPILED §4). AUDIT: einvoice writes write audit_log.';

CREATE TABLE einvoice_counters (
    branch_id    BIGINT NOT NULL REFERENCES branches(id),
    kind         einvoice_kind NOT NULL DEFAULT 'zatca',
    last_counter INTEGER NOT NULL DEFAULT 0,
    last_hash    VARCHAR(200) DEFAULT '',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (branch_id, kind)
);
COMMENT ON TABLE einvoice_counters IS 'DB-resident ZATCA/ETA counter+hash chain (←oot3/netcounter/counter.txt+hash.txt, §1.9). Updated atomically with each invoice.';

-- ============================================================================
-- 18. AUDIT & SYNC — TitanUserAction, usersourceupdate (§1.6, §1.3)
-- ============================================================================

CREATE TABLE audit_log (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id  BIGINT REFERENCES branches(id),
    user_id    BIGINT REFERENCES users(id),
    entity     VARCHAR(50) NOT NULL,               -- table name (drugs, stock_batches, journal_lines, invoices, ...)
    entity_id  BIGINT,                             -- PK of the changed row
    field      VARCHAR(50) DEFAULT '',             -- changed column
    old_value  TEXT,
    new_value  TEXT,
    drug_id    BIGINT REFERENCES drugs(id),        -- TitanUserAction.drugname
    barcode    VARCHAR(16) DEFAULT '',             -- TitanUserAction.curbarcode
    action     VARCHAR(30) NOT NULL DEFAULT 'update',  -- insert|update|delete|count|correction|price_change
    namee      VARCHAR(100) DEFAULT '',            -- TitanUserAction.namee
    typevalue  VARCHAR(100) DEFAULT '',            -- legacy action-type text
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_entity ON audit_log (entity, entity_id);
CREATE INDEX ix_audit_drug ON audit_log (drug_id);
CREATE INDEX ix_audit_created ON audit_log (created_at);
COMMENT ON TABLE audit_log IS 'Audit trail (←TitanUserAction 11-col). Written atomically with EVERY money/stock/balance mutation (§1.6).';

CREATE TABLE sync_log (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id       BIGINT NOT NULL REFERENCES branches(id),
    entity          VARCHAR(50) NOT NULL,           -- invoices, branch_stock, drugs, ...
    entity_id       BIGINT,
    action          VARCHAR(30) NOT NULL DEFAULT 'update',
    payload         JSONB,                          -- full row snapshot for last-write-wins
    synced_at       TIMESTAMPTZ,
    status          sync_status NOT NULL DEFAULT 'pending',
    source_device_id BIGINT REFERENCES branches(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_sync_log_status ON sync_log (branch_id, status);
COMMENT ON TABLE sync_log IS 'Last-write-wins sync outbox (←usersourceupdate 6-col, §1.3). Every mutating write enqueues here; syncer applies to peers and marks applied.';

CREATE TABLE drug_sync_outbox (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT NOT NULL REFERENCES branches(id),
    drug_id     BIGINT NOT NULL REFERENCES drugs(id),
    price       NUMERIC(18,4) DEFAULT 0,            -- drgserver.price
    units       INTEGER DEFAULT 0,                  -- drgserver.units
    vat         NUMERIC(5,2)  DEFAULT 0,            -- drgserver.vat
    barcode     VARCHAR(16) DEFAULT '',             -- drgserver.barcode
    shape       INTEGER DEFAULT 0,                  -- drgserver.shape
    datee       DATE,                               -- drgserver.datee
    localimport INTEGER DEFAULT 0,                  -- drgserver.localimport
    status      sync_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE drug_sync_outbox IS 'Chain drug-server list channel (←drgserver, §2.1).';

CREATE TABLE branch_identities (
    legacy_table  VARCHAR(50) NOT NULL,
    legacy_column VARCHAR(50) NOT NULL,
    legacy_value  VARCHAR(100) NOT NULL,            -- e.g. farysales.mobile='05xxxx'
    branch_id     BIGINT NOT NULL REFERENCES branches(id),
    PRIMARY KEY (legacy_table, legacy_column, legacy_value)
);
COMMENT ON TABLE branch_identities IS 'Legacy alias→branch map (phar/pharmacyid/mobile, §1.3). Used by the migration to decide which legacy column maps to which branch.';

-- ============================================================================
-- 19. OPERATIONAL / STATE FILES → SQL (§1.9, §2.2)
-- ============================================================================

CREATE TABLE user_drawer_money (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT NOT NULL REFERENCES branches(id),
    user_id     BIGINT REFERENCES users(id),
    shift_id    BIGINT REFERENCES shifts(id),
    datee       DATE,
    cash        NUMERIC(18,2) NOT NULL DEFAULT 0,   -- usersmony.phy money@0x04
    card        NUMERIC(18,2) NOT NULL DEFAULT 0,
    manual_cash NUMERIC(18,2) NOT NULL DEFAULT 0,
    manual_card NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit      NUMERIC(18,2) NOT NULL DEFAULT 0,
    record_no   INTEGER,                            -- usersmony.phy record index (I2 @0x00)
    source_file VARCHAR(50) DEFAULT 'usersmony.phy',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE user_drawer_money IS 'Money per user/shift (←usersmony.phy 318 B, FormUsersMony). AUDIT: drawer money writes audit_log.';

CREATE TABLE drug_interactions (
    id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drug_a   BIGINT NOT NULL REFERENCES drugs(id),
    drug_b   BIGINT NOT NULL REFERENCES drugs(id),
    severity interaction_severity NOT NULL DEFAULT 'unknown',
    note     VARCHAR(500) DEFAULT '',
    CONSTRAINT uq_drug_interactions UNIQUE (drug_a, drug_b),
    CONSTRAINT ck_interactions_ordered CHECK (drug_a < drug_b)
);
COMMENT ON TABLE drug_interactions IS 'Drug-drug interactions (←DDI.Phy, §1.9; ModDDI 1300-B records).';

CREATE TABLE integration_config (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id  BIGINT REFERENCES branches(id),
    key        VARCHAR(50) NOT NULL,                -- myftp.phy config keys, FTP creds (encrypted by app)
    value      TEXT DEFAULT '',
    config     JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_integration_config UNIQUE (branch_id, key)
);
COMMENT ON TABLE integration_config IS 'External integration config (←myftp.phy, §1.9). Secrets encrypted at the app layer.';

CREATE TABLE archive_imports (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT REFERENCES branches(id),
    source_path VARCHAR(500) DEFAULT '',            -- Archive\Input
    file_count  INTEGER DEFAULT 0,
    status      archive_status NOT NULL DEFAULT 'pending',
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    note        TEXT DEFAULT ''                     -- ETL runbook: per-file OK/UNKNOWN_LAYOUT record
);
COMMENT ON TABLE archive_imports IS 'Fat import archive (←Archive\Input). Also logs every legacy_import/ ETL run for graceful degradation (§5).';

CREATE TABLE archive_exports (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT REFERENCES branches(id),
    target_path VARCHAR(500) DEFAULT '',            -- Archive\Output, Titan3-Backup\{...}
    file_count  INTEGER DEFAULT 0,
    status      archive_status NOT NULL DEFAULT 'pending',
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    note        TEXT DEFAULT ''
);
COMMENT ON TABLE archive_exports IS 'Fat export archive (←Archive\Output, Titan3-Backup, Phye.safer opaque store).';

CREATE TABLE external_drug_catalog (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT REFERENCES branches(id),
    create_date DATE,                               -- taronlineeg.CreateDate
    mobile      VARCHAR(15) DEFAULT '',             -- taronlineeg.mobile
    name_en     VARCHAR(200) DEFAULT '',            -- NameEnglish
    name_ar     VARCHAR(200) DEFAULT '',            -- NameArabic
    drugname    VARCHAR(100) DEFAULT '',
    price       NUMERIC(18,4) DEFAULT 0,
    barcode     VARCHAR(16) DEFAULT '',
    status      sync_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE external_drug_catalog IS 'Online EG drug catalog (←taronlineeg 7-col, SCHEMA_RESOLVED §9). Legal feed source: CC0/SFDA, not DrugEye.';

CREATE TABLE price_change_log (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id     BIGINT REFERENCES branches(id),
    drug_id       BIGINT REFERENCES drugs(id),
    barcode       VARCHAR(16) DEFAULT '',
    price         NUMERIC(18,4) DEFAULT 0,
    disco         NUMERIC(5,2)  DEFAULT 0,
    units         INTEGER DEFAULT 0,
    quant         NUMERIC(18,4) DEFAULT 0,
    datee         DATE,
    tips          VARCHAR(50) DEFAULT '',
    country       VARCHAR(50) DEFAULT '',           -- storediscount.country
    storename     VARCHAR(100) DEFAULT '',
    pharmacyname  VARCHAR(100) DEFAULT '',          -- storediscount.pharmacyname (SCHEMA_RESOLVED §8)
    pharmacyname2 VARCHAR(100) DEFAULT '',
    titanver      VARCHAR(50) DEFAULT '',
    pricechanged  BOOLEAN DEFAULT FALSE,
    localimport   INTEGER DEFAULT 0,
    changed_by    BIGINT REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_price_change_log_drug ON price_change_log (branch_id, drug_id);
COMMENT ON TABLE price_change_log IS 'Price/discount change log (←storediscount 16-col, §2.1). AUDIT: price changes also write audit_log.';

CREATE TABLE manual_journal_entries (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    branch_id   BIGINT NOT NULL REFERENCES branches(id),
    record_no   INTEGER,                            -- daily-manual.phy record index (base 44000)
    datee       DATE,
    amount      NUMERIC(18,2) NOT NULL DEFAULT 0,   -- money@0x00 (R4)
    source_file VARCHAR(50) DEFAULT 'daily-manual.phy',
    journal_id  BIGINT REFERENCES journals(id),     -- linked when posted (القيود اليدوية)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE manual_journal_entries IS 'Manual journal money (←daily-manual.phy 52 B / daily-manual-2.phy 56 B, §2.2). AUDIT: manual money writes audit_log.';

CREATE TABLE branch_registry (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mobile       VARCHAR(15) NOT NULL UNIQUE,       -- legacy PK (titanpharmalist.mobile)
    pharmacyname VARCHAR(100) DEFAULT '',
    barcode      VARCHAR(16) DEFAULT '',
    changed      TIMESTAMPTZ,
    apptype      VARCHAR(50) DEFAULT '',
    is_registered BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE branch_registry IS 'Registered-pharmacy registry (←titanpharmalist, §2.1). Sync participants list.';

-- ============================================================================
-- 20. APP CONFIG — VAT/currency country config (§1.11)
-- ============================================================================

CREATE TABLE app_config (
    key           VARCHAR(50) PRIMARY KEY,
    value         TEXT DEFAULT '',
    value_numeric NUMERIC(18,4),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE app_config IS 'Country/currency/VAT config (§1.11). Seed rows: (country, value), (currency, value), (vat_default_rate, value_numeric) — Gulf 15% vs Egypt 14%.';

-- Seed config
INSERT INTO app_config (key, value, value_numeric) VALUES
    ('country', 'SA', NULL),
    ('currency', 'SAR', NULL),
    ('vat_default_rate', NULL, 15.00),
    ('rounding', 'half-up-2dp', NULL);

COMMIT;