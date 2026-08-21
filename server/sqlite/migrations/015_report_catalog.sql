-- PharmaTag core rev 015 — SQLite twin of alembic 015_report_catalog.py
-- Report framework (S3.1, ticket #23): `report_catalog` is the RPT menu +
-- dispatch key (later report slices add rows, not code); `print_jobs` is the
-- durable print queue. Seeds mirror alembic 015 exactly.

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
