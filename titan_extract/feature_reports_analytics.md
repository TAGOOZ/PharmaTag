# TITAN.W1 — التقارير والتحليلات (Reports & Analytics)

> Consolidated feature doc. Extracted from the VB6 P-Code disassembly of `Phye.exe` (TITAN.W1) via the decoder tool, reusing the existing extraction corpus. Primary sources: `reports_complete.md` (50+ reports, 1300 lines), `reports.md` (532 lines), `feature_balances.md`, `feature_account_closing.md`, `feature_sales_invoices.md`, `feature_shortages.md`, `feature_transfers_logistics.md`, `ui_complete.md`, `ui_strings.json`, `modules_gap_2.md` (§10 FormSafiarbah), `schema_complete.sql`. All citations are `file:line` unless stated otherwise.

**Purpose:** catalog every report of the pharmacy (sales, purchases, stock, customers, suppliers, money, tax, chain, shortages, discounts, day/month close, balance sheet), the report infrastructure (report forms, printer engine, templates), the print flow, profit analysis (تحليل الأرباح / راس المال), the report-ID numbering scheme (RPT-xx), and the business rules that govern report generation, filtering, printing, and export.

---

## 1. Objects (forms / modules / procs)

| Object | Type | Procs | Role |
|---|---|---|---|
| `ModPrint` | Module | 70 | Core printing engine — all print/export operations (`reports_complete.md:5`, `reports.md:393`) |
| `FormReportsGeneral` | Form | 61 | Central reports hub — generates the majority of report categories (`reports_complete.md:5`, `ui_strings.json:381`) |
| `FFFOutputTakarir` | Form | 16 | Sales report engine — تقارير المبيعات / اجمالي المبيعات والارباح (`reports_complete.md:5,27,30`) |
| `FFFInputTakarir` | Form | — | Purchase report engine — تقارير المشتريات (RPT-P01..P07) (`reports_complete.md:28,200`) |
| `FormOutPuttakarirSpeed` | Form | 9 | Fast sales-volume reports — تقارير المخرجات السريعة (RPT-S05/S06), correction receipts (كشف تصحيح) (`ui_strings.json:382`, `feature_invoice_editing.md:20`) |
| `FormInputtakarirSpeed` | Form | 5 | Fast purchase-volume reports — تقارير المدخلات السريعة (`ui_strings.json:388`) |
| `FormAmilTakarir` | Form | 23 | Employee reports — تقارير الموظفين, drug-sales detail (RPT-S03/S04/S08/S09, RPT-A01..A03) (`ui_strings.json:380`, `reports_complete.md:5`) |
| `FormPrintSales` | Form | 17 | Sales printing — prints sales invoices/receipts (طباعة المبيعات) (`ui_strings.json:844`, `feature_sales_invoices.md:19`) |
| `FormPrinterSettings` | Form | 31 | Printer configuration (report/barcode/receipt/A4 printers, paper, margins, copies) (`reports_complete.md:5,893`) |
| `FormPrinterSettingFary` | Form | 28 | Branch/sub-device printer configuration (`reports_complete.md:5,943`) |
| `FffSelectPrinter` | Form | 2 | Printer selection dialog (`reports_complete.md:952`) |
| `FFFOutputTakarir`/`FFFDayEnd` | Form | 16/25 | Day & month close report engine (تقفيل اليوم / الشهر) (`reports_complete.md:5,335,342`, `feature_account_closing.md:17`) |
| `FormTaslimReport` | Form | 7 | Shift drawer handover reports — تقارير تسليم الدرج بين الفترات (RPT-A04) (`ui_strings.json:126`, `reports_complete.md:38,492`) |
| `FormTawsil` | Form | 6 | Delivery reports — تقارير التوصيل (RPT-DEL01) (`reports_complete.md:39,597`, `modules_gap_2.md:308`) |
| `FormSilsila` | Form | 26 | Chain reports (modern) — تقارير السلسلة (RPT-CH01); chain administration (`ui_strings.json:778`, `reports_complete.md:40,607`, `feature_transfers_logistics.md:51`) |
| `FormFaryNet` | Form | 8 | FaryNet network form — remote branch sales monitoring & sync (`ui_strings.json:1234`, `feature_sales_invoices.md:30`) |
| `FormOotSum` | Form | 9 | Output summary — ملخص المخرجات (sales summary; data source `invoicedata`) (`ui_strings.json:964`, `feature_sales_invoices.md:26`) |
| `FormootThisDay` | Form | 11 | Today's output — مخرجات هذا اليوم (فواتير مبيعات اليوم, incl. returns) (`ui_strings.json:712`, `feature_sales_invoices.md:25`) |
| `FormSafiarbah` | Form | 3 | تحليل الأرباح — profit & capital analysis (RPT-F02); connects FormMohasaby, FormDariba, FormMoamla, ModCapital (`ui_strings.json:958`, `modules_gap_2.md:279-298`, `feature_balances.md:19`) |
| `FormMizan` / `FormMizanCreate` | Form | 7 / 33 | Balance sheet / trial balance — الميزان (RPT-F04), ميزان المراجعة (+ تفصيلي) (`reports.md:83`, `feature_balances.md:17`) |
| `FormAccReports` | Form | 4 | General accounting reports — تقارير المحاسبية عامة (RPT-F03) (`reports_complete.md:37,526`) |
| `FormAccUploader` | Form | — | Accounting entries upload — رفع القيود المحاسبية (RPT-F11) (`reports_complete.md:588`) |
| `FormDailyManual` / `FormDailyManual2` | Form | 6 | Manual daily entries — القيود اليدوية (RPT-F10) (`reports.md:18`, `feature_account_closing.md:23`) |
| `FormMonyDetails` | Form | 7 | Daily cash flow — حركة النقدية اليوم (RPT-F01) (`feature_balances.md:20`, `feature_account_closing.md:26`) |
| `FormVat` / `FormVat2` | Form | 20 / 38 | VAT processing & GCC/quarterly VAT report (RPT-F08/F07) (`reports.md:88`, `ui_strings.json:193`) |
| `ModVatReport` | Module | — | VAT report generation (`reports_complete.md:555`) |
| `ModZatca` / `ModZatca2Wraber` | Module | 14 / 24 | ZATCA e-invoicing integration & submission-status reports (`reports.md:90`) |
| `FormWasfaty` | Form | 27 | Wasfaty prescription reports (RPT-S15) (`reports.md:51,109`) |
| `FormBest100` | Form | — | Top-100 drugs report (RPT-S07) (`reports_complete.md:133`) |
| `FormDrugFlow` | Form | 32 | Drug movement tracking (RPT-ST06) (`reports.md:73`, `reports_complete.md:395`) |
| `FormDrugsDetails` | Form | 51 | Stock detail reports (`reports.md:66`) |
| `FormExpiredDrugs` / `FormExpireDetails` | Form | 21 / — | Expired drugs (RPT-D01) / expiry details (`reports.md:68-69`) |
| `FormExpiresControl` | Form | — | Expiry control (RPT-EXP01) (`reports_complete.md:619`) |
| `FormDrugStckAtMonths` | Form | 12 | Drug stock at month end (RPT-D03) (`reports.md:67`) |
| `FormDrugMonthly` / `FormDrugMoveMonthly` | Form | 7 / — | Monthly drug report (RPT-D02) / movement (RPT-D04) (`reports.md:74`) |
| `FormDrugsLastDays` | Form | — | Last-days drug activity (RPT-D07) (`reports_complete.md:446`) |
| `FormLastEdited` | Form | 10 | Last manually-edited drugs (RPT-D05) (`feature_sales_invoices.md:27`) |
| `FormInvoiceTrackEditing` | Form | 4 | Invoice edit tracking (RPT-SP03) (`feature_sales_invoices.md:20`) |
| `FormSimilars` | Form | — | Similar drugs report (RPT-D08) (`reports_complete.md:452`) |
| `FormDrugPrice` | Form | — | Drug price report (RPT-D09) (`reports_complete.md:458`) |
| `FFFDrugrasidCorrect` | Form | — | Stock-correction tracking (RPT-D10) (`reports_complete.md:464`) |
| `FormStoreDiscount` | Form | — | Store discounts report (RPT-F05) (`reports_complete.md:540`) |
| `FormHodour` / `FormHodour19` | Form | 16 / 35 | Attendance / login-time reports (RPT-A02/A03) (`reports.md:98-99`) |
| `FormNeedsAll` | Form | 50 | Needs / shortage reports (RPT-ST) (`reports.md:107`) |
| `FormPeriodEhsa` | Form | 9 | Period statistics (`reports.md:112`) |
| `FormUserEhsa` | Form | 12 | User statistics (`ui_strings.json:394`) |
| `FormDrugMonthly` | Form | 7 | Monthly drug follow-up (`reports.md:74`) |
| Data modules | Module | — | `ModStorage` (154) all data access, `ModOot` (105) output/purchases, `ModInn` (71) sales/input, `ModMony` (30) money, `ModAccounting` (25) accounting, `ModCapital` (capital), `ModPrint` (70) printing (`reports.md:425-432`) |

