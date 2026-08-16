# Feature: تعديل في فواتير (Editing Existing Sales/Purchase Invoices)

**Purpose:** How the TITAN.W1 / Phye.exe VB6 pharmacy app edits existing (already-posted) sales and purchase invoices, corrects them (stock/رصيد, VAT, discount), reverses and re-applies stock and money side-effects, and tracks who edited which invoice (audit trail). This doc is the basis for a modern replacement's invoice-edit + correction + audit capabilities.

Primary screens: `FormInvoiceTrackEditing` (تتبع فواتير المبيعات — audit trail of edited invoices), `FormLastEdited` (اخر تعديل — recency), `FormDailyQuiod`, `FFFOOTQuant`/`FFFINNquant` (sales/purchase invoice forms), `FFFDrugrasidCorrect` (رصيد correction), `FormDiscCorrect`/`FFFDiscCorrect` (discount correction), `FormOutPuttakarirSpeed` (correction receipt output).

---

## 1. Objects

| Object / Proc | Role |
|---|---|
| **FormInvoiceTrackEditing** (`@0x008e4dd0`, `@0x00a40788`, `@0x009fe8f8`, `@0x00a37a6c`) | Audit-trail form tracking which sales invoices were modified after creation. Uses SQL filter `'  and master =N'` + the app GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (reference GUID). |
| **FormLastEdited** (`@0x009eef18` … `@0x00a23474`) | Lists most-recently edited invoices; persists to `\Files\DBI\LastEdited.phy` (`LastEdited.phy`). |
| **FormDailyQuiod** (`@0x00a31298` … `@0x00aa725c`) + **ModDailyQuiod** (`@0x0093f5e4`, `@0x00934920`) | Daily cash-register edit screen; shows pharmacy value at public price (`<div>قيمة كل ادوية الصيدلية بسعر الجمهور =`); city/branch context (`اسيوط:البداري`); `CoReg`; section رابعا (4th report). |
| **FFFOOTQuant** (`@0x008f38c4` … ) | Sales invoice form (فاتورة مبيعات / Oot). Hosts edit, un-save (الغاء الحفظ), copy, transfer actions. |
| **FFFINNquant** | Purchase invoice form (فاتورة مشتريات / Inn). Hosts edit / discount / VAT correction on purchases. |
| **FFFDrugrasidCorrect** (`@0x008da0dc` … `@0x008eac7c`) + **FormDrugRasidCorrectCalc** (`@0x0096ef2c`, `@0x0099950c`, `@0x00999ffc`) | Drug running-balance (رصيد/rasid) correction. Recomputes/rebuilds stock balance. Persists to `\Files\DBI\RasidCorrect.phy`; procedures `ReloadRasidCorrect500`, `RasidCorrect loading ..`, `Rasid is Bigger than`, `Done for  ReloadRasidCorrect500`. |
| **FormDiscCorrect** (`@0x00a79cac`, `@0x009feebc`, `@0x00907db8`, `@0x009fce14`) / **FFFDiscCorrect** | Discount correction (تعديل/تصحيح الخصم). Corrects discount applied to an invoice/item. |
| **FormOutPuttakarirSpeed** (`@0x0090b0a4`, `@0x00ac2cac`, `@0x00b36284` … ) | Outputs corrected receipt / correction report (كشف تصحيح). |
| Raz.@0x00a512c0 (size 820, frame 456) | **Invoice modification** — edits an existing invoice, reverses then re-applies stock (wzgard). |
| Raz.@0x00a62be8 (size 916, frame 552) | **Invoice deletion** — removes invoice + reverses stock (largest proc). |
| Raz.@0x00a49668 (size 872, frame 404) | Invoice main controller — full invoice lifecycle including edit. |
| Raz.@0x009ee1f4 (size 444) | Invoice copy — duplicates invoice (to sales / sales return / purchases). |
| Raz.@0x00961d64 / @0x009b1a44 | Sales discount application / sales total (VAT, discounts, net) calculation. |
| Raz.@0x0093404c / @0x00938fd4 / @0x0097a07c | Purchase discount / purchase VAT / purchase total calculation. |

