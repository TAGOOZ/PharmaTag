# TITAN.W1 Pharmacy Application - Reports, Print Templates & Structure Analysis

## Overview
- **Application**: TITAN.W1 (Phye.exe) - VB6 Pharmacy Management System
- **Forms**: 237 | **Objects**: 336 | **Procedures**: 6192
- **Language**: Arabic (RTL) with English labels
- **Integration**: ZATCA (Saudi Arabia e-invoicing), SFDA DTTS drug tracking

---

## 1. REPORT TYPES (All Discovered)

### A. Daily Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Daily Sales Summary | فواتير مبيعات اليوم | FormDailyQuiod, FormReportsGeneral |
| Daily Expenses | Expenses-daily restrictions | FFFDayEnd |
| Daily Manual | Daily Manual | FormDailyManual, FormDailyManual2 |
| Daily Sales During Day | Sales reports during the day | FormReportsGeneral |
| Daily Max | Reload_Daily_Max | ModStorage |
| Day End Report | End of day closing | FFFDayEnd (25 procs) |
| Work Period Report | فترة العمل | FFFDayEnd |

### B. Monthly Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Monthly Drug Movement | حركة الادوية الشهرية | FormDrugMoveMonthly |
| Monthly Stock | رصيد ا月末 | FormDrugStckAtMonths |
| Monthly Data | البيانات الشهرية | FormReadMonthlyData |
| Monthly Closing | الاغلاق الشهري | FormReportsGeneral |
| Monthly Accounting | المحاسبة الشهرية | Files\Accounting\monthly\ |
| Monthly Backup | النسخ الاحتياطي الشهري | ModBackupMonthly |
| VAT Monthly Report | تقرير ضريبة القيمة المضافة الشهري | FormVat2, ModVatReport |

### C. Yearly/Period Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Capital Account Reports | تقارير الحسابات Capitals | FormReportsGeneral |
| Capital Reports | تقارير راس المال | FormReportsGeneral |
| Total Sales & Profit | اجمالي المبيعات والارباح | FormReportsGeneral |
| Annual Net Profits | الارباح الصافية السنوية | FormReportsGeneral |
| Quarterly VAT Report | تقرير ضريبي ربع سنوي | FormReportsGeneral |

### D. Sales Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Sales Reports | تقارير المبيعات | FormReportsGeneral |
| Sales Volume Reports | تقارير حجم المبيعات | FormReportsGeneral |
| Customer Reports | تقارير العملاء | FormReportsGeneral |
| Delivery Report | تقرير التوصيل | FormTawsil |
| Prescription Reports | تقارير الوصفات | FormWasfaty (27 procs) |
| Sales by Employee | فواتير مبيعات موظف | FormReportsGeneral |
| Shift Sales Inquiry | الاستعلام عن مبيعات الوردية | FormReportsGeneral |

### E. Purchase Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Purchase Reports | تقارير المشتريات | FormReportsGeneral |
| Supplier Claims | تقارير مستحقات الموردين | FormReportsGeneral |
| Purchase Invoices Period | فواتير المشتريات عن فترة | FormReportsGeneral |
| Supplier Sales Period | مبيعات اصناف مورد محدد عن فترة | FormReportsGeneral |

### F. Stock/Inventory Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Stock Details | تفاصيل المخزون | FormDrugsDetails (51 procs) |
| Stock at Months | ارصدةشهور | FormDrugStckAtMonths |
| Expired Drugs | الادوية المنتهية | FormExpiredDrugs (21 procs) |
| Expire Details | تفاصيل الصلاحية | FormExpireDetails |
| Inventory Correction | تصحيح الجرد | FormReportsGeneral |
| Inventory Integrity | سلامة الجرد | FormReportsGeneral |
| Stock is Zero | الصفر من المخزون | FormReportsGeneral |
| Drug Flow | حركة الدواء | FormDrugFlow (32 procs) |
| Monthly Drug Follow-up | متابعة حركة الصنف شهريا | FormDrugMonthly |

