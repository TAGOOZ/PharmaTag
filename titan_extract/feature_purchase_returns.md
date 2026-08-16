# TITAN.W1 — Feature: مرتجع مشتريات (Purchase Returns)

**App:** TITAN.W1 (Phye.exe, VB6 p-code)
**Arabic name:** مرتجع مشتريات (Purchase Return) — also **مرتجع الاكسبير** (Expired-items Return) as a second purchase-return variant.
**Purpose:** Reverse all effects of a purchase invoice: remove returned quantity from stock, reduce the supplier's payable (مستحقات المورد / دائن), and reverse the purchase cost/VAT. Returns are the mirror of purchase invoices and behave like purchase invoices with inverted stock/payable signs.
**Sources reused:** `feature_purchases.md`, `schema_complete.sql`, `schema_complete.md`, `business_logic_complete.md`, `raz_complete.md`, `reports_complete.md`, `strings_utf16.txt`, `strings_readable.txt`.

---

## 1. Objects (Modules / Forms / Procedures)

### 1.1 Modules
| Module | Role |
|--------|------|
| `ModInn.bas` | Purchase/inbound module — contains purchase-return processing proc `@0x00949e78` ("Purchase return processing"). |
| `ModStock.cls` | **Reverses stock**: subtracts returned quantity from `wzgard` / `titanksastock`. |
| `ModMony` / `ModOot` | Reverses payment/payable: purchase return reduces supplier payable; cash refund (مردود نقدي) if supplier refunds. |
| `ModPrint.bas` | Prints the return report (تقرير ارتجاع) / return invoice. |

### 1.2 Forms
| Form | Arabic | Role |
|------|--------|------|
| `FFFINPut` | المشتريات | Same MDI purchase screen hosts return invoices; File → *فاتورة مرتجع جديدة*. |
| `FFFWaredMonsaref` | المونسرف | Supplier/warehouse settings (return-eligible suppliers, معدوم supplier for expired items). |
| `FormReadArcInn` | قراءة المشتريات المؤرشفة | Read archived returns. |
| `FFFInputTakarir` | تقارير المشتريات | "تقرير ادوية مرتجعة" (returned-drugs report), "تقرير اكسبير" (expiry report). |
| `FormPrintSales` | الطباعة | Print engine for return invoice / return report. |

### 1.3 Key procedures
- `@0x00949e78` — **Purchase return processing** (Raz.bas / ModInn) — main reversal logic. (`raz_complete.md` §3.2)
- `@0x0095a100` — Purchase stock update (used in reverse for returns).
- `@0x00938fd4` — Purchase VAT calculation (reversed for return VAT).
- `@0x0093d948` — Purchase payment processing (reversed/refunded for returns).
- `@0x0096d944` — Purchase reports (returns reported here).
- Related sales-return reversal procs (mirror): `@0x00949e78`-style logic on the "oot" side.

---

## 2. Step-by-step workflow

1. **Open a purchase-return invoice** — on the purchase screen (`FFFINPut`), File menu → *فاتورة مرتجع جديدة* (new return invoice). Alternatively **convert** the current saved invoice: قائمة تحرير → نسخ → فاتورة مرتجع مشتريات ("يمكنك الغاء حفظ اي فاتورة ... الا اذا قمت بتقفيل اليوم فلا تملك الا نسخها الي فاتورة مرتجع مشتريات").
2. **Select supplier (المورد)** — the supplier being returned to; supplier's dues (مستحقات المورد) will be reduced.
3. **Add drugs to return** — the invoice references items to be returned ("اضف اليها الادوية التي تود ارتجاعها"); user may type the original purchase invoice number ("اكتب رقم فاتورة المشتريات التي تود اضافة الادوية المختارة اليها"; "ادخل رقم الفاتورة التي تم الارتجاع منها"). Return quantity must not exceed the purchased quantity.
4. **Set return cost/price, discount, VAT** — return uses the purchase cost; VAT may be reversed (the returned items are no longer taxable-in).
5. **Payment/refund** — the return reduces the payable; if the supplier refunds cash it is recorded as **مردود نقدي / دخول نقدية** (cash in).
6. **Save (F9)** — validates and **subtracts** quantity from stock and **debits** the supplier payable (reduces مستحقات المورد).
7. **Print** the return report/invoice (طباعة تقرير ارتجاع).

