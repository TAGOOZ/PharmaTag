# ارصدة — Balances / Trial Balance / Account Balances ("ميزان")

**Purpose:** Full extraction of the balances / trial-balance / balance-sheet feature of TITAN.W1 (Phye.exe). Covers the chart-of-accounts hierarchy (اصول/خصوم/ايرادات/مصروفات — assets / liabilities / income / expenses / equity), opening balances (الارصدة الافتتاحية), double-entry journal posting via ModAccounting / ModMony, the trial balance (ميزان المراجعة) and detailed trial balance (ميزان المراجعة تفصيلي), the balance sheet (الميزانية العمومية / ميزانية), account statements (كشف حساب), capital/equity (راس المال) and profit & loss (ارباح وخسائر) aggregation, and the per-account/per-drug balance tracking that feeds these statements.

Source: `titan_decompile/` (strings_utf16.txt, strings_readable.txt, pcode_disasm.txt), reused from `business_logic_complete.md` (§10 ModMony), `schema_complete.sql` (tables 7, 11, 25, 27), `schema_mapping.md`, `reports_complete.md` (RPT-F02/F03/F04), `reports.md`, `ui_complete.md`, `ui_strings.json`, `modules_gap_1.md` (§14 ModAccounting), `modules_gap_2.md` (§10 FormSafiarbah).

---

## 1. Objects

### 1.1 Core modules / forms (from `pcode_strings.py names`, `ui_forms.json`)

| Object | Type | Procs | Role |
|---|---|---|---|
| **ModAccounting** | Module | 25 | Full double-entry accounting: chart of accounts, journal entries, trial balance, financial statements, reconciliation (modules_gap_1 §14). pcode ~lines 555471–556496. |
| **ModMony** | Module | 41 | Financial module — invoice tracking, financial reports, capital accounts, cash movement (business_logic_complete §10). |
| **FormMizan** | Form | 7 | الميزانية العمومية — balance sheet / trial balance report (reports_complete RPT-F04). pcode ~lines 656838–658676. |
| **FormMizanCreate** | Form | 33 | انشاء ميزان عمومات — trial-balance / balance-sheet creation (reports.md: Mizan/Balance Sheet). pcode ~lines 666261–675931. |
| **FormSafiarbah** | Form | 3 | تحليل الأرباح / راس المال — profit & capital analysis (modules_gap_2 §10; ModCapital). |
| **FormMonyDetails** | Form | 7 | تفاصيل المال — daily cash-flow detail feeding balances (reports RPT-F01). |
| **FormUsersMony** | Form | 24 | أموال المستخدمين — per-user money aggregation. |
| **FormDailyManual / FormDailyManual2** | Form | 6 / 5 | Manual journal entries (القيود اليدوية) — post ad-hoc debit/credit entries to accounts. |
| **FormCorrecyMony** | Form | 4 | تصحيح المال — money balance correction. |
| **ModDailyQuiod** | Module | 2 | Daily close/quietus that computes daily balances. |
| **FormAccReports** | Form | — | تقارير المحاسبية عامة — general accounting reports (RPT-F03 Account/Debit/Credit/Balance). |
| **FormAccUploader** | Form | — | رفع القيود المحاسبية — accounting entries upload (RPT-F11). |
| **FormMohasaby** | Form | — | المحاسب (accountant) screen — accounting operations; connects to FormSafiarbah, FormDariba, FormMoamla, ModAccounting. |
| **ModCapital** | Module | — | Capital management — profit/loss, capital account balance (modules_gap_2 §10). |

### 1.2 Key accounting data files (from strings_readable.txt)

```
\Files\Accounting\                  — accounting data directory
\Files\Accounting\Vat-reports\      — VAT reports
\Files\Accounting\monthly\          — monthly closing accounting data
\Files\Accounting\monthly\ascode\   — monthly account codes
\Files\Accounting\moves\            — journal entries (moves)
\Files\Accounting\sales\            — sales accounting
\Files\accounting\id.txt            — accounting id
\Files\DBI\acctree.phy              — account tree (chart of accounts)
\Files\DBI\acctree2.phy             — account tree (alt)
\Files\DBI\MonyInfo.phy             — money/balance info
\Files\Archive\monthy\moves\        — monthly closing journal moves
\Files\Archive\monthy\start-data\   — monthly closing opening (start) balances
\Files\Archive\mizan-manual\        — manual trial-balance archive
```

