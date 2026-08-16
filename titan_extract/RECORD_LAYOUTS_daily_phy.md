# RECORD LAYOUT — `Daily*.phy` money record files

Source: `titan_decompile/pcode_disasm.txt` (token-level P-Code), `strings_utf16.txt` (string table, index = 1-based line − 3), `/tmp/opencode/rec_procs.json`, `/tmp/opencode/proc_io_strings.json`.
Scope this run: ONLY the `Daily*.phy` money files. Other record files are noted at the bottom and left unmapped.

## 1. File inventory (from string table `strings_utf16.txt`)

| String index | 1-based line | Filename |
|---|---|---|
| 7097 | 7100 | `\Files\DBI\Daily.phy` |
| 7098 | 7101 | `\Files\DBI\Dailyline.phy` |
| 7099 | 7102 | `\Files\DBI\Dailymax.phy` |
| 7139 | 7142 | `\Files\DBI\daily-manual-2.phy` |
| 7140 | 7143 | `\Files\DBI\daily-manual.phy` |

Schema-evolution strings confirm the family: `Upgrading Daily to Dailyline`, `Upgrading DailyLine to dailymax` (strings_utf16.txt idx 6793/6794). The filenames are built at runtime (concatenated) so the pcode `LitStr` refs for them decode only to the raw reference blob; the record length + module role below identify the files unambiguously.

### How the Daily family is used
- `Daily.phy` — the per-day money/journal record (largest, 614 B). `ModDailyQuiod` saves/loads the whole file into a module UDT array; `FormDailyQuiod` is the money screen (16 procs) that reads/writes the money-group fields of each day's record.
- `daily-manual.phy` (52 B) / `daily-manual-2.phy` (56 B) — the manual money records handled by `ModDailyManual`/`FormDailyManual`/`FormDailyManual2`. The "-2" variant is exactly 4 B larger.
- `Dailyline.phy` / `Dailymax.phy` — migrated successors of `Daily.phy` (same record family; record length not separately observable because the migration is data-copy, not field-access).

## 2. Procs that OpenFile a Daily*.phy (from proc_io_strings.json / rec_procs.json)

| File (inferred) | Proc | start line | OpenFile line | Record length |
|---|---|---|---|---|
| `Daily.phy` (main money) | `ModDailyQuiod` @0x0093f5e4 | 535240 | 535265 | **614** (`LitI2 [f3 66 02]` = 0x0266) @535264 |
| `Daily.phy` (main money) | `ModDailyQuiod` @0x00934920 | 535286 | 535322 | **614** (`LitI2 [f3 66 02]` @535321) |
| `daily-manual.phy` | `ModDailyManual` @0x009203f8 | 546959 | 546982 | **52** (`LitI2_Byte [f4 34]` @546981) |
| `daily-manual.phy` | `ModDailyManual` @0x00936394 | 547078 | 547097 | **52** (`LitI2_Byte [f4 34]` @547096) |
| `daily-manual-2.phy` | `ModDailyManual` @0x0091f3d8 | 546997 | 547020 | **56** (`LitI2_Byte [f4 38]` @547019) |
| `daily-manual-2.phy` | `ModDailyManual` @0x00936a14 | 547035 | 547054 | **56** (`LitI2_Byte [f4 38]` @547053) |

Pairing note: the two procs using LitStr ref `[1b 05 00]` (idx 5) open length **52** (`daily-manual.phy`); the two using `[1b 06 00]` (idx 6) open length **56** (`daily-manual-2.phy`). Each file has one save proc + one load proc.

### I/O primitive used per proc (trace)
- `ModDailyQuiod@0x0093f5e4` (load all): `OpenFile` L535265 → loop (`ForVar`) → `DestructRecord` L535277 + `GetRecOwn4` L535278 → `NextStepVar` L535280 → `Close` L535282. Record buffer = module array @0x08 (`FMemLdRf [07 08 00 04 00]` + `Ary1LdRf [40]` @L535275-276).
- `ModDailyQuiod@0x00934920` (save all): `OpenFile` L535322 → `PutRecOwn4` L535329 (same array buffer @L535327-328) → `Close` L535331.
- `ModDailyManual@0x009203f8`/`@0x0091f3d8` (save manual/-2): `OpenFile` L546982/L547020 → `PutRec4` L546991/L547029 (record len literal 52/56 @L546990/L547028) → `Close`.
- `ModDailyManual@0x00936a14`/`@0x00936394` (load manual/-2): `OpenFile` L547054/L547097 → loop → `GetRec4` L547069/L547112 → `Close`.

Because the file procs move whole records, the field offsets below come from the UDT-mirroring money procs that address individual fields.

## 3. Loop bounds / record addressing

