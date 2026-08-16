# TITAN.W1 — Day-to-Day Operational Utility Forms (نماذج تشغيلية يومية)

**Project:** TITAN.W1 (Phye.exe) — VB6 P-Code Pharmacy Application
**Scope:** Small helper forms and dialogs used during daily pharmacy operation. None own the main sales/purchase flow; each is a self-contained utility (grid viewers, record files, keyboard helpers, classification/totals tools) invoked from the main screens or reports. Two forms in the assigned cluster are already documented elsewhere and are only referenced here (`FormSellTime`, `FormootThisDay`).

| Form | Procs | Purpose (per `ui_strings.json`) | Status |
|---|---|---|---|
| `FormMagazine` | 12 | المجلة/الكتالوج — magazine/catalog viewer | New |
| `FormMrdKashf` | 10 | معاينة حسابات المدينة — receivables preview | New |
| `FormExam` | 7 | وحدة الفحص — examination unit (record file) | New |
| `FFFMHFZ` | 10 | نموذج: FFFMHFZ (generic) — message/utility box | New |
| `FFFUM` | 10 | إدارة المستخدمين — user management | New |
| `FFFPiano` | 12 | تخطيط لوحة المفاتيح — keyboard layout | New |
| `Forminputtotal` | 5 | إجمالي المدخلات — input totals | New |
| `FormExForceChanged` | 3 | العناصر المعدّلة بالقوة — force-changed items | New |
| `FFFPriceExtra` | 3 | تسعير إضافي — extra pricing | New |
| `FFFDrugsClassification` | 2 | تصنيف الأدوية — drug classification | New |
| `FormDaysShortNote` | 14 | ملاحظات يومية قصيرة — daily short notes | New |
| `FFFDrugsMore` | 11 | أدوية إضافية — additional drugs | New |
| `FormSellTime` | 9 | توقيت المبيعات — sales timing | Covered (`feature_sales_invoices.md:18`) |
| `FormootThisDay` | 11 | مخرجات هذا اليوم — today's output | Covered (`feature_reports_analytics.md:30`) |

Sources: `pcode_disasm.txt` (proc bodies with line numbers), `strings_utf16.txt` (verified line numbers), `ui_strings.json` (form purposes), `ui_complete.md` (menu wiring), existing `feature_*.md` docs.

---

## 1. FormMagazine — المجلة/الكتالوج (Magazine/Catalog Viewer)

**Purpose (inferred):** A general "magazine/journal" viewer that loads a named data set (`and master = N`, strings_utf16.txt:1282) into a grid and renders running totals. Its strings mix catalog-style totals, drawer-printer wiring, and main-device-only guards, so the exact screen is unconfirmed.

**Evidence**
- 12 procs, headers at pcode_disasm.txt:414188–414983. Main grid builders: `0x00a73b00` (414983, size=1184 — 22 grid-column writes), `0x00a527b4` (414700, size=916), `0x009bf058` (414223, size=424). No record-file I/O (only OpenFile absent; loads come from array data).
- Totals strings: `اجمالي الصافي` (net total, strings_utf16.txt:8962) referenced by `0x00981bf0`/`0x00a527b4`; `<div>قيمة كل ادوية الصيدلية بسعر الجمهور = ` (public-price value of all drugs, strings_utf16.txt:3330) in `0x009671f0`/`0x00a73b00`.
- Drawer/master guards (all in `0x00a73b00`): `هذا الاجراء من اختصاص الجهاز الرئيسي فقط` (main-device only, strings_utf16.txt:13058), `يجب توصيل الدرج بطابعة الريسيت بكابل شبيه التليفون` (drawer-to-receipt-printer wiring, strings_utf16.txt:13314), `لقد تم ايقاف ميزة الغاء الحفظ نهائيا اتصل بخدمة العملاء` (strings_utf16.txt:12546).
- Path/token strings: `5856-1296-1296-5628` (strings_utf16.txt:2818), `</local-folder-path>` (3072-range), `>>ftpcmd.dat`, `الدقهلية:المنزلة` (region, strings_utf16.txt:9986).
- `ui_strings.json` purpose: `المجلة/الكتالوج`.

