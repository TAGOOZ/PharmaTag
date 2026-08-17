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
 * Money is INTEGER minor units (plan/01 §4.2): price/price_now ×10000,
 * vat rate ×100. Medicines are VAT-exempt (G06): tax_type 'exempt', vat 0.
 * price_wholesale/price_cost repeat the public price (rev 005 backfill).
 */
export interface SeedDrug {
  drugname: string;
  drugnamear: string;
  generic: string;
  classy: string;
  pharmacology: string;
  co: string;
  unitsclass: string;
  taxType: string;
  vat: number;
  units: number;
  unitsmall: number;
  price: number;
  price_now: number;
  priceWholesale: number;
  priceCost: number;
}

export const DRUG_SEEDS: SeedDrug[] = [
  {
    drugname: 'Panadol Extra',
    drugnamear: 'بانادول إكسترا',
    generic: 'paracetamol + caffeine',
    classy: 'analgesic',
    pharmacology: '',
    co: 'GSK',
    unitsclass: 'pack',
    taxType: 'exempt',
    vat: 0,
    units: 24,
    unitsmall: 0,
    price: 125000,
    price_now: 125000,
    priceWholesale: 125000,
    priceCost: 125000,
  },
  {
    drugname: 'Augmentin 1g',
    drugnamear: 'أوجمنتين',
    generic: 'amoxicillin/clavulanate',
    classy: 'antibiotic',
    pharmacology: '',
    co: 'GSK',
    unitsclass: 'pack',
    taxType: 'exempt',
    vat: 0,
    units: 14,
    unitsmall: 0,
    price: 480000,
    price_now: 480000,
    priceWholesale: 480000,
    priceCost: 480000,
  },
  {
    drugname: 'Amaryl 2mg',
    drugnamear: 'أماريل',
    generic: 'glimepiride',
    classy: 'antidiabetic',
    pharmacology: '',
    co: 'Sanofi',
    unitsclass: 'pack',
    taxType: 'exempt',
    vat: 0,
    units: 30,
    unitsmall: 0,
    price: 287500,
    price_now: 287500,
    priceWholesale: 287500,
    priceCost: 287500,
  },
  {
    drugname: 'Cataflam 50mg',
    drugnamear: 'كاتافلام',
    generic: 'diclofenac potassium',
    classy: 'antiinflammatory',
    pharmacology: '',
    co: 'Novartis',
    unitsclass: 'pack',
    taxType: 'exempt',
    vat: 0,
    units: 20,
    unitsmall: 0,
    price: 150000,
    price_now: 150000,
    priceWholesale: 150000,
    priceCost: 150000,
  },
  {
    drugname: 'Ventolin Inhaler',
    drugnamear: 'فينتولين',
    generic: 'salbutamol',
    classy: 'bronchodilator',
    pharmacology: '',
    co: 'GSK',
    unitsclass: 'pack',
    taxType: 'exempt',
    vat: 0,
    units: 1,
    unitsmall: 0,
    price: 225000,
    price_now: 225000,
    priceWholesale: 225000,
    priceCost: 225000,
  },
];

/** Minor-unit scale for money (plan/01 §4.2): NUMERIC(18,4) <-> INTEGER ×10000. */
export const PRICE_MINOR_UNIT = 10000;

/**
 * Insert the seed catalog (idempotent): only the drugnames still missing are
 * inserted, so a partial table is completed instead of permanently suppressed.
 */
export async function seedDrugs(db: Database): Promise<void> {
  const placeholders = DRUG_SEEDS.map((_, i) => `$${i + 1}`).join(',');
  const rows = await db.select<{ drugname: string }[]>(
    `SELECT drugname FROM drugs WHERE drugname IN (${placeholders})`,
    DRUG_SEEDS.map((d) => d.drugname),
  );
  const existing = new Set(rows.map((r) => r.drugname));
  for (const drug of DRUG_SEEDS) {
    if (existing.has(drug.drugname)) continue;
    await db.execute(DRUG_INSERT_SQL, [
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
   (drugname, drugnamear, generic, classy, pharmacology, co, unitsclass,
    tax_type, vat, units, unitsmall, price, price_now, price_wholesale,
    price_cost, disco, active)
 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)`;

export const DRUG_LIST_SQL = `SELECT id, drugname, drugnamear, price, units
 FROM drugs WHERE active = 1 ORDER BY drugname`;