---

## 2. Step-by-step workflow

From `modules_gap_1.md` §14 (ModAccounting) + string evidence:

1. **Chart-of-accounts definition** — the account tree is stored in `wzaccfreetree` (master/fary parent-child) and mirrored to `acctree.phy`/`acctree2.phy`. ModAccounting procs 5–10 create/update/delete/simple-balance-check accounts; proc 11 traverses the account tree. Accounts follow a fixed hierarchy (see §9 chart of accounts).

2. **Account lookup** — ModAccounting procs 1–2 look up accounts by code/name; proc 15 validates accounts. FormDailyManual2 selects a master account via `' and master =N'` (idx 1279).

3. **Journal entry posting (double-entry)** — ModAccounting proc 3 (size=272) creates journal entries with debit/credit balancing; proc 12–14 compute account balances. Manual entries require a description first: "ادخل وصف القيد اولا" (idx 8637). Entry types include debit (مدين) and credit (دائن), receipt/payment vouchers (سند قبض idx 11010 / سند صرف idx 11009), and internal transfers (ترحيل النقود ما بين الخزائن idx 10128).

4. **Posting sources** — balances are fed automatically from sales and purchases: "تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات" (idx 10054). The sales GUID loop (`a2a100e1-906b-44df-99c2-6e7c6098421e`, idx 7423) writes `titanksasales`; customer/supplier accrued balances (اجل العملاء / مستحقات الموردين) update from invoices. "البيانات المغذية للقوائم المالية وميزان المراجعة" (idx 9218) — data feeding the financial statements and trial balance.

5. **Trial balance generation** — ModAccounting proc 4 (size=296) generates the trial balance; procs 16 (size=312) generate financial statements; proc 17 reconciles accounts. Reports: ميزان المراجعة (idx 12283), ميزان المراجعة تفصيلي (idx 12284), ميزانية عمومية (idx 12287) via FormMizan / FormMizanCreate.

6. **Balance-sheet creation (FormMizanCreate)** — the user builds the balance sheet; totals include "اجمالي الميزانية" (idx 8322) and per-page subtotal "اجمالي الصفحة الحالية" (idx 8960). The create workflow prompts for opening balances and uses the account tree. A "جرد حسابي" (accounting inventory, idx 11264) and "راس المال" (capital, idx 11520) appear in this flow. Print-template selector: "ادخل رقم نموذج الطباعه من القيم الاتيه 500 600 700 800" (idx 9216).

7. **Capital & P&L (FormSafiarbah / ModCapital)** — capital account (راس المال), profit/loss (ارباح وخسائر, idx 8709), current partner account (جاري الشريك), and capital stats (احصائيات راس المال) are analyzed. Capital calculation: opening capital, investments, withdrawals, net profit, closing capital (RPT-F02).

8. **Account statements (كشف حساب)** — per-account detail: كشف حساب العميل، كشف حساب البنك، كشف حساب الخزينة، كشف حساب النقدية كاش و شبكة شهري، كشف حساب شركة، كشف حساب عميل بالاصناف (idx 11585–11590).

9. **Balance correction** — balances can be adjusted: "تعديل رصيد الاصناف", "تعديل رصيد هذا الدواء", "تصحيح الارصدة بالزيادة/بالعجز" (idx 10174/10175); FormCorrecyMony (تصحيح المال). Staff may request a balance adjustment and the manager accepts/rejects: "اصبح من المتاح ان يقوم اي مستخدم بتقديم طلب تعديل الرصيد ويمكن للمدير قبول الطلب او رفضه" (idx 8837). Rejection on race: "بعد ان تم تقديم الطلب حدث تعديل علي الرصيد لا يمكن قبول الطلب" (idx 9945). Corrections tracked automatically (تتبع تصحيح الارصدة تلقائيا, idx 8910; `RasidCorrect.phy`).

