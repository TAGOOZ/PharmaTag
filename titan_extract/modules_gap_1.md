# TITAN.W1 Module Extraction — Gap Analysis (24 Modules)

**Project:** TITAN.W1 (Phye.exe) — VB6 P-Code Pharmacy Application
**Source:** pcode_disasm.txt (6,192 procs), strings_utf16.txt (26,970 strings), objects.txt

---

## 1. ModDisc — Discount Logic

**Purpose:** Implements multi-tier discount calculation engine for sales/purchases. Handles percentage-based discounts, per-item discounts, and cumulative discount stacking across invoice line items.

**Key Procedures (10):**
- Discount rate calculation with `MulR8`, `DivR8`, `SubVar` — arithmetic on discount percentages
- Nested `ForVar` loops iterating over item arrays (up to 100 items per invoice)
- Comparison against code `0x00DF` (223) — likely a discount-type discriminator (item-level vs. invoice-level)
- A small dispatcher proc (size=16) that chains 3 calls — likely a "calculate all discounts" entry point
- Procs that compare `EqVarBool` against literal `1`, `2`, `3` — mapping discount types to calculation modes

**Database Tables:**
- `storediscount` — per-store discount configuration (`if not exists (select * from storediscount ...`)
- `titanksasales` — sales records with `SellDisc` column
- `titanstock` — stock records with `disco` field (`order by drugname desc, disco desc`)

**Key Strings:**
- `Discount=`, `Total Disc`, `Buy Discount`, `Cash discount`
- `Discount by currency`, `Discount by percent of profit value`, `Discount by percent of total value`
- `Apply a sale discount for tax items`, `Apply the discount of the last purchase`
- `Cancel discount`, `Clean sale discount for all items`
- `Abnormal Discount`, `Add. Disc`, `Local discount`, `No Extra Discount`
- `Imports discount`, `Fave disc`, `contain discount`
- `<purchases-disco>`, `<sales-disco>`, `<sales-with-vat-no-disc>`
- Arabic: `خصم`, `نسبة`, `نظام احتساب خصم الشراء`

---

## 2. ModMarid — Customer/Supplier (مراد) Management

**Purpose:** Customer and supplier (Marid = مراد) database management. Handles lookup, search, selection, and field initialization for customer/supplier records. The large proc (size=1288) initializes 107 fields of a customer/supplier data structure.

**Key Procedures (4):**
- Proc 1 (size=72): Iterates over customer array (3000 entries), matching by a float value — likely customer ID lookup
- Proc 2 (size=144): Searches customer array by name string, returns index — customer name search
- Proc 3 (size=312): Complex string matching with `InStr4Var` — fuzzy customer name search with string comparison
- Proc 4 (size=1288): Bulk initialization of 107 `LitStr` values into an array — field name mapping for customer/supplier record structure

**Database Tables:**
- Customer/supplier records (array-based in memory, likely loaded from file or DB)
- `wzgard` — related to customer transactions

**Key Strings:**
- `customers is :`, `Add a customer`, `Add new customer`, `Add a new supplier`
- `Best supplier`, `Dealing with suppliers`, `Debt customers`, `Debtless customers`
- Arabic: `اسم العميل`, `مديونية العميل`, `رقم العميل`, `المورد`, `سند صرف لمورد`
- XML tags: `<customer>`, `<customers>`, `<creditor>`, `<debtor>`, `<suppliers>`

---

## 3. ModScreen — Screen/Form Management

**Purpose:** Low-level Windows API wrapper for screen resolution detection, DPI awareness, and form positioning. Uses `GetSystemMetrics` and `SystemParametersInfo` Win32 APIs to detect screen dimensions and ensure forms fit within the display area.

**Key Procedures (3):**
- Proc 1 (size=312): Detects screen resolution using `GetSystemMetrics`/`SystemParametersInfo`, converts ANSI↔Unicode, calculates form position — handles high-DPI displays
- Proc 2 (size=148): Gets physical screen dimensions (`GetSystemMetrics` with SM_CXSCREEN/SM_CYSCREEN), shows warning dialog if resolution is too low (768x1024 threshold)
- Proc 3 (size=96): Gets a configuration string, shows a message dialog, and calls `End` (program termination) — likely a fatal "screen too small" error handler

**Database Tables:** None (purely UI/system-level)

**Key Strings:**
- `Screen Resolution...`
- `Approximate search screen`, `Collected deficiencies screen`, `Design screen`
- `Storage shelf screen`, `sales screen`
- `Go to the purchases screen`, `To sales screen`, `To purchases screen`
- `Zoom in program screens`, `Print Screen`

---

## 4. ModFTP — FTP Operations

**Purpose:** FTP file transfer client using Windows WinInet API (`InternetOpen`, `InternetConnect`, `FtpOpenFile`, `FtpGetFile`, `FtpPutFile`). Handles upload/download of database files, ZIP archives, and drug data between pharmacy instances.

