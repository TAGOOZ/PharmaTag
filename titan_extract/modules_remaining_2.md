# TITAN.W1 Remaining Modules & Forms - Analysis Report

**Date:** 2026-08-15  
**Source Files:** `pcode_disasm.txt`, `strings_utf16.txt`, `objects.txt`  
**Project:** TITAN.W1 (Phye.exe) VB6 Pharmacy Management System

---

## Module Summary

| Module | Procs | Size (bytes) | Status |
|--------|-------|-------------|--------|
| ModNed | 4 | 240+ | ✅ Analyzed |
| ModDate | 4 | 200+ | ✅ Analyzed |
| ModDateInternal | 3 | 150+ | ✅ Analyzed |
| ModDate15 | 35 | 3000+ | ✅ Analyzed |
| ModReg | 2 | 100+ | ✅ Analyzed |
| ModNewsLine | 2 | 150+ | ✅ Analyzed |
| ModOOTTrans | 1 | 4 | ⚠️ Empty stub |
| ModAC | 1 | 8404 | ✅ Analyzed |
| Maliat | 1 | 500+ | ✅ Analyzed |
| Moddelivery | 3 | 300+ | ✅ Analyzed |
| ModArchive | 2 | 200+ | ✅ Analyzed |
| ModPharX | 1 | 100+ | ✅ Analyzed |
| Modfarynet | 2 | 200+ | ✅ Analyzed |
| Modallinone | 10 | 2000+ | ✅ Analyzed |
| ModVatReport | 3 | 300+ | ✅ Analyzed |
| ModServerConnections | 1 | 50+ | ✅ Analyzed |
| Modeveryday | 9 | 7164 | ✅ Analyzed |
| ModAutoUpdate | 1 | 50+ | ✅ Analyzed |
| ModUpDBI | 3 | 300+ | ✅ Analyzed |
| ModAPI | 3 | 200+ | ✅ Analyzed |
| Modhelp | 0 | 0 | ⚠️ Empty module |
| ModCompany | 0 | 0 | ⚠️ Empty module |
| Types | 0 | 0 | ⚠️ Empty module |
| ModChanges | 0 | 0 | ⚠️ Empty module |
| ZzBookMark | 0 | 0 | ⚠️ Empty module |

## Form Summary

| Form | Procs | Status |
|------|-------|--------|
| FormChatAnydesk | 4 | ✅ Analyzed |
| FormUpdator | 7 | ✅ Analyzed |
| FormNews | 2 | ✅ Analyzed |
| FormVat2 | 38 | ✅ Analyzed |
| FormEcommerce | 6 | ✅ Analyzed |
| FormFaryNet | 8 | ✅ Analyzed |
| FormDeliver | 5 | ✅ Analyzed |

---

## Detailed Module Analysis

### 1. ModNed (Cash/POS Module)
**Location:** pcode_disasm.txt line 314849  
**Procedures:** 4  
**Functionality:** Cash register and point-of-sale operations

**Key Strings Found:**
- `مشتريات بسعر البيع` (Purchases at selling price)
- `فات المشتريات` (Purchase invoices)
- `مسدد نقدا مشتريات` (Cash-paid purchases)
- `مسدد شبكة مشتريات` (Network-paid purchases)
- `اجل المشتريات` (Credit purchases)
- `</cash-now>`, `<cash-now>` - Cash transaction tags
- `</sales-payed-cash>`, `<sales-payed-cash>` - Sales cash payment tags
- `</purchases-payed-cash>`, `<purchases-payed-cash>` - Purchases cash payment tags
- `</shereek-cash>`, `<shereek-cash>` - Partner cash tags
- `</masrofat-cash>`, `<masrofat-cash>` - Expenses cash tags
- `</moves-eradat-cash>`, `<moves-eradat-cash>` - Transfer moves tags
- `</moves-mrd-pay-cash>`, `<moves-mrd-pay-cash>` - Patient payment moves
- `</moves-sharik-eda-cash>`, `<moves-sharik-eda-cash>` - Partner share moves

