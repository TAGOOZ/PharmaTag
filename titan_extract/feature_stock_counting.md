# Feature: Stock Counting / Inventory (جرد ارصدة)

## Purpose
The stock-counting feature lets a pharmacist take a **physical count** of on-shelf
inventory, compare the counted quantity against the **system stock**, and then
**correct the balance** up or down. Corrections are recorded as stock-movement rows
in `wzgard` (with cost + VAT + total-with-VAT) so the counted balance, average cost,
and VAT exposure all stay consistent with the rest of the system.

---

## 1. Objects

| Object | Type | # procs | Address | Role |
|---|---|---|---|---|
| `ModStock` | Class | ~165 | `0x00ad4a50`+ | Core stock engine: add/update/query/delete stock, cost+vat rolls, corrections, negative-balance handling |
| `ModStorage` | Module | many | `0x00998a08`+ | Storage/warehouse helpers feeding stock moves |
| `ModNed` | Class | several | (search `Class ModNed`) | Shortages/needs engine |
| `FFFDrugrasidCorrect` | Form | 28 | `0x008da0dc`+ | **Drug balance correction** screen (جرد/تعديل الارصدة) |
| `FormDrugRasidCorrectCalc` | Form | 3 | `0x0096ef2c`+ | Correction calculator (up vs deficit) |
| `FormStockNow` | MDIForm | several | `0x009bea80`+ | Current stock view (الرصيد الان) |
| `FormSilsila` | Form | 26 | `0x009d4058`+ | Chain-pharmacy / serial-connection view |
| `FFFSilsilaStock` | MDIForm | 2 | `0x009e2fcc`+ | Chain stock view |
| `FormMinimumControl` | Form | 23 | `0x009ca240`+ | Minimum-stock control (set حد الطلب / حد ادني) |
| `FormAutoOrder` | Form | 43 | `0x0097b6fc`+ | Automatic order generation |
| `FormNeedsAll` | Form | 50 | `0x00972d14`+ | All-needs management (النواقص المجمعة) |
| `FormNeedsDetails` | Form | 9 | `0x00962af4`+ | Needs details |
| `FormNedBirbish` | Form | 6 | `0x009c040c`+ | Needs calculation |
| `ModStockTest` | Module | — | — | Test helpers for stock |

> Note: per the extraction notes, the Arabic UI strings and several SQL fragments
> live in the `strings_utf16.txt` table even where they are not (or only partially)
> referenced as live `LitStr` in the p-code. The string table is authoritative for
> content; p-code shows live usage where found.

---

## 2. Step-by-step workflow

### 2.1 Entering a physical count (جرد)
1. From the main screen: **قائمة الادوية → جرد الادوية** (Drugs menu → Drug counting).
2. The counting screen (`FFFDrugrasidCorrect`) lists drugs. It now also shows every
   drug that has **had movement**, not just drugs with a current balance
   (string idx: شاشة جرد الادوية اصبحت تعرض ايضا كل الادوية التي تمت عليها حركة وليس التي لها رصيد فقط).
3. The user searches by barcode directly (`تعديل نظام الجرد ... ليسمح بالبحث المباشر بالباركود`),
   by pharmaceutical form (الشكل الصيدلي), or by usage method (طريقة الاستخدام).
4. The user enters the **physical counted quantity** for each drug.
5. The system compares **counted vs system balance** and computes a **correction**:
   - counted > system → **تصحيح الارصدة بالزيادة** (increase / overage)
   - counted < system → **تصحيح الارصدة بالعجز** (deficit / underage)
   - or **مجموع تعديل الارصدة للدواء بالعبوة** (net correction in packs).
6. Optionally the user edits the drug name in the counting screen, removes yellow
   (highlighted) items before printing, etc.
7. A report column layout is used: **رقم الدواء | اسم الصنف | الرصيد | السعر شامل الضريبة | الاجمالي**
   and **الصنف | سعر | الرصيد | عدد شهري | قيمة شهرية | اخر شراء**.

### 2.2 Applying the correction
- The user runs **ابدأ جرد الصيدلية** (Start pharmacy count), then can run the
  **الارصدة السالبة** (negative balances) command to fix negative stock
  (strings: `اضافة امر الارصدة السالبة في قائمة ابدا جرد الصيدلية ... من قائمة الادوية`).