### G. Financial Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Cash Delivery Reports | تقارير تسليم النقد بين الفترات | FormReportsGeneral |
| Balance Chronology | تسلسل الأرصدة والعملاء | FormReportsGeneral |
| Client Financial Dues | العملاء بأمور مالية | FormReportsGeneral |
| Expenses Vat | ضريبة المصروفات | FormReportsGeneral |
| Mizan/Balance Sheet | الميزان | FormMizan (7 procs), FormMizanCreate (33 procs) |

### H. VAT/Tax Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| VAT Report | تقرير الضريبة | FormVat (20 procs), FormVat2 (38 procs) |
| VAT Quarterly | تقرير ضريبي ربع سنوي | FormReportsGeneral |
| ZATCA Integration | ربط الزكاة | ModZatca (14 procs), ModZatca2Wraber (24 procs) |
| E-Invoice Reports | الفواتير الإلكترونية | FormVat2 |
| Tax Registration | رقم التسجيل الضريبي | FormReportsGeneral |

### I. Employee/Admin Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| User Permissions | تقرير الصلاحيات | FormReportsGeneral |
| Employee Hours | اجمالي ساعات الموظفين | FormHodour |
| Attendance/Departure | الحضور والانصراف | FormHodour (16 procs), FormHodour19 (35 procs) |
| User Ehsa | احصائيات المستخدم | FormUserEhsa |
| Manual Adjustment | تقرير التعديل اليدوي | FormReportsGeneral |

### J. Specialized Reports
| Report | Arabic Name | Module/Form |
|--------|------------|-------------|
| Series Reports | تقارير السلاسل | FormSilsila (26 procs) |
| Needs Reports | تقارير الاحتياجات | FormNeedsAll (50 procs) |
| Chain Buy Reports | تقارير الشراء المتسلسل | FormChainBuy |
| Wasfaty/Prescription | تقرير وصفتي | FormWasfaty |
| Drug Comparisons | مقارنة الادوية | FormDrugsCompare |
| Best 100 | أفضل 100 صنف | FormBest100 |
| Period Statistics | احصائيات الفترة | FormPeriodEhsa |

---

## 2. PRINT TEMPLATES

### A. Invoice Templates
| Template | Arabic | Description |
|----------|--------|-------------|
| **Sales Invoice** | فاتورة مبيعات | Standard sales invoice with items |
| **Purchase Invoice** | فاتورة مشتريات | Purchase entry invoice |
| **Tax Invoice** | فاتورة ضريبية | VAT-compliant invoice |
| **Tax Invoice - Return** | فاتورة ضريبية مرتجع | Sales return with tax |
| **Tax Invoice - Credit** | فاتورة ضريبية اجلة | Credit/deferred invoice |
| **Simplified Tax Invoice** | فاتورة ضريبية مبسطة | Simplified tax invoice |
| **Transfer Invoice** | فاتورة محولة | Inter-branch transfer |
| **Fake Invoice** | Fake-invoice | Test/template invoice |
| **E-Invoice** | E-Invoice / Electronic Invoice | ZATCA-compliant |

### B. Receipt/Document Templates
| Template | Arabic | Description |
|----------|--------|-------------|
| **Cash Receipt** | سند قبض | Payment received voucher |
| **Payment Voucher** | سند صرف | Payment disbursement voucher |
| **Supplier Payment** | سند صرف لمورد | Supplier payment slip |
| **Delivery Receipt** | إيصال التوصيل | Delivery confirmation |

### C. Barcode Label Templates
| Template | Arabic | Description |
|----------|--------|-------------|
| **Barcode Label (Zebra)** | ملصق باركود (زيبرا) | Thermal printer labels |
| **Barcode Label (Standard)** | ملصق باركود عادي | Laser/A4 printer labels |
| **Shelf Label** | ملصق رف | Shelf price labels |
| **A4 Barcode Sheet** | ورق ايه فور | 6 Column x 24 Rows (12*35) |
| **Split Label** | ملصق مقسم | Label 2 = splitted label |
| **Non-Split Label** | ملصق غير مقسم | Label 1 = non-splitted |
| **Attendance Barcode** | باركود الحضور والانصراف | Employee check-in barcode |