---

## 2. Report catalog by category

Reports are reached under the main menu قائمة تقارير (Reports) in **18 major categories** (`reports_complete.md:23-45`):

| # | Category (Arabic) | Category (English) | Engine |
|---|---|---|---|
| 1 | تقارير المبيعات | Sales Reports | FFFOutputTakarir |
| 2 | تقارير المشتريات | Purchase Reports | FFFInputTakarir |
| 3 | تقارير العملاء | Customer Reports | FormReportsGeneral |
| 4 | تقارير اجمالي المبيعات والارباح | Total Sales & Profit | FFFOutputTakarir |
| 5 | تقارير حجم المبيعات | Sales Volume | FormOutPuttakarirSpeed |
| 6 | تقارير حجم مبيعات الادوية | Drug Sales Volume | FormOutPuttakarirSpeed |
| 7 | تقارير تاريخ الصيدلية | Pharmacy History | FormReportsGeneral |
| 8 | تقارير النواقص | Shortages | FormReportsGeneral |
| 9 | تقارير النواقص للاطلاع | Shortages Review | FormReportsGeneral |
| 10 | تقارير المحاسب | Accountant | FormReportsGeneral |
| 11 | تقارير المحاسبية عامة | General Accounting | FormAccReports |
| 12 | تقارير تسليم الفترات | Shift Handover | FormTaslimReport |
| 13 | تقارير التوصيل | Delivery | FormTawsil |
| 14 | تقارير السلسلة | Chain (Modern) | FormSilsila |
| 15 | تقارير حساب راس المال | Capital Calculation | FormReportsGeneral |
| 16 | تقارير متعددة | Multiple/Misc | FormReportsGeneral |
| 17 | تقارير مستحقات الشركات | Company Dues | FormReportsGeneral |
| 18 | تقارير مبيعات (تفصيلية) | Sales (Detailed) | FormAmilTakarir |

