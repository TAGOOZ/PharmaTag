# TITAN.W1 Extraction Corpus — GAPS REPORT

**Auditor:** builder-readiness pass over the `titan_extract/` corpus
**Date:** 2026-08-15
**Purpose:** list everything a builder of a modern replacement (FastAPI + PostgreSQL, Tauri + React) cannot implement as-is from these docs — contradictions, mis-citations, orphan/undocumented objects, unconfirmed purposes, and record-layout gaps.
**Ground truth used:** `titan_decompile/` (strings_utf16.txt, strings_readable.txt 18,972 lines, pcode_disasm.txt, objects.txt, procedures.txt) + `schema_complete.sql` (28 tables).
**Convention:** all citations are `doc.md:line`. Verified-by-me claims say `[VERIFIED]`.

---

## 1. CITATION BUG (systematic, affects every feature doc)

**Rule (DECOMPILE_CHEATSHEET.md:19):** `string index = 1-based line number − 3`. p-code LitVarStr 2-byte `idx = ((hi & 0x3F) << 8) | lo`; 4-byte `idx = b[1] | (b[2]<<8) | (b[3]<<16)`.

The feature docs use the **string index** as if it were a **line number**. Verified examples:

| Doc citation | Actual line in strings_readable.txt | Diff |
|---|---|---|
| `TitanUserAction` INSERT at `strings_readable.txt:4945` (feature_users_permissions_menus.md:236) | `INSERT INTO TitanUserAction(...)` at **4948** | +3 `[VERIFIED]` |
| `ChainBuyUsers` INSERT at `:4943` (feature_users_permissions_menus.md:267) | `INSERT INTO ChainBuyUsers` at **4946** | +3 `[VERIFIED]` |
| `ChainBuyUsers` SELECT at `:5867` (feature_users_permissions_menus.md:267) | `SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%` at **5870** | +3 `[VERIFIED]` |

Consequence: **every `strings_*.txt:N` citation in the feature docs must be read as `N+3`.** Adjacent confirmed landmarks: 4945 `INSERT INTO ChainBuyStore`, 4947 `INSERT INTO RawakidTablew`, 5867 `SELECT * FROM RawakidTablew WHERE PharmacistTel = N'`, 5869 `SELECT * FROM ChainBuyStore ORDER BY DrugName DESC`, 5871 `SELECT * FROM Win32_NetworkAdapter WHERE NetEnabled = True`, 5873 `SELECT top 3000 * FROM usersourceupdate WHERE Datee > '` `[VERIFIED]`.

Second symptom: **cross-file citations point at the wrong file/range.** feature_users_permissions_menus.md:236 cites `schema_complete.sql:245–256` for `TitanUserAction` — the real DDL is at **schema_complete.sql:266–278**. Same doc line 255 cites `schema_complete.sql:263–273` for `usersourceupdate` — that range is *TitanUserAction's* section; real DDL at **283–290**. A builder following those citations lands on the wrong table.

---

## 2. SCHEMA CONTRADICTIONS (blocking — cannot build a single schema from the corpus)

Ground truth = `schema_complete.sql` (28 tables). The other docs disagree on the core tables:

