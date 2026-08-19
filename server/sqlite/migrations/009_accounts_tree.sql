-- PharmaTag core rev 009 — SQLite twin of alembic 009_accounts_tree.py
-- Legacy chart-of-accounts tree (ticket #16): five roots + intermediates,
-- the legacy-missing leaves, and the rev-002/007 accounts reparented under
-- them. Branch 1 is the only branch the twin seeds (per-branch chart comes
-- from the branch-create tooling, S5.1). Pure seed change; no table change.
INSERT INTO accounts (branch_id, code, name_ar, name_en, type, is_active) VALUES
    (1, '100',  'اصول',                          'Assets',               'asset', 1),
    (1, '110',  'اصول.متداولة',                  'Current Assets',       'asset', 1),
    (1, '200',  'خصوم',                          'Liabilities',          'liability', 1),
    (1, '210',  'خصوم.متداولة',                  'Current Liabilities',  'liability', 1),
    (1, '220',  'خصوم.ثابتة',                    'Fixed Liabilities',    'liability', 1),
    (1, '300',  'حقوق ملكية',                    'Equity',               'equity', 1),
    (1, '400',  'ايرادات',                       'Revenue',              'income', 1),
    (1, '500',  'مصروفات',                       'Expenses',             'expense', 1),
    (1, '1001', 'اصول.متداولة.نقدية.شبكة',       'Network Cash',         'asset', 1),
    (1, '1010', 'اصول.متداولة.بنوك',             'Banks',                'asset', 1),
    (1, '1110', 'اصول.متداولة.ضريبة.قيمة مضافة','Input VAT',            'asset', 1);

-- parent wiring by code (branch 1)
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '100') WHERE branch_id = 1 AND code = '110';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '200') WHERE branch_id = 1 AND code = '210';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '200') WHERE branch_id = 1 AND code = '220';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code = '1000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code = '1001';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code = '1010';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code = '1100';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code = '1110';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '110') WHERE branch_id = 1 AND code = '1200';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '100') WHERE branch_id = 1 AND code = '1300';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '210') WHERE branch_id = 1 AND code = '2000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '210') WHERE branch_id = 1 AND code = '2100';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '210') WHERE branch_id = 1 AND code = '2110';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '300') WHERE branch_id = 1 AND code = '3000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '400') WHERE branch_id = 1 AND code = '4000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '500') WHERE branch_id = 1 AND code = '5000';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '500') WHERE branch_id = 1 AND code = '5900';
UPDATE accounts SET parent_id = (SELECT id FROM accounts p WHERE p.branch_id = 1 AND p.code = '500') WHERE branch_id = 1 AND code = '6000';

-- English display names for the rev-002/007 accounts (empty only)
UPDATE accounts SET name_en = 'Cash Drawer'        WHERE branch_id = 1 AND code = '1000' AND name_en = '';
UPDATE accounts SET name_en = 'Customers (AR)'     WHERE branch_id = 1 AND code = '1100' AND name_en = '';
UPDATE accounts SET name_en = 'Inventory'           WHERE branch_id = 1 AND code = '1200' AND name_en = '';
UPDATE accounts SET name_en = 'Fixed Assets'        WHERE branch_id = 1 AND code = '1300' AND name_en = '';
UPDATE accounts SET name_en = 'Suppliers (AP)'      WHERE branch_id = 1 AND code = '2000' AND name_en = '';
UPDATE accounts SET name_en = 'Output VAT (Sales)'  WHERE branch_id = 1 AND code = '2100' AND name_en = '';
UPDATE accounts SET name_en = 'Output VAT (Purchases)' WHERE branch_id = 1 AND code = '2110' AND name_en = '';
UPDATE accounts SET name_en = 'Capital'             WHERE branch_id = 1 AND code = '3000' AND name_en = '';
UPDATE accounts SET name_en = 'Sales Revenue'       WHERE branch_id = 1 AND code = '4000' AND name_en = '';
UPDATE accounts SET name_en = 'Expenses'            WHERE branch_id = 1 AND code = '5000' AND name_en = '';
UPDATE accounts SET name_en = 'Stock Corrections'   WHERE branch_id = 1 AND code = '5900' AND name_en = '';
UPDATE accounts SET name_en = 'Cost of Goods Sold'  WHERE branch_id = 1 AND code = '6000' AND name_en = '';

-- accounts.manage gates chart-of-accounts writes (admin role 1 + accountant role 4)
INSERT INTO permissions (code, name_ar) VALUES ('accounts.manage', 'إدارة شجرة الحسابات');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id FROM roles r, permissions p
    WHERE p.code = 'accounts.manage' AND r.id IN (1, 4);
