# Legacy `.phy` Historical Import — runbook

Toolchain: `legacy_import/` — converts TITAN.W1 VB6 fixed-record `.phy` money files
into normalized JSONL, then loads into the new schema (SQLite / PostgreSQL).

## How `.phy` files work

VB6 `Open ... For Random As #n Len = L`:
- No header. Record *k* starts at byte `(k-1)*L`.
- Each field is a fixed-size VB type:
  `I2`=int16 LE, `I4`=int32 LE, `R4`=float32 LE, `R8`=float64 LE,
  `CURR`=int64/10000, `STR`=fixed bytes, `BOOL`=int16, `VAR`=16-byte Variant.
- Record 1 is the first record (not 0). Offsets in `RECORD_LAYOUTS_daily_phy.md`
  and `PHY_MIGRATION.md` are 0-based byte offsets into the record.

## 1. Collect the legacy data

Copy the whole `Files\DBI` directory from the legacy TITAN.W1 install:

    Files\DBI\*.phy

Keep it byte-identical (do NOT open/save the files in the legacy app first —
resave may rewrite records). Put a copy in e.g. `legacy_data/DBI/`.

> If the install is gone, restore from a backup of `Files\DBI` (the .phy files
> ARE the money truth; the SQL Server DB holds only client/other data).

## 2. Scan + decode

    cd legacy_import
    python3 migrate_phy.py /path/to/Files/DBI --out /path/to/output

For each file:
- **known layout** → writes `<name>.jsonl` (one JSON record per line) + marks `OK`.
- **unknown layout** → writes `<name>.hex` (hex dump of first 6 records) + marks
  `UNKNOWN_LAYOUT`, so the layout can be reconstructed from the sample.

Run with `--limit N` to cap records per file during exploration.

## 3. Load into the new schema

    python3 load_sql.py /path/to/output/Daily.phy.jsonl --sqlite new.db
    python3 load_sql.py /path/to/output/*.jsonl --sqlite new.db

- `--sqlite FILE` writes into SQLite (stdlib only).
- Default is `--dry-run` (row counts + sample rows, no DB).
- PostgreSQL: add a `--psql DSN` mode using `psycopg2` (import time).

Mapping targets (from schema_complete.sql + SCHEMA_EVALUATION.md):

| Legacy file | Length | Target table |
|---|---|---|
| `Daily.phy` | 614 | `drawer_movements` / `daily_close` |
| `daily-manual.phy` | 52 | `manual_journal_entries` |
| `daily-manual-2.phy` | 56 | `manual_journal_entries` |
| `usersmony.phy` | 318 | `user_drawer_money` |
| `delivery.phy` | 55 | `transfers` |

## 4. Reconcile

Legacy money files are the source of truth; the SQL Server DB is not. After
load, reconcile totals per day against the `daily_close` style figures in the
legacy reports to catch field mis-mappings before going live.

## Layout status

- **Complete enough to import known fields:** Daily.phy (money group at
  0x00/0x04/0x08/0x18, txn count 0x30, R8s 0x34/0x3c; 0x3c..614 opaque),
  daily-manual / -2 (money 0x00), usersmony (idx 0x00, money 0x04).
- **Needs a real sample to finish:** MonyInfo.phy (runtime-built filename, 0
  static refs — must be read from a live copy), the full 614-B Daily.phy tail,
  delivery.phy fields beyond 0x00, and every `UNKNOWN_LAYOUT` file the scan
  reports.

Once you have the real `Files\DBI` copy, run step 2 and paste the
`migration_report.json` — unknown layouts get decoded from the `.hex` dumps and
any field-mapping mismatches get corrected in `layouts.py`.