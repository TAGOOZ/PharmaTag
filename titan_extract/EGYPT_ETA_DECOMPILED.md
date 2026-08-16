# Egypt ETA e-Invoicing — Decompiled Path (TITAN.W1 / Phye.exe)

## 1. What the ETA path does

- 3 objects implement the Egyptian Tax Authority (ETA) e-invoicing feature:
  `ModDttsEgypt` (2 procs), `ModEtaWrappper` (7 procs), `FormEtaInfo` (9 procs) = 18 procs total.
- ETA invoice **JSON fragments** live in the string pool and are heavily referenced
  (idx 228–267: `"amount":`, `"rate":`, `"subType": "`, `"taxType": "`,
  `"buildingNumber": "`, `"street": "`, `"taxableItems": [`, `"buyer": {`,
  `"seller": {`, `"commercialDiscountData": [`, `"itemDiscountData": [`, etc.),
  confirming the app assembles ETA invoice payloads as JSON (not SOAP/XML).
- The ETA submission URL set (`https://api.invoicing.eta.gov.eg`, preprod, `id.eta.gov.eg`,
  `https://invoicing.eta.gov.eg`) IS in the string pool but has **ZERO references in p-code** —
  the submission code path in this build is **dead/inert** (see §4).
- `C:\eToolKit\` (appsettings.json, toolkit.exe, summer_with_uuid.json, e_sqlite3.dll…),
  `C:\eta-qr\`, and the `set root=C:\eToolKit` batch strings are also **0-reference dead strings**.

## 2. ModDttsEgypt (2 procs)

### Proc @0x009b3cb4 — size=332, frame=264 (pcode_disasm.txt:556534–556638)
- CONFIRMED: references idx255 `"street": ` at L556543, 556554, 556566, 556601
  (4 refs, idx255 total 248 refs / 8 procs; utf16 line 258). Builds an ETA invoice
  JSON address block (`"street":`).
- Uses LitStr idx5/7/8 (low-index literals) for `Like` comparisons (L556582/589/590).
- 7 import calls / 7 distinct targets (mostly `ImpAdCallFPR4`/`ImpAdCallI2` helpers).

### Proc @0x00aa5278 — size=1504, frame=308 (pcode_disasm.txt:556639–557063)
- CONFIRMED: references the sales UUID GUID `a2a100e1-906b-44df-99c2-6e7c6098421e`
  (idx7423, utf16 line 7426, **3564 refs** — the shared "sales UUID" GUID used across
  the app). Used for `"uuid":`/`"previousUUID":` fields.
- References idx3327 `<div>قيمة كل ادوية الصيدلية بسعر الجمهور = ` (Arabic report header,
  **465 refs**; also used by FormEtaInfo @0x0090a2a8), idx9726 `اكد الاختيار مرة اخري`
  (confirm dialog), idx8190 `p@4`, idx7678 `ddd`, idx7422 `a`.
- 20 import calls / 15 distinct targets — the busiest of the 18 procs (loops over
  pharmacy sales, builds per-sale JSON + report header).

## 3. ModEtaWrappper (7 procs)

### Proc @0x00a5f250 — size=1060, frame=60 (pcode_disasm.txt:554085–554429) — MAIN BUILDER
- Builds a large string by concatenating low-index literals with **fixed-length string
  variables** (`LdFixedStr [33 XX 00]`, lengths 0x32/0x32/0x32/0x28/0x0a/0x10/0x14/0x32/0x08
  at L554093, 117, 141, 194, 218, 242, 266, 290, 314) plus property/member lookups
  (`ImpAdLdPr → MemLdRfVar → ImpAdCallI2`) — the ETA XML/JSON wrapper builder.
- References LitStr indices 0,3,4,5,6,7,8,9,0x0a,0x0b,0x0c,0x0e,0x0f,0x10…0x29
  (34 distinct low indices; idx4 used 16×). These decode (per strings_readable.txt) to the
  ETA JSON template fragments + whitespace indentation.
- 33 import calls / 7 distinct targets.

### Procs @0x008f6c4c (52B, 554430–451), @0x008f4280 (40B, 554452–470), @0x0094e004 (176B, 554471–525)
- Small helpers; `If Not cond Then … Exit Sub` pattern (validation/guard checks).
- 0x0094e004: 2 nested conditionals.

### Proc @0x00922aa0 — size=104, frame=120 (pcode_disasm.txt:554526–559)
- References idx6399 `Start` (utf16 line 6402, **996 refs** — shared). Stub shows `1 = "Y"`
  (likely a Boolean flag toggle).

### Proc @0x008ddf38 — size=12, frame=4 (pcode_disasm.txt:554560–567)
- Single import call, no strings — trivial wrapper.

### Proc @0x009c4bfc — size=436, frame=136 (pcode_disasm.txt:554568–730)
- Guards + state writes (`_MemProperty_ = 30 / 255`, `_VarRef_ And 0`); 16 import calls.

## 4. FormEtaInfo (9 procs) — ETA link-status UI

- @0x00a29940 (796B, 554731–965): references idx5375 `Invalid seller information.`
  (utf16 line 5378, **436 refs**) — seller/branch validation error; 27 import calls / 5 targets.
- @0x009eb2ec (572B, 554966–555141): 27 import calls / 2 targets, no strings.
- @0x00909e68 (72B), @0x009154f4 (92B), @0x00915590 (92B), @0x009156c8 (92B):
  small; idx15 + idx16/18/19/20.
- @0x0091e714 (108B, 555270–303) and @0x009cf27c (472B, 555304–445): both reference
  idx11519 `رابعا` (utf16 line 11522, **1350 refs** — section 4 of an Arabic report).
- @0x0090a2a8 (72B, 555446–470): references idx3327 (Arabic `<div>قيمة كل ادوية…`).

## 5. String-pool status (LIVE vs DEAD)

| String | utf16 line | idx | Refs | Status |
|---|---|---|---|---|
| `https://api.invoicing.eta.gov.eg` | 7941 | 7938 | 0 | DEAD |
| `https://api.preprod.invoicing.eta.gov.eg` | 7942 | 7939 | 0 | DEAD |
| `https://id.eta.gov.eg` | 7949 | 7946 | 0 | DEAD |
| `https://id.preprod.eta.gov.eg` | 7950 | 7947 | 0 | DEAD |
| `https://invoicing.eta.gov.eg` | 7951 | 7948 | 0 | DEAD |
| `C:\eToolKit\` + appsettings/toolkit.exe… | 4177–84 | 4174–81 | 0 | DEAD |
| `C:\eta-qr\` | 4185 | 4182 | 0 | DEAD |
| `set root=C:\eToolKit` | 8362 | 8359 | 0 | DEAD |
| `"street": ` | 258 | 255 | 248 | LIVE |
| sales UUID GUID | 7426 | 7423 | 3564 | LIVE |
| `<div>قيمة كل ادوية الصيدلية بسعر الجمهور` | 3330 | 3327 | 465 | LIVE |
| `Invalid seller information.` | 5378 | 5375 | 436 | LIVE |
| `رابعا` | 11522 | 11519 | 1350 | LIVE |
| `Start` | 6402 | 6399 | 996 | LIVE |

Ref counts from idx2refs2.json/full_refs2.json; DEAD confirmed independently by
raw byte-pattern scan of pcode_disasm.txt (no `LitStr/LitVarStr` operand encodes them).

## 6. Builder gaps / STILL-UNKNOWN

- **Submission is dead in this build**: the ETA endpoint URLs are never loaded from the
  string pool by any p-code. Either the URLs come from a runtime source (DB/config/
  user-provided, e.g. the dead `C:\eToolKit\appsettings.json` tool) or ETA submission was
  stubbed/removed. No WinInet/WinHTTP/XHR import targets were confirmed in the 18 procs.
- **Low-index literal text (idx 0–57)**: strings_utf16.txt shows a decode artifact
  (`\x01…허P`) for these; strings_readable.txt decodes them as the ETA JSON template
  fragments + whitespace. Exact byte content of each wrapper fragment is STILL-UNKNOWN
  (extraction artifact), though the family is confirmed as ETA JSON template tokens.
- **ModEta class** (48 procs, project_structure.json:6751) is the biggest consumer of the
  ETA JSON fragments (e.g. 0x009bb674, 0x00a6d248) — **OUT OF SCOPE** for this report but
  required to trace the actual invoice assembly end-to-end.
- ZATCA/Saudi ModDTTS/VAT computation: NOT examined (out of scope, hard stop).

## 7. Key references

- pcode_disasm.txt line ranges per proc: see §2–§4.
- strings_utf16.txt: idx = 1-based line − 3 (verified: idx255@L258, idx7423@L7426).
- Reference map: /tmp/opencode/idx2refs2.json (162 idx), full_refs2.json (423 idx).
- Stubs (p-code placeholders): ModEtaWrappper.bas, ModDttsEgypt.bas, FormEtaInfo.frm.
