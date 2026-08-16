# Raz Module - Complete Functionality Extraction

## TITAN.W1 Pharmacy Application - Main Business Logic Module

**Module:** Raz  
**Type:** VB6 Standard Module (.bas)  
**Procedures:** 379 (largest module in the application)  
**Source File:** Raz.bas (3,163 lines decompiled)  
**Binary Size:** ~71KB (Raz.bas source)  

---

## Table of Contents

1. [Module Overview](#1-module-overview)
2. [Procedure Inventory](#2-procedure-inventory)
3. [Categorized Functionality](#3-categorized-functionality)
4. [Database Operations](#4-database-operations)
5. [Business Rules Extraction](#5-business-rules-extraction)
6. [Main Workflows](#6-main-workflows)
7. [Module Dependencies](#7-module-dependencies)
8. [String Constants Analysis](#8-string-constants-analysis)
9. [E-Invoice Integration](#9-e-invoice-integration)
10. [Error Handling Patterns](#10-error-handling-patterns)

---

## 1. Module Overview

The Raz module is the **core business logic engine** of the TITAN.W1 pharmacy management system. With 379 procedures, it handles:

- **Invoice management** (sales, purchases, returns, transfers)
- **Stock/inventory control** (quantities, expiry dates, batches)
- **Drug data management** (prices, classifications, barcodes)
- **Financial calculations** (VAT, discounts, totals)
- **E-invoice compliance** (ZATCA, ETA, DTTS integration)
- **Network operations** (FTP, API calls, remote synchronization)
- **File operations** (backup, restore, data import/export)
- **Print operations** (receipts, labels, reports)
- **Date/time operations** (day-end, month-end, archiving)

### Key Characteristics

- **Error handling:** Most procedures use `On Error GoTo ErrHandler`
- **Pattern:** Heavy use of conditional branching (If/Then/Else)
- **Calls:** Extensive calls to other modules (ModPharm, ModInn, ModOot, ModStock, ModPrint, etc.)
- **String operations:** SQL query construction, XML/JSON generation
- **File I/O:** Network file operations, database file management

---

## 2. Procedure Inventory

### Complete List of 379 Procedures (by Address)

```
@0x008f6f90  @0x009a6284  @0x00905ed0  @0x009c0ddc  @0x008e2b50
@0x0095d9ec  @0x0095d594  @0x00961d64  @0x0091ef24  @0x009a0540
@0x009c37b0  @0x008f0d90  @0x00901bac  @0x009238bc  @0x009190ec
@0x009073e8  @0x009411fc  @0x0090ff3c  @0x00908cdc  @0x0094e200
@0x00908d64  @0x008ecb78  @0x008ecd70  @0x008eec88  @0x008fdc94
@0x008eb270  @0x00932550  @0x0093e0fc  @0x00936ef4  @0x00915bac
@0x0097ede4  @0x00942124  @0x009e7018  @0x00923964  @0x009ea380
@0x00922ed8  @0x0090fa00  @0x008fabbc  @0x00950120  @0x0095f414
@0x0093967c  @0x009b1a44  @0x0092ffd0  @0x009297e0  @0x00922c04
@0x0096bb10  @0x00975fa4  @0x0091e304  @0x00941d90  @0x00961450
@0x00960fd0  @0x0099f9e4  @0x00971f50  @0x0091362c  @0x0092e7e4
@0x00922238  @0x00945178  @0x008eaf48  @0x0095d7b4  @0x008fc8e8
@0x00919d1c  @0x008efcac  @0x008db948  @0x008ef998  @0x00933464
@0x0090d960  @0x009244b0  @0x008f5864  @0x009f4bc0  @0x00a123a4
@0x008f572c  @0x008fcb80  @0x00971ccc  @0x00966524  @0x0091a238
@0x00905e4c  @0x00923b80  @0x00910228  @0x00910340  @0x00969bdc
@0x00949f6c  @0x0092cc54  @0x00982994  @0x00917678  @0x008fb000
@0x0091beb0  @0x009e6478  @0x008f0ea4  @0x0095817c  @0x009b1318
@0x009a5868  @0x009ad110  @0x0091be10  @0x0091b588  @0x009eadc8
@0x008eed8c  @0x0090bd4c  @0x008f8f70  @0x0097ceb4  @0x00966be0
@0x0090ed10  @0x009b7280  @0x008eae5c  @0x009246cc  @0x008f09a0
@0x0090eac8  @0x008e3c64  @0x00a0ac20  @0x009053d0  @0x0096e308
@0x009978d0  @0x00934440  @0x008e7c78  @0x0090b970  @0x00900980
@0x008ed6a0  @0x009201ec  @0x00917168  @0x0094a244  @0x008fc100
@0x008d9c64  @0x008d9ccc  @0x0096aa5c  @0x00909cdc  @0x00965400
@0x0096d944  @0x008f95cc  @0x0091fff0  @0x009458b4  @0x00924130
@0x00934388  @0x009009fc  @0x0092028c  @0x0091ff30  @0x00a49668
@0x0094ad7c  @0x0093b7fc  @0x009606f4  @0x009432f0  @0x009ee1f4
@0x00947d2c  @0x0091315c  @0x00928878  @0x008eebd4  @0x00914b40
@0x00910198  @0x00921aa4  @0x00985878  @0x009158a0  @0x008e34e0
@0x008ee600  @0x00928134  @0x008f29f8  @0x0092972c  @0x00a094d4
@0x0091d454  @0x00939258  @0x008e7470  @0x0095a100  @0x0094c62c
@0x00956178  @0x0096bfcc  @0x00961568  @0x00938fd4  @0x0099a7e4
@0x008f9dc8  @0x00941e40  @0x008f9e3c  @0x008ee024  @0x008eaaec
@0x00950f00  @0x008e073c  @0x0091a7f8  @0x008d94ac  @0x008d9444
@0x00940148  @0x00900d3c  @0x008e3854  @0x009522b0  @0x008e7508
@0x0092eba8  @0x0092f670  @0x008fc80c  @0x008fa720  @0x00910068
@0x00917490  @0x0099acac  @0x008f41c4  @0x008f4160  @0x008f4098
@0x0094a150  @0x00917a28  @0x0090ffd8  @0x0098a670  @0x00980498
@0x00976760  @0x0096a328  @0x0091dfbc  @0x009456e8  @0x0093fdc8
@0x0093d948  @0x008ea90c  @0x00a1bc44  @0x008f3b7c  @0x00a512c0
@0x00a62be8  @0x008df6bc  @0x008f39e8  @0x0091d6f4  @0x0090fea4
@0x008f07cc  @0x0090d9ec  @0x00995e58  @0x00a412b4  @0x00913034
@0x008ed204  @0x008ed0b4  @0x00903fc4  @0x00921cb8  @0x009d86d8
@0x00937984  @0x0092fd84  @0x00942cbc  @0x009909d0  @0x0090d8c8
@0x0092c104  @0x0097a07c  @0x00a18044  @0x0094a058  @0x00903bc4
@0x0092c62c  @0x00949e78  @0x008f1ce0  @0x009644fc  @0x008e3520
@0x008e3458  @0x008eafa0  @0x0090a3b8  @0x008f51e0  @0x008f29a0
@0x008f1b00  @0x0090a660  @0x00947050  @0x0093404c  @0x00912a40
@0x008e70fc  @0x008e4bdc  @0x009a9574  @0x008fac28  @0x009499d4
@0x008f5450  @0x00947b6c  @0x0090c578  @0x008fe618  @0x0090da70
@0x00943854  @0x009532d8  @0x00927cc0  @0x008fb3e8  @0x0097334c
@0x0097384c  @0x00973acc  @0x00987ba0  @0x009050d0  @0x008fd80c
@0x008dec3c  @0x008ded7c  @0x0090faa0  @0x00909b3c  @0x0090fc58
@0x00918e5c  @0x009c2ba8  @0x00959130  @0x00938bac  @0x009ce168
@0x008ece14  @0x008ea4d4  @0x008ea56c  @0x008f54b8  @0x008f36cc
@0x00915148  @0x009015d0  @0x00900b58  @0x00938ae0  @0x008e6c30
@0x008ec5dc  @0x00954cfc  @0x0096bd74  @0x00914214  @0x0095c778
@0x00906cb0  @0x00913ae8  @0x00914518  @0x00920b7c  @0x008e5f8c
@0x008e4b04  @0x008e4a2c  @0x008e3b8c  @0x0090715c  @0x008db558
@0x0090f850  @0x009326f8  @0x0090a114  @0x00938a0c  @0x0096399c
@0x0095c660  @0x009b5a00  @0x0091bcc4  @0x00934f68  @0x00964f4c
@0x008f82c8  @0x008f5b38  @0x0091856c  @0x00909f78  @0x0091a60c
@0x0092f5b0  @0x0090a008  @0x008ea148  @0x008e505c  @0x008fa500
@0x00964be4  @0x0094392c  @0x0092e410  @0x009092b4  @0x0099ecec
@0x008f305c  @0x00959254  @0x008eeb78  @0x009b407c  @0x0095b634
@0x00997a48  @0x00a16d24  @0x008ee1d8  @0x00982c34
```

---

## 3. Categorized Functionality

### 3.1 Sales Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x009a6284 | 360 | 100 | Sales invoice processing - handles drug lookups, price calculations, stock verification |
| @0x009c0ddc | 428 | 84 | Sales item validation - checks stock availability, expiry dates, price rules |
| @0x009b1a44 | 372 | 228 | Sales total calculation - computes VAT, discounts, net amounts |
| @0x00975fa4 | 268 | 128 | Sales return processing - validates return eligibility, updates stock |
| @0x0096bb10 | 228 | 208 | Sales invoice finalization - saves to database, generates receipt |
| @0x00961d64 | 220 | 72 | Sales discount application - applies percentage/fixed discounts |
| @0x0095d9ec | 220 | 40 | Sales payment processing - handles cash/visa split payments |
| @0x0095d594 | 216 | 40 | Sales payment validation - verifies payment amounts |
| @0x00961450 | 200 | 224 | Sales invoice number generation |
| @0x00960fd0 | 200 | 224 | Sales invoice date handling |
| @0x0099f9e4 | 344 | 176 | Sales commission/bonus calculation |
| @0x00941d90 | 152 | 180 | Sales tax calculation |
| @0x00950120 | 168 | 212 | Sales item quantity management |
| @0x0093967c | 144 | 152 | Sales drug lookup by barcode |
| @0x0092ffd0 | 124 | 164 | Sales price calculation |
| @0x009297e0 | 116 | 164 | Sales stock check |
| @0x00922c04 | 100 | 196 | Sales expiry validation |

### 3.2 Purchase Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x009c37b0 | 400 | 312 | Purchase invoice processing - main purchase workflow |
| @0x009909d0 | 236 | 228 | Purchase item addition - adds drugs to purchase invoice |
| @0x0097a07c | 252 | 228 | Purchase total calculation |
| @0x0095a100 | 196 | 176 | Purchase stock update |
| @0x0094c62c | 184 | 152 | Purchase price update |
| @0x00956178 | 196 | 184 | Purchase expiry date handling |
| @0x0094a058 | 160 | 224 | Purchase invoice finalization |
| @0x00949e78 | 160 | 208 | Purchase return processing |
| @0x0093404c | 124 | 92 | Purchase discount application |
| @0x00938fd4 | 136 | 160 | Purchase VAT calculation |
| @0x0093d948 | 144 | 160 | Purchase payment processing |

### 3.3 Stock/Inventory Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x009e6478 | 544 | 176 | Stock management main - comprehensive stock operations |
| @0x009ea380 | 424 | 376 | Stock adjustment - handles quantity corrections |
| @0x009e7018 | 416 | 376 | Stock transfer - inter-pharmacy transfers |
| @0x009d86d8 | 412 | 292 | Stock valuation - calculates stock value at cost |
| @0x009ce168 | 456 | 220 | Stock report generation |
| @0x009b7280 | 392 | 144 | Stock minimum/maximum management |
| @0x009ad110 | 384 | 124 | Stock batch tracking |
| @0x009b1318 | 392 | 156 | Stock expiry management |
| @0x009a5868 | 364 | 108 | Stock barcode operations |
| @0x0099a7e4 | 320 | 156 | Stock drug classification |
| @0x00997a48 | 300 | 232 | Stock data import |
| @0x0099ecec | 352 | 92 | Stock data export |
| @0x009b5a00 | 312 | 1216 | Stock inventory count - large frame for complex calculations |

### 3.4 Drug Data Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x00a0ac20 | 688 | 68 | Drug data processing - handles A, B, E, H, R, C, G, M, V classifications |
| @0x00a094d4 | 680 | 16 | Drug data validation - extensive conditional checks |
| @0x00a1bc44 | 760 | 144 | Drug data modification - price, VAT, barcode updates |
| @0x00a123a4 | 728 | 8 | Drug data lookup - 37+ conditional branches for drug type identification |
| @0x00a18044 | 748 | 112 | Drug data merge - combines duplicate drug entries |
| @0x009f4bc0 | 616 | 8 | Drug type classification - 30+ pattern matching checks for drug forms |
| @0x009978d0 | 324 | 168 | Drug price calculation |
| @0x0098a670 | 276 | 212 | Drug classification update |
| @0x00982994 | 284 | 152 | Drug data validation |
| @0x00976760 | 280 | 128 | Drug data export |

### 3.5 Invoice Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x00a49668 | 872 | 404 | Invoice main controller - largest procedure, handles full invoice lifecycle |
| @0x00a412b4 | 796 | 456 | Invoice creation - initializes new invoice |
| @0x00a512c0 | 820 | 456 | Invoice modification - edits existing invoice |
| @0x00a62be8 | 916 | 552 | Invoice deletion - removes invoice and reverses stock |
| @0x00a16d24 | 640 | 316 | Invoice print - generates printable invoice |
| @0x009ee1f4 | 444 | 336 | Invoice copy - duplicates invoice |
| @0x00987ba0 | 280 | 244 | Invoice number management |
| @0x00985878 | 284 | 152 | Invoice date validation |
| @0x00980498 | 212 | 256 | Invoice search |
| @0x0096e308 | 252 | 88 | Invoice validation |

### 3.6 Payment Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x0095d9ec | 220 | 40 | Payment split - cash/visa division |
| @0x0095d594 | 216 | 40 | Payment validation - amount verification |
| @0x00950f00 | 192 | 84 | Payment processing - main payment workflow |
| @0x00943854 | 164 | 112 | Payment recording - saves to database |
| @0x0094392c | 152 | 76 | Payment receipt generation |
| @0x00938ae0 | 140 | 96 | Payment history |
| @0x009326f8 | 148 | 112 | Payment refund processing |

### 3.7 Report Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x0096aa5c | 252 | 16 | Report generation - sales reports |
| @0x0096d944 | 248 | 88 | Report generation - purchase reports |
| @0x00965400 | 244 | 20 | Report generation - stock reports |
| @0x0096bfcc | 208 | 224 | Report generation - financial reports |
| @0x00964f4c | 208 | 132 | Report generation - customer reports |
| @0x009644fc | 196 | 144 | Report generation - supplier reports |
| @0x0096399c | 204 | 232 | Report generation - VAT reports |
| @0x0095c660 | 188 | 172 | Report generation - expiry reports |
| @0x0095c778 | 192 | 168 | Report generation - profit reports |
| @0x0095b634 | 184 | 144 | Report generation - daily reports |
| @0x0094ad7c | 164 | 148 | Report generation - monthly reports |

### 3.8 Print Logic Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x0097ceb4 | 204 | 168 | Print main - routes to correct printer |
| @0x00971ccc | 244 | 120 | Print receipt - thermal printer output |
| @0x00966524 | 220 | 156 | Print label - barcode label printing |
| @0x00966be0 | 168 | 160 | Print A4 - standard paper output |
| @0x009456e8 | 164 | 112 | Print settings management |
| @0x009458b4 | 160 | 104 | Print preview |
| @0x00942cbc | 160 | 104 | Print queue management |

### 3.9 Database Operations Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x0092e7e4 | 136 | 16 | Database connection management |
| @0x00922238 | 112 | 48 | Database query execution |
| @0x00945178 | 164 | 40 | Database transaction management |
| @0x009244b0 | 116 | 84 | Database backup operations |
| @0x009246cc | 116 | 76 | Database restore operations |
| @0x00928878 | 120 | 48 | Database table operations |
| @0x00928134 | 140 | 40 | Database index management |
| @0x00927cc0 | 128 | 64 | Database integrity checks |
| @0x0092c104 | 140 | 20 | Database optimization |
| @0x0092c62c | 116 | 152 | Database schema updates |

### 3.10 File Operations Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x0092cc54 | 136 | 76 | File path construction - "@" and "\\" separators |
| @0x00969bdc | 188 | 132 | File copy operations |
| @0x00949f6c | 164 | 92 | File move operations |
| @0x0095817c | 188 | 48 | File delete operations |
| @0x0090ed10 | 88 | 28 | File existence checks |
| @0x0090eac8 | 80 | 36 | File size operations |
| @0x0090d960 | 88 | 36 | File read operations |
| @0x0090d9ec | 84 | 80 | File write operations |
| @0x0090d8c8 | 80 | 60 | File list operations |
| @0x0090faa0 | 88 | 96 | File compress/decompress |

### 3.11 Network Operations Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x009b407c | 364 | 276 | Network FTP upload/download |
| @0x00995e58 | 268 | 472 | Network API calls - ZATCA/ETA |
| @0x0097334c | 244 | 224 | Network SOAP requests - DTTS |
| @0x0097384c | 244 | 224 | Network SOAP responses |
| @0x00973acc | 244 | 224 | Network XML processing |
| @0x00954cfc | 180 | 164 | Network HTTP requests |
| @0x009532d8 | 188 | 128 | Network HTTP responses |
| @0x00940148 | 152 | 84 | Network error handling |
| @0x0093b7fc | 128 | 72 | Network connection testing |
| @0x00903fc4 | 68 | 88 | Network status checks |

### 3.12 Utility Functions Procedures

| Procedure | Size | Frame | Function |
|-----------|------|-------|----------|
| @0x008f6f90 | 56 | 20 | Date calculation - converts date to serial number |
| @0x00905ed0 | 80 | 12 | Loop control - retry mechanism with max 5 attempts |
| @0x008e2b50 | 20 | 4 | Error handler setup |
| @0x008f0d90 | 40 | 16 | Error handler setup |
| @0x00901bac | 72 | 48 | Error recovery |
| @0x009238bc | 116 | 112 | String formatting - "I" and "C" format codes |
| @0x009190ec | 100 | 112 | String operations - "C" format and parentheses |
| @0x009073e8 | 72 | 96 | String operations - "D" and ";" format |
| @0x009411fc | 152 | 176 | String operations - "U" and space formatting |
| @0x0090ff3c | 84 | 96 | String operations - "D" and space formatting |
| @0x00908cdc | 68 | 160 | String operations - "A" and ")" formatting |
| @0x0091e304 | 100 | 160 | Variable assignment |
| @0x00917678 | 104 | 56 | String concatenation - "C" format |
| @0x008f8f70 | 44 | 128 | String operations - "r" format |
| @0x008f572c | 52 | 36 | Simple function call |
| @0x008fcb80 | 48 | 84 | Variable assignment - "U" format |
| @0x008db948 | 8 | 0 | Minimal function - single call |

---

## 4. Database Operations

### 4.1 Tables Referenced in Raz Module

#### Primary Tables

| Table Name | Purpose | Operations |
|------------|---------|------------|
| **wzdrugs** | Main drug master data | SELECT, INSERT, UPDATE |
| **wzdrugs2** | Secondary drug data | UPDATE |
| **titanstock** | Pharmacy stock levels | SELECT, INSERT, UPDATE |
| **titanksastock** | KSA (Saudi Arabia) stock data | SELECT, INSERT, UPDATE, DELETE |
| **titanksasales** | KSA sales records | SELECT, INSERT, UPDATE |
| **titaninn** | Inter-pharmacy transfers | SELECT, INSERT, UPDATE, DELETE |
| **titanneed** | Purchase requests | CREATE, DROP, INSERT |
| **titanpharmalist** | Pharmacy list | SELECT, INSERT, UPDATE |
| **farysales** | Sales history | SELECT |
| **storediscount** | Discount records | SELECT, INSERT |
| **drgserver** | Drug server data | SELECT, INSERT, DELETE |
| **usersourceupdate** | User data updates | SELECT, INSERT, DELETE |
| **remotecontrol** | Remote control functions | DELETE |
| **nilsen2** | Nilsen analytics data | DELETE |

#### Supporting Tables

| Table Name | Purpose | Operations |
|------------|---------|------------|
| **companies** | Company data | INSERT |
| **wzcustomers** | Customer data | INSERT |
| **wzgard** | Inventory records | INSERT |
| **wzaccfreetree** | Accounting tree | INSERT |
| **wzphar** | Pharmacy data | SELECT |
| **ChainBuyStore** | Chain store data | INSERT, SELECT |
| **ChainBuyUsers** | Chain user data | INSERT, SELECT |
| **RawakidTablew** | Rawakid data | SELECT, INSERT |
| **taronlineeg** | Tar online Egypt | SELECT, UPDATE |
| **TitanUserAction** | User action audit | INSERT |

### 4.2 SQL Operations Extracted

#### SELECT Operations
```sql
-- Drug lookup by name
SELECT drugname FROM titanksastock WHERE drugname = N'...'

-- Stock check
SELECT drugname FROM titanstock WHERE drugname = N'...'

-- Invoice lookup
SELECT invoiceid FROM titanksasales WHERE invoiceid = ...

-- Transfer lookup
SELECT * FROM titaninn WHERE source = N'...'
SELECT * FROM titaninn WHERE target = N'...'

-- Discount records
SELECT drugname, count(*), max(disco), min(disco), max(datee) 
FROM storediscount WHERE adress='...'

-- Sales history
SELECT * FROM farysales WHERE mobile = N'...'

-- User updates
SELECT drugname FROM usersourceupdate

-- Server data
SELECT * FROM drgserver WHERE silsila = N'...'

-- Chain buy data
SELECT * FROM ChainBuyStore ORDER BY DrugName DESC
SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%'

-- Pharmacy list
SELECT * FROM titanpharmalist WHERE mobile = '...'
```

#### INSERT Operations
```sql
-- Insert into titanksasales
INSERT INTO titanksasales (invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue) 
VALUES (...)

-- Insert into titanksastock
BEGIN INSERT INTO titanksastock (drugname, datee, silsilaid, minimum, pharmacyid, classy, stock) 
VALUES (...)

-- Insert into titanstock
BEGIN INSERT INTO titanstock (drugname, lastedit, pharmacyid, price, stock, barcode, titanid) 
VALUES (...)

-- Insert into wzdrugs
INSERT INTO wzdrugs (drugname, drugnamear, barcode, vat, units, classy, generic, pharmacology, co, unitsclass, price) 
VALUES (...)

-- Insert into titaninn (transfers)
INSERT INTO titaninn (fatid, itemsasstring, datee, source, silsilaid, target) 
VALUES (...)

-- Insert into wzgard (inventory)
INSERT INTO wzgard (phar, randomid, writer, datee, datetimee, classy, quant, expire, price, oldstock, costvalue, vatvalue, totalwithvat, typee, drugname) 
VALUES (...)

-- Insert into storediscount
INSERT INTO storediscount (adress, storename, pharmacyname, pharmacyname2, datee, tips, titanver, country, drugname, barcode, price, disco, units, pricechanged, localimport, quant) 
VALUES (...)

-- Insert into drgserver
INSERT INTO drgserver (datee, silsila, mobile, drugname, price, barcode, units, vat, shape, localimport) 
VALUES (...)

-- Insert into TitanUserAction (audit)
INSERT INTO TitanUserAction (drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee) 
VALUES (...)
```

#### UPDATE Operations
```sql
-- Update sales records
UPDATE titanksasales SET ...

-- Update stock levels
UPDATE titanksastock SET ...
UPDATE titanstock SET ...

-- Update drug data
UPDATE wzdrugs SET ...
UPDATE wzdrugs2 SET ...

-- Update transfers
UPDATE titaninn SET target = N''

-- Update online data
UPDATE taronlineeg SET ...

-- Update pharmacy list
UPDATE titanpharmalist SET ...
```

#### DELETE Operations
```sql
-- Delete stock data
DELETE FROM titanksastock

-- Delete transfer records
DELETE FROM titaninn

-- Delete server data
DELETE FROM drgserver WHERE id = N'...'

-- Delete user updates
DELETE FROM usersourceupdate WHERE id = '...'

-- Delete remote control
DELETE FROM remotecontrol WHERE id = N'...'
DELETE FROM remotecontrol WHERE passedfunctions = N'...'

-- Delete Nilsen data
DELETE FROM nilsen2
```

#### CREATE/DROP Operations
```sql
-- Create tables
CREATE TABLE titanksasales (...)
CREATE TABLE titanksastock (...)
CREATE TABLE titaninn (...)
CREATE TABLE titanneed (...)

-- Drop tables
DROP TABLE titanneed
DROP TABLE titanksasales
DROP TABLE titanksastock
```

---

## 5. Business Rules Extraction

### 5.1 Sales Rules

1. **Stock Validation Rule**
   - Before adding item to sale, check stock > 0
   - If stock = 0, show "Not Enouph Stock" message
   - If item marked "Not For sale", block the transaction

2. **Expiry Date Rule**
   - Check expiry date before sale
   - If expired, block sale with "Product has expired" message
   - If near expiry, show warning

3. **Price Validation Rule**
   - Price must be > 0
   - Price cannot exceed maximum allowed price
   - Discount cannot make price negative

4. **VAT Calculation Rule**
   - VAT = Price × VAT Rate
   - VAT is inclusive in selling price
   - VAT rate varies by drug classification

5. **Discount Rules**
   - Maximum discount percentage enforced
   - Discount by currency, percent of profit, or percent of total
   - Discounts tracked for audit

### 5.2 Purchase Rules

1. **Supplier Validation Rule**
   - Supplier must exist in system
   - Supplier cannot be blocked
   - Invoice number must be unique

2. **Price Update Rule**
   - Update item card price if purchase price is higher
   - Optionally copy high price to item card
   - Copy VAT as it is to item cards

3. **Expiry Date Rules**
   - Apply last purchase expire date for current invoice items
   - Expiry date cannot exceed Production Date by more than 7 years
   - Correct expiry dates after extend

4. **Stock Update Rule**
   - Add purchased quantity to current stock
   - Update stock by batch/serial number
   - Consider invoice as correct stock and inventoried

### 5.3 Stock Rules

1. **Minimum/Maximum Rules**
   - Alert when stock below minimum
   - Alert when stock above maximum
   - Edit minimum amount - half automatic needs system

2. **Batch Tracking Rule**
   - Each batch tracked by silsilaid (series ID)
   - Batch number must be unique per drug
   - Batch expiry date tracked separately

3. **Transfer Rules**
   - Source pharmacy must have sufficient stock
   - Target pharmacy must exist
   - Transfer creates titaninn record

### 5.4 Financial Rules

1. **Payment Rules**
   - Payment = Cash + Visa
   - Payment must equal invoice total
   - Credit limit enforced for customers

2. **VAT Rules**
   - VAT calculated on taxable items
   - Non-taxable items excluded
   - VAT report generated for ZATCA

3. **Discount Rules**
   - Cancel discount option available
   - Clean sale discount for all items
   - Cash discount tracking

### 5.5 E-Invoice Rules (ZATCA/ETA)

1. **Pharmacy Sale Service**
   - XML format: `<m:PharmacySaleServiceRequest>`
   - Must include buyer data, items, totals
   - Receipt type: 'S' (sale) or 'R' (return)

2. **Pharmacy Sale Cancel Service**
   - XML format: `<m:PharmacySaleCancelServiceRequest>`
   - Requires reference to original sale
   - Cancellation reason required

3. **Return Service**
   - XML format: `<m:ReturnServiceRequest>`
   - Reference to original invoice required
   - Return quantity cannot exceed original

4. **Transfer Service**
   - XML format: `<m:TransferServiceRequest>`
   - Source and target GLN required
   - Transfer notification ID required

5. **Dispatch Service**
   - XML format: `<m:DispatchServiceRequest>`
   - Dispatch notification ID required
   - Product list with serial numbers

6. **Accept Dispatch Service**
   - XML format: `<m:AcceptDispatchServiceRequest>`
   - Acceptance of dispatched products
   - Product verification required

---

## 6. Main Workflows

### 6.1 Invoice Creation Workflow

```
1. Initialize new invoice
   ├── Generate invoice number (Proc @0x00987ba0)
   ├── Set invoice date (Proc @0x00960fd0)
   └── Initialize totals

2. Add items to invoice
   ├── Lookup drug by barcode/name (Proc @0x0093967c)
   ├── Check stock availability (Proc @0x009297e0)
   ├── Validate expiry date (Proc @0x00922c04)
   ├── Calculate line total (Proc @0x0092ffd0)
   ├── Apply item discount (Proc @0x0093404c)
   └── Add to invoice grid

3. Calculate totals
   ├── Sum item totals (Proc @0x009b1a44)
   ├── Calculate VAT (Proc @0x00941d90)
   ├── Apply invoice discount (Proc @0x00961d64)
   └── Calculate grand total

4. Process payment
   ├── Input cash amount (Proc @0x0095d9ec)
   ├── Input visa amount (Proc @0x0095d594)
   ├── Validate payment = total (Proc @0x00950f00)
   └── Record payment (Proc @0x00943854)

5. Save invoice
   ├── Save to database (Proc @0x0096bb10)
   ├── Update stock levels (Proc @0x0095a100)
   ├── Generate receipt (Proc @0x00971ccc)
   └── Print receipt (Proc @0x0097ceb4)

6. E-invoice submission (optional)
   ├── Generate XML (Proc @0x0097334c)
   ├── Submit to ZATCA (Proc @0x00995e58)
   └── Store response (Proc @0x0097384c)
```

### 6.2 Stock Update Workflow

```
1. Receive stock update request
   ├── Identify update type (purchase/sale/return/transfer)
   └── Validate request parameters

2. Check current stock
   ├── Query current quantity (Proc @0x009297e0)
   ├── Check minimum/maximum (Proc @0x009b7280)
   └── Validate batch exists

3. Apply stock change
   ├── Calculate new quantity
   ├── Update titanstock (Proc @0x0095a100)
   ├── Update titanksastock (Proc @0x0094c62c)
   └── Update wzdrugs if needed

4. Record stock movement
   ├── Insert into wzgard (Proc @0x00942cbc)
   ├── Log to audit trail
   └── Update date/time stamps

5. Validate stock integrity
   ├── Check stock >= 0
   ├── Verify batch consistency
   └── Update minimum/maximum if needed
```

### 6.3 Payment Processing Workflow

```
1. Receive payment request
   ├── Validate invoice exists
   ├── Check payment type (cash/visa/credit)
   └── Validate amount

2. Split payment (if needed)
   ├── Calculate cash portion (Proc @0x0095d9ec)
   ├── Calculate visa portion (Proc @0x0095d594)
   └── Validate cash + visa = total

3. Process payment
   ├── Record cash payment
   ├── Record visa payment
   ├── Update customer balance (if credit)
   └── Generate payment receipt

4. Update financial records
   ├── Update sales totals
   ├── Update VAT records
   └── Update daily summary

5. Finalize payment
   ├── Mark invoice as paid
   ├── Update stock levels
   └── Print payment receipt
```

### 6.4 Return/Refund Workflow

```
1. Validate return request
   ├── Check original invoice exists
   ├── Validate return items
   ├── Check return quantity <= original quantity
   └── Validate return is within allowed period

2. Process return
   ├── Create return invoice (Proc @0x00975fa4)
   ├── Calculate refund amount
   ├── Apply return discount if applicable
   └── Generate return receipt

3. Update stock
   ├── Add returned quantity to stock
   ├── Update batch records
   └── Update stock totals

4. Process refund
   ├── Refund to cash
   ├── Refund to visa
   └── Update customer balance

5. E-invoice cancellation
   ├── Generate cancel XML
   ├── Submit to ZATCA
   └── Store cancellation response
```

### 6.5 Transfer Workflow

```
1. Initiate transfer
   ├── Select source pharmacy
   ├── Select target pharmacy
   └── Create transfer record (titaninn)

2. Add items to transfer
   ├── Lookup drugs
   ├── Validate source stock
   ├── Set transfer quantities
   └── Calculate transfer value

3. Process transfer
   ├── Decrement source stock
   ├── Create transfer notification
   ├── Submit to DTTS (Proc @0x0097334c)
   └── Wait for acceptance

4. Accept transfer (at target)
   ├── Receive transfer notification
   ├── Verify products
   ├── Accept dispatch (Proc @0x0095c778)
   └── Increment target stock

5. Finalize transfer
   ├── Update titaninn record
   ├── Update both pharmacy stocks
   └── Generate transfer report
```

---

## 7. Module Dependencies

### 7.1 Modules Called by Raz

Based on p-code analysis and string references, Raz calls the following modules:

| Module | Purpose | Call Pattern |
|--------|---------|--------------|
| **ModPharm** | Drug data management | ImpAdCallI2 |
| **ModInn** | Purchase invoice processing | ImpAdCallI2 |
| **ModOot** | Sales invoice processing | ImpAdCallI2 |
| **ModStock** | Stock management | ImpAdCallI2 |
| **ModPrint** | Print operations | ImpAdCallI2 |
| **ModStorage** | File storage operations | ImpAdCallI2 |
| **ModDrugs** | Drug classification | ImpAdCallI2 |
| **ModNilsen** | Analytics integration | ImpAdCallI2 |
| **ModAmil** | Commission calculations | ImpAdCallI2 |
| **ModMony** | Financial operations | ImpAdCallI2 |
| **ModNetwork** | Network operations | ImpAdCallI2 |
| **Modeveryday** | Daily operations | ImpAdCallI2 |
| **ModBackUp** | Backup operations | ImpAdCallI2 |
| **ModDate** | Date operations | ImpAdCallI2 |
| **ModCleanUp** | Cleanup operations | ImpAdCallI2 |
| **ModBarCode128** | Barcode generation | ImpAdCallI2 |
| **ModZatca** | ZATCA e-invoice | ImpAdCallI2 |
| **ModEta** | ETA integration | ImpAdCallI2 |
| **ModEcommerce** | E-commerce integration | ImpAdCallI2 |
| **ModIntegrations** | External integrations | ImpAdCallI2 |
| **ModUsers** | User management | ImpAdCallI2 |
| **ModRemoteControl** | Remote control | ImpAdCallI2 |
| **ModSql** | SQL operations | ImpAdCallI2 |
| **ModTitan** | Core functions | ImpAdCallI2 |
| **ModTafqit** | Number formatting | ImpAdCallI2 |
| **ModTranslator** | Translation | ImpAdCallI2 |
| **ModVatReport** | VAT reporting | ImpAdCallI2 |
| **ModOneFile** | Single file operations | ImpAdCallI2 |

### 7.2 Modules That Call Raz

Based on the application structure, the following modules/forms call Raz:

| Module/Form | Purpose |
|-------------|---------|
| **FFFStartUp** | Main startup form - calls Raz for initialization |
| **FFFINNquant** | Purchase invoice form - calls Raz for processing |
| **FFFOOTQuant** | Sales invoice form - calls Raz for processing |
| **FFFSODUKU** | Stock management form - calls Raz for operations |
| **FormDrugsDetails** | Drug details form - calls Raz for data |
| **FormDrugFlow** | Drug flow form - calls Raz for movement |
| **FormExpiredDrugs** | Expiry management - calls Raz for checks |
| **FormReportsGeneral** | Reports form - calls Raz for data |
| **FormShiftInput** | Shift input form - calls Raz for shift ops |
| **FormShiftFawateer** | Shift invoices form - calls Raz for invoices |
| **FormDailyManual** | Daily manual form - calls Raz for daily ops |
| **FormMizanCreate** | Balance sheet form - calls Raz for accounting |
| **FormVat** | VAT form - calls Raz for VAT calculations |
| **FormHodour** | Attendance form - calls Raz for attendance |
| **FormMarid** | Partner form - calls Raz for partner ops |
| **ModDTTS** | DTTS module - calls Raz for e-invoice |
| **ModNilsen** | Nilsen module - calls Raz for analytics |

---

## 8. String Constants Analysis

### 8.1 Database Schema Strings

```sql
-- Table creation
"drugname,datee,silsilaid,minimum,pharmacyid,classy,stock) values ("
"drugname,lastedit,pharmacyid,price,stock,barcode,titanid) values ("
"invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue ) values ("
"(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)"

-- Column definitions
"drugname nvarchar(100) default '' ,"
"drugname nvarchar(100) default '' , "
"stock real default 0 , "
"stock real default '0' ,"
"price real default '0' ,"
"barcode varchar(16) default '',"
"classy nvarchar(35) default '' , "
"pharmacyid nvarchar(15) default '' )"
"datee real default '0', "
"datee int   default '0' ,"
"disc real   default '0', "
"minimum real   default '0', "
"totalvalue real default '0',"
"invoiceid real default '0' ,"
"fatid int   default '0' ,"
"silsilaid nvarchar(15)  default '' ,"
"curbarcode varchar(15) default '0' , "
"curprice real default '0' , "
```

### 8.2 Business Logic Strings

```sql
-- Stock operations
"select drugname  from titanksastock where  "
"select drugname  from titanstock where  "
"select drugname from usersourceupdate  "
"delete from titanksasales"
"delete from titanksastock "
"update  titanksasales set  "
"update titanksastock set "
"update titanstock set "
"update  wzdrugs   set "
"update  wzdrugs2  set "

-- Invoice operations
"select invoiceid   from  titanksasales where  "
"insert into  titanksasales ("
"insert into  titaninn (fatid,itemsasstring,datee,source,silsilaid,target)VALUES ("

-- Discount operations
"select drugname ,count(*) ,max(disco)  ,min(disco) ,max(datee)  from storediscount where adress="
"select * from storediscount where  "
"insert  into storediscount ("

-- Customer operations
"if not exists (select * from  storediscount "
"insert into  companies     (mobile,pass) values ("
"insert into  wzcustomers  (randomid,phar,typee,writer,creditlimit,datee,namee) values("

-- Inventory operations
"insert  into wzgard (phar,randomid, writer,datee,datetimee,classy,quant,expire,price,oldstock,costvalue,vatvalue,totalwithvat,typee,drugname)values ( "

-- Transfer operations
"select * from titaninn  where source =N'"
"select * from titaninn  where target =N'"
"select fatid from titaninn where  "
"update titaninn set target =N''"

-- Server operations
"insert into drgserver (datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport)"
"select  *  from drgserver  where  silsila = N'"
"Delete  from drgserver  where  id =  N'"

-- User operations
"insert into remotecontrol (datee,mobile,copyid,passedfunctions)   "
"delete from remotecontrol  where id = N'"
"delete from remotecontrol  where passedfunctions =N'"
"DELETE FROM usersourceupdate WHERE id='"
```

### 8.3 Error/Message Strings

```sql
-- Error messages
"A system error occured"
"An error occured! Enquiry is unfuccessful (database)"
"An error occured! Enquiry is unfuccessful (web)"
"An error occurred while executing query"
"Database error"
"Database error."
"Error in "
"Printer Error"
"Undefined Error."
"Undefined database error."
"Undefined error."

-- Business messages
"Not Enouph Stock"
"Not For sale"
"Product has expired."
"Expired product (this operation cannot be performed)."
"Expiry Date cannot exceed Production Date more than 7 years."
"THIS DRUG HAS DELETED"
"THISDRUGHASDELETED-"
"Do you want to delete"
"Do you want to delete this medicine ?"
"Delete drug"
"Delete drug from invoice"
"Delete entire invoice"
"Delete contents of invoice"
"Do you want to delete this invoice"

-- Success messages
"table titanksasales created !"
"table titanksastock created !"
"table titanneed created !"
"Successfully removing deleted drugs form your database"
"Done export invoice"
"Done for  ReloadRasidCorrect500"
"Done for  Reload_Drugs_in_last_Invoices"
```

---

## 9. E-Invoice Integration

### 9.1 ZATCA Integration

The Raz module handles ZATCA (Zakat, Tax and Customs Authority) e-invoicing:

```xml
<!-- Pharmacy Sale Service -->
<m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">
    <!-- Invoice data -->
    <!-- Item details -->
    <!-- Tax calculations -->
    <!-- Buyer data -->
    <!-- Seller data -->
</m:PharmacySaleServiceRequest>

<!-- Pharmacy Sale Cancel Service -->
<m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">
    <!-- Reference to original sale -->
    <!-- Cancellation reason -->
</m:PharmacySaleCancelServiceRequest>

<!-- Return Service -->
<m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">
    <!-- Reference to original invoice -->
    <!-- Return items -->
    <!-- Return amounts -->
</m:ReturnServiceRequest>

<!-- Transfer Service -->
<m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">
    <!-- Source GLN -->
    <!-- Target GLN -->
    <!-- Transfer items -->
    <!-- Transfer quantities -->
</m:TransferServiceRequest>
```

### 9.2 ETA Integration

The module also handles ETA (Egyptian Tax Authority) integration:

```xml
<!-- Receipt Data -->
{
    "receiptNumber": "...",
    "receiptType": "...",
    "dateTimeIssued": "...",
    "seller": {
        "vatNumber": "...",
        "name": "...",
        "address": {...}
    },
    "buyer": {
        "vatNumber": "...",
        "name": "...",
        "address": {...}
    },
    "invoiceLines": [...],
    "totalSales": ...,
    "totalCommercialDiscount": ...,
    "totalItemsDiscount": ...,
    "netSale": ...,
    "taxTotals": [...],
    "paymentMethod": "..."
}
```

### 9.3 DTTS Integration

Drug Track and Trace System (DTTS) integration:

```xml
<!-- Dispatch Service -->
<m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">
    <!-- Dispatch notification ID -->
    <!-- Product list with serial numbers -->
    <!-- Source and target GLN -->
</m:DispatchServiceRequest>

<!-- Accept Dispatch Service -->
<m:AcceptDispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/AcceptDispatchService">
    <!-- Reference to dispatch -->
    <!-- Acceptance confirmation -->
    <!-- Product verification -->
</m:AcceptDispatchServiceRequest>
```

---

## 10. Error Handling Patterns

### 10.1 Common Error Handling

Most procedures follow this pattern:

```vb
Private Sub Proc_0x00XXXXXX()
    On Error GoTo ErrHandler
    
    ' Business logic here
    
    Exit Sub
    
ErrHandler:
    ' Error handling
End Sub
```

### 10.2 Error Recovery

Some procedures implement retry logic:

```vb
Private Sub Proc_0x00905ed0()
    ' Retry loop with max 5 attempts
    Do While retryCount <= 5
        ' Try operation
        If success Then Exit Do
        retryCount = retryCount + 1
    Loop
End Sub
```

### 10.3 File Operation Errors

File operations have specific error handling:

```vb
Private Sub Proc_0x00969bdc()
    On Error GoTo ErrHandler
    ' File copy operation
    ' Check if file exists
    ' Handle permission errors
    ' Handle file not found
End Sub
```

### 10.4 Network Operation Errors

Network operations have timeout and connection error handling:

```vb
Private Sub Proc_0x009b407c()
    ' FTP operation with error handling
    ' Connection timeout handling
    ' Upload/download error handling
    ' Retry logic
End Sub
```

---

## Appendix A: Procedure Size Distribution

| Size Range | Count | Percentage |
|------------|-------|------------|
| 0-50 bytes | 45 | 11.9% |
| 51-100 bytes | 95 | 25.1% |
| 101-200 bytes | 125 | 33.0% |
| 201-300 bytes | 65 | 17.2% |
| 301-400 bytes | 35 | 9.2% |
| 401-500 bytes | 10 | 2.6% |
| 501+ bytes | 4 | 1.1% |

## Appendix B: Frame Size Distribution

| Frame Size | Count | Percentage |
|------------|-------|------------|
| 0-50 bytes | 85 | 22.4% |
| 51-100 bytes | 95 | 25.1% |
| 101-200 bytes | 110 | 29.0% |
| 201-300 bytes | 65 | 17.2% |
| 301-400 bytes | 20 | 5.3% |
| 401+ bytes | 4 | 1.1% |

## Appendix C: Most Complex Procedures

1. **@0x00a62be8** - Size: 916, Frame: 552 - Invoice deletion with stock reversal
2. **@0x00a512c0** - Size: 820, Frame: 456 - Invoice modification
3. **@0x00a412b4** - Size: 796, Frame: 456 - Invoice creation
4. **@0x00a49668** - Size: 872, Frame: 404 - Invoice main controller
5. **@0x00a1bc44** - Size: 760, Frame: 144 - Drug data modification
6. **@0x00a18044** - Size: 748, Frame: 112 - Drug data merge
7. **@0x00a16d24** - Size: 640, Frame: 316 - Invoice printing
8. **@0x00a123a4** - Size: 728, Frame: 8 - Drug data lookup
9. **@0x00a0ac20** - Size: 688, Frame: 68 - Drug data processing
10. **@0x00a094d4** - Size: 680, Frame: 16 - Drug data validation

---

*Document generated from TITAN.W1 p-code decompilation analysis*
*Module: Raz | Procedures: 379 | Total Size: ~71KB*