### 2.1 Sales reports — تقارير المبيعات (`reports_complete.md:50-195`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-S01 | فواتير مبيعات اليوم | Daily Sales Invoices | FFFOutputTakarir | `titanksasales` where `datee=TODAY`; cols invoiceid,datee,drugname,quant,price,disc,vat,totalvalue,mobile,writer; grouped by invoice, sorted by date desc |
| RPT-S02 | تقرير ادوية مرتجعة | Drug Returns | FFFOutputTakarir | `titanksasales` where `creditdebit`=return; total returned value |
| RPT-S03 | تقرير مبيعات الادوية | Drug Sales | FormAmilTakarir | `titanksasales` GROUP BY `drugname`; SUM(quant), SUM(totalvalue), AVG/MAX/MIN(price); group by `classy` |
| RPT-S04 | فواتير مبيعات موظف | Employee Sales Invoices | FormAmilTakarir | `titanksasales` GROUP BY `writer`; invoice count, total, VAT, avg |
| RPT-S05 | اجمالي مبيعات الفترة | Period Sales Total | FormOutPuttakarirSpeed | Aggregated sales; period, total sales, cost, gross profit, VAT, net |
| RPT-S06 | تقارير حجم مبيعات الادوية | Drug Sales Volume | FormOutPuttakarirSpeed | Sales GROUP BY drug; qty, value, cost, profit, margin %; by `classy`/supplier |
| RPT-S07 | افضل 100 دواء | Top 100 Drugs | FormBest100 | Top 100 by volume; rank, qty, revenue, last sale date |
| RPT-S08 | تقارير مبيعات اثناء اليوم | Intraday Sales | FormAmilTakarir | Current-day real-time; time, invoice#, drug, qty, price, total, running total |
| RPT-S09 | طباعة للشركات التأمين | Insurance-company printing | FormAmilTakarir | Sales filtered by insurance customer type; insurance share vs patient share |
| RPT-S10 | الفواتير غير المربوطه مع الهيئات الحكوميه | Unlinked gov. entity invoices | FormReportsGeneral | Invoices not linked to gov entities (added v348+, `ui_strings_readable.txt:1148`) |
| RPT-S11 | تقرير لتجميع المدفوع يدويا عند تقفيل اليوم | Manual payments aggregation at day close | FormReportsGeneral | Manual payment entries at day close (added v348+, `ui_strings_readable.txt:1951`) |
| RPT-S12 | تقرير لعرض ملاحظات الفوتير المسجلة يدويا | Manual invoice notes | FormReportsGeneral | Invoice notes/comments field (added v348+, `ui_strings_readable.txt:2076`) |
| RPT-S13 | تقرير مبيعات اصناف مورد محدد لعميل محدد | Supplier's items → specific customer | FormReportsGeneral | Sales filtered by supplier AND customer (added v348+, `ui_strings_readable.txt:428`) |
| RPT-S14 | تقرير مسحوبات العميل | Customer withdrawals | FormReportsGeneral | Customer withdrawal transactions; name, amount, date, remaining, branch |
| RPT-S15 | تقرير وصفتي عن الفترة ادناه | Wasfaty prescription report | FormWasfaty | Prescription data; patient, doctor, drug list, status, date range |

### 2.2 Purchase reports — تقارير المشتريات (`reports_complete.md:198-258`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-P01 | تقارير المشتريات | Purchase Reports | FFFInputTakarir | Purchase invoice tables; invoice#, date, supplier, drug, qty, unit price, disc, total, expiry date (تاريخ الصلاحية), batch no (رقم التشغيلة); group by supplier/date |
| RPT-P02 | مشتريات بسعر البيع | Purchases at Selling Price | FFFInputTakarir | Purchases recalculated at selling price; cost vs selling, margin, totals |
| RPT-P03 | فات المشتريات (الاجل) | Outstanding/Credit Purchases | FFFInputTakarir | Unpaid purchase invoices; supplier, invoice#, date, paid, remaining, due |
| RPT-P04 | مسدد نقدا مشتريات | Cash-paid purchases | FFFInputTakarir | Purchases where `payed>0` and `creditdebit`=cash |
| RPT-P05 | مسدد شبكة مشتريات | Network-paid purchases | FFFInputTakarir | Purchases where `payed>0` and `creditdebit`=network/card |
| RPT-P06 | اجل المشتريات | Credit purchases | FFFInputTakarir | Purchases on credit (`creditdebit`=credit) |
| RPT-P07 | تقرير الواردات والمصروفات | Imports & Expenses | FFFInputTakarir | Date, import type, drug, supplier, qty, value, tax, notes (`ui_strings_readable.txt:1994`) |

### 2.3 Customer reports — تقارير العملاء (`reports_complete.md:261-297`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-C01 | تقارير العملاء | Customers' Reports | FormReportsGeneral | Customer + sales aggregation; **اسم العميل, مديونية العميل, الفرع**; sort by debt desc; filter branch/debt threshold/type |
| RPT-C02 | احصائيات نقاط العملاء | Customer Points Statistics | FormReportsGeneral | Points earned/redeemed/balance + purchases per customer |
| RPT-C03 | تقرير عملاء شركة التأمين | Insurance-company customers | FormReportsGeneral | Customers linked to insurance companies; policy#, claims, coverage; filter by company (added v348+, `ui_strings_readable.txt:2075`) |
| RPT-C04 | تقرير بالاصناف لعميل | Item detail per customer | FormReportsGeneral | Customer, drug, qty, value, last purchase (A4 print improved v352+, `ui_strings_readable.txt:615`) |

### 2.4 Supplier reports — تقارير الموردين (`reports_complete.md:298-317`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-SUP01 | تقارير الموردين | Suppliers' Reports | FormReportsGeneral | Supplier purchase aggregation; **اسم المورد, مستحقات المورد, الفرع**; sort by dues desc |
| RPT-SUP02 | تقارير مستحقات الشركات | Company Dues | FormReportsGeneral | Company, total purchases, total paid, remaining due, last payment |

### 2.5 Pharmacy history — تقارير تاريخ الصيدلية (`reports_complete.md:319-347`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-H01 | تقرير تاريخ الصيدلية | Pharmacy History | FormReportsGeneral | **التاريخ, القيمة, الضريبة, الوصف, البيان, الخزينة, الفرع**; group by date/branch; daily/monthly/yearly totals; aggregation lists (قائمة تجميعات) at top of screen (`ui_strings_readable.txt:2065`) |
| RPT-H02 | تقفيل اليوم | Day Close | FFFDayEnd | End-of-day aggregation: opening balance, sales, returns, purchases, expenses, cash received, card received, closing balance, difference (`feature_account_closing.md:89`) |
| RPT-H03 | تقفيل الشهر | Month Close | FFFDayEnd | Month: sales, purchases, expenses, profit, cash flow, outstanding (`feature_account_closing.md:193-194`) |

