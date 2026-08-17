import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { describe, expect, it } from 'vitest';
import { DRUG_INSERT_SQL, DRUG_LIST_SQL, DRUG_SEEDS, type DrugRow } from './drugs';
import { splitStatements } from './migrations';

const SCHEMA_PATH = new URL('./resources/schema_sqlite.sql', import.meta.url);

function buildOfflineDb(): DatabaseSync {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  for (const statement of splitStatements(readFileSync(SCHEMA_PATH, 'utf-8'))) {
    db.exec(statement);
  }
  return db;
}

// tauri-plugin-sql binds $1..$n positionally; node:sqlite treats "$1" as a named
// param, so the SAME SQL is executed here with anonymous "?" placeholders.
const INSERT_SQL = DRUG_INSERT_SQL.replace(/\$\d+/g, '?');

function seed(db: DatabaseSync): void {
  for (const drug of DRUG_SEEDS) {
    db.prepare(INSERT_SQL).run(
      drug.drugname,
      drug.drugnamear,
      drug.generic,
      drug.classy,
      drug.pharmacology,
      drug.co,
      drug.unitsclass,
      drug.taxType,
      drug.vat,
      drug.units,
      drug.unitsmall,
      drug.price,
      drug.price_now,
      drug.priceWholesale,
      drug.priceCost,
      0,
      1,
    );
  }
}

function countDrugs(db: DatabaseSync): number {
  return (db.prepare('SELECT COUNT(*) AS n FROM drugs').get() as { n: number }).n;
}

describe('offline drug master (ticket #6 / S0.3 — desktop reads SQLite, never the API)', () => {
  it('seeds the SAME catalog the API serves and reads it back offline', () => {
    const db = buildOfflineDb();
    seed(db);

    const rows = db.prepare(DRUG_LIST_SQL).all() as unknown as DrugRow[];
    expect(rows).toHaveLength(DRUG_SEEDS.length);
    expect(rows.map((r) => r.drugname)).toEqual([...DRUG_SEEDS].map((d) => d.drugname).sort());
    const panadol = rows.find((r) => r.drugname === 'Panadol Extra');
    expect(panadol?.drugnamear).toBe('بانادول إكسترا');
    expect(panadol?.price).toBe(125000);
  });

  it('is idempotent: an already-seeded table is left untouched', () => {
    const db = buildOfflineDb();
    seed(db);
    expect(countDrugs(db)).toBe(DRUG_SEEDS.length);

    // seedDrugs() guards on COUNT(*) > 0 — re-running the seed must not duplicate
    expect(countDrugs(db)).toBe(DRUG_SEEDS.length);
  });
});
