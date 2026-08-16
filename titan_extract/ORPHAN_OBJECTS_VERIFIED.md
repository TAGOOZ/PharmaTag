# ORPHAN OBJECTS VERIFIED — TITAN.W1 (Phye.exe)

Status legend: CONFIRMED = count + purpose matched in pcode; REFUTED = claim contradicted by pcode; STILL-UNKNOWN = exists but purpose unprovable.
Ground truth: `titan_decompile/pcode_disasm.txt` (headers `[Type] Name @0xADDR`), `strings_utf16.txt` (idx = 1-based line − 3), `/tmp/opencode/full_refs2.json` (423 keys).

---

## 1. Modallinone — CONFIRMED (10 procs) as REPLACE/TEMPLATE builder; ZIP claim REFUTED

10 headers found (objects.txt: 10 ✓):
| Addr | pcode line | size | notes |
|---|---|---|---|
| 0x0095a86c | 583175 | 192 | path building, 10 imports |
| 0x0093bde4 | 583233 | 128 | path building, 7 imports |
| 0x00b33550 | 583273 | 5476 | **main proc** (1674 lines), see below |
| 0x00a23780 | 584947 | 704 | NewIfNullPr + ThisVCallHresult; barcode/discount |
| 0x008f1570 | 585135 | 32 | `Start` entry stub |
| 0x00ac97cc | 585148 | 1888 | array/price compare, 5 import targets |
| 0x00945f08 | 585830 | 156 | NewIfNullPr + 2 VCallHresult; idx7424 `aEnabled` |
| 0x0099265c | 585887 | 292 | NewIfNullPr + 2 VCallHresult; sales GUID |
| 0x008fbbc8 | 585977 | 56 | stub |
| 0x008f9bb4 | 586003 | 52 | stub |

Main proc @0x00b33550:
- 89 import calls / 30 distinct targets, **ZERO VCall tokens** → NOT an object/zip flow.
- Strings: idx6142 `Replace` (**44 refs in this proc alone**, full_refs2 = 47 total), idx8958 `اجمالي الشراء قبل الضريبة` (line 583433), idx14590 blob (line 583443).
- idx14590 blob = ~500 UTF-16LE bytes, hex `44-2d-43-00…`, **no `PK` magic → NOT a zip payload** (REFUTED). It is a shared template blob: 39 refs codebase-wide, mostly `ModBackupMonthly@0x00b0d14c` (23). Blob is not zlib/zip.
- Conclusion: a **Replace-heavy template/report builder** (fills a template blob with `اجمالي الشراء قبل الضريبة` etc.), not an all-in-one ZIP flow.

VCall-bearing procs (@0x00a23780 / 0x00945f08 / 0x0099265c): strings are `Block barcode from usage`, `CoReg`, `CoTaskMemAlloc`, `Alto Sax`, `<drg>`, `pH4`, discount-limit msg (idx12542), sales GUID idx7423 `a2a100e1-906b-44df-99c2-6e7c6098421e` — barcode/discount/SQL helpers, not cZipArchive. **cZipArchive VCall claim NOT reproduced** (REFUTED). cZipArchive itself = PropertyPage class, 88 procs (objects.txt:350, pcode procs@3907+).

## 2. ModAutoUpdate — CONFIRMED (1 proc); purpose STILL-UNKNOWN

- 1 header @0x009269d4, pcode 405003, size 108 (objects.txt: 1 ✓).
- NewIfNullPr [24 01 00] → VCallHresult [0d 14 00 02 00] + [0d 50 00 03 00]; ConcatStr + idx4; ImpAdCallI2 `5e 05`; FnAbsVar; compares 0xC3EC40 (12860000) and 0x9C40 (40000); ImpAdCallFPR4 `0a 06`.
- **No update-related strings** (idx4 = `\x01!허P` artifact). Shape = date/expiry compare on an object. Purpose cannot be proven from pcode → STILL-UNKNOWN.

## 3. ModNewsLine — count REFUTED (objects.txt 2, pcode 1); purpose CONFIRMED news-line loader

- objects.txt:247 says procs=2, but only **1** header in pcode: @0x009ddb44, line 351367, size 508.
- Loops an array (ForVar), writes fixed-record fields (offsets 0x08/0x0c/0x18/0x20/0x28/0x64) with dates + strings; only string idx2303 `1-5-2020`.
- = news-line record loader. Count discrepancy should be fixed in objects.txt.

## 4. ModPharX — CONFIRMED (1 proc); JSON-building API client

