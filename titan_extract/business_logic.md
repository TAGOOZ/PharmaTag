# TITAN.W1 Pharmacy Application - Business Logic Rules Extraction

**Source:** P-code disassembly of TITAN.W1 (Phye.exe) VB6 application
**Extracted from:** `pcode_disasm.txt`, `strings_utf16.txt`, `strings_readable.txt`, `objects.txt`, `procedures.txt`
**Total Procedures:** 6,192 | **Forms:** 237 | **Objects:** 336

---

## Table of Contents

1. [Drug Expiry Rules](#1-drug-expiry-rules)
2. [Stock Minimum/Maximum Rules](#2-stock-minimummaximum-rules)
3. [Price Calculation Rules](#3-price-calculation-rules)
4. [Invoice Creation Workflow](#4-invoice-creation-workflow)
5. [User Permission Levels](#5-user-permission-levels)
6. [Backup/Sync Rules](#6-backupsync-rules)
7. [Validation Rules](#7-validation-rules)
8. [Financial Calculation Formulas](#8-financial-calculation-formulas)
9. [Tax/VAT Compliance (ZATCA)](#9-taxvat-compliance-zatca)
10. [Database Schema Rules](#10-database-schema-rules)
11. [Module-Level Logic](#11-module-level-logic)

---

## 1. Drug Expiry Rules

### 1.1 Expiry Date Validation
- **Maximum Expiry Duration:** Expiry Date cannot exceed Production Date more than **7 years**
  - String: `"Expiry Date cannot exceed Production Date more than 7 years."`
- **Format Validation:** Expiry date format must match expected format; incompatible formats trigger error
  - String: `"The format of the expiry date of the product (XD) is incompatible."`
- **Missing Expiry:** If expiry date is missing or incorrect, system blocks the operation
  - String: `"<XD> Expiry date information is missing or incorrect."`

### 1.2 Expired Product Handling
- **Block on Expired Product:** Expired products cannot be sold or processed
  - String: `"Expired product (this operation cannot be performed)."`
  - String: `"Product has expired."`
- **Deactivation Notification:** System can use deactivation notification for expired units
  - String: `"Use deactivation notification for expired units."`
- **Automatic Expiry Detection:** System detects expiry automatically
  - String: `"Expiry detection"`
  - String: `"Medicines whose expiry date has changed automatically"`

### 1.3 Expiry Date Management
- **Apply Last Purchase Expiry:** Can apply last purchase expire date for current invoice items
  - String: `"Apply last purchase expire date for current invoice items"`
- **Edit Expiry Date:** Can edit expiry date with the latest purchase expiry date
  - String: `"Edit Expiry date with the latest purchase expiry date"`
  - String: `"Edit this item expiry date"`
- **Reset Expire for Invoice:** Can reset expire for entire invoice
  - String: `"Reset Expire for this invoice"`
- **Set Expiry Dates:** Can set expiry dates according to sales rates
  - String: `"Set expiry dates"`
  - String: `"Expiry dates according to sales rates"`
- **Extension of Expiry Date:** Supports extension of expiry dates
  - String: `"Extension of expiry date"`
- **Batch Number Uniqueness:** Batch number with different expire/production date is rejected
  - String: `"This batch number was used before with a different expire date or production date."`

### 1.4 Expiry in Stock Table Schema
- Database field: `expire` column in stock/invoice tables
- Sample schema: `(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)`
- Stock tracking: `drugname,datee,silsilaid,minimum,pharmacyid,classy,stock`
- CSV import format: `name^barcode^stock^expire YYYY-MM`

### 1.5 Expiry Display Options
- Always hide the quantity and expiry bar
- Quantity and expiry dates display mode
- Expire paritaly reset capability

---

## 2. Stock Minimum/Maximum Rules

### 2.1 Minimum Stock Level
- Each drug has a `minimum` field in the stock table
- Schema: `minimum real default '0'`
- System tracks drugs with large minimum rates
  - String: `"Medicines with large minimum rate"`
- Minimum control form exists: `FormMinimumControl` (23 procedures)

### 2.2 Stock Validation
- **Insufficient Stock Check:** System blocks sales when stock is insufficient
  - String: `"Not Enouph Stock"`
- **Zero Stock Detection:** System detects zero stock situations
  - String: `"Stock is zero"`
- **False Stock Detection:** System detects drugs with false/incorrect stock
  - String: `"These drug have False stock"`

### 2.3 Stock Table Structure
- Main tables: `titanstock`, `titanksastock`
- Schema: `drugname,lastedit,pharmacyid,price,stock,barcode,titanid`
- Stock field: `stock real default '0'`
- Stock update operations: `update titanksastock set stock =` and `update titanstock set stock =`
- Stock deletion: `delete from titanksastock`

### 2.4 Stock Management Features
- Cloud storage of stock
- Stock details view
- Stock correction: `Titan CorrectStockForAll`
- Fill empty names: `Titan ZuFillEmptyNameIftheresStock`
- Monthly stock tracking: `\Files\DBI\month.start.stock.`

### 2.5 Maximum Sales Quantity
- System supports maximum sales quantity per transaction
  - JSON field: `"maximum_sales_quantity":`

---

## 3. Price Calculation Rules

### 3.1 Price Fields
- **Current Price:** `price` field in drug/stock table
- **Price Now:** `PriceNow real default '0'`
- **Current Price:** `curprice real default '0'`
- **Extra Prices:** Up to 4 extra price levels
  - `Price.extra.1`, `Price.extra.2`, `Price.extra.3`, `Price.extra.4`

### 3.2 Price Types
- **Sale Price:** Final selling price
- **Purchase Price:** Cost price from supplier
  - `"Actual purchase price"`
  - `"Real purchase price"`
  - `"Calculated purchase price"`
- **Wasfaty Price:** Prescribed/medical price
  - `"Wasfaty Price"`
- **Temp Price:** Temporary price adjustment
  - `"Temp price"`
- **Temporary Price:** Can make temporary price equal to current price
  - `"Make temporary price equal to current price"`

### 3.3 Discount Rules
- **Drug Discount:** Per-item discount
  - String: `"Buy Discount"`
- **Sale Discount:** Applied to sales
  - String: `"sale discount"`
- **Purchase Discount:** Applied to purchases
  - String: `"Purchase discount"`
- **Cash Discount:** Cash payment discount
  - String: `"Cash discount"`
- **Wholesale Discount:** Bulk purchase discount
  - String: `"Wholesale discount"`
- **Warehouse Discounts:** Warehouse-level discounts
  - String: `"werehouse discounts"`
- **Store Discount:** Per-store discount rules
- **Group Discount:** Import from group pricing
  - String: `"Import price adjustments from the group"`
- **Last Purchase Discount:** Apply discount of last purchase
  - String: `"Apply the discount of the last purchase"`
- **Tax Item Discount:** Apply sale discount for tax items
  - String: `"Apply a sale discount for tax items"`

### 3.4 Discount Table Schema
- Table: `storediscount`
- Fields tracked: `drugname,barcode,units,pricechanged,localimport,quant`
- Query patterns:
  - `select drugname, count(*), max(disco), min(disco), max(datee) from storediscount where adress=`
  - `select pharmacyname, adress, count(*), max(datee) from storediscount`
- Abnormal discount detection: `"Abnormal Discount"`

### 3.5 Price Change Tracking
- Price change log: `prices-changes.txt`
- Old prices backup: `oldprices.phy`
- Price log: `\Files\DBI\Price-log.txt`
- Price update operations: `update titanstock set price =`

### 3.6 TATAMIA Pricing Structure
- Complex pricing formula fields:
  ```
  TttPak2^TttPart2^TttBomus2^TttDiscMain^TttDiscadd3^TttExpire2^TttNotVatedUnit^TttNotvatedAll^TttBuyValue3^TttEgmaly2
  ```
- Alternative pricing:
  ```
  TttPart2^TttBomus2^TttDiscadd3^TttNotVatedUnit^TttNotvatedAll^TttBuyValue3
  ```

### 3.7 Auto Price Update
- System supports automatic price updates
  - String: `"Auto-price-Update"`
- New price comparison: `"Newly priced drugs"`

---

## 4. Invoice Creation Workflow

### 4.1 Invoice Types
- **Sales Invoice:** Standard sales transaction
  - String: `"As a Sales invoice"`
- **Purchase Invoice:** Incoming stock from supplier
  - String: `"As a new purchase invoice"`
- **Purchase Return Invoice:** Return to supplier
  - String: `"As a new purchase return invoice"`
- **Sales Return Invoice:** Customer return
  - String: `"Sales return invoice"`
- **Transfer Invoice:** Between pharmacies
  - String: `"Transfer invoice to another pharmacy"`
- **Modified Invoices:** Post-creation modifications
  - String: `"Modified invoices"`

### 4.2 Invoice Data Structure
- Invoice header fields: `invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue`
- Invoice items include: `(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)`
- Sales record: `PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,SourceIdDateTime,price`

### 4.3 Invoice Workflow Steps
1. **Add Drug to Invoice:** Add item by barcode reader or manual entry
   - `"Add drug to this invoice"`
   - `"Add medicine to this invoice"`
2. **Apply Discounts:** System applies various discount rules
3. **Calculate VAT:** VAT is calculated on applicable items
4. **Set Payment:** Cash or credit payment
5. **Save Invoice:** Persist to database
6. **Print Invoice:** Optional printing
   - `"Print the invoice once it is saved"`
   - `"Print this invoice in sales invoice form"`
7. **Open Drawer:** Optional cash drawer opening
   - `"Open drawer while saving invoice"`

### 4.4 Invoice Operations
- **Invoice Numbering:** Sequential internal invoice numbers
  - `"Titan Internal invoice number"`
- **Invoice Counter:** System tracks invoice count
- **Invoice Tracking:** Edit tracking
  - `"InvoiceTrackEditing"` form
- **Invoice Date Modification:** Can modify invoice date
  - `"Modifiy invoice date"`
- **Change Customer:** Can change customer for saved invoice
  - `"change customer for saved invoice"`
- **Invoice Excel Export:** Can save invoice as Excel file
  - `"Save invoice as an excel file"`

### 4.5 Invoice Validation Rules
- **Abnormal Entries Detection:**
  - `"Abnormal entries in the invoice"`
- **Stock Validation:** Must have sufficient stock before saving
- **Expiry Validation:** Must have valid expiry dates
- **Price Validation:** Prices must be valid and non-negative
- **Invoice Repair:** System can repair damaged invoices
  - `"we found that your invoices needs to repaired,and this process completed,restart now"`

### 4.6 Invoice Query/Search
- Search by invoice number
- Bring invoices by date range
- Quick access to invoices containing specific item
- Today's invoices view
- All invoices view
- Archived invoices: `"Read archived invoices"`

---

## 5. User Permission Levels

### 5.1 User Types
- **Super Admin:** Highest privilege level
  - `"Login as super admin"`
- **Manager:** Management-level access
  - `"Pharmacy manager"`
  - `"Log in as a manager without logging off current user"`
- **Operations Account:** Standard operations
  - `"Login with operations account"`
- **Management Account:** Management-level operations
  - `"Login with management account"`
- **Technical Support:** Limited support access
  - `"Log in as Technical Support"`
- **One-time Login:** Single session access
  - `"Login one time"`

### 5.2 Permission System
- **Admin Permissions:** Full system access
  - `"Give permissions of admin user"`
- **Normal User Permissions:** Standard user access
  - `"Give permissions of normal user"`
- **Group ID:** User grouping
  - `<iGroupId> 2 </iGroupId>`
- **Permission Level:** Numeric level system
  - `<iLevel> 1 </iLevel>`
- **User Level:** Product level tracking
  - `"Undefined Product Level"`

### 5.3 User Management Features
- **Add New User:** User creation
  - `"*AddNewUser*"`
- **Change User Authorizations:** Modify permissions
  - `"*ChangeUserAuths*"`
- **Password Management:**
  - `"Change Password"`
  - `"Change password"`
  - `"Forgot password"`
  - `"Password is empty."`
  - `"Password required"`
- **Deactivation:**
  - `"deactivate"`
  - `"Indicated seller is deactivated"`
  - `"Your account is deactivated. Apply to your system manager."`
  - `"The receiver is deactivated."`

### 5.4 Login Validation
- `"Invalid Username or Password."`
- `"Invalid password"`
- `"Invalid user."`
- `"Invalid block level"`
- `"Invalid level information."`
- `"Invalid recall level"`

### 5.5 User Types by Role
- Chain buy users: `"ChainBuyUsers"`
- Home users: `"HomeUsers"`
- Stakeholder users
- Admin users
- Normal users

---

## 6. Backup/Sync Rules

### 6.1 Backup Types
- **Standard Backup:** Regular database backup
  - `"Save a backup"`
- **Daily Backup:** Automated daily backups
  - `Labirdo\Titan3-Backup\Daily\`
- **Monthly Backup:** Monthly archives
  - `Labirdo\Titan3-Backup\Monthly\`
- **Internet Backup:** Cloud-based backup
  - `"Create Internet backup"`
- **Server Backup:** Network server backup
  - `"sever backup contibued"`
  - `"sever backup stopped"`
- **No-Backup Folder:** Excluded from backup
  - `"Back up is ignored by 'no-backup' folder"`
  - `"no-backup"` folder marker

### 6.2 Backup Locations
- Primary: `\Titan3-backup`
- Daily: `Labirdo\Titan3-backup\Daily\`
- Monthly: `Labirdo\Titan3-Backup\Monthly\`
- Export: `Labirdo\Titan3-Backup\Export\`
- Deleted: `Labirdo\Titan3-Backup\Export\Del\`
- RUR files: `Labirdo\Titan3-Backup\Rur\*.rur`
- Images: `Labirdo\Titan3-Backup\images\`
- TAR copies: `Labirdo\Titan3-Backup\tars-copy\`
- ZIP archive: `Labirdo\Titan3-Backup\xj\Phye.zip`
- QR backups: `labirdo\titan3-backup\qr\`
- DBI backups: `titan-users/dbi-zipped/Bux-w-backup/`

### 6.3 Restore Operations
- **Restore Backup:** Full database restore
  - `"Restore backup"`
  - `"Restore.exe"`
- **Restore Deleted Invoice:** Recover deleted transactions
  - `"Restore a deleted invoice"`
- **Restore Item Price:** Revert price changes
  - `"Restore item price before this invoice"`
- **Restore File:** `\Files\DB\Restore.bak`

### 6.4 Cloud Sync
- **Cloud Copy:** Local to cloud synchronization
  - `"Cloud copy"`
- **Cloud Storage:** Cloud-based stock storage
  - `"Cloud storage of stock"`
- **Drug Database Upload:**
  - `"Upload the drug database to the cloud storage"`
- **Group Sharing:**
  - `"Share between my group - Show"`
  - `"Share between my group - upload"`
- **Pending Invoices:** Sync from linked devices
  - `"Pending invoice folder from linked devices"`

### 6.5 Backup Validation
- Backup backup backup
- Backup folder configuration
- Clean backups: `"Clean backups"`
- Backup failure handling: `"failed to backup copy"`
- Backup identification: `"This is Titan backup maked by"`

---

## 7. Validation Rules

### 7.1 Drug Validation
- **Barcode Validation:** Multiple barcode formats supported
  - Barcode1 through Barcode5 fields
  - International barcode structure validation
    - `"An international barcode with an incorrect structure"`
  - Duplicate barcode detection
    - `"An international barcode common to more than one drug"`
- **Drug Existence:** Product must be registered
  - `"The product is not registered in your stock."`
- **Deactivation Status:**
  - `"The product has already been deactivated."`
  - `"The product is in deactivated status"`
  - `"The product is not deactivated."`
  - `"The product is not deactivated by you."`

### 7.2 Invoice Validation
- **Stock Check:** Available stock must meet quantity requested
- **Expiry Check:** Products must have valid expiry dates
- **Price Check:** Prices must be valid
- **Discount Validation:** Discounts cannot exceed reasonable limits
  - `"Abnormal Discount"`
  - `"Abnormal entries in the invoice"`
- **Invoice Data Integrity:** System can detect and repair corrupted invoices

### 7.3 User Validation
- **Password Requirements:** Password cannot be empty
- **Login Validation:** Username/password combination must be valid
- **Permission Check:** User must have appropriate permission level
- **Account Status:** Account must not be deactivated

### 7.4 Country Validation
- **Country ID:** Must be valid
  - `"Country ID cannot be null."`
  - `"Country information is empty or invalid"`
  - `"Invalid country ID format."`
- **Country Change:** Can change country setting
  - `"Change Country"`
- **Country-Specific Rules:** Different rules for Egypt vs Saudi Arabia

### 7.5 Batch/Lot Validation
- **Batch Uniqueness:** Same batch number cannot have different expiry/production dates
- **Production Date:** Must precede expiry date
- **Expiry Range:** Maximum 7 years from production date

### 7.6 Network Validation
- **Connectivity Check:** System verifies network connectivity
  - `"press ok to start check network connectivity"`
- **Permission Denied:** File access validation
  - `". Permission denied. File may be open by another user or otherwise locked."`

---

## 8. Financial Calculation Formulas

### 8.1 VAT Calculation
- **VAT Rate:** Configurable per item (Egypt: 14%, Saudi: 15%)
- **VAT Types:**
  - Taxable items: items subject to VAT
  - Non-taxable items: items exempt from VAT
  - VAT items: items with VAT applied
- **VAT Fields:**
  - `vat` field in drug table
  - `vatvalue` in transaction records
  - `totalwithvat` in transaction records
- **VAT Operations:**
  - Add VAT to price: `input + to add vat to price`
  - Remove VAT from price: `or - to remove it`
  - Cancel VAT with price increase: `"Cancellation of the vat with an increase in the price of items"`
  - Re-apply VAT on invoices: `"Re-apply vat on invoices"`
  - Manually reset VAT: `"Manually resetting the Vat value in old invoices"`

### 8.2 Cost Calculation
- **Cost Value:** `costvalue` field in transaction records
- **Stock Cost with VAT:** `drugs-stock-cost-withvat`
- **Stock Cost without VAT:** `drugs-stock-cost-novat`
- **Total Cost:**
  - With VAT: `total-Cost-with-vat`
  - Without VAT: `total-Cost-no-vat`

### 8.3 Profit Calculation
- **Annual Net Profits:** Yearly profit calculation
  - `"annual net profits"`
- **Sales and Profit Reports:**
  - `"Total sales and profit reports"`
- **Profit Margin:** Calculated from cost vs sale price

### 8.4 Tax Reporting
- **VAT Report:** Quarterly VAT report
  - `"Quarterly VAT report"`
- **VAT Registeration:** Tax registration number
  - `"Tax registration number"`
  - `"Vat registration number"`
- **VAT File Output:** `VatFile-Result.txt`
- **Tax Report Location:** `\Files\Accounting\Vat-reports\`

### 8.5 Payment Calculations
- **Cash Payment:** Direct cash transactions
- **Credit Payment:** Accounts receivable/payable
- **Payment Methods:**
  - Cash: `purchases-payed-cash`
  - Visa: `purchases-payed-visa`

### 8.6 Invoice Total Calculation
```
Total = Σ(Item_Quantity × Item_Price)
Total_VAT = Σ(Item_VAT_Amount)
Total_With_VAT = Total + Total_VAT
Net_After_Discount = Total_With_VAT - Discount
```

---

## 9. Tax/VAT Compliance (ZATCA)

### 9.1 ZATCA Integration
- **Saudi Arabia Compliance:** ZATCA (Zakat, Tax and Customs Authority) electronic invoicing
- **Egypt Compliance:** Egyptian tax authority integration
- **E-Invoice XML Structure:**
  - Header with seller/buyer info
  - Item data with tax calculations
  - Tax totals and breakdowns
  - QR code generation

### 9.2 ZATCA XML Fields
- Seller VAT number
- Buyer VAT number (B2B only)
- Tax type and rate
- Taxable items
- Tax totals
- Commercial discount data
- Item discount data
- Payment method
- Receipt type
- UUID tracking

### 9.3 SFDA Integration (Saudi Arabia)
- Drug Track and Trace System (RSD)
- Pharmacy Sale Service
- Pharmacy Sale Cancel Service
- Dispatch Service
- Return Service
- Transfer Service

### 9.4 Electronic Invoice Features
- QR code generation and printing
- Electronic invoice submission
- Invoice cancellation support
- Reference invoice tracking
- UUID-based invoice identification

---

## 10. Database Schema Rules

### 10.1 Core Tables

#### titanstock (Main Drug Stock)
```sql
drugname, lastedit, pharmacyid, price, stock, barcode, titanid
```

#### titanksastock (Network Stock)
```sql
drugname, datee, silsilaid, minimum, pharmacyid, classy, stock
```

#### titanksasales (Sales Records)
```sql
PharmacistTel, Expire, IdDateTime, Quant, DrugName, SellDisc,
Mohafaza, Markaz, Tips, RequisterTel, country, price
```

#### storediscount (Discount Records)
```sql
drugname, barcode, units, pricechanged, localimport, quant
```

#### Invoice Table
```sql
invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue
```

#### Drug Master Table
```sql
drugname, drugnamear, barcode, vat, units, classy, generic,
pharmacology, co, unitsclass, price
```

### 10.2 Field Defaults
- `stock real default '0'`
- `minimum real default '0'`
- `price real default '0'`
- `PriceNow real default '0'`
- `curprice real default '0'`
- `invoiceid real default '0'`

### 10.3 Data Types
- `decimal(14,6) default '0'`
- `nvarchar(n)` for text fields
- `varchar(16)` for barcodes
- `real` for numeric fields

---

## 11. Module-Level Logic

### 11.1 ModPharm (12 procedures)
- Drug management and pharmaceutical operations
- Drug name and classification management
- Drug search and lookup operations

### 11.2 ModStock (165 procedures)
- Stock level management
- Stock correction operations
- Stock transfer between locations
- Minimum/maximum stock monitoring

### 11.3 ModInn (71 procedures)
- Purchase/inward invoice processing
- Supplier management
- Purchase price tracking
- Inward stock validation

### 11.4 ModOot (105 procedures)
- Sales/outward invoice processing
- Customer management
- Sales price calculations
- Outward stock deduction

### 11.5 ModStorage (154 procedures)
- Warehouse management
- Storage location tracking
- Multi-warehouse operations
- Storage capacity monitoring

### 11.6 ModUsers (39 procedures)
- User authentication
- Permission management
- User group management
- Login/logout operations

### 11.7 ModMony (30 procedures)
- Financial calculations
- Payment processing
- Account reconciliation
- Financial reporting

### 11.8 ModBackUp (43 procedures)
- Backup creation and management
- Restore operations
- Cloud synchronization
- Network backup operations

### 11.9 Raz (379 procedures)
- Main business logic orchestration
- Cross-module coordination
- Business rule enforcement
- Core application workflows

---

## Key String Constants Reference

| Category | String | Purpose |
|----------|--------|---------|
| Expiry | `Expired product (this operation cannot be performed).` | Block expired product operations |
| Expiry | `Expiry Date cannot exceed Production Date more than 7 years.` | Maximum expiry validation |
| Stock | `Not Enouph Stock` | Insufficient stock warning |
| Stock | `Stock is zero` | Zero stock detection |
| Price | `Abnormal Discount` | Discount validation |
| User | `Your account is deactivated.` | Account status check |
| User | `Invalid Username or Password.` | Login validation |
| Invoice | `Abnormal entries in the invoice` | Invoice validation |
| Backup | `failed to backup copy` | Backup failure handling |
| Tax | `Quarterly VAT report` | Tax reporting |

---

## Arabic Business Terms

| Arabic Term | English Translation |
|-------------|---------------------|
| أدوية منتهية الصلاحية | Expired medicines |
| اختر تاريخ الصلاحية اولا | Select expiry date first |
| ادخل الصلاحية كما تنطقها | Enter expiry as spoken |
| اخفاء شريط الكمية والصلاحية دائما | Always hide quantity and expiry bar |
| الصافي بالضريبة | Net with VAT |
| ضريبة ق مضافة | Total VAT |
| اضافة صلاحية عمل الخصم | Add discount permission |
| استخدام اتجاهات لوحة المفاتيح | Use keyboard directions |
| الصنف قابل للارتجاع عند انتهاء الصلاحية | Product returnable when expired |

---

*Extracted from TITAN.W1 VB6 p-code disassembly - 6,192 procedures analyzed*
*Documentation generated for business logic reverse engineering purposes*