### D. Report Print Formats
| Format | Paper | Description |
|--------|-------|-------------|
| **A4 Paper** | A4 | Standard report printing |
| **A5 Paper** | A5 | Half-size report printing |
| **Thermal Receipt** | Thermal | Cash register roll paper |
| **Zebra Printer** | Zebra/Thermal | Dedicated barcode printer |
| **XPrinter** | Thermal | XPrinter brand support |
| **A4 6 Col x 24 Rows** | A4 | Specific layout: 12mm x 35mm per cell |

---

## 3. REPORT COLUMN DEFINITIONS

### A. Financial Transaction Columns (Arabic)
```
التاريخ      القيمة     الضريبة      الوصف       البيان       الخزينة     الفرع
(Date)       (Value)    (Tax)     (Description) (Statement) (Cashbox)  (Branch)
```

### B. Invoice Line Columns
```
رقم    اسم الصنف   الكمية    سعر     خصم     اجمالي     عميل    مستخدم   تاريخ
(Number) (Item Name) (Qty)  (Price) (Disc)  (Total)  (Customer) (User) (Date)
```

### C. Drug Detail Columns
```
رقم الدواء    سعر الصنف    العميل    التاريخ     النوع
(Drug No)  (Item Price) (Customer) (Date)  (Type)
```

### D. Adjustment Report Columns
```
تاريخ التعديل    الصنف    التعديل     سعر البيع     خصم الشراء     قيمة التعديل      الفرع
(Adj Date)    (Item)  (Adjustment) (Sell Price) (Buy Discount) (Adj Value)  (Branch)
```

### E. Customer/Supplier Report Columns
```
اسم العميل    مديونية العميل    الفرع
(Customer Name) (Customer Debt) (Branch)

اسم المورد    مستحقات المورد  الفرع
(Supplier Name) (Supplier Due) (Branch)
```

### F. VAT Report XML Structure Fields
```xml
<sales-vat>
<sales-with-vat>
<sales-taxable>
<sales-non-taxable>
<sales-cost-no-vat>
<sales-cost-with-vat>
<sales-total-vat>
<purchases-vat>
<purchases-with-vat>
<purchases-taxable>
<purchases-non-taxable>
<purchases-total-vat>
<masrofat-vat>
<total-Cost-no-vat>
<total-Cost-with-vat>
<qr>
<zatca-response>
```

### G. E-Invoice (ZATCA) JSON Structure
```json
{
  "header": {
    "uuid": "",
    "dateTimeIssued": "",
    "receiptNumber": "",
    "receiptType": "",
    "currency": "",
    "exchangeRate": 0
  },
  "seller": {
    "name": "",
    "vatNumber": "",
    "address": {
      "country": "",
      "governate": "",
      "street": "",
      "buildingNumber": "",
      "postalCode": "",
      "regionCity": ""
    }
  },
  "buyer": {
    "name": "",
    "vatNumber": ""
  },
  "itemData": [{
    "itemCode": "",
    "internalCode": "",
    "quantity": 0,
    "unitType": "",
    "unitPrice": 0,
    "taxableItems": [{
      "taxType": "",
      "subType": "",
      "rate": 0,
      "amount": 0
    }],
    "total": 0,
    "netSale": 0,
    "itemDiscountData": [],
    "commercialDiscountData": []
  }],
  "totalSales": 0,
  "totalAmount": 0,
  "netAmount": 0,
  "totalCommercialDiscount": 0,
  "totalItemsDiscount": 0,
  "taxTotals": [],
  "paymentMethod": ""
}
```

---

## 4. PRINTER CONFIGURATION