---

## 2. Step-by-step workflow (editing a posted invoice)

### 2.1 Invoice states (from business_logic_complete.md §16.3)
```
Saved                    — Invoice saved (محفوظ)
Unsaved                  — Invoice not yet saved (غير محفوظ)
Un save                  — Revert save (الغاء الحفظ / حفظ-الغاء الحفظ)
Copy me to another location — Duplicate invoice (نسخة / تحويل الي صيدلية اخري)
Transfer to sales return — Convert to return (تحويل الي مرتجع مبيعات / مردودات)
Transfer to purchases   — Convert to purchase (تحويل الي مشتريات / تحويل الي طلبية محولة)
```
Purchase types (business_logic §17.3): new purchase, new purchase return, transfer to purchases, transfer to purchase return.

**Key rule:** Only a **saved** invoice can be edited, and only after **un-saving** it first. Unsaved invoices can be edited freely and have their customer changed.
- `الفاتورة المحفوظة لا تملك التعديل فيها الا اذا الغيت حفظها وذلك من اسفل يسار الشاشة` — "A saved invoice cannot be edited unless you cancel its save (from the bottom-left of the screen)."
- `الفاتورة غير محفوظة يمكن تغيير العميل من اسفل الشاشة` — "An unsaved invoice can have its customer changed from the bottom of the screen."
- `تاكد ان الفاتورة غير محفوظة` — "Make sure the invoice is not saved."

### 2.2 Editing a saved (posted) sales invoice
```
1. Open the invoice (search by invoice number / date / customer / drug).
2. Revert save: press "Un save / الغاء الحفظ" (bottom-left). [Permission-restricted]
   - "لا يمكن الغاء الحفظ الا بواسطة مدير الصيدلية" — only the pharmacy manager can un-save.
3. Modify lines: change quantity, price, discount, add/remove a drug, change customer.
   - On an item change in a large purchase invoice, Titan re-shows the invoice on the SAME edited item, not the last item:
     "عند التعديل في  صنف في   فاتورة مشتريات كبيرة فان تيتان يعرض الفاتورة علي نفس الصنف المعدل وليس اخر صنف في الفاتورة"
4. Re-calculate totals: Subtotal → Discount → VAT → Total (see §5).
5. Re-save (F9). Optionally print + open drawer.
6. The edit is logged for audit (see §2.4 / §3 audit trail).
```

### 2.3 Edit / correction of a posted invoice (money + stock)
```
1. Load the posted invoice.
2. Reverse old stock movement: find the original wzgard row(s) (randomid, drugname, phar, datee) and negate quant / restore oldstock.
3. Reverse old money/journal: negate the corresponding wzmony / wzdaily entries (sales total, VAT, payment cash/visa/credit).
4. Apply new values:
   - Re-insert corrected wzgard row with new quant/costvalue/vatvalue/totalwithvat and updated oldstock.
   - Re-insert corrected wzmony/wzdaily rows.
5. Persist corrected header (invoiceid, payed, disc, agel, totalvalue) in invoicedata / titanksasales.
6. Log to audit trail (TitanUserAction / FormInvoiceTrackEditing).
```

### 2.4 Audit-trail workflow (FormInvoiceTrackEditing — تتبع فواتير المبيعات)
```
1. From reports: "في شاشة التقارير المتعددة تم اضافة امر تتبع  فواتير المبيعات التي طراء عليها تعديل وتغيير بعد انشائها"
   — A report command tracks sales invoices that were edited/changed after being created.
2. Also "فواتير مبيعات تم التعديل عليها بعد يوم من انشائها" — invoices edited more than one day after creation (flagged specially).
3. Rows show: تاريخ التعديل (edit date) | الصنف (item) | التعديل (edit type/value) | سعر البيع (selling price) | خصم الشراء (purchase discount) | قيمة التعديل (edit value) | الفرع (branch).
4. "القائم بالتعديل" — the user who made the edit (editor identity).
5. Filtered per branch via `'  and master =N'` + GUID `a2a100e1-906b-44df-99c2-6e7c6098421e`.
```

