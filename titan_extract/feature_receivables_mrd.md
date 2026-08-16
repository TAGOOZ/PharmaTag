# Feature: حسابات المدينة — MRD Receivables (المديونيات / MRD)

**Purpose:** Full extraction of the receivables / debtor-accounts (حسابات المدينة) feature of TITAN.W1 (Phye.exe). Covers the MRD family of forms — `FormMRDAgel` حسابات المدينة (المديونيات), `FFFMRD` وحدة حسابات المدينة, `FormMrdAmlManual` حسابات المدينة اليدوية, and `FormMrdKashf` معاينة حسابات المدينة — plus their connections to the agent/employee module (`ModAmil`), the money-details screen (`FormMonyDetails`), the agent-report archive (`FormAmilReportsArchiv`), and how they relate to customer/supplier balances, the sales `agel` field, and the ledger cluster. **This document is a cluster-level map**: the exact per-proc byte analysis is in the *Relevant Files* section and the sister feature docs; here we reconcile the four MRD forms against each other and against the business flow, flag confirmed vs inferred facts, and record dead/unused strings.

The MRD (مدفوعات MRD / installment customers) cluster is the receivables side of the credit-sale (أجل) pipeline: credit sales post a customer debt via the sales screen (`feature_customers_suppliers.md:43-49`, `feature_sales_invoices.md:151-157`), and this cluster displays, reviews, and manually adjusts those debts. Note an apparent **naming split**: `ui_strings.json` lists all four MRD forms as "حسابات المدينة" variants, while `ui_complete.md:140-144` labels them by function (installment customers / installment payments / manual entry). The disassembly shows the first three are near-identical grid-building forms with very few global pool strings, and `FormMrdKashf` (already covered in `feature_operational_utilities.md §2`) is the "preview" screen.

---

## 1. Objects

| Object | Type | Arabic | Role |
|--------|------|--------|------|
| `FormMRDAgel` | Form (7 procs) | حسابات المدينة (المديونيات) / مدفوعات MRD | Debtor accounts (installment payments) screen — three near-identical grid builders, a count guard, a grid-setup proc, a stub, and a large 580-byte builder. Only global string used: ايجارات (rents). |
| `FFFMRD` | Form (11 procs) | وحدة حسابات المدينة | Debtor accounts unit — small numeric/array procs, **zero** global-pool string references. |
| `FormMrdAmlManual` | Form (9 procs) | حسابات المدينة اليدوية / ادخال يدوي MRD | Manual receivables entry — grid builders keyed to the sales GUID `a2a100e1-...` (idx 7423); includes a string-concat/export proc. |
| `FormMrdKashf` | Form (10+ procs) | معاينة حسابات المدينة | Receivables preview — main @0x00ae56ac size=2340, uses idx 11519 رابعا. **Already documented in `feature_operational_utilities.md §2` — reference, do not duplicate.** |
| `ModAmil` | Module (44 procs) | العاملين | Agents/employees module — sales/purchase/stock/financial report generation, HTML/text export procs (`business_logic_complete.md §12`). Parent of the MRD manual-entry data. 30+ procs span `pcode_disasm.txt:67432–69900`. |
| `FormMonyDetails` | Form (7 procs) | تفاصيل النقود | Money/cash details (RPT-F01) — pure numeric, no pool strings (`feature_accounting_ledger.md:19,60-61`). |
| `FormAmilReportsArchiv` | Form (6 procs) | أرشيف تقارير الموظفين | Agent report archive — archive load loop + report builder using sales GUID idx 7423 (`feature_accounting_ledger.md:59`). |

**Data mapping:** `titanksasales` — chain sales ledger (schema_complete §7), has explicit `payed` and `agel` columns (`schema_complete.sql:113-121`); `invoicedata` — invoice header/line items with `payed`/`agel` (`schema_complete.sql:168-176`). The MRD forms are **UI-only grids** — they read/write in-memory arrays and the sales GUID; the *persistence* of the receivable itself is the `agel` column written by the sales loop (idx 7423), not by these forms directly.

---

## 2. Step-by-step workflow