### A. Printer Types Supported
| Type | Arabic | Notes |
|------|--------|-------|
| **Barcode Label Printer** | طابعة الباركود | Zebra, Pixelon, Godex thermal |
| **Report Printer** | طابعة التقارير | Standard laser/A4 |
| **Cash Printer** | طابعة الكاش | Receipt printer |
| **A4 Paper Printer** | طابعة ورق ايه فور | Standard A4 laser |
| **XPrinter** | *XPrinter* | Thermal receipt brand |
| **No Printer** | لا يوجد طابعة | (No Printer Installed) |
| **Zebra Printer** | طابعة الزبرا | Dedicated barcode/label |
| **Barcode = Laser** | اجعل طابعة الباركود هي طابعة الليزر | Use laser for barcodes |

### B. Printer Settings Form
**FormPrinterSettings** (31 procedures) - Main printer configuration:
- Paper size selection (A4, A5, Thermal)
- Printer selection per function (barcode, reports, invoices)
- Margin settings (top, bottom, left, right)
- Drawer connection (cash drawer)
- Auto-print on save toggle
- Label dimensions

**FormPrinterSettingFary** (28 procedures) - Secondary/branch settings

**FffSelectPrinter** (2 procedures) - Printer selection dialog

### C. Paper/Label Sizes
| Size | Dimensions | Usage |
|------|-----------|-------|
| A4 | 6 Column x 24 Rows (12x35mm) | Barcode sheets |
| A4 Standard | 210x297mm | Reports, invoices |
| A5 | 148x210mm | Smaller reports |
| Thermal 38mm | 38mm width | Barcode rolls |
| Thermal 25mm | 25mm width | Small labels |
| Shelf Label | 3.8cm x 1.2cm | Price shelf labels |

### D. Printer Settings Options
- **Auto-print invoice on save** - طباعة الفاتورة تلقائيا مع الحفظ
- **Open drawer on save** - فتح الدرج المتصل بالطابعة مع كل عملية حفظ
- **Drawer connected to printer** - الدرج المتصل بالطابعة
- **Print on A4 paper** - طباعة علي ورق ايه فور
- **Print A5 paper** - طباعة ورق ايه فايف
- **Old QR code printing** - طباعة نموزج كيو ار قديم
- **Print shelf label** - طباعة ملصق رف
- **Print barcode for drug** - طباعة باركود لهذا الدواء
- **Print individual item barcode** - طباعة باركود لهذا الصنف منفردا
- **Print all items barcode** - Apply barcode printing to all items
- **Print without international barcode** - Apply barcode printing to medicines without international barcode
- **Do not print prices on label** - عدم طباعة اسعار علي ملصقة الباركود
- **Print doses** - طباعة الجرعات
- **Print as storehouse** - طباعة كمستودع
- **Print for insurance companies** - طباعة لشركات التامين
- **Number printed on paper invoice** - الرقم المطبوع علي ورق الفاتورة
- **Print model selection** - Choose a print model

### E. Label Configuration
- **Label Count** - عدد الملصقات
- **Splitted vs Non-splitted** - 1 for non-splitted, 2 for splitted
- **Print date on barcode** - هل تود طباعة تاريخ شراء الصنف
- **Print item number on barcode** - هل تود طباعة رقم الصنف
- **Label paper compatibility** - Types of barcode paper compatible with Titan
- **Margin adjustment** - ضبط هوامش الطابعة
- **Printing starts at row** - يمكن البدا من اي صف في الصفحة
- **Printing starts 1.5mm from edge** - الهامش 1.5 مللي من حافة الورقة
- **Printing starts 4.5mm from edge** - الهامش 4.5 مللي من حافة الورقة
- **Printing starts from edge** - الهامش يبدا مباشرة من حافة الورقة

---

## 5. EXPORT CAPABILITIES

### A. Export Formats
| Format | Method | Description |
|--------|--------|-------------|
| **Excel (.xlsx)** | Excel.Application | Export to Excel files |
| **CSV** | Cusom-export.csv | Custom CSV export |
| **PDF** | Foxit Reader / PDF printer | Requires PDF printer (e.g., Foxit) |
| **Database Export** | FormExportdataBase | Full database export |
| **File Export** | Export to file | Generic file export |

