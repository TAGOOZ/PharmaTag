# 07 — Legacy Data Migration Plan (TITAN.W1 → Postgres)

**Status:** Planning (research complete; no implementation yet)
**Date:** 2026-08-16
**Scope:** Full migration of legacy TITAN.W1 (Phye.exe) data — fixed-record `.phy` money files plus the SQL Server extraction — into the new Postgres schema defined in `schema/schema_postgres.sql` and `schema/schema_sqlite.sql`.
**Related docs:** `titan_extract/PHY_MIGRATION.md`, `titan_extract/RECORD_LAYOUTS_daily_phy.md`, `titan_extract/schema_mapping.md`, `titan_extract/SCHEMA_EVALUATION.md`, `titan_extract/GAPS_REPORT.md`, `schema/schema_design.md`, `legacy_import/README.md`.

---

## 1. Pipeline architecture

```
┌─────────────────────────── LEGACY SOURCES ───────────────────────────┐
│                                                                      │
│  A) .phy random-access files          B) SQL Server tables (28)      │
│     ~/.wine/drive_c/TITAN.W1/Files/     [backup: NOT present in      │
│     .../DBI/*.phy                       workspace — DDL only]        │
│     .../DB/DDI.Phy, Archive/monthy/                                 │
│     .../Archive/moves, start-data                                   │
│     runtime-built: MonyInfo, Daily,                                  │
│     usersmony, fary.date, closefary …                                │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │                               │
                ▼                               ▼
        ┌──────────────────┐          ┌──────────────────────┐
        │ STAGE 0          │          │ STAGE 4              │
        │ DBI inventory &  │          │ SQL extract loader   │
        │ file classif.    │          │ (future: dump import)│
        │ text vs binary   │          └──────────┬───────────┘
        └────────┬─────────┘                     │
                 ▼                               │
        ┌──────────────────┐                     │
        │ STAGE 1          │  filesize =         │
        │ record-length    │  reclen × nrecs     │
        │ factorisation    │  (catalogue priors) │
        └────────┬─────────┘                     │
                 ▼                               │
        ┌──────────────────┐                     │
        │ STAGE 2          │  layouts.py known → │
        │ layout decode    │  typed records;     │
        │ phy_reader.py    │  unknown → .hex     │
        └────────┬─────────┘  dump (first 6)     │
                 ▼                               │
        ┌──────────────────┐                     │
        │ STAGE 3          │  count & value      │
        │ validation &     │  sanity; zero-ratio │
        │ float→decimal    │  rounding once-4dp  │
        └────────┬─────────┘                     │
                 ▼                               ▼
        ┌──────────────────────────────────────────────┐
        │ STAGE 5  STAGING DB (Postgres, single schema)│
        │  per-file idempotent load, ON CONFLICT NOTHING│
        │  audit_log + archive_imports rows            │
        └──────────────────────┬───────────────────────┘
                               ▼
        ┌──────────────────────────────┐
        │ STAGE 6  Reconciliation      │
        │  row counts, per-day sums,   │
        │  cross-file totals           │
        └──────────────────────┬───────┘
                               ▼
        ┌──────────────────────────────┐
        │ STAGE 7  branch_identities   │
        │  map legacy device → branch  │
        └──────────────────────────────┘
```

Stages are scripts, not a daemon. Each stage is independently runnable and
re-runnable (idempotent). A top-level `migrate_all.sh` chains them in order and
writes a run report to `archive_imports`.

---

## 2. Assessment of existing scripts

All live in `legacy_import/`. They form a solid *reader* foundation but are
**not yet a production pipeline**.

| Script | What it does | Gap |
|---|---|---|
| `phy_reader.py` | `FORMATS` registry (I2/I4/R4/R8/CURR/BOOL), STR ansi/utf16, RAW; `decode_record`, `detect_record_len` | `detect_record_len` picks *smallest* factor (e.g. 4) — wrong for every verified file (pruchworld 5234, salesfull 997…). Needs catalogue-prior driven factorisation. |
| `layouts.py` | `DAILY_PHY` 614 (only 0x00–0x3c mapped, `tail_raw` for 0x3c–614), `DAILY_MANUAL_PHY` 52, `DAILY_MANUAL2_PHY` 56, `USERSMONY_PHY` 318, more | Daily family layouts are **partial** (0x3c–614 opaque). Many files have no layout at all. |
| `migrate_phy.py` | Known layout → jsonl; unknown → `.hex` dump (first 6 records) + `UNKNOWN_LAYOUT`; writes `migration_report.json`; `--limit N` | Does not compute branch, does not reconcile, writes jsonl not DB. |
| `load_sql.py` | `MAPPINGS` → drawer_movements, manual_journal_entries, user_drawer_money, transfers (status placeholder), drugs; `--dry-run` default; `--psql`/`--sqlite` | No audit_log, no archive_imports, no float→decimal rounding, no branch resolution, transfers.status hardcoded placeholder. |