**Workflow:** Load data set → populate grid columns → accumulate net/public-price totals → guard on main device + drawer wiring. No saving inside the form (cancel-save disabled message).

**Connections:** Same guard strings as `FormMrdKashf` (`0x00a2daa4`) and `FFFMHFZ` `0x00b557e8`; likely invoked from a cash-drawer/receipt-printing flow.

---

## 2. FormMrdKashf — معاينة حسابات المدينة (Receivables/Debtor Accounts Preview)

**Purpose (confirmed by purpose string, but note name ambiguity):** `ui_strings.json` labels it `معاينة حسابات المدينة` (preview of "medina" accounts = receivables/debtor accounts, i.e. كشف حساب). Despite the task-name hint of "patient examination", the Arabic purpose string and its sibling forms (FormMRDAgel حسابات المدينة, FFFMRD وحدة حسابات المدينة) place it in the accounts-receivable family.

**Evidence**
- 10 procs, headers at pcode_disasm.txt:581667–582982. Main grid proc `0x00ae56ac` (581667, size=2340, frame=376): array-driven grid fill with date filter — reads array string+double members, converts dates (`CVarDate`), populates grid via `LateIdSt`; 31 array reads in the body.
- `0x009bd920` (582434, size=428) is a loader: references sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (strings_utf16.txt:7426), `Start`, `Titan.path`, `deactivate`, `\Files\DBI\month.start.stock.` (7168-range), `Package ... cannot be found in system!` (5888-range).
- `0x00912888`/`0x009129b8` (582558/582593, size=100 each): drug-warning / net-total snippets (`testosterone not suitable for pregnancy`, strings_utf16.txt:8448-area; `اجمالي الصافي`, strings_utf16.txt:8962).
- `0x00a2daa4` (582714, size=800): same master-device + drawer guard strings as FormMagazine (strings_utf16.txt:13058/13314/12546), plus `مشاهدة اجمالية للعملاء` (overall customer view, strings_utf16.txt:12803) and `ادخل رقم موبايل صحيح ليتخدم ككود لنسختك علي السيرفر` (mobile-as-license-code, 9216-range).
- No record-file I/O; data sourced from arrays/recordsets.

**Workflow:** Pick accounts-receivable range → main proc filters rows by date and fills the grid with debtor balances; totals computed for the "net" column. Guarded by main-device-only restrictions.

**Connections:** Sibling forms `FormMRDAgel` (7 procs) and `FFFMRD` (11 procs) exist but are NOT covered by `feature_customers_suppliers.md` (which covers balances) or any feature doc — a gap (see §Gaps).

---

## 3. FormExam — وحدة الفحص (Examination Unit)

**Purpose (inferred):** Small "examination/inspection" unit that persists one record to a fixed-length record file (`.phy`-style). Its only non-trivial strings are a public-price drug-value line and the generic `رابعا`, so the exact examination is unconfirmed.

**Evidence**
- 7 procs, headers at pcode_disasm.txt:350876–351336.
- Record write proc `0x00910754` (351306, size=84): `OpenFile` (channel 0x16, record length 0x7bea), `PutRecOwn4` of form field `MemLdRfVar [0x34]` as record #1, then `Close`. This is genuine record-file I/O — the only form in this cluster with it.
- Record read proc `0x0091358c` (351336, size=88): reads the record back (`GetRecOwn4` path), closes.
- `0x009f2f0c` (350978, size=572): report-style builder — `ForVar` loop over array `MemLdRfVar`, per-element branch on flags `[89 58 02]`/`[89 5a 02]`, writes `<div>قيمة كل ادوية الصيدلية بسعر الجمهور = ` (strings_utf16.txt:3330) HTML line; references `1-5-2020` (strings_utf16.txt:2306).
- `ui_strings.json` purpose: `وحدة الفحص`.

**Workflow:** Open record file → read existing record into form → user edits → write record #1 back → close. A companion report proc streams a drug-value line with a HTML div.

**Connections:** Record-file pattern matches `ModOneFile`/`Files` module family (`feature_misc_modules.md` §14/§16). Likely invoked from an inspection/audit screen.

---

## 4. FFFMHFZ — Generic Form / Message-String Aggregator