### 2.1 `titanksasales` — 9 vs 15 columns
- Ground truth (schema_complete.sql:113-123): `id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue`.
- business_logic_complete.md:104-120: 15 line-item columns `invoiceid, IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price, PharmacistTel, Mohafaza, Markaz, SourceIdDateTime, RequisterTel, country`.
- reports_complete.md:1033 adds yet more: `creditdebit, vat, mobile, writer, phar, tips`.
- The live insert loop in the chain-sales sync uses a third shape — `insert into titanksasales (invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue) VALUES (...)` (raz_complete.md:404) with the GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` used 3,564× in that loop (feature_sales_invoices.md:17).
- **Not decidable:** is `titanksasales` a summary table (9-col) that coexists with a line-item table, or is the 15-col form the real one? No doc resolves this.

### 2.2 `titanksastock` — 8 vs 24 columns
- Ground truth (schema_complete.sql:128-137): `id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock`.
- business_logic_complete.md:72-99 (called "Primary Drug Table"): 24 columns incl. `Barcode1..5, PriceNow, wareprice3, SellDisc, ExpireId/Expire, Tips, Mohafaza, Markaz, SourceIdDateTime, RequisterTel, country`.

### 2.3 `titanneed` — 5 vs 7 columns, disjoint
- Ground truth (schema_complete.sql:156-163): `id, drugname, quant, datee, sender, target`.
- business_logic_complete.md:129-137: `drugname, datee, silsilaid, minimum, pharmacyid, classy, stock` — **no overlap** in purpose (needs-request vs stock snapshot).

### 2.4 `TitanUserAction` — three different DDLs
- schema_complete.sql:266-278: 11 cols, `id INT IDENTITY`, `drugname NVARCHAR(100)`, `curbarcode VARCHAR(15)`, `units INT`, `datee REAL`.
- permissions_complete.md:261-272: 10 cols, **no `id`**, `curbarcode varchar(50)`, `units int`, `datee datetime`.
- business_logic_complete.md:142-153: 10 cols, `units NVARCHAR(20)`, `datee DATETIME`, `curbarcode NVARCHAR(50)`.
- feature_users_permissions_menus.md:222-235 matches the SQL file (with `curbarcode VARCHAR(15)`) but mis-cites its source (see §1).

### 2.5 `usersourceupdate` — 6 vs 9 vs 4 columns
- schema_complete.sql:283-290: 6 cols `id, drugname, price, units, localimport, datee`.
- feature_users_permissions_menus.md:240-250: 9 cols (adds `barcode, pharmacyid, lastedit`) — **this 9-col form is exactly what raw `schema.sql:263-273` contains**, so it is not fabricated; the two schema files disagree with each other.
- permissions_complete.md:285-292: 4 cols `drugname varchar(200), price float, units int, localimport int` — no `id`, no `datee`.
- SELECT landmark at strings_readable.txt:5873 (`top 3000 ... WHERE Datee > '<timestamp>'`) matches the 6-col or 9-col form, not the 4-col.

### 2.6 `ChainBuyUsers` — 12 vs 4 vs 1 columns
- schema_complete.sql:338-353: 12 cols incl. `Expire, IdDateTime, Quant, DrugName, SellDisc, Mohafaza, Markaz, Tips, RequisterTel, country, price`.
- feature_users_permissions_menus.md:259-267: 4 cols `PharmacistTel, Name, PharmacyId, Datee` (cites `schema.sql:317-323` — raw schema.sql matches this 4-col shape).
- permissions_complete.md:277-281: `PharmacistTel varchar(20)` only.

### 2.7 `invoicedata` — header and line items merged
schema_complete.sql:168-187 fuses invoice-header columns (`invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue`) with line-item columns (`IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price`). Raw schema.sql:131-140 has header-only. Whether TITAN stores header+lines in one row or two tables is undecidable.

### 2.8 `wzphar` — `pharname` vs `pharmacyname`
Schema (schema_complete.sql:204-210) and schema_mapping.md:17 use `pharname`. SQL evidence uses `pharmacyname`: `"group by pharmacyname,adress"`, `"where pharmacyname=N'"` (schema_complete.md:329-330), and `"select pharmacyname,adress,count(*),max(datee) from storediscount"` (modules_remaining_2.md:233). Schema (storediscount) itself uses `pharmacyname` (schema_complete.sql:219).

### 2.9 `taronlineeg` vs `farysales` — swapped column lists
- reports_complete.md:1040 documents `taronlineeg` as `mobile, grand, father, son, datee, datetimee, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy`.
- That exact column list is **farysales** in schema_complete.sql:411-431. `taronlineeg` in schema_complete.sql:305-315 is `CreateDate, mobile, NameEnglish, NameArabic, drugname, price, barcode`.
- Either reports_complete.md or schema_complete.sql swapped the two tables' columns.

### 2.10 `titaninn` — transfer vs purchases
schema_complete.sql:100-108: inter-pharmacy transfer (`fatid, itemsasstring, datee, source, silsilaid, target`). business_logic_complete.md:123-125: "Purchase/Inbound table — stores all inbound invoice items". Same table, two conflicting roles; the docs never reconcile them.

### 2.11 raw `schema.sql` vs `schema_complete.sql`
`schema.sql` (354 lines) is the *older/rawer* extraction: `wzdrugs` 13 cols vs 29 in schema_complete.sql:14-43; `titanpharmalist` uses `pharname`+`phar`+`tip` vs `pharmacyname` in schema_complete.sql:398-406; `usersourceupdate` 9-col, `ChainBuyUsers` 4-col, `taronlineeg` 4-col, `drugeyedash2` 3-col. The two SQL files are **not** the same schema.

---

## 3. ORPHAN / UNDOCUMENTED OBJECTS

### 3.1 Tables referenced in code but missing/underspecified in the 28-table schema
| Table | Seen in | Issue |
|---|---|---|
| `farysales` | schema_complete.sql:411-431 (table 27) | In schema, but every doc that reads sales uses `titanksasales`/`invoicedata`; its role (per-branch ledger) is asserted, not demonstrated. |
| `ZATCA` | schema_complete.sql:436-446 (table 28) | 100% `[INFERRED]`; no SQL fragment anywhere; the whole ZATCA log may live in `saturn` files (`C:\saturn\zatca\computer-1\invoices\`) instead (zatca_complete.md:740). |
| `drugeyedash2` | schema_complete.sql:378-383 | "SELECTed but no INSERT found" — the INSERT target is the `db_9ffe55_apifordrugeye` MySQL DB (modules_remaining_2.md:394, api_integration.md:398), not a SQL Server table. |
| `nilsen2` | schema_complete.sql:295-300 | "cleared with DELETE but no INSERT found" — ingestion path unknown (class `ModNilsen`, no doc). |
| `titanpharmalist` | schema_complete.sql:398-406 | Column set differs between the two SQL files; reports_complete.md:1038 shows yet another shape. |
| `orders` | schema_complete.sql:192-199 | Only `update orders set status='saved'` (schema_complete.md:310) — who creates orders, and the full write path, are undocumented. |

### 3.2 DB tables used in SQL but absent from the 28-table schema
- `taronlineeg` in the reports_complete.md:1040 shape (see §2.9) is not a valid schema table.
- `storediscount` INSERT in raz_complete.md:428 uses `adress, storename, pharmacyname, pharmacyname2, datee, tips, titanver, country, drugname, barcode, price, disco, units, pricechanged, localimport, quant` — 16 cols. schema_complete.sql:215-233 matches. But business_logic.md:156 (raw) says `drugname, barcode, units, pricechanged, localimport, quant` (6 cols). Same table, two widths.

### 3.3 Non-SQL persistence ("the money lives in `.phy` files")
The financial core is **not** in the SQL schema. `wzmony/wzdaily/wzbank` are shorthand references, not tables (connections_overview.md, feature_sales_invoices.md:118). File-based stores with **undocumented record layouts**:
- `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `daily-manual.phy`, `daily-manual-2.phy`, `workperiod.phy`, `delivery.phy`, `PIFary.phy`, `fary.date.phy`, `oot3.phy`, `rasd-config.phye`, `rasd-config.txt`, `month.start.stock.*`, `drugeye-for-titan.phy`, `oldprices.phy`, `prices-changes.txt`, `Price-log.txt`, `server.connection.report.txt`, `hungerstation.token.txt` (sources: business_logic.md:103,339; modules_remaining_2.md:188,248-251,337,586; reports.md:482-488; config_complete.md).
- **Known layouts** (partial, from `.phy` I/O in pcode): `ModDrgW` — `I4 id@0x00`, `str15@0x04`, `str40@0x22`, prices at `0x64`/`0x2C0`. A full per-file field-map inventory was never produced.
- `drugeye-for-titan.phy` is proprietary PHYCOD binary; the `.rar` "feed" is actually ROT-4 text and dead code `[VERIFIED 2026-08-15]` (drug_database_legal.md:65, connections_overview.md:436). Decoded feed: `/tmp/opencode/drugeye.update.titan.decoded.txt` (23,452 records).

