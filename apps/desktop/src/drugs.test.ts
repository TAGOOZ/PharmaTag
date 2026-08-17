import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { describe, expect, it } from 'vitest';
import { DRUG_INSERT_SQL, DRUG_LIST_SQL, DRUG_SEEDS, type DrugRow, seedDrugs } from './drugs';
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

describe('seedDrugs (seed-set-aware idempotency)', () => {
  // tauri-plugin-sql exposes async select/execute; adapt node:sqlite to it.
  function adapter(db: DatabaseSync) {
    return {
      async select<T>(sql: string, params: (string | number)[] = []): Promise<T[]> {
        return db.prepare(sql.replace(/\$\d+/g, '?')).all(...params) as T[];
      },
      async execute(sql: string, params: (string | number)[] = []): Promise<void> {
        db.prepare(sql.replace(/\$\d+/g, '?')).run(...params);
      },
    };
  }

  it('seeds all five rows on an empty table', async () => {
    const db = buildOfflineDb();
    await seedDrugs(adapter(db) as never);
    expect(countDrugs(db)).toBe(DRUG_SEEDS.length);
  });

  it('completes a partially-seeded table without duplicating', async () => {
    const db = buildOfflineDb();
    const panadol = DRUG_SEEDS[0];
    if (!panadol) throw new Error('seed catalog is empty');
    db.prepare(INSERT_SQL).run(
      panadol.drugname,
      panadol.drugnamear,
      panadol.generic,
      panadol.classy,
      panadol.pharmacology,
      panadol.co,
      panadol.unitsclass,
      panadol.taxType,
      panadol.vat,
      panadol.units,
      panadol.unitsmall,
      panadol.price,
      panadol.price_now,
      panadol.priceWholesale,
      panadol.priceCost,
      0,
      1,
    );
    expect(countDrugs(db)).toBe(1);

    await seedDrugs(adapter(db) as never);

    expect(countDrugs(db)).toBe(DRUG_SEEDS.length);
    const names = new Set(
      (db.prepare('SELECT drugname FROM drugs').all() as { drugname: string }[]).map(
        (r) => r.drugname,
      ),
    );
    expect(names.size).toBe(DRUG_SEEDS.length);
  });

  it('leaves a fully-seeded table exactly as-is on re-run', async () => {
    const db = buildOfflineDb();
    seed(db);
    await seedDrugs(adapter(db) as never);
    await seedDrugs(adapter(db) as never);
    expect(countDrugs(db)).toBe(DRUG_SEEDS.length);
  });
});
