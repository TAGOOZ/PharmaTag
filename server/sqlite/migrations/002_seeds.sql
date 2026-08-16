-- PharmaTag core rev 002 — SQLite seeds (mirrors alembic 002_seeds.py)
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

-- default chart of accounts (per-branch template)
INSERT INTO accounts (branch_id, code, name_ar, type, is_active) VALUES
    (1, '1000', 'اصول.متداولة.خزينة/درج', 'asset', 1),
    (1, '1100', 'اصول.متداولة.عملاء', 'asset', 1),
    (1, '1200', 'اصول.متداولة.مخزون', 'asset', 1),
    (1, '1300', 'اصول.ثابتة', 'asset', 1),
    (1, '2000', 'خصوم.متداولة.موردين', 'liability', 1),
    (1, '2100', 'خصوم.ضريبة.مبيعات', 'liability', 1),
    (1, '2110', 'خصوم.ضريبة.مشتريات', 'liability', 1),
    (1, '3000', 'حقوق ملكية.راس المال', 'equity', 1),
    (1, '4000', 'ايرادات.مبيعات', 'income', 1),
    (1, '5000', 'مصروفات', 'expense', 1),
    (1, '6000', 'تكلفة المبيعات', 'expense', 1);

-- pilot plugins registered (A10), disabled until the plugin ships
INSERT INTO app_plugins (slug, name_ar, name_en, version, core_requires, sdk_version, status)
VALUES
    ('pharmatag-eta', 'الفوترة الإلكترونية', 'E-invoicing (ETA)', '0.0.0', '>=0.1.0,<1.0.0', '0.1.0', 'installed'),
    ('pharmatag-ledger', 'المحاسبة', 'Accounting & Ledger', '0.0.0', '>=0.1.0,<1.0.0', '0.1.0', 'installed');

INSERT INTO plugin_branch_grants (plugin_id, branch_id, enabled)
SELECT id, 1, 0 FROM app_plugins;