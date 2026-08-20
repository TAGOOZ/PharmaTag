-- PharmaTag core rev 013 — SQLite twin of alembic 013_month_close.py
-- Month close (S2.6, ticket #21): a `monthly_close` row archives the period
-- (mirrors monthy\moves) and `month_open_balances` seeds the next month's
-- opening balances (mirrors monthy\start-data). Reopen is manager >= 7 (A07).

CREATE TABLE monthly_close (
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    status    TEXT NOT NULL DEFAULT 'closed',
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
    debit      INTEGER NOT NULL DEFAULT 0 CHECK (1=1),  -- x100
    credit     INTEGER NOT NULL DEFAULT 0 CHECK (1=1),
    PRIMARY KEY (branch_id, account_id, year, month),
    CHECK (month BETWEEN 1 AND 12)
);

-- months.close gates month close (manager/accountant/admin; legacy floor 7)
INSERT INTO permissions (code, name_ar) VALUES ('months.close', 'تقفيل الشهر');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'months.close' AND r.id IN (1, 4, 5);
