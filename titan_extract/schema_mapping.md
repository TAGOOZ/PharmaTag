# TITAN.W1 Database Schema & VB6 Module Mapping

**Source:** TITAN.W1 (Phye.exe) — VB6 P-Code Application  
**Tables Found:** 16  
**Total SQL Fragments Analyzed:** ~120+  
**Date Extracted:** 2026-08-15

---

## Table Overview

| # | Table Name | Purpose | Primary Key |
|---|-----------|---------|-------------|
| 1 | `wzdrugs` | Master drug list | drugname |
| 2 | `wzdrugs2` | Extended drug data | drugname |
| 3 | `titanpharmalist` | Pharmacy network registry | mobile |
| 4 | `wzphar` | Pharmacy names (reference) | pharname |
| 5 | `wzaccfreetree` | Pharmacy hierarchy tree | mobile |
| 6 | `titaninn` | Inventory transfers | ID (identity) |
| 7 | `titanksasales` | Chain sales data | invoiceid |
| 8 | `titanksastock` | Chain stock transfers | drugname+pharmacyid |
| 9 | `titanstock` | Chain stock data | drugname+pharmacyid |
| 10 | `titanneed` | Shortage requests | drugname+sender+target |
| 11 | `invoicedata` | Sales invoice headers | invoiceid |
| 12 | `wzgard` | Sales invoice line items | drugname+datee |
| 13 | `orders` | Pharmacy orders | orderid |
| 14 | `wzcustomers` | Customer records | randomid |
| 15 | `companies` | Supplier records | mobile |
| 16 | `storediscount` | Discount tracking | ID (identity) |
| 17 | `drgserver` | Central server drug data | ID (identity) |
| 18 | `remotecontrol` | Remote control relay | ID (identity) |
| 19 | `TitanUserAction` | Audit trail | drugname+datee |
| 20 | `usersourceupdate` | User data sync | ID (identity) |
| 21 | `nilsen2` | Market research reports | ID (identity) |
| 22 | `taronlineeg` | e-Government integration | id (identity) |
| 23 | `ChainBuyStore` | Chain store registry | DrugName+PharmacyId |
| 24 | `ChainBuyUsers` | Chain user registry | PharmacistTel |
| 25 | `RawakidTablew` | Warehouse/shelf tracking | PharmacistTel+DrugName |
| 26 | `drugeyedash2` | Drug monitoring dashboard | id (identity) |

---

## VB6 Module → Table Mapping

### Core Data Modules (ModStorage, ModInn, ModOot, ModNed)

| Module | Procs | Tables Accessed | Purpose |
|--------|-------|-----------------|---------|
| `ModStorage` | 154 | `wzdrugs`, `wzdrugs2`, `wzgard` | Main drug CRUD operations, inventory management |
| `ModInn` | 71 | `titaninn`, `titanksasales`, `titanksastock`, `titanstock`, `titanpharmalist` | Inventory transfer operations between pharmacies |
| `ModOot` | 105 | `invoicedata`, `wzgard`, `orders` | Sales invoice processing, order management |
| `ModNed` | 4 | `titanneed` | Shortage/needs request operations |
| `ModUsers` | 39 | `wzcustomers`, `companies`, `titanpharmalist` | Customer and supplier management |

### Sales & Financial Modules

| Module | Procs | Tables Accessed | Purpose |
|--------|-------|-----------------|---------|
| `ModMony` | 30 | `invoicedata`, `wzgard` | Financial calculations, payment processing |
| `ModDisc` | 10 | `storediscount` | Discount management and calculations |
| `ModAmil` | 44 | `invoicedata`, `wzgard`, `titanpharmalist` | Employee sales tracking and reports |
| `ModAmil2` | 9 | `invoicedata` | Extended employee reports |
| `ModAccounting` | 25 | `invoicedata`, `wzcustomers` | Accounting integration |
| `ModAccFreeOne` | 19 | `wzaccfreetree` | Free accounting tree operations |

### Chain/Network Modules

