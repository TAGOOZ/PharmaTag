# TITAN.W1 Pharmacy Application — Complete Report & Printing Specifications

> Extracted from VB6 P-Code disassembly of Phye.exe (TITAN.W1)
> Project: 237 Forms | 336 Objects | 6192 Procedures | 26970 String Constants
> Key modules: ModPrint (70 procs), FormReportsGeneral (61 procs), FormPrinterSettings (31 procs), FormPrinterSettingFary (28 procs), FFFOutputTakarir (16 procs), FormAmilTakarir (23 procs), FormOutPuttakarirSpeed (9 procs)

---

## TABLE OF CONTENTS

1. [Report Categories Overview](#1-report-categories-overview)
2. [Complete Report Catalog](#2-complete-report-catalog)
3. [Print Templates](#3-print-templates)
4. [Printer Configuration](#4-printer-configuration)
5. [Export Capabilities](#5-export-capabilities)
6. [Database Tables & Data Sources](#6-database-tables--data-sources)
7. [Column Specifications](#7-column-specifications)

---

## 1. REPORT CATEGORIES OVERVIEW

TITAN organizes reports into **18 major categories**, accessible from the main menu under "تقارير" (Reports):

| # | Category (Arabic) | Category (English) | Form/Module |
|---|---|---|---|
| 1 | تقارير المبيعات | Sales Reports | FFFOutputTakarir |
| 2 | تقارير المشتريات | Purchase Reports | FFFInputTakarir |
| 3 | تقارير العملاء | Customer Reports | FormReportsGeneral |
| 4 | تقارير اجمالي المبيعات والارباح | Total Sales & Profit Reports | FFFOutputTakarir |
| 5 | تقارير حجم المبيعات | Sales Volume Reports | FormOutPuttakarirSpeed |
| 6 | تقارير حجم مبيعات الادوية | Drug Sales Volume Reports | FormOutPuttakarirSpeed |
| 7 | تقارير تاريخ الصيدلية | Pharmacy History Reports | FormReportsGeneral |
| 8 | تقارير النواقص | Shortage Reports | FormReportsGeneral |
| 9 | تقارير النواقص للاطلاع | Shortage Review Reports | FormReportsGeneral |
| 10 | تقارير المحاسب | Accountant Reports | FormReportsGeneral |
| 11 | تقارير المحاسبية عامة | General Accounting Reports | FormAccReports |
| 12 | تقارير تسليم الفترات | Shift Handover Reports | FormTaslimReport |
| 13 | تقارير التوصيل | Delivery Reports | FormTawsil |
| 14 | تقارير السلسلة | Chain Reports (Modern) | FormSilsila |
| 15 | تقارير حساب راس المال | Capital Calculation Reports | FormReportsGeneral |
| 16 | تقارير متعددة | Multiple/Misc Reports | FormReportsGeneral |
| 17 | تقارير مستحقات الشركات | Company Dues Reports | FormReportsGeneral |
| 18 | تقارير مبيعات | Sales Reports (Detailed) | FormAmilTakarir |

---

## 2. COMPLETE REPORT CATALOG

### 2.1 SALES REPORTS (تقرير المبيعات)

#### RPT-S01: Daily Sales Report — تقرير مبيعات اليوم
- **Form**: FFFOutputTakarir
- **Arabic Title**: فواتير مبيعات اليوم
- **English Title**: Daily Sales Invoices
- **Data Source**: `titanksasales` table, filtered by `datee = TODAY`
- **Columns**:
  | Column Header (Arabic) | Column Header (English) | Field |
  |---|---|---|
  | رقم الفاتورة | Invoice Number | invoiceid |
  | التاريخ | Date | datee |
  | الصنف | Drug Name | drugname |
  | الكمية | Quantity | quant |
  | السعر | Price | price |
  | الخصم | Discount | disc |
  | الضريبة | VAT | vat |
  | الاجمالي | Total | totalvalue |
  | العميل | Customer | mobile |
  | الموظف | Employee/Writer | writer |
- **Grouping**: By invoice number
- **Sorting**: By date descending
- **Filters**: Date range, employee, customer
- **Summary**: Total sales, total VAT, total discount, total items count
- **Export**: Print, Excel, PDF

#### RPT-S02: Sales Returns Report — تقرير ادوية مرتجعة
- **Form**: FFFOutputTakarir
- **Arabic Title**: تقرير ادوية مرتجعة
- **English Title**: Drug Returns Report
- **Data Source**: `titanksasales` where `creditdebit` indicates return
- **Columns**: Invoice #, Date, Drug Name, Quantity, Price, Return Value, Customer, Branch
- **Filters**: Date range, customer, drug name
- **Summary**: Total returned value, returned items count

#### RPT-S03: Sales by Drug Report — تقرير مبيعات الادوية
- **Form**: FormAmilTakarir
- **Arabic Title**: تقرير مبيعات الادوية
- **English Title**: Drug Sales Report
- **Data Source**: `titanksasales` aggregated by `drugname`
- **Columns**:
  | Column Header (Arabic) | Column Header (English) | Field |
  |---|---|---|
  | الصنف | Drug Name | drugname |
  | الكمية المباعة | Quantity Sold | SUM(quant) |
  | اجمالي المبيعات | Total Sales | SUM(totalvalue) |
  | متوسط السعر | Average Price | AVG(price) |
  | اعلي سعر | Highest Price | MAX(price) |
  | ادني سعر | Lowest Price | MIN(price) |
- **Grouping**: By drug name, by drug category (`classy`)
- **Sorting**: By total sales descending
- **Filters**: Date range, category, supplier
- **Summary**: Grand total sales, average discount percentage

#### RPT-S04: Employee Sales Report — فواتير مبيعات موظف
- **Form**: FormAmilTakarir
- **Arabic Title**: فواتير مبيعات موظف
- **English Title**: Employee Sales Invoices
- **Data Source**: `titanksasales` grouped by `writer`
- **Columns**: Employee Name, Invoice Count, Total Sales, Total VAT, Average Invoice Value, Items Count
- **Grouping**: By employee (`writer`)
- **Sorting**: By total sales descending
- **Filters**: Date range, specific employee

#### RPT-S05: Sales Volume Report — تقارير حجم المبيعات
- **Form**: FormOutPuttakarirSpeed
- **Arabic Title**: اجمالي مبيعات الفترة
- **English Title**: Period Sales Total
- **Data Source**: Aggregated sales data
- **Columns**: Period, Total Sales, Total Cost, Gross Profit, VAT Amount, Net Sales
- **Filters**: Date range (from/to)
- **Summary**: Total sales, total cost, gross profit margin, VAT total

#### RPT-S06: Drug Sales Volume Report — تقارير حجم مبيعات الادوية
- **Form**: FormOutPuttakarirSpeed
- **Arabic Title**: تقارير حجم مبيعات الادوية
- **English Title**: Drug Sales Volume Reports
- **Data Source**: Sales aggregated by drug
- **Columns**: Drug Name, Quantity Sold, Total Value, Cost, Profit, Profit Margin %
- **Grouping**: By drug category, by supplier
- **Filters**: Date range, category, profit threshold

#### RPT-S07: Best 100 Drugs Report — افضل 100 دواء
- **Form**: FormBest100
- **Arabic Title**: افضل 100 دواء
- **English Title**: Top 100 Drugs
- **Data Source**: Top 100 drugs by sales volume
- **Columns**: Rank, Drug Name, Quantity Sold, Total Revenue, Last Sale Date

#### RPT-S08: Sales During Day Report — تقارير مبيعات اثناء اليوم
- **Form**: FormAmilTakarir
- **Arabic Title**: تقارير مبيعات اثناء اليوم
- **English Title**: Intraday Sales Reports
- **Data Source**: Current day sales with real-time updates
- **Columns**: Time, Invoice #, Drug, Qty, Price, Total, Running Total

#### RPT-S09: Insurance Company Sales —Printing for insurance companies
- **Form**: FormAmilTakarir
- **Arabic Title**: طباعة للشركات التأمين
- **English Title**: Printing for Insurance Companies
- **Data Source**: Sales filtered by insurance customer type
- **Columns**: Insurance Company, Patient Name, Drug, Qty, Price, Insurance Share, Patient Share

#### RPT-S10: Unlinked Invoices Report — تقرير الفواتير غير المربوطة
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير الفواتير غير المربوطه مع الهيئات الحكوميه
- **English Title**: Unlinked Government Entity Invoices
- **Data Source**: Invoices not linked to government entities
- **Columns**: Invoice #, Date, Customer, Amount, Status, Link Status

#### RPT-S11: Manual Payments Aggregation — تقرير تجميع المدفوع يدويا
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير لتجميع المدفوع يدويا عند تقفيل اليوم
- **English Title**: Manual Payments Aggregation at Day Close
- **Data Source**: Manual payment entries during day close
- **Columns**: Date, Amount, Payment Type, Employee, Notes

#### RPT-S12: Invoice Notes Report — تقرير ملاحظات الفواتير
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير لعرض ملاحظات الفوتير المسجلة يدويا
- **English Title**: Manual Invoice Notes Report
- **Data Source**: Invoice notes/comments field
- **Columns**: Invoice #, Date, Notes, Employee, Drug Name

#### RPT-S13: Supplier Drug Sales Report — تقرير مبيعات اصناف مورد محدد لعميل محدد
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير مبيعات اصناف مورد محدد لعميل محدد
- **English Title**: Sales of Specific Supplier's Items to Specific Customer
- **Data Source**: Sales filtered by supplier and customer
- **Columns**: Supplier, Customer, Drug, Qty, Price, Total, Discount, Date

#### RPT-S14: Customer Withdrawals Report — تقرير مسحوبات العميل
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير مسحوبات العميل
- **English Title**: Customer Withdrawals Report
- **Data Source**: Customer withdrawal transactions
- **Columns**: Customer Name, Withdrawal Amount, Date, Remaining Balance, Branch

#### RPT-S15: Prescription Report (Wasfaty) — تقرير وصفتي
- **Form**: FormWasfaty
- **Arabic Title**: تقرير وصفتي عن الفترة ادناه
- **English Title**: Wasfaty Prescription Report for Below Period
- **Data Source**: Prescription data from Wasfaty system
- **Columns**: Prescription Date, Patient, Doctor, Drug List, Status
- **Filters**: Date range

---

### 2.2 PURCHASE REPORTS (تقرير المشتريات)

#### RPT-P01: Purchases Report — تقارير المشتريات
- **Form**: FFFInputTakarir
- **Arabic Title**: تقارير المشتريات
- **English Title**: Purchase Reports
- **Data Source**: Purchase invoice tables
- **Columns**:
  | Column Header (Arabic) | Column Header (English) |
  |---|---|
  | رقم الفاتورة | Invoice Number |
  | التاريخ | Date |
  | المورد | Supplier |
  | الصنف | Drug Name |
  | الكمية | Quantity |
  | السعر | Unit Price |
  | الخصم | Discount |
  | الاجمالي | Total |
  | تاريخ الصلاحية | Expiry Date |
  | رقم التشغيلة | Batch Number |
- **Grouping**: By supplier, by date
- **Sorting**: By date descending, by total descending
- **Filters**: Date range, supplier, drug name
- **Summary**: Total purchases, total discount, total items count

#### RPT-P02: Purchases by Selling Price — مشتريات بسعر البيع
- **Form**: FFFInputTakarir
- **Arabic Title**: مشتريات بسعر البيع
- **English Title**: Purchases at Selling Price
- **Data Source**: Purchase data recalculated at selling price
- **Columns**: Drug, Qty Bought, Cost Price, Selling Price, Margin, Total Cost, Total Selling Value

#### RPT-P03: Outstanding Purchases — فات المشتريات
- **Form**: FFFInputTakarir
- **Arabic Title**: فات المشتريات (الاجل)
- **English Title**: Outstanding/Credit Purchases
- **Data Source**: Unpaid purchase invoices
- **Columns**: Supplier, Invoice #, Date, Amount Paid, Amount Remaining, Due Date

#### RPT-P04: Cash Purchases — مسدد نقدا مشتريات
- **Form**: FFFInputTakarir
- **Arabic Title**: مسدد نقدا مشتريات
- **English Title**: Cash-Paid Purchases
- **Data Source**: Purchases where `payed > 0` and `creditdebit = cash`

#### RPT-P05: Network-Paid Purchases — مسدد شبكة مشتريات
- **Form**: FFFInputTakarir
- **Arabic Title**: مسدد شبكة مشتريات
- **English Title**: Network/Network-Paid Purchases

#### RPT-P06: Credit Purchases — اجل المشتريات
- **Form**: FFFInputTakarir
- **Arabic Title**: اجل المشتريات
- **English Title**: Credit Purchases

#### RPT-P07: Purchases Import Report — تقرير الواردات والمصروفات
- **Form**: FFFInputTakarir
- **Arabic Title**: تقرير الواردات و المصروفات
- **English Title**: Imports and Expenses Report
- **Columns**: Date, Import Type, Drug, Supplier, Qty, Value, Tax, Notes

---

### 2.3 CUSTOMER REPORTS (تقرير العملاء)

#### RPT-C01: Customer Reports — تقارير العملاء
- **Form**: FormReportsGeneral
- **Arabic Title**: تقارير العملاء
- **English Title**: Customers' Reports
- **Data Source**: Customer data + sales aggregation
- **Columns**:
  ```
  اسم العميل    مديونية العميل    الفرع
  (Customer Name    Customer Debt    Branch)
  ```
- **Sorting**: By debt amount descending
- **Filters**: Branch, debt threshold, customer type

#### RPT-C02: Customer Points Statistics — احصائيات نقاط العملاء
- **Form**: FormReportsGeneral
- **Arabic Title**: احصائيات نقاط العملاء
- **English Title**: Customer Points Statistics
- **Columns**: Customer Name, Total Points, Points Redeemed, Points Balance, Total Purchases, Date Range

#### RPT-C03: Insurance Company Customers — عملاء شركة التأمين
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير عملاء شركة التأمين
- **English Title**: Insurance Company Customers Report
- **Data Source**: Customers linked to insurance companies
- **Columns**: Insurance Company, Customer Name, Policy #, Total Claims, Remaining Coverage
- **Filter**: By insurance company name

#### RPT-C04: Customer Sales Detail — تقرير بالاصناف لعميل
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير بالاصناف لعميل
- **English Title**: Item Detail Report for Customer
- **Columns**: Customer, Drug Name, Qty Purchased, Total Value, Date Range, Last Purchase

---

### 2.4 SUPPLIER REPORTS (تقرير الموردين)

#### RPT-SUP01: Supplier Report — تقرير الموردين
- **Form**: FormReportsGeneral
- **Arabic Title**: تقارير الموردين
- **Data Source**: Supplier purchase aggregation
- **Columns**:
  ```
  اسم المورد    مستحقات المورد  الفرع
  (Supplier Name    Supplier Dues    Branch)
  ```
- **Sorting**: By dues amount descending

#### RPT-SUP02: Supplier Dues Report — مستحقات الشركات
- **Form**: FormReportsGeneral
- **Arabic Title**: تقارير مستحقات الشركات
- **English Title**: Company Dues Reports
- **Columns**: Company, Total Purchases, Total Paid, Remaining Due, Last Payment Date

---

### 2.5 PHARMACY HISTORY REPORTS (تقرير تاريخ الصيدلية)

#### RPT-H01: Pharmacy History — تقرير تاريخ الصيدلية
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير تاريخ الصيدلية
- **English Title**: Pharmacy History Report
- **Columns**:
  ```
  التاريخ      القيمة     الضريبة      الوصف       البيان       الخزينة     الفرع
  (Date      Value     Tax      Description       Notes       Cashier     Branch)
  ```
- **Grouping**: By date, by branch
- **Filters**: Date range, branch
- **Summary**: Daily total, monthly total, yearly total

#### RPT-H02: Day Close Report — تقرير تقفيل اليوم
- **Form**: FFFDayEnd
- **Arabic Title**: تقفيل اليوم
- **English Title**: Day Close Report
- **Data Source**: End-of-day aggregation
- **Columns**: Date, Opening Balance, Total Sales, Total Returns, Total Purchases, Expenses, Cash Received, Card Received, Closing Balance, Difference

#### RPT-H03: Month Close Report — تقرير تقفيل الشهر
- **Form**: FFFDayEnd
- **Arabic Title**: تقفيل الشهر
- **English Title**: Month Close Report
- **Columns**: Month, Total Sales, Total Purchases, Total Expenses, Profit, Cash Flow, Outstanding Amounts

---

### 2.6 SHORTAGE/STOCK REPORTS (تقرير النواقص)

#### RPT-ST01: Shortages Report — تقرير النواقص
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير النواقص
- **English Title**: Shortages Report
- **Data Source**: Drugs where `stock < minimum`
- **Columns**:
  | Column Header (Arabic) | Column Header (English) | Field |
  |---|---|---|
  | الصنف | Drug Name | drugname |
  | الرصيد الحالي | Current Stock | stock |
  | الحد الادني | Minimum Level | minimum |
  | النقص | Shortage | minimum - stock |
  | اخر سعر شراء | Last Purchase Price | price |
  | التصنيف | Category | classy |
  | السلسلة | Chain ID | silsilaid |
- **Grouping**: By category, by chain
- **Sorting**: By shortage amount descending

#### RPT-ST02: Manual Registration Shortages — كشف النواقص بنظام التسجيل اليدوي
- **Form**: FormReportsGeneral
- **Arabic Title**: كشف النواقص بنظام التسجيل اليدوي
- **English Title**: Manual Registration Shortages Check
- **Data Source**: Manually registered shortage entries
- **Columns**: Drug, Registered Stock, Actual Stock, Difference, Date, Employee

#### RPT-ST03: Stock Below Minimum — كل دواء قل رصيده الحالي عن الحد الادني
- **Form**: FormReportsGeneral
- **Arabic Title**: كل دواء قل رصيده الحالي عن الحد الادني
- **English Title**: All Drugs Below Minimum Stock
- **Columns**: Drug Name, Current Stock, Minimum Level, Deficit, Last Restock Date

#### RPT-ST04: Drugs Never Sold — كل الادوية التي لم ترد في المبيعات
- **Form**: FormReportsGeneral
- **Arabic Title**: كل الادوية التي لم ترد في المبيعات
- **English Title**: All Drugs Not Appearing in Sales
- **Columns**: Drug Name, Current Stock, Last Purchase Date, Category, Days Since Last Sale

#### RPT-ST05: Drugs in Sales — كل الادوية التي وردت في المبيعات
- **Form**: FormReportsGeneral
- **Arabic Title**: كل الادوية التي وردت في المبيعات
- **English Title**: All Drugs Appearing in Sales
- **Columns**: Drug Name, Total Sold, Total Revenue, Last Sale Date

#### RPT-ST06: Drug Movement Track — تتبع تغيير الرصيد
- **Form**: FormDrugFlow
- **Arabic Title**: بتتبع تغيير الرصيد عن صنف محدد في ايام مختلفة
- **English Title**: Track Stock Changes for Specific Drug on Different Days
- **Columns**: Date, Opening Stock, Purchases, Sales, Returns, Adjustments, Closing Stock
- **Filters**: Drug name, date range

---

### 2.7 DRUG/INVENTORY REPORTS

#### RPT-D01: Expired Drugs Report — تقرير الادوية منتهية الصلاحية
- **Form**: FormExpiredDrugs
- **Arabic Title**: الادوية منتهية الصلاحية
- **English Title**: Expired Drugs Report
- **Columns**: Drug Name, Expiry Date, Stock, Batch #, Category, Supplier

#### RPT-D02: Drug Monthly Report — تقرير شهري للادوية
- **Form**: FormDrugMonthly
- **Arabic Title**: التقرير الشهري للادوية
- **English Title**: Monthly Drug Report
- **Columns**: Drug, Monthly Sales Qty, Monthly Sales Value, Monthly Purchases, Stock Change, Avg Daily Sales

#### RPT-D03: Drug Stock at Month End — ارصدة الادوية اخر الشهر
- **Form**: FormDrugStckAtMonths
- **Arabic Title**: ارصدة الادوية اخر الشهر
- **English Title**: Drug Stock at Month End
- **Columns**: Drug, Month/Year, Stock Quantity, Stock Value (Cost), Stock Value (Retail)

#### RPT-D04: Drug Movement Monthly — حركة الدواء الشهرية
- **Form**: FormDrugMoveMonthly
- **Arabic Title**: حركة الدواء الشهرية
- **English Title**: Monthly Drug Movement
- **Columns**: Drug, Month, Opening, Purchased, Sold, Returns, Adjusted, Closing

#### RPT-D05: Last Edited Drugs — اخر الادوية المعدلة يدويا
- **Form**: FormLastEdited
- **Arabic Title**: اخر الادوية المعدلة يدويا
- **English Title**: Last Manually Edited Drugs
- **Columns**:
  ```
  تاريخ التعديل    الصنف    التعديل     سعر البيع     خصم الشراء     قيمة التعديل      الفرع
  (Edit Date    Drug    Edit Type     Selling Price     Purchase Discount     Edit Value      Branch)
  ```

#### RPT-D06: Drug History — حركة الدواء
- **Form**: FormDrugHistory
- **Arabic Title**: حركة الدواء
- **English Title**: Drug Movement History
- **Columns**: Drug Name, Movement Date, Movement Type, Quantity, Value, Balance After

#### RPT-D07: Last Days Drug Activity — حركة اخر الايام
- **Form**: FormDrugsLastDays
- **Arabic Title**: حركة اخر الايام
- **English Title**: Last Days Drug Activity
- **Columns**: Drug, Day-by-Day Sales, Day-by-Day Purchases, Net Change

#### RPT-D08: Similar Drugs Report — تقرير الادوية الشبيهة
- **Form**: FormSimilars
- **Arabic Title**: ادوية مشابهة
- **English Title**: Similar Drugs Report
- **Columns**: Drug Name, Generic Name, Similar Drugs Count, Price Comparison

#### RPT-D09: Drug Price Report — تقرير اسعار الادوية
- **Form**: FormDrugPrice
- **Arabic Title**: تقرير اسعار الادوية
- **English Title**: Drug Price Report
- **Columns**: Drug Name, Current Price, Last Purchase Price, Price History, Price Change %

#### RPT-D10: Drug Rasid Correction — تقرير تصحيح الارصدة
- **Form**: FFFDrugrasidCorrect
- **Arabic Title**: تقرير تتبع تصحيح الارصدة تلقائيا
- **English Title**: Automatic Stock Correction Tracking Report
- **Columns**: Drug, Old Stock, Correction, New Stock, Reason, Date, Employee

---

### 2.8 EMPLOYEE/WORKER REPORTS (تقرير العمال)

#### RPT-A01: Employee Reports — تقارير العاملين
- **Form**: FormAmilTakarir
- **Arabic Title**: تقارير العاملين
- **English Title**: Employee Reports
- **Data Source**: Employee sales/activity aggregation
- **Columns**: Employee Name, Invoices Count, Total Sales, Total VAT, Average Sale, Period

#### RPT-A02: Employee Attendance — تقرير وقت تسجيل الدخول للموظفين
- **Form**: FormAmilTakarir
- **Arabic Title**: تقرير وقت تسجيل الدخول للموظفين
- **English Title**: Employee Login Time Report
- **Columns**: Employee Name, Login Date, Login Time, Logout Time, Duration, Status

#### RPT-A03: Total Employee Hours — اجمالي ساعات الموظفين
- **Form**: FormAmilTakarir
- **Arabic Title**: اجمالي ساعات الموظفين في الفترة
- **English Title**: Total Employee Hours in Period
- **Columns**: Employee Name, Total Hours, Days Worked, Average Hours/Day, Overtime

#### RPT-A04: Employee Cash Settlement — تقارير تسليم الدرج
- **Form**: FormTaslimReport
- **Arabic Title**: تقارير تسليم الدرج بين الفترات
- **English Title**: Shift Drawer Handover Reports
- **Columns**: Employee, Shift, Opening Amount, Sales (Cash), Sales (Card), Returns, Expenses, Closing Amount, Variance

#### RPT-A05: Employee Permissions Report — تقرير الصلاحيات
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير الصلاحيات
- **English Title**: Permissions Report
- **Columns**: Employee Name, Permission Level, Allowed Functions, Last Modified

#### RPT-A06: Employee Activity Log — سجل الانشطة
- **Form**: FormReportsGeneral
- **Arabic Title**: سجل الانشطة
- **English Title**: Activity Log
- **Columns**: Timestamp, Employee, Action, Screen, Details

---

### 2.9 FINANCIAL/ACCOUNTING REPORTS

#### RPT-F01: Cash Flow Report — حركة النقدية اليوم
- **Form**: FormMonyDetails
- **Arabic Title**: حركة النقدية اليوم
- **English Title**: Daily Cash Flow
- **Columns**: Time, Transaction Type, In Amount, Out Amount, Running Balance, Description, Employee

#### RPT-F02: Capital Calculation Report — تقرير حساب راس المال
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير حساب راس المال
- **English Title**: Capital Calculation Report
- **Columns**: Opening Capital, Investments, Withdrawals, Net Profit, Closing Capital

#### RPT-F03: General Accounting Reports — تقارير المحاسبية عامة
- **Form**: FormAccReports
- **Arabic Title**: تقارير المحاسبية عامة
- **English Title**: General Accounting Reports
- **Columns**: Account, Debit, Credit, Balance, Period

#### RPT-F04: Mizan (Balance Sheet) — الميزان
- **Form**: FormMizan
- **Arabic Title**: الميزان
- **English Title**: Balance Sheet / Mizan
- **Columns**: Account Code, Account Name, Debit, Credit, Balance
- **Grouping**: By account category (Assets, Liabilities, Equity, Revenue, Expenses)

#### RPT-F05: Store Discount Report — تقرير خصومات المخازن
- **Form**: FormStoreDiscount
- **Arabic Title**: تقرير خصومات المخازن
- **English Title**: Store/warehouse Discounts Report
- **Columns**: Store, Drug, Discount Type, Discount Value, Effective Date

#### RPT-F06: Expenses Report — تقرير المصروفات
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير المصروفات
- **English Title**: Expenses Report
- **Columns**: Expense Type, Amount, Date, Paid To, Payment Method, Notes

#### RPT-F07: VAT Report (Quarterly) — تقرير الضريبة المضافة الربع سنوي
- **Form**: FormVat2
- **Arabic Title**: تقرير الضريبة المضافة الربع سنوي
- **English Title**: Quarterly VAT Report
- **Module**: ModVatReport
- **Data Source**: Sales + Purchases VAT data
- **Columns**:
  ```
  Period, Total Sales (excl VAT), VAT on Sales, Total Purchases (excl VAT),
  VAT on Purchases, Net VAT Payable, VAT Rate (15%)
  ```
- **Filters**: Quarter/Year, branch
- **Export**: ZATCA format, Excel, PDF

#### RPT-F08: VAT Report (Gulf States) — تقرير ضريبة القيمة المضافة لدول الخليج
- **Form**: FormVat
- **Arabic Title**: تقرير ضريبة القيمة المضافة لدول الخليج العربي
- **English Title**: GCC VAT Report
- **Columns**: Period, Total Sales, VAT Amount, Total Purchases, Input VAT, Net VAT, Country

#### RPT-F09: Manual Edit Report — تقرير التعديل اليدوي
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير التعديل اليدوي
- **English Title**: Manual Edit Report
- **Columns**:
  ```
  المستخدم الحالي    تاريخ التعديل    الصنف    التعديل     سعر البيع     خصم الشراء     قيمة التعديل      الفرع
  (Current User    Edit Date    Drug    Edit Type     Selling Price     Purchase Discount     Edit Value      Branch)
  ```

#### RPT-F10: Daily Manual Entry — القيود اليدوية اليومية
- **Form**: FormDailyManual
- **Arabic Title**: القيود اليدوية
- **English Title**: Manual Daily Entries
- **Columns**: Date, Entry Type, Amount, Description, Employee

#### RPT-F11: Accounting Entries Upload — رفع القيود المحاسبية
- **Form**: FormAccUploader
- **Arabic Title**: رفع القيود المحاسبية
- **English Title**: Accounting Entries Upload
- **Columns**: Entry Date, Account, Debit, Credit, Description, Status

---

### 2.10 DELIVERY REPORTS (تقرير التوصيل)

#### RPT-DEL01: Delivery Reports — تقارير التوصيل
- **Form**: FormTawsil
- **Arabic Title**: تقارير التوصيل
- **English Title**: Delivery Reports
- **Columns**: Delivery Date, Customer, Address, Items, Status, Driver, Amount

---

### 2.11 CHAIN/SERIES REPORTS

#### RPT-CH01: Chain Reports — تقارير السلسلة الطريقة الحديثة
- **Form**: FormSilsila
- **Arabic Title**: تقارير السلسلة-الطريقة الحديثة
- **English Title**: Chain Reports (Modern Way)
- **Data Source**: `silsilaid` field across all transactions
- **Columns**: Chain ID, Chain Name, Total Purchased, Total Sold, Current Stock, Total Value

---

### 2.12 EXPIRY REPORTS

#### RPT-EXP01: Expiry Control — مراقبة الصلاحيات
- **Form**: FormExpiresControl
- **Arabic Title**: مراقبة الصلاحيات
- **English Title**: Expiry Control
- **Columns**: Drug, Expiry Date, Days Until Expiry, Stock, Status (OK/Warning/Expired)

#### RPT-EXP02: Expired Drug Details — تفاصيل الصلاحيات
- **Form**: FormExpireDetails
- **Arabic Title**: تفاصيل الصلاحيات
- **English Title**: Expiry Details

---

### 2.13 ELECTRONIC INVOICE REPORTS (ZATCA/ETA)

#### RPT-EI01: ZATCA Submission Status
- **Form**: Formdtts / FormVat2
- **Arabic Title**: حالة رفع الفواتير الالكترونية
- **English Title**: E-Invoice Submission Status
- **Data Source**: ZATCA API responses
- **Columns**: Invoice UUID, Submission Date, Status, Response Code, Amount

#### RPT-EI02: ETA Egypt Submission Status
- **Form**: FormEtaInfo
- **Arabic Title**: حالة ربط_eta
- **English Title**: ETA Egypt Link Status
- **Columns**: Document Type, Submission Time, Status, Document ID

---

### 2.14 PHARMACY OPERATIONS REPORTS

#### RPT-OP01: All Pharmacy Operations Summary — احصائيات مجملة
- **Form**: FormReportsGeneral
- **Arabic Title**: احصائيات مجملة للمبيعات / احصائيات مجملة للمشتريات
- **English Title**: Aggregate Sales/Purchase Statistics
- **Columns**: Total Sales, Total Purchases, Total Returns, Net Revenue, Profit Margin, Items Count, Unique Customers

#### RPT-OP02: Total Sales & Profits — اجمالي المبيعات والارباح
- **Form**: FormReportsGeneral
- **Arabic Title**: اجمالي المبيعات والارباح
- **English Title**: Total Sales & Profits
- **Columns**: Period, Sales Revenue, Cost of Goods Sold, Gross Profit, Profit %, VAT Collected

#### RPT-OP03: Total Sales, Purchases, Returns — الاجماليات
- **Form**: FormReportsGeneral
- **Arabic Title**: الاجماليات
- **English Title**: Aggregates
- **Data from strings**:
  ```
  اجمالي المبيعات = Total Sales
  اجمالي الفاتورة = Invoice Total
  اجمالي قيمة الفاتورة = Total Invoice Value
  اجمالي المبيعات الادوية = Total Drug Sales
  اجمالي خصومات العملاء اليوم = Today's Customer Discounts
  اجمالي ضريبه المبيعات = Total Sales Tax
  اجمالي الربح في المبيعات = Total Sales Profit
  اجمالي مبيعات فترتك = Your Period Total Sales
  اجمالي مرتجع المبيعات = Total Sales Returns
  اجمالي مدفوعات المشتريات = Total Purchase Payments
  ```

#### RPT-OP04: Total VAT from Sales — اجمالي ضريبة القيمة المضافة
- **Form**: FormReportsGeneral
- **Arabic Title**: ضريبة ق مضافة Total VAT
- **English Title**: Total VAT from Value Added Tax
- **Columns**: Period, Gross Sales, VAT Amount, Net Sales, VAT Rate

#### RPT-OP05: Lost Sales Calculation — حساب المبيعات المفقودة
- **Form**: FormReportsGeneral
- **Arabic Title**: حساب المبيعات المفقودة
- **English Title**: Lost Sales Calculation
- **Columns**: Drug, Stockout Date, Estimated Lost Qty, Estimated Lost Revenue

---

### 2.15 OTHER SPECIALIZED REPORTS

#### RPT-SP01: Patient Prescription Link — تقرير ربط مريض بوصفة طبية
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير ربط مريض بوثفة طبية
- **English Title**: Patient-Prescription Link Report
- **Columns**: Patient Name, National ID, Prescription Date, Doctor, Drug List, Status

#### RPT-SP02: User Login Time — تقرير وقت تسجيل الدخول
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير وقت تسجيل الدخول للموظفين
- **English Title**: Employee Login Time Report
- **Columns**: Employee, Login Date, Login Time, Logout Time, Total Hours

#### RPT-SP03: Invoice Editing Track — تتبع تعديل الفواتير
- **Form**: FormInvoiceTrackEditing
- **Arabic Title**: تتبع تعديل الفواتير
- **English Title**: Invoice Edit Tracking
- **Columns**: Invoice #, Edit Date, Field Changed, Old Value, New Value, Employee

#### RPT-SP04: Expiry Report (Custom) — تقرير اكسبير
- **Form**: FormReportsGeneral
- **Arabic Title**: تقرير اكسبير
- **English Title**: Expiry Report
- **Columns**: Drug, Expiry Date, Batch #, Qty, Status

---

## 3. PRINT TEMPLATES

### 3.1 INVOICE LAYOUT (Sales Invoice)

**Template**: Standard A4/A5 Sales Invoice

```
┌─────────────────────────────────────────────────────────┐
│                      HEADER                             │
│  Pharmacy Name (اسم الصيدلية)                            │
│  Address (العنوان)                                      │
│  Phone (الهاتف) | Tax Number (رقم التسجيل الضريبي)      │
│  Commercial Registration (السجل التجاري)                 │
│                                                         │
│  Invoice #: __________    Date: __________              │
│  Customer: __________     Phone: __________             │
│  Employee: __________                                   │
│  Payment Type: □ Cash  □ Credit  □ Card                 │
├─────────────────────────────────────────────────────────┤
│                      ITEMS                              │
│  # │ Drug Name │ Qty │ Unit Price │ Disc │ VAT │ Total │
│  1 │           │     │           │      │     │       │
│  2 │           │     │           │      │     │       │
│  ...                                                    │
├─────────────────────────────────────────────────────────┤
│                    FOOTER/TOTALS                        │
│  Subtotal (اجمالي قبل الخصم):              __________  │
│  Discount (خصم):                          __________  │
│  After Discount (اجمالي بعد الخصم):        __________  │
│  VAT 15% (ضريبة 15%):                    __________  │
│  Total (الاجمالي):                        __________  │
│  Paid (المدفوع):                          __________  │
│  Remaining (المتبقي):                     __________  │
│  Customer Credit Limit Status:                        │
│                                                         │
│  [Barcode]                                             │
│  Barcode: __________                                   │
│  Writer: __________                                    │
└─────────────────────────────────────────────────────────┘
```

**Invoice Columns (all variants)**:
- Row number (#)
- Drug Name (الصنف / الصنف والجرعة)
- Quantity (الكمية)
- Unit Price (سعر الوحدة)
- Batch Number (رقم التشغيلة)
- Expiry Date (تاريخ الصلاحية)
- Discount (الخصم)
- VAT (الضريبة)
- Line Total (الاجمالي)

**Footer Fields**:
- Subtotal before discount (اجمالي قبل الخصم)
- Total discount (اجمالي الخصم)
- Subtotal after discount (جملة بعد الخصم)
- Total VAT (اجمالي الضريبة)
- Grand Total (اجمالي الفاتورة / الاجمالي الكلي)
- Paid amount (المدفوع / قبض)
- Remaining amount (المتبقي / للمزيد)
- Customer debt status (مديونية العميل)

### 3.2 RECEIPT LAYOUT (Cash Receipt / سند قبض)

```
┌───────────────────────────────────┐
│         CASH RECEIPT              │
│         سند قبض                   │
│                                   │
│  Receipt #: _____ Date: _____    │
│  Customer: _____                 │
│  Amount: _____                   │
│  Payment Method: Cash/Card       │
│  Invoice #: _____                │
│  Employee: _____                 │
│  Notes: _____                    │
│                                   │
│  [Barcode]                       │
│  Signature: ____________         │
└───────────────────────────────────┘
```

### 3.3 DISBURSEMENT RECEIPT (سند صرف)

```
┌───────────────────────────────────┐
│      DISBURSEMENT RECEIPT         │
│      سند صرف                     │
│                                   │
│  سند صرف لمورد [Supplier Name]   │
│  Receipt #: _____ Date: _____    │
│  Supplier: _____                 │
│  Amount: _____                   │
│  Payment Method: _____           │
│  Employee: _____                 │
│  Notes: _____                    │
└───────────────────────────────────┘
```

### 3.4 BARCODE LABEL LAYOUTS

#### 3.4.1 Standard Barcode Label (Zebra Printer)
- **Printer Type**: Barcode label Printer (Zebra-compatible)
- **Label Sizes**: Configurable (see settings)
- **Layout**:
```
┌─────────────────────────┐
│  Drug Name (Arabic)     │
│  Drug Name (English)    │
│                         │
│  |||||||||||||||||||||  │
│  Barcode: 1234567890   │
│                         │
│  Price: XX.XX           │
│  Exp: MM/YYYY           │
│  Batch: XXXXX           │
└─────────────────────────┘
```
- **Settings String**: `Input 1 for non splitted label, 2 for splitted label`

#### 3.4.2 A4 Barcode Sheet
- **Printer Type**: A4 Paper Printer
- **Layout**: 6 Columns × 24 Rows (12×35mm per label)
- **Label String**: `A4 6 Column * 24 Rows (12*35)`
- **Alt String**: `A4 (6*24)(12.3*35)`
- **Config**: `Barcode label settings` / `Barcode printing`
- **Option**: `Do not print prices on the barcode label`

#### 3.4.3 Shelf Label (ملصق الرف)
- **Printer Type**: Shelf label printer
- **Action**: `Print shelf label`
- **Layout**: Drug name, price, barcode

#### 3.4.4 Storehouse Barcode (باركود كمخزن)
- **Action**: `Print as a storehouse`
- **Layout**: Drug name, category, stock location

### 3.5 REPORT PAGE LAYOUT

- **Orientation**: Portrait (default), Landscape (configurable)
- **Paper Sizes**: A4 (default), A5, Letter
- **Margins**: Configurable via FormPrinterSettings
- **Font**: System default (Arabic-compatible font)
- **Header**: Pharmacy name, logo, report title, date range
- **Footer**: Page number, print date, "Generated by TITAN"
- **Group Headers**: Category/section breaks with subtotals
- **Group Footers**: Group totals, counts

### 3.6 PRESCRIPTION/DELIVERY NOTE LAYOUT

```
┌───────────────────────────────────┐
│  Prescription / وصفة طبية         │
│                                   │
│  Patient: _____ Date: _____      │
│  Doctor: _____                   │
│  National ID: _____              │
│                                   │
│  # │ Drug │ Dosage │ Duration    │
│  1 │      │        │             │
│  2 │      │        │             │
│                                   │
│  Notes: _____                    │
│  [QR Code / Barcode]             │
└───────────────────────────────────┘
```

---

## 4. PRINTER CONFIGURATION

### 4.1 Printer Settings Form (FormPrinterSettings — MDIForm, 31 procs)

**Printer Types Configured** (from strings):

| Setting Key (Arabic) | Setting Key (English) | Purpose |
|---|---|---|
| طابعة التقارير | Report Printer | Main report printer |
| طابعة الباركود | Barcode Label Printer | Barcode label printer |
| طابعة الريسيت | Cash/Receipt Printer | Thermal receipt printer |
| طابعة الفواتير | Invoice Printer | Invoice printer |
| طابعة A4 | A4 Paper Printer | A4 document printer |

**Printer Settings Fields** (from FormPrinterSettings initialization):

```
Setting Key = "" (initialized empty, loaded from INI/registry)
```

The FormPrinterSettings stores approximately **30+ printer configuration values** including:

| # | Setting Name (from Arabic pcode strings) | English Equivalent | Type |
|---|---|---|---|
| 1 | طابعة التقارير | Report Printer Name | String |
| 2 | طابعة الريسيت | Receipt Printer Name | String |
| 3 | طابعة الباركود | Barcode Printer Name | String |
| 4 | طابعة الفواتير | Invoice Printer Name | String |
| 5 | ورقة التقارير | Report Paper Size | Integer |
| 6 | اتجاه الطباعة | Print Orientation | Integer (1=Portrait, 2=Landscape) |
| 7 | عدد النسخ | Number of Copies | Integer |
| 8 | هوامش علوية | Top Margin | Integer (twips) |
| 9 | هوامش سفلية | Bottom Margin | Integer (twips) |
| 10 | هوامش يسرى | Left Margin | Integer (twips) |
| 11 | هوامش يمنى | Right Margin | Integer (twips) |
| 12 | حجم الخط | Font Size | Integer |
| 13 | نوع الخط | Font Name | String |
| 14 | عرض الباركود | Barcode Width | Integer |
| 15 | ارتفاع الباركود | Barcode Height | Integer |
| 16 | حجم ورقة الباركود | Barcode Paper Size | Integer |
| 17 | عدد اعمدة الباركود | Barcode Columns | Integer |
| 18 | عدد صفوف الباركود | Barcode Rows | Integer |
| 19 | عرض الاستيكر | Sticker Width | Double (e.g., 3.8) |
| 20 | ارتفاع الاستيكر | Sticker Height | Double (e.g., 1.2) |
| 21 | طابعة فرعية | Branch Printer | String |
| 22 | طباعة تلقائية | Auto-print on save | Boolean |
| 23 | فتح الدرج | Open cash drawer | Boolean |
| 24 | فتح الدرج عند الحفظ | Open drawer on save | Boolean |
| 25 | فتح الدرج عند الطباعة | Open drawer on print | Boolean |
| 26 | اسم المسار | Path name | String |
| 27 | مسار الطابعات | Printer path | String |

### 4.2 Branch Printer Settings (FormPrinterSettingFary — MDIForm, 28 procs)

Identical structure to FormPrinterSettings but for **branch/subsidiary devices**. Stores the same ~30 configuration values for remote/branch printers.

**Key Features**:
- Separate printer configuration per branch
- Supports remote printing from main pharmacy to branches
- Same field structure as main FormPrinterSettings

### 4.3 Printer Selection (FffSelectPrinter — Form, 2 procs)

Simple printer selection dialog:
- Lists available Windows printers
- Allows user to select active printer
- Stores selection in settings

### 4.4 Printer Error Handling
- **Error String**: `Printer Error` / `(No Printer Installed)` / `No Printers`
- **Recovery**: Falls back to default printer, displays error dialog

### 4.5 Special Printer Commands
```
RUNDLL32 PRINTUI.DLL,PrintUIEntry /e /n [printer_name]  — Open printer properties
*XPrinter*  — XPrinter SDK integration (receipt printer)
```

---

## 5. EXPORT CAPABILITIES

### 5.1 PDF Export
- **Action**: `حفظ الي ملف بي دي اف` (Save to PDF file)
- **File Path**: Application directory or user-selected
- **File Naming**: Report name + date + time
- **Settings**: Configurable via save dialog

### 5.2 Excel Export
- **Action**: `حفظ الي ملف اكسيل` (Save to Excel file)
- **Action**: `حفظ الفاتورة في صورة ملف اكسيل` (Save invoice as Excel)
- **File Path**: `مجلد ملفات الاكسيل` (Excel files folder)
- **Settings**:
  - `حرف الفصل بين الاعمدة في جدول الاكسيل` — CSV delimiter character
  - `تم الحفظ في مجلد ملفات الاكسيل` — Saved to Excel folder
  - `تم حفظ الجدول في صورة ملف اكسيل في مجلد ملفات الاكسيل` — Table saved as Excel
- **Access Path**: Main menu → File → Excel Files Folder

### 5.3 CSV Export
- **Format**: Comma/semicolon-separated values
- **Delimiter**: Configurable (comma, semicolon, tab)
- **Encoding**: UTF-8 (from string `"utf-8"`)

### 5.4 Clipboard Export
- **Action**: `تم النسخ الي الحافظة` (Copied to clipboard)
- **Purpose**: Copy report data for pasting into other applications

### 5.5 HTML/WebView Export
- **Format**: HTML with embedded CSS
- **Strings Found**:
  ```
  <div id='divmoosh'>اخر فواتير المشتريات</div>
  <div id='divsigil' style='background-color: #abeb34;'>معلومات مبيعات الايام السابقة</div>
  <div id='divthisday' >فواتير مبيعات اليوم</div>
  <div>الادوية المباعة هذا اليوم</div>
  <div>قيمة كل ادوية الصيدلية بسعر الجمهور = </div>
  <td class='jo'><a href='#divmoosh'>المشتريات</a></td>
  <td class='jo'><a href='#divthisday'>مبيعات اليوم</a></td>
  ```
- **CSS**: `.jo {text-align: center; font-weight:bolder;padding-top:12px;padding-bottom:12px;}`

### 5.6 File Naming Conventions
- **Reports**: `ReportName_YYYYMMDD_HHMMSS.ext`
- **Invoices**: `Invoice_YYYYMMDD_ID.ext`
- **Backups**: `TitanBackup_YYYYMMDD.ext`
- **Excel**: Stored in `مجلد ملفات الاكسيل` (Excel Files Folder)

### 5.7 File Paths
- **Application Root**: Program installation directory
- **Excel Folder**: Subfolder for Excel exports
- **Backup Folder**: Subfolder for backup files
- **Log Folder**: Application log files
- **Archive Folder**: Archived invoices/folders

---

## 6. DATABASE TABLES & DATA SOURCES

### 6.1 Core Tables

| Table Name | Purpose | Key Fields |
|---|---|---|
| `titanksasales` | Sales invoices & line items | id, drugname, quant, price, disc, totalvalue, datee, mobile, writer, creditdebit, invoiceid, tips, phar, payed, vat |
| `titanksastock` | Drug stock/ inventory | id, drugname, stock, price, minimum, barcode, expire, silsilaid, classy, pharmacyid, costvalue |
| `titanstock` | Main drug master | drugname, stock, price, minimum, barcode, titanid, lastedit, pharmacyid |
| `titaninn` | Transfer/transfer records | fatid, itemsasstring, datee, source, silsilaid, target |
| `titanneed` | Shortages/needs list | drugname, quantity, status, date |
| `titanpharmalist` | Pharmacy branch list | mobile, pharmacyname, adress |
| `usersourceupdate` | User updates tracking | drugname, update_date |
| `taronlineeg` | Online/Egypt transactions | mobile, grand, father, son, datee, datetimee, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy |
| `storediscount` | Store discount rules | drugname, discount_type, discount_value |
| `wzdrugs` | Drug data (main DB) | drugname, barcode, price, stock, Generic, Units, etc. |
| `wzphar` | Pharmacy data | pharname, pharmacyid |
| `nilsen2` | Nilsen/analytics data | Various |
| `remotecontrol` | Remote control entries | id, passedfunctions |
| `orders` | Order tracking | orderid, orderdate, status, datee |

### 6.2 Accounting Tables (from Mizan/Accounting module)

| Table Path | Account Category |
|---|---|
| حقوق ملكية | Equity |
| حقوق ملكية.ارباح وخسائر | Equity → P&L |
| حقوق ملكية.جاري الشريك | Equity → Partner Current |
| حقوق ملكية.راس المال | Equity → Capital |
| خصوم | Liabilities |
| خصوم.خصوم ثابتة | Liabilities → Fixed |
| خصوم.خصوم متداولة | Liabilities → Current |
| خصوم.خصوم متداولة.ضريبة | Liabilities → Current → Tax |
| خصوم.خصوم متداولة.موردين | Liabilities → Current → Suppliers |
| اصول | Assets |
| اصول.ثابتة | Assets → Fixed |
| اصول.متداولة | Assets → Current |
| اصول.متداولة.عملاء | Assets → Current → Customers |
| اصول.متداولة.خزينة | Assets → Current → Cash |

### 6.3 SQL Patterns Found

**Report Query Patterns**:
```sql
-- Sales by date
SELECT * FROM titanksasales WHERE datee >= [start] AND datee <= [end] ORDER BY Datee DESC

-- Stock below minimum
SELECT drugname, stock, minimum, (minimum-stock) as shortage FROM titanksastock WHERE stock < minimum

-- Sales by drug
SELECT drugname, SUM(quant), SUM(totalvalue) FROM titanksasales WHERE datee BETWEEN ... GROUP BY drugname

-- Customer debt
SELECT mobile, SUM(totalvalue - payed) as debt FROM titanksasales WHERE creditdebit = 'credit' GROUP BY mobile

-- Drug search
SELECT * FROM wzdrugs WHERE Barcode1 = N'...' OR Barcode2 = N'...' OR NameArabic LIKE N'%...%'

-- Pharmacy group
SELECT pharmacyname, adress FROM titanpharmalist GROUP BY pharmacyname, adress

-- Store stock
SELECT storename FROM titanksastock GROUP BY storename

-- Order by count
SELECT * FROM titanksasales GROUP BY drugname ORDER BY COUNT(*) DESC

-- Supplier dues
SELECT name, SUM(debit-credit) as dues FROM accounting GROUP BY name ORDER BY SUM(debit-credit) DESC
```

---

## 7. COLUMN SPECIFICATIONS

### 7.1 Universal Column Headers (Arabic → English)

| Arabic Header | English Header | Data Type | Width (chars) |
|---|---|---|---|
| رقم الفاتورة | Invoice # | Long | 8 |
| التاريخ | Date | Date | 12 |
| الوقت | Time | Time | 8 |
| الصنف | Drug Name | String(100) | 40 |
| الكمية | Quantity | Decimal | 8 |
| سعر الوحدة | Unit Price | Currency | 12 |
| السعر | Price | Currency | 12 |
| الخصم | Discount | Currency | 12 |
| الضريبة | VAT | Currency | 12 |
| الاجمالي | Total | Currency | 15 |
| المورد | Supplier | String(50) | 30 |
| العميل | Customer | String(50) | 30 |
| الموظف | Employee | String(30) | 20 |
| الرصيد | Balance/Stock | Decimal | 10 |
| الحد الادني | Minimum Level | Decimal | 10 |
| تاريخ الصلاحية | Expiry Date | Date | 12 |
| رقم التشغيلة | Batch Number | String(20) | 15 |
| الباركود | Barcode | String(16) | 16 |
| التصنيف | Category | String(35) | 20 |
| السلسلة | Chain ID | String(15) | 10 |
| الفرع | Branch | String(50) | 20 |
| ملاحظات | Notes | String(200) | 40 |
| المدفوع | Paid Amount | Currency | 12 |
| المتبقي | Remaining | Currency | 12 |
| مديونية العميل | Customer Debt | Currency | 15 |
| مستحقات المورد | Supplier Dues | Currency | 15 |
| نوع الفاتورة | Invoice Type | String(20) | 15 |
| حالة الباركود | Barcode Status | String(20) | 15 |
| الصنف والجرعة | Drug & Dosage | String(120) | 40 |
| الكمية المباعة | Quantity Sold | Decimal | 10 |
| اجمالي المبيعات | Total Sales | Currency | 15 |
| متوسط السعر | Average Price | Currency | 12 |
| اعلي سعر | Highest Price | Currency | 12 |
| ادني سعر | Lowest Price | Currency | 12 |
| الربح | Profit | Currency | 12 |
| نسبة الربح | Profit % | Percent | 8 |
| اسم الصيدلية | Pharmacy Name | String(50) | 30 |
| عنوان الصيدلية | Pharmacy Address | String(100) | 40 |
| تلفون الصيدلية | Pharmacy Phone | String(15) | 15 |
| رقم التسجيل الضريبي | Tax Registration # | String(20) | 20 |
| السجل التجاري | Commercial Registration | String(30) | 25 |
| الشركة | Company | String(50) | 25 |
| المندوب | Sales Rep | String(30) | 20 |
| الوحدات | Units | Integer | 6 |
| الوصف | Description | String(200) | 40 |
| البيان | Statement | String(100) | 30 |
| الخزينة | Cashier | String(30) | 15 |
| القائم بالحدث | Action By | String(30) | 20 |
| نوع التعديل | Edit Type | String(30) | 15 |
| قيمة التعديل | Edit Value | Currency | 12 |
| سعر البيع | Selling Price | Currency | 12 |
| خصم الشراء | Purchase Discount | Currency | 12 |
| المبلغ | Amount | Currency | 15 |
| النسبة | Percentage | Percent | 8 |
| الحساب | Account | String(50) | 30 |
| مدين | Debit | Currency | 15 |
| دائن | Credit | Currency | 15 |
| الرصيد الختامي | Closing Balance | Currency | 15 |
| الفاتورة | Invoice | String(30) | 20 |
| رقم العميل | Customer # | String(15) | 10 |
| الهاتف | Phone | String(15) | 15 |
| العنوان | Address | String(100) | 30 |
| الاجل | Credit Term | String(20) | 10 |
| الحد الائتمان | Credit Limit | Currency | 12 |
| اسم العميل | Customer Name | String(50) | 30 |
| اسم المورد | Supplier Name | String(50) | 30 |
| جملة الحساب | Account Total | Currency | 15 |
| جملة الخصم | Total Discount | Currency | 12 |
| جملة قبل الخصم | Subtotal Before Discount | Currency | 15 |
| جملة بعد الخصم | Subtotal After Discount | Currency | 15 |
| جمهور | Public/Retail Price | Currency | 12 |
| جملة | Wholesale | Currency | 12 |
| التكلفة | Cost | Currency | 12 |
| تكلفة المبيعات | Cost of Sales | Currency | 15 |
| الربح الصافي | Net Profit | Currency | 15 |
| عدد الاصناف | Items Count | Integer | 8 |
| عدد الفواتير | Invoices Count | Integer | 8 |
| عدد العملاء | Customers Count | Integer | 8 |
| رقم التسلسلي | Serial Number | Long | 10 |
| رقم البلوك | Block Number | String(10) | 8 |
| رقم الرف | Shelf Number | String(10) | 8 |
| ترتيب | Order/Rank | Integer | 6 |
| المجموعة | Group | String(30) | 20 |

### 7.2 ZATCA E-Invoice Columns (JSON Fields)

```json
{
  "header": {
    "dateTimeIssued": "",
    "receiptNumber": "",
    "uuid": "",
    "type": "",
    "typeVersion": "",
    "currency": "",
    "exchangeRate": 0
  },
  "seller": {
    "name": "",
    "vatNumber": "",
    "crNumber": "",
    "activityCode": "",
    "branchAddress": {
      "country": "",
      "governate": "",
      "regionCity": "",
      "street": "",
      "buildingNumber": "",
      "postalCode": ""
    }
  },
  "buyer": {
    "name": "",
    "vatNumber": "",
    "id": ""
  },
  "documentType": {
    "receiptType": "",
    "documentUseReason": ""
  },
  "itemData": [{
    "itemCode": "",
    "internalCode": "",
    "description": "",
    "quantity": 0,
    "unitType": "",
    "unitPrice": 0,
    "currency": "",
    "taxableItems": [{
      "taxType": "",
      "amount": 0,
      "rate": 0,
      "subType": ""
    }],
    "commercialDiscountData": [],
    "itemDiscountData": []
  }],
  "taxTotals": [{
    "taxType": "",
    "amount": 0
  }],
  "totalSales": 0,
  "totalCommercialDiscount": 0,
  "totalItemsDiscount": 0,
  "netAmount": 0,
  "totalAmount": 0,
  "paymentMethod": "",
  "extraReceiptDiscountData": []
}
```

---

## 8. REPORT ACCESS CONTROL

### Password Protection
- **String**: `input report password 9******4`
- Certain sensitive reports require a special password
- Employee-level permissions control report access
- `تقرير الصلاحيات` (Permissions Report) — only for manager

### Report Launch Paths
- **From Main Menu**: `Reporting > operation list > [Report Category] > [Specific Report]`
- **From Sales Screen**: Quick access via menu dropdown
- **From Purchase Screen**: Via dropdown menu next to delete button
- **From Day Close**: Financial summary reports auto-generated
- **From Pharmacy History**: `الشاشة الرئيسية > قائمة تقارير > تقرير تاريخ الصيدلية > قائمة تجميعات`

---

## 9. VERSION/CHANGE LOG ENTRIES (Report-Related)

| Version | Change |
|---|---|
| v348+ | Added report for tracking automatic stock corrections from main menu > Multiple reports |
| v348+ | Added filter command in insurance company customer report |
| v348+ | Added report for unlinked government entity invoices |
| v348+ | Added report for manual payments aggregation at day close |
| v348+ | Added report for invoice notes display |
| v348+ | Added report for specific supplier's items to specific customer |
| v348+ | Added printing capability for receipt and barcode from branch devices |
| v348+ | Added ability to print daily data during day close (must enable from advanced settings) |
| v352+ | Enhanced printing for A4 item report per customer |
| v352+ | Enhanced shift system; report accessible from drawer handover screen |
| v352+ | Added employee login time tracking report |
| v352+ | GCC VAT report improvements |
| v352+ | Zebra barcode printing support |
| v352+ | Non-splitted barcode label printing support |
| v352+ | Shelf label printing |
| v352+ | A4 paper barcode printing (6×24 grid) |

---

*Document generated from TITAN.W1 VB6 P-Code decompilation. Some fields may have been initialized with empty values at runtime and populated from INI files, registry, or database.*