**Key Procedures (10):**
- Proc 1 (size=56): Converts FTP file timestamp to VB Date format
- Proc 2 (size=360): Full FTP upload workflow — `InternetOpen` → `InternetConnect` → `FtpOpenFile` → write data → close. Uses ANSI string conversion for Win32 API
- Proc 3 (size=96): FTP download with retry loop (max 5 retries, delay between attempts)
- Proc 4 (size=428): Full FTP directory listing — connects, enumerates files, reads file attributes, returns file list
- Proc 5 (size=164): Constructs FTP upload command file (`ftpcmd.dat`) with multiple FTP commands
- Proc 6 (size=20): Error handler — calls `InternetCloseHandle` on error
- Proc 7 (size=140): Alternative FTP connection using COM object (`InetCtls` control)
- Proc 8 (size=108): File existence check via FTP `FtpFindFirstFile`
- Proc 9 (size=44): FTP connection status check
- Proc 10 (size=40): FTP file info retrieval (size, date)

**Database Tables:** None (file transfer operations)

**Key Strings:**
- `FTP://`, `--ftp-pasv --retry 3 --retry-delay 2`
- `ftpcmd.dat`, `C:\curl\curl.exe`, `C:\curl\curl_upload.log`
- `C:\ftpdbi.zip`, `D:\ftpdbi.zip`, ... through all drive letters
- `<function>ftp-upload</function>`, `<function>ftp-zip-upload</function>`
- `Current uploading item Stock :`, `Current uploading item name :`
- `Done uploading item unit cost`, `Download`

---

## 5. ModReBuild — Database Schema Rebuild

**Purpose:** Database schema migration and rebuild engine. Creates/modifies/drops tables, adds columns, rebuilds indexes, and handles schema versioning. The largest proc (size=2196) contains repetitive column-adding operations across many tables.

**Key Procedures (14):**
- Proc 1 (size=2196): Bulk schema modification — repeatedly calls `ALTER TABLE` with different column names (LitStr references). Adds ~30+ columns across multiple tables
- Proc 2 (size=824): Table creation with large frame (6172 bytes) — creates new tables with many columns
- Proc 3 (size=404): Index rebuild — creates/drops indexes
- Proc 4 (size=40): Simple proc — likely a schema version check
- Proc 5-7: Table migration procs (sizes 156, 168, 608) — data migration between old/new schemas
- Proc 8-10: Column existence check and conditional ALTER TABLE
- Proc 11-14: Schema validation and repair

**Database Tables:**
- `titanksasales`, `titanksastock`, `titanneed`, `titaninn` — core tables
- `TitanUserAction` — user action logging
- Various tables created/modified dynamically

**Key Strings:**
- `ALTER TABLE`, `CREATE TABLE`, `DROP TABLE`
- `CREATE TABLE titanksasales (`, `CREATE TABLE titanksastock (`, `CREATE TABLE titanneed (`
- `create table titaninn (`, `drop table titaninn;`
- `DROP TABLE titanksastock;`, `DROP table titanksasales;`
- `select Column_name From Information_schema.Columns where Table_name like`
- `Column separation letter in Excel table`, `ColumnWidth`, `Columns`

---

## 6. VB7 — VB6 Runtime Compatibility Layer

**Purpose:** VB6 backward-compatibility shim layer. Provides utility functions that bridge VB6 runtime features — date handling, array manipulation, string operations, file I/O wrappers, and memory management. Named "VB7" possibly for internal versioning (VB6 code targeting "VB7-like" behavior).

**Key Procedures (42):**
- Proc 1 (size=136): Date comparison and file write — checks if a date is within threshold, writes to file using `CStr2Ansi` for Unicode→ANSI conversion
- Proc 2 (size=284): Array processing — iterates over a dynamic array (`VarIndexLdVar`), performs sorting/comparison with `GtVar`
- Proc 3 (size=104): String length check and conditional operations
- Proc 4-5: Simple wrapper procs (sizes 24, 48) — thin delegation to other functions
- Proc 6 (size=112): Memory allocation/copy operations
- Proc 7 (size=124): File read/write with error handling
- Proc 8 (size=412): Large proc with complex control flow — likely a file parser or data transformer
- Proc 9-42: Various utility functions — array bounds checking, string manipulation, date formatting, error handling wrappers

**Database Tables:** None (utility functions)

**Key Strings:**
- `Sent XML data structure is not compatible with the scheme in WSDL document`
- `The format of the batch number of the product is incompatible.`
- `The format of the expiry date of the product (XD) is incompatible.`
- `The format of the product information of the product (GTIN) is incompatible.`
- `Types of barcode paper compatible with Titan`

---

## 7. ModSQL — SQL Database Operations

**Purpose:** Core SQL database abstraction layer. Manages ADODB connections, executes queries, handles connection pooling, and provides CRUD operations for all database tables. Acts as the central data access module.

**Key Procedures (13):**
- Proc 1 (size=216): Main SQL execution — creates ADODB connection (`ImpAdLdRf` → COM object), builds SQL string from concatenated `LitStr` references, executes via `LateMemCall`
- Proc 2 (size=280): Parameterized query execution — similar to proc 1 but with parameter binding
- Proc 3-4 (sizes 40, 60): Connection check/status — tests if connection is open
- Proc 5 (size=96): SQL string builder — concatenates table name, column list, values
- Proc 6-7 (sizes 36, 36): Simple return procs — likely connection open/close
- Proc 8 (size=68): Recordset iteration
- Proc 9 (size=148): Complex query builder with conditional WHERE clauses
- Proc 10 (size=76): Recordset field extraction
- Proc 11 (size=4): Empty proc — placeholder
- Proc 12 (size=636): Large query execution with multiple branches — handles INSERT, UPDATE, DELETE, SELECT
- Proc 13 (size=188): Transaction management