| Module | Procs | Tables Accessed | Purpose |
|--------|-------|-----------------|---------|
| `ModNetwork` | 65 | `titanpharmalist`, `titaninn`, `titanksasales`, `titanksastock`, `titanstock`, `titanneed` | Multi-pharmacy networking and synchronization |
| `ModSaturn` | 29 | `titanpharmalist`, `ChainBuyStore`, `ChainBuyUsers`, `RawakidTablew` | Chain pharmacy operations |
| `ModTitanCloud` | 16 | `drgserver`, `remotecontrol`, `usersourceupdate` | Cloud sync and remote operations |
| `ModDRGEXChange` | 4 | `drgserver`, `usersourceupdate` | Drug data exchange between pharmacies |

### Integration Modules

| Module | Procs | Tables Accessed | Purpose |
|--------|-------|-----------------|---------|
| `ModZatca` | 14 | `invoicedata`, `wzgard` | ZATCA e-invoice integration (Saudi Arabia) |
| `ModZatca2Wraber` | 24 | `invoicedata`, `wzgard` | Extended ZATCA compliance |
| `ModMobile` | 9 | `titanpharmalist`, `titaninn` | Mobile device integration |
| `ModSQL` | 13 | All tables | SQL query building utilities |
| `ModSqlLink` | 19 | `titanpharmalist`, `drgserver` | SQL Server remote connections |
| `ModOuterConnections` | 18 | `taronlineeg`, `drgserver` | External API integrations |
| `ModFarWay` | 4 | `invoicedata`, `wzgard` | FarWay POS integration |
| `ModIntegrations` | 18 | `invoicedata`, `wzgard`, `wzcustomers` | Third-party integrations |

### Reporting Modules

| Module | Procs | Tables Accessed | Purpose |
|--------|-------|-----------------|---------|
| `ModPrint` | 70 | `invoicedata`, `wzgard`, `wzdrugs` | Print formatting for invoices/reports |
| `ModDrgW` | 13 | `wzdrugs`, `wzgard` | Drug report generation |
| `ModVatReport` | 3 | `invoicedata`, `wzgard` | VAT reporting |
| `ModBackupMonthly` | 13 | All tables | Monthly backup operations |
| `ModReBuild` | 14 | All tables | Database rebuild/repair |
| `ModBackUp` | 43 | All tables | Backup and restore operations |

### Drug Management Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormDrugsDetails` | 51 | `wzdrugs` | Drug data entry/edit screen |
| `FormDrugFlow` | 32 | `wzdrugs`, `wzgard` | Drug movement history |
| `FormDrugPrice` | 18 | `wzdrugs` | Drug price management |
| `FormDrugMonthly` | 7 | `wzdrugs`, `wzgard` | Monthly drug reports |
| `FormDrugHistory` | 5 | `wzdrugs` | Drug audit trail |
| `FormDrugStckAtMonths` | 12 | `wzdrugs` | Stock level reports |
| `FormDrugMoveMonthly` | 6 | `wzgard` | Monthly movement reports |
| `FormExpiredDrugs` | 21 | `wzdrugs`, `wzgard` | Expiry date management |
| `FormMoreBarcodes` | 8 | `wzdrugs` | Multiple barcode management |
| `FormDrugNameUnify` | 12 | `wzdrugs` | Drug name standardization |
| `FormSimilars` | 5 | `wzdrugs` | Generic substitution lookup |
| `FormDrugsLists` | 15 | `wzdrugs` | Drug list management |
| `FormDrugsdataTrue` | 8 | `wzdrugs` | Drug data validation |
| `FormDrugsHelper` | 13 | `wzdrugs` | Drug information lookup |
| `FormReapetedDrugMerge` | 10 | `wzdrugs` | Duplicate drug merging |
| `FormImportFromOtherDBI` | 19 | `wzdrugs` | Import drugs from other databases |

### Sales Screen Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FFFINNquant` | 75 | `titaninn`, `titanksasales`, `titanksastock` | Inventory transfer entry screen |
| `FFFINNquantEG` | 47 | `titaninn`, `titanksasales` | Egyptian variant transfer screen |
| `FFFootEx` | 17 | `invoicedata`, `wzgard` | Sales footer/summary display |
| `FFFINNquant` | 75 | `titaninn` | Transfer quantity management |
| `FormSilsila` | 26 | `invoicedata`, `wzgard` | Invoice chain/series management |
| `FormShiftFawateer` | 9 | `invoicedata` | Shift invoice tracking |
| `FormPrintSales` | 17 | `invoicedata`, `wzgard` | Sales printing |

