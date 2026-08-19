-- PharmaTag core rev 012 — SQLite twin of alembic 012_settlement_vouchers.py
-- Settlement vouchers (S2.4, ticket #19): a سند قبض (receipt) and a سند صرف
-- (payment voucher) post to the journal engine (source 'settlement'), update
-- balances, and record the drawer movement. reverses_voucher_id links an
-- A07-style reversal back to the voucher it offsets.
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

-- receivables.manage gates settlement posting + reversal (admin role 1,
-- accountant role 4, manager role 5; legacy floor 7)
INSERT INTO permissions (code, name_ar) VALUES ('receivables.manage', 'تحصيل وسداد الآجل');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'receivables.manage' AND r.id IN (1, 4, 5);