### 2.1 Receivable creation (source side, in the sales feature)
1. In the sales screen, a credit sale sets `agel` (اجل) portion of the invoice; total constraint `totalvalue = payed + agel` (`feature_sales_invoices.md:153`).
2. Saving requires the `السماح بالبيع الاجل` permission (idx 10040) and fails when debt+current invoice exceeds the credit limit (idx 8965).
3. The sales GUID loop (idx 7423) writes `titanksasales`, and customer/supplier balances auto-update (idx 10709) — `feature_balances.md:60` (note: that doc prints idx as the strings_utf16 line; verified idx = line − 3).

### 2.2 FormMRDAgel — display / review receivables

The form is built from seven procs (`pcode_disasm.txt:178352-179100`):

| Proc | Line | Size | Frame | Role |
|------|------|------|-------|------|
| @0x00a0a620 | L178352 | 648 | 320 | Grid builder #1 |
| @0x00a0e9fc | L178563 | 664 | 320 | Grid builder #2 |
| @0x00a0e700 | L178780 | 664 | 320 | Grid builder #3 |
| @0x008eed34 | L178997 | 36 | 4 | Count guard (count == 0x1b) → proc 0x0d |
| @0x009711bc | L179014 | 260 | 108 | Grid setup (two `LitVarI4`, `LateIdCallSt`, `ImpAdCallFPR4`; local binary idx 32) |
| @0x008dbd00 | L179093 | 8 | 0 | Stub (`ThisVCallHresult`) |
| @0x009f784c | L179100 | 580 | 320 | Grid builder #4 |

- The three builders (@0x00a0a620, @0x00a0e9fc, @0x00a0e700) plus @0x009f784c follow the **same pattern**: load a form member (`LateIdLdVar [61 58 ff 01 00 03 68]`), compare against the pool string **ايجارات (rents, idx 10495)** via `EqVarBool`, then loop `ForVar` counters (~0xc9 = 201 and 0x1388 = 5000 rows) reading array elements (`Ary1LdPr` / `MemLdRfVar`) and writing grid cells (`LateIdCallSt` / `ImpAdCallFPR4`).
- The ايجارات comparison appears **twice per proc** (L178359/L178394, L178570/L178605, L178787/L178822) — an *inferred* rent-category filter/branch inside each builder.
- Proc @0x008eed34 (size=36) is a guard: branches when a count equals 0x1b (27) and calls proc 0x0d — likely an empty-list / row-cap message path (inferred).
- Proc @0x009711bc (size=260) is the grid setup — issues two `LitVarI4` (0x00/0x01) calls, grid `LateIdCallSt`, and `ImpAdCallFPR4`; uses local binary string idx 32 (`\x01=\xecP`) as a column key.
- Proc @0x008dbd00 (size=8) is a `ThisVCallHresult` stub (no-op).

### 2.3 FFFMRD — debtor accounts unit

Eleven procs (`pcode_disasm.txt:205826-206079`), all small; **no global-pool string is referenced at all** (empty `pcode_strings.py` output; no idx2refs entries):

| Proc | Line | Size | Frame | Role |
|------|------|------|-------|------|
| @0x008de8bc | L205826 | 16 | 0 | Stub |
| @0x008fec74 | L205835 | 64 | 4 | Float store + count==0x1b guard, `VCallHresult` 0x10/0x06 |
| @0x008dc588 | L205864 | 8 | 0 | `ImpAdCallFPR4` 0x07 stub |
| @0x0091dcfc | L205871 | 104 | 72 | Numeric/array proc |
| @0x008ee5a8 | L205911 | 40 | 12 | Guard |
| @0x00909450 | L205932 | 72 | 40 | Numeric proc |
| @0x0091da50 | L205959 | 108 | 100 | Array/grid proc |
| @0x008ec43c | L205999 | 28 | 4 | Guard |
| @0x0093aa88 | L206013 | 140 | 148 | Larger numeric handler |
| @0x008ec82c | L206063 | 32 | 4 | Guard |
| @0x0093cc78 | L206079 | 164 | 8 | Larger numeric handler |

- @0x008fec74 (size=64) stores a float (`ImpAdStR4`), compares count == 0x1b (27), and dispatches `VCallHresult` 0x10/0x06.
- Inference: FFFMRD is a helper module backing the MRD grids (row counting, formatting), consistent with `ui_complete.md:512` "MRD (installment customers) management".

### 2.4 FormMrdAmlManual — manual receivables entry

Nine procs (`pcode_disasm.txt:288121-289008`):