**Purpose:** Handles all cash transactions including sales, purchases, expenses, and partner settlements in a pharmacy POS system.

---

### 2. ModDate (Date Management)
**Location:** pcode_disasm.txt line 105438  
**Procedures:** 4  
**Functionality:** Core date manipulation and formatting

**Purpose:** Provides date utility functions for the application, likely including date formatting, validation, and conversion operations.

---

### 3. ModDateInternal (Internal Date Operations)
**Location:** pcode_disasm.txt line 90635  
**Procedures:** 3  
**Functionality:** Internal date calculations

**Purpose:** Handles internal date operations such as date arithmetic, period calculations, and date range validations.

---

### 4. ModDate15 (Extended Date Operations)
**Location:** pcode_disasm.txt line 339068  
**Procedures:** 35  
**Functionality:** Extended date handling with multiple variants

**Purpose:** Comprehensive date management with 35 different procedures for various date-related operations including:
- Date formatting
- Period calculations
- Fiscal year handling
- Date range validations
- Calendar operations

---

### 5. ModReg (Registration/License Module)
**Location:** pcode_disasm.txt line 343801  
**Procedures:** 2  
**Functionality:** Software registration and licensing

**Key Strings Found:**
- `Commercial register` - Commercial registration
- `CoReg` - Company registration

**Purpose:** Manages software licensing, activation codes, and registration validation.

---

### 6. ModNewsLine (News/Updates Module)
**Location:** pcode_disasm.txt line 351367  
**Procedures:** 2  
**Functionality:** News and update notifications

**Purpose:** Handles news feed, software updates, and notification delivery to users.

---

### 7. ModOOTTrans (Out-of-Transactions)
**Location:** pcode_disasm.txt line 359829  
**Procedures:** 1  
**Size:** 4 bytes  
**Status:** ⚠️ Empty stub (only `ExitProc`)

**Purpose:** Placeholder module for out-of-transaction handling. Currently not implemented.

---

### 8. ModAC (Accounting Module)
**Location:** pcode_disasm.txt line 87127  
**Procedures:** 1  
**Size:** 8404 bytes  
**Functionality:** Accounting operations

**Key Strings Found:**
- `Capital account reports` - Capital account reporting
- `Capital reports` - Capital reports
- `Capital stats and pharmacy overview` - Capital statistics

**Purpose:** Core accounting module for financial operations, capital tracking, and pharmacy financial overview.

---

### 9. Maliat (Quantities Module)
**Location:** pcode_disasm.txt line 173623  
**Procedures:** 1  
**Functionality:** Quantity counting and inventory tracking

**Key Strings Found:**
- `"quantity":` - Quantity field
- `"maximum_sales_quantity":` - Maximum sales quantity
- `Abnormal Discount` - Discount detection
- `Order by count(*)` - Counting queries
- `STRING_AGG(CAST(titanid AS NVARCHAR(20)) + ':' + CAST(quantity AS NVARCHAR(20)), '^ ')` - Quantity aggregation

**Purpose:** Handles inventory quantities, stock counting, and quantity-based operations.

---

### 10. Moddelivery (Delivery Management)
**Location:** pcode_disasm.txt line 500167  
**Procedures:** 3  
**Functionality:** Delivery service management

**Key Strings Found:**
- `خدمة توصيل` (Delivery service)
- `توصيل` (Delivery)
- `التقارير التوصيل` (Delivery reports)
- `Delivery report` - Delivery reporting
- `Cash delivery reports between work periods` - Cash delivery reports
- `Delivery man` - Delivery personnel
- `https://hungerstation.partner.deliveryhero.io/v2/chains/` - HungerStation integration
- `https://hungerstation.partner.deliveryhero.io/v2/oauth/token` - HungerStation OAuth
- `Files\DBI\delivery.phy` - Delivery database file

**Purpose:** Manages delivery operations including:
- Delivery tracking
- Delivery personnel management
- Integration with HungerStation delivery platform
- Cash collection from deliveries

