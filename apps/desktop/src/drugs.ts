import type Database from '@tauri-apps/plugin-sql';

/**
 * Offline drug-master seed for the desktop (ticket #6 / S0.3).
 *
 * The desktop is deliberately disconnected: it reads the drug master from its
 * local SQLite twin, never from the API. These are the SAME rows seeded into
 * Postgres by alembic rev 003 (`server/alembic/versions/003_drug_seeds.py`)
 * and the SQLite twin (`server/sqlite/migrations/003_drug_seeds.sql`), so web
 * (via API) and desktop (offline) render the identical list.
 *
 * The desktop twin schema predates `tax_type`, so medicines (all VAT-exempt
 * per G06) are seeded without a tax column here.
 */
export interface SeedDrug {
  drugname: string;
  drugnamear: string;
  generic: string;
  classy: string;
  co: string;
  units: number;
  unitsmall: number;
  price: number;
  price_now: number;
}

export const DRUG_SEEDS: SeedDrug[] = [
  {
    drugname: 'Panadol Extra',
    drugnamear: 'بانادول إكسترا',
    generic: 'paracetamol + caffeine',
    classy: 'analgesic',
    co: 'GSK',
    units: 24,
    unitsmall: 0,
    price: 12.5,
    price_now: 12.5,
  },
  {
    drugname: 'Augmentin 1g',
    drugnamear: 'أوجمنتين',
    generic: 'amoxicillin/clavulanate',
    classy: 'antibiotic',
    co: 'GSK',
    units: 14,
    unitsmall: 0,
    price: 48,
    price_now: 48,
  },
  {
    drugname: 'Amaryl 2mg',
    drugnamear: 'أماريل',
    generic: 'glimepiride',
    classy: 'antidiabetic',
    co: 'Sanofi',
    units: 30,
    unitsmall: 0,
    price: 28.75,
    price_now: 28.75,
  },
  {
    drugname: 'Cataflam 50mg',
    drugnamear: 'كاتافلام',
    generic: 'diclofenac potassium',
    classy: 'antiinflammatory',
    co: 'Novartis',
    units: 20,
    unitsmall: 0,
    price: 15,
    price_now: 15,
  },
  {
    drugname: 'Ventolin Inhaler',
    drugnamear: 'فينتولين',
    generic: 'salbutamol',
    classy: 'bronchodilator',
    co: 'GSK',
    units: 1,
    unitsmall: 0,
    price: 22.5,
    price_now: 22.5,
  },
];

/** Insert the seed catalog on first run (idempotent: skips a non-empty table). */
export async function seedDrugs(db: Database): Promise<void> {
  const count = await db.select<{ n: number }[]>('SELECT COUNT(*) AS n FROM drugs');
  if (count[0] && count[0].n > 0) return;

  for (const drug of DRUG_SEEDS) {
    await db.execute(DRUG_INSERT_SQL, [
      drug.drugname,
      drug.drugnamear,
      drug.generic,
      drug.classy,
      drug.co,
      drug.units,
      drug.unitsmall,
      drug.price,
      drug.price_now,
      0,
      1,
    ]);
  }
}

export interface DrugRow {
  id: number;
  drugname: string;
  drugnamear: string;
  price: number;
  units: number;
}

/** Active drug master read from the offline SQLite twin. */
export async function listDrugs(db: Database): Promise<DrugRow[]> {
  return db.select<DrugRow[]>(DRUG_LIST_SQL);
}

// Shared SQL (exported so the offline read is verifiable against a real
// SQLite engine in tests without the Tauri runtime).
export const DRUG_INSERT_SQL = `INSERT INTO drugs
   (drugname, drugnamear, generic, classy, co, units, unitsmall,
    price, price_now, disco, active)
 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`;

export const DRUG_LIST_SQL = `SELECT id, drugname, drugnamear, price, units
 FROM drugs WHERE active = 1 ORDER BY drugname`;