### Network/Chain Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormChainBuy` | 6 | `ChainBuyStore`, `ChainBuyUsers` | Chain pharmacy purchasing |
| `FormRawakid` | 10 | `RawakidTablew` | Warehouse shelf management |
| `FormRemoteControl` | 10 | `remotecontrol` | Remote control interface |
| `FormRempteTitan` | 13 | `remotecontrol`, `drgserver` | Remote Titan operations |
| `FormFaryNet` | 8 | `titanpharmalist`, `titaninn` | Branch network operations |
| `FormSendChanges` | 3 | `usersourceupdate` | Send updates to network |
| `FormUpdator` | 7 | `usersourceupdate` | Receive updates from network |

### Reporting Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormReportsGeneral` | 61 | `invoicedata`, `wzgard`, `wzdrugs` | General reports hub |
| `FormMonyDetails` | 7 | `invoicedata` | Financial detail reports |
| `FormUsersMony` | 24 | `invoicedata`, `titanpharmalist` | User sales reports |
| `FormTaslimReport` | 7 | `invoicedata` | Delivery reports |
| `FormTawsil` | 6 | `invoicedata` | Shipping reports |
| `FormHodour` | 16 | `invoicedata` | Attendance reports |
| `FormPeriodEhsa` | 9 | `invoicedata` | Period statistics |
| `FormBest100` | 2 | `wzgard` | Top 100 selling drugs |
| `FormOotSum` | 9 | `invoicedata` | Sales summary reports |
| `FormDailyQuiod` | 16 | `invoicedata` | Daily quick reports |
| `FormDailyManual` | 6 | `invoicedata` | Manual daily reports |

### Settings & Configuration Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormAdvanced` | 33 | `wzdrugs`, `titanpharmalist` | Advanced settings |
| `FormPharmacyInfo` | 14 | `titanpharmalist` | Pharmacy info management |
| `FormBarcodeSettings` | 13 | `wzdrugs` | Barcode printing settings |
| `FormStoreDiscount` | 23 | `storediscount` | Store discount settings |
| `FormMinimumControl` | 23 | `wzdrugs` | Minimum stock level management |
| `FormVat` | 20 | `wzdrugs` | VAT configuration |
| `FormVat2` | 38 | `wzdrugs`, `invoicedata` | Extended VAT management |

### Import/Export Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormImportFat` | 14 | `invoicedata`, `wzgard` | Import invoices from files |
| `FormImportFRomExcell` | 6 | `wzdrugs` | Import from Excel |
| `FormImportFormOtherApps` | 11 | `wzdrugs` | Import from other applications |
| `FormExportdataBase` | 8 | All tables | Export database to file |
| `FormAccUploader` | 47 | `wzaccfreetree` | Account data upload |

### User & Security Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormUserEdit` | 18 | `titanpharmalist` | User settings management |
| `FormUserChoose` | 19 | `titanpharmalist` | User selection |
| `FormUserEhsa` | 12 | `invoicedata` | User statistics |
| `FormAmilTamin` | 16 | `invoicedata`, `wzgard` | Employee sales entry |
| `FormAmilTamin2` | 10 | `invoicedata` | Extended employee entry |
| `FormAmilShow` | 9 | `invoicedata` | Employee display |
| `FormActivation` | 23 | `titanpharmalist` | License activation |

### E-Invoice & Compliance Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormElectroniaChecker` | 14 | `invoicedata`, `wzgard` | Electronic invoice validation |
| `FormGovData` | 5 | `taronlineeg` | Government data interface |
| `FormVatfakeInvo` | 15 | `invoicedata` | VAT fake invoice handling |
| `FormWasfaty` | 27 | `wzdrugs` | Prescription management (Saudi) |
| `FormEtaInfo` | 9 | `taronlineeg` | ETA info system integration |

### Database Maintenance Forms