**Database Tables:**
- `titaninn` — invoice/import records
- `titanksasales` — sales records
- `titanksastock` — stock records
- `titanstock` — drug stock
- `titanpharmalist` — pharmacy list
- `drgserver` — drug server records
- `storediscount` — store discount config
- `nilsen2`, `remotecontrol` — remote control/data
- `RawakidTablew` — rawakid data
- `taronlineeg` — online transactions
- `usersourceupdate` — user source updates
- `farysales` — fary sales
- `wzdrugs`, `wzphar` — drug/pharmacy working tables

**Key Strings:**
- `ADODB.connection`
- `select * from titaninn`, `select * from titanksasales`, `select * from titanksastock`
- `delete from drgserver`, `delete from nilsen2`, `delete from remotecontrol`
- `insert into titaninn`, `insert into titanksasales`, `insert into wzdrugs`
- `if not exists (select * from storediscount ...`
- `select invoiceid from titanksasales where`
- `select drugname from titanksastock where`
- `items need to update :`

---

## 8. ModAmil2 — Employee Module 2 (Shifts/Attendance)

**Purpose:** Employee (AMIL = عميل/موظف) management for shift tracking, attendance logging, and employee data operations. Handles shift-in/shift-out recording, employee sales inquiry, and attendance barcode printing.

**Key Procedures (9):**
- Proc 1 (size=164): Employee data loading from `amil2.phy` file
- Proc 2 (size=192): Shift attendance recording — reads barcode, validates employee, logs time
- Proc 3 (size=68): Simple employee lookup
- Proc 4-6 (sizes 204, 136, 160): Employee data manipulation — add/edit/delete
- Proc 7 (size=52): File I/O for employee records
- Proc 8 (size=80): Employee report generation
- Proc 9 (size=368): Large proc — attendance reporting with date range filtering

**Database Tables:**
- Employee records stored in `Files\DBI\amil2.phy` and `Files\DBI\AmilInfo.phy`
- `taronlineeg` — online transactions per employee

**Key Strings:**
- `Employee number`, `Enter Amil name`
- `Inquiry about employee sales`, `Inquiry about shifts sales`
- `Sort your employees according to the degree of trust`
- `SHIFT`, `Shift+F2`, `F7, F8 : Shift Left and Right in piano keys`
- Arabic: `ادخل رقم مرور المدير او الموظف`, `تسجيل حضور`, `حضور`, `حضور وانصراف`
- `Done for Reload_amil_500`, `Reload_amil_500`
- `Files\DBI\amil2.phy`, `Files\DBI\AmilInfo.phy`
- `verapamil` (drug name — appears in employee context as a sample/test)

---

## 9. ModSqlLink — SQL Remote/Network Database Linking

**Purpose:** Manages database connections to remote SQL Server instances for multi-pharmacy network synchronization. Handles linked pharmacy discovery, data replication, and network-based data exchange between pharmacy branches.

**Key Procedures (19):**
- Proc 1 (size=168): Remote SQL connection setup using `Driver={SQL Server};SERVER=`
- Proc 2 (size=4): Empty placeholder
- Proc 3 (size=168): Remote query execution
- Proc 4 (size=176): Data synchronization — push local data to remote server
- Proc 5 (size=1540): Large proc — bulk data transfer with multiple table operations
- Proc 6 (size=4): Empty placeholder
- Proc 7 (size=1252): Network pharmacy discovery and linking
- Proc 8 (size=60): Connection validation
- Proc 9 (size=1124): Data replication — pull remote data to local
- Proc 10 (size=4): Empty placeholder
- Proc 11 (size=64): Connection status check
- Proc 12 (size=24): Simple wrapper
- Proc 13 (size=676): Remote invoice lookup and transfer
- Proc 14 (size=224): Network adapter detection via WMI
- Proc 15 (size=1404): Bulk sync operations
- Proc 16 (size=1772): Full synchronization workflow
- Proc 17 (size=1568): Data merge/consolidation
- Proc 18 (size=1340): Remote pharmacy data import
- Proc 19 (size=620): Connection cleanup

**Database Tables:**
- `drgserver` — drug server records (remote)
- `remotecontrol` — remote control commands
- `titanpharmalist` — pharmacy list
- `titanksasales`, `titanksastock` — synced sales/stock
- `titaninn` — invoice transfers

**Key Strings:**
- `Driver={SQL Server};SERVER=`, `Input server name`
- `Linking`, `Link with google drive`, `Unlink current pharmacy`
- `Network`, `Network-activation`
- `Pending invoice folder from linked devices`
- `Search for electronic invoice on server`
- `Server.control still executing its own work`
- `now, goto other computers and find 'Titan.master' in your network`
- `Cancel-phar-link`, `FillWithLinkedPhras`
- `$cred = New-Object System.Net.NetworkCredential($username, $password)`
- `SELECT * FROM Win32_NetworkAdapter WHERE NetEnabled = True`
- `Msxml2.ServerXMLHTTP.6.0`

---

## 10. ModAppType — Application Type Configuration

**Purpose:** Configures the application mode/type (pharmacy vs. clinic vs. wholesaler). Controls which features are enabled, which forms are shown, and which database tables are used based on the deployment type.