### Return types (three purchase-invoice states — `arabic_purchase_strings.txt:13445`)
- **مشتريات** (purchase) — normal inbound.
- **مرتجع مشتريات** (purchase return) — goods returned to supplier.
- **مرتجع الاكسبير** (expired-items return) — expired/date-expired (اكسبير) goods returned, using a dedicated **معدوم** (dead/expired) supplier.

### Expired-items return (مرتجع الاكسبير)
- **الكشف عن الاكسبير** — detect near/expired items for return.
- **يستخدم هذا المورد لاخراج الادوية المعدومة ومنتهية الصلاحية من الرصيد** — the "معدوم" (expired) supplier is used to remove expired/dead drugs from stock; their value can be counted from purchase reports.
- **ادوية معدومة** (dead drugs) / **ادوية قابلة للارتجاع** (returnable drugs) — classify items as returnable when expired using arrow keys ("استخدم اتجاهات لوحة المفاتيح لتحديد اذا كان هذا الدواء قابل للارتجاع عند كونه منتهي الصلاحية").

---

## 3. Fields / data captured

Same invoice structure as purchases (`invoicedata` header + line items), with the return type encoded:
- `invoicedata`: `invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue` (+ line: `IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price`).
- Line items carry **negative/normal return quantity** (Quant = returned qty), the **original purchase price** (cost), buy discount, expiry of the returned batch.
- `agel` / `typee` distinguishes return from purchase (invoice state: مرتجع مشتريات / مرتجع الاكسبير).
- Reference to the **original purchase invoice** (رقم الفاتورة التي تم الارتجاع منها).
- Supplier, payment/refund (مردود نقدي / مدفوع), treasury source.
- Fields on return screens: النوع (type), تاريخ (date), الصنف (item), الكمية (qty), القيمة (value), سعر الشراء (purchase price), الخصم (discount), الضريبة (VAT).

### wzgard return columns
Each returned batch writes a `wzgard` row with `typee` = return/out direction and **negative `quant`**, preserving `costvalue`, `vatvalue`, `totalwithvat` (reversed) for correct stock valuation.

---

## 4. Side-effects

### 4.1 Stock — REVERSED (subtract)
- Purchases ADD stock; **purchase returns SUBTRACT** stock.
- `wzgard` gets a batch row with return direction (`typee` = out), negative `quant`, and the cost value so that removing it reduces valued stock correctly.
- The drug-card `titanksastock`/`titanstock` `stock` field is **decremented** by the returned quantity.
- **Returned quantity cannot exceed available/purchased quantity** — stock must be sufficient (mirror of the sales "Not Enouph Stock" guard on the out side).
- Expired-items return (مرتجع الاكسبير) removes dead/expired stock entirely via the معدوم supplier; the returned value is reported in purchase reports.

### 4.2 Supplier payable — REVERSED (debit / reduce)
- A purchase **credits** (دائن) the supplier; a **purchase return debits** (مدين) the supplier, **reducing مستحقات المورد / مستحقات الشركات** (supplier dues / payable).
- Accounting entries via `farysales` (creditdebit = 'debit' for the return) against `خصوم.خصوم متداولة.موردين` (Liabilities → Suppliers).
- Cash refund from supplier = **دخول نقدية نتيجة ارتجاع الدفع من الشركات** (cash in from refunded supplier payment) — recorded as incoming cash (مردود نقدي).