**Purpose (unconfirmed):** `ui_strings.json` gives only the placeholder `نموذج: FFFMHFZ`. One proc (`0x00b557e8`, 9736 bytes) is a giant string/message aggregator holding ~79 tokens spanning many features — evidence of a shared message module rather than a single screen.

**Evidence**
- 10 procs, headers at pcode_disasm.txt:397141–400891.
- `0x00b557e8` (397715, size=9736): ~79 decoded strings across money, stock and guard topics, including `ايرادات` (revenues, strings_utf16.txt:10499), `اكد المبلغ كاش` (confirm cash amount, strings_utf16.txt:9731), `جرد حسابي` (stock reconciliation, strings_utf16.txt:11267), `راس المال` (capital, strings_utf16.txt:11523), `Expiry detection` (4866), `Medicines changed their powers automatically` (5635), `Explanation field cannot be empty` (4867), `لقد تم ايقاف ميزة الغاء الحفظ نهائيا...` (12546). Also `\Files\DBI\month.start.stock.`, `<drg>`, `http://www.oorsprong.org/websamples.countryinfo`, `CoTaskMemAlloc`, `Alto Sax`, `Warfarin+piroxicam Potential for serious bleed`.
- `0x0099cfb4` (397499, size=316): `Expiry detection` (strings_utf16.txt:4866) + `"street": "` JSON token — expiry + JSON/bluetooth profile.
- `0x00a26d1c` (397141, size=736): JSON `"street": "` token (256-range) — profile/JSON marshaling.
- No grid operations and no file I/O; the form is mostly procs that raise message boxes / emit strings.

**Workflow:** Used as a shared message/string hub for expiry detection, money confirmations and stock reconciliation prompts. The `Expiry detection` proc is the only concrete function identifiable.

**Connections:** Message strings overlap FormMagazine/FormMrdKashf guards and `ModStockTest` (stock reconciliation, `feature_misc_modules.md` §20). The FFF prefix groups it with other FFF* tool dialogs (`ui_complete.md:229` shows FFFPiano in same family).

---

## 5. FFFUM — إدارة المستخدمين (User Management)

**Purpose (confirmed):** User-management dialog. `ui_strings.json` labels it `إدارة المستخدمين`. Fills grids with user/permission data and issues permission/warning messages.

**Evidence**
- 10 procs, headers at pcode_disasm.txt:347302–347959. Grid builders `0x00a1df5c` (347302, size=740, frame=188) and `0x00a2a6e8` (347533, size=792, frame=192) dominate (arrays + grid writes).
- `0x0095cbe0` (347860, size=216): permission messages — `Give permissions of normal user`, `Invalid seller information.`, `Medicines` (strings 5120/5376/5632-range) and `Dh,` (4608-range).
- Small event procs: `0x00938020` (347791, size=144), `0x0095b534` (347959, size=200), `0x009118a4` (347934, size=76). No file I/O.
- `ui_strings.json` purpose: `إدارة المستخدمين`.

**Workflow:** Load user list into grid → edit/grant permissions per user → raise warnings for invalid seller data. No fixed record file — user data comes from arrays/DB.

**Connections:** Complements the user/permission tooling in `feature_users_permissions_menus.md` (which documents FFFUserList/FFFUserEdit/FormMenusPerUser but not FFFUM — see §Gaps).

---

## 6. FFFPiano — تخطيط لوحة المفاتيح (Keyboard Layout / "Piano")

**Purpose (inferred):** `ui_strings.json` purpose is `تخطيط لوحة المفاتيح` (keyboard layout). Two large procs are keyboard-handler dispatch chains: they compare incoming keycodes (ASCII 0x5A 'Z' … 0x2F '/') and route to form methods. Strings in the pool include `البيانو` (strings_utf16.txt:9870) and `برنامج البيانو` (strings_utf16.txt:10587), but no proc in this form references them via the global pool — name meaning unconfirmed.