### 3.4 Backup/archive file trees a builder must reproduce
`Labirdo\Titan3-Backup\{Daily, Monthly, Export, Export\Del, Rur\*.rur, images, tars-copy, xj\Phye.zip, xj\RSD-XML, qr}`, `Files\Archive\{Input, Output}`, `last-3-days-sales.csv`, `monthy\`, `undo.sales.txt` (business_logic.md:333-344, modules_remaining_2.md:206-216). Formats of `.rur`/`.zip`/`CompressArchive` and the `cZipArchive` payloads undocumented.

---

## 4. UNCONFIRMED PURPOSES (behavior asserted, not proven)

1. **`Titan CorrectStockForAll` / `ReloadRasidCorrect500` / `Reload_Drugs_in_last_Invoices` / `Titan ZuFillEmptyNameIftheresStock`** — named as "stock correction" (business_logic.md:101-102, raz_complete.md:970-972) but the actual correction rule (thresholds, which fields are rewritten, dedup key) is never stated.
2. **`ModOOTTrans`** — empty stub, 1 proc, 4 bytes (modules_remaining_2.md:133-140). Builders should treat as dead.
3. **`Modhelp, ModCompany, Types, ModChanges, ZzBookMark`** — empty modules (modules_remaining_2.md:406-444). Dead placeholders.
4. **`FormOotSum`, `FormShiftFawateer`, `FormDailyQuiod`, `FormDailyManual`** — their exact SQL aggregation formulas are not recovered; only table names are mapped (schema_mapping.md:155-158).
5. **The `agel` column** (`invoicedata`, `titanksasales`) — called "age/type" in schema_complete.sql:121,177 but its meaning in the cash-flow logic is unconfirmed.
6. **`creditdebit` semantics** — sales returns distinguished by `creditdebit` (reports_complete.md:80,1081) yet the column exists in neither `titanksasales` (ground truth) nor `invoicedata`; the "return" discriminator is undocumented in the schema.
7. **`gate` on day-close / ZATCA invoice counter** — `counter.txt` + `hash.txt` chain (zatca_complete.md:456-477, api_integration.md:362-363) is documented at file level, but the counter-rollover and hash-format spec are missing.
8. **`ModGS1Reader` (24 procs)** — GS1 AI parsing for the 6 DTTS fields is named (dtts_complete.md:771-799) but no AI-element map (AI=01/10/17/21/…) is given.
9. **HungerStation** integration — OAuth token file + `https://hungerstation.partner.deliveryhero.io/v2/chains/` (modules_remaining_2.md:186-188) but no request/response contract.
10. **`ModFarynet`/`Modfarynet`** annual-subscription flow (`الاشتراك السنوي 300 جنيه ... ماكينة فوري`) — activation handshake unspecified (modules_remaining_2.md:256).