### 4.3 Money / cash
- If the original purchase was paid in cash and the supplier refunds, cash **returns to the drawer/treasury**: "دخول نقدية نتيجة ارتجاع الدفع من الشركات".
- Refund recorded as مردود نقدي (cash refund) / مرتجع مدفوع (returned-payment).
- Mirrors the sales-return cash-in flow: "خروج نقدية نتيجة ارتجاع ادوية في المبيعات" (the purchase side is the cash-in counterpart).

### 4.4 Other side-effects
- **VAT reversal**: returned items are no longer counted as taxable purchases; purchase VAT report (ضريبة المشتريات) is reduced accordingly.
- `storediscount` purchase-discount history is reduced/removed for returned items.
- Drug cost basis (wzdrugs2.unitcost from wzgard) is recomputed after the return (cost of remaining stock reflects the reversal).
- E-invoice/DTTS: purchase returns may generate return transactions (return services supported in DTTS/ZATCA flows — `ReturnServiceRequest`).
- Audit logging to `TitanUserAction`.

---

## 5. Pricing + VAT

- **Return price = original purchase cost** (سعر الشراء). The value returned equals the purchase cost of the returned units (with its buy discount).
- **VAT is reversed**: returned taxable items have their VAT removed from the purchase VAT total ("الضريبة في المشتريات" is reduced). A return may be issued as a **فاتورة ضريبية - مرتجع** (tax return invoice) for VAT reconciliation.
- `wzgard` return batch stores `costvalue`, `vatvalue`, `totalwithvat` as the reversed amounts so the stock value and VAT balances stay correct.
- Validation mirrors purchases: real vs calculated purchase price consistency applies to returns too.
- VAT exemption list (الموردين المستثنيين) applies symmetrically on returns.

---

## 6. Payment methods

| Method | Arabic | Handling on return |
|--------|--------|--------------------|
| Supplier refund | مردود نقدي / مرتجع مدفوع | Cash returned to drawer/treasury (دخول نقدية). |
| Reduce payable | تخفيض مستحقات المورد | If not refunded in cash, the return simply **reduces** the supplier's payable (أجل / مستحقات). |
| Returned payment | مرتجع مدفوع | Payment previously made is reversed. |
| Network/visa refund | — | Refund via network possible, mirrors sales-return visa handling. |

The purchase-return default behavior is to **reduce the supplier payable** (أجل) rather than receive cash, unless a cash refund (مردود نقدي) is explicitly recorded.

---

## 7. Printing

- **طباعة تقرير ارتجاع** — print the return report.
- Return invoice printed via the shared print engine (`ModPrint`, `FormPrintSales` host) in purchase-invoice form.
- Returned-drugs report: **تقرير ادوية مرتجعة** (RPT in `reports_complete.md` — "Returned drugs report").
- Expiry report: **تقرير اكسبير** — lists expired items (typically for return/disposal).
- Only saved invoices can be printed (shared rule).

---

## 8. Tables

Same tables as purchases, used in reverse:
- `invoicedata` — return invoice header + lines (type in `agel`; negative-effect lines).
- `wzgard` — **return batch row with negative `quant`, `typee` = return/out**, cost/vat/total reversed.
- `titanksastock` / `titanstock` — drug-card `stock` **decremented**.
- `wzcustomers` — supplier account; `creditlimit` enforced; payable reduced.
- `companies` — supplier master (including special معدوم/expired supplier).
- `farysales` — **debit** (creditdebit='debit') accounting entry for the return; cash-in entry on refund.
- `storediscount` — return removes/updates purchase-discount history.
- `wzdrugs` / `wzdrugs2` — cost basis recomputed.
- `titaninn` — (chain transfer returns can post reversed transfers).
- `TitanUserAction` — audit.

Schema for all above: see `feature_purchases.md` §8 and `schema_complete.sql`.

---

## 9. UI strings (Arabic)