### 2.6 Shortage / stock reports — تقارير النواقص (`reports_complete.md:349-401`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-ST01 | تقرير النواقص | Shortages | FormReportsGeneral | Drugs where `stock<minimum`; drugname, stock, minimum, shortage=min−stock, last purchase price, classy, silsilaid; group by category/chain; sort by shortage desc (`feature_shortages.md:156`, idx 10962) |
| RPT-ST02 | كشف النواقص بنظام التسجيل اليدوي | Manual-registration shortages | FormReportsGeneral | Manually registered shortage entries |
| RPT-ST03 | كل دواء قل رصيده الحالي عن الحد الادني | All drugs below minimum | FormReportsGeneral | `titanksastock` where `stock<minimum`; deficit, last restock |
| RPT-ST04 | كل الادوية التي لم ترد في المبيعات | Drugs never sold | FormReportsGeneral | Drug master minus sales; current stock, last purchase, days since sale |
| RPT-ST05 | كل الادوية التي وردت في المبيعات | Drugs in sales | FormReportsGeneral | Drugs appearing in sales; total sold, revenue, last sale |
| RPT-ST06 | بتتبع تغيير الرصيد عن صنف محدد | Track stock changes for a drug | FormDrugFlow | Date, opening, purchases, sales, returns, adjustments, closing; per drug + date range |

### 2.7 Drug / inventory reports (`reports_complete.md:403-469`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-D01 | الادوية منتهية الصلاحية | Expired Drugs | FormExpiredDrugs | Expiry date < today; drug, expiry, stock, batch, category, supplier |
| RPT-D02 | التقرير الشهري للادوية | Monthly Drug | FormDrugMonthly | Monthly sales qty/value, purchases, stock change, avg daily sales |
| RPT-D03 | ارصدة الادوية اخر الشهر | Stock at Month End | FormDrugStckAtMonths | Drug, month/year, stock qty, stock value at cost & at retail |
| RPT-D04 | حركة الدواء الشهرية | Monthly Drug Movement | FormDrugMoveMonthly | Drug, month, opening, purchased, sold, returns, adjusted, closing |
| RPT-D05 | اخر الادوية المعدلة يدويا | Last Manually Edited Drugs | FormLastEdited | **تاريخ التعديل, الصنف, التعديل, سعر البيع, خصم الشراء, قيمة التعديل, الفرع** |
| RPT-D06 | حركة الدواء | Drug History | FormDrugHistory | Drug, movement date/type, qty, value, balance after |
| RPT-D07 | حركة اخر الايام | Last Days Activity | FormDrugsLastDays | Day-by-day sales/purchases/net change |
| RPT-D08 | تقرير الادوية الشبيهة | Similar Drugs | FormSimilars | Drug, generic name, similar count, price comparison |
| RPT-D09 | تقرير اسعار الادوية | Drug Prices | FormDrugPrice | Current price, last purchase price, history, change % |
| RPT-D10 | تقرير تتبع تصحيح الارصدة تلقائيا | Automatic stock-correction tracking | FFFDrugrasidCorrect | Drug, old stock, correction, new stock, reason, date, employee (added v348+, `ui_strings_readable.txt:2074`) |

### 2.8 Employee / worker reports — تقارير العاملين (`reports_complete.md:471-510`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-A01 | تقارير العاملين | Employee Reports | FormAmilTakarir | Employee sales aggregation; invoices count, total, VAT, avg |
| RPT-A02 | تقرير وقت تسجيل الدخول للموظفين | Employee Login Time | FormAmilTakarir | Login/logout date-time, duration, status (added v352+, `ui_strings_readable.txt:1837`) |
| RPT-A03 | اجمالي ساعات الموظفين في الفترة | Total Employee Hours | FormAmilTakarir / FormHodour | Total hours, days worked, avg/day, overtime |
| RPT-A04 | تقارير تسليم الدرج بين الفترات | Shift Drawer Handover | FormTaslimReport | Employee, shift, opening, cash sales, card sales, returns, expenses, closing, variance (newer shift system v352+, `ui_strings_readable.txt:1841`) |
| RPT-A05 | تقرير الصلاحيات | Permissions Report | FormReportsGeneral | Employee, permission level, allowed functions; manager-only (`ui_strings_readable.txt:1788`) |
| RPT-A06 | سجل الانشطة | Activity Log | FormReportsGeneral | Timestamp, employee, action, screen, details (`TitanUserAction`) |