10. **Opening balances (الارصدة الافتتاحية)** — set at setup: opening drawer cash (الرصيد الافتتاحي للخزينه idx 8482), opening stock at cost excl. VAT (الرصيد الافتتاحي للمخزون بسعر التكلفه غير شامل الضريبه idx 8483), opening customer receivables (الرصيد الافتتاحي لمديونيات العملاء idx 8484), opening supplier payables (الرصيد الافتتاحي لمستحقات الموردين idx 8485). Labels: "الارصدة الافتتاحية" (idx 9102), "افتتاحي مدين/دائن" (idx 9055/9056). Month-end closing writes start-data (opening balances) for the next month (`\Files\Archive\monthy\start-data\`). Closing balances: "ختامي مدين/دائن" (idx 10748/10749).

11. **Reconciliation & audit** — ModAccounting proc 17 reconciles accounts; "عرض كشف حساب العميل" (idx 11287); "ضبط الحسابات المالية" (idx 11183) — adjust financial accounts; pending balance-adjustment requests review ("Review pending requests to adjust balances" per modules_gap_1 §14).

---

## 3. Fields / data captured

### 3.1 Trial-balance / balance-sheet report columns (reports_complete RPT-F04)
```
Account Code, Account Name, Debit, Credit, Balance
```
Grouped by account category: Assets, Liabilities, Equity, Revenue, Expenses. Totals: اجمالي الميزانية (total of the balance sheet, idx 8322), اجمالي الاصول (total assets, idx 8885), اجمالي الخصوم (total liabilities, idx 8304), اجمالي الصفحة الحالية (current page subtotal, idx 8960).

### 3.2 Accounting-entry fields (FormAccReports / ModAccounting journal)
```
Account, Debit, Credit, Balance, Period        (RPT-F03)
Entry Date, Account, Debit, Credit, Description, Status   (RPT-F11 upload)
```

### 3.3 Account-statement (كشف حساب) types
```
كشف حساب                      (idx 11585) — generic account statement
كشف حساب البنك                 (idx 11586) — bank statement
كشف حساب الخزينة               (idx 11587) — treasury statement
كشف حساب النقدية كاش و شبكة شهري (idx 11588) — monthly cash & network statement
كشف حساب شركة                 (idx 11589) — supplier statement
كشف حساب عميل بالاصناف          (idx 11590) — customer statement by items
```

### 3.4 Capital / P&L fields (FormSafiarbah / RPT-F02)
```
Opening Capital, Investments, Withdrawals, Net Profit, Closing Capital
راس المال (capital, idx 11520 / 10857), ارباح وخسائر (idx 8709),
حقوق ملكية.راس المال / جاري الشريك / ارباح وخسائر (idx 10734–10736)
احصائيات راس المال ونظرة عامة علي الصيدلية (idx 8350), احصائيات راس المال (idx 8354)
```

### 3.5 Balance field variants (drug balances, idx 9367–9373)
```
الرصيد (balance), الرصيد لاصناف الفاتورة الحالية, الرصيد الان (current),
الرصيد الحالي (current stock), الرصيد الكلي (total), الرصيد عشري (decimal),
الرصيد وتواريخ الصلاحية (balance & expiry dates)
```

### 3.6 Per-account double-entry sides
```
مدين (debit, idx 12035), دائن (credit, idx 10830)
حركه مدين / حركة دائن (idx 10696/10693) — debit movement / credit movement
الي حساب مدين / الي حساب دائن (idx 9766/9765) — to debit / to credit account
قيمة مدينة / قيمة دائنة (idx 11568/11558) — debit value / credit value
صافي المدين / صافي الدائن (idx 11145/11138) — net debit / net credit
افتتاحي مدين/دائن (idx 9055/9056) — opening debit/credit
ختامي مدين/دائن (idx 10748/10749) — closing debit/credit
```

---

## 4. Side-effects

- **Customer/supplier balances:** automatically update from sales & purchases screens (idx 10054); accrued balances (اجل العملاء، مستحقات الموردين، الشركات) feed the balance sheet and age analysis (التسلسل الزمني للارصدة والعملاء, idx 9249).
- **Stock balances:** drug stock (الرصيد) in `wzdrugs.stock` / `wzgard` / `titanstock`; cost of stock feeds أصول-المخزون (inventory asset).
- **Cash & bank:** cash (كاش) and network/bank (بنوك) positions feed أصول-النقديةكاش / أصول-النقدية بنوك; money movement (حركة مالية) updates these balances.
- **Journal (moves):** journal entries stored under `\Files\Accounting\moves\` and `\Files\Archive\monthy\moves\`; manual entries in `daily-manual.phy`.
- **Capital:** withdrawals (توزيع ارباح / خروج مال من المشروع) reduce capital; profits increase it.
- **Fary/branch:** `farysales` (father/son accounts, creditdebit) records per-branch ledger; monthly start-data carries opening balances forward.
- **VAT:** VAT payable/receivable tracked as accounts (اصول متداولة.ضريبة.قيمة مضافة, خصوم متداولة.ضريبة.قيمة مضافة); VAT reports under `\Files\Accounting\Vat-reports\`.

---

## 5. Pricing + VAT

Balances do not compute prices, but they account for VAT by account:
- Input VAT (purchases) and output VAT (sales) are represented as chart accounts (اصول متداولة.ضريبة.قيمة مضافة = receivable; خصوم متداولة.ضريبة.قيمة مضافة = payable).
- "التاريخ-...-الضريبة في المبيعات اليوم - الضريبة في المشتريات اليوم - الضريبة في المصروفات اليوم" (idx 9232) — daily VAT buckets by sales/purchases/expenses feed the VAT accounts.
- VAT-tag `<masrofat-vat>` (expense VAT) live in the expense pipeline; `ModAccounting` proc 21 integrates a VAT report (modules_gap_1 §14).

---

## 6. Payment methods

Balance accounts capture all payment methods:
- Cash (كاش / نقدية) → أصول-النقديةكاش; Network/card (شبكة) → نقدية.شبكة; Bank (بنوك) → أصول-النقدية بنوك.
- Credit/accrued (اجل) → عملاء / موردين accounts; receivable and payable ledgers.
- Transfers between treasuries (ترحيل النقود ما بين الخزائن, idx 10128) move balances between cash accounts without affecting totals.
- Vouchers: سند قبض (receipt, idx 11010), سند صرف (payment, idx 11009).

---

## 7. Printing

- **Trial balance** (ميزان المراجعة) and **detailed trial balance** (ميزان المراجعة تفصيلي) — FormMizan / FormMizanCreate.
- **Balance sheet** (الميزانية العمومية / ميزانية) — FormMizan (RPT-F04).
- **Account statement** (كشف حساب) — per customer/bank/treasury/cash-network/supplier (idx 11585–11590).
- **Capital report** (تقارير راس المال, RPT-F02) — FormReportsGeneral / FormSafiarbah.
- **General accounting report** (تقارير المحاسبية عامة, RPT-F03) — FormAccReports.
- **Accounting entries upload report** (RPT-F11) — FormAccUploader.
- **Manual-entry report** (RPT-F10) — FormDailyManual.
- Print-template selector for balance/close reports: "ادخل رقم نموذج الطباعه من القيم الاتيه 500 600 700 800" (idx 9216).
- "اجمالي الصفحة الحالية" (idx 8960) — current-page subtotal label used on printed balance sheets.

---

## 8. Tables

### 8.1 wzaccfreetree — chart-of-accounts tree (account hierarchy)
From `schema_complete.sql` table 25 + `strings_readable` line 7604 + `FormDailyManual2` (`' and master =N'` idx 1279).

```sql
CREATE TABLE wzaccfreetree (
    id       INT IDENTITY(1,1),           -- [INFERRED] auto-increment PK
    mobile   NVARCHAR(15) DEFAULT '',     -- [EXPLICIT] pharmacy phone
    master   NVARCHAR(100) DEFAULT '',    -- [EXPLICIT] master (parent) account
    fary     NVARCHAR(100) DEFAULT ''     -- [EXPLICIT] sub (child/leaf) account
);
-- INSERT INTO wzaccfreetree (mobile,master,fary) VALUES (...)   (line 7604)
-- master/fary pairs encode the dotted hierarchy (اصول.متداولة.نقدية.كاش, etc.)
```

### 8.2 farysales — per-branch/per-account ledger
From `schema_complete.sql` table 27 + `strings_readable` line 181 / 773. Columns: `mobile, grand, father, son, datee, datetimee, dateemanual, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy`. `father`/`son` map to chart accounts, `creditdebit` marks the side, `payed` is the amount, `monthe`/`yearo` allow monthly aggregation. Live: `SELECT * FROM farysales WHERE mobile = N'...'`.

### 8.3 invoicedata — invoice/line source for customer & money balances
`schema_complete.sql` table 11 — `invoiceid, datee, pharmacyid, payed, disc, totalvalue, IdDateTime, Quant, DrugName, SellDisc, price`; drives customer accrued balances and money totals.

### 8.4 titanksasales — chain sales summary
`schema_complete.sql` table 7 — feeds sales balances; written via the live GUID insert loop.

### 8.5 wzcustomers — customer master (credit balances)
`schema_complete.sql` table 4 — `randomid, phar, typee, writer, creditlimit, datee, namee`; `creditlimit` is the customer credit ceiling that balances are checked against.

### 8.6 Stock tables feeding inventory asset
`schema_complete.sql` tables 1, 3, 9, 10 (`wzdrugs.stock`, `wzgard`, `titanstock`, `titanksastock`) — the inventory (المخزون) asset account aggregates cost-of-stock.

### 8.7 File-backed account data
`acctree.phy`, `acctree2.phy` (account tree), `MonyInfo.phy` (balances), `RasidCorrect.phy` (balance corrections), `\Files\Accounting\moves\` (journal), `\Files\Archive\monthy\start-data\` (opening balances).

---

## 9. Chart of accounts (اصول/خصوم/ايرادات/مصروفات)

Reconstructed dotted hierarchy from `strings_readable.txt` (idx 8885–8907, 10734–10736, 10785–10795, 9847–9848, 12139–12146):

**Assets (اصول):**
```
اصول.اجمالي الاصول                       — total assets
اصول.اصول ثابتة / اصول.ثابتة             — fixed assets
اصول.اصول متداولة / اصول.متداولة          — current assets
اصول.متداولة.نقدية                       — cash (cash on hand)
اصول.متداولة.نقدية.كاش                   — cash drawer
اصول.متداولة.نقدية.شبكة                  — network/card cash
اصول.متداولة.مخزون                       — inventory
اصول.متداولة.عملاء / اصول.العملاء        — customers (receivables)
اصول.متداولة.بنوك / اصول.النقدية بنوك     — banks
اصول.متداولة.ضريبة.قيمة مضافة            — input VAT receivable
اصول-مصروفات اهلاك / مصروفات اهلاك        — depreciation
اصول.متداولة.قيمة مضافة                  — VAT asset
اصول.اصول متداولة.عملاء.الكل              — all customers
اصول-النقديةكاش                          — cash assets
اصول-النقدية بنوك                        — bank assets
اصول-المخزون                             — inventory assets
اصول-العملاء                             — customer assets
```

**Liabilities (خصوم):**
```
خصوم.ثابتة / خصوم.خصوم ثابتة             — fixed liabilities
خصوم.خصوم متداولة / خصوم.متداولة          — current liabilities
خصوم.متداولة.موردين / خصوم.موردين         — suppliers (payables)
خصوم.متداولة.موردين.الكل                  — all suppliers
خصوم.متداولة.ضريبة.قيمة مضافة            — output VAT payable
اجمالي الخصوم                            — total liabilities
```

**Equity (حقوق ملكية):**
```
حقوق ملكية.راس المال                     — capital
حقوق ملكية.جاري الشريك                   — partner current account
حقوق ملكية.ارباح وخسائر                  — profit & loss
```

**Income (ايرادات):**
```
ايرادات.مبيعات                           — sales revenue
ايرادات.ايرادات اخري                     — other income
اجمالي ايرادات المبيعات الكاش و الشبكه    — total cash & network sales revenue
```

**Expenses (مصروفات):**
```
مصروفات.ادارية                           — administrative expenses
مصروفات.تاسيسية                          — establishment expenses
مصروفات.تشغيلية / مصروفات مصروفات تشغيلية — operating expenses
مصروفات.تشغيلية.تكلفة مبيعات             — cost of sales
مصروفات.تشغيلية.متنوع                    — sundry operating
مصروفات ايجارات                          — rent expenses (idx 12128)
اجمالي المصروفات                         — total expenses
```

---

## 10. UI strings (Arabic)

### 10.1 Report titles
- `ميزان المراجعة` (idx 12283) — Trial balance
- `ميزان المراجعة تفصيلي` (idx 12284) — Detailed trial balance
- `ميزان مراجعة` (idx 12285) — Trial balance (variant)
- `ميزانية` (idx 12286) — Budget/balance sheet
- `ميزانية عمومية` (idx 12287) — Balance sheet (general)
- `الميزان` / `الميزانية العمومية` — Mizan / balance sheet (ui_complete form titles)
- `اجمالي الميزانية` (idx 8322) — Total of the balance sheet
- `البيانات المغذية للقوائم المالية وميزان المراجعة` (idx 9218) — data feeding financial statements & trial balance
- `احصائيات راس المال ونظرة عامة علي الصيدلية` (idx 8350) — capital stats & pharmacy overview
- `احصائيات راس المال` (idx 8354) — capital stats
- `ارباح وخسائر` (idx 8709) — profit & loss
- `كشف حساب` (idx 11585) + bank/treasury/cash-network/supplier/customer variants (idx 11586–11590)
- `تسلسل الارصدة والعملاء` / `التسلسل الزمني للارصدة والعملاء` (idx 9249) — chronological balance & customer sequence

### 10.2 Buttons / actions
- `الارصدة الافتتاحية` (idx 9102) — opening balances
- `ادخل الرصيد الافتتاحي للخزينه` (idx 8482) — enter opening drawer cash
- `ادخل الرصيد الافتتاحي للمخزون بسعر التكلفه غير شامل الضريبه` (idx 8483)
- `ادخل الرصيد الافتتاحي لمديونيات العملاء` (idx 8484)
- `ادخل الرصيد الافتتاحي لمستحقات الموردين` (idx 8485)
- `افتتاحي مدين / افتتاحي دائن` (idx 9055/9056) — opening debit / credit
- `ختامي مدين / ختامي دائن` (idx 10748/10749) — closing debit / credit
- `تعديل رصيد الاصناف` / `تعديل رصيد هذا الدواء` / `تعديل رصيد هذا الصنف` — adjust item/drug balances
- `تصحيح الارصدة بالزيادة` / `تصحيح الارصدة بالعجز` (idx 10174/10175) — correct balances up/down
- `تعديل رصيد هذا الدواء مباشرة` — adjust this drug balance directly
- `ادخل وصف القيد اولا` (idx 8637) — enter journal-entry description first
- `سند قبض` (idx 11010) / `سند صرف` (idx 11009) — receipt / payment voucher
- `ترحيل النقود ما بين الخزائن` (idx 10128) — transfer money between treasuries
- `ضبط الحسابات المالية` (idx 11183) — adjust financial accounts
- `جرد حسابي` (idx 11264) — accounting inventory
- `راس المال` (idx 11520/10857) — capital

### 10.3 Column labels
- `اصناف بسعر الجمهور` / `اصناف بسعر التكلفة` (idx 9226) — items at public price / cost price
- `عملاء مدينون` / `موردين دائنون` (idx 9226) — debtor customers / creditor suppliers
- `الرصيد الحالي` / `الرصيد الكلي` / `الرصيد الان` / `الرصيد عشري` (idx 9370/9371/9369/9372)
- `الصنف سعر الرصيد عدد شهري قيمة شهرية اخر شراء` (idx 9447)
- `مبيعات / تكلفة المبيعات / قبل الخصم / فات المبيعات / اجل العملاء / محصل نقدا مبيعات / محصل شبكة مبيعات` (idx 9225/9451)
- `التاريخ الفرع الاصناف بسعر الجمهور الاصناف بسعر التكلفة عملاء مدينون موردين دائنون` (idx 9226)

### 10.4 Messages
- `فشلت عمليت تعديل الرصيد` — balance-adjustment failed
- `بعد ان تم تقديم الطلب حدث تعديل علي الرصيد لا يمكن قبول الطلب` (idx 9945) — concurrent balance change; request cannot be accepted
- `التسلسل غير صحيح ، من فضلك اعد المحاولة` (idx 9250) — sequence incorrect, retry
- `التاريخ المثالي وفقا للتسلسل` (idx 9229) — ideal date per the sequence
- `انت لا تملك صلاحيات كافية لدخول هذه الشاشة` — insufficient permissions
- `اعتبار الارصدة صحيحة وتم جردها لهذه الفاتورة` (idx 9030) — balances considered correct & counted for this invoice

---

## 11. Business rules / edge cases

1. **Double-entry balance:** journal entries must balance debit = credit (ModAccounting proc 3); entries split across `farysales` (creditdebit) and account tree.
2. **Auto-posted balances:** customer and supplier balances change automatically from sales and purchases (idx 10054); no manual reposting needed for normal sales/purchases.
3. **Data integrity:** "غير مسموح بتغير التاريخ الا بهذه الطريقة حفاظا علي الحسابات الدقيقة للبرنامج" (idx 12032) — date changes are restricted to protect accurate accounting; "لقد تم ايقاف ميزة تعديل التاريخ نهائيا اتصل بخدمة العملاء" (idx 12544).
4. **Sequence check:** the chronological balance sequence must be correct ("التسلسل غير صحيح...", idx 9250); an ideal date is derived from the sequence (idx 9229).
5. **Opening balances:** set once at setup for treasury cash, stock-at-cost (excl. VAT), customer receivables, supplier payables (idx 8482–8485); month-end close writes next month's opening (`start-data`).
6. **Approval workflow:** any user may request a balance adjustment; only the manager accepts or rejects (idx 8837); concurrent modification invalidates a pending request (idx 9945).
7. **Audit trail:** balance corrections are tracked automatically (idx 8910; `RasidCorrect.phy`); admin can delete old records from the balance/counting screen (idx 8840).
8. **Negative-balance alert:** the app warns when items have negative balances on a new sales invoice and explains how to fix them (idx 9267); a "negative balances" command exists in the counting menu (idx 8929).
9. **Retention option:** deleting all invoices can keep drug/customer/supplier balances (idx 8938) — "delete invoices but keep balances".
10. **Security:** additional tools guard against tampering/theft/balance-settling by staff in purchase invoices (idx 8987).
11. **Capital/equity accounting:** capital, partner current account and P&L are equity accounts (حقوق ملكية); profit distribution / capital withdrawal (خروج مال من المشروع- توزيع ارباح, idx 10757) debits capital.
12. **VAT accounts:** input VAT (asset) and output VAT (liability) are chart accounts; quarterly VAT reports (FormVat/FormVat2) reconcile against them.
13. **Per-branch (fary):** balances are tracked per pharmacy `mobile`/`phar` in `wzaccfreetree` and `farysales`, enabling chain-level balance sheets.

---

## 12. Reused references

- business_logic_complete.md §10 ModMony (financial ops, trial balance, capital account reports, payment types).
- schema_complete.sql tables 4, 7, 11, 25, 27.
- schema_mapping.md (FormMizan→, FormMizanCreate→, ModAccounting→invoicedata/wzcustomers).
- reports_complete.md RPT-F02 (capital), RPT-F03 (general accounting), RPT-F04 (mizan), RPT-F11 (entries upload).
- reports.md G (financial reports: Balance Chronology, Mizan/Balance Sheet).
- modules_gap_1.md §14 ModAccounting (25 procs, accounting files, key strings).
- modules_gap_2.md §10 FormSafiarbah, ModCapital.
- ui_complete.md form-title table (FormMizan=الميزانية العمومية, FormMizanCreate=انشاء ميزان عمومات).
