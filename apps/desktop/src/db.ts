import Database from '@tauri-apps/plugin-sql';
import { splitStatements } from './migrations';
import schemaSql from './resources/schema_sqlite.sql?raw';

/**
 * Offline-first SQLite bootstrap (plan/03 §4.1, A01).
 * DB lives in the OS app-data dir (file-backable, survives restarts); the
 * canonical `schema/schema_sqlite.sql` twin is applied on first run.
 */
export async function initDb(): Promise<Database> {
  const db = await Database.load('sqlite:pharmatag.db');
  const alreadyMigrated = await db.select<{ name: string }[]>(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'branches'",
  );
  if (alreadyMigrated.length > 0) return db;

  for (const statement of splitStatements(schemaSql)) {
    await db.execute(statement);
  }
  return db;
}