---

### 11. ModArchive (Archive Module)
**Location:** pcode_disasm.txt line 507444  
**Procedures:** 2  
**Functionality:** Data archiving and historical records

**Key Strings Found:**
- `Archive old sales invoices` - Archive old invoices
- `Read archived invoices` - Read archived data
- `Files\Archive\Input\` - Archive input directory
- `Files\Archive\Output\` - Archive output directory
- `CompressArchive` - Archive compression
- `Empty archive` - Empty archive
- `OpenArchive` - Open archive
- `Invalid archive` - Invalid archive error
- `ForceArchive` - Force archiving
- `\\Files\Archive\last-3-days-sales.csv` - Recent sales archive
- `\\Files\Archive\monthy\` - Monthly archives
- `\\Files\Archive\undo.sales.txt` - Undo sales archive
- `cZipArchive` - ZIP archive component

**Purpose:** Manages data archiving including:
- Historical sales invoice archiving
- Archive compression
- Archive restoration
- Monthly data archival

---

### 12. ModPharX (Pharmacy X Module)
**Location:** pcode_disasm.txt line 542690  
**Procedures:** 1  
**Functionality:** Extended pharmacy operations

**Key Strings Found:**
- `PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,SourceIdDateTime,price` - Pharmacy data fields
- `select pharmacyname ,adress,count(*) ,max(datee) from storediscount` - Pharmacy statistics query

**Purpose:** Extended pharmacy operations module, likely for multi-branch pharmacy management.

---

### 13. Modfarynet (FaryNet Network Module)
**Location:** pcode_disasm.txt line 549048  
**Procedures:** 2  
**Functionality:** Network operations for remote pharmacy branches

**Key Strings Found:**
- `select * from farysales where mobile = N'` - Fary sales query
- `' and Fary =N'` - Fary filter
- `Files\FarWay\Titanfary.exe` - Fary executable
- `Files\DBI\PIFary.phy` - Fary pharmacy info
- `Files\DBI\fary.date.phy` - Fary date file
- `Files\DBI\fary.net.worked.txt` - Fary network worked file
- `Files\DB\closefary.phy` - Close Fary
- `forfary.far` - Fary format file
- `insert into wzaccfreetree (mobile,master,fary) values (` - Fary database insert
- `pifary loading ..` - Loading Fary
- `titan-users/fary-net/` - FaryNet directory
- `الاشتراك السنوي 300 جنيه عن طريق ماكينة فوري محفظة بنك مصر` (Annual subscription 300 EGP via Fawry machine)

**Purpose:** Network connectivity for remote pharmacy branches (Fary system).

---

### 14. Modallinone (All-in-One Reports Module)
**Location:** pcode_disasm.txt line 583175  
**Procedures:** 10  
**Functionality:** Consolidated reporting system

