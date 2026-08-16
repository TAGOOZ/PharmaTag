# TITAN.W1 (Phye.exe) — Complete Business Logic Extraction

**Author:** Dr. Saleh Mansour  
**Last Version:** 2021.02.10  
**Application:** TITAN.W1 Pharmacy Management System  
**Executable:** Phye.exe (VB6 p-code)  
**Extraction Date:** 2026-08-15  

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Core Database Tables & Schema](#2-core-database-tables--schema)
3. [Module: Raz (Main Library)](#3-module-raz-main-library)
4. [Module: ModStock (Stock Management)](#4-module-modstock-stock-management)
5. [Module: ModInn (Purchases/Inbound)](#5-module-modinn-purchasesinbound)
6. [Module: ModOot (Sales/Outbound)](#6-module-modoot-salesoutbound)
7. [Module: ModPharm (Pharmacy Core)](#7-module-modpharm-pharmacy-core)
8. [Module: ModStorage (Storage/Shelf)](#8-module-modstorage-storageshelf)
9. [Module: ModUsers (User Management)](#9-module-modusers-user-management)
10. [Module: ModMony (Financial)](#10-module-modmony-financial)
11. [Module: ModBackup (Backup/Restore)](#11-module-modbackup-backuprestore)
12. [Module: ModAmil (Reports)](#12-module-modamil-reports)
13. [Module: ModMergeBarcodes (Barcode Merge)](#13-module-modmergebarcodes-barcode-merge)
14. [Module: ModTitanCloud (Cloud Sync)](#14-module-modtitancloud-cloud-sync)
15. [Module: ModPrint (Printing)](#15-module-modprint-printing)
16. [Sales Invoice Business Rules](#16-sales-invoice-business-rules)
17. [Purchase Invoice Business Rules](#17-purchase-invoice-business-rules)
18. [Drug Management Business Rules](#18-drug-management-business-rules)
19. [Price & VAT Business Rules](#19-price--vat-business-rules)
20. [Expiry Date Management](#20-expiry-date-management)
21. [User Permission System](#21-user-permission-system)
22. [E-Invoice (ZATCA/RASD)](#22-e-invoice-zatcarasd)
23. [Backup & Cloud Architecture](#23-backup--cloud-architecture)
24. [Error Messages & Conditions](#24-error-messages--conditions)
25. [Numeric Constants & Thresholds](#25-numeric-constants--thresholds)
26. [Date/Time Handling](#26-datetime-handling)
27. [Currency & Financial Formats](#27-currency--financial-formats)
28. [Barcode System](#28-barcode-system)
29. [File System Architecture](#29-file-system-architecture)
30. [Drug Interaction Database](#30-drug-interaction-database)

---

## 1. System Overview

TITAN.W1 is a comprehensive pharmacy management system built in VB6. It handles:
- **Sales & Purchase Invoicing** with full VAT/tax support
- **Stock Management** with multi-pharmacy support
- **Drug Database** with 12,000+ drugs and Drug-Drug interactions
- **E-Invoice Integration** with Egyptian ZATCA and RASD systems
- **Cloud Sync** between multiple pharmacy locations
- **Barcode Management** with multi-barcode support (up to 5 barcodes per drug)
- **Expiry Date Tracking** with partial expiry reset
- **User Permission System** with role-based access
- **Financial Accounting** with trial balance integration
- **Backup System** with daily/monthly archives

### Key Statistics
- **237 Forms** (UI screens)
- **336 Objects** (Forms, Classes, Modules, UserControls)
- **6,192 Procedures** (business logic functions)
- **26,970 String Constants**
- **124 Windows API declarations**

---

## 2. Core Database Tables & Schema

### 2.1 Primary Drug Table: `titanksastock`
```sql
CREATE TABLE titanksastock (
    DrugName    NVARCHAR(90) DEFAULT '',
    Barcode     VARCHAR(16) DEFAULT '',
    Barcode1    NVARCHAR(20) DEFAULT '',
    Barcode2    NVARCHAR(20) DEFAULT '',
    Barcode3    NVARCHAR(20) DEFAULT '',
    Barcode4    NVARCHAR(20) DEFAULT '',
    Barcode5    NVARCHAR(20) DEFAULT '',
    PriceNow    REAL DEFAULT 0,
    stock       REAL DEFAULT 0,
    minimum     REAL DEFAULT 0,
    pharmacyid  NVARCHAR(50) DEFAULT '',
    lastedit    DATETIME DEFAULT NULL,
    titanid     NVARCHAR(50) DEFAULT '',
    classy      NVARCHAR(100) DEFAULT '',
    silsilaid   NVARCHAR(50) DEFAULT '',
    ExpireId    NVARCHAR(50) DEFAULT '',
    Expire      NVARCHAR(50) DEFAULT '',
    Tips        NVARCHAR(200) DEFAULT '',
    wareprice3  NVARCHAR(100) DEFAULT '',
    -- Additional fields from drug card:
    SellDisc    REAL DEFAULT 0,       -- Sale discount
    Mohafaza    NVARCHAR(50),         -- Governorate
    Markaz      NVARCHAR(50),         -- District
    SourceIdDateTime DATETIME,        -- Source invoice date
    RequisterTel NVARCHAR(20),        -- Requester phone
    country     NVARCHAR(50)          -- Country
)
```

### 2.2 Sales Table: `titanksasales`
```sql
CREATE TABLE titanksasales (
    invoiceid   REAL DEFAULT 0,
    IdDateTime  DATETIME,
    Quant       REAL DEFAULT 0,
    DrugName    NVARCHAR(90),
    SellDisc    REAL DEFAULT 0,
    Tips        NVARCHAR(200),
    Expire      NVARCHAR(50),
    Minimum     REAL DEFAULT 0,
    price       REAL DEFAULT 0,
    PharmacistTel NVARCHAR(20),
    Mohafaza    NVARCHAR(50),
    Markaz      NVARCHAR(50),
    SourceIdDateTime DATETIME,
    RequisterTel NVARCHAR(20),
    country     NVARCHAR(50)
)
```

### 2.3 Purchase/Inbound Table: `titaninn`
- Stores all inbound invoice items
- Fields mirror sales table with purchase-specific additions

### 2.4 Needs Table: `titanneed`
```sql
CREATE TABLE titanneed (
    drugname    NVARCHAR(90),
    datee       DATETIME,
    silsilaid   NVARCHAR(50),
    minimum     REAL DEFAULT 0,
    pharmacyid  NVARCHAR(50),
    classy      NVARCHAR(100),
    stock       REAL DEFAULT 0
)
```

### 2.5 User Action Audit: `TitanUserAction`
```sql
CREATE TABLE TitanUserAction (
    drugname    NVARCHAR(90),
    typevalue   NVARCHAR(50),
    oldvalue    NVARCHAR(100),
    newvalue    NVARCHAR(100),
    mobile      NVARCHAR(20),
    namee       NVARCHAR(100),
    curbarcode  NVARCHAR(50),
    curprice    REAL,
    units       NVARCHAR(20),
    datee       DATETIME
)
```

### 2.6 Store Discount Table: `storediscount`
- Stores discount configurations per item
- Created if not exists during invoice operations

### 2.7 Chain Pharmacy Tables: `ChainBuyUsers`, `ChainBuyStore`
- `ChainBuyUsers`: PharmacistTel, username linking
- `ChainBuyStore`: Drug sharing between chain pharmacies

### 2.8 Customer Table: `taronlineeg`
- Customer registration data
- Fields: NameEnglish, mobile, CreateDate, GLN

### 2.9 User Source Update: `usersourceupdate`
- Tracks drug updates from external sources
- Fields: id, drugname, Datee

### 2.10 Remote Control: `remotecontrol`
- Inter-pharmacy communication
- Used for cloud sync operations

### 2.11 Sales Archive: `farysales`
- Archived sales invoices
- Queried by mobile number

### 2.12 Drug Server: `drgserver`
- Drug database server sync

### 2.13 External Drug DB: `wzdrugs`, `wzdrugs2`, `wzphar`
- External drug reference data

---

## 3. Module: Raz (Main Library) — 379 Procedures

**Location:** `pcode_disasm.txt` lines 5031+  
**Header:** `Raz vb6 liberary made by dr. saleh mansour last version 2021.02.10`

### 3.1 Core Functions

#### Data Loading & Caching
- **`ReloadAllData2`** — Master data reload (takes significant time)
- **`Reload_Drugs_500`** — Load first 500 drugs from database
- **`Reload_Drugs_in_last_Invoices`** — Load drugs appearing in recent invoices
- **`Reload_amil_500`** — Load first 500 report entries
- **`Reload_mrd_500`** — Load first 500 MRD entries
- **`ReloadCurent500Inn`** — Load first 500 inbound items
- **`ReloadCurent500Oot`** — Load first 500 outbound items
- **`ReloadDailyManual`** — Load daily manual entries
- **`Reload_Daily_Max`** — Load daily maximum values
- **`ReloadRasidCorrect500`** — Load first 500 balance corrections

#### Invoice Number Generation
- **`AutoId=`** — Auto-generate invoice ID
- **`PharmacyId=`** — Get pharmacy identifier
- **`SilsilaId=`** — Get serial chain ID

#### Startup Operations
- **`Titan Extract_startup_Price`** — Extract and apply startup pricing
- **`Titan Check_default_Sales`** — Validate default sales configuration
- **`Titan CorrectStockForAll`** — Correct stock across all pharmacies
- **`Titan ZuFillEmptyNameIftheresStock`** — Fill empty drug names if stock exists

### 3.2 Validation Functions

- **Drug Name Validation:** Must be at least 3 characters long
- **Barcode Validation:** varchar(16), can have up to 5 barcodes per drug
- **GLN Validation:** Must be 13 digits, numeric only
- **Date Validation:** Various format checks
- **Stock Validation:** Check for negative stock

---

## 4. Module: ModStock (Stock Management) — 165 Procedures

**Location:** `pcode_disasm.txt` line 1999+

### 4.1 Stock Operations

#### Stock Addition
```
INSERT INTO titanksastock (drugname, lastedit, pharmacyid, price, stock, barcode, titanid) VALUES(...)
INSERT INTO titanstock (drugname, datee, silsilaid, minimum, pharmacyid, classy, stock) VALUES(...)
```

#### Stock Updates
```
UPDATE titanksastock SET stock = [new_value] WHERE drugname = '[name]'
UPDATE titanstock SET stock = [new_value] WHERE drugname = '[name]'
```

#### Stock Queries
```
SELECT drugname FROM titanksastock WHERE ...
SELECT drugname FROM titanstock WHERE ...
```

#### Stock Deletion
```
DELETE FROM titanksastock WHERE ...
```

### 4.2 Stock Business Rules

1. **Stock cannot go negative** — System prevents sales that would result in negative stock
2. **Minimum stock tracking** — Each drug has a configurable minimum threshold
3. **Stock amnesty** — Special handling for stock corrections: "Due to stock amnesty"
4. **False stock detection** — "These drug have False stock" flag
5. **Stock zero detection** — "Stock is zero" status check
6. **Multi-pharmacy stock** — Stock tracked per pharmacy location

### 4.3 Stock Calculation Fields
```
TttPak2       — Package quantity
TttPart2      — Part quantity  
TttBomus2     — Bonus quantity
TttDiscMain   — Main discount
TttDiscadd3   — Additional discount
TttExpire2    — Expiry date
TttNotVatedUnit — Non-vatted unit price
TttNotvatedAll  — Non-vatted total
TttBuyValue3  — Buy value
TttEgmaly2    — Total value
```

---

## 5. Module: ModInn (Purchases/Inbound) — 71 Procedures

**Location:** `pcode_disasm.txt` line 2918+

### 5.1 Purchase Invoice Operations

#### Creating Purchase Invoices
- Purchase invoices can be created as:
  - New purchase invoice
  - Transfer from another invoice type
  - Purchase return invoice

#### Purchase Data Fields
```
PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,SourceIdDateTime,price
PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,Tips,RequisterTel,country,price
```

### 5.2 Purchase Business Rules

1. **Purchase Discount Tracking** — `Buy Discount` field tracked per item
2. **Purchase Price Types:**
   - `Actual purchase price` — Real cost paid
   - `Calculated purchase price` — System-calculated cost
   - `Real purchase price` — Verified cost
3. **Last Purchase Apply:** "Apply last purchase expire date for current invoice items"
4. **Purchase Discount Apply:** "Apply the discount of the last purchase"
5. **Purchase Price Edit:** "Edit the total selling price in purchases for old invoices"

### 5.3 Purchase Validation
- Cannot purchase from same pharmacy
- Expiry date must be valid
- Quantity must be positive
- Drug must exist in system

---

## 6. Module: ModOot (Sales/Outbound) — 105 Procedures

**Location:** `pcode_disasm.txt` line 2813+

### 6.1 Sales Invoice Operations

#### Sales Data Structure
```
(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)
```

#### Key Sales Fields
- `invoiceid` — Invoice number
- `Quant` — Quantity sold
- `SellDisc` — Sale discount percentage
- `price` — Unit price
- `Expire` — Expiry date of sold batch
- `Tips` — Notes/comments
- `PharmacistTel` — Pharmacist identifier

### 6.2 Sales Business Rules

1. **Cannot sell expired products** — "Any product cannot be sold to the person registered as dead"
2. **Prevent sale of recalled drugs** — "Drugs prohibited for sale"
3. **Stock check before sale** — "Not Enouph Stock" validation
4. **Discount validation** — "Abnormal Discount" detection
5. **Invoice copying** — "Copy the invoice to sales invoice" / "Copy the invoice to a sales return invoice"
6. **Invoice modification tracking** — "Modified invoices" logging

### 6.3 Sales Return Logic
- Sales returns reference original invoice
- Return quantity cannot exceed original
- Return creates reverse entry in sales table
- "Sales returnes" tracking

### 6.4 Sales Discount Types
```
Disc in                    — Discount on input
Disc out                   — Discount on output  
Cash discount              — Cash payment discount
Wholesale discount         — Bulk purchase discount
Sale discount for tax items — Tax-item specific discount
```

---

## 7. Module: ModPharm (Pharmacy Core) — 12 Procedures

**Location:** `pcode_disasm.txt` line 1637+

### 7.1 Drug Search by Barcode
```sql
SELECT * FROM titanksastock 
WHERE Barcode = N'[barcode]'
   OR Barcode1 = N'[barcode]'
   OR Barcode2 = N'[barcode]'
   OR Barcode3 = N'[barcode]'
   OR Barcode4 = N'[barcode]'
   OR Barcode5 = N'[barcode]'
```

### 7.2 Drug Form Types
The system supports extensive pharmaceutical forms:
```
TAB, CAPS, INJ, DROPS, SYRUP, CREAM, OINT, GEL, LOTION, 
SUSP, POWDER, SPRAY, INHALER, PATCH, SUPP, EYE DROPS, 
NASAL DROPS, VAGINAL, RECTAL, etc.
```

### 7.3 Drug Classification System
Hierarchical classification with categories like:
```
Analgesic&Anti-inflammatory Agents -> Analgesic Anti-Pyretic Drugs
Anti-Diabetic -> Secretagogues -> Sulfonylurea
Anti-hypertensive -> Beta blocker -> Selective B1
```

---

## 8. Module: ModStorage (Storage/Shelf) — 154 Procedures

**Location:** `pcode_disasm.txt` line 2009+

### 8.1 Storage Operations

#### Storage Locations
```
\Files\StockNow           — Current stock data
\Files\Archive\           — Archived data
\Files\Archive\Input\     — Purchase archives
\Files\Archive\Output\    — Sales archives
```

#### Storage Search
- "Search for a medicine in the storage shelf screen"
- "Search for a medicine in the search screen"

### 8.2 Storage Business Rules

1. **Shelf Organization** — Items organized by shelf location
2. **Storage Temperature** — "Storage temperature" tracking
3. **Minimum Stock Alert** — Configurable minimum thresholds
4. **Expiry Detection** — "Expiry detection" scanning
5. **Stagnant Detection** — "Stagnant detection" for slow-moving items

---

## 9. Module: ModUsers (User Management) — 39 Procedures

### 9.1 User Roles & Permissions

#### Permission Levels
- `Give permissions of admin user` — Full access
- `Give permissions of normal user` — Limited access
- `Login as super admin` — Emergency access
- `Log in as a manager without logging off current user` — Override
- `Log in as Technical Support` — Support access
- `Login with management account` — Management level
- `Login with operations account` — Operations level
- `Login one time` — Single session

#### Permission Strings
```
*AddNewUser*
*ChangeUserAuths*
*authentication*
```

### 9.2 User Actions Audit
```sql
INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)
```

### 9.3 User Business Rules

1. **Username Validation:**
   - Cannot be null
   - Cannot be empty
   - Must be unique

2. **Password Rules:**
   - "Password required"
   - "Password is empty" error
   - "Invalid password" error
   - "Wrong password !" error
   - Default password: "3030"

3. **User States:**
   - Active/Passive status
   - "Your user has been temporarily blocked"
   - "Your account is deactivated"
   - "Sender user is passive"

4. **User Operations:**
   - "Change password" / "Change  password"
   - "Forgot  password"
   - "Change my password"
   - "Add stakeholder user"

### 9.4 Chain Pharmacy Users
```sql
SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%'
INSERT INTO ChainBuyUsers(...)
```

---

## 10. Module: ModMony (Financial)

### 10.1 Financial Operations

#### Invoice Tracking
```
"(*)invoice(*): (*)"  — Invoice reference format
"Invoice.b2b.Number." — B2B invoice numbering
"Last output Fatoora = " — Last invoice number
"Internal invoice number" — Titan internal tracking
```

#### Financial Reports
- "Cash delivery reports between work periods"
- "Cash flow" statements
- "Cash movement today"
- "Capital account reports"
- "Account statement"
- "Trial Balance"

### 10.2 Payment Types
```
Cash                    — Cash payment
Cash PC                 — Cash payment card
Cards paid              — Card payment
Paid                    — Fully paid
Payable amount          — Amount due
Relayed amount          — Deferred amount
```

### 10.3 Financial Calculations
```
"Net with VAT"          — Net amount including VAT
"Total VAT"             — Total tax amount
"Total Disc"            — Total discount
"Total points"          — Loyalty points
"Actual cost"           — Real cost
"Actual purchase price" — Purchase cost
"Calculated purchase price" — Computed cost
```

---

## 11. Module: ModBackup (Backup/Restore) — 43 Procedures

### 11.1 Backup Architecture

#### Backup Locations
```
Labirdo\Titan3-Backup\Daily\          — Daily backups
Labirdo\Titan3-Backup\Monthly\        — Monthly archives
Labirdo\Titan3-Backup\Export\         — Export data
Labirdo\Titan3-Backup\xj\             — Compressed backups
Labirdo\Titan3-Backup\images\         — Image files
Labirdo\Titan3-Backup\tars-copy\      — Transfer archives
```

#### Key Backup Files
```
\Files\DBI\*.bak                       — Database backups
\Files\DB\Restore.bak                  — Restore point
Labirdo\Titan3-Backup\History.txt      — Backup history
DBI\internet-backup.txt                — Internet backup config
```

### 11.2 Backup Business Rules

1. **Backup Skip:** "Back up is ignored by 'no-backup' folder"
2. **Backup Cleanup:** "Clean backups" — Remove old backups
3. **Internet Backup:** "Create Internet backup"
4. **Cloud Storage:** "Cloud storage of stock"
5. **USB Backup:** "Save a bakeup on the usb flash"
6. **Restore:** "Restore.exe" / "Run restore.exe to restore your data"
7. **Backup Label:** "This is Titan backup maked by [user]"

### 11.3 Backup Operations
```
Save a backup
Save - Unsave
Save by F9 ; Unsave by F12
Restore backup
Restore a deleted invoice
```

---

## 12. Module: ModAmil (Reports) — 44 Procedures

### 12.1 Report Types

#### Sales Reports
- "Sales reports"
- "Sales reports during the day"
- "Sales volume reports"
- "Total sales and profit reports"
- "Salses reports" (variant spelling)

#### Purchase Reports
- "Purchase reports"
- "Purchases reports"
- "Acceptance of purchase invoices from warehouses"

#### Stock Reports
- "Stock details"
- "Medicines that have more than one international barcode"
- "Medicines whose expiry date has changed automatically"
- "Medicines with large minimum rate"
- "Medicines with messages"

#### Financial Reports
- "Capital stats and pharmacy overview"
- "Capital account reports"
- "Cash delivery reports between work periods"
- "Trial Balance"

### 12.2 Report Parameters
```
"Current task purchases of date  "
"Current task sales of date  "
"Bring all invoices"
"Bring invoices"
"Bring company name"
```

---

## 13. Module: ModMergeBarcodes (Barcode Merge) — 15 Procedures

**Location:** `pcode_disasm.txt` lines 5675-5689

### 13.1 Barcode Operations

#### Multi-Barcode System
- Each drug can have up to 5 barcodes (Barcode, Barcode1-5)
- "An international barcode common to more than one drug" detection
- "An international barcode with an incorrect structure" validation
- "Medicines that have more than one international barcode" listing

#### Barcode Types
- International barcode (GTIN)
- Short code (internal)
- Custom barcodes
- "Short Codes" management

### 13.2 Barcode Validation
```
Barcode varchar(16) default ''
- Must be valid format
- Checked against all 5 barcode fields
- Duplicate detection across drugs
```

### 13.3 Barcode Operations
```
"Add barcode"
"Cancel barcode blocking"
"Block barcode from usage"
"Clean duplicate barcode"
"Remove duplicate barcodes for items"
"Define barcodes block"
"Apply barcode printing to all items"
"Apply barcode printing to medicines without international barcode"
```

---

## 14. Module: ModTitanCloud (Cloud Sync) — 16 Procedures

**Location:** `pcode_disasm.txt` lines 6149-6152

### 14.1 Cloud Operations

#### Cloud URLs
```
/titan-users/allinone/data/
/titan-users/allinone/mobiles/
/titan-users/by-dos/
/titan-users/data-for-sale/avros/egypt/
/titan-users/data-for-sale/avros/saudi/
/titan-users/data-for-sale/avros/world/
/titan-users/floor2/
/titan-users/titan-mobile/files/
```

#### Cloud Configuration
```
Mobile number for cloud connectivity
Mobile number for current cloud connectivity
Link with google drive
Send to google drive
Set google drive folder
```

### 14.2 Cloud Business Rules

1. **Upload Operations:**
   - "Upload the drug database to the cloud storage"
   - "Upload to mobile"
   - "Upload allinone"
   - "Upload Merge File"
   - "Upload zipped DBI"

2. **Download Operations:**
   - "Download" data
   - "Download Avast Antivirus"
   - "Download deleted files recovery software"
   - "Download duplicated barcode blocking tool"

3. **Sync Rules:**
   - "Sync list cannot be receieved"
   - "Share between my group - Show"
   - "Share between my group - upload"
   - "Share data"

---

## 15. Module: ModPrint (Printing) — 70 Procedures

### 15.1 Print Operations

#### Print Types
- "Print a barcode for this item individually"
- "Print barcode for this drug"
- "Print doses"
- "Print on A4 paper"
- "Print A5 Paper"
- "Print shelf label"
- "Print statements"
- "Print the attendance and departure barcode"
- "Print the invoice once it is saved"
- "Print this invoice in sales invoice form"

#### Print Settings
- "Printer settings in titan"
- "Printer settings in windows"
- "Barcode label settings"
- "Barcode options"
- "Choose a print model"

### 15.2 Barcode Paper Types
```
"Types of barcode paper compatible with Titan"
"Input 1 for non splitted label, 2 for splitted label"
"Code 128"
```

### 15.3 Print Business Rules
1. **Drawer Control:**
   - "Open drawer while saving invoice"
   - "Open the drawer connected to the computer"
   - "Open the drawer connected to the printer"
   - "Drawer connected to the computer"
   - "Drawer connected to the printer"

2. **Print Triggers:**
   - "Print the invoice once it is saved"
   - Auto-print on specific conditions

---

## 16. Sales Invoice Business Rules

### 16.1 Sales Flow
1. Customer selection or "RANDOM CLIENT"
2. Drug search by:
   - Barcode reader ("Add an item by barcode reader")
   - Manual search ("Add an item by Manual search")
   - Name search ("Search by trade name")
   - Invoice number ("Search by invoice number")

3. Quantity entry
4. Price verification
5. Discount application
6. VAT calculation
7. Invoice save (F9)
8. Optional print
9. Optional drawer open

### 16.2 Sales Validation Rules

| Rule | Message |
|------|---------|
| Stock check | "Not Enouph Stock" |
| Expiry check | "Product has expired." |
| Price validation | "Abnormal Discount" |
| Drug status | "Status of this drug is passive" |
| Drug prohibition | "Drugs prohibited for sale" |
| Minimum quantity | Quantity must be > 0 |
| Invoice number | Must be unique |

### 16.3 Sales Invoice States
```
Saved                    — Invoice saved
Unsaved                  — Invoice not yet saved
Un save                  — Revert save
Copy me to another location — Duplicate invoice
Transfer to sales return — Convert to return
Transfer to purchases   — Convert to purchase
```

### 16.4 Sales Calculation
```
Subtotal = Sum(Quantity × Unit Price)
Discount = Subtotal × (SellDisc / 100)
VAT = (Subtotal - Discount) × (VAT% / 100)
Total = Subtotal - Discount + VAT
```

---

## 17. Purchase Invoice Business Rules

### 17.1 Purchase Flow
1. Supplier selection
2. Drug search/entry
3. Quantity entry
4. Price entry
5. Expiry date entry
6. Batch number entry
7. Invoice save

### 17.2 Purchase Validation

| Rule | Message |
|------|---------|
| Supplier check | "Company not found" |
| Duplicate batch | "This batch number was used before with a different expire date" |
| Same pharmacy | Cannot purchase from self |
| Price validation | "Actual purchase price" vs "Calculated purchase price" |

### 17.3 Purchase Types
```
As a new purchase invoice
As a new purchase return invoice
Transfer to purchases
Transfer to purchase return
```

### 17.4 Purchase Calculations
```
"Buy Discount"           — Purchase discount
"BuySum"                 — Purchase total
"Discadd"                — Additional discount
"Recalculate DiscADD In Purchases" — Recalculation trigger
```

---

## 18. Drug Management Business Rules

### 18.1 Drug Card Fields
```
DrugName nvarchar(90) default ''
Barcode varchar(16) default ''
PriceNow real default 0
stock real default 0
minimum real default 0
classy nvarchar(100) default ''
silsilaid nvarchar(50) default ''
ExpireId nvarchar(50) default ''
Expire nvarchar(50) default ''
Tips nvarchar(200) default ''
wareprice3 nvarchar(100) default ''
```

### 18.2 Drug Operations

#### Add/Modify
```
"Add new drug"
"Modify drug data"
"Modify drugs data"
"Delete drug"
"Save drug data"
"Obtain data for this drug from another drug"
```

#### Search
```
"Search for a medicine in the search screen"
"Approximate search screen"
"Near similars"
"Alternatives"
"This item alternatives"
```

### 18.3 Drug Validation Rules

1. **Name Validation:**
   - "Drug name must be at least 3 characters long"
   - "The name contain letters"
   - "Duplicate names with same formula" warning

2. **Price Validation:**
   - Price must be > 0
   - "New Price for [drug]"
   - "Input new Price for [drug]"

3. **Stock Validation:**
   - Stock cannot be negative
   - "Medicines with large minimum rate" warning

4. **Expiry Validation:**
   - Expiry date cannot be in the past
   - "Expiry Date cannot exceed Production Date more than 7 years"

### 18.4 Drug Status
```
Active                    — Drug available
Passive                   — Drug blocked
*DELETED*                 — Drug deleted
THISDRUGHASDELETED-       — Deleted marker
"THIS DRUG HAS DELETED"   — Deletion message
```

### 18.5 Drug Pricing Types
```
Price                      — Base price
Price before tax           — Pre-VAT price
Price includes Vat         — VAT-inclusive price
Price+vat                  — Price plus VAT
Price-Vat                  — Price minus VAT
Price.extra.1 to Price.extra.4 — Extra price tiers
Temp price                 — Temporary price
Wasfaty Price              — Wasfaty platform price
Sale price                 — Selling price
Sales Price Per Pack       — Pack selling price
```

---

## 19. Price & VAT Business Rules

### 19.1 VAT Configuration

#### VAT Operations
```
"Add or Remove Vat"
"Change Vat status"
"Change tax value"
"Change value of VAT for tax items"
"Changing tax value with final price"
"Cancellation of the vat with an increase in the price of items"
"Copy the VAT as it is to the item cards for the current invoice"
"Manually resetting the Vat value in old invoices"
"Re-apply vat on invoices"
"Reset-old-vat"
```

#### VAT Types
```
TttNotVatedUnit            — Non-vatted unit price
TttNotvatedAll             — Non-vatted total
Vat%                       — VAT percentage
Vat.No                     — VAT invoice number
```

### 19.2 Price Update Rules

1. **Price Change Flow:**
   - "New Price for [drug]"
   - "Input new Price for [drug]"
   - "Price change" logged
   - User permission required

2. **Price Copy Operations:**
   - "Copy the price as it is to the item card for the current invoice"
   - "Copy the high price to the item card for the current invoice"
   - "Restore item price before this invoice"

3. **Discount Types:**
   ```
   "Discount by currency"            — Fixed amount discount
   "Discount by percent of profit value" — % of profit
   "Discount by percent of total value"  — % of total
   "Apply a sale discount for tax items" — Tax item discount
   "Cancel discount"                 — Remove discount
   "Clean sale discount for all items" — Clear all discounts
   "Local discount"                  — Location-specific
   "Extra Discount"                  — Additional discount
   ```

### 19.3 VAT Reporting
```
"Quarterly VAT report"
"VatFile-" + date format
"VatFile-Result.txt"
\Files\Accounting\Vat-reports\
```

---

## 20. Expiry Date Management

### 20.1 Expiry Date Formats
```
YYYY-MM-DD
YY-MM-DD
YYMMDD
YYYYMMDD
YY-MM
YYYY-MM
YY.MM.DD
```

### 20.2 Expiry Operations

#### Detection
```
"Expiry detection"           — Find expiring items
"Check expiration date"      — Validate expiry
"Expired product (this operation cannot be performed)" — Blocked operation
```

#### Correction
```
"Edit Expiry date with the latest purchase expiry date"
"Edit this item expiry date"
"Correct expiry dates after extand"
"Correction of dates after extension of validity"
"Extension of expiry date"
"Set expiry dates"
"Change expiration dates"
"Reset Expire for this invoice"
"Apply last purchase expire date for current invoice items"
```

#### Partial Reset
```
"Expire paritaly reset"      — Reset expiry for specific batches
"ExpireId"                   — Expiry batch identifier
```

### 20.3 Expiry Business Rules

1. **Maximum Expiry:** "Expiry Date cannot exceed Production Date more than 7 years"
2. **Past Expiry:** Cannot sell expired products
3. **Expiry Tracking:** Each batch tracked separately
4. **Auto-Expiry:** "Medicines whose expiry date has changed automatically"
5. **Partial Reset:** Allows resetting expiry for specific batches without affecting others

---

## 21. User Permission System

### 21.1 User Levels
```
Super Admin       — Full system access
Admin             — Administrative access
Manager           — Management access
Pharmacist        — Standard pharmacy access
Staff             — Limited access
Technical Support — Support access
Read-only         — View only
```

### 21.2 Permission Areas

| Area | Permissions |
|------|------------|
| Sales | Create, Edit, Delete, Print, Return |
| Purchases | Create, Edit, Delete, Print, Return |
| Stock | View, Edit, Correct |
| Prices | View, Edit, Change VAT |
| Users | Add, Edit, Delete, Permissions |
| Reports | View, Print, Export |
| Settings | View, Edit |
| Backup | Create, Restore |
| Cloud | Upload, Download, Sync |

### 21.3 Permission Validation
```
"Stakeholder is unauthorized for this operation"
"User is not authorized for this service. Apply to your firm."
"You are not authorized to use this service."
"The stakeholder is not authorized to supply for this drug."
"This stakeholder is not authorized for human drugs."
"This stakeholder is not authorized for veterinary drugs."
```

---

## 22. E-Invoice (ZATCA/RASD)

### 22.1 ZATCA Integration

#### XML Auth Structure
```xml
<user>
  <userid>[ID]</userid>
  <username>[NAME]</username>
  <password>[PASS]</password>
  <authid>[AUTH]</authid>
</user>
```

#### E-Invoice JSON Structure
```json
{
  "activityCode": "...",
  "branchCode": "...",
  "companyTradeName": "...",
  "taxableItems": [...],
  "commercialDiscountData": [...],
  "itemDiscountData": [...],
  "unitPrice": 0.0,
  "totalSales": 0.0,
  "totalCommercialDiscount": 0.0,
  "totalItemsDiscount": 0.0,
  "extraReceiptDiscountData": [...],
  "salesIssuedDateTime": "..."
}
```

### 22.2 RASD Integration

#### RASD Configuration
```
"Registration in the second stage of the electronic invoice"
"View operations reports on the Rasd website"
"Upload to RSD"
"Wait for rsd integration"
```

#### RASD XML Tags
```
<buyer-vat-number>
<seller-vat-number>
<drugs-stock-cost-novat>
<drugs-stock-cost-withvat>
<masrofat-vat>
<purchases-vat>
<purchases-with-vat>
<sales-vat>
<sales-with-vat>
<total-Cost-no-vat>
<total-Cost-with-vat>
```

### 22.3 E-Invoice Business Rules

1. **Registration:** "Register your app with technical support"
2. **GLN Format:** "Number Composed of 14 digit"
3. **Invoice Numbering:** "Invoice.b2b.Number."
4. **Response Codes:**
   - "Status=200 all things runs well!"
   - "Status=202 all things runs well! with these warnings"

---

## 23. Backup & Cloud Architecture

### 23.1 Backup Structure

```
Pharmacy Root/
├── Files/
│   ├── DB/                     — Core databases
│   │   └── Restore.bak         — Restore point
│   ├── DBI/                    — Data files
│   │   ├── *.bak               — Database backups
│   │   ├── internet-backup.txt — Internet backup config
│   │   └── [various].phy       — Data files
│   ├── Archive/                — Archived data
│   │   ├── Input/              — Purchase archives
│   │   └── Output/             — Sales archives
│   ├── Drugs/                  — Drug database
│   ├── Export/                 — Export data
│   │   ├── DrugEye/            — DrugEye exports
│   │   └── Titan/              — Titan exports
│   ├── StockNow/               — Current stock
│   ├── Updates/                — Software updates
│   └── Zatca/                  — E-invoice files
├── Labirdo/
│   └── Titan3-Backup/
│       ├── Daily/              — Daily backups
│       ├── Monthly/            — Monthly archives
│       ├── Export/             — Export archives
│       ├── images/             — Image files
│       ├── xj/                 — Compressed backups
│       └── History.txt         — Backup history
└── [App Files]
```

### 23.2 Cloud Sync Protocol

1. **Upload Phase:**
   - Compress data files
   - Upload to cloud storage
   - Verify upload success

2. **Download Phase:**
   - Check for updates
   - Download new data
   - Merge with local data

3. **Sync Validation:**
   - "Sync list cannot be received" error handling
   - Conflict resolution

---

## 24. Error Messages & Conditions

### 24.1 Critical Errors
```
"Database error"
"Database error."
"An error occured! Enquiry is unsuccessful (database)"
"An error occured! Enquiry is unsuccessful (web)"
"An error occurred while executing query"
```

### 24.2 Validation Errors
```
"Invalid Username or Password."
"Invalid authentication code"
"Invalid password"
"Invalid user."
"Username cannot be null."
"Username is empty or invalid"
"Password is empty."
"Password required"
"Wrong password !"
"Invalid GLN format."
"Invalid SN"
"Invalid archive"
```

### 24.3 Business Logic Errors
```
"Not Enouph Stock"
"Abnormal Discount"
"Expired product (this operation cannot be performed)"
"Drugs prohibited for sale"
"Any product cannot be sold to the person registered as dead"
"Stakeholder is unauthorized for this operation"
"Sender user is passive"
"Receiver stakeholder is passive"
"Last transaction more than 120 days ago"
"Last transaction more than 180 days ago"
```

### 24.4 File Errors
```
"Permission denied. File may be open by another user or otherwise locked."
"Unable to Delete File"
"Sorry ; File now is in use; try again !"
"You can not run your app from this path"
"You must restart your computer, and then open the program again."
```

---

## 25. Numeric Constants & Thresholds

### 25.1 System Constants
```
45 years       — System age limit ("Sorry i have served you for more than 45 years")
1000 days      — Record retention ("Records of last 1000 day")
500 items      — Batch load limit (Reload_Drugs_500, etc.)
3000 records   — Query limit ("SELECT top 3000 * FROM usersourceupdate")
120 days       — Transaction expiry
180 days       — Transaction expiry (extended)
30 days        — Transaction expiry (short)
365 days       — Transaction expiry (year)
730 days       — Transaction expiry (2 years)
3 days         — Temporary activation
7 years        — Maximum expiry span
13 digits      — GLN format length
16 characters  — Barcode field length
90 characters  — Drug name max length
10000 bytes    — Max package size
14 digits      — Product code length
```

### 25.2 Default Values
```
Password: 3030
Stock default: 0
Price default: 0
Minimum default: 0
Invoice ID default: 0
```

---

## 26. Date/Time Handling

### 26.1 Supported Date Formats
```
YYYY-MM-DD
YYYY-MM-DD HH:NN
YYYY-MM-DD HH:NN:SS
YYYY-MM-DDTHH:NN:00
YY-MM-DD
YY-MM-DD HH:NN
YY-MM-DD HH:MM
YY.MM.DD
YYMMDD
YYMMDDHHNNSS
YYYYMM
YYYYMMDD
DD-MM-YYYY
MM-DD
MM-YYYY
```

### 26.2 Time Format
```
HH:NN:SS      — Standard time
MM-DD         — Month-day
"Time Format must be like 05:22:00 or 18:05:15"
```

### 26.3 Date Operations
```
"Set titan date from internet"
"Set windows date"
"Computer Date = "
"Windows date Is  : "
"Titan date Is  : "
"Phye date Is  : "
"Date is Wrong"
```

---

## 27. Currency & Financial Formats

### 27.1 Supported Currencies
```
EGP     — Egyptian Pound (default)
SAR     — Saudi Riyal
AED     — UAE Dirham
KWD     — Kuwaiti Dinar
BHD     — Bahraini Dinar
QAR     — Qatari Riyal
OMR     — Omani Rial
JOD     — Jordanian Dinar
LBP     — Lebanese Pound
SDG     — Sudanese Dinar
DZD     — Algerian Dinar
TND     — Tunisian Dinar
LYD     — Libyan Dinar
YER     — Yemeni Rial
TRY     — Turkish Lira
```

### 27.2 Currency Operations
```
"Discount by currency"       — Fixed amount discount
"N.Price"                    — Net price
"Price+vat"                  — VAT inclusive
"Price-Vat"                  — VAT exclusive
"Net with VAT"               — Net including VAT
```

---

## 28. Barcode System

### 28.1 Barcode Fields
```
Barcode     — Primary barcode (varchar(16))
Barcode1    — Secondary barcode
Barcode2    — Tertiary barcode
Barcode3    — Fourth barcode
Barcode4    — Fifth barcode
Barcode5    — Sixth barcode
```

### 28.2 Barcode Types
```
International barcode (GTIN)
Short code (internal)
Custom barcodes
Code 128
```

### 28.3 Barcode Operations
```
"Add barcode"
"Cancel barcode blocking"
"Block barcode from usage"
"Clean duplicate barcode"
"Remove duplicate barcodes for items"
"Apply barcode printing to all items"
"Apply barcode printing to medicines without international barcode"
"Short code" — Internal code system
```

### 28.4 Barcode Validation
```
"An international barcode common to more than one drug"
"An international barcode with an incorrect structure"
"Product barcode information is missing or invalid"
```

---

## 29. File System Architecture

### 29.1 Application Files
```
Phye.exe                    — Main executable
\Files\DBI\[various].phy   — Data files
\Files\DB\[various]         — Database files
\Files\Drugs\               — Drug database
\Files\Export\              — Export files
\Files\Archive\             — Archive files
```

### 29.2 Data File Types
```
.phy     — Phycod data files
.txt     — Text configuration
.xml     — XML data
.csv     — CSV exports
.bak     — Backup files
.rur     — Archive files
```

### 29.3 Key Data Files
```
Daily.phy             — Daily transactions
Dailyline.phy         — Daily line items
Dailymax.phy          — Daily maximums
sales.phy             — Sales data
salesfull.phy         — Full sales
purchases.phy         — Purchase data
customers.phy         — Customer data
usersmony.phy         — User financial
workperiod.phy        — Work period
```

---

## 30. Drug Interaction Database

### 30.1 Drug Interactions (Partial List)

| Drug 1 | Drug 2 | Interaction |
|--------|--------|-------------|
| Amiodaron | Quinolones | Increased risk of TdP and/or QTc prolongation |
| Carbamazepin | Warfarin | Increased carbamazepine concentrations |
| Ciprofloxacin | Quinolones | Avoid in children below 18 years |
| Diclofenac | Warfarin | Potential for serious bleed |
| Ketoconazol | Pimozide | Marked increases in serum levels |
| Lithium | - | Cause kidney damage |
| Macrolides | Warfarin | May cause toxicity |
| Simvastatin | Amiodaron | Increased risk of myopathy |
| Warfarin | NSAIDs | Potential for serious bleed |

### 30.2 Pregnancy Contraindications
```
"Contraindicated in pregnancy"
"not suitable for third trimester pregnancy"
"not suitable for pregnancy"
"Breast Feeding" warnings
```

---

## Appendix: Form-to-Module Mapping

### Key Forms
| Form | Procedures | Purpose |
|------|-----------|---------|
| FFFStartUp | 252 | Application startup |
| FormDrugsDetails | 51 | Drug card editing |
| FormDrugFlow | 32 | Drug movement tracking |
| FFFSODUKU | 36 | Drug Sudoku game |
| FormExpiredDrugs | 21 | Expiry management |
| FormActivation | 23 | License activation |
| FormStoreDiscount | 23 | Discount management |
| FormDrugPrice | 18 | Price management |
| FormPrintSales | 17 | Sales printing |
| FormBarcodeSettings | 13 | Barcode config |
| FormUserEhsa | 12 | User attendance |
| FormUsersMony | 24 | User financials |
| FormInvoiceTrackEditing | 4 | Invoice tracking |
| FormMoreBarcodes | 8 | Multi-barcode |
| FormMinimumControl | 23 | Minimum stock |
| FormAutoExpire | 12 | Auto-expiry |
| FormBackRestore | 4 | Backup/restore |
| FormRestore | 6 | Data restore |

---

**End of Business Logic Extraction**