**Key Procedures (9):**
- Proc 1 (size=168): Application type initialization — reads config, sets global flags
- Proc 2-4 (sizes 148, 136, 156): Feature flag checks — returns boolean based on app type
- Proc 5-6 (sizes 160, 136): Form visibility control based on app type
- Proc 7 (size=120): Database table selection based on app type
- Proc 8 (size=72): App type string mapping
- Proc 9 (size=68): Configuration persistence

**Database Tables:**
- `titanksastock` — filtered by `pharmacyid` and `apptype`
- `titanstock` — filtered by `pharmacyid`
- `titanneed` — filtered by `pharmacyid`
- `titanpharmalist` — pharmacy identification

**Key Strings:**
- `and apptype ='`, `pharmacyid =`, `pharmacyid =N'`
- `pharmacyname`, `adress`, `pharmacyid`
- `4=All drugs With No International Barcode And they are pharmacy drugs`
- `<m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">`
- `<m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">`
- `typeVersion:`, `documentType:`, `receiptType:`
- `subType:`, `taxType:`, `itemType:`, `unitType:`

---

## 11. ModColors — Color/UI Theme Settings

**Purpose:** Manages application color scheme and UI theming. Stores and loads color preferences (background, foreground, cell colors) for the application's data grids and forms.

**Key Procedures (3):**
- Proc 1 (size=148): Color initialization — loads color settings from `colors.phy` file
- Proc 2 (size=96): Color application — sets `BackColor`, `ForeColor` on UI controls
- Proc 3 (size=76): Color persistence — saves current color scheme

**Database Tables:**
- `Files\DBI\colors.phy` — color configuration file

**Key Strings:**
- `BackColor`, `ForeColor`, `CellBackColor`, `CellForeColor`
- `BColor`, `bcolor`, `forecolor`
- `Colors`, `Color blindness`
- `.drugs-tabe td {border: 1px solid black;color: blue;}`
- `.final-tabe td {border: 1px solid black;color: red;}`
- `.titilo {text-size:150%;color: green;}`
- `background-color: #abeb34;`
- `Tinea vercicolour`
- `\\Files\\DBI\\colors.phy`

---

## 12. ModGS1Reader — GS1 Barcode Parser

**Purpose:** Parses GS1-128/DataMatrix barcodes used in pharmaceutical products. Extracts GTIN, batch number, expiry date, and serial numbers from structured barcode data. Handles both 1D (EAN-13, GS1-128) and 2D (DataMatrix, QR) barcode formats.

**Key Procedures (24):**
- Proc 1 (size=484): Main GS1 barcode parser — extracts GTIN, batch, expiry from GS1 Application Identifiers (AI)
- Proc 2 (size=104): GTIN validation — checks check digit
- Proc 3 (size=88): Batch number extraction from AI 10
- Proc 4 (size=588): DataMatrix parser — handles 2D barcode with embedded GS1 data
- Proc 5 (size=336): Barcode format detection — identifies barcode type from prefix
- Proc 6-7 (sizes 240, 240): Similar barcode parsing variants
- Proc 8 (size=344): QR code parser
- Proc 9 (size=68): Expiry date extraction from AI 17
- Proc 10 (size=48): Serial number extraction from AI 21
- Proc 11-24: Various barcode lookup and validation functions

**Database Tables:**
- `titanstock` — barcode column for drug lookup
- `titaninn` — barcode reference in invoices

**Key Strings:**
- `Barcode:`, `barcode`, `Barcode1=`, `Barcode2=`, etc.
- `GTIN`, `<GTIN>`, `</GTIN>`
- `<qr>`, `</qr>`, `<barcode>`, `</barcode>`
- `Add a barcode or short code`, `Add an item by barcode reader`
- `Add barcode`, `Apply barcode printing to all items`
- `An international barcode common to more than one drug`
- `An international barcode with an incorrect structure`
- `About Titan Scan`
- `barcode =`, `drugname,datee,silsilaid,minimum,pharmacyid,classy,stock) values (`
- `drugname,lastedit,pharmacyid,price,stock,barcode,titanid) values (`

---

## 13. ModEtaWrappper — Egyptian Tax Authority (ETA) Wrapper

**Purpose:** Wrapper for the Egyptian Tax Authority (ETA) e-invoicing API. Handles XML invoice generation, submission to ETA endpoints, UUID management, and invoice validation. Supports both production and pre-production ETA environments.

**Key Procedures (7):**
- Proc 1 (size=1060): Main ETA invoice submission — builds XML payload, sends to ETA API, parses response
- Proc 2 (size=52): UUID generation/retrieval
- Proc 3 (size=40): Connection test to ETA endpoint
- Proc 4 (size=176): Invoice XML builder — constructs invoice with header, items, tax totals
- Proc 5 (size=104): Response parser — extracts status, UUID, errors from ETA response
- Proc 6 (size=12): Simple wrapper
- Proc 7 (size=436): Invoice validation and retry logic

**Database Tables:**
- `titanksasales` — invoice data with `invoiceid`
- Various tables with `uuid` field for ETA tracking