**Key Strings Found:**
- `/allinone/` - All-in-one directory
- `/titan-users/allinone/data/` - Data directory
- `/titan-users/allinone/mobiles/` - Mobiles directory
- `Upload allinone` - Upload functionality
- `Files\All-in-one\` - All-in-one files
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/data/` - Data URL
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/mobiles/` - Mobiles URL
- `اضافة شاشة تجيمع كل الادوية المسحوبة بواسطة العميل في فترة محددة في جدول واحد` (Add screen to collect all drugs withdrawn by customer in specific period)
- `اضافة شاشة تقارير متعددة في الشاشة الرئيسية` (Add multiple reports screen)
- `تجميع كل انظمة النواقص في شاشة واحدة` (Consolidate all shortage systems in one screen)
- `تجميع كل نواقص الصيدليات التابعة لك في شاشة واحدة` (Collect all subordinate pharmacy shortages in one screen)
- `نحاول في هذه الشاشة ان نجمع كل التقارير في مكان واحد` (We try to collect all reports in one place)

**Purpose:** Consolidated reporting hub that brings together:
- Drug shortage reports
- Customer purchase history
- Multiple report types in unified interface
- Data upload/sync capabilities

---

### 15. ModVatReport (VAT Report Module)
**Location:** pcode_disasm.txt line 595524  
**Procedures:** 3  
**Functionality:** VAT tax reporting

**Key Strings Found:**
- `Quarterly VAT report` - Quarterly reporting
- `Files\Accounting\Vat-reports\` - VAT reports directory
- `الاجمالي قبل الضريبة` (Total before tax)
- `اجمالي الضريبة` (Total tax)
- `اجمالي ضريبة القيمة المضافة 15 بالمائة` (Total VAT 15%)
- `ادخل 500 لاحتياب الضريبة او 750 لعدم الاحتساب` (Enter 500 for tax inclusion or 750 for exclusion)
- `ادخل اجمالي المبلغ شامل الضريبة لكل الفترة` (Enter total amount including tax for period)

**Purpose:** Generates VAT reports for tax compliance, including quarterly and period-based reports.

---

### 16. ModServerConnections (Server Connections Module)
**Location:** pcode_disasm.txt line 641714  
**Procedures:** 1  
**Functionality:** Server connectivity management

**Key Strings Found:**
- `Files\DB\server.connection.report.txt` - Connection report
- `Files\DB\server.connector.exe` - Server connector executable
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/world/server.connector.exe` - Server connector download
- `labirdo-server-connector` - Server connector component
- `server.connector.exe` - Server connector

**Purpose:** Manages connections to central server for data synchronization and remote operations.

---

### 17. Modeveryday (Daily Operations Module)
**Location:** pcode_disasm.txt line 675966  
**Procedures:** 9  
**Size:** 7164 bytes  
**Functionality:** Daily business operations