### 2.9 Financial / accounting reports — تقارير المحاسب (`reports_complete.md:512-593`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-F01 | حركة النقدية اليوم | Daily Cash Flow | FormMonyDetails | Time, tx type, in/out, running balance, description, employee |
| RPT-F02 | تقرير حساب راس المال | Capital Calculation | FormReportsGeneral / FormSafiarbah / ModCapital | Opening capital, investments, withdrawals, net profit, closing capital (see §7) |
| RPT-F03 | تقارير المحاسبية عامة | General Accounting | FormAccReports | Account, debit, credit, balance, period |
| RPT-F04 | الميزان | Balance Sheet / Trial Balance | FormMizan / FormMizanCreate | Account code/name, debit, credit, balance; grouped by Assets/Liabilities/Equity/Revenue/Expenses; also ميزان المراجعة + ميزان المراجعة تفصيلي (`ui_strings.json:6513-6514`) |
| RPT-F05 | تقرير خصومات المخازن | Store Discounts | FormStoreDiscount | `storediscount`; store, drug, discount type/value, effective date |
| RPT-F06 | تقرير المصروفات | Expenses | FormReportsGeneral | Expense type, amount, date, paid-to, method, notes |
| RPT-F07 | تقرير الضريبة المضافة الربع سنوي | Quarterly VAT | FormVat2 / ModVatReport | Period, sales (excl VAT), VAT on sales, purchases (excl VAT), VAT on purchases, net VAT payable @15%; ZATCA/Excel/PDF export |
| RPT-F08 | تقرير ضريبة القيمة المضافة لدول الخليج العربي | GCC VAT | FormVat | Period, sales, VAT, purchases, input VAT, net VAT, country (improved v352+, `ui_strings_readable.txt:2080`) |
| RPT-F09 | تقرير التعديل اليدوي | Manual Edit | FormReportsGeneral | **المستخدم الحالي, تاريخ التعديل, الصنف, التعديل, سعر البيع, خصم الشراء, قيمة التعديل, الفرع** |
| RPT-F10 | القيود اليدوية | Manual Daily Entries | FormDailyManual / FormDailyManual2 | Date, entry type, amount, description, employee; stored `daily-manual.phy` (`feature_account_closing.md:73,137`) |
| RPT-F11 | رفع القيود المحاسبية | Accounting Entries Upload | FormAccUploader | Entry date, account, debit, credit, description, status |

### 2.10 Delivery reports — تقارير التوصيل (`reports_complete.md:595-601`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-DEL01 | تقارير التوصيل | Delivery Reports | FormTawsil | Delivery date, customer, address, items, status, driver, amount |

### 2.11 Chain / series reports — تقارير السلسلة (`reports_complete.md:605-613`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-CH01 | تقارير السلسلة-الطريقة الحديثة | Chain Reports (Modern) | FormSilsila | `silsilaid` across all transactions; chain ID/name, total purchased, total sold, current stock, total value (`feature_transfers_logistics.md:529`); chain stock via FFFSilsilaStock |

### 2.12 Expiry reports (`reports_complete.md:615-628`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-EXP01 | مراقبة الصلاحيات | Expiry Control | FormExpiresControl | Drug, expiry date, days until expiry, stock, status OK/Warning/Expired |
| RPT-EXP02 | تفاصيل الصلاحيات | Expiry Details | FormExpireDetails | Expiry detail per batch |

### 2.13 Electronic-invoice reports (ZATCA / ETA) (`reports_complete.md:630-646`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-EI01 | حالة رفع الفواتير الالكترونية | E-Invoice Submission Status | Formdtts / FormVat2 / ModZatca2Wraber | ZATCA API responses; invoice UUID, submission date, status, response code, amount |
| RPT-EI02 | حالة ربط eta | ETA Egypt Link Status | FormEtaInfo | Document type, submission time, status, document ID |

### 2.14 Pharmacy operations — احصائيات مجملة (`reports_complete.md:648-692`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-OP01 | احصائيات مجملة للمبيعات/للمشتريات | Aggregate Statistics | FormReportsGeneral | Total sales, purchases, returns, net revenue, margin, items, unique customers |
| RPT-OP02 | اجمالي المبيعات والارباح | Total Sales & Profits | FormReportsGeneral / FFFOutputTakarir | Period, revenue, COGS, gross profit, profit %, VAT collected |
| RPT-OP03 | الاجماليات | Aggregates | FormReportsGeneral | اجمالي المبيعات, اجمالي الفاتورة, اجمالي مبيعات الادوية, اجمالي خصومات العملاء اليوم, اجمالي ضريبه المبيعات, اجمالي الربح في المبيعات, اجمالي مرتجع المبيعات, اجمالي مدفوعات المشتريات (`reports_complete.md:667-678`) |
| RPT-OP04 | ضريبة ق مضافة Total VAT | Total VAT | FormReportsGeneral | Period, gross sales, VAT amount, net sales, VAT rate |
| RPT-OP05 | حساب المبيعات المفقودة | Lost Sales Calculation | FormReportsGeneral | Drug, stockout date, estimated lost qty/revenue |

### 2.15 Other specialized reports (`reports_complete.md:694-719`)

| ID | Arabic | English | Form | Data source / key fields |
|---|---|---|---|---|
| RPT-SP01 | تقرير ربط مريض بوثفة طبية | Patient–Prescription Link | FormReportsGeneral | Patient, national ID, prescription date, doctor, drug list, status (`ui_strings_readable.txt:2100`) |
| RPT-SP02 | تقرير وقت تسجيل الدخول | Login Time (dup. of A02) | FormReportsGeneral | Employee, login/logout, total hours |
| RPT-SP03 | تتبع تعديل الفواتير | Invoice Edit Tracking | FormInvoiceTrackEditing | Invoice#, edit date, field changed, old/new value, employee |
| RPT-SP04 | تقرير اكسبير | Expiry Report (custom) | FormReportsGeneral | Drug, expiry date, batch, qty, status (`ui_strings_readable.txt:2096`) |

---

## 3. Report infrastructure

### 3.1 Report engine (FormReportsGeneral, 61 procs)
Central hub that binds category menu → report SQL → grid → printer. Data is pulled with SQL against the live tables and rendered to a grid, then passed to `ModPrint`. Report periods are Daily, Monthly, Quarterly, Yearly, or a custom from/to range (`reports.md:531`). Aggregation lists (قائمة تجميعات) sit at the top of the history screen (`ui_strings_readable.txt:2065`). Live SQL identifiers include the sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (idx 7423) used in SQL-concat loops in `FFFStartUp`/`FFFOutPut`; VAT tags `<masrofat-vat>` and `<drug-stock>` are live (`feature_notes.md:22`).