### B. Export Functions
- **Export all sales to Excel** - تصدير كل المبيعات الي ملف اكسل
- **Export database to Excel** - تصدير قاعدة البيانات الي اكسل
- **Export current drug to file** - تصدير الدواء الحالي الي ملف
- **Export prices to file** - تصدير الاسعار الي ملف
- **Export to purchase file** - تصدير الي ملف مشتريات
- **Export to sales file** - تصدير الي ملف مبيعات
- **Export invoice to another pharmacy** - تصدير الفاتورة الي صيدلية اخري
- **Export to drugeye** - تصدير الي drugeye
- **Export stocks and data** - تصدير المخزون والبيانات
- **Export price change** - تصدير تغيير السعر
- **Export barcode change** - تصدير تغيير الباركود
- **Export to batch file** - تصدير الي ملف دفعة
- **Export to merge file** - تصدير الي ملف دمج
- **Export-Data** - General data export
- **Export-Data-Worked** - Export worked data
- **Export-Many_Sales** - Multiple sales export
- **Save invoice as Excel** - حفظ الفاتورة كملف اكسل
- **Column separator in Excel** - حرف فصل الاعمدة في جدول الاكسل

### C. Export Paths
```
Labirdo\Titan-to-excel\
Labirdo\Titan3-Backup\Export\
Labirdo\Titan3-Backup\Export\Del\
Files\Accounting\Vat-reports\
Files\Accounting\monthly\
C:\saturn\Zatca\computer-1\invoices\
```

---

## 6. MODULE-TO-REPORT MAPPING

### Primary Print/Report Modules
| Module | Procs | Role |
|--------|-------|------|
| **ModPrint** | 70 | Core printing engine - all print operations |
| **FormReportsGeneral** | 61 | Central reports hub - all report generation |
| **FormPrinterSettings** | 31 | Printer configuration management |
| **FormPrinterSettingFary** | 28 | Branch/secondary printer settings |
| **FormPrintSales** | 17 | Sales-specific printing |
| **FormVat2** | 38 | VAT report generation |
| **FormVat** | 20 | VAT processing |
| **ModZatca2Wraber** | 24 | ZATCA e-invoicing integration |
| **ModZatca** | 14 | ZATCA core functions |

### Report-Generating Forms
| Form | Procs | Reports Generated |
|------|-------|-------------------|
| **FormReportsGeneral** | 61 | All general reports (daily, monthly, yearly, sales, purchase, financial) |
| **FormDailyQuiod** | 16 | Daily quick reports |
| **FFFDayEnd** | 25 | End-of-day closing reports |
| **FormDrugsDetails** | 51 | Drug detail reports |
| **FormDrugFlow** | 32 | Drug movement reports |
| **FormNeedsAll** | 50 | Needs/requirements reports |
| **FormExpiredDrugs** | 21 | Expiry reports |
| **FormAmilTakarir** | 23 | Employee reports |
| **FormHodour19** | 35 | Attendance reports |
| **FormAccReports** | 4 | Accounting reports |
| **FormTaslimReport** | 7 | Delivery reports |
| **FormPeriodEhsa** | 9 | Period statistics |
| **FormMizanCreate** | 33 | Balance sheet creation |
| **FormWasfaty** | 27 | Prescription reports |
| **FormSilsila** | 26 | Series/chain reports |
| **FormDrugStckAtMonths** | 12 | Monthly stock reports |
| **FormDrugMonthly** | 7 | Monthly drug reports |

### Storage/Data Modules
| Module | Procs | Role |
|--------|-------|------|
| **ModStorage** | 154 | Core data storage - all data access |
| **ModOot** | 105 | Purchase/output operations |
| **ModInn** | 71 | Sales/input operations |
| **ModMony** | 30 | Financial operations |
| **ModAccounting** | 25 | Accounting integration |
| **Raz** | 379 | Core utility functions |

