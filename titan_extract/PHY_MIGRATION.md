# PHY_MIGRATION.md — Legacy VB6 .phy Record-Layout Mapping (SQL Migration Path)

**Scope note:** The Daily*.phy layouts are DONE (see `RECORD_LAYOUTS_daily_phy.md`). This document maps the REMAINING money/state `.phy` fixed-record files to enable a SQL migration. The Daily*.phy layouts are DONE; the task here is the remaining files, especially those flagged MISSING for the SQL migration.

**Method (CORRECTED 2026-08-16):** filename string idx → `idx2refs2.json` → procs touching the idx is **unreliable for these files**. MonyInfo.phy (idx 7110), Daily.phy (idx 7097), and the other `.phy` names have **0 direct p-code refs** (`grep MonyInfo` = 0 hits; idx2refs2/idx2refs_all/idx2refs_correct all EMPTY). The VB6 runtime builds these filenames at runtime: base path + a per-module string-table blob (small idx 5/6/12-17/24-29/44 = **per-module refs, NOT global-pool refs**) + `.phy`.

**Consequence:** the small idx (5, 6, 44, …) cannot identify a file across modules — e.g. `LitStr [1b 05 00]` (idx 5) is used by BOTH ModDailyQuiod (opens 614 B Daily.phy) AND ModDailyManual (opens 52 B daily-manual.phy). **Files must be identified by (module role + record length literal), not by string index.**

**Working tool:** full record-length catalogue of every `OpenFile` site in `pcode_disasm.txt` (265 sites). Record length = `LitI2 [f3 lo hi]` = lo|(hi<<8), or `LitI2_Byte [f4 xx]`, immediately preceding the `OpenFile`.

**Empirical method (NEW 2026-08-16, primary):** the actual `.phy` files exist in the local Wine install at `~/.wine/drive_c/TITAN.W1/Files/DBI`. A `.phy` file is a VB6 random-access store with **no header** — record k at offset `(k-1)*reclen`. So:
- **reclen × nrecs = filesize**, and prime-factorising the file size gives the record length directly (e.g. `salesfull.phy` = 49,850,000 B = 997 × 50,000).
- When the file holds real data, field offsets are read straight off the bytes (e.g. `tar.phy` English name @0x00, Arabic name @0x34 — verified against 18,100 real records).
- Sparse files (pre-allocated, lazily written) still reveal `reclen` from the size factorisation even when every record is zeros.
- This replaces static disassembly for layout discovery and is **fully automated** in `legacy_import/` (`migrate_phy.py` + `layouts.py` + `phy_reader.py` + `load_sql.py`, runbook in `legacy_import/README.md`).

---

## §0 Record-length catalogue (verified 2026-08-16)

Confirmed anchors (from RECORD_LAYOUTS_daily_phy.md):
- ModDailyQuiod @0x0093f5e4/0x00934920 → **614 B** (Daily.phy) — L535265/L535322
- ModDailyManual @0x009203f8/0x00936394 → **52 B**; @0x0091f3d8/0x00936a14 → **56 B** — L546982/L547097/L547020/L547054
- FormUsersMony @0x0093ce1c/0x0091f32c → **318 B** (usersmony.phy, NEW 2026-08-16) — L640052/L640101

