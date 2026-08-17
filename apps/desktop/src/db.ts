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
 * Offline-first SQLite bootstrap (plan/03 §4.1, A01).
 * DB lives in the OS app-data dir (file-backable, survives restarts); the
 * canonical `schema/schema_sqlite.sql` twin is applied on first run, then the
 * S0.3 drug-master seed (same rows as alembic rev 003) so the disconnected
 * desktop shows the same catalog as the API (ticket #6).
 */
export async function initDb(): Promise<Database> {
  const db = await Database.load('sqlite:pharmatag.db');
  await bootstrapSchema(db, schemaSql);
  await seedDrugs(db);
  return db;
}
