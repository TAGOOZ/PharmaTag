# مرتجع بيع — Sales Returns ("oot" return)

**Purpose:** Full extraction of the sales-return (مرتجع بيع / مرتجع مبيعات) feature of TITAN.W1 (Phye.exe). A sales return reverses a previously-saved sales invoice: stock is restored to `wzgard`, the customer's balance is restored/reversed in `wzcustomers`, money is reversed in the daily files, the chain sales record is mirrored in `titanksasales`, and per-line reverse entries land in `invoicedata`. Includes the return workflow (from a saved invoice or a new return), expiry returns (مرتجع اكسبير), paid-return (مرتجع مدفوع), conversion codes (600 vs 800), the tax-return invoice (`فاتورة ضريبية - مرتجع`), and all Arabic UI strings.

Source: `titan_decompile/` (strings_utf16.txt, strings_readable.txt, pcode_disasm.txt), reused from `business_logic_complete.md` (§6.3, §16), `schema_complete.sql`, `reports_complete.md`, `ui_complete.md`, `raz_complete.md`.

---

## 1. Objects

Same object family as the sales-invoice feature (the return runs on the same sales screens / "oot" forms), so:

| Object | Type | Procs | Role in returns |
|---|---|---|---|
| **ModOot** | Module | 105 | Core sales/outbound engine — includes **Sales Return Logic** (§6.3): return references original invoice, return qty cannot exceed original, return creates reverse entry, "Sales returnes" tracking. |
| **FFFStartUp** | Form | 252 | Hosts the `titanksasales` reverse-insert (GUID `a2a100e1-...` idx 7423) used when recording return invoices; contains conversion-code prompt (idx 9092). |
| **FFFOUTPut** | MDIForm | 278 | Output MDI parent where the تحويل الفاتورة الي مرتجع مبيعات command lives. |
| **FormSellTime** | Form | 9 | Sales timing (وقت البيع). |
| **FormPrintSales** | Form | 17 | Prints return invoices (فاتورة ضريبية - مرتجع). |
| **FormReadArcOot** | Form | 9 | Read archived sales (returns may reference archived invoices). |
| **FFFOOTQuant** | Form | 20 | Qty/expiry selection for return lines. |
| **FormInvoiceTrackEditing** | Form | 4 | Tracks edits including conversions/returns. |
| **FormootThisDay / FormOotSum** | Form | 11 / 9 | Today's output / output summary including returns (اجمالي مرتجع المبيعات). |
| **ModOOTTrans** | Module | 1 | Empty stub. |
| **ModOuterConnections / Modfarynet / FormFaryNet** | — | 18/2/8 | Network sync of returns across branches. |

---

## 2. Step-by-step workflow

A sales return is created by one of two routes:

### 2.1 Route A — Convert a saved sales invoice to a return
1. Open the (saved) sales invoice.
2. From the **تحرير (Edit)** menu choose **تحويل الفاتورة الي مرتجع مبيعات** (idx 12929: `من شريط قوائم الشاشة اختر قائمة تحرير ثم امر تحويل الفاتورة الي مرتجع مبيعات`).
3. The system prompts with the conversion code (idx 9092): **`ادخل 800 لتحويل الفاتورة الي مبيعات ... او 600 لتحويلها الي مرتجع مبيعات`** — **600 = sales return**, 800 = sales.
4. Enter the original invoice number to return from (idx 9196: `ادخل رقم الفاتورة التي تم الارتجاع منها`).
5. Validate that the original invoice exists (idx 10149: `الفاتورة التي تحاول الارجاع منها غير موجودة علي السيرفر`).
6. Confirm which lines / quantities to return (return quantity ≤ original quantity).
7. Save; the system reverses the sales: stock, customer balance, money, chain record, and per-line records.

### 2.2 Route B — New return invoice (empty return)
1. From قائمة ملف choose **فاتورة مرتجع حديدة** (new return invoice) — idx 9319 (purchase context analog: `من قائمة ملف اختر فاتورة مرتجع حديدة`).
2. Add the drugs to return (idx 9658: `اضف اليها الادوية التي تود ارتجاعها`).
3. Enter original invoice # (idx 9196); validate existence (10149).
4. Save to reverse the sale.

### 2.3 Expiry return (مرتجع اكسبير)
- Return of expired/expiring drugs: `مرتجع اكسبير` (12743), `فواتير مرتجع اكسبير` (12116). The expiry-return is a distinct type (`النوع:مرتجع مبيعات` 10389 vs the expirer variant). When a drug is expired, use the up/down arrows to mark whether it is returnable (idx 9405: `استخدم اتجاهات لوحة المفاتيح لتحديد اذا كان هذا الدواء قابل للارتجاع عند كونه منتهي الصلاحية`).
- `أدوية منتهية الصلاحية` (8898) and expiry control apply.

---

## 3. Fields / data captured

