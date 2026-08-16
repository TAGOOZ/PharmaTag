"""core rev 002 — seed data (plan/01 §5.2)

Seeds: one main branch (EG/EGP/14% VAT-inclusive), admin superuser (G08:
permission_level 9 + admin role), roles/permissions (legacy الصلاحية 1-9
surface + module codes; admin → all), a default per-branch chart of accounts
(feature_balances.md:240 template), and app_config (EG/EGP/14%, half-up-2dp,
vat_inclusive_prices, plugins_enabled — correction §1.3#5, G06, A08).
Opening receivables/payables are NOT hardcoded (plan/01 §5.2: seeded via
opening journal entries at cutover, not in seeds).

Uses explicit, deterministic IDs (rev 002 runs once on a fresh schema where
identity starts at 1), so the migration also renders in offline SQL mode.

Revision ID: 002_seeds
Revises: 001_core
"""
from alembic import op
import sqlalchemy as sa

revision = "002_seeds"
down_revision = "001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- app_config (correction §1.3#5: Egypt-first, EG/EGP/14%) ---
    op.execute(sa.text("""
        INSERT INTO app_config (key, value, value_numeric) VALUES
            ('country', 'EG', NULL),
            ('currency', 'EGP', NULL),
            ('vat_default_rate', NULL, 14.00),
            ('rounding', 'half-up-2dp', NULL),
            ('vat_inclusive_prices', 'true', NULL),
            ('plugins_enabled', 'true', NULL)
    """))

    # --- main branch (wzphar seed; G06 vat_inclusive_prices=true) ---
    op.execute(sa.text("""
        INSERT INTO branches
            (id, pharmacyid, phar, mobile, pharname, vat_default, vat_inclusive_prices,
             is_main_device, is_active)
        OVERRIDING SYSTEM VALUE
        VALUES (1, 'MAIN', 'MAIN', '01000000000', 'Main Pharmacy', 14.00, true, true, true)
    """))

    # --- permissions: legacy الصلاحية 1-9 + module codes ---
    op.execute(sa.text("""
        INSERT INTO permissions (id, code, name_ar)
        OVERRIDING SYSTEM VALUE
        VALUES
            (1,  '1',               'المبيعات'),
            (2,  '2',               'المشتريات'),
            (3,  '3',               'الأصناف والمخزون'),
            (4,  '4',               'العملاء والموردين'),
            (5,  '5',               'الخزينة والأمانات'),
            (6,  '6',               'الصلاحيات والمستخدمين'),
            (7,  '7',               'إغلاق اليوم'),
            (8,  '8',               'تعديل الفواتير'),
            (9,  '9',               'التقارير'),
            (10, 'sale.create',     'بيع'),
            (11, 'sale.edit_invoice', 'تعديل فاتورة'),
            (12, 'day.close',       'إغلاق اليوم'),
            (13, 'stock.adjust',    'تعديل رصيد'),
            (14, 'approvals',       'الموافقات'),
            (15, 'reports',         'التقارير'),
            (16, 'users.manage',    'إدارة المستخدمين')
    """))

    # --- roles: admin/pharmacist/cashier/accountant/manager (plan/01 §5.2) ---
    op.execute(sa.text("""
        INSERT INTO roles (id, name)
        OVERRIDING SYSTEM VALUE
        VALUES
            (1, 'admin'), (2, 'pharmacist'), (3, 'cashier'),
            (4, 'accountant'), (5, 'manager')
    """))

    # admin → all permissions
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT 1, id FROM permissions
    """))
    # manager → operational subset (no user management)
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id) VALUES
            (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15)
    """))
    # accountant → reports/approvals
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id) VALUES
            (4, 14), (4, 15)
    """))
    # pharmacist/cashier → sale.create
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id) VALUES
            (2, 10), (3, 10)
    """))

    # --- admin superuser (G08: permission_level 9; pass_hash set by T02) ---
    op.execute(sa.text("""
        INSERT INTO users (id, username, namee, pass_hash, permission_level, branch_id, active)
        OVERRIDING SYSTEM VALUE
        VALUES (1, 'admin', 'Administrator', 'changeme', 9, 1, true)
    """))
    op.execute(sa.text("INSERT INTO user_roles (user_id, role_id) VALUES (1, 1)"))

    # --- default chart of accounts (feature_balances.md:240 template) ---
    op.execute(sa.text("""
        INSERT INTO accounts (id, branch_id, code, name_ar, type, is_active)
        OVERRIDING SYSTEM VALUE
        VALUES
            (1,  1, '1000', 'اصول.متداولة.خزينة/درج', 'asset', true),
            (2,  1, '1100', 'اصول.متداولة.عملاء',     'asset', true),
            (3,  1, '1200', 'اصول.متداولة.مخزون',    'asset', true),
            (4,  1, '1300', 'اصول.ثابتة',            'asset', true),
            (5,  1, '2000', 'خصوم.متداولة.موردين',   'liability', true),
            (6,  1, '2100', 'خصوم.ضريبة.مبيعات',     'liability', true),
            (7,  1, '2110', 'خصوم.ضريبة.مشتريات',    'liability', true),
            (8,  1, '3000', 'حقوق ملكية.راس المال',  'equity', true),
            (9,  1, '4000', 'ايرادات.مبيعات',        'income', true),
            (10, 1, '5000', 'مصروفات',               'expense', true),
            (11, 1, '6000', 'تكلفة المبيعات',        'expense', true)
    """))

    # --- default plugin host rows: pilot plugins registered as installed (A10) ---
    op.execute(sa.text("""
        INSERT INTO app_plugins (id, slug, name_ar, name_en, version, core_requires, sdk_version)
        OVERRIDING SYSTEM VALUE
        VALUES
            (1, 'pharmatag-eta',    'الفوترة الإلكترونية', 'E-invoicing (ETA)',      '0.0.0', '>=0.1.0,<1.0.0', '0.1.0'),
            (2, 'pharmatag-ledger', 'المحاسبة',           'Accounting & Ledger',    '0.0.0', '>=0.1.0,<1.0.0', '0.1.0')
    """))
    op.execute(sa.text("""
        INSERT INTO plugin_branch_grants (plugin_id, branch_id, enabled)
        VALUES (1, 1, false), (2, 1, false)
    """))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM plugin_branch_grants"))
    op.execute(sa.text("DELETE FROM app_plugins"))
    op.execute(sa.text("DELETE FROM accounts"))
    op.execute(sa.text("DELETE FROM user_roles"))
    op.execute(sa.text("DELETE FROM users"))
    op.execute(sa.text("DELETE FROM role_permissions"))
    op.execute(sa.text("DELETE FROM roles"))
    op.execute(sa.text("DELETE FROM permissions"))
    op.execute(sa.text("DELETE FROM branches"))
    op.execute(sa.text("DELETE FROM app_config"))