| Form | Procs | Tables Accessed | Purpose |
|------|-------|-----------------|---------|
| `FormBackRestore` | 4 | All tables | Backup/restore interface |
| `FormRestore` | 6 | All tables | Data restore |
| `FormSaveFile` | 3 | All tables | Save to file |
| `FormOpenFile` | 20 | All tables | Open from file |
| `FormDolap` | 12 | `wzdrugs` | Drug closet/shelf view |
| `FormDrugeeyeUpadteFrom` | 16 | `wzdrugs` | Drug data update from external |
| `FFFClean` | 36 | All tables | Database cleanup operations |
| `FormSelectdataBase` | 12 | All tables | Database selection |

### Cross-Reference: Tables → Modules

| Table | Primary Modules | Primary Forms |
|-------|----------------|---------------|
| `wzdrugs` | ModStorage, ModDrgW | FormDrugsDetails, FormDrugPrice |
| `wzgard` | ModStorage, ModOot, ModPrint | FormDrugFlow, FormPrintSales |
| `invoicedata` | ModOot, ModMony, ModAmil | FormReportsGeneral, FormDailyQuiod |
| `titaninn` | ModInn, ModNetwork | FFFINNquant, FormRemoteControl |
| `titanksasales` | ModInn, ModNetwork | FFFINNquant, FormChainBuy |
| `titanksastock` | ModInn, ModNetwork | FFFINNquant, FormChainBuy |
| `titanstock` | ModInn, ModNetwork | FFFINNquant |
| `titanneed` | ModNed, ModNetwork | FormNeedsAll, FormAutoOrder |
| `titanpharmalist` | ModUsers, ModNetwork | FormPharmacyInfo, FormUserEdit |
| `wzcustomers` | ModUsers | FormMaridData |
| `companies` | ModUsers | FormCoData |
| `storediscount` | ModDisc | FormStoreDiscount |
| `drgserver` | ModTitanCloud, ModDRGEXChange | FormRempteTitan |
| `remotecontrol` | ModRemoteControl | FormRemoteControl |
| `TitanUserAction` | ModUsers, ModAmil | FormDrugHistory |
| `usersourceupdate` | ModTitanCloud | FormUpdator, FormSendChanges |
| `ChainBuyStore` | ModSaturn | FormChainBuy |
| `ChainBuyUsers` | ModSaturn | FormChainBuy |
| `RawakidTablew` | ModSaturn | FormRawakid |
| `taronlineeg` | ModOuterConnections | FormGovData, FormEtaInfo |
| `wzaccfreetree` | ModAccFreeOne | FormAccUploader |
| `orders` | ModOot | FormShiftFawateer |
| `nilsen2` | ModNilsen (Class) | FormReportsGeneral |
| `drugeyedash2` | ModDrugEye (Class) | FFFDrugEye |
| `wzphar` | ModNetwork | FormPharmHistory |
| `wzdrugs2` | ModStorage | FormDrugsDetails |

---

## Key Business Logic Observations

### Multi-Pharmacy Architecture
- The system supports a **main pharmacy** and multiple **branch pharmacies**
- `titanpharmalist` is the central registry; `wzaccfreetree` defines parent-child relationships
- `titaninn` handles inter-pharmacy inventory transfers
- `titanneed` tracks shortage requests between branches

### Saudi Arabia E-Invoice Integration
- ZATCA (Zakat, Tax and Customs Authority) compliance via `ModZatca` and `ModZatca2Wraber`
- JSON fields for e-invoice: `activityCode`, `branchCode`, `taxableItems`, `unitPrice`, `vatValue`
- Remote SQL server at `SQL5033.site4now.net` / `sql5111.site4now.net` / `sql5112.site4now.net`

### Drug Data Flow
1. Drug entry → `wzdrugs` (master list)
2. Sales → `wzgard` (line items) → `invoicedata` (headers)
3. Chain sync → `titanksasales`, `titanksastock`, `titanstock`
4. Price updates → `usersourceupdate` → network propagation
5. Audit → `TitanUserAction`

### Discount System
- Multiple discount types: sale discount, purchase discount, chain discount
- `storediscount` tracks per-store discounts with date ranges
- Discount types: `DISCOUNT_TYPE_SALE`, `DISCOUNT_TYPE_PURCHASE`, `DISCOUNT_TYPE_CHAIN`