**Key Strings:**
- `uuid:`, `previousUUID:`, `referenceOldUUID:`, `referenceUUID:`
- `netAmount:`, `totalAmount:`, `totalSales:`
- `https://api.invoicing.eta.gov.eg`
- `https://api.preprod.invoicing.eta.gov.eg`
- `<invoice>`, `</invoice>`, `<invoice-items>`, `<invoice-data>`
- `<invoice-number>`, `<invoice-type>`, `<invoice-counter>`
- `<refrenceInvoiceDate>`, `<refrenceInvoiceNumber>`
- `<zatca-response>`, `</zatca-response>`
- Arabic: `رقم الفاتورة`, `فاتورة : للمزيد اعد تنفيذ العملية`
- `invoice`, `invoiceid =`
- `select invoiceid from titanksasales where`

---

## 14. ModAccounting — Accounting System

**Purpose:** Full double-entry accounting module. Manages chart of accounts, journal entries, trial balance, financial statements, and account reconciliation. Supports both simplified (free) and full accounting modes.

**Key Procedures (25):**
- Proc 1-2 (sizes 112, 112): Account lookup by code/name
- Proc 3 (size=272): Journal entry creation with debit/credit balancing
- Proc 4 (size=296): Trial balance generation
- Proc 5-10 (sizes 48-60 each): Simple account operations (create, update, delete, balance check)
- Proc 11 (size=124): Account tree traversal
- Proc 12-14 (sizes 60 each): Account balance calculations
- Proc 15 (size=64): Account validation
- Proc 16 (size=312): Financial statement generation
- Proc 17 (size=140): Account reconciliation
- Proc 18-20 (sizes 104, 136, 148): Report generation
- Proc 21 (size=148): VAT report integration
- Proc 22-25 (sizes 16 each): Simple utility procs

**Database Tables:**
- `wzaccfreetree` — account tree structure
- `Files\Accounting\` directory — accounting data files
- `Files\Accounting\Vat-reports\` — VAT reports
- `Files\Accounting\monthly\` — monthly closing data
- `Files\Accounting\monthly\ascode\` — account codes
- `Files\Accounting\moves\` — journal entries
- `Files\Accounting\sales\` — sales accounting

**Key Strings:**
- `Account statement`, `Activate the integrated accounting department`
- `Capital account reports`, `Capital stats and pharmacy overview`
- `Chronology of balances and customers`
- `Data feeding the financial statements and trial balance`
- `Entry with operations account`, `Login with management account`
- `Login with operations account`, `Review pending requests to adjust balances`
- `Trial Balance`, `opening balances`
- Arabic: `اجمالي ساعات الموظفين في الفترة`, `اجمالي الاجل`, `اجمالي المخصوم`, `اجمالي المدفوع نقدا`
- `<account>`, `</account>`
- `Your account is deactivated. Apply to your system manager.`
- `\\Files\\Accounting\\`, `\\Files\\accounting\\id.txt`

---

## 15. ModDttsEgypt — DTTS for Egypt

**Purpose:** Egyptian DTTS (Drug Tracking & Tracing System) integration — part of the Saudi SFDA system adapted for Egypt. Handles drug dispatch notifications, sale submissions, returns, and transfers through the DTTS SOAP API.

**Key Procedures (2):**
- Proc 1 (size=288): DTTS API call — constructs SOAP envelope, sends to SFDA endpoint, parses response
- Proc 2 (size=144): Response handler — processes DTTS confirmation/rejection

**Database Tables:**
- `titanksasales` — sale records submitted to DTTS

**Key Strings:**
- `<m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">`
- `<m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">`
- `<m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">`
- `<m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">`
- `<m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">`
- `<m:AcceptDispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/AcceptDispatchService">`

---

## 16. ModZatca2Wraber — ZATCA Wrapper (Saudi E-Invoicing)

**Purpose:** Wrapper for ZATCA (Zakat, Tax and Customs Authority) e-invoicing system. Handles invoice XML generation, CSID (Clearance & Sales ID) management, invoice submission, and QR code generation for Saudi Arabia compliance.

**Key Procedures (23):**
- Proc 1 (size=2108): Main ZATCA integration — builds invoice XML, generates CSID, submits to ZATCA API
- Proc 2 (size=116): CSID validation
- Proc 3-4 (sizes 32, 52): Simple config/proxy
- Proc 5 (size=88): Invoice XML builder with item details
- Proc 6 (size=168): QR code generation from invoice data
- Proc 7 (size=228): ZATCA response parser
- Proc 8 (size=240): Invoice counter management
- Proc 9-10 (sizes 56, 1064): Large invoice processing workflow
- Proc 11-23: Various helpers — XML signing, hash calculation, retry logic, B2B/B2C invoice handling

**Database Tables:**
- `titanksasales` — sales records with ZATCA fields
- Invoice counter tracking tables

**Key Strings:**
- `<invoice>`, `</invoice>`, `<invoice-data>`, `<invoice-items>`
- `<invoice-number>`, `<invoice-type>`, `<invoice-type-all>`
- `<invoice-counter>`, `<purchases-invoices-number>`, `<sales-invoices-number>`
- `<zatca-response>`, `</zatca-response>`
- `<refrenceInvoiceDate>`, `<refrenceInvoiceNumber>`
- `<buyer-data-in-case-of-b2b-invoice-only/>`
- `<qr>`, `</qr>`
- `Reload_Drugs_in_last_Invoices`
- `select invoiceid from titanksasales where`
- `invoice`, `invoiceid =`