| Proc | Line | Size | Frame | Role |
|------|------|------|-------|------|
| @0x00a27e20 | L288121 | 788 | 184 | Main grid builder (ForVar 780, `MemLdI2` 0x00/0x0c/0x3c) |
| @0x008e6528 | L288381 | 20 | 16 | Call proc 0x14 |
| @0x0092c4b0 | L288393 | 120 | 140 | Array read (`Ary1LdPr` string field 0x1c) |
| @0x009ba398 | L288433 | 424 | 132 | Grid column setup — **idx 7423 GUID** at L288438 |
| @0x00a0cc4c | L288555 | 652 | 264 | State machine — 3 ForVar loops, `MemLdI2` 0x0c vs 1/2, `ThisVCallHresult` 0x08/0x11 |
| @0x008ee390 | L288770 | 32 | 64 | Flag + `ThisVCallHresult` |
| @0x008ee3e8 | L288783 | 32 | 64 | Flag + `ThisVCallHresult` |
| @0x00a00490 | L288796 | 632 | 188 | Grid renderer — `MemLdFPR4` 0x04/0x08, `ImpAdCallFPR4` 0x13/0x15 |
| @0x0098d218 | L289008 | 316 | 84 | String-concat / export — **idx 7423 GUID** at L289011, repeated |

- Main grid builder @0x00a27e20 (size=788, frame=184): loops `ForVar` 0x30c (780 rows), reads `MemLdI2` fields 0x00/0x0c/0x3c, `MemLdRfVar` arrays, `LateIdCallLdVar`, writes via `ImpAdCallFPR4`.
- Grid column setup @0x009ba398 (size=424): issues a `LitVarStr` GUID **idx 7423** (`a2a100e1-906b-44df-99c2-6e7c6098421e`) at L288438, then `LateIdCallSt` column headers.
- State machine @0x00a0cc4c (size=652): three `ForVar` loops comparing `MemLdI2` field 0x0c to 1 and 2, dispatching `ThisVCallHresult` 0x08/0x11 — row-mode selection (new/edit modes, inferred).
- Grid renderer @0x00a00490 (size=632): `MemLdFPR4` fields 0x04/0x08, `ImpAdCallFPR4` 0x13/0x15, `LateIdCallSt` writes.
- **String-concat / export proc @0x0098d218 (size=316)**: begins at L289008 with a `LitVarStr` GUID idx 7423 at L289011 and repeats `LitVarStr [3a 5c ff 17..22 00]` + `[3a 3c ff 18 00]` (all decoding to idx 7423) plus local binary idx 60 (`\x01Y\xecP`) — builds a GUID-prefixed text line (export/print payload, inferred).
- Small procs: @0x008e6528 (size=20) calls proc 0x14; @0x0092c4b0 (size=120) reads a `LateIdLdVar [0a]` field and array (`Ary1LdPr`) string field 0x1c; @0x008ee390/@0x008ee3e8 (size=32 each) set flag + call `ThisVCallHresult`.

### 2.5 FormMrdKashf — preview
- Fully documented in `feature_operational_utilities.md §2` (main @0x00ae56ac, size=2340, idx 11519 رابعا at L582753; proc @0x009f24c4). **Referenced here only.**
- Proc inventory (from `pcode_strings.py search "FormMrdKashf"`): @0x00ae56ac (main, L581667), @0x008e67f8 (L582422), @0x009bd920 (L582434, idx 6399 `Start`), @0x00912888 (L582558, idx 7423 GUID at L582573), @0x009129b8 (L582593, idx 7423 at L582608), @0x008dac08 (L582628), @0x00967c54 (L582635), @0x00a2daa4 (L582714), @0x009f24c4 (L582982).
- Cluster notes for cross-checking: the preview main proc reads a form member `[61 60 ff 04/05 00 00 00]`, writes grid cells via `LateIdSt [2c 04 00 00 00]` / `LateIdCallSt [fe a4 41 00 00 00 02 00]`, loops `ForVar` over the receivable rows, and formats floats with `ImpAdCallFPR4` 0x3d/0x3e/0x40 — the same grid-writing signature as the FormMRDAgel builders, confirming a shared renderer family across the cluster.
- The preview also consumes the sales GUID (idx 7423) at L582573/L582608 and `Start` (idx 6399) at L582445, tying it to the same GUID-keyed receivable data.