Return invoices reuse the sales structure with reversed signs:

- `invoiceid` — the (new) return invoice number; `datee` — return date; `pharmacyid`, `silsilaid`.
- `payed` — reversed paid amount; `agel` — reversed deferred portion; `disc` — reversed discount; `totalvalue` — reversed grand total.
- Per line: `Quant` (return qty ≤ original), `DrugName`, `SellDisc`, `Tips`, `Expire`, `price`, `IdDateTime`.
- Source original invoice # (من الفاتورة / رقم الفاتورة التي تم الارتجاع منها idx 9196).
- Return type field: `النوع:مرتجع مبيعات` (10389), `مرتجع اكسبير` (12743), `مرتجع مدفوع` (12745 — a paid/refunded return).

---

## 4. Side-effects (reverse of sales)

On saving a sales return:

- **Stock (`wzgard`)** — restored: a new `wzgard` batch row with `quant` = returned quantity (positive) and `typee` = `return`/`مرتجع مبيعات`; `oldstock` records prior stock. This reverses the decrement made at sale time. Expiry returns reverse expired batches specifically.
- **Customer balance (`wzcustomers`)** — restored/reversed: credit (أجل) returns reduce the customer's debt; the balance re-computed automatically (تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات idx 10712).
- **Money / daily files** — reversed: cash returns remove cash from the drawer (خروج نقدية نتيجة ارتجاع ادوية في المبيعات idx 11421; نقدية خرجت عن طريق شاشة المبيعات في شكل مرتجع ادوية او خروج نقدية لعميل باي شكل idx 13032). Return amounts factor into the daily drawer equation: drawer = cash sales − cash returns + customer settlements (idx 12675, 8956). Daily totals include `اجمالي مرتجع المبيعات` (8991). Money stored in `.phy` files (Daily.phy, Dailymax.phy, MonyInfo.phy).
- **Chain record (`titanksasales`)** — a mirror/reverse row via the same GUID insert loop (GUID idx 7423), with `totalvalue`/`payed`/`agel` reversed and type reflecting `مرتجع مبيعات`.
- **Per-line data (`invoicedata`)** — reverse lines recorded.
- **ZATCA (`ZATCA`)** — a tax return invoice (`فاتورة ضريبية - مرتجع` idx 12045) may be logged.
- **User action audit (`TitanUserAction`)** — records the return modification.

---

## 5. Pricing + VAT

Returns use the same pricing/VAT model as sales but in reverse:

```
Returned Subtotal = Σ (Return Qty × Original Unit Price)
Discount  = Subtotal × (SellDisc / 100)
VAT       = (Subtotal − Discount) × (VAT% / 100)   [reversed]
Total     = Subtotal − Discount + VAT                [reversed / refunded]
```

- Return line values are taken from the **original** invoice (price and discount at sale time).
- VAT reversed on the return so the tax invoice nets correctly; label `فاتورة ضريبية - مرتجع` (12045).
- Discount is reversed too; a refund reflects net of discount + VAT.

---

## 6. Payment / refund methods

- **مرتجع مدفوع** (12745) — a *paid* return, i.e. the customer is refunded cash/visa. Cash refunds exit the drawer (خروج نقدية نتيجة ارتجاع ادوية في المبيعات idx 11421; نقدية خرجت عن طريق شاشة المبيعات ... idx 13032).
- **Credit return** — for an original أجل sale, the return reduces the customer's outstanding `agel` rather than refunding cash.
- Payment/refund split across cash (كاش) and visa/network (فيزا / شبكة), mirroring the original payment split (`payed` / `agel`).
- Consistency check applies as for sales: `يجب ان يكون مجموع الاجل والمدفوع مساويا لسعر الفاتورة` (13344) — including the return.

---

## 7. Printing

- **Form:** FormPrintSales — prints the return invoice.
- Template variant: **`فاتورة ضريبية - مرتجع`** (idx 12045) — the tax return invoice layout (A4/A5, reports_complete §3.1).
- Other relevant variants: `فاتورة محولة` (12049), `فاتورة ضريبية` (12044), `فاتورة ضريبية اجلة` (12046), `فاتورة ضريبية مبسطة` (12047).
- Receipt layouts: cash receipt سند قبض and disbursement سند صرف (reports_complete §3.2/3.3) for refunds.
- Cannot print an unsaved return (لا يمكن طباعة فاتورة غير محفوظة idx 12416).
- Auto-print on save config (طباعة الفاتورة تلقائيا مع الحفظ 11743).

---

## 8. Tables

Identical table set to sales invoices (see `feature_sales_invoices.md` §8 for full DDL). Return-specific notes:

```sql
-- Chain sales master — return = reversed row via GUID insert:
titanksasales ( invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue )

-- Per-line reverse data:
invoicedata ( invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue,
              IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price )

-- Stock restored (return batch):
wzgard ( phar, randomid, writer, datee, datetimee, classy, quant, expire, price,
         oldstock, costvalue, vatvalue, totalwithvat, typee, drugname )
--   insert template: insert into wzgard (phar,randomid,writer,datee,datetimee,classy,quant,expire,price,oldstock,costvalue,vatvalue,totalwithvat,typee,drugname) values ( ... )
--   typee = 'return' / 'مرتجع مبيعات' / 'مرتجع اكسبير'

-- Customer balance restored:
wzcustomers ( randomid, phar, typee, writer, creditlimit, datee, namee )

-- Tax return log:
ZATCA ( invoiceid, uuid, datee, pharmacyid, status, hash, xml, response )

-- Transfer of a return across branches:
titanin ( fatid, itemsasstring, datee, source, silsilaid, target )
```

Live templates (strings_readable): `insert into titanksasales (` (719), `invoiceid,datee,...` (idx 8019), `insert into wzgard (...)` (7600), `insert into titaninn (...)` (718), `select * from farysales where mobile = N'` (764).

---

## 9. UI strings (Arabic)

- `ادخل 800 لتحويل الفاتورة الي مبيعات ... او 600 لتحويلها الي مرتجع مبيعات` (9092) — **600 = sales return, 800 = sales**
- `تحويل الفاتورة الي مرتجع مبيعات` (12929) — Edit-menu command
- `نسخ الفاتورة الي فاتورة ارتجاع بيع` (13006) — copy to return invoice
- `الي مرتجع مبيعات` (10423)
- `النوع:مرتجع مبيعات` (10389) · `النوع:مبيعات` (10388)
- `فاتورة ضريبية -  مرتجع` (12045)
- `مرتجع` (12742) · `مرتجع مبيعات` (12744) · `مرتجع اكسبير` (12743) · `مرتجع مدفوع` (12745) · `مرتجع مشتريات` (12746)
- `فواتير مرتجع اكسبير` (12116) · `فواتير مرتجع المبيعات` (12117)
- `ادخل رقم الفاتورة التي تم الارتجاع منها` (9196)
- `الفاتورة التي تحاول الارجاع منها غير موجودة علي السيرفر` (10149)
- `اجمالي مرتجع المبيعات` (8991)
- `خروج نقدية نتيجة ارتجاع ادوية في المبيعات` (11421)
- `نقدية خرجت عن طريق شاشة المبيعات في شكل مرتجع ادوية او خروج نقدية لعميل باي شكل` (13032)
- `اضف اليها الادوية التي تود ارتجاعها` (9658)
- `استخدم اتجاهات لوحة المفاتيح لتحديد اذا كان هذا الدواء قابل للارتجاع عند كونه منتهي الصلاحية` (9405)
- `ادوية قابلة للارتجاع` (9300) · `الارتجاع` (9752) · `أدوية منتهية الصلاحية` (8898)
- `تقرير ادوية مرتجعة` (10980) — returned-drugs report
- `من قائمة ملف اختر فاتورة مرتجع حديدة` (9319) — new return invoice (purchase analog)

---

## 10. Business rules / edge cases

1. **Return qty ≤ original qty** — a sales return cannot exceed the original invoice quantity (§6.3).
2. **Original must exist** — `الفاتورة التي تحاول الارجاع منها غير موجودة علي السيرفر` (10149); if on server vs local distinction applies.
3. **Reference original invoice** — return stores the source invoice number (9196).
4. **Conversion codes** — 600 = sales return, 800 = sales (9092). The same prompt/mechanism converts between invoice types.
5. **Only returnable/saved invoices** — cannot return an unsaved invoice; returns build from saved invoices only (لا يمكن طباعة فاتورة غير محفوظة 12416; invoice must be saved to convert 9011).
6. **Expiry returns** — expired drugs are returnable only when flagged (9405); expiry returns are a separate type (مرتجع اكسبير 12743 / فواتير مرتجع اكسبير 12116).
7. **Paid vs credit return** — مرتجع مدفوع (12745) refunds cash/visa; credit returns reduce customer `agel` instead.
8. **Full reversal** — a return reverses stock (wzgard), customer balance (wzcustomers), money/drawer (daily files), chain record (titanksasales), per-line data (invoicedata).
9. **Drawer accounting** — cash returns are subtracted from the drawer: drawer = cash sales − cash returns + customer settlements (12675, 8956).
10. **Reports** — returns appear in: اجمالي مرتجع المبيعات (8991), تقرير ادوية مرتجعة (10980), فواتير مرتجع المبيعات (12117).
11. **Post-day-close** — after day close, unsave is disabled; only copy to a return/purchase invoice is possible (idx 13407).
12. **Cross-branch** — returns can be transferred to another pharmacy (تحويل الفاتورة الي صيدلية اخري 10770 / titaninn transfer).