---

## 5. RECORD-LAYOUT / P-CODE RECONSTRUCTION GAPS

- Of 6,192 procedures, only **Raz** (379) has per-proc sizes/frames + inferred purpose (raz_complete.md), and **ModStorage 154 / ModOot 105 / ModStock 165 / ModInn 71 / ModUsers 39 / ModMony 30 / ModBackUp 43 / ModPrint 70** exist only as proc-count + table-map entries (schema_mapping.md:49-97, business_logic.md:586-637). **Procedure bodies are not reconstructed** for any module — every rule in §4 of this doc and in business_logic.md/business_logic_complete.md is inferred from string constants, not from executed p-code paths.
- `.phy` record layouts: only `ModDrgW` partially mapped (§3.3). All Daily/delivery/fary/drugeye layouts unknown.
- `FormReportsGeneral` (61 procs) is the report hub, but the 45+ report types in reports.md/reports_complete.md are mapped to *forms*, not to *procedures* or *SQL*; a builder cannot reproduce e.g. "Shortage Review" vs "Shortage" without the SQL behind each.
- ZATCA: two competing JSON shapes — reports_complete.md:1193-1256 vs api_integration.md:216-328 vs zatca_complete.md:99-205 — **three different "summer" JSON schemas**. The real one is whichever saturn consumes; undecidable from docs alone.
- DTTS SOAP: xmlauth3.txt content and CSID flow described at file level (zatca_complete.md:359-409) but the signing algorithm (BouncyCastle) is delegated to `saturn.exe`/`toolkit.exe` — a replacement needs to reimplement or re-wrap that external toolchain (api_integration.md:162-176).

---

## 6. COVERAGE MATRIX (23 feature docs + foundational docs)

Legend: `✓` present, `~` partial/contradictory, `✗` absent.