### 2.6 Related screens (money / agents)
- `FormMonyDetails` (7 procs, RPT-F01) — money details, numeric only (`feature_accounting_ledger.md:19,60-61`).
- `FormAmilReportsArchiv` (6 procs) — archive load (135 items) + report builder using sales GUID idx 7423 (`feature_accounting_ledger.md:59`).
- `ModAmil` (44 procs per `business_logic_complete.md:572`) — agent report generation (`business_logic_complete.md §12`); MRD-relevant procs observed during cluster search (`pcode_strings.py search "ModAmil"` reports 53 module headers spanning `pcode_disasm.txt:67432–69900`; the count difference reflects embedded sub-module headers vs documented top-level procs):
  - @0x00983f78 (size=264, frame=184), @0x0092e960 (size=124, frame=112), @0x0095c88c (size=192, frame=208) — report frame builders at `pcode_disasm.txt:67432+`.
  - Notable embedded strings: `"taxableItems": [` (idx 256, L69763), HTML `<td style...>` table markup (idx 1024, L69841/L69854), `*AddMasrouf*` (idx 1536, L69940), `St` (idx 6399, L69964).
  - ModAmil is the parent of the manual entry / agent report archive: agent sales and allowances feed the same GUID-keyed data model as MRD.
  - Sample full proc list (first 30 headers): @0x00983f78, @0x0092e960, @0x0095c88c, @0x008db51c, @0x00903b44, @0x00913de0, @0x0091545c, @0x009a9af4, @0x00944dd8, @0x0090ee2c, @0x009163b4, @0x0090ed9c, @0x008e2c60, @0x00959038, @0x0099c5fc, @0x009d3750, @0x00931110, @0x009ef1b0, @0x009531dc, @0x009b09a8, @0x009f05bc, @0x008d8c8c, @0x0092acb4, @0x00944954, @0x008eee98, @0x0098b1f4, @0x00a7c9f0, @0x0099fb6c, @0x0094952c, @0x008eb62c.

### 2.7 How to read the evidence
- Ground truth is `pcode_disasm.txt` (proc ranges listed in §1 table); every proc line is cited as `L<line>`.
- String indices: `strings_utf16.txt` line number **minus 3** = idx. 2-byte `LitVarStr [3a <hi> <lo>]`: idx = `((hi&0x3F)<<8)|lo` when the first operand byte < 0x80; otherwise 4-byte `idx = b[1]|(b[2]<<8)|(b[3]<<16)`.
- `idx2refs2.json` maps idx → [[pcode_line, 'Form@addr']...]; a count of 0 means the string is pool-only (dead), the documented convention used in §5.

### 2.8 Cross-form invariants (the 27-row motif)
- FormMRDAgel's guard @0x008eed34 and FFFMRD's @0x008fec74 both compare a count to **0x1b (27)** before branching/calling. Combined with the grid builders capping at ~201 and ~5000 rows, this suggests a shared fixed-width receivable row model across the two forms (27 columns × up to N rows).
- All MRD grid procs write cells with the identical `LateIdCallSt [fe a4 41 00 00 00 02 00]` signature (also present in FormMrdKashf), reinforcing that FormMRDAgel / FormMrdAmlManual / FormMrdKashf are three views over the same in-memory receivable array.

---

## 3. Fields / data captured

### 3.1 Columns implied by the grid builders
- FormMRDAgel: 27-column guard (0x1b) at @0x008eed34/@0x008fec74; rows capped at ~201 and ~5000 across the three builders; numeric cells formatted with `ImpAdCallFPR4`.
- FormMrdAmlManual: 780-row loop; `MemLdI2` field 0x0c selects row mode (1/2); float fields 0x04/0x08; string field 0x1c; column headers set with GUID + `LateIdCallSt`.
- Exact column labels are **not in the global pool** — the forms use local binary string keys (idx 8/32/60/96 etc.) instead of the readable Arabic headers.

### 3.2 Sales-side receivable fields (persistence)
- `titanksasales`: `payed` (amount paid), `agel` (age/type — the credit portion per `feature_sales_invoices.md:153`), `pharmacyid` (`schema_complete.sql:111-121`).
- `invoicedata`: `payed` / `agel` / `pharmacyid` (`schema_complete.sql:168-176`).
- Customer balance and credit limit live in `wzcustomers` (`creditlimit`, current debt) — updated from the sales screen (`feature_customers_suppliers.md:33,43-49`).

