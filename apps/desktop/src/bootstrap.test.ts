import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { bootstrapSchema, type SqlRunner } from './db';

/**
 * The offline-first bootstrap (plan/03 §4.1) exercised against a REAL SQLite
 * database — no Tauri plugin, no network. The SqlRunner port lets node:sqlite
 * stand in for the tauri-plugin-sql Database.
 */
const here = dirname(fileURLToPath(import.meta.url));
const schemaSql = readFileSync(join(here, 'resources', 'schema_sqlite.sql'), 'utf8');

class NodeSqliteRunner implements SqlRunner {
  constructor(private readonly db: DatabaseSync) {}

  async select<T>(sql: string): Promise<T[]> {
    return this.db.prepare(sql).all() as T[];
  }

  async execute(sql: string): Promise<unknown> {
    return this.db.exec(sql);
  }
}

function openInMemory(): { db: DatabaseSync; runner: NodeSqliteRunner } {
  const db = new DatabaseSync(':memory:');
  return { db, runner: new NodeSqliteRunner(db) };
}

function tableNames(db: DatabaseSync): string[] {
  return (
    db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
      .all() as { name: string }[]
  ).map((row) => row.name);
}

describe('bootstrapSchema (first-run offline schema application)', () => {
  it('applies the full 52-table schema on first boot (branches guard)', async () => {
    const { db, runner } = openInMemory();
    expect(tableNames(db)).toEqual([]);
    await bootstrapSchema(runner, schemaSql);
    const names = tableNames(db);
    expect(names).toContain('branches');
    expect(names.length).toBe(52);
  });

  it('is idempotent — a second boot is a no-op, never duplicate tables', async () => {
    const { db, runner } = openInMemory();
    await bootstrapSchema(runner, schemaSql);
    const afterFirst = tableNames(db).length;
    await bootstrapSchema(runner, schemaSql);
    expect(tableNames(db).length).toBe(afterFirst);
    expect(tableNames(db)).toContain('branches');
  });

  it('supports offline reads and writes right after bootstrap (no Tauri, no network)', async () => {
    const { db, runner } = openInMemory();
    await bootstrapSchema(runner, schemaSql);
    db.exec(
      "INSERT INTO branches (pharmacyid, mobile, pharname) VALUES ('br-1', '0100', 'أوليفر فارماسي')",
    );
    const row = db.prepare("SELECT pharname FROM branches WHERE pharmacyid = 'br-1'").get() as {
      pharname: string;
    };
    expect(row.pharname).toBe('أوليفر فارماسي');
  });

  it('skips schema application when the branches table already exists', async () => {
    const { db, runner } = openInMemory();
    db.exec('CREATE TABLE branches (id INTEGER PRIMARY KEY)');
    await bootstrapSchema(runner, schemaSql);
    expect(tableNames(db)).toEqual(['branches']);
  });
});
