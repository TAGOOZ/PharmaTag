import Database from '@tauri-apps/plugin-sql';
import { seedDrugs } from './drugs';
import { splitStatements } from './migrations';
import schemaSql from './resources/schema_sqlite.sql?raw';

/**
 * Offline-first SQLite bootstrap (plan/03 §4.1, A01).
 * DB lives in the OS app-data dir (file-backable, survives restarts); the
 * canonical `schema/schema_sqlite.sql` twin is applied on first run, then the
 * S0.3 drug-master seed (same rows as alembic rev 003) so the disconnected
 * desktop shows the same catalog as the API (ticket #6).
 */
export async function initDb(): Promise<Database> {
  const db = await Database.load('sqlite:pharmatag.db');
  const alreadyMigrated = await db.select<{ name: string }[]>(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'branches'",
  );
  if (alreadyMigrated.length === 0) {
    for (const statement of splitStatements(schemaSql)) {
      await db.execute(statement);
    }
  }
  await seedDrugs(db);
  return db;
}