---

## 3. Fields / data captured

### 3.1 Invoice header (invoicedata, schema_complete.sql:168)
`invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue` + line columns: `IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price`.

### 3.2 Chain sales header (titanksasales, schema_complete.sql:113)
`id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue`.

### 3.3 Audit trail — TitanUserAction (schema_complete.sql:266)
```
id          INT IDENTITY PK
drugname    NVARCHAR(100)  — drug affected by edit
typevalue   NVARCHAR(100)  — action type (e.g. edit type)
oldvalue    NVARCHAR(100)  — previous value (before)
newvalue    NVARCHAR(100)  — new value (after)
mobile      NVARCHAR(15)   — user/phone (editor)
namee       NVARCHAR(100)  — user name
curbarcode  VARCHAR(15)    — current barcode
curprice    REAL           — current price
units       INT            — units
datee       REAL           — date (VB6 serial)
```
INSERT: `INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)`.

### 3.4 Correction files
- `LastEdited.phy` (or `\Files\DBI\LastEdited.phy`) — persisted last-edited invoice list (FormLastEdited).
- `RasidCorrect.phy` (or `\Files\DBI\RasidCorrect.phy`) — persisted balance correction state (FFFDrugrasidCorrect).
- `ismaster.txt` / `Titan.master` — master/standalone flags that gate edit behavior (only the master machine may apply manual balance edits — see §10).

---

## 4. Side-effects

### 4.1 Stock side-effect (wzgard) — reverse then re-apply
When editing/deleting/correcting a posted invoice, the stock movement recorded in `wzgard` is reversed then re-applied with corrected values. The canonical INSERT (raz §8.2) is:
```sql
INSERT INTO wzgard (phar, randomid, writer, datee, datetimee, classy, quant,
                    expire, price, oldstock, costvalue, vatvalue, totalwithvat, typee, drugname)
VALUES (...)
```
- **Reverse:** for each original line, negate `quant` and restore `oldstock` (the pre-movement stock) so the batch returns to its prior level.
- **Re-apply:** insert a new row with corrected `quant`, `costvalue`, `vatvalue`, `totalwithvat`; `oldstock` = the current stock just before the corrected movement; `typee` marks the movement kind (purchase / sale / return / correction).
- `d.costvalue = g.costvalue, d.expire = g.expire` — a `wzdrugs`-level sync copies cost value and expiry from the stock batch (used after corrections/extensions).
- Deleting an invoice: Raz.@0x00a62be8 (size 916) reverses stock and money and removes the invoice record.

### 4.2 Money side-effect (wzmony / wzdaily)
Reverse and re-apply the money/journal entries when amounts change:
- Reverse the original sales/purchase money rows (negative of total / VAT / payment portions).
- Re-insert corrected `wzmony` / `wzdaily` rows reflecting the new total, discount, VAT, and payment split (cash كاش / visa شبكة / credit آجل).
- Daily cash register is re-computed (FormDailyQuiod / ModDailyQuiod), including "قيمة كل ادوية الصيدلية بسعر الجمهور" (total pharmacy stock at public price).

### 4.3 Customer / supplier balance side-effect
- Editing a credit (آجل) sale changes the customer's مديونية (debt) in `wzcustomers`; manual corrections available (`تصحيح مديونية العميل الحالي`).
- Editing a purchase changes supplier مستحقات (dues) in `companies` / accounting tree `wzaccfreetree`.
- `التعديل اليدوي لارصدة العملاء` — manual customer-balance edits are tracked and reported (`تقرير التعديل اليدوي`).

### 4.4 Balance (رصيد) correction side-effect (FFFDrugrasidCorrect)
- "تصحيح الارصدة بالزيادة" (increase) / "تصحيح الارصدة بالعجز" (deficit) — corrections recorded.
- "اصناف تم تصحيح ارصدتها تلقائيا" — items auto-corrected.
- Manual edits to balances are **gated to the master machine only**: `التعديلات علي النواقص من الجهاز الرئيسي فقط`.
- Any user may **request** a balance edit; the manager accepts or rejects: `اصبح من المتاح ان يقوم اي مستخدم بتقديم طلب تعديل الرصيد ويمكن للمدير قبول الطلب او رفضه`; `بعد ان تم تقديم الطلب حدث تعديل علي الرصيد لا يمكن قبول الطلب`.