| Doc | Workflow | Fields | SQL cit. | Proc-level | Side-effects | Rules | Citation issues |
|---|---|---|---|---|---|---|---|
| feature_users_permissions_menus | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 + wrong schema range (see §1) |
| feature_sales_invoices | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_purchases | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_sales_returns | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_purchase_returns | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_shortages | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_stock_counting | ✓ | ~ | ✓ | ~ | ✓ | ~ | off-by-3 |
| feature_transfers_logistics | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_customers_suppliers | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_drug_master_pricing | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_discounts | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_tax_invoicing | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_receivables_mrd | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_accounting_ledger | ✓ | ~ | ✓ | ~ | ~ | ✓ | off-by-3 |
| feature_account_closing | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_balances | ~ | ~ | ✓ | ~ | ✓ | ~ | off-by-3 |
| feature_doctors_prescriptions | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_reports_analytics | ✓ | ~ | ✓ | ~ | ✓ | ~ | off-by-3 |
| feature_invoice_editing | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_backup_archive_import | ✓ | ~ | ✓ | ~ | ✓ | ✓ | off-by-3 |
| feature_operational_utilities | ✓ | ~ | ✓ | ~ | ~ | ~ | off-by-3 |
| feature_external_integrations | ✓ | ~ | ✓ | ~ | ✓ | ~ | off-by-3 |
| feature_misc_modules | ~ | ✗ | ✓ | ~ | ~ | ✗ | off-by-3 |
| schema_complete.sql/.md | ✗ | ✓(28 tbl) | ✓ | ✗ | ✗ | ✗ | marks `[INFERRED]` cols |
| schema.sql (raw) | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | conflicts with _complete (§2.11) |
| business_logic_complete.md | ✓ | ~ | ✓ | ~ | ✓ | ✓ | 9 table DDLs conflict with schema |
| business_logic.md (raw) | ✓ | ~ | ✓ | ~ | ✓ | ✓ | older/rawer; conflicts as above |
| permissions_complete.md | ✓ | ~ | ✓ | ~ | ✓ | ✓ | 3 DDLs conflict |
| reports_complete.md | ✓ | ~ | ~ | ~ | ✓ | ~ | taronlineeg/farysales swap |
| reports.md (raw) | ✓ | ~ | ~ | ✗ | ✓ | ~ | partial (map to forms, no SQL) |
| modules_gap_1 / gap_2 / remaining_1 / remaining_2 | ✓ | ~ | ✓ | ~ | ✓ | ✓ | stub modules flagged |
| network_complete.md | ✓ | ~ | ✓ | ~ | ✓ | ✓ | — |
| config_complete.md | ✓ | ✓ | ✓ | ✗ | ✓ | ~ | — |
| nielsen_complete.md | ~ | ~ | ✓ | ✗ | ~ | ~ | ingest path unknown |
| drugeye_complete.md | ✓ | ~ | ~ | ✓(ModDrugEye 8) | ✓ | ✓ | feed=ROT-4, dead rar path |
| zatca_complete.md / api_integration.md / dtts_complete.md | ✓ | ✓ | ✓ | ~ | ✓ | ✓ | 3 JSON shapes conflict |
| phycodsystems_complete.md | ✓ | ✓ | ✗ | ✗ | ✓ | ~ | servers/URLs only |
| connections_overview.md | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | **best single map** |

**Overall:** workflows and business rules are broadly covered (~80-90%); **field-level truth is the weakest area** — 11 of 28 schema tables have at least one conflicting DDL in the corpus, and every feature doc's `strings` citations need `+3`.

---

## 7. RECOMMENDED NEXT ACTIONS (in order)

1. **Adopt `schema_complete.sql` as the single source of truth** for the 28 tables; re-derive `titanksasales/titanksastock/titanneed/TitanUserAction/usersourceupdate/ChainBuyUsers/invoicedata/wzphar/taronlineeg/titaninn` column lists from **p-code insert/select fragments only** (resolve §2.1-2.10) and delete the conflicting DDLs from the feature/permissions/business_logic docs.
2. **Normalize every `strings_*.txt:N` citation** to `N+3` across all 23 feature docs (§1) — mechanical, safe, high-value.
3. **Map the `.phy` record layouts** for the money files (`Daily*.phy`, `workperiod.phy`, `delivery.phy`, `PIFary.phy`, `drugeye-for-titan.phy`) from pcode `Get`/`Put` statements — this is the only hard blocker for a data-migration path. Start with `ModDrgW`'s known layout as the reference.
4. **Pick one ZATCA "summer" JSON schema** by checking which one `saturn.exe`/`toolkit.exe` arguments match (`--generate-uuid`, api_integration.md:181) and discard the other two.
5. **Confirm the `taronlineeg` vs `farysales` column swap** against pcode (which INSERT actually targets which table) before building the ETA/online-gov module.
6. **Verify `creditdebit`** in the raw pcode strings — it appears in report SQL (reports_complete.md:1081) but in no ground-truth CREATE TABLE; likely it lives in `wzgard.typee` or `invoicedata.agel`.
7. **Reverse the real invoice-storage model** (`invoicedata` header vs `wzgard` lines — are they 1:1 by `randomid`? is `invoicedata` even used at runtime?) — this determines the entire PostgreSQL relational design.
8. Resolve the legal question (drug_database_legal.md:241-260): **do not ship DrugEye data**; use the CC0 `karem505/egyptian-drug-database` + SFDA open data instead.

---

## 8. SHORT VERDICT

The corpus is **builder-blocking at the field layer, usable at the workflow layer**. Workflows, forms, reports catalog, integration contracts (DTTS/ZATCA/ETA/RSD/FTP/Fawry/HungerStation) and business rules are well-enough described to design against. But the SQL schema cannot be instantiated without adjudicating the 10 contradictions in §2, every strings citation needs +3, the `.phy` money files have no documented layouts, and at least two whole persistence systems (`.phy` files, Drugeye MySQL) sit outside the documented schema. **Do not start the PostgreSQL DDL until §7.1-7.3 are done.**