### 3.2 Report numbering
The app itself has no fixed numeric report IDs; the **RPT-xx** scheme below is the documentation convention used by this corpus. Prefix letters reflect the category: **S**ales, **P**urchases, **C**ustomer, **SUP**plier, **H**istory/close, **ST**ock/shortage, **D**rug/inventory, **A**mil (employee), **F**inance, **DEL**ivery, **CH**ain, **EXP**iry, **EI** e-invoice, **OP** operations, **SP** special (`reports_complete.md` throughout). Examples: `RPT-A04` shift drawer handover, `RPT-F01` cash flow, `RPT-ST01` shortages, `RPT-CH01` chain.

### 3.3 Report-launch paths
- Main menu: `Reporting > operation list > [Category] > [Specific report]` (`reports_complete.md:1269`)
- Quick access from the Sales screen (menu dropdown) and from Purchase screen (dropdown next to delete button) (`reports_complete.md:1271-1272`)
- Day close: financial summaries auto-generated; optional print of day data during close — "اضافة امكانية طباعة بيانات اليوم اثناء التقفيل ويجب تفعيلها اولا من شاشة اعدادات متقدمة" (idx 8944) (`feature_account_closing.md:77`)
- Pharmacy history aggregation lists: `الشاشة الرئيسية > قائمة تقارير > تقرير تاريخ الصيدلية > قائمة تجميعات` (`reports_complete.md:1273`)

### 3.4 Access control
- Sensitive reports (e.g. financial) gated by a special password — string `input report password 9******4` (`reports_complete.md:1263`)
- Employee permissions (`تقرير الصلاحيات`) control report access; the permissions report itself is manager-only (`reports_complete.md:1266`)

### 3.5 Report SQL patterns (`reports_complete.md:1069-1097`)
```sql
-- Daily sales
SELECT * FROM titanksasales WHERE datee >= [start] AND datee <= [end] ORDER BY datee DESC
-- Stock below minimum
SELECT drugname, stock, minimum, (minimum-stock) AS shortage FROM titanksastock WHERE stock < minimum
-- Sales by drug
SELECT drugname, SUM(quant), SUM(totalvalue) FROM titanksasales WHERE datee BETWEEN ... GROUP BY drugname
-- Customer debt
SELECT mobile, SUM(totalvalue - payed) AS debt FROM titanksasales WHERE creditdebit = 'credit' GROUP BY mobile
-- Pharmacy list
SELECT pharmacyname, adress FROM titanpharmalist GROUP BY pharmacyname, adress
-- Top drugs
SELECT * FROM titanksasales GROUP BY drugname ORDER BY COUNT(*) DESC
-- Supplier dues
SELECT name, SUM(debit-credit) AS dues FROM accounting GROUP BY name ORDER BY SUM(debit-credit) DESC
```

---

## 4. Printing

### 4.1 Print flow
1. Report form builds the recordset (SQL above) and shows it in a grid.
2. User picks print/export; `ModPrint` (70 procs) is the shared engine (`reports.md:393`).
3. Template selected by report type — invoice templates via `FormPrintSales` (17 procs, طباعة المبيعات); report page layout for tabular reports; thermal receipt for cash receipts.
4. Output device chosen per category from printer settings (report printer, A4 printer, receipt printer, barcode printer, branch printer).
5. Cash drawer opens on print/save when configured (فتح الدرج عند الحفظ / عند الطباعة).
6. Optional auto-print on save: "طباعة الفاتورة تلقائيا مع الحفظ" (`reports.md:312`).