- **Daily.phy** — record cap **40,000**: `ModDailyQuiod@0x00934920` L535292/L535296 `LitI4 0x9C40=40000`; `if rec# > 40000 then rec# = rec# − 40000` @L535292-535297, so day-derived record numbers wrap into a 40,000-record file.
- **Daily.phy** — load loop `1..16,000`: `ModDailyQuiod@0x0093f5e4` L535267 `LitVarI2 1` .. L535269 `LitVarR8 0x40CF400000000000 = 16000.0` (ForVar @L535276/GetRecOwn4 @L535278/NextStepVar @L535280).
- **daily-manual.phy / daily-manual-2.phy** — date base **44,000**: `ModDailyManual@0x009203f8` L546962 / @0x0091f3d8 L547000 `LitI4 0xABE0=44000`; day# = serial − 44000 (@L546963/547001).
- **daily-manual / -2** — load loop `1..16,000`: `ModDailyManual@0x00936a14` L547059 / @0x00936394 L547102 `LitVarI4 0x3E80=16000` (GetRec4 @L547069/L547112).
- Report/UI loop `1..1000` days: `FormDailyQuiod@0x00a31298` L533146 `LitI2 0x3E8=1000`; record index = day + 40000 (L533181).

## 4. Field table — `Daily.phy` (record length **614**, money/day-journal record)

The file is moved record-by-record via `GetRecOwn4`/`PutRecOwn4`/`DestructRecord` against a module-level UDT array (`FMemLdRf [07 08 00 04 00]` + `Ary1LdRf`, ModDailyQuiod@0x0093f5e4 L535275-278, @0x00934920 L535327-329), so the FULL 614-byte layout is not spelled out in those procs. The same record is mirrored in-memory by `FormDailyQuiod` UDT arrays; the leading fields observed there (all Single/R8/I2, consistent with a per-day money summary):

| Offset | Type | Size | Purpose | Evidence (pcode_disasm.txt:line) |
|---|---|---|---|---|
| 0x00 | Single (R4) | 4 | money group value (cash?) | MemLdFPR4/MemStFPR4 `[8c 00 00]`/`[91 00 00]` after AryInRecLdPr `[ff 06 04 00 01 00]`: L533276, L533297, L533318; L534014, L534036, L534058 |
| 0x04 | Single (R4) | 4 | money group value | MemLdFPR4 `[8c 04 00]` L533201; MemStFPR4 `[91 04 00]` L533935 |
| 0x08 | Single (R4) | 4 | money group value | MemLdFPR4 `[8c 08 00]` L533219; MemStFPR4 `[91 08 00]` L533954 |
| 0x18 | Single (R4) | 4 | money group value | MemLdFPR4 `[8c 18 00]` L533237; MemStFPR4 `[91 18 00]` L533973 |
| 0x30 | Integer (I2) | 2 | counter (transaction count) | MemLdI2 `[89 30 00]` L533911; MemStI2 `[8e 30 00]` L533918 |
| 0x34 | Double (R8) | 8 | money amount | MemStFPR8 `[92 34 00]` L533905 |
| 0x3c | Double (R8) | 8 | money amount | MemLdFPR8 `[8d 3c 00]` L533767, L533892; MemStFPR8 `[92 3c 00]` L533886 |

All rows above are from `FormDailyQuiod@0x00a31298` (L533114) and `FormDailyQuiod@0x00a67570` (L533737), which populate the daily money UDT array (module offset 0x03 via `ImpAdLdRf [05 03 00]`, and record array at offset 0x04 via `AryInRecLdPr`). These are the money-group fields of the daily quota record. **Offsets 0x3c..614 are UNKNOWN** — the balance of the record (614 − 68 = ~546 bytes: further money fields, fixed strings, flags) is only moved wholesale by the ModDailyQuiod file procs and not individually referenced in the code examined this run.

## 5. Field table — `daily-manual.phy` (52) / `daily-manual-2.phy` (56)

| Offset | Type | Size | Purpose | Evidence |
|---|---|---|---|---|
| 0x00 | Single (R4) | 4 | manual money value (per day) | ModDailyManual@0x0090cc18 L547137 MemLdFPR4 `[8c 00 00]`, L547151 MemStFPR4 `[91 00 00]`; ModDailyManual@0x00913cbc L547179/L547193; FormDailyManual@0x009d9b5c L546800 |

`daily-manual-2.phy` (56) = `daily-manual.phy` (52) + 4 bytes → likely one extra R4 field beyond offset 0x00; that field and all offsets ≥ 4 are UNKNOWN (records otherwise moved wholesale via `GetRec4`/`PutRec4` with length literal, e.g. L546991 PutRec4, L547069/L547112 GetRec4).

## 6. Known vs unknown summary

- **Known**: file names; record lengths (Daily.phy = 614, daily-manual = 52, daily-manual-2 = 56); record caps/bounds (40000 Daily cap, 16000 load loops, 44000 manual date base); the money-group R4 fields at 0x00/0x04/0x08/0x18, I2 at 0x30, R8 at 0x34/0x3c (Daily), and R4 at 0x00 (both manual files).
- **Unknown**: full 614-byte Daily layout beyond 0x3c; manual records beyond 0x00 (except the +4-byte size delta of daily-manual-2); exact runtime filename assembly (LitStr idx 5/6 resolve only to the string-reference blob, not text).

## 7. Other files still needing layout work (NOT mapped this run)

delivery.phy, PIFary.phy, workperiod.phy, drugeye-for-titan.phy, fromdrugeye.phy — all present in strings_utf16.txt (idx 7144/7116/7218/7244/7149) and left for a follow-up agent.