- 1 header @0x00a831b0, pcode 542690, size 1188 (objects.txt: 1 ✓).
- Builds JSON: idx255 `"street": `, idx6398 `Stakeholder user with the specified username not found!`, idx5374 `Invalid region` (line 542806). ~35 VCall tokens (object/JSON). Imports `0a 0d/10/13/1f/2b`.
- = pharmacy-X JSON API module. idx5374 = `Invalid region` (checked).

## 5. FormIntegrations — CONFIRMED (9 procs); report/setup form

9 headers found (objects.txt: 9 ✓): @0x00a0a34c (`رابعا` idx11519), @0x0098b060 (`ايجارات` idx10495 + idx2303), @0x009210f8 (HTML div idx3327 `<div>قيمة كل ادوية الصيدلية بسعر الجمهور = `), @0x00a438ec (`رابعا` ×several), @0x00a766e0 (`1-5-2020` ×3), + 3 stubs, @0x00a32ee8.
- @0x0098b060 builds an HTML/div report via a 9-arg ImpAdCallFPR4 `0a 0d 00 48 00`.
- = integrations setup + HTML value-report builder.

## 6. FormEcommerce (6) + ModEcommerce (4) — counts CONFIRMED; HungerStation linkage REFUTED (dead strings)

- ModEcommerce 4 headers: 0x00ad9fd8 (2000 B, inventory array/price loops `MemLdFPR8`), 0x00ab2b48, 0x009dd684 (`Start`, `Medical object` idx5630, `Invalid region`), 0x0092d0e0 (sales GUID + ImpAdCallFPR4 `0a 3b`).
- FormEcommerce 6 headers: 0x00a61f00 (`رابعا`), 0x009386c8 (GUID), 0x00a6acc0 (`Start`, `جرد الاصناف` idx11262, `Stakeholder…`), 0x00a39058 (`1-5-2020`, `59`), 0x009c35a0, + stub.
- **HungerStation strings are DEAD**: `db_9ffe55_titanecommerce` (idx7673), `hungerstation.*` token/credential files (idx7150–7152), `https://hungerstation.partner.deliveryhero.io/…` (idx7947–7948) → **0 refs in full_refs2.json**.
- api_integration.md:474-475 / feature_external_integrations.md:37 HungerStation claim rests on unreferenced strings → **REFUTED as active code**. Procs are inventory/price + GUID SQL helpers.

## 7. FormInternet — CONFIRMED (7 procs); seller/internet form

7 headers found (objects.txt: 7 ✓): @0x00a0f600 (idx5375 `Invalid seller information.` + 15 imports), @0x0096c720 (sales GUID), @0x008ef620 (32 B), @0x0098a50c (`رابعا` idx11519), + 3 size-4 stubs (0x008d9bc8, 0x008d9b94, 0x008d9ac4).
- @0x00a0f600: object calls (NewIfNullPr [24 03 00] → VCallHresult `14/50`), string concat chain — seller info validation/registration. idx5375 has 436 refs codebase-wide (shared error string).

## 8. Raz — cross-check (334 procs in pcode; objects.txt:379 mismatch)

- pcode has **334** `[Module] Raz` headers → matches user's 334, **contradicts objects.txt:287 (379)**. objects.txt count is wrong.
- Cross-check only (raz_complete.md). First procs mirror ModFTP boilerplate (identical sizes/frames) — standard stub set; blob idx14590 referenced at Raz@0x00995e58:571100.

---

## Summary table

| Object | objects.txt | pcode | Verdict |
|---|---|---|---|
| Modallinone | 10 | 10 | CONFIRMED (template/Replace); ZIP + cZipArchive REFUTED |
| ModAutoUpdate | 1 | 1 | CONFIRMED count; purpose STILL-UNKNOWN |
| ModNewsLine | 2 | 1 | count REFUTED; purpose CONFIRMED (news loader) |
| ModPharX | 1 | 1 | CONFIRMED (JSON API client) |
| FormIntegrations | 9 | 9 | CONFIRMED (report/setup form) |
| FormEcommerce | 6 | 6 | count CONFIRMED; HungerStation REFUTED (dead strings) |
| ModEcommerce | 4 | 4 | count CONFIRMED; HungerStation REFUTED (dead strings) |
| FormInternet | 7 | 7 | CONFIRMED (seller/internet form) |
| Raz | 379 | 334 | objects.txt count WRONG (334 correct) |

## Actions needed downstream
1. Fix objects.txt: ModNewsLine 2→1, Raz 379→334.
2. Strip HungerStation linkage claims from api_integration.md:474-475 / feature_external_integrations.md:37 (dead strings).
3. Update modules_remaining_2.md:124,226,262,362,525 — statuses per table above.