**Key Strings Found:**
- `ReloadDailyManual` - Reload daily manual
- `Reload_Daily_Max` - Reload daily max
- `Daily instructions about Software` - Daily instructions
- `DailyManua loading ..` - Loading daily manual
- `DailyManual2 loading ..` - Loading daily manual 2
- `Daily\` - Daily directory
- `Expenses-daily restrictions` - Daily expense restrictions
- `Files\DBI\Dailymax.phy` - Daily max file
- `Labirdo\Titan3-Backup\Daily` - Backup daily
- `Upgrading Daily to Dailyline` - Upgrade daily
- `Upgrading DailyLine to dailymax` - Upgrade to dailymax
- `\\Files\DBI\Daily.phy` - Daily file
- `\\Files\DBI\Dailyline.phy` - Daily line file
- `\\Files\DBI\Dailymax.phy` - Daily max file
- `\\Files\DBI\daily-manual-2.phy` - Daily manual 2
- `\\Files\DBI\daily-manual.phy` - Daily manual
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/dailynotes.html` - Daily notes
- `titan.everyday\` - Everyday directory
- `ارشادات يومية متجددة عن البرنامج` (Daily updated instructions about software)
- `انشاء مجلد داخل مجلد النسخ الاحتياطية` (Create folder inside backup folder)
- `برجاء تتبع جيدا التعليمات التالية` (Please follow the following instructions carefully)
- `تفاصيل يومية عن كل صيدلية` (Daily details for each pharmacy)

**Purpose:** Manages daily business operations including:
- Daily manual/instructions
- Daily expense tracking
- Daily backup procedures
- Work period management
- End-of-day procedures

---

### 18. ModAutoUpdate (Auto-Update Module)
**Location:** pcode_disasm.txt line 405003  
**Procedures:** 1  
**Functionality:** Automatic software updates

**Purpose:** Handles automatic software update checks and installations.

---

### 19. ModUpDBI (Database Import/Update Module)
**Location:** pcode_disasm.txt line 405037  
**Procedures:** 3  
**Functionality:** Database file import and updates

**Key Strings Found:**
- `Files\DBI\` - DBI files directory
- `DBI\internet-backup.txt` - Internet backup
- `ftpdbi.zip` - FTP DBI archive
- Various `.phy` files in `Files\DBI\` directory

**Purpose:** Manages database imports, updates, and synchronization from various sources including FTP.

---

### 20. ModAPI (API Integration Module)
**Location:** pcode_disasm.txt (3 procedures)  
**Functionality:** External API integrations

**Key Strings Found:**
- `/api-sign.aspx` - API signing
- `/api/v1/receipts/recent` - Recent receipts API
- `/api/v1/receiptsubmissions` - Receipt submissions API
- `db_9ffe55_apifordrugeye` - Drug Eye API database
- `Failed to copy QR from saturmn path to API path` - QR code handling
- `PUSHD %root%` - Push notification

**Purpose:** Integrates with external APIs for:
- Drug Eye (pharmacy monitoring) system
- Receipt processing
- QR code generation
- Push notifications

---

### 21. Modhelp (Help Module)
**Procedures:** 0  
**Status:** ⚠️ Empty module

**Purpose:** Placeholder for help system functionality.

---

### 22. ModCompany (Company Module)
**Procedures:** 0  
**Status:** ⚠️ Empty module

**Purpose:** Placeholder for company information management.

---

### 23. Types (Type Definitions)
**Procedures:** 0  
**Status:** ⚠️ Empty module

**Purpose:** Placeholder for custom type definitions.

---

### 24. ModChanges (Changes Module)
**Procedures:** 0  
**Status:** ⚠️ Empty module

**Purpose:** Placeholder for change tracking functionality.

---

### 25. ZzBookMark (Bookmark Module)
**Procedures:** 0  
**Status:** ⚠️ Empty module

**Purpose:** Placeholder for bookmark/favorites functionality.

---

## Detailed Form Analysis

### 1. FormChatAnydesk (Remote Support Form)
**Location:** pcode_disasm.txt line 408387  
**Procedures:** 4  
**Functionality:** Remote desktop support via AnyDesk

**Key Features:**
- AnyDesk integration for remote support
- Chat functionality
- Screen sharing capabilities
- Remote control session management

**Purpose:** Provides remote support and troubleshooting capabilities through AnyDesk integration.

---

### 2. FormUpdator (Software Updater Form)
**Location:** pcode_disasm.txt line 465047  
**Procedures:** 7  
**Functionality:** Software update management UI

**Key Features:**
- Update checking
- Download progress
- Installation management
- Version comparison

**Purpose:** User interface for managing software updates, downloads, and installations.

---

### 3. FormNews (News Form)
**Location:** pcode_disasm.txt line 351506  
**Procedures:** 2  
**Functionality:** News and announcements display

**Key Features:**
- News feed display
- Announcement rendering
- Update notifications

**Purpose:** Displays news, announcements, and software update notifications to users.

---

### 4. FormVat2 (VAT 2 Form)
**Location:** pcode_disasm.txt line 598587  
**Procedures:** 38  
**Functionality:** VAT tax management interface

**Key Strings Found:**
- `التاريخ القيمة الضريبة الوصف البيان الخزينة الفرع` (Date, Value, Tax, Description, Statement, Treasury, Branch)
- `السعر شامل الضريبة` (Price including tax)
- `السعر قبل الضريبة` (Price before tax)
- `القيمة شامل الضريبة` (Value including tax)
- `ضريبة ق مضافة Total VAT` (VAT added Total)
- `اجمالي الشراء قبل الضريبة` (Total purchases before tax)
- `اجمالي الضريبة` (Total tax)
- `ادخل السعر الرسمي الجديد لهذا الدواء شامل الضريبة` (Enter new official price including tax)
- `ادخل السعر الرسمي الجديد لهذا الدواء غير شامل الضريبة` (Enter new official price excluding tax)
- `ادخل خصم بيع ثابت لكل اصناف الضريبة` (Enter fixed sale discount for all tax items)
- `ادخل سعر القطعة غير شامل الضريبة` (Enter unit price excluding tax)
- `ادخل قيمة الضريبة` (Enter tax value)
- `ادخل نسبة ضريبة القيمة المضافة` (Enter VAT rate)
- `اصناف بدون ضريبة` (Items without tax)
- `اصناف بضريبة` (Items with tax)
- `اضافة عمود الباتش وضريبة القيمة المضافة` (Add batch and VAT column)
- `اعادة ضبط قيمة الضريبة في الفوانتير القديمة يدويا` (Reset tax value in old vouchers manually)

**Purpose:** Comprehensive VAT management interface for:
- Tax calculation and reporting
- Price management with/without tax
- Tax rate configuration
- Tax item categorization
- Historical tax adjustments

---

### 5. FormEcommerce (E-Commerce Form)
**Location:** pcode_disasm.txt line 691691  
**Procedures:** 6  
**Functionality:** E-commerce platform integration

**Key Strings Found:**
- `db_9ffe55_titanecommerce` - E-commerce database
- `db_9ffe55_titanecommerce_admin` - E-commerce admin database
- `اضافة الفاتورة الالكترونية وفقا لتعليمات الهيئات المالية الرسمية` (Add electronic invoice per official financial authorities)
- `برجاء اكمال بيانات الفاتورة الالكترونية` (Please complete electronic invoice data)
- `تسجيل في المرحلة الثانية للفاتورة الالكترونية` (Register in second phase of electronic invoice)
- `تم تفعيل خدمة الفاتورة الالكترونية` (Electronic invoice service activated)
- `جاري الان الربط مع موقع التجاره الالكترونية` (Linking with e-commerce site now)
- `عرض الفاتورة الالكترونية لهذه الفاتورة` (Display electronic invoice for this invoice)

**Purpose:** Integrates with e-commerce platforms for:
- Electronic invoicing
- Product listing synchronization
- Order management
- Multi-platform e-commerce support

---

### 6. FormFaryNet (FaryNet Form)
**Location:** pcode_disasm.txt line 684096  
**Procedures:** 8  
**Functionality:** Remote branch network management

**Key Features:**
- Remote pharmacy branch management
- Network connectivity status
- Data synchronization
- Branch sales monitoring

**Purpose:** User interface for managing remote pharmacy branches through the FaryNet network system.

---

### 7. FormDeliver (Delivery Form)
**Location:** pcode_disasm.txt line 500167  
**Procedures:** 5  
**Functionality:** Delivery service management UI

**Key Features:**
- Delivery order management
- Delivery personnel tracking
- Delivery status updates
- Integration with delivery platforms

**Purpose:** User interface for managing delivery operations, tracking deliveries, and coordinating delivery personnel.

---

## Cross-Module Dependencies

### Database Files Referenced
- `Files\DBI\delivery.phy` - Delivery data
- `Files\DBI\PIFary.phy` - Fary pharmacy info
- `Files\DBI\fary.date.phy` - Fary date data
- `Files\DBI\Daily.phy` - Daily operations
- `Files\DBI\Dailyline.phy` - Daily line data
- `Files\DBI\Dailymax.phy` - Daily max data
- `Files\DB\server.connection.report.txt` - Server connections
- `Files\Archive\` - Archive directory

### External Services
- HungerStation delivery platform
- Fawry payment system
- AnyDesk remote support
- Server connector (phycodsystems-001-site12.htempurl.com)

### API Endpoints
- `/api/v1/receipts/recent` - Receipts API
- `/api/v1/receiptsubmissions` - Receipt submissions
- `/api-sign.aspx` - API authentication

---

## Recommendations

1. **Empty Modules:** Consider removing or implementing Modhelp, ModCompany, Types, ModChanges, ZzBookMark as they appear to be placeholders.

2. **Documentation:** Add inline comments to pcode for better maintainability.

3. **Error Handling:** Review error handling in modules with `OnErrorGoto` patterns.

4. **Security:** Review API endpoints and authentication mechanisms.

5. **Archiving:** Ensure archive module has proper backup/restore testing.

---

*Report generated from pcode disassembly analysis of TITAN.W1 VB6 application.*