**Evidence**
- 12 procs, headers at pcode_disasm.txt:212913–213644.
- Keyboard handlers `0x00a28190` (213086, size=804, frame=40) and `0x00a01804` (213358, size=656, frame=8): sequences of `MemLdI2`/`ILdI2` keycode compares against byte literals 0x5A/0x58/0x43/0x56/0x42/0x4E/0x4D/0xBC/0xBE/0xBF, then `VCallAd` dispatch to form methods (form-method calls at `0x0004`).
- `0x00924564` (213034, size=116): references the sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (strings_utf16.txt:7426) three times — GUID seed/diagnostics.
- `0x0091f124` (213572, size=104): numeric loop (0..100) — counter/speed control.
- Stub handlers `0x008dcd30`/`0x008dc978` (213609/213616, size=8 each); misc `0x0095e3c8` (212913), `0x008fca40` (212988), `0x008f5798` (213013), `0x008f17fc` (213067), `0x008ef470` (213623), `0x00918f00` (213644).

**Workflow:** KeyDown/KeyPress events are captured; each mapped keycode triggers a `VCallAd` form method (menu/shortcut action). The GUID proc suggests an activation/diagnostic path.

**Connections:** Referenced in `ui_complete.md:229` as "Piano utility". The "بيانو" (piano) naming plus a keyboard-layout purpose is consistent with a shortcut-key / soft-keyboard screen. Unconfirmed.

---

## 7. Forminputtotal — إجمالي المدخلات (Input Totals)

**Purpose (confirmed):** Totals summary for input (purchase/receipt) flows. `ui_strings.json` labels it `إجمالي المدخلات`.

**Evidence**
- 5 procs, headers at pcode_disasm.txt:432709–433315. Main grid proc `0x00a5f638` (432994, size=920, frame=340): array reads + grid writes (totals grid); `0x009dc8fc` (432709, size=532): grid builder referencing `CREATE TABLE titanneed (` (768-range) and `and master = N` (strings_utf16.txt:1282).
- `0x008e5b08` (433315, size=20): trivial — `ImpAdCallFPR4` numeric conversion (amount conversion helper).
- `0x0097d1b4` (432863, size=284), `0x00911d54` (432956, size=92): totals/format helpers. No file I/O.
- `ui_strings.json` purpose: `إجمالي المدخلات`.

**Workflow:** Aggregate input amounts into a grid with running totals; convert amounts via `ImpAdCallFPR4`; filter with `and master = N`.

**Connections:** Complements purchase entry (`feature_purchases.md`) — an input-side counterpart to the sales "output today" screen.

---

## 8. FormExForceChanged — العناصر المعدّلة بالقوة (Force-Changed Items)

**Purpose (inferred):** `ui_strings.json` labels it `العناصر المعدّلة بالقوة` — a listing of items whose data was changed by force. The two main procs are near-identical builders.

**Evidence**
- 3 procs, headers at pcode_disasm.txt:404610–404953.
- `0x009f9300` (404610, size=600) and `0x009f17ec` (404786, size=572): grid builders referencing `and master = N` (strings_utf16.txt:1282) and `target nvarchar(20) default '')` (1024-range, SQL `titanneed` create) plus `*Send*note*` (1792-range). Frame=224 both — same routine shape.
- `0x0093c9d8` (404953, size=152): event handler. No file I/O.
- `ui_strings.json` purpose: `العناصر المعدّلة بالقوة`.

**Workflow:** Query force-modified items (expiry/price overrides) from the DB, render as a grid; send-note path included. Likely shown after a bulk/force change operation.

**Connections:** Related to expiry/price enforcement (see `feature_drug_master_pricing.md`); the `titanneed` table reference links it to the DB-rebuild family (`feature_misc_modules.md` §16).

---

## 9. FFFPriceExtra — تسعير إضافي (Extra Pricing)

**Purpose (inferred):** Small extra-pricing dialog. `ui_strings.json` labels it `تسعير إضافي`.

**Evidence**
- 3 procs, headers at pcode_disasm.txt:654492–654549. Main proc `0x00967eac` (654549, size=240, frame=72): array reads + numeric conversions (`ImpAdCallFPR4`) and branch logic — computing an extra price value.
- `0x00923698` (654492, size=108), `0x008f4544` (654527, size=48): event handlers. No grid strings, no file I/O.
- `ui_strings.json` purpose: `تسعير إضافي`.

**Workflow:** Enter/adjust an extra price component; values converted to FPR4 and applied. No shared strings decoded, so the specific extra-price kind (per-unit? per-size?) is unconfirmed.