### 4.2 Templates (`reports_complete.md:722-887`, `reports.md:116-158`)
- **Sales invoice** (فاتورة مبيعات): header (pharmacy name/address/phone/tax number/CR), invoice#, date, customer/phone, employee, payment type (cash/credit/card); items table (# | drug & dosage | qty | unit price | batch | expiry | disc | VAT | line total); footer subtotal→discount→after-discount→VAT 15%→grand total→paid→remaining→customer-debt status→barcode→writer.
- **Tax invoice variants**: فاتورة ضريبية, فاتورة ضريبية مرتجع (return), فاتورة ضريبية اجلة (credit), فاتورة ضريبية مبسطة (simplified), E-Invoice (ZATCA) (`reports.md:121-129`).
- **Transfer invoice** (فاتورة محولة), Fake-invoice test template (`reports.md:127-128`).
- **Receipts**: سند قبض (cash receipt, incl. amount/method/invoice#), سند صرف (payment voucher), سند صرف لمورد (supplier payment slip), إيصال التوصيل (delivery receipt) (`reports_complete.md:784-819`).
- **Barcode labels**: Zebra thermal; A4 sheet 6×24 (12×35mm) — `A4 6 Column * 24 Rows (12*35)` / `A4 (6*24)(12.3*35)`; split vs non-split (`Input 1 for non splitted label, 2 for splitted label`); shelf label (ملصق الرف, 3.8×1.2cm); storehouse barcode (باركود كمخزن); attendance barcode (باركود الحضور والانصراف); option "Do not print prices on the barcode label" (`reports_complete.md:821-857`).
- **Prescription / delivery note**: patient, doctor, national ID, items with dosage/duration, notes, QR/barcode (`reports_complete.md:870-887`).

### 4.3 Printer configuration (`reports_complete.md:891-967`)
`FormPrinterSettings` (31 procs) and branch twin `FormPrinterSettingFary` (28 procs) hold ~30 values: printers per purpose (طابعة التقارير / الباركود / الريسيت / الفواتير / A4), paper size (A4/A5/Letter/thermal), orientation (portrait/landscape), copies, margins (top/bottom/left/right), font, barcode width/height/columns/rows, sticker dimensions (3.8×1.2), branch printer, auto-print, cash-drawer options, printer path. `FffSelectPrinter` (2 procs) picks the active printer. Error handling: `Printer Error` / `(No Printer Installed)` / `No Printers`; falls back to default. Special: `RUNDLL32 PRINTUI.DLL,PrintUIEntry /e /n [printer]` and `*XPrinter*` SDK (`reports_complete.md:960-967`).

### 4.4 Export capabilities (`reports_complete.md:971-1023`, `reports.md:344-383`)
- **PDF**: `حفظ الي ملف بي دي اف`; report name + date + time.
- **Excel**: `حفظ الي ملف اكسيل` / `حفظ الفاتورة في صورة ملف اكسيل` → `مجلد ملفات الاكسيل`; configurable column separator `حرف الفصل بين الاعمدة في جدول الاكسيل`; confirmation `تم الحفظ في مجلد ملفات الاكسيل`.
- **CSV**: custom-export.csv, UTF-8, configurable delimiter.
- **Clipboard**: `تم النسخ الي الحافظة`.
- **HTML/WebView dashboard**: divs `divmoosh` (اخر فواتير المشتريات), `divsigil` (معلومات مبيعات الايام السابقة), `divthisday` (فواتير مبيعات اليوم), anchor nav المشتريات/مبيعات اليوم, CSS class `.jo` (`reports_complete.md:1000-1010`).
- **Data export paths**: `Labirdo\Titan-to-excel\`, `Labirdo\Titan3-Backup\Export\[Del\]`, `Files\Accounting\Vat-reports\`, `Files\Accounting\monthly\`, `C:\saturn\Zatca\computer-1\invoices\` (`reports.md:377-383`).
- **Export actions**: export all sales to Excel, export DB to Excel, export drug/prices/barcode change to file, export to sales/purchase file, export invoice to another pharmacy, export to drugeye, batch/merge files (`reports.md:356-373`).

---

## 5. Data tables (report sources)

Core tables (`reports_complete.md:1029-1046`, `reports.md:467-490`):

| Table | Purpose for reports |
|---|---|
| `titanksasales` | Sales invoices & line items — id, drugname, quant, price, disc, vat, totalvalue, datee, mobile, writer, creditdebit, invoiceid, tips, phar, payed (RPT-S01..S06, S13, C04, OP01..05) |
| `titanksastock` | Branch stock — drugname, stock, price, minimum, barcode, expire, silsilaid, classy, pharmacyid, costvalue (RPT-ST01..ST05, D01) |
| `titanstock` | Main drug master — drugname, stock, price, minimum, barcode, titanid, lastedit, pharmacyid (RPT-D02..D10) |
| `invoicedata` | Per-line invoice data (FormOotSum sales summary, FormPrintSales) (`schema_mapping.md:128,156`, `feature_sales_invoices.md:26`) |
| `farysales` | Per-branch ledger — father/son accounts, creditdebit (day-close, balances) (`feature_balances.md:137`) |
| `wzgard` | Stock ledger — used by FormDrugFlow, FormPrintSales, ModPrint (`schema_mapping.md:222`) |
| `wzcustomers` / `wzsuppliers` | Customer/supplier balances (RPT-C01, SUP01) |
| `wzmony` / `wzdaily` / `wzbank` | Money/daily/bank records (RPT-F01 cash flow, RPT-H01 history) |
| `titaninn` | Transfer records — fatid, itemsasstring, datee, source, silsilaid, target (transfers) |
| `titanneed` | Shortages/needs — drugname, quantity, status, date (RPT-ST) |
| `titanpharmalist` | Branch list — mobile, pharmacyname, adress |
| `usersourceupdate` / `TitanUserAction` | Edit/activity tracking (RPT-D05, A06, SP03, F09): drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee |
| `taronlineeg` | Online/Egypt transactions — mobile, grand, father, son, datee, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy |
| `storediscount` | Store discount rules — drugname, discount_type, discount_value (RPT-F05) |
| `wzdrugs` | Drug master (main DB) — drugname, barcode, price, stock, Generic, Units |
| `wzphar` | Pharmacy data — pharname, pharmacyid |
| `wzaccfreetree` | Chart of accounts tree (RPT-F03/F04/F10) — `master` column used in FormDailyManual2 (`feature_balances.md:178`) |
| `nilsen2` | Nielsen analytics data |
| `remotecontrol` | Remote control — id, passedfunctions |
| `orders` | Order tracking — orderid, orderdate, status |
| `.phy` data files | `Files\DBI\Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `workperiod.phy`, `delivery.phy`, `oot3.phy`, `daily-manual.phy`, `daily-manual-2.phy`, `Files\StockNow`, `Files\Archive\Input\`, `Files\Archive\Output\` (`reports.md:478-490`) |

Accounting structure (chart-of-accounts tree, `reports_complete.md:1048-1065`): حقوق ملكية (Equity) → ارباح وخسائر / جاري الشريك / راس المال; خصوم (Liabilities) → ثابتة / متداولة → ضريبة / موردين; اصول (Assets) → ثابتة / متداولة → عملاء / خزينة.

---

## 6. Workflow — generating & printing a report

1. **Choose category** from قائمة تقارير (18 categories; `reports_complete.md:23-45`).
2. **Set filters**: date range (from/to), branch, employee, customer, supplier, category, profit threshold, insurance company — filters vary per report (`reports_complete.md` per-report rows).
3. **Query**: engine (FormReportsGeneral / FFFOutputTakarir / FFFInputTakarir / FormOutPuttakarirSpeed / FormAmilTakarir) runs SQL against the source tables and fills a grid.
4. **Aggregate**: report-specific summaries (totals, counts, VAT, discounts, profit) computed; grouped headers/footers with subtotals (`reports_complete.md:866-868`).
5. **Print / export**: `ModPrint` renders the template to the configured printer (report/A4/receipt), or exports PDF/Excel/CSV/clipboard/HTML.
6. **Day-close flow**: FFFDayEnd aggregates the day → prints تقرير تقفيل اليوم (RPT-H02); monthly close (تقفيل الشهر, RPT-H03) archives `\Files\Archive\monthy\` and carries opening balances (`feature_account_closing.md:81,193-194`).
7. **Audit trail**: edits logged (RPT-F09 manual edit, RPT-SP03 invoice tracking, RPT-D10 rasid correction); activity log (RPT-A06) records employee actions.

---

## 7. Profit analysis — تحليل الأرباح

FormSafiarbah (تحليل الأرباح, 3 procs) is the dedicated profit/capital analysis screen (`ui_strings.json:958`, `modules_gap_2.md:279-298`). It connects `FormMohasaby`, `FormDariba`, `FormMoamla`, and `ModCapital`.

- **Capital calculation (RPT-F02)**: Opening Capital + Investments − Withdrawals + Net Profit = Closing Capital (`feature_balances.md:66,104`).
- **Capital accounts** (idx 10734–10736): حقوق ملكية.راس المال, جاري الشريك, ارباح وخسائر; راس المال (idx 11520/10857); ارباح وخسائر (idx 8709) (`feature_balances.md:105-107`).
- **Statistics screen**: احصائيات راس المال / احصائيات راس المال ونظرة عامة علي الصيدلية (idx 8350/8354); اجمالي الميزانية (`modules_gap_2.md:300-304`). "لعدم تشغيلها الآن اضغط علي زر... لعرض شاشة صافي الارباح" (`ui_strings.json:2485`).
- **Daily profit inputs** (day-close feed, `ui_strings.json:7125`): كاش, كاش يدوي, شبكة, شبكة يدوي, عجز زيادة, محسوب المبيعات, صافي اليوم كاش, صافي اليوم شبكة, **تكلفة مبيعات اليوم, ربح اليوم**, شكك اليوم, خصومات اليوم, مشتريات اليوم, مصروفات اليوم, حركة مالية, الضريبة في المبيعات/المشتريات/المصروفات اليوم.
- **Overall statistics** (`ui_strings.json:7124`): التاريخ, الشركات حتي الان, اجل العملاء حتي الان, شراء غير شامل الضريبة, جمهور حتي الان شامل الضريبة, الكاش حتي الان, البنوك حتي الان, راس المال.
- **Profit aggregates**: اجمالي الربح, اجمالي الربح في المبيعات, اجمالي نسبة الربح للصيدلي اليوم, اجمالي ض.ق.مضافة, اجمالي خصومات العملاء اليوم (`ui_strings.json:1856-1892`). Sales-profit rule: "اجمالي مبيعات الفترة هو 2000 جنيه وليس 1400 جنيه لان المنصرفات لا تحتسب" (`ui_strings.json:1886`).
- **P&L / balance-sheet linkage**: profit (ارباح وخسائر) lives under Equity and feeds الميزان (RPT-F04) and ميزان المراجعة (trial balance); data feeding financial statements: "البيانات المغذية للقوائم المالية وميزان المراجعة" (`ui_strings.json:3508`). Cost of sales (تكلفة المبيعات) and net profit (الربح الصافي) are report columns (`reports_complete.md:1180-1181`).
- **Capital reports**: تقارير حساب راس المال (RPT-F02) under category 15; also تقارير الحسابات Capitals, Annual Net Profits (الارباح الصافية السنوية) (`reports.md:38-41`, `ui_strings.json:8419`).

---

## 8. Business rules / edge cases

1. **RPT-S02 returns**: `creditdebit` flag distinguishes returns; return totals and items counted separately (`reports_complete.md:80`).
2. **RPT-S05 margin rule**: period sales = 2000 LE not 1400 LE because "المنصرفات لا تحتسب" (expensed/pulled stock not counted in sales) (`ui_strings.json:1886`).
3. **RPT-ST01 shortages**: shortage = `minimum − stock`; group by category and chain; sort by shortage desc; per-branch stock via `titanksastock` (`reports_complete.md:351-367`).
4. **RPT-A04 drawer handover**: drawer-current formula — current drawer minus drawer-at-period-start plus any cash removed during the period ("اجمالي الدرج حاليا مطروح منه الدرج عن بداية الفترة ومضافا اليه اي نقدية خرجت من الدرج اثناء الفترة") (`ui_strings.json:1855`); cash leaving the drawer should be recorded externally or transferred immediately ("اي نقدية تخرج عن طريق الدرج خلال اليوم فيفضل تسجيلها خارجيا او ترحيل قيمتها فورا من الخزينة الي..." idx 10494, `FormSilsila` pcode).
5. **VAT 15%**: VAT reports apply the 15% rate; quarterly report is ZATCA-exportable; `<masrofat-vat>` tag live in the expense pipeline (`feature_balances.md:147`).
6. **Credit-limit rule**: invoice cannot save if customer's remaining balance exceeds credit limit — message strings at `ui_strings.json:1867`.
7. **Print during day close** must be enabled in advanced settings first (idx 8944) (`feature_account_closing.md:77`).
8. **Employee filters**: reports honor employee permissions; the permissions report (RPT-A05) is manager-only.
9. **Invoice edit tracking**: edits post an audit row (TitanUserAction) feeding RPT-F09/RPT-SP03/RPT-D10.
10. **Cash/net split**: purchases & sales reports distinguish نقدا / شبكة / اجل via `creditdebit` + `payed` (RPT-P04/P05/P06).
11. **v348/v352 additions** (`reports_complete.md:1279-1297`): unlinked-gov-invoices, manual-payments-at-close, invoice-notes, supplier→customer sales, insurance-customer filter, branch receipt/barcode printing, day-close printing, A4 item-per-customer, new shift system, login-time tracking, GCC VAT improvements, Zebra/non-split/shelf/A4-6×24 barcode printing.

---

*Consolidated from the TITAN.W1 extraction corpus. Cite as: `reports_complete.md` (catalog, templates, printer config, export, tables, columns), `reports.md` (form mapping, print formats, export paths), `feature_balances.md` (profit/capital, chart of accounts), `feature_account_closing.md` (day/month close), `ui_strings.json` (Arabic labels idx 1840–1909, 7124–7125).*