| module/role | record length | OpenFile line(s) | file (known or guess) |
|---|---|---|---|
| FFFOutPut | 997 | L26961/30501/31982 | output/summary store |
| MD (Files DB) | 255 | L63492..65255 | generic 255-B row |
| Files module (bulk) | 471 | L65518/65657/65688/65734 | – |
| Files module (bulk) | 176 | L65925/65960/65999 | – |
| Files module (bulk) | 2241 | L66216/66253/66294/66325 | – |
| Files module (bulk) | 5234 | L66381/66498/66525 | – |
| Files module (bulk) | 997 | L66436/66579/66604 | – |
| Files module (bulk) | 2280 | L66763 | – |
| Files module (bulk) | 206 | L67066 | – |
| Files module (bulk) | 144 | L67331/67355/67391 | – |
| ModAmil | 2010 | L68260/68365/68780/68824 | amil (salesperson) data |
| FFFClean | 856 | L78941/79471 | cleanup scan |
| FFFMony big forms | 238/856/60928(=0xEE00)… | L114590/116199 etc. | **money module reads** |
| FFFInPut | 5234 | L145755/147459 | import |
| ModStock bulk | 856 | L213914..235959 (many) | stock rows |
| ModPrint | 948 | L252445/252476 | print queue |
| FormAdvanced | 856 | L273845 | advanced (money?) |
| FormShiftFawateer | 997 / 316 | L297969/298033 | shift invoices |
| FormShiftInput | 5234 / 2696 | L299890/300594 | shift input |
| ModOot | 997 | L320361/320399/328014/328155 | day-end (oot) |
| ModInn | 5234 | L330191/333709/333850 | inward (transfer in) |
| ModUsers | 557 | L334412/334451 | users file |
| ModTitan | 3159/428 | L343923/344840 | – |
| FormExam | 31722 | L351322/351352 | – |
| FormHodour | 244 | L353876/353920 | attendance |
| ModDDI | 1300 | L356302 | drug interactions |
| ModDRGEXChange | 856 | L363689/364131 | drug exchange |
| ModReBuild | 856/471 | L374333/374423/374477 | rebuild |
| FormAmilHistory | 2010 | L405306 | salesperson history |
| FormHodour19 | 255 | L415383.. | attendance 19 |
| ModAmil2 | **56** | L418512/418576/418869 | amil2 (small, 56 B) |
| ModOneFile | 856 | L425195 | onefile |
| ModNetwork (many) | 856/997/5234/471/176 | L427030..432565 | sync files |
| FFFDrugEye | 544 | L464333/465015 | drugeye feed |
| ModColors/FormStyles | 3159/28 | L465616/465654/466541 | theme |
| ModDTTS | 556 | L478848/478882 | DTTS |
| ModUpto352 (many) | 4516/6637/5234/2696/666/997/426/316/176/471/124/144 | L492869..497293 | bulk tables |
| Moddelivery | **55** | L500192/500238 | delivery.phy (55 B, NEW) |
| ModOrood | 2050 | L506826/506875 | – |
| ModArchive | 2696/316 | L507514/507608 | archive |
| FFFRCAccept | 46 | L526305 | remote control accept |
| ModDailyQuiod | **614** | L535265/535322 | Daily.phy ✓ |
| ModDailyManual | **52/56** | L546982/547020/547054/547097 | daily-manual/-2 ✓ |
| ModEta | 255 | L550074..552715 | ETA |
| ModAccounting | 255/514 | L555495/556391 | accounting |
| ModAccFreeOne | 328 | L595106/595135 | free accounting |
| ModDrgW | 59 | L609136/609171/609203 | drgw |
| FormUsersMony | **318** | L640052/640101 | usersmony.phy ✓ NEW |
| FormRsdDispatch | 12611 | L661837..662987 | RSD dispatch |
| FormImportFromOtherDBI | 5234/997 | L663150/663280 | import |
| FormWasfaty | 1396 | L665913/665980 | wasfaty (prescriptions) |
| ModSaturn | 255 | L679077..679298 | saturn (ETA) |
| FormDrugsCompare | 856 | L682466/682729 | compare |
| ModIntegrations | **105** | L686803/686841/686881 | integration config |

**NEW confirmed record lengths this run:** usersmony.phy = 318 B (FormUsersMony, read/write pair), delivery.phy = 55 B (Moddelivery), ModAmil2 = 56 B.

---

## §0b Verified against the real Wine install (`~/.wine/drive_c/TITAN.W1/Files/DBI`, 2026-08-16)

Record lengths **confirmed empirically** by file-size factorisation (no disasm needed):

| File | size (B) | reclen | nrecs | evidence |
|---|---|---|---|---|
| `tar.phy` | 27,392,000 | **856** | 32,000 | 856 = 0x0358 = `LitI2 [f3 58 03]` (10+ OpenFile sites); record boundary lands on `DERMOTRACIN…` |
| `salesfull.phy` | 49,850,000 | **997** | 50,000 | 997 = 0x03E5 = `LitI2 [f3 e5 03]` (19 OpenFile sites, all FFFOutPut report/export) |
| `customers.w.phy` | 4,710,000 | **157** | 30,000 | 157 = 0x009D = `LitI2 [f3 9d 00]` (single site, FFFNeed @0x00b04314) |
| `ShogUser.phy` | 54,586 | **1114** | 49 | records decode to `????? …` name strings + codes (`4`, `5678`) |
| `Dailymax.phy` | 1,099,648 | 614-family* | ~16,000 | *exact reclen UNRESOLVED — size is not a clean multiple of 614 (Daily) or 856; see §1c |