**Connections:** Pairs with `FFFDrugsMore` (below) as drug-card adjunct dialogs; general pricing flow in `feature_drug_master_pricing.md`.

---

## 10. FFFDrugsClassification — تصنيف الأدوية (Drug Classification)

**Purpose (confirmed):** Drug classification screen. `ui_strings.json` labels it `تصنيف الأدوية`, and the global pool holds its exact prompts.

**Evidence**
- 2 procs, headers at pcode_disasm.txt:456110–456139. `0x00917348` (456110, size=88): single branched proc. `0x008ecc70` (456139, size=32): stub.
- Classification strings (global pool): `تصنيف الادوية حسب عدد الوحدات الوسطي` (classify by average unit count, strings_utf16.txt:10863), `تصنيف الادوية وفقا لاخر تعامل` (classify by last transaction, strings_utf16.txt:10864), `حدد تصنيف الادوية المبحوثة وفترة البحث اولا من الازرار المجاورة` (strings_utf16.txt:11320), `امر الضبط الشامل يساعد في سرعة تصنيف الادوية والمستحضرات` (strings_utf16.txt:10438).
- `ui_strings.json` purpose: `تصنيف الأدوية`.

**Workflow:** Choose classification method (avg units vs last-transaction recency) + search period → assign category. Heavily string-driven; likely a guided dialog.

**Connections:** Classification feeds drug-card fields in `feature_drug_master_pricing.md`; NOT covered there (gap confirmed).

---

## 11. FormDaysShortNote — ملاحظات يومية قصيرة (Daily Short Notes)

**Purpose (confirmed):** Daily short-notes screen whose self-describing message states it was created to "show all effects on the cash-drawer finances during the day for review, located in the Money (ماليات) menu" (strings_utf16.txt:11010).

**Evidence**
- 14 procs — the largest in this cluster. Headers at pcode_disasm.txt:443762–445889.
- Self-documenting message proc `0x00934ab0` (445889, size=132): references `تم استحداث شاشة تظهر كافة المؤثرات علي مالية الدرج اثناء اليوم للمراجعة وهي موجودة في قائمة ماليات` (strings_utf16.txt:11010) and `رابعا` (strings_utf16.txt:11522).
- Grid builders `0x00a73608` (443762, size=1152), `0x00a7cfc4` (444098, size=1212), `0x00a817d8` (444461, size=1248), `0x00a88184` (444816, size=1284): array/grid population with `and master = N` (strings_utf16.txt:1282), `</local-folder-path>`, and date loops (`ForVar` over day counts).
- `0x00a3d6b4` (445356, size=864): heavy array processing (12 array reads, 4 loops) — the note/effect accumulator. `0x009c6268` (445706, size=456): 18 array reads — second accumulator.
- Snippet procs: `0x00991190` (445178, size=320) + `CREATE TABLE titanneed (` (768-range); small handlers at 445269–445336 and 445689.
- No record-file I/O. `ui_strings.json` purpose: `ملاحظات يومية قصيرة`.

**Workflow:** Track per-day financial effects on the cash drawer (cash/network, shortages/surpluses) into arrays; render day rows in a grid with a short-note per day. The review screen lives under the ماليات (money) menu.

**Connections:** Cash-drawer daily money effects tie into `feature_balances.md` (day cash/net) and the daily closing flow (`feature_account_closing.md`). NOT covered elsewhere (grep of all feature docs returned no hit).

---

## 12. FFFDrugsMore — أدوية إضافية (Additional Drugs)

**Purpose (inferred):** Drug-card adjunct dialog for extra drug information/value. `ui_strings.json` labels it `أدوية إضافية`.

**Evidence**
- 11 procs, headers at pcode_disasm.txt:654108–654462. Main builder `0x009b54cc` (654108, size=396): `Block app from this path` (strings_utf16.txt:4099) + `<div>قيمة كل ادوية الصيدلية بسعر الجمهور = ` (strings_utf16.txt:3330) — path guard + public-price value line.
- `0x00938f08` (654388, size=144): region string `الدقهلية:المنزلة` (strings_utf16.txt:9986).
- `0x0091720c`/`0x0091ce6c` (654303/654268): `Start` (6400-range) string handlers. Small event/stub procs at 654237, 654256, 654334, 654353, 654369, 654440, 654462.
- No file I/O. `ui_strings.json` purpose: `أدوية إضافية`.