---

## 17. ModAccFreeOne — Free/Limited Accounting Version

**Purpose:** Manages the free/limited version of the accounting module. Handles trial period tracking, activation code validation, license management, and feature restrictions for non-premium users.

**Key Procedures (19):**
- Proc 1 (size=112): Trial period check — validates activation status
- Proc 2-5 (sizes 48-64): Activation code validation
- Proc 6 (size=60): License status check
- Proc 7-10 (sizes 60 each): Feature restriction enforcement
- Proc 11 (size=64): Trial counter increment
- Proc 12-19: Activation persistence, deactivation handling, network activation

**Database Tables:**
- `wzaccfreetree` — free accounting tree structure
- `Files\accounting\id.txt` — activation ID
- `Files\DBI\mandoup.phy` — mandoup (activation) data

**Key Strings:**
- `License`, `License number is empty`, `License number used by someone else`
- `TRial No:`, `Trial No :`
- `Temporary activation for 3 days`
- `Activate your app`, `Active up to`
- `Input activation code for mandoup`
- `Successfull activation`
- `Invalid deactivation reason`, `you choosed to remove your activation`
- `Network-activation`
- `Free Disk Space ON C:\  is`
- `MB and it is not enough for windows system`
- `Use deactivation notification for expired units.`
- `insert into wzaccfreetree (mobile,master,fary) values (`
- `if not exists( select * from wzaccfreetree where`

---

## 18. ModDrgW — Drug World Database

**Purpose:** Manages the comprehensive drug reference database (DRG World). Contains drug names, active ingredients, therapeutic categories, drug interactions, and combination formulas. Serves as the pharmaceutical knowledge base.

**Key Procedures (13):**
- Proc 1 (size=148): Drug name lookup from DRG database
- Proc 2 (size=128): Active ingredient search
- Proc 3 (size=96): Drug similarity search
- Proc 4 (size=72): Drug category lookup
- Proc 5 (size=44): Simple wrapper
- Proc 6 (size=68): Drug interaction check
- Proc 7 (size=84): Combination formula lookup
- Proc 8 (size=176): Drug interaction report generation
- Proc 9 (size=144): Therapeutic category listing
- Proc 10-11 (sizes 64, 60): Data import/export
- Proc 12 (size=656): Large drug comparison engine — finds similar drugs, compares active ingredients
- Proc 13 (size=384): Drug classification report

**Database Tables:**
- `drgserver` — drug server data (remote drug info)
- `DRG320.PHY` — DRG320 drug database
- `Files\DBI\drgw.phy` — DRG World data file

**Key Strings:**
- `DRUGS.PHY`, `DRG320.PHY`, `DRGINFO loading ..`
- `Drg Last edited loading ..`, `Drgw loading ..`
- `Drugs =`, `Drugs Similar to`
- `Duplicate names with same formula`
- `Near similars`, `Similarity`
- `Bring active ingredient`
- `gdb.drgw.rar`, `.drgw.rar`
- `group.combined.txt`
- Drug interaction strings: `Beta Blockers like Atenolol...`, `Anti-hypertensive.Combined...`
- `insert into drgserver (datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport)`
- `select * from drgserver where silsila = N'`

---

## 19. ModBackupMonthly — Monthly Backup & Archive

**Purpose:** Monthly database backup, archival, and restoration system. Compresses sales data into monthly archives, manages backup rotation, handles internet backup uploads, and provides data restoration from archives.

**Key Procedures (13):**
- Proc 1 (size=188): Monthly archive initialization
- Proc 2 (size=48): Archive status check
- Proc 3 (size=1300): Large proc — monthly data archival with compression (creates ZIP from sales data)
- Proc 4 (size=1260): Archive extraction/restoration
- Proc 5 (size=1292): Internet backup upload (FTP-based)
- Proc 6 (size=3208): Largest proc — full monthly closing workflow (archive, compress, upload, verify)
- Proc 7 (size=1504): Backup rotation and cleanup
- Proc 8 (size=112): Backup status report
- Proc 9 (size=900): Archive data verification
- Proc 10 (size=3240): Alternative monthly closing path
- Proc 11 (size=3928): Another large proc — handles edge cases in monthly closing
- Proc 12 (size=320): Archive-to-FTP workflow
- Proc 13 (size=92): Simple cleanup