**Reuse decisions**
- KEEP `phy_reader.py` decode core; REPLACE `detect_record_len` with catalogue-aware factorisation (priors: 55, 105, 244, 318, 556, 614, 856, 997, 1300, 2010, 5234, 12611, … from `titan_extract/PHY_MIGRATION.md` §0) *and* runtime-built detection (MonyInfo, Daily, usersmony, fary.date, closefary, acctree — 0 static OpenFile refs).
- REWRITE `load_sql.py` load path into staged SQL with full column fidelity per `schema/schema_mapping.md` and the money/audit/branch rules from `schema/schema_design.md`.
- All money values travel as **decimal** end-to-end; floats are rounded **once to 4dp at import** (design §1.2); historical totals are **never re-summed** from floats.

---

## 3. Coverage matrix

Legend: `KNOWN` = record length + field layout fully verified; `PARTIAL` = reclen known, some fields mapped; `MISSING` = no layout / reclen unresolved → **blocker**; `TEXT` = plain-text state file (not fixed records); `N/A` = not money-critical (config/reference).

### 3.1 Money / journal truth files (the critical set)

| Legacy file | reclen × nrecs (verified) | Target table(s) | Layout status | Blocker? |
|---|---|---|---|---|
| `Daily.phy` | 614 (cap 40000; load 1..16000) | `daily_close`, `drawer_movements` | PARTIAL (0x00–0x3c known, 0x3c–614 opaque) | field-level |
| `daily-manual.phy` / `daily-manual-2.phy` | 52 / 56; date base 44000 | `manual_journal_entries` | PARTIAL (money@0x00) | field-level |
| `usersmony.phy` | 318 (runtime-built) | `user_drawer_money` | PARTIAL (I2 idx, R4 money, name, VARs, flag@0x268) | field-level |
| `Dailymax.phy` | **1,099,648 = no 614/856 factor**; candidates 781×1408, 968×1136, 71×15488, 88×12496 … | `drawer_movements`, `daily_close` | MISSING (reclen UNRESOLVED; only 2 nonzero blocks near EOF) | **YES** |
| `MonyInfo.phy` | runtime-built, 0 static refs (pcode grep = 0) | `daily_close`, `drawer_movements` | MISSING | **YES** |
| `Dailyline.phy` | runtime-built (migration successor) | `drawer_movements` | MISSING | **YES** |
| `fary.date.phy` | runtime-built, 0 refs | branch calendar / close flags | MISSING | **YES** |
| `closefary.phy` | runtime-built, 0 refs | `daily_close.status` | MISSING | **YES** |
| `acctree.phy` / `acctree-2.phy` | runtime-built, 0 refs | accounts tree | MISSING | **YES** |
| `RasidCorrect.phy` / `stcorrrect.phy` | runtime-built, 0 refs | stock corrections | MISSING | **YES** |
| `workperiod.phy` | runtime-built, 0 refs (0 B in Wine) | `work_periods`, `shifts` | MISSING | **YES** |
| `oot3.phy` / `netcounter.phy` / `netcouny.phy` | `netcouny.phy` is **TEXT** `"5840\r\n"` (ZATCA/Saturn network counter) | `einvoice_counters` | TEXT (parsed, not records) | no |

### 3.2 Master / reference files