- مرتجع مشتريات (Purchase return) — invoice type
- مرتجع الاكسبير (Expired-items return) — invoice type
- فواتير مرتجع اكسبير (Expired-return invoices) / فواتير مرتجع المبيعات (Sales-return invoices)
- انواع فواتير المشتريات (Purchase invoice types) — مشتريات / مرتجع مشتريات / مرتجع الاكسبير
- كفاتورة مرتجع مشتريات (As a new purchase-return invoice)
- تحويل الي مرتجع مشتريات (Transfer to purchase return)
- اذا اردت ان تفتح فاتورة مرتجع مشتريات او اكسبيرات فمن شريط القوائم ... ملف اختر فاتورة مرتجع جديدة
- اضف اليها الادوية التي تود ارتجاعها (Add the drugs you want to return)
- ادخل رقم الفاتورة التي تم الارتجاع منها (Enter the invoice number from which the return is made)
- اكتب رقم فاتورة المشتريات التي تود اضافة الادوية المختارة اليها (Enter the purchase invoice to add selected drugs to)
- يمكنك الغاء حفظ اي فاتورة ... الا اذا قمت بتقفيل اليوم فلا تملك الا نسخها الي فاتورة مرتجع مشتريات
- ادوية قابلة للارتجاع (Returnable drugs) / ادوية معدومة (Dead/expired drugs)
- الكشف عن الاكسبير (Detect expired items) / تطوير الية الكشف عن الادوية الاكسبير او وشيكة الاكسبير
- يستخدم هذا المورد لاخراج الادوية المعدومة ومنتهية الصلاحية من الرصيد
- طباعة تقرير ارتجاع (Print return report)
- تقرير ادوية مرتجعة (Returned-drugs report) / تقرير اكسبير (Expiry report)
- مردود نقدي (Cash refund) / مرتجع مدفوع (Returned payment)
- دخول نقدية نتيجة ارتجاع الدفع من الشركات (Cash in from refunded supplier payment)
- خروج نقدية نتيجة ارتجاع ادوية في المبيعات (cash-out on sales returns — the mirror)
- فاتورة ضريبية - مرتجع (Tax return invoice)
- الارتجاع (Return) / مرتجع (Return)
- النوع: مرتجع مبيعات (Type: sales return) — return-type label

---

## 10. Business rules / edge cases

1. **Full reversal**: purchase returns reverse all effects of the purchase — stock (subtract), supplier payable (reduce/debit), purchase VAT (reduce), storediscount (reduce).
2. **Return quantity ≤ purchased quantity** — a return cannot exceed the amount originally purchased for that drug/batch.
3. **Stock must be sufficient** — returning more than current stock is prevented (mirror of the sales out-guard).
4. **Three purchase-invoice states**: مشتريات / مرتجع مشتريات / مرتجع الاكسبير.
5. **After day-close (تقفيل اليوم)**: an invoice can no longer be unsaved — it can only be **copied** to a purchase-return invoice (قائمة تحرير → نسخ).
6. **Return by reference** — returns link to the original purchase invoice (by invoice number) and only permit returning items present on it.
7. **Expired-items return (مرتجع الاكسبير)** uses the special **معدوم** (dead) supplier to remove expired/damaged stock; their value is countable from purchase reports.
8. **Cash refund** (مردود نقدي) is recorded as incoming cash when the supplier actually refunds; otherwise the return reduces the payable (أجل).
9. **VAT symmetry**: returned taxable items reduce the purchase VAT total; a tax return invoice (فاتورة ضريبية - مرتجع) can be issued for reconciliation.
10. **Cost basis recalculated** after return so remaining stock value/COGS stays correct.
11. **Returnable detection**: expired items flagged as قابل للارتجاع (returnable) vs معدوم (dead) using arrow keys.
12. **Audit** of all return edits is logged (TitanUserAction; supplier-balance changes require justification).
13. **Permissions** mirror purchases (price/discount view & edit permissions).
14. **E-invoice/DTTS**: purchase returns can be reported to tracking systems (ReturnServiceRequest) — batch/serial-aware.