**Workflow:** From a drug card, open the "more drugs" dialog; guard against unauthorized paths, render value line; region-specific data. Purpose mostly inferred — no workflow-specific Arabic strings decoded.

**Connections:** Adjunct to `feature_drug_master_pricing.md` drug master; NOT covered there.

---

## 13. FormSellTime — توقيت المبيعات (Sales Timing) [COVERED]

Already documented. See `feature_sales_invoices.md:18` (sales timing / وقت البيع) and `feature_sales_returns.md:18`. 9 procs at pcode_disasm.txt:346340–347278; key strings include the network-amount confirmation (`اكد المبلغ ...` family). Referenced only here for completeness.

## 14. FormootThisDay — مخرجات هذا اليوم (Today's Output) [COVERED]

Already documented. See `feature_reports_analytics.md:30` and `feature_sales_invoices.md:25` (today's invoices, incl. returns). 11 procs at pcode_disasm.txt:409612–411887. Referenced only here for completeness.

---

## Summary Table

| Form | Procs | Purpose | Status | Covered-already-in |
|---|---|---|---|---|
| FormMagazine | 12 | المجلة/الكتالوج — catalog viewer | inferred | — |
| FormMrdKashf | 10 | معاينة حسابات المدينة — receivables preview | confirmed (name) | — |
| FormExam | 7 | وحدة الفحص — examination unit | inferred | — |
| FFFMHFZ | 10 | generic message hub | unconfirmed | — |
| FFFUM | 10 | إدارة المستخدمين — user mgmt | confirmed | — |
| FFFPiano | 12 | تخطيط لوحة المفاتيح — keyboard layout | inferred | — |
| Forminputtotal | 5 | إجمالي المدخلات — input totals | confirmed | — |
| FormExForceChanged | 3 | العناصر المعدّلة بالقوة | inferred | — |
| FFFPriceExtra | 3 | تسعير إضافي — extra pricing | inferred | — |
| FFFDrugsClassification | 2 | تصنيف الأدوية — drug classification | confirmed | — |
| FormDaysShortNote | 14 | ملاحظات يومية قصيرة — daily notes | confirmed | — |
| FFFDrugsMore | 11 | أدوية إضافية — additional drugs | inferred | — |
| FormSellTime | 9 | توقيت المبيعات | covered | feature_sales_invoices.md:18 |
| FormootThisDay | 11 | مخرجات هذا اليوم | covered | feature_reports_analytics.md:30 |

---

## Gaps & Open Questions

1. **FormMrdKashf naming vs purpose.** Name suggests "examination" (كشف), but the UI purpose is receivables preview (معاينة حسابات المدينة). The sibling family `FormMRDAgel`/`FFFMRD`/`FormMrdAmlManual` (7/11/9 procs) is undocumented in feature docs — likely a dedicated receivables/installment (MRD) cluster worth its own doc.
2. **FormExam** — the only form in the cluster writing a fixed-length record file (record #1, channel 0x16). What is being "examined"? Candidate: expiry/inspection audit. Needs the .phy file name to confirm.
3. **FFFMHFZ** — a 9736-byte string aggregator holding tokens from many features (money, stock, JSON, WHO country service, SFDA expiry). Likely a shared message module; its exact screen (if any) is unidentifiable from strings alone.
4. **FFFPiano** — the "بيانو" strings (البيانو / برنامج البيانو) are in the global pool but not referenced by any FFFPiano proc; the form's purpose rests on the `تخطيط لوحة المفاتيح` label + keycode-dispatch procs. Confirm whether it is a real shortcut-key screen or a leftover.
5. **FFFPriceExtra / FFFDrugsMore** — no workflow-specific strings; purposes are labels only. Local (form-scoped) string tables were not resolved, so the exact extra price/drug fields are unknown.
6. **FFFUM** is not covered by `feature_users_permissions_menus.md`; reconcile which user-management forms own which permissions UI.
7. **FormDaysShortNote** — 14 procs (largest here) but no record-file I/O; the day-effects arrays likely read from the sales DB via `titanneed`-style tables. Confirm the ماليات (money) menu wiring in `ui_complete.md`.