---

## 5. Pricing + VAT

### 5.1 Sales calculation (business_logic §16.4)
```
Subtotal = Sum(Quantity × Unit Price)
Discount = Subtotal × (SellDisc / 100)
VAT      = (Subtotal − Discount) × (VAT% / 100)
Total    = Subtotal − Discount + VAT
```
### 5.2 Purchase calculation (business_logic §17.4)
`Buy Discount` (خصم الشراء), `BuySum` (اجمالي الشراء), `Discadd` (خصم اضافي), `Recalculate DiscADD In Purchases`.

### 5.3 VAT correction
- Editing can manually correct VAT totals: `امكانية تعديل قيمة اجمالي ضريبة القيمة المضافة يدويا في المشتريات` (purchases) — manual VAT total edit.
- Per-item VAT: `تعديل قيمة ضريبة القيمة المضافة لهذا الصنف` (edit the VAT value of this item).
- VAT mode toggle: `تعديل نظام احتساب ضريبة القيمة المضافة في فاتورة المشتريات` / `تعديل طريقة حساب ضريبة القيمة المضافة في فاتورة المشتريات`.
- Purchases edited by value are flagged in reports: `فواتير مشتريات تم تعديل قيمتها يدويا`.

### 5.4 Pricing correction
- Selling price editable on edit (`تعديل بيانات هذا الدواء`, `تعديل السعر والباركود عند الحاجة`).
- Copy corrected price to item card: `Copy the price as it is to the item card`, `Copy the high price to the item card`, `Copy the VAT as it is to the item cards`.
- Discount (FormDiscCorrect): correct the discount applied; permission required — `هذا الموظف لا يملك عمل خصومات  ويمكن للمدير ان يمنحه هذه الصلاحية` (no-discount permission message).

---

## 6. Payment methods

Editing recalculates the payment split (cash كاش / visa شبكة / credit آجل). Daily cash-register correction allows adjusting manual (cash / network) sales values for a selected day:
- `ادخل تصحيح   قيمة المبيعات اليدوية - كاش - لليوم المختار` — enter manual cash-sales correction for the day.
- `ادخل تصحيح   قيمة المبيعات اليدوية - شبكة - لليوم المختار` — enter manual network(visa)-sales correction for the day.
- Credit (آجل) sales require the `بيع الاجل` permission: `لا تملك صلاحية البيع الاجل يمكن الحصول علي هذه الصلاحية ... تعديل اعدادات العاملين`.

---

## 7. Printing

- `FormPrintSales` — sales receipt printing; re-print an edited invoice (`Print the invoice once it is saved`).
- `FormOutPuttakarirSpeed` — output corrected receipt/correction statement (كشف تصحيح) after an edit/correction.
- `FormPrint` / `FormPrintPreview` — generic print routing and preview.
- Barcode label printing for an edited item: `امكانية طباعة  باركود لصنف ما من شاشة تعديل بيانات الادوية قائمة ادوات`.

---

## 8. Tables

| Table | Role in editing |
|---|---|
| **invoicedata** (schema:168) | Invoice header + line items; the rows that get modified on edit (invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue + Quant, DrugName, SellDisc, Expire, price). |
| **titanksasales** (schema:113) | Chain-sales invoice header (KSA). Updated on edit. |
| **titanksastock** / **titanstock** (schema:128/142) | Per-branch / per-drug stock levels; `titanstock.lastedit` timestamp records last stock edit. |
| **wzgard** (schema:58) | Stock movement / correction journal — reverse + re-apply rows (`phar, randomid, writer, datee, datetimee, classy, quant, expire, price, oldstock, costvalue, vatvalue, totalwithvat, typee, drugname`). |
| **TitanUserAction** (schema:266) | Audit log — `drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee`. |
| **wzmony** / **wzdaily** | Money/journal — reversed and re-applied on money-affecting edits. |
| **wzcustomers** (schema:79) | Customer balance — updated for credit-sale edits / manual corrections. |
| **companies** (schema:92) | Supplier dues — updated for purchase-edit corrections. |
| **storediscount** (schema:215) | Discount records (discount correction audit: `drugname, barcode, price, disco, units, ...`). |
| **wzaccfreetree** | Accounting tree — updated on money-affecting edits. |
| `LastEdited.phy` / `RasidCorrect.phy` / `ismaster.txt` | Local persisted state (not SQL) for last-edited list, balance-correction state, master flag. |