**Database Tables:**
- `titanksasales` — sales records being archived
- `titanksastock` — stock snapshot at archive time
- `Files\Archive\Input\`, `Files\Archive\Output\` — archive staging
- `Files\DB\Restore.bak` — restore point
- `Files\DBI\internet-backup.txt` — backup metadata

**Key Strings:**
- `Monthly`, `Monthly closing`, `Archive old sales invoices`
- `Archive not opened`, `Empty archive`, `Invalid archive`
- `Back up is ignored by 'no-backup' folder`
- `Backup folder`, `Clean backups`
- `CompressArchive`, `Create Internet backup`
- `Cannot init deflate compressor`, `Cannot init inflate decompressor`
- `Error compressing`, `Error decompressing`, `Error reading archive`
- `FORCEARCHIVE`, `ForceArchive`, `OpenArchive`
- `Drugs stock before archive was :`
- `Files\Archive\Input\`, `Files\Archive\Output\`
- `Files\DB\Restore.bak`
- `Labirdo\Titan3-Backup\` — backup directory structure
- `Labirdo\Titan3-Backup\Monthly\`, `Labirdo\Titan3-Backup\Daily\`
- `*.zip`, `C:\ftpdbi.zip` through all drive letters
- `ftp-zip-upload`, `/Monthly/St/`
- `<monthly-data>`, `</monthly-data>`
- `Titan ZuLastArchiveCheck`

---

## 20. ModDrugsUnify — Drug Name Unification

**Purpose:** Deduplicates and unifies drug names across the database. Identifies duplicate entries (same drug with different names), merges records, and maintains a unified drug name reference. Handles combination drugs and similar formulations.

**Key Procedures (10):**
- Proc 1 (size=416): Drug name comparison engine — compares names using string similarity
- Proc 2 (size=1028): Bulk unification — processes all drugs, identifies duplicates
- Proc 3 (size=124): Drug record merge — combines two drug records
- Proc 4 (size=2556): Largest proc — comprehensive unification workflow with user interaction
- Proc 5 (size=2208): Alternative unification path — handles edge cases
- Proc 6 (size=392): Unification verification
- Proc 7-8 (sizes 44, 68): Simple helpers
- Proc 9 (size=68): Duplicate detection
- Proc 10 (size=1196): Large proc — export/import of unified drug data

**Database Tables:**
- `titanstock` — main drug stock table
- `titanksastock` — sales stock table
- `drgserver` — drug server reference
- `wzdrugs` — working drug data

**Key Strings:**
- `Duplicate names with same formula`
- `Clean duplicate barcode`
- `Download duplicated barcode blocking tool`
- `Export to a merge file`
- `Import the new items from the Merge file`
- `Near similars`
- Drug combination categories: `Anti-Diabetic.Combined...`, `Anti-hypertensive.Combined...`
- `NSAID.Analgesic.Combination`, `Antibiotic.Macrolide.combined...`
- Various therapeutic combination category names

---

## 21. ModOuterConnections — External System Connections

**Purpose:** Manages connections to external APIs and web services. Handles ETA (Egyptian Tax Authority) API, ZATCA API, SFDA (Saudi FDA) API, and DrugEye integration. Provides a unified interface for external system communication.

**Key Procedures (18):**
- Proc 1 (size=168): External API connection setup
- Proc 2 (size=4): Placeholder
- Proc 3 (size=168): API request execution
- Proc 4 (size=176): Response parsing
- Proc 5-18: Various API integrations — ETA, ZATCA, SFDA, DrugEye

**Database Tables:**
- `Files\DB\server.connection.report.txt` — connection logs

**Key Strings:**
- `https://api.invoicing.eta.gov.eg` — ETA API
- `https://api.preprod.invoicing.eta.gov.eg` — ETA pre-production
- `http://www.drugeye.pharorg.com/rsd-api/start.aspx` — DrugEye
- `http://api.qrserver.com/v1/create-qr-code/?` — QR code generation
- `https://chart.googleapis.com/chart?` — Google Charts
- `/api/v1/receipts/recent`, `/api/v1/receiptsubmissions`
- `/api-sign.aspx`
- `ADODB.connection`, `ConnectionTimeout`
- `db_9ffe55_apifordrugeye`
- `No internet connection`
- `Failed to copy QR from saturn path to API path`
- `update zatca api`
- `Capital account reports`, `Capital stats and pharmacy overview`

---

## 22. ModSaturn — Saturn ZATCA Tool

**Purpose:** Wrapper for the Saturn ZATCA integration tool — an external .NET executable that handles ZATCA digital signing, CSID generation, and invoice submission. Saturn is a separate executable (`saturn.exe`) that Titan calls via command line.

**Key Procedures (24):**
- Proc 1 (size=484): Saturn process launch — starts `saturn.exe` with parameters
- Proc 2 (size=104): Saturn status check
- Proc 3-4 (sizes 88, 336): Parameter passing to Saturn
- Proc 5 (size=240): Response file reading from Saturn output
- Proc 6-7 (sizes 240, 344): Invoice XML preparation for Saturn
- Proc 8 (size=68): Saturn version check
- Proc 9-24: Various Saturn interaction — file management, counter tracking, hash verification

