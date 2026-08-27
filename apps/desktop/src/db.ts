import Database from '@tauri-apps/plugin-sql';
import { seedDrugs } from './drugs';
import { splitStatements } from './migrations';
import schemaSql from './resources/schema_sqlite.sql?raw';

/**
 * Minimal SQL port the offline bootstrap needs — the tauri-plugin-sql Database
 * implements it, and node:sqlite can stand in during tests.
 */
export interface SqlRunner {
  select<T>(sql: string): Promise<T[]>;
  execute(sql: string): Promise<unknown>;
}

/**
 * Idempotent first-run schema application (plan/03 §4.1). Applies the bundled
 * `schema_sqlite.sql` twin only when the `branches` table is missing, so a
 * repeated boot is a no-op. Pure enough to exercise against a real SQLite file
 * in tests (offline: no Tauri plugin, no network).
 */
export async function bootstrapSchema(db: SqlRunner, schemaSqlText: string): Promise<void> {
  const alreadyMigrated = await db.select<{ name: string }[]>(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'branches'",
  );
  if (alreadyMigrated.length === 0) {
    for (const statement of splitStatements(schemaSqlText)) {
      await db.execute(statement);
    }
  }
}

/**
 * Backfill for existing desktop DBs created before #53 (and #34/#26).
 * `bootstrapSchema` is one-shot (guarded on `branches`), so old DBs never
 * receive new `report_catalog` rows or permission seeds. This runs on every
 * boot, idempotently, via `INSERT OR IGNORE`.
 */
export async function upgradeExistingDb(db: SqlRunner): Promise<void> {
  const hasCatalog = await db.select<{ name: string }[]>(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'report_catalog'",
  );
  if (hasCatalog.length === 0) return;
  // report_catalog backfill (016_day_totals + 017_stock + 018-022 + 033/034)
  await db.execute(
    `INSERT OR IGNORE INTO report_catalog (code, category, title_ar, title_en, params, paper, sort) VALUES
    ('day_totals', 'money', 'الإجماليات اليومية', 'Day Totals', '["date_from", "date_to"]', 'A4', 25),
    ('stock_current', 'stock', 'رصيد الأصناف', 'Current Stock', '[]', 'A4', 50),
    ('stock_movements', 'stock', 'تتبع تغيير الرصيد', 'Drug Movement Track', '["drug_id", "date_from", "date_to"]', 'A4', 60),
    ('stock_expired', 'stock', 'الادوية منتهية الصلاحية', 'Expired / Expiring Stock', '["datee", "horizon_days"]', 'A4', 70),
    ('stock_needs', 'stock', 'احتياجات الطلب (الحد الأدنى)', 'Order Needs (Minimum-Based)', '[]', 'A4', 80),
    ('sales_invoices', 'sales', 'فواتير المبيعات', 'Sales Invoices', '["date_from", "date_to"]', 'A4', 90),
    ('purchase_invoices', 'sales', 'فواتير المشتريات', 'Purchase Invoices', '["date_from", "date_to"]', 'A4', 100),
    ('returns_period', 'sales', 'مرتجعات الفترة', 'Period Returns', '["date_from", "date_to"]', 'A4', 110),
    ('party_totals', 'sales', 'إجمالي العملاء والموردين', 'Customer & Supplier Totals', '["date_from", "date_to"]', 'A4', 120),
    ('ledger_account', 'accounting', 'دفتر الأستاذ لحساب', 'Ledger by Account', '["account_code", "month", "year", "date_from", "date_to"]', 'A4', 130),
    ('vat_summary', 'accounting', 'ملخص ضريبة القيمة المضافة', 'VAT Summary (Form 10)', '["month", "year", "date_from", "date_to"]', 'A4', 140),
    ('chain_sales', 'chain', 'مبيعات السلسلة', 'Chain Sales Summary', '["date_from", "date_to"]', 'A4', 200),
    ('chain_stock', 'chain', 'مخزون السلسلة', 'Chain Stock Snapshot', '[]', 'A4', 210)`,
  );
  await db.execute(
    `UPDATE report_catalog SET params = '["datee", "date_from", "date_to"]' WHERE code = 'day_profit' AND params = '["datee"]'`,
  );
  // permission backfills (014,026,027,034)
  await db.execute(
    `INSERT OR IGNORE INTO permissions (code, name_ar) VALUES
    ('opening_balances.manage', 'الأرصدة الافتتاحية'),
    ('branches.manage', 'إدارة الفروع والأجهزة'),
    ('transfers.manage', 'إدارة التحويلات بين الفروع'),
    ('stock.manage', 'إدارة المخزون')`,
  );
  // role grants for the 4 permissions (INSERT OR IGNORE for idempotency)
  await db.execute(
    `INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
     SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'opening_balances.manage' AND r.id IN (1, 4, 5)`,
  );
  await db.execute(
    `INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
     SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'branches.manage' AND r.id IN (1, 5)`,
  );
  await db.execute(
    `INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
     SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'transfers.manage' AND r.id IN (1, 2, 5)`,
  );
  await db.execute(
    `INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
     SELECT r.id, p.id FROM roles r, permissions p WHERE p.code = 'stock.manage' AND r.id IN (1, 2, 5)`,
  );
}

/**
 * Offline-first SQLite bootstrap (plan/03 §4.1, A01).
 * DB lives in the OS app-data dir (file-backable, survives restarts); the
 * canonical `schema/schema_sqlite.sql` twin is applied on first run, then the
 * S0.3 drug-master seed (same rows as alembic rev 003) so the disconnected
 * desktop shows the same catalog as the API (ticket #6).
 */
export async function initDb(): Promise<Database> {
  const db = await Database.load('sqlite:pharmatag.db');
  await bootstrapSchema(db, schemaSql);
  await upgradeExistingDb(db);
  await seedDrugs(db);
  return db;
}