---

## 9. UI strings (Arabic)

**Invoice states / edit entry:**
- `الفاتورة المحفوظة لا تملك التعديل فيها الا اذا الغيت حفظها وذلك من اسفل يسار الشاشة` — saved invoice editable only after un-saving (bottom-left).
- `الفاتورة غير محفوظة يمكن تغيير العميل من اسفل الشاشة` — unsaved invoice: customer changeable.
- `تاكد ان الفاتورة غير محفوظة` — make sure invoice is not saved.
- `حفظ-الغاء الحفظ` / `حفظ/الغاء الحفظ` — save / un-save toggle button.
- `Un save` / `Un saved` / `unsaved` — un-save states.
- `لا يمكن الغاء الحفظ الا بواسطة مدير الصيدلية` — only manager may un-save.

**Edit actions / screen names:**
- `تعديل` (edit) · `تعديل الارصدة` (edit balances) · `تعديل الارصدة والجرد` · `تعديل رصيد الاصناف` · `تعديل رصيد هذا الدواء مباشرة`
- `تعديل تاريخ الفاتورة` (edit invoice date) · `تعديل بيانات الادوية` (edit drug data) · `تعديل اعدادات العاملين/العملاء/الموردين`
- `تعديل قيمة ضريبة القيمة المضافة لهذا الصنف` (edit item VAT) · `تعديل نظام احتساب ضريبة القيمة المضافة`
- `تغيير العميل لفاتورة محفوظة` (change customer for a saved invoice)
- `تحويل الي مشتريات` / `تحويل الي طلبية محولة` / `تحويل الي مرتجع مشتريات` / `تحويل الي صيدلية اخري` / `تحويل نوع الفاتورة` / `تم تحويل الفاتورة`
- `انشاء نسخة فارغة تماما من كل البيانات` (make an empty copy) · `تم النقل الي قائمة التحويل`

**Correction / balance:**
- `تصحيح الارصدة بالزيادة` / `تصحيح الارصدة بالعجز` / `تصحيح رصيد يدويا` / `تصحيح مديونية العميل الحالي` / `تصحيح تاريخ تيتان`
- `تعديل الرصيد` (balance edit) · `طلب تعديل الرصيد` / `قبول الطلب` / `رفض الطلب` · `فشلت عمليت تعديل الرصيد`
- `اصناف تم تصحيح ارصدتها تلقائيا` · `التعديلات علي النواقص من الجهاز الرئيسي فقط`
- `ادخل تصحيح قيمة المبيعات اليدوية - كاش - لليوم المختار` / `- شبكة -` (daily manual-sales corrections)

**Audit trail (FormInvoiceTrackEditing):**
- `تتبع  فواتير المبيعات التي طراء عليها تعديل وتغيير بعد انشائها` — track sales invoices edited after creation.
- `فواتير مبيعات تم التعديل عليها بعد يوم من انشائها` — invoices edited more than a day after creation.
- Report header: `تاريخ التعديل    الصنف    التعديل     سعر البيع     خصم الشراء     قيمة التعديل      الفرع` (edit date | item | edit | selling price | purchase discount | edit value | branch).
- `القائم بالتعديل` — the editor (who made the change). · `المستخدم الحالي` — current user.
- `تاريخ اخر تعديل` / `تاريخ التعديل` (last-edit date). · `اخر تعديل لهذه الفاتورة كان بتاريخ` (this invoice was last edited on …).
- `التاريخ     المبيعات بعد التعديل  المبيعات قبل التعديل    الفارق` (date | sales after edit | sales before edit | difference) — sales-comparison report.
- `مسلسل    تاريخ      القيمة المحسوبة    القيمة اليدوية     الفارق  اسم المورد` (serial | date | calculated value | manual value | difference | supplier) — purchase manual-value audit.