`daily-manual.phy` / `-2` / `delivery.phy` are 0 B on this install (never used). `MonyInfo.phy` and `usersmony.phy` **do not exist** here — they are created at runtime on first use, confirming they cannot be resolved by static analysis (§1).

### Data reality of this install
It is a **fresh test install** — not a production copy. Actual nonzero data found:
- `tar.phy`: **18,100 real drug records** (English name @0x00, Arabic name cp1256 @0x34, size/flags fields) — the only file with real business data.
- `salesfull.phy`: **5 nonzero bytes total** (header/counters `02 01 01 01 e2` @offset 28-52); all 50,000 records are zeros.
- `customers.w.phy`: 1 placeholder record (`????? ??????` — Arabic bytes stored as literal `?`); 29,999 zeros.
- `ShogUser.phy`: rec1 placeholder (`????? …` + code `4`), rec2+ blank.
- `Dailymax.phy`: ~1.9 KB nonzero at the very end.

**Implication:** the Wine install proves the toolchain end-to-end (layout detection, decoding, SQL load) on real files, but contains **no real money/sales history**. The historical import still needs the production machine's `Files\DBI` (or a backup). The pipeline is ready and driven entirely by `legacy_import/`.

### tar.phy field layout (VERIFIED — real data)
| offset | type | size | meaning | example (rec2) |
|---|---|---|---|---|
| 0x00 | STR cp1256 | 50 | English name (space-padded) | `DERMOTRACIN AEROSOL POWDER 150 ML` |
| 0x34 | STR cp1256 | ~40 | Arabic name + size text | `ديرموتراسين 150 مل بخاخ` |
| 0x5C..856 | RAW | — | opaque tail (stock/price/flags) | — |

Arabic is **cp1256** (not UTF-16); the reader must decode with `cp1256` and strip ` \x00` padding (fixed `phy_reader.py`).

### Where `?` comes from
Names in `customers.w.phy`/`ShogUser.phy` show `?` (0x3F) bytes — Arabic text was stored as literal `?` in this install (an old/corrupt encoding path), so those fields are not recoverable as names here. Production files should be re-checked.

---

## File inventory (all remaining .phy files)

| idx | filename | purpose (if known) | record length | proc refs | status |
|-----|----------|--------------------|---------------|-----------|--------|
| 7110 | `\Files\DBI\MonyInfo.phy` | day-close money snapshot → `daily_close` | **UNKNOWN (0-ref)** | none (runtime-built) | **NOT MAPPABLE by string idx** |
| 7102 | `\Files\DBI\fary.date.phy` (TBD) | per-branch date/close flags | UNKNOWN | 0-ref | follow-up |
| (blob) | `usersmony.phy` | money per user/shift | **318** | FormUsersMony @0x0093ce1c/0x0091f32c | **DONE (rec len); fields partial** |
| (blob) | `delivery.phy` | transfer delivery state | **55** | Moddelivery @L500192/500238 | rec len NEW; fields TODO |
| (blob) | `daily-manual.phy` / `-2` | manual journal entries | **52/56** | ModDailyManual | DONE (see daily doc) |
| (blob) | `Daily.phy` | daily sales/cash | **614** | ModDailyQuiod | DONE (see daily doc) |

*(MonyInfo.phy accessor: NOT locatable via string refs — see §3 strategy.)*

---

## §1 MonyInfo.phy — findings

### What is known
- Full literal `\Files\DBI\MonyInfo.phy` exists at **idx 7110** (strings_utf16.txt line 7113).
- It has **0 refs** in every reference map (idx2refs2 / idx2refs_all / idx2refs_correct). `grep -c MonyInfo pcode_disasm.txt` = **0**.
- Therefore the filename is built entirely at runtime. The day-close money writer lives in a money form (FFFMony / FormDailyQuiod / FormMonyDetails), but which OpenFile corresponds to MonyInfo.phy cannot be resolved by string index — the small idx blobs are per-module and ambiguous across modules.
- ModDailyQuiod writes **only Daily.phy** (614 B, keyed by day number, cap 40000). FFFMony / FormMonyDetails read many 856/238/997-B stores but none is proven to be MonyInfo.

### Known vs UNKNOWN summary
| item | status |
|---|---|
| literal string | KNOWN (idx 7110) |
| direct procs | UNKNOWN (0 refs) |
| record length | UNKNOWN |
| record cap | UNKNOWN |
| field table | UNKNOWN |
| → migration mapping | NOT SAFE without runtime/format sample |