---

## 7. ZATCA E-INVOICE INTEGRATION

### API Endpoints
```
/api/v1/receipts/recent
/api/v1/receipts/recent?ReceiptNumber=
/api/v1/receiptsubmissions
/receipts/search/
```

### SFDA DTTS Service Requests
```xml
<m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">
<m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">
<m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">
<m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">
<m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">
```

### E-Invoice Fields
```
UUID, Receipt Number, Receipt Type, DateTime Issued, Currency
Seller: Name, VAT Number, Address (Country, Governorate, Street, Building, Postal, Region)
Buyer: Name, VAT Number
Items: Code, Internal Code, Quantity, Unit Type, Unit Price, Tax, Total, Discounts
Payment Method, Total Sales, Total Amount, Net Amount
```

---

## 8. DATABASE TABLES (Report Data Sources)

### Core Tables
| Table | Purpose |
|-------|---------|
| **titanstock** | Drug stock data (drugname, lastedit, pharmacyid, price, stock, barcode, titanid) |
| **titanksastock** | Branch stock (drugname, datee, silsilaid, minimum, pharmacyid, classy, stock) |
| **titanksasales** | Sales invoices |
| **titaninn** | Input/sales operations (fatid, itemsasstring, datee, source, silsilaid, target) |
| **TitanUserAction** | User action log (drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee) |
| **storediscount** | Store discount data |

### Data Files
```
Files\DBI\Daily.phy          - Daily data
Files\DBI\Dailyline.phy      - Daily line data
Files\DBI\Dailymax.phy       - Daily max data
Files\DBI\workperiod.phy     - Work period data
Files\DBI\delivery.phy       - Delivery data
Files\DBI\oot3.phy           - Purchase output data
Files\DBI\monthly-data       - Monthly data
Files\DBI\rasd-config.phye   - Rasd configuration
Files\StockNow               - Current stock
Files\Archive\Input\         - Archived inputs
Files\Archive\Output\        - Archived outputs
```

---

## 9. REPORT ACCESS PATHS

### Main Menu Navigation
```
الشاشة الرئيسية (Main Screen)
├── قائمة تقارير (Reports Menu)
│   ├── تقرير تاريخ الصيدلية (Pharmacy History Reports)
│   │   └── قائمة تجميعات اعلي الشاشة (Aggregation lists at top of screen)
│   ├── تقارير المبيعات (Sales Reports)
│   ├── تقارير المشتريات (Purchase Reports)
│   ├── تقارير العملاء (Customer Reports)
│   ├── تقارير الاحتياجات (Needs Reports)
│   └── تقارير متعددة (Multiple Reports)
├── قائمة الطباعة (Print Menu)
│   ├── اعدادات الطابعة (Printer Settings)
│   │   ├── طابعة الباركود (Barcode Printer)
│   │   ├── طابعة التقارير (Report Printer)
│   │   └── تعديل اعدادات الطابعة (Modify Printer Settings)
│   ├── طباعة الباركود (Barcode Printing)
│   └── طباعة ملصق رف (Shelf Label Printing)
├── قائمة مشتريات (Purchases Menu)
│   └── فاتورة مشتريات (Purchase Invoice)
├── قائمة بيع (Sales Menu)
│   └── فاتورة مبيعات (Sales Invoice)
└── قائمة ملف (File Menu)
    └── تصدير (Export)
```

---

## 10. SUMMARY STATISTICS

- **Total Report Types**: 45+ distinct report types
- **Print Templates**: 15+ invoice/document templates
- **Barcode Label Formats**: 7+ label configurations
- **Export Formats**: Excel, CSV, PDF, Database files
- **Printer Types**: 7+ supported printer categories
- **Report Periods**: Daily, Monthly, Quarterly, Yearly, Custom Period
- **Integration Points**: ZATCA, SFDA DTTS, Rasd, FaryNet, E-Commerce