### 3.3 Shared business identifier
- **idx 7423 = `a2a100e1-906b-44df-99c2-6e7c6098421e`** — the sales GUID. Referenced 3,564× across the binary, including FormMrdAmlManual (L288438, L289011, L289018–L289081) and the ledger/archive/report cluster (`feature_accounting_ledger.md:55,59,61,127`). This is the canonical key linking MRD manual entries to the sales data.

### 3.4 Pool layout of receivable strings (strings_utf16.txt)
Verified string indices in the receivable/money zone (idx = line − 3):
- idx 8944 `اجل العملاء`, idx 8947 `اجمالي الاجل اليوم`, idx 8965 `اجمالي المتبقي... (credit-limit block)`, idx 8966 `اجمالي المدفوع فيزا اليوم`.
- idx 8922 `اثناء عرض مديونية العميل... (invoice counted in debt)`, idx 8987 `اجمالي مديونية`, idx 9155 `ادخل المديونية الحالية`, idx 9156 `ادخل المديونية الحالية للعميل`, idx 9320 `اذا اردت ان تسدد جزء من مديونية العميل...`, idx 10040 `السماح بالبيع الاجل`, idx 10277 `المتبقي في الاجل`, idx 10299 `المديونية`, idx 10426 `اما اذا اردت ان تصحح المديونية...`, idx 10834 `تصحيح مديونية العميل الحالي`, idx 11463 `خطأ في حسابات هذه الفاتورة...`, idx 11857 `ضبط المديونية`, idx 12132 `في حقل المديونية ادخل المديونية الفعلية الحالية`.
- idx 13341 `يجب ان يكون مجموع الاجل والمدفوع مساويا لسعر الفاتورة` (payed+agel==total constraint).
- The Arabic column captions `مسلسل / اسم العميل / المديونية / التعاملات / زيارات / الموبايل...` (idx 12787-12790) and `رقم الفاتورة / التاريخ / قيمة الفاتورة / الضريبة / مدفوع نقدا / مدفوع شبكة / اجل / المورد / الفرع` (idx 11559-11560) are **pool-only** (0 refs) — the MRD forms draw their grid labels from local binary keys instead (see §3.1).

---

## 4. Side-effects

- **Balances:** the customer/supplier balances auto-update from sales/purchases (idx 10709); opening balances include الرصيد الافتتاحي لمديونيات العملاء (`feature_balances.md:72`). The MRD forms themselves do **not** write balances — they display/edit the underlying sale rows.
- **Manual correction:** the sales/customer feature exposes manual debt correction via `تصحيح مديونية العميل الحالي` (readable:10182) and `التعديل اليدوي لارصدة العملاء` (readable:9258) (`feature_customers_suppliers.md:39`); FormMrdAmlManual is the dedicated manual-entry surface for this.
- **Reports:** agent archive and money reports consume the sales GUID (`feature_accounting_ledger.md:59,61`).
- **Permissioning:** credit sales require `السماح بالبيع الاجل` (idx 10040) and are per-user (`feature_sales_invoices.md:155`).

---

## 5. Dead / unused strings (pool-only, 0 refs in `idx2refs2.json`)

These receivables-related strings exist in the pool but are **not referenced by any proc** — dead UI leftovers:

- idx 8922: `اثناء عرض مديونية العميل في شاشة المبيعات يتم احتساب الفاتورة الحالية حتي لو غير محفوظة` (note: the *live* version of this logic is driven by the sales feature, not a string ref)
- idx 8965: `اجمالي المتبقي من هذه الفاتورة ومديونية هذا العميل اكبر من الحد الائتماني...` (credit-limit block message)
- idx 8987: `اجمالي مديونية`
- idx 9155/9156: `ادخل المديونية الحالية` / `ادخل المديونية الحالية للعميل`
- idx 9320: `اذا اردت ان تسدد جزء من مديونية العميل او كلها ... حقل مدفوع اسفل الشاشة`
- idx 10277: `المتبقي في الاجل`
- idx 10299: `المديونية`
- idx 10426: `اما اذا اردت ان تصحح المديونية فيمكنك الاستمرار هنا`
- idx 10834: `تصحيح مديونية العميل الحالي`
- idx 11857: `ضبط المديونية`
- idx 12132: `في حقل المديونية ادخل المديونية الفعلية الحالية`
- idx 10040: `السماح بالبيع الاجل`
- idx 11463: `خطأ في حسابات هذه الفاتورة من فضلك راجع قيم المدفوع والاجل`
- idx 12787/12788/12790: `مسلسل اسم العميل المديونية...` column-header strings (grid caption leftovers)
- Also unreferenced (debt/money messaging, same status): idx 8947 `اجمالي الاجل اليوم`, idx 8944 `اجل العملاء`, idx 11559/11560 (invoice-table headers listing `مدفوع نقدا/مدفوع شبكة/اجل/المورد/الفرع`), idx 10336 `المنصرف اجل`.