**Errors / guardrails:**
- `مر علي هذه الفاتورة اكثر من 1000 فاتورة اخري  ولم يعد بامكانك التعديل عليها` — invoice is more than 1000 invoices back; no longer editable.
- `هذه الفاتورة قديمة ولم يعد بامكانك التعديل عليها` — this invoice is old; no longer editable.
- `لا يمكن تعديل اسم الكاتب لفواتير سابقة` — cannot change the writer name of earlier invoices.
- `المدير فقط يمكنه تعديل مدخلات الايام السابقة` — only the manager can edit previous days' entries.
- `لا تملك صلاحية تنفيذ هذا الامر ... اطلب من مدير الصيدلية منحك هذه الصلاحية` / `غير مسموح لك-للمدير منحك هذه الصلاحية من شاشة تعديل اعدادات العاملين`
- `هذا الموظف لا يملك صلاحية تعديل رصيد الاصناف ...` / `هذا الموظف لا يملك عمل خصومات ...`
- `لقد تم ايقاف ميزة تعديل التاريخ نهائيا اتصل بخدمة العملاء` — the date-edit feature is permanently disabled (contact support).

---

## 10. Business rules / edge cases

1. **Only saved invoices are editable, and only after un-saving** — `Un save` (الغاء الحفظ) is required; un-save is **manager-only** (`لا يمكن الغاء الحفظ الا بواسطة مدير الصيدلية`).
2. **Age limits on editing:**
   - More than **1000 invoices** since this one → no longer editable.
   - Old invoices (`هذه الفاتورة قديمة`) → not editable.
   - Editing **previous days'** entries is **manager-only**.
   - Date-edit feature may be **permanently disabled** (locked by support) → date edit blocked.
3. **Writer (كاتب) of earlier invoices is immutable** — `لا يمكن تعديل اسم الكاتب لفواتير سابقة`.
4. **Reverse-then-reapply is atomic for stock and money:** each edited posted invoice must negate the original `wzgard` / `wzmony` / `wzdaily` rows and insert corrected ones with correct `oldstock`/`costvalue`/`vatvalue`/`totalwithvat`/`typee`. Deletion (Raz.@0x00a62be8) reverses both stock and money.
5. **Permission flags (permissions_complete.md):** Sales → can edit/override prices, can apply discounts, can void; Purchase → can edit purchase prices; Inventory → can edit stock; manager assigns via `تعديل اعدادات العاملين`. Dedicated messages when the user lacks balance-edit or discount permission.
6. **Balance (رصيد) corrections:** manual balance edits apply **only from the master machine**; any user may *request* a correction, but the **manager must accept/reject**; a re-edit after the request invalidates the pending request (`بعد ان تم تقديم الطلب حدث تعديل علي الرصيد لا يمكن قبول الطلب`). Auto-correction may be toggled (`ايقاف عملية تصحيح صلاحيات الاصناف تلقائيا عند استشعار خلل`).
7. **Editing a large purchase invoice** re-positions the view on the edited item (not the last item).
8. **Purchase VAT can be edited manually** on the invoice total and per item; such purchases are flagged in reports (`فواتير مشتريات تم تعديل قيمتها يدويا`).
9. **Every edit is audited:** logged to `TitanUserAction` (old/new values, editor mobile+name, barcode, price, units, date) and visible via `FormInvoiceTrackEditing` report (edit date, item, type, prices, value, branch, editor). Edits made **more than one day after creation** are specially flagged.
10. **Re-print after edit** is available; corrected receipts output via `FormOutPuttakarirSpeed`; barcode re-print from drug-data edit screen.

---

*Compiled from TITAN.W1 / Phye.exe p-code disassembly, string tables, and existing extraction docs (business_logic_complete.md §16–17, schema_complete.sql, permissions_complete.md, raz_complete.md).*