**Recommendation:** obtain a real `MonyInfo.phy` sample (from the legacy install) and infer the layout from the 318-B usersmony.phy pattern + day-close fields; static disassembly cannot resolve it.

---

## §1b usersmony.phy — 318 B record layout (NEW 2026-08-16)

Accessor pair: read `FormUsersMony@0x0093ce1c` (L640027, `GetRecOwn4 [ff 17 2f 00]`) / write `@0x0091f32c` (L640076, `PutRecOwn4 [ff 19 2f 00]`). Record length 318 B (`LitI2 [f3 3e 01]` before OpenFile). Filename = base path + per-module blob idx 44.

Record field offsets (from `MemLd*`/`MemSt*` on the array element in FormUsersMony procs):

| offset | type | meaning | evidence |
|---|---|---|---|
| 0x00 | I2 | user/shift index | `MemLdI2 [89 00 00]` ×7, `MemStI2` |
| 0x04 | R4 | money amount | `MemLdFPR4 [8c 04 00]` ×11 |
| 0x08 | String | (name/date) | `MemLdStr [8a 08 00]` ×8, `MemLdI4 [8f 08 00]` |
| 0x0c | Variant | (cash/notes) | `MemLdRfVar [06 0c 00]` ×11 |
| 0x38 | Variant | (drawer/close) | `MemLdRfVar [06 38 00]` ×62 |
| 0x0268 | I2 | (state flag) | `MemLdI2 [89 68 02]` ×6 |

**→ SQL:** per-user/per-shift drawer money (`user_drawer_money` / `shifts.cash`), matching feature_sales_invoices.md:118.

## §1c Dailymax.phy — record length still UNRESOLVED (2026-08-16)

`Dailymax.phy` = 1,099,648 B. The Daily family schema-evolution strings (`Upgrading Daily to Dailyline`, `Upgrading DailyLine to dailymax`) show Dailymax is the **migrated successor** of Daily.phy (614 B). Prime factors of 1,099,648 include 71 × 15,488 and 88 × 12,496 etc., but **none matches 614** — so either Dailymax grew to a new record length on migration, or the file was never rewritten to its true capacity on this fresh install. The file is ~99.8% zeros here (only the last ~1.9 KB nonzero), so byte-inspection cannot confirm the layout. **Resolution path:** obtain a populated `Dailymax.phy` (production machine) and factor its size; or find the OpenFile+`LitI2` length pair in ModDailyQuiod-family procs that specifically migrates to Dailymax.

---

## §2 Migration mapping (MonyInfo.phy → SQL)

*(blocked on §1 — see SCHEMA_EVALUATION.md §1.5 for target `daily_close` + `drawer_movements` shape)*

---

## §3 Remaining work list for follow-up agents

1. **usersmony.phy fields (318 B)** — DONE (see §1b above): record length + UDT offsets mapped.
2. **delivery.phy fields (55 B)** — Moddelivery @L500192..500260.
3. **MonyInfo.phy** — needs a live sample file, not disassembly.
4. Remaining 0-ref files (fary.date, closefary, acctree, workperiod, oot3, netcounter, myftp, DDI, RasidCorrect) — same runtime-built problem; pair each with its record-length from §0 and module role instead.
5. Schema work is independent of the above — resolve the 11 DDL contradictions (SCHEMA_RESOLVED.md) in parallel.
6. **NEW: solve remaining `UNKNOWN_LAYOUT` files by size factorisation** against the Wine install (same method that solved tar/salesfull/customers/ShogUser): `Dailymax.phy`, `tarinfo.phy`, `MRDINFO.phy`, `workperiod.phy`, `masrofat.phy`, `trackdt.phy`, `netcouny.phy`, `titanver.phy`, `bio.phy`, `integrations.phy` (105 B known), `lact.phy`, `orooda.phy`, `pruchworld.phy` (4,710,000 B factorable), `sounds.phy`, `colors.phy`, `PI3.phy`, `Mcr.phy`, `RCore.phy`, `Tarhil.phy`, `LastEdited.phy`, `Foloos.phy`. Each resolves to `reclen × nrecs = filesize`.
7. **Field-level layouts** for `salesfull.phy` (997 B) and `customers.w.phy` (157 B) require a populated production copy — the fresh install holds no real records to read offsets from.