| Legacy file | reclen × nrecs | Target table(s) | Layout status | Notes |
|---|---|---|---|---|
| `tar.phy` | 856 × 32000 = 27,392,000 ✓ | `drugs` | PARTIAL (name at 0x00; FFFClean/ModStock 856) | canonical drug master |
| `pruchworld.phy` | 5234 × 5000 = 26,170,000 ✓ | `drugs` import staging / purchase world | PARTIAL (FFFInPut/ModInn 5234) | sparse |
| `customers.w.phy` | 157 × 30000 = 4,710,000 ✓ | `parties` | PARTIAL (name@0x00, `?` filler) | names show `?` placeholders in Wine sample |
| `salesfull.phy` | 997 × 50000 = 49,850,000 ✓ | `archive` / invoices | PARTIAL (FFFOutPut 997) | sparse |
| `ShogUser.phy` | 1114 × 49 = 54,586 ✓ | `users`, `shifts`, `user_drawer_money` | PARTIAL (name@0x00) | |
| `delivery.phy` | 55 (Moddelivery) | `transfers` (status only) | PARTIAL (only 0x00) | status placeholder removed in load |
| `integrations.phy` | 105 (ModIntegrations) | `integration_config` | PARTIAL | |
| `DDI.Phy` (in `Files\DB`) | 1300 (ModDDI) | drug interactions | PARTIAL | |
| `Hodour.phy` | 244 (FormHodour) | attendance | PARTIAL | |
| `amil2.phy` | 56 (ModAmil2) | salesmen | PARTIAL | |
| `MRDINFO.phy` | 128-byte stride observed; size 1,279,928 **not** multiple of 128; factors 397×403×8 | receivables reasons / MRD reference | PARTIAL (reference list, not money truth) | low priority |
| `PI3.phy` | 3159 (ModColors/FormStyles) | theme/config | KNOWN | N/A money |
| `titanver.phy` | TEXT `"351\r\n"` | `app_config` (version) | TEXT | |
| `bio.phy` | TEXT `"3056546965\r\n"` | config / identifier | TEXT | |
| `trackdt.phy` | TEXT `"26-08-15 02:55\r\n\r\n"` | last-track timestamp | TEXT | |
| `max.drug.txt` | TEXT `"18101\r\n"` | max drug seq | TEXT | |
| `app.version.txt` | TEXT `"360.260217\r\n"` | `app_config` | TEXT | |
| `ismaster.txt` / `Titan.master` | TEXT flag | `branches.is_main_device` | TEXT | master/standalone flag |
| `rasd-config.phye` | 0 B | – | N/A | encrypted config, skip |

### 3.3 Wine-install reality check

The Wine install at `~/.wine/drive_c/TITAN.W1/Files/DBI/` has **22 `.phy`** files; most are **0 bytes** (fresh install): `Foloos`, `LastEdited`, `Mcr`, `RCore`, `Tarhil`, `colors`, `daily-manual`, `daily-manual-2`, `delivery`, `integrations`, `lact`, `masrofat`, `orooda`, `sounds`, `tarinfo`, `workperiod`. Populated files were used to verify the factorisations above. **Factorisation is only possible on populated files**; empty files must be verified from a real deployment backup.

### 3.4 SQL side

No actual SQL dump (`.bak`/`.csv`/`.dat`) is present in the workspace — only DDL. The 28-table extraction is **deferred**; loader will accept the documented column set from `schema_mapping.md` once a real dump is supplied.

---

## 4. Correctness & trust strategy

1. **Reclen verification, not guesswork.** Every reclen is confirmed by (a) `filesize % reclen == 0`, (b) a catalogue prior from `PHY_MIGRATION.md` §0, (c) a sample hex/typed decode. Files failing (a)+(b) are declared `UNKNOWN_LAYOUT` and **block** that table — never guessed.
2. **Round once, keep decimal.** VB6 Single/Double money → `round(x, 4)` at import only. No re-summing from floats ever. `NUMERIC(18,4)` per-unit, `NUMERIC(18,2)` totals (design §1.1–1.2).
3. **Day-key correctness for Daily family.** Daily record index = `day + 40000`; manual date base = 44000; VB6 date serial from `record_no + base`. Load loops only 1..16000 — the 40000-cap wrap must be handled or explicitly reconciled.
4. **Idempotency = dedupe guarantee.** Loads use natural keys (see §6); re-running a stage cannot duplicate rows.
5. **Audit trail.** Every money/stock write inserts an `audit_log` row in the same transaction (design §1.2). `archive_imports` records each file+run with checksums and row counts.
6. **Reconciliation report (Stage 6).** Per-file: expected `reclen × nrecs` vs actual bytes, nonzero-block ratio, decoded row count, per-day sums. Compare summed staging totals against the legacy SQL extraction totals where available. Any mismatch halts promotion to live.
7. **CITATION CAVEAT (GAPS_REPORT.md:23):** all `strings_*.txt:N` citations in feature docs are off by **+3** (string index = 1-based line − 3). Any future lookup that relies on those indexes must apply the offset; the plans in this directory already do.

---

## 5. Sequencing & branch_identities

### 5.1 Suggested order (respects FK dependencies)

1. **Branches & identity** — seed `branches` + `branch_identities` from `titanpharmalist.mobile`, `wzphar.pharname`, `wzaccfreetree.mobile`, `invoicedata.pharmacyid`, `titanstock.pharmacyid`, and `ismaster.txt`.
2. **Reference masters** — `drugs` (tar.phy), `parties` (customers.w.phy), salesmen (amil2.phy), users (ShogUser.phy).
3. **Money history** — once layouts are resolved: `user_drawer_money`, `manual_journal_entries`, `drawer_movements`, `daily_close`, `transfers`.
4. **Counters/config** — `einvoice_counters` (netcouny text), `app_config` (version files), `integration_config`.
5. **Archive** — salesfull/invoice archive; monthly `Archive/monthy/moves` + `start-data/month.start.info` per branch.