(Note: `idx2refs2.json` only carries decoded reference maps for the subset of pool strings actually exercised by decoded procs; 0 refs here means *dead at disassembly time*, which is the documented convention.)

---

## 6. Side-effects / cross-feature wiring (see also §4)

- **`feature_customers_suppliers.md`** — credit limits, current debt, manual debt correction, and the credit-limit save block.
- **`feature_sales_invoices.md`** — `agel`/`payed` split, credit permission (idx 10040), invoice-in-debt calculation.
- **`feature_balances.md`** — auto-updating balances (idx 10709), opening receivables, sales GUID write of `titanksasales`.
- **`feature_accounting_ledger.md`** — FormMonyDetails (RPT-F01), FormAmilReportsArchiv, sales-GUID identifier across ledger cluster.
- **`feature_operational_utilities.md §2`** — FormMrdKashf preview (do not duplicate here).

---

## 7. Gaps & open questions

1. **The rent-string puzzle:** FormMRDAgel's only global-pool string is **ايجارات (rents, idx 10495)**, compared against form member `[61 58 ff 01 00 03 68]` in every large proc. Given the form is "debtor accounts", the most likely reading is a category/account filter where "rents" (ايجارات) is one selectable account (it is a chart-of-accounts sub-account per `feature_accounting_ledger.md §3.5`) — **unconfirmed**. It could also be a leftover from a templated grid builder shared with the chart-accounts screen.
2. **FFFMRD has zero pool strings** — pure numeric; its 27-count guard (0x1b) matches FormMRDAgel's, suggesting a shared row model, but no Arabic labels exist at all. Whether it *is* the data provider for the FormMRDAgel grids is **unconfirmed**.
3. **Table mapping:** no `mrd*` table exists in `schema_complete.sql`; receivables persist as `agel` on `titanksasales`/`invoicedata`, and the MRD forms read in-memory arrays keyed by local binary strings (idx 8/32/60/96). The exact array population procs are **unconfirmed** (candidates: ModAmil report loads, `Reload_mrd_500` in `business_logic_complete.md:200`).
4. **FormMRDAgel vs FFFMRD vs FormMrdAmlManual:** three separate "حسابات المدينة" screens with different shapes (27-col vs 780-row vs string-export) — the menu/screen-launch mapping is **unconfirmed** (`ui_complete.md:140-144` gives functional labels only).
5. **Export proc @0x0098d218:** the GUID-prefixed string-concat strongly suggests an export/print payload, but its target (file/network/print) is **unconfirmed**.

---

## Relevant Files
- `titan_decompile/pcode_disasm.txt` — FormMRDAgel procs L178352–179100; FFFMRD L205826–206079; FormMrdAmlManual L288121–289008; FormMrdKashf L581667–582982; FormMonyDetails L407615–408201; ModAmil L67432+.
- `titan_decompile/strings_utf16.txt` — string pool (idx = line − 3); idx 10495 ايجارات @line 10498, idx 7423 GUID @line 7426.
- `titan_decompile/strings_readable.txt`, `titan_decompile/ui_strings.json` — readable Arabic labels + form purposes.
- `titan_extract/schema_complete.sql` — `titanksasales` (§7), `invoicedata` (§11), `wzcustomers`.
- `titan_extract/feature_operational_utilities.md` (§2 FormMrdKashf), `feature_customers_suppliers.md`, `feature_accounting_ledger.md`, `feature_balances.md`, `feature_sales_invoices.md`, `ui_complete.md` (lines 140-144, 505-534), `business_logic_complete.md` (§3 Raz `Reload_mrd_500`, §12 ModAmil).