- Negative-balance fix moves balances **between expiry dates** to offset negative
  balances against positive ones for the same drug:
  `سيتم الان نقل الارصدة بين تواريخ الصلاحية لضبط الارصدة السالبة ومعادلتها مع الارصدة الموجبة لنفس الدواء`.
- Corrections are posted to `wzgard` with a **special `typee`** marking the stock move
  as a correction rather than a normal purchase/sale.

### 2.3 "Assume balances correct" mode (اعتبار الارصدة صحيحة)
- String idx 9678: **اعتبار الارصدة صحيحة وتم جردها لهذه الفاتورة** — a flag on a
  purchase invoice meaning "treat the current balances as verified/counted and
  accept them as the opening for this invoice." This is how opening balances are
  seeded.
- Related: **الارصدة الافتتاحية** (opening balances, idx 9750), and prompts to enter:
  - **ادخل الرصيد الافتتاحي للمخزون بسعر التكلفه غير شامل الضريبه** (opening stock at
    cost excluding VAT, idx 9131)
  - **ادخل الرصيد الافتتاحي للخزينه** (opening cash drawer, idx 9130)
  - **ادخل الرصيد الافتتاحي لمديونيات العملاء / لمستحقات الموردين** (opening customer
    debit / supplier credit, idx 9132-9133).

### 2.4 Approval workflow (optional, newer versions)
- A user can submit a **balance-correction request**; the **manager** accepts or
  rejects it (strings: `اصبح من المتاح ان يقوم اي مستخدم بتقديم طلب تعديل الرصيد ويمكن للمدير قبول الطلب او رفضه`,
  `مراجعة الطلبات المعلقة لتعديل الارصدة`, `بعد ان تم تقديم الطلب حدث تعديل علي الرصيد لا يمكن قبول الطلب`).
- Balance edits are restricted by permission **7 or higher**
  (`منع المسخدمين من تعديل الارصدة الا بحصولهم علي صلاحية 7 او اعلي`).

### 2.5 Share balances between pharmacies
- `مشاركة الارصدة ما بين صيدلياتي-رفع` (upload) and `-عرض` (view), used to seed
  sub-pharmacies without re-counting (`هذا الجزء بغرض تأهيل الصيدلية الفرعية للربط بدون إعادة جرد`).

---

## 3. Fields / data captured

### Counting screen fields
- Drug name (editable during count)
- Barcode (direct search)
- System balance (الرصيد الحالي / الرصيد الان)
- Physical counted quantity
- Calculated correction (زيادة / عجز)
- Expiry date (الرصيد وتواريخ الصلاحية)
- Price including VAT (السعر شامل الضريبة)

### `wzgard` columns (per schema_complete.sql:58-74)
| Column | Type | Meaning |
|---|---|---|
| `phar` | NVARCHAR(15) | Pharmacy ID |
| `randomid` | NVARCHAR(50) | Unique batch identifier |
| `writer` | NVARCHAR(50) | Entering user |
| `datee` | REAL | Date (VB6 serial) |
| `datetimee` | DATETIME | Date + time |
| `classy` | NVARCHAR(35) | Drug category/form |
| `quant` | REAL | Quantity |
| `expire` | REAL | Expiry (VB6 serial) |
| `price` | REAL | Price |
| `oldstock` | REAL | Previous balance before this move |
| `costvalue` | REAL | Cost value |
| `vatvalue` | REAL | VAT value |
| `totalwithvat` | REAL | Total including VAT |
| `typee` | NVARCHAR(50) | Move type (purchase/sale/return/**correction**) |
| `drugname` | NVARCHAR(100) | FK → wzdrugs |

Insert fragment (idx 7999):
```
insert into wzgard (phar,randomid,writer,datee,datetimee,classy,quant,expire,price,oldstock,costvalue,vatvalue,totalwithvat,typee,drugname) values (...)
```

---

## 4. Side-effects

### Stock
- **`wzdrugs.stock`** — updated to the counted value.
- **`wzgard`** — a correction row is appended with `typee` marking the correction;
  `oldstock` = balance before correction, `quant` = correction delta,
  `costvalue`/`vatvalue`/`totalwithvat` carry the cost+VAT of the adjusted units.
- **`wzdrugs2`** — `unitcost` / `costvalue` are recomputed from `wzgard` cost rolls.
- **`titanstock`** (per-pharmacy) and **`titanksastock`** (chain) are updated to keep
  sync copies of the new balance (idx 912 insert includes `minimum, pharmacyid, classy, stock`).
- Negative balance repair moves units **between expiry-date batches** (no net change
  to total, but re-allocates so expiry batches are non-negative).

### Money / accounting
- Counting **does not** post a cash/sales transaction; it only re-books the inventory
  valuation. However the cost/VAT values on the correction row keep the inventory
  ledger (ميزان المخزون) and VAT exposure correct.
- Opening balances (الارصدة الافتتاحية) may be recorded as special purchase-type
  invoices so stock and supplier/customer opening balances are consistent
  (`يجب تسديد الشركات من شاشة المشتريات بينما هذا الاجراء استثنائي فقط مثل تسجيل الرصيد الافتتاحي اول مرة`).
- Historical price/cost corrections are auditable via `TitanUserAction`
  (drugname, oldvalue, newvalue, mobile, curbarcode, curprice, units, datee).

### Audit
- `Titan CorrectStockForAll` (idx 834) is a global "correct stock across all
  pharmacies" routine (see business_logic_complete.md §3.1).
- `TitanUserAction` logs who changed what balance and to what (old/new values).

---

## 5. Pricing + VAT

- Counting updates `costvalue`, `vatvalue`, `totalwithvat` on the `wzgard` row so the
  weighted average cost and VAT of the drug reflect the corrected balance.
- The counting report shows **السعر شامل الضريبة** (price including VAT) and the
  **الاجمالي** (total) — the total is the sum over items of quantity × price-with-VAT.
- Opening stock entry is done **بسعر التكلفه غير شامل الضريبه** (at cost excluding VAT),
  and VAT is then added per the drug's VAT percentage (`wzdrugs.vat`).

---

## 6. Payment
- Not applicable to counting itself. Corrections re-book inventory value but do not
  create cash/visa/credit (أج) payment events.
- Opening-balance seeding may run through a purchase-style invoice where payment can
  be cash/drawer (خزينة الدفع) or supplier credit.

---

## 7. Printing
- The counting screen prints a **جرد (counting) sheet**; items highlighted (yellow)
  can be removed before printing (`في شاشة جرد الادوية يمكنك ازالة الاصناف المصفرة قبل طباعتها`).
- Report layouts are selected by a print-form number (500/600/700/800)
  (`ادخل رقم نموذج الطباعه من القيم الاتيه 500 600 700 800`).
- Reports include:
  - **تقرير تصحيح الارصدة** (balance-correction tracking report, see reports_complete.md RPT-D10).
  - Drug-movement tracking (تتبع تغيير الرصيد) — see RPT-ST06.
  - Items not counted recently (اصناف لم يتم جردها مؤخرا).

---

## 8. Tables

See schema_complete.sql. Relevant tables for counting:
- `wzdrugs` (drug master, `stock`, `price`, `vat`, `units`)
- `wzdrugs2` (`unitcost`, `costvalue`, `expire`)
- `wzgard` (stock movement ledger with cost+VAT, `typee` for corrections)
- `titanstock` (per-pharmacy stock sync copy)
- `titanksastock` (chain stock sync copy incl. `minimum`)
- `invoicedata` (opening-balance seed invoices)
- `orders` (pending balance-correction requests can be stored here)
- `TitanUserAction` (audit of balance edits)
- `farysales` (branch valuation, `costvalue`, `totalwithvat`)

---

## 9. UI strings (Arabic)

| String | idx | Meaning |
|---|---|---|
| جرد | 11258 | Count |
| جرد ادوية الصيدلية | 11259 | Count pharmacy drugs |
| جرد الأدوية | 11260 | Drug counting (screen title) |
| جرد الاصناف | 11262 | Count items |
| جرد اولي | 11263 | Initial/opening count |
| جرد حسابي | 11264 | Accounting count |
| تصحيح الارصدة | 10828/9558 | Correct balances |
| تصحيح الارصدة بالزيادة | 10829 | Correct balances up (overage) |
| تصحيح الارصدة بالعجز | 10830 | Correct balances down (deficit) |
| تعديل الارصدة والجرد | 9488 | Edit balances & count |
| الارصدة الافتتاحية | 9750 | Opening balances |
| اعتبار الارصدة صحيحة وتم جردها لهذه الفاتورة | 9678 | Assume balances correct for this invoice |
| ارصدة سالبة | 9915 | Negative balances |
| معالجة الارصدة السالبة | 12851 | Fix negative balances |
| اصناف لم يتم جردها مؤخرا | 9517 | Items not counted recently |
| اصناف تم تصحيح ارصدتها تلقائيا | 9510 | Items auto-corrected |
| تصدير الارصدة والبيانات | 10838 | Export balances & data |
| حفظ الارصدة الحالية الي ملف | 11374 | Save current balances to file |
| مشاركة الارصدة ما بين صيدلياتي-رفع | 12796 | Share balances – upload |
| مشاركة الارصدة ما بين صيدلياتي-عرض | 12797 | Share balances – view |
| مجموعة تعديل الارصدة للدواء بالعبوة | 12697 | Net balance correction in packs |
| Not Enouph Stock | 439 | Not enough stock (error) |
| Titan CorrectStockForAll | 834 | Correct stock for all (routine) |
| Files\DBI\RasidCorrect.phy | 5007 | Correction data file |
| Files\DBI\auto.correction.txt | 7129 | Auto-correction data file |
| Files\DBI\month.start.stock. | 7167 | Monthly opening-stock files |
| ReloadRasidCorrect500 | 343 | Load first 500 corrections |
| لا يمكن اجراء عملية تعديل الارصدة قبل ادخال ارصدة الصيدلية في صورة فواتير مشتريات | 12359 | Cannot correct balances before entering pharmacy balances as purchase invoices |
| لا يمكن تنفيذ هذا الاجراء الا علي نسخة خالية من الارصدة | 12403 | Only on a stock-free copy |
| وجد تيتان ان رصيد هذا الدواء غير مطابق لما هو مدون في فواتير البيع والشراء | 13227 | Titan found balance mismatch vs invoices |
| الرصيد الكلي / الرصيد الحالي / الرصيد الان | 10019-10021 | Total / current / now balance |
| الرصيد عشري | 10020 | Decimal balance |
| الرصيد وتواريخ الصلاحية | 10021 | Balance & expiry dates |
| ق.الرصيد | 12150 | Balance header (short) |
| كم منذ يوم بدات عملية الجرد الحالية | 12953 | Days since current count started |
| خلال مدة الجرد | 13238 | During the count period |

---

## 10. Business rules / edge cases

1. **Counting requires prior stock** — cannot correct balances before the pharmacy's
   balances have been entered as purchase invoices (idx 12359). This is how opening
   balances must be seeded.
2. **Zero/empty-copy restriction** — the "reset" correction only runs on a copy free
   of balances (idx 12403).
3. **Stock cannot go negative on sale** — sales that would drive stock negative are
   blocked by default (config: `منع البيع اذا كان الرصيد غير كافي`), and negative
   balances are repaired by moving units between expiry batches (idx 11727).
4. **Corrections are ledger movements** — a correction is a `wzgard` row with a
   dedicated `typee` carrying `oldstock`/`quant`/`costvalue`/`vatvalue`/`totalwithvat`.
5. **Cost & VAT follow the balance** — updating stock also re-books cost and VAT so
   valuation and VAT exposure stay consistent.
6. **Mismatch detection** — Titan flags drugs whose balance doesn't reconcile with the
   sales/purchase invoices and prior corrections (idx 13227).
7. **Counts show movement, not just positive balance** — the counting screen lists
   every drug that has had movement (idx 11765).
8. **Permissions** — editing balances requires permission ≥ 7 (idx 12958); branch
   ("تابعة") pharmacies may be restricted (هذا الاجراء متاح فقط للصيدليات التابعة).
9. **Request/approval** — modern flow lets a user submit a balance-change request that
   a manager must accept/reject (idx 9485).
10. **Audit** — all balance changes are logged to `TitanUserAction` and visible in the
    drug-movement (حركة الدواء) screen.