### 5.2 branch_identities mapping

- A legacy deployment may be a standalone single device or a master+slave network. Identity comes from `ismaster.txt` (main device flag) plus the `pharmacyid` / `mobile` / `pharname` fields across the 28 SQL tables.
- `branches`: one row per detected device, `is_main_device` from `ismaster.txt`.
- `branch_identities`: one row per alias (mobile, pharmacyid, pharname variant) so any later file/source can be resolved to a `branch_id`.
- Import of every money row must carry a resolved `branch_id`; if a file has no device identity, the run must be pinned to an explicit `--branch-id` and that choice recorded in `archive_imports`.

---

## 6. Rollback & idempotency

### 6.1 Natural keys (ON CONFLICT DO NOTHING)

| Target | Key |
|---|---|
| `drawer_movements` | (`branch_id`, `datee`, `source_file`, `record_no`) |
| `manual_journal_entries` | (`branch_id`, `record_no`, `source_file`) |
| `user_drawer_money` | (`branch_id`, `record_no`, `source_file`) |
| `transfers` | (`branch_id`, `record_no`, `source_file`) |
| `drugs` | (`branch_id`, `drugname` EN) |
| `parties` | (`branch_id`, `randomid`) |
| `daily_close` | (`branch_id`, `datee`) |
| `einvoice_counters` | (`branch_id`, `kind`, `period`) |

All of these already exist in `schema_sqlite.sql` / `schema_postgres.sql` (record_no + source_file columns are present on `drawer_movements`, `manual_journal_entries`, `user_drawer_money`).

### 6.2 Rollback

- Each **file** is loaded in a single transaction; a failed file rolls back fully and is re-attemptable without side effects.
- `archive_imports` has `status` (running/done/failed) + checksum; a full "reset" = `DELETE FROM <table> WHERE source_file = ?` for the affected files (safe because every imported row carries `source_file`), then re-run the stage.
- Live data is never touched directly: Stage 5 loads into a **staging schema**; promotion to live is a reviewed, single-step switch after Stage 6 reconciliation passes.

---

## 7. Open decisions (for user)

1. **Dailymax.phy reclen (1,099,648 B)** — no factor matches 614/856. Candidates include 781×1408, 968×1136. Can you provide a real-deployment `Dailymax.phy` (or the `ModDailyQuiod` record spec beyond 0x3c) so we can resolve the record length? **This blocks drawer_movements/daily_close history.**
2. **MonyInfo.phy / Dailyline.phy / fary.date.phy / closefary.phy / acctree.phy / RasidCorrect.phy / workperiod.phy** — runtime-built, zero static refs. Provide sample files (even a few KB) or confirm these tables can start empty and be backfilled from the SQL extraction.
3. **Actual SQL dump** — no `.bak`/`.csv`/`.dat` is present. When will the 28-table extraction be supplied, and in what format?
4. **`transfers.status`** — `load_sql.py` currently writes a placeholder. Confirm the legacy `delivery.phy` 0x00 field semantics (status vs timestamp) before finalizing.
5. **Daily 40000-cap wrap** — the load loop reads 1..16000 of a 40000-cap file. Confirm the intended day-range so record→date serial mapping is exact.
6. **Branch identity for standalone single-device deployments** — should `branch_id` default to a single seeded "main" branch when `ismaster.txt`/pharmacyid is absent? What branch name/identifier should be seeded?
7. **`customers.w.phy` `?` filler** — names in the Wine sample contain `?` bytes. Real data trusted as-is, or is there a charset/normalisation rule?
8. **Archive granularity** — `salesfull.phy` (997×50000) and `Archive/monthy/moves`: import as a single archive table or split per-branch/per-month?
9. **MRDINFO.phy** — confirmed as a reference list (receivables reasons) not money truth; OK to import as reference config only, low priority?
10. **Binaries beyond `.phy`** — `rasd-config.phye`, `Phye.safer`, `counter.txt`+`hash.txt` (ZATCA): include in migration, or leave in a legacy archive folder untouched?

---

## Appendix — immediate next steps

1. Deliver this plan; confirm open decisions 1–3 first (they gate the money-history path).
2. Implement Stage 1 factorisation with catalogue priors + runtime-built detection; re-run on a real backup's DBI folder.
3. Implement Stage 5 staged loader with audit_log + archive_imports + ON CONFLICT NOTHING (replacing `load_sql.py` load path).
4. Build Stage 6 reconciliation and gate promotion.