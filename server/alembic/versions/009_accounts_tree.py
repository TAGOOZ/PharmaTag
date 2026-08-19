"""core rev 009 — legacy chart-of-accounts tree + accounts.manage (ticket #16)

S2.1 (plan/05 §S2.1) turns the flat rev-002 chart into the hierarchical legacy
tree (wzaccfreetree master/fary → parent_id, feature_balances.md §9): five
roots (اصول / خصوم / حقوق ملكية / ايرادات / مصروفات), two intermediates
(اصول.متداولة, خصوم.متداولة), the legacy-missing leaves (نقدية.شبكة, بنوك,
input-VAT asset, خصوم.ثابتة), and the existing rev-002/007 accounts reparented
under them. Pure seed change — no table/column change.

* Wired by CODE within each branch (self-join UPDATE), never by hardcoded id,
  so it is robust on any DB state: a real legacy-migrated pharmacy keeps its
  custom account names (NOT EXISTS guard skips existing codes; name_en fills
  only when empty) and every branch that exists at migration time gets the
  full tree (per-branch COA, same pattern as rev 007's 5900).
* New leaves use codes that never collide with the posting-critical journal
  codes (1000/1100/1200/2000/2100/4000/5000/6000/5900) — those stay leaves
  with their codes intact, so the sale/purchase/return posting engine is
  unaffected.
* `accounts.manage` (إدارة شجرة الحسابات) gates chart-of-accounts writes —
  the ledger area's coarse floor is 7 (plan/02 §3 "balance edits" ≥ 7) and the
  granular code is granted to BOTH the admin role (role 1) and the accountant
  role (role 4), since chart maintenance is an accounting duty.

Revision ID: 009_accounts_tree
Revises: 008_correction_decision_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "009_accounts_tree"
down_revision = "008_correction_decision_fields"
branch_labels = None
depends_on = None


# the 11 account rows migration 009 adds on top of the rev-002/007 chart.
# codes/names follow the legacy dotted hierarchy (feature_balances.md §9).
_NEW_ACCOUNTS = """
    ('100',  'اصول',                           'Assets',               'asset'),
    ('110',  'اصول.متداولة',                   'Current Assets',       'asset'),
    ('200',  'خصوم',                           'Liabilities',          'liability'),
    ('210',  'خصوم.متداولة',                   'Current Liabilities',  'liability'),
    ('220',  'خصوم.ثابتة',                     'Fixed Liabilities',    'liability'),
    ('300',  'حقوق ملكية',                     'Equity',               'equity'),
    ('400',  'ايرادات',                        'Revenue',              'income'),
    ('500',  'مصروفات',                        'Expenses',             'expense'),
    ('1001', 'اصول.متداولة.نقدية.شبكة',        'Network Cash',         'asset'),
    ('1010', 'اصول.متداولة.بنوك',              'Banks',                'asset'),
    ('1110', 'اصول.متداولة.ضريبة.قيمة مضافة', 'Input VAT',            'asset')
"""

# child_code -> parent_code (within the same branch)
_PARENT_PAIRS = """
    ('110','100'), ('210','200'), ('220','200'),
    ('1000','110'), ('1001','110'), ('1010','110'),
    ('1100','110'), ('1110','110'), ('1200','110'),
    ('1300','100'),
    ('2000','210'), ('2100','210'), ('2110','210'),
    ('3000','300'), ('4000','400'), ('5000','500'),
    ('5900','500'), ('6000','500')
"""

# English backfill for the rev-002/007 accounts (only when name_en is empty —
# a real legacy-migrated install's own names are never clobbered).
_ENGLISH_BACKFILL = """
    ('1000','Cash Drawer'), ('1100','Customers (AR)'), ('1200','Inventory'),
    ('1300','Fixed Assets'), ('2000','Suppliers (AP)'), ('2100','Output VAT (Sales)'),
    ('2110','Output VAT (Purchases)'), ('3000','Capital'), ('4000','Sales Revenue'),
    ('5000','Expenses'), ('5900','Stock Corrections'), ('6000','Cost of Goods Sold')
"""


def upgrade() -> None:
    # 1. the tree nodes, inserted for EVERY branch that exists at migration time
    op.execute(sa.text(f"""
        INSERT INTO accounts (branch_id, code, name_ar, name_en, type, is_active)
        SELECT b.id, t.code, t.name_ar, t.name_en, t.type::account_type, true
        FROM branches b
        JOIN (VALUES
            {_NEW_ACCOUNTS}
        ) AS t(code, name_ar, name_en, type) ON true
        WHERE NOT EXISTS (
            SELECT 1 FROM accounts a
            WHERE a.branch_id = b.id AND a.code = t.code
        )
    """))

    # 2. parent wiring by code within each branch (never hardcoded ids)
    op.execute(sa.text(f"""
        UPDATE accounts
        SET parent_id = p.id
        FROM accounts p
        JOIN (VALUES
            {_PARENT_PAIRS}
        ) AS t(code, parent_code) ON p.code = t.parent_code
        WHERE accounts.code = t.code AND accounts.branch_id = p.branch_id
    """))

    # 3. English display names for the rev-002/007 accounts (empty only)
    op.execute(sa.text(f"""
        UPDATE accounts
        SET name_en = t.name_en
        FROM (VALUES
            {_ENGLISH_BACKFILL}
        ) AS t(code, name_en)
        WHERE accounts.code = t.code AND accounts.name_en = ''
    """))

    # 4. accounts.manage — chart-of-accounts writes (admin + accountant)
    op.execute(sa.text("""
        INSERT INTO permissions (code, name_ar)
        VALUES ('accounts.manage', 'إدارة شجرة الحسابات')
    """))
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE p.code = 'accounts.manage' AND r.id IN (1, 4)
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'accounts.manage')"
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'accounts.manage'"))
    # unwire the parents that pointed into the tree nodes, then drop the nodes
    op.execute(sa.text(f"""
        UPDATE accounts
        SET parent_id = NULL
        WHERE parent_id IN (
            SELECT id FROM accounts WHERE code IN (
                '100','110','200','210','220','300','400','500',
                '1001','1010','1110'
            )
        )
    """))
    op.execute(sa.text("""
        DELETE FROM accounts
        WHERE code IN ('100','110','200','210','220','300','400','500',
                       '1001','1010','1110')
    """))