**Database Tables:**
- `Files\DBI\netcounter.phy` — network counter for Saturn
- `Files\Zatca\` — ZATCA data directory
- `Files\Zatca\saturnonboard.exe` — Saturn onboarding tool
- `Files\Zatca\xmlauth3.txt` — ZATCA authentication data

**Key Strings:**
- `C:\saturn\saturn.exe`, `C:\saturn\saturn2.exe`
- `C:\saturn\BouncyCastle.Crypto.dll`
- `C:\saturn\MessagingToolkit.QRCode.dll`
- `C:\saturn\SDKNETFrameWorkLib.dll`
- `C:\saturn\System.Net.Http.dll`
- `C:\saturn\Zatca\computer-1\invoices\`
- `C:\saturn\help\summer.txt`, `C:\saturn\help\xmlauth3.txt`
- `C:\saturn\zatca\computer-1\lastdata\counter.txt`
- `C:\saturn\zatca\computer-1\lastdata\hash.txt`
- `Hash Check Failed`, `HashDigestLength`
- `Sending to zatca`
- `Re-start upload counter`, `Restart upcounter`
- `Zatca-response.txt`, `Zatca\B2c\`
- `\\Files\\Zatca\\saturnonboard.exe`, `\\Files\\Zatca\\xmlauth3.txt`
- HTTP URLs for downloading Saturn components

---

## 23. Modzatcasign — ZATCA Digital Signing

**Purpose:** Handles XML digital signing for ZATCA e-invoicing compliance. Creates signed XML documents using API-SIGN service, validates signatures, and manages signing certificates.

**Key Procedures (3):**
- Proc 1 (size=244): XML signing — sends unsigned XML to API-SIGN endpoint, receives signed XML
- Proc 2 (size=788): Large proc — full signing workflow including XML construction, HTTP request, response parsing
- Proc 3 (size=144): Signature validation — checks if XML has valid signature

**Database Tables:**
- `Files\DBI\inndesign.phy` — invoice design/template
- `Files\DBI\pixml.phy` — processed invoice XML
- `Files\DBI\xmlauth3.txt` — XML authentication data
- `Files\DBI\last-archive-process.xml` — last archive XML
- `Files\DBI\months.data.xml` — monthly data XML

**Key Strings:**
- `/api-sign.aspx`, `C:\api-sign.aspx`, `\api-sign.aspx`
- `signed.xml`, `phar-x.xml`
- `MSXML.DomDocument`, `MSXML2.DOMDocument`, `MSXML2.XMLHTTP`
- `Msxml2.ServerXMLHTTP.6.0`
- `text/xml; charset=utf-8`
- `Failed to sign document`
- `Entry %1 has invalid signature`
- `LoadXML`
- `Sent XML data structure is not compatible with the scheme in WSDL document`
- `http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/api-sign.rar`
- `\\DBI\\PurSales\\`, `\\Files\\DBI\\inndesign.phy`

---

## 24. FormToForm — Form Navigation

**Purpose:** Central form navigation dispatcher. Routes form transitions based on form IDs, handles form loading/unloading, and manages the reload queue for data refresh after form changes.

**Key Procedures (1):**
- Proc 1 (size=44): Single dispatcher proc with `SelectCaseByte` instructions — maps form IDs to target forms and triggers navigation. The `SelectCaseByte [02 XX]` patterns indicate a switch-case on form type/ID.

**Database Tables:** None (pure navigation logic)

**Key Strings:**
- `ReloadCurent500Inn` — reload import data
- `ReloadCurent500Oot` — reload export data
- `ReloadDailyManual` — reload daily manual entries
- `ReloadRasidCorrect500` — reload rasid corrections
- `Reload_Daily_Max` — reload daily maximum values
- `Reload_Drugs_500` — reload drug data
- `Reload_Drugs_in_last_Invoices` — refresh drugs in current invoices
- `Reload_amil_500` — reload employee data
- `Reload_mrd_500` — reload customer/supplier data

---

## Summary Table

| # | Module | Procs | Purpose | Key Tables |
|---|--------|-------|---------|------------|
| 1 | ModDisc | 10 | Discount calculation engine | storediscount, titanksasales |
| 2 | ModMarid | 4 | Customer/supplier management | Customer/supplier arrays |
| 3 | ModScreen | 3 | Screen resolution/DPI handling | None (Win32 API) |
| 4 | ModFTP | 10 | FTP file transfer client | None (WinInet API) |
| 5 | ModReBuild | 14 | Database schema migration | titanksasales, titaninn, etc. |
| 6 | VB7 | 42 | VB6 runtime compatibility | None (utility functions) |
| 7 | ModSQL | 13 | SQL database abstraction | All core tables |
| 8 | ModAmil2 | 9 | Employee/shift management | amil2.phy, AmilInfo.phy |
| 9 | ModSqlLink | 19 | Remote SQL server linking | drgserver, remotecontrol |
| 10 | ModAppType | 9 | Application mode config | titanksastock (filtered) |
| 11 | ModColors | 3 | UI color/theme settings | colors.phy |
| 12 | ModGS1Reader | 24 | GS1 barcode parsing | titanstock (barcode) |
| 13 | ModEtaWrappper | 7 | Egyptian Tax Authority API | titanksasales (uuid) |
| 14 | ModAccounting | 25 | Double-entry accounting | wzaccfreetree, accounting files |
| 15 | ModDttsEgypt | 2 | DTTS drug tracking (Egypt) | titanksasales |
| 16 | ModZatca2Wraber | 23 | ZATCA e-invoicing (Saudi) | titanksasales |
| 17 | ModAccFreeOne | 19 | Free/trial accounting | wzaccfreetree, mandoup.phy |
| 18 | ModDrgW | 13 | Drug reference database | drgserver, DRG320.PHY |
| 19 | ModBackupMonthly | 13 | Monthly backup/archive | Archive directories |
| 20 | ModDrugsUnify | 10 | Drug name deduplication | titanstock, titanksastock |
| 21 | ModOuterConnections | 18 | External API connections | server.connection.report.txt |
| 22 | ModSaturn | 24 | Saturn ZATCA tool wrapper | Files\Zatca\ |
| 23 | Modzatcasign | 3 | ZATCA XML digital signing | Files\DBI\pixml.phy |
| 24 | FormToForm | 1 | Form navigation dispatcher | None (navigation logic) |
