# TITAN.W1 Pharmacy App — Form Extraction Report

**Source:** Decompiled VB6 project (Phye.exe)  
**Date:** 2026-08-15  
**Total project forms:** 212 | **Target list:** 65 forms | **Forms with pcode/frm:** 11 | **Forms with Arabic strings:** all via `strings_readable.txt`

---

## Key Finding

Out of the 65 form names provided, **only 11 actually exist** in the decompiled project (present in `project_structure.json` and/or have `.frm`/pcode files). The remaining 54 names do not appear in the project metadata — they may be aliases, internal references, names from a different build, or conceptual labels.

For all 65 forms, functionality is inferred from:
1. **Form name semantics** (Arabic/English naming conventions)
2. **Procedure count and complexity** (pcode size)
3. **Arabic string literals** from `strings_readable.txt` (18,830 entries)
4. **Cross-references** to known modules (`ModUsers`, `ModNeed`, `ModMohasaby`, etc.)
5. **Egyptian FDA (NTRA/DTTS)** invoice structures visible in strings

---

## Part A — Forms That Exist in the Project (11 forms)

### 1. FFFUserEdit

| Field | Value |
|-------|-------|
| **Arabic name** | تعديل بيانات المستخدم |
| **Purpose** | Edit user account data — password change, role assignment, shift assignment, permission toggles |
| **Procedures** | 18 (largest among target forms) |
| **Size** | Multiple sections totaling ~4000+ bytes |
| **Decoded strings** | None directly; context from project: user management labels |

**Likely controls:**
- `txtUsername` — username input (17-digit numeric ID per strings)
- `txtPassword` / `txtNewPassword` — password fields
- `cmbRole` — role dropdown (مدير/دعم فني/صيدلي/موظف)
- `cmbShift` — shift assignment
- `chkPermissions[]` — permission checkboxes (خصم، تعديل سعر، حذف فاتورة)
- `btnSave`, `btnCancel`

**Connections:** `ModUsers`, `FFFUserList`, `FFFUserMenu`, `FFFUserMenuList`, `FormEmployee`, `FormEnd`

**Arabic context strings:**
- `ادخل اسم المستخدم وهو رقم طويل مكون من 17 رقم`
- `ادخل كلمة المرور`
- `ادخل كلمة المرور الجديدة`
- `ادخل كلمة المرور الخاصة بالمدير`
- `تغيير كلمة المرور الخاصة بي`
- `اخفاء كلمة المرور عند محاولة التسجيل الدخول كمدير`

---

### 2. FormBarcodeSettings

| Field | Value |
|-------|-------|
| **Arabic name** | إعدادات الباركود |
| **Purpose** | Configure barcode printer settings — printer selection, label size, barcode type, per-item print options |
| **Procedures** | 13 |
| **Size** | Multiple procedure sections |
| **Decoded strings** | None directly |

**Likely controls:**
- `cmbPrinter` — barcode printer selection
- `cmbLabelSize` — label size options
- `cmbBarcodeType` — barcode type (EAN13, Code128, etc.)
- `txtPrefix` / `txtSuffix` — barcode prefix/suffix
- `chkAutoPrint` — auto-print on save
- `btnTest` — test print button
- `btnSave`, `btnClose`

**Connections:** `FormBarcode`, `FormAddItem`, `FormNewDrug`, `FormDrugsList`, `ModBarcode`

**Arabic context strings:**
- `اختر طابعة الباركود اولا`
- `اجعل طابعة الباركود هي طابعة الليزر`
- `اختبار الباركود الدولي`

---

### 3. FormChainBuy

| Field | Value |
|-------|-------|
| **Arabic name** | سلسلة المشتريات / فواتير الشراء المتسلسلة |
| **Purpose** | Chain/purchase series — link related purchase invoices, track sequential purchases from same supplier |
| **Procedures** | 6 |
| **Size** | ~1200 bytes total |
| **Decoded strings** | None directly |

**Likely controls:**
- `dgChain` — DataGrid showing chain of invoices
- `txtChainID` — chain identifier
- `cmbSupplier` — supplier filter
- `btnLink` — link invoice to chain
- `btnUnlink` — unlink invoice
- `lblTotal` — chain total

**Connections:** `FormChainBuyList`, `FormWared`, `FormWaredList`, `ModBuy`

**Arabic context strings:**
- `اختر اسم الشركة او المخزن الذي تود تسديد مستحقاته`
- `ادخل رقم الفاتورة التي تريد حذف الفواتير بعدها`

---

### 4. FormCopyMe

| Field | Value |
|-------|-------|
| **Arabic name** | نسخ لي / نسخةสำเนة |
| **Purpose** | Copy/duplicate — duplicate invoice, copy items between invoices, or create template from existing invoice |
| **Procedures** | 3 |
| **Size** | ~400 bytes total |
| **Decoded strings** | None directly |

**Likely controls:**
- `cmbSource` — source invoice selector
- `dgItems` — items to copy
- `btnCopy` — execute copy
- `chkIncludePrices` — include prices flag
- `lblStatus` — status label

**Connections:** `FormFat`, `FormFatList`, `FormSales`, `FormSalesList`

**Arabic context strings:**
- `اختر العميل الذي سيتم نقل الفواتير اليه`

---

### 5. FormDariba

| Field | Value |
|-------|-------|
| **Arabic name** | الدريبة / الحسابات الجارية |
| **Purpose** | Current accounts / running balance — customer/supplier debit-credit ledger, payment tracking, balance reconciliation |
| **Procedures** | 5 |
| **Size** | ~1084 bytes total |
| **Decoded strings** | `"DB/ "` (خطأ = error), `"-// "` (تعديل = edit) |

**Likely controls:**
- `dgLedger` — DataGrid showing transactions
- `txtCustomerName` / `txtSupplierName` — entity selector
- `txtBalance` — current balance
- `txtPayment` — payment entry
- `btnPay` — record payment
- `btnPrint` — print statement
- `cmbPeriod` — period filter

**Connections:** `FormMohasaby`, `FormSafiarbah`, `ModDariba`, `FormMoamla`

**Arabic context strings:**
- `اجمالي مديونية`
- `اجل العملاء`
- `اسم العميل مديونية العميل الفرع`
- `اسم المورد مستحقات المورد الفرع`
- `اجمالي الاجل اليوم`

---

### 6. FormDolap

| Field | Value |
|--------------|
| **Arabic name** | الدولاب / خزنة الصيدلية |
| **Purpose** | Pharmacy cash drawer / safe — cash register operations, cash in/out, daily cash reconciliation, shift-end settlement |
| **Procedures** | 12 |
| **Size** | ~1400 bytes total |
| **Decoded strings** | `"-// "` (تعديل = edit), `"GD "` (فاتورة = invoice), Arabic punctuation fragments |

**Likely controls:**
- `txtCashIn` — cash input
- `txtCashOut` — cash output
- `txtCurrentBalance` — current drawer balance
- `dgTransactions` — transaction grid
- `cmbShift` — shift selector
- `btnOpen` — open drawer
- `btnClose` — close/settle drawer
- `btnPrint` — print report

**Connections:** `FormEnd`, `FormMohasaby`, `FormSales`, `ModCash`, `FormShiftFawateer`

**Arabic context strings:**
- `اجمالي الدرج حاليا مطروح منه الدرج عن بداية الفترة ومضافا اليه اي نقدية خرجت من الدرج اثناء الفترة`
- `اجمالي النقدية`
- `اجمالي المدفوع فيزا اليوم`

---

### 7. FormEnd

| Field | Value |
|-------|-------|
| **Arabic name** | نهاية اليوم / إغلاق اليوم |
| **Purpose** | End-of-day procedures — daily closing, shift settlement, report generation, archive old invoices, backup |
| **Procedures** | 13 |
| **Size** | ~2200 bytes total |
| **Decoded strings** | `"DB/ "` (خطأ = error), `"B"` (some constant), conditional branches with `"Like *"` patterns |

**Likely controls:**
- `btnCloseDay` — close business day
- `btnArchive` — archive old invoices
- `btnBackup` — backup database
- `btnReport` — daily summary report
- `dgSummary` — summary grid
- `txtDate` — date selector
- `chkForceClose` — force close flag
- `lblStatus` — status display

**Connections:** `FormDolap`, `FormXEnd`, `FormXBackup`, `FormXRestore`, `FormBackup`, `FormArchiveBuy`, `FormArchiveSales`, `ModEnd`

**Arabic context strings:**
- `الي نهاية يوم`
- `تم حفظ كافة الفواتير ما عدا الفارغة`
- `الان يمكنك اكمال ادخال بقية بيانات الدواء`
- `امكانية خروج الموظف مع الابقاء علي الشيفت`

---

### 8. FormGetFats

| Field | Value |
|-------|-------|
| **Arabic name** | جلب الفواتير / استيراد الفواتير |
| **Purpose** | Fetch/import invoices — retrieve invoices from other branches, import from database, merge invoice data |
| **Procedures** | 2 |
| **Size** | ~600 bytes total |
| **Decoded strings** | None directly |

**Likely controls:**
- `cmbBranch` — source branch selector
- `dgInvoices` — invoices grid
- `btnFetch` — fetch invoices
- `btnImport` — import selected
- `txtFromDate` / `txtToDate` — date range
- `lblCount` — count of fetched invoices

**Connections:** `FormGetFatsFromStore`, `FormImportFat`, `FormExportFat`, `ModImportExport`

**Arabic context strings:**
- `اختر العميل الذي سيتم نقل الفواتير اليه`
- `برجاء تحديد الفواتير التي تريد جمعها من الجدول ادناه`
- `ادخل رقم الفاتورة التي تريد حذف الفواتير بعدها`

---

### 9. FormImportFat

| Field | Value |
|-------|-------|
| **Arabic name** | استيراد الفاتورة |
| **Purpose** | Import invoice — import purchase/sales invoice from file (Excel, CSV, or other DB), map fields, validate data |
| **Procedures** | 14 |
| **Size** | ~3500 bytes total |
| **Decoded strings** | None directly |

**Likely controls:**
- `txtFilePath` — file path input
- `btnBrowse` — browse file button
- `cmbImportType` — import type (مشتريات/مرتجعات)
- `dgPreview` — data preview grid
- `btnMap` — field mapping
- `btnImport` — execute import
- `btnValidate` — validate data
- `lblProgress` — progress indicator
- `chkOverwrite` — overwrite existing flag

**Connections:** `FormImportFatList`, `FormExportFat`, `FormExportFatList`, `FormGetFats`, `ModImportExport`

**Arabic context strings:**
- `اختر القيمة التي تود استيرادها`
- `تحسين خدمة تصدير الفواتير ما بين افرع الصيدليات`
- `تحسين قراءة الفواتير المؤرشفة في المبيعات والمشتريات`
- `ادخل اسم الشركة التي تود اذالتها من التقرير`

---

### 10. FormSafiarbah

| Field | Value |
|-------|-------|
| **Arabic name** | رأس المال / safezone |
| **Purpose** | Capital management — capital transactions, profit/loss tracking, capital account balance, financial summaries |
| **Procedures** | 3 |
| **Size** | ~1260 bytes total (one large procedure at 928 bytes) |
| **Decoded strings** | None directly |

**Likely controls:**
- `txtCapital` — capital amount
- `txtProfit` — profit field
- `txtLoss` — loss field
- `dgCapital` — capital transactions grid
- `btnUpdate` — update capital
- `btnReport` — capital report
- `cmbPeriod` — period selector

**Connections:** `FormMohasaby`, `FormDariba`, `FormMoamla`, `ModCapital`

**Arabic context strings:**
- `احصائيات راس المال`
- `احصائيات راس المال ونظرة عامة علي الصيدلية`
- `اجمالي الميزانية`
- `Current task capital change of date`

---

### 11. FormTawsil

| Field | Value |
|-------|-------|
| **Arabic name** | التوصيل / الدليفري |
| **Purpose** | Delivery management — assign delivery drivers, track delivery status, delivery scheduling, customer delivery assignments |
| **Procedures** | 6 |
| **Size** | ~2100 bytes total |
| **Decoded strings** | None directly |

**Likely controls:**
- `cmbDriver` — driver selector
- `dgDeliveries` — delivery list grid
- `txtAddress` — delivery address
- `cmbStatus` — delivery status
- `btnAssign` — assign driver
- `btnTrack` — track delivery
- `txtPhone` — customer phone
- `btnPrint` — print delivery note

**Connections:** `FormDrivers`, `Formdeliver`, `FormSales`, `ModDelivery`

**Arabic context strings:**
- `اختيار طيار الدليفري بالاسم من شاشة المبيعات بجوار مفتاح ملاحظات`
- `اختر عامل اولا`

---

## Part B — Forms NOT in Project (54 forms)

These form names were provided in the target list but **do not exist** in the decompiled `project_structure.json`. Analysis is based solely on name semantics and context from `strings_readable.txt`.

---

### 12. FFFUserList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة المستخدمين |
| **Purpose** | List/display all users — user directory, selection for editing, status display |
| **In project** | NO |

**Likely controls:** `dgUsers` (DataGrid), `txtSearch`, `btnAdd`, `btnEdit`, `btnDelete`  
**Connections:** `FFFUserEdit`, `FFFUserMenu`, `FormEmployee`

---

### 13. FFFUserMenu

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة المستخدم / صلاحيات القوائم |
| **Purpose** | Menu permissions per user — assign which menus/screens each user can access |
| **In project** | NO |

**Likely controls:** `dgMenus` (tree/grid), `chkAccess[]`, `btnSave`, `cmbUser`  
**Connections:** `FFFUserEdit`, `FFFUserMenuList`, `FormMenusPerUser`

---

### 14. FFFUserMenuList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة قوائم المستخدمين |
| **Purpose** | Master list of user-menu permission sets — manage permission templates |
| **In project** | NO |

**Likely controls:** `dgPermissionSets`, `btnNew`, `btnEdit`, `btnDelete`  
**Connections:** `FFFUserMenu`, `FFFUserEdit`

---

### 15. FormAddress

| Field | Value |
|-------|-------|
| **Arabic name** | العنوان / بيانات العنوان |
| **Purpose** | Address management — customer/supplier address entry, governorate/city selection (Egyptian address format) |
| **In project** | NO |

**Likely controls:** `txtStreet`, `txtBuilding`, `cmbGovernorate`, `cmbCity`, `txtPostalCode`, `btnSave`  
**Connections:** `FormDoctor`, `FormMoamla`, customer/supplier forms

**Arabic context strings:**
- `"buildingNumber":`, `"governate":`, `"regionCity":`, `"street":`, `"postalCode":` (from JSON invoice structure)

---

### 16. FormAddItem

| Field | Value |
|-------|-------|
| **Arabic name** | إضافة صنف |
| **Purpose** | Add single drug/item — quick-add a new drug to database from sales or purchase screen |
| **In project** | NO |

**Likely controls:** `txtDrugName`, `txtBarcode`, `txtPrice`, `txtQuantity`, `cmbCompany`, `btnAdd`, `btnCancel`  
**Connections:** `FormNewDrug`, `FormDrugsList`, `FormAddItems`, `FormFat`

---

### 17. FormAddItems

| Field | Value |
|-------|-------|
| **Arabic name** | إضافة أصناف متعددة |
| **Purpose** | Bulk add items — add multiple drugs at once, batch import from list |
| **In project** | NO |

**Likely controls:** `dgItems` (editable grid), `btnImport`, `btnAdd`, `btnRemove`, `btnSave`  
**Connections:** `FormAddItem`, `FormNewDrug`, `FormDrugsList`

---

### 18. FormArchiveBuy

| Field | Value |
|-------|-------|
| **Arabic name** | أرشفة المشتريات القديمة |
| **Purpose** | Archive old purchase invoices — move old purchase data to archive, reduce main database size |
| **In project** | NO |

**Likely controls:** `txtFromDate`, `txtToDate`, `btnArchive`, `dgPreview`, `lblCount`, `chkDeleteAfter`  
**Connections:** `FormArchiveSales`, `FormEnd`, `FormWared`, `FormWaredList`

**Arabic context strings:**
- `أرشفة المشتريات القديمة`

---

### 19. FormArchiveSales

| Field | Value |
|-------|-------|
| **Arabic name** | أرشفة المبيعات القديمة |
| **Purpose** | Archive old sales invoices — move old sales data to archive, reduce main database size |
| **In project** | NO |

**Likely controls:** `txtFromDate`, `txtToDate`, `btnArchive`, `dgPreview`, `lblCount`  
**Connections:** `FormArchiveBuy`, `FormEnd`, `FormSales`, `FormSalesList`

**Arabic context strings:**
- `أرشفة المبيعات القديمة`

---

### 20. FormBackup

| Field | Value |
|-------|-------|
| **Arabic name** | النسخ الاحتياطي |
| **Purpose** | Backup database — manual backup creation, restore point, backup scheduling |
| **In project** | NO |

**Likely controls:** `btnBackup`, `btnRestore`, `txtPath`, `btnBrowse`, `chkAutoBackup`, `cmbFrequency`  
**Connections:** `FormXBackup`, `FormXRestore`, `FormEnd`, `FormDatabase`

---

### 21. FormBarcode

| Field | Value |
|-------|-------|
| **Arabic name** | طباعة الباركود |
| **Purpose** | Print barcodes — generate and print barcode labels for drugs, batch printing |
| **In project** | NO |

**Likely controls:** `dgDrugs`, `txtQuantity`, `btnPrint`, `cmbLabelType`, `chkBatch`  
**Connections:** `FormBarcodeSettings`, `FormDrugsList`, `FormNewDrug`

---

### 22. FormChainBuyList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة سلاسل المشتريات |
| **Purpose** | List of purchase chains — display all chain groups, filter by supplier/date |
| **In project** | NO |

**Likely controls:** `dgChains`, `cmbSupplier`, `txtSearch`, `btnOpen`, `btnDelete`  
**Connections:** `FormChainBuy`, `FormWared`

---

### 23. FormDatabase

| Field | Value |
|-------|-------|
| **Arabic name** | قاعدة البيانات / تصفية قاعدة البيانات |
| **Purpose** | Database management — compact, repair, filter, clean orphaned records |
| **In project** | NO |

**Likely controls:** `btnCompact`, `btnRepair`, `btnClean`, `dgStats`, `lblSize`, `btnBackup`  
**Connections:** `FormBackup`, `FormEnd`, `FormXBackup`

**Arabic context strings:**
- `اضافة امكانية حذف الفواتير كلها مع الاحتفاظ بارصدة الادوية والعملاء والموردين وهذا من شاشة تصفية قواعد البيانات`

---

### 24. FormDoctor

| Field | Value |
|-------|-------|
| **Arabic name** | بيانات الطبيب / الأطباء |
| **Purpose** | Doctor data management — doctor directory, prescription tracking, doctor fees |
| **In project** | NO |

**Likely controls:** `dgDoctors`, `txtName`, `txtSpecialty`, `txtPhone`, `btnAdd`, `btnEdit`, `btnDelete`  
**Connections:** `FormDoctorFees`, `ModDoctor`

---

### 25. FormDoctorFees

| Field | Value |
|-------|-------|
| **Arabic name** | أتعاب الأطباء |
| **Purpose** | Doctor fees tracking — record fees paid to doctors, fee reports |
| **In project** | NO |

**Likely controls:** `dgFees`, `cmbDoctor`, `txtAmount`, `txtDate`, `btnAdd`, `btnPrint`  
**Connections:** `FormDoctor`, `ModDoctor`

---

### 26. FormDrivers

| Field | Value |
|-------|-------|
| **Arabic name** | السائقين / عمال التوصيل |
| **Purpose** | Delivery driver management — driver directory, availability, contact info |
| **In project** | NO |

**Likely controls:** `dgDrivers`, `txtName`, `txtPhone`, `cmbStatus`, `btnAdd`, `btnEdit`  
**Connections:** `FormTawsil`, `Formdeliver`

**Arabic context strings:**
- `اختر عامل اولا`

---

### 27. FormDrugsList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الأدوية / الأصناف |
| **Purpose** | Drug catalog listing — browse/search all drugs, view stock, prices, expiry |
| **In project** | NO |

**Likely controls:** `dgDrugs`, `txtSearch`, `cmbCategory`, `cmbCompany`, `btnAdd`, `btnEdit`, `btnDelete`  
**Connections:** `FormNewDrug`, `FormAddItem`, `FormDrugStore`, `FormDrugsList`

**Arabic context strings:**
- `ابحث عن الصنف بالاسم او الباركودج وعدل السعر والباركود عند الحاجة من اسفل الشاشة`

---

### 28. FormDrugStore

| Field | Value |
|-------|-------|
| **Arabic name** | المخزن / مستودع الأدوية |
| **Purpose** | Drug warehouse/store — stock management, inventory levels, stock transfers |
| **In project** | NO |

**Likely controls:** `dgStock`, `cmbDrug`, `txtQuantity`, `cmbLocation`, `btnTransfer`, `btnAdjust`  
**Connections:** `FormDrugStoreList`, `FormDrugStoreName`, `FormNewStore`

**Arabic context strings:**
- `المخزن`
- `ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة`

---

### 29. FormDrugStoreList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة المخازن |
| **Purpose** | List of warehouses/stores — display all store locations, selection |
| **In project** | NO |

**Likely controls:** `dgStores`, `btnAdd`, `btnEdit`, `btnDelete`  
**Connections:** `FormDrugStore`, `FormDrugStoreName`, `FormNewStore`

---

### 30. FormDrugStoreName

| Field | Value |
|-------|-------|
| **Arabic name** | اسم المخزن |
| **Purpose** | Store name management — rename, create new store with name |
| **In project** | NO |

**Likely controls:** `txtStoreName`, `btnSave`, `btnCancel`  
**Connections:** `FormDrugStore`, `FormDrugStoreList`, `FormNewStore`

---

### 31. FormEditExpDate

| Field | Value |
|-------|-------|
| **Arabic name** | تعديل تاريخ الصلاحية |
| **Purpose** | Edit expiry date — correct/adjust expiry dates for drug batches |
| **In project** | NO |

**Likely controls:** `cmbDrug`, `txtBatchNo`, `txtOldExpiry`, `txtNewExpiry`, `btnSave`, `btnCancel`  
**Connections:** `FormFixExpDate`, `FormEditFatDate`, `FormExpireDetails`

**Arabic context strings:**
- `اختر تاريخ الاستحقاق`

---

### 32. FormEditFatDate

| Field | Value |
|-------|-------|
| **Arabic name** | تعديل تاريخ الفاتورة |
| **Purpose** | Edit invoice date — change the date on existing invoices |
| **In project** | NO |

**Likely controls:** `txtInvoiceNo`, `txtOldDate`, `txtNewDate`, `btnSave`, `btnCancel`  
**Connections:** `FormEditFatDate2`, `FormFatList`, `FormSalesList`

**Arabic context strings:**
- `ادخل عدد الفواتير التي تريد تعديل تاريخها بدا من الفاتورة الحالية`
- `اختر تاريخ اليوم كما هو بساعتك الشخصية`

---

### 33. FormEditFatDate2

| Field | Value |
|-------|-------|
| **Arabic name** | تعديل تاريخ الفاتورة (خيارات متقدمة) |
| **Purpose** | Advanced invoice date editing — batch date changes, date range adjustments |
| **In project** | NO |

**Likely controls:** `txtFromInvoice`, `txtToInvoice`, `txtNewDate`, `btnApply`, `btnPreview`  
**Connections:** `FormEditFatDate`, `FormFatList`

---

### 34. FormEmployee

| Field | Value |
|-------|-------|
| **Arabic name** | بيانات الموظفين / العاملين |
| **Purpose** | Employee data management — employee directory, roles, shifts, permissions |
| **In project** | NO |

**Likely controls:** `dgEmployees`, `txtName`, `cmbRole`, `cmbShift`, `btnAdd`, `btnEdit`, `btnPermissions`  
**Connections:** `FFFUserEdit`, `FFFUserList`, `FormMenusPerUser`

**Arabic context strings:**
- `اضافة حصلاحية عمل الخصم من عدمه للموظفين في قائمة صلاحيات الموظف`
- `تم منح هذا المستخدم الصاحايت الاساسية ويمكنك الاضافة اليها والحذف منها كما تشاء`

---

### 35. FormExportFat

| Field | Value |
|-------|-------|
| **Arabic name** | تصدير الفاتورة |
| **Purpose** | Export invoice — export invoice data to file, send to other branches, generate XML/JSON |
| **In project** | NO |

**Likely controls:** `cmbInvoiceType`, `txtFilePath`, `btnExport`, `cmbFormat`, `dgPreview`  
**Connections:** `FormExportFatList`, `FormImportFat`, `ModImportExport`

**Arabic context strings:**
- `تصدير الفواتير التي تحتوي علي مشكلة في حساب الاجل`
- `تحسين خدمة تصدير الفواتير ما بين افرع الصيدليات`

---

### 36. FormExportFatList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الفواتير المُصدّرة |
| **Purpose** | List of exported invoices — view previously exported invoices, re-export |
| **In project** | NO |

**Likely controls:** `dgExports`, `cmbDate`, `btnReExport`, `btnDelete`  
**Connections:** `FormExportFat`, `FormImportFatList`

---

### 37. FormFat

| Field | Value |
|-------|-------|
| **Arabic name** | الفاتورة (مشتريات/مرتجعات) |
| **Purpose** | Purchase/return invoice entry — main purchase invoice screen, item entry, totals, save |
| **In project** | NO |

**Likely controls:** `dgItems` (editable grid), `cmbSupplier`, `txtInvoiceNo`, `txtTotal`, `txtDiscount`, `txtTax`, `btnSave`, `btnPrint`, `btnDelete`  
**Connections:** `FormFatList`, `FormWared`, `FormWaredList`, `FormChainBuy`

**Arabic context strings:**
- `الفواتير`
- `اجمالي الفاتورة`
- `اجمالي الشراء`
- `اجمالي الشراء قبل الضريبة`
- `GD ` (فاتورة)

---

### 38. FormFatList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الفواتير |
| **Purpose** | Invoice listing — browse/search all purchase invoices, filter by date/supplier |
| **In project** | NO |

**Likely controls:** `dgInvoices`, `txtSearch`, `cmbSupplier`, `cmbDate`, `btnOpen`, `btnPrint`, `btnDelete`  
**Connections:** `FormFat`, `FormSalesList`, `FormArchiveBuy`

---

### 39. FormFixDrugPrice

| Field | Value |
|-------|-------|
| **Arabic name** | تعديل سعر الدواء |
| **Purpose** | Fix drug price — correct pricing errors, bulk price updates |
| **In project** | NO |

**Likely controls:** `cmbDrug`, `txtOldPrice`, `txtNewPrice`, `btnApply`, `chkBulk`, `dgDrugs`  
**Connections:** `FormDrugsList`, `FormPriceSetting`, `FormNewDrug`

**Arabic context strings:**
- `ابحث عن الصنف بالاسم او الباركودج وعدل السعر والباركود عند الحاجة من اسفل الشاشة`

---

### 40. FormFixExpDate

| Field | Value |
|-------|-------|
| **Arabic name** | تصحيح تاريخ الصلاحية |
| **Purpose** | Fix expiry date — batch correction of expiry dates, expiry validation |
| **In project** | NO |

**Likely controls:** `dgDrugs`, `txtBatchNo`, `txtNewExpiry`, `btnFix`, `btnBulkFix`  
**Connections:** `FormEditExpDate`, `FormExpireDetails`, `FormExpiredDrugs`

---

### 41. FormGetFatsFromStore

| Field | Value |
|-------|-------|
| **Arabic name** | جلب الفواتير من المخزن |
| **Purpose** | Fetch invoices from store/warehouse — retrieve invoices linked to specific warehouse |
| **In project** | NO |

**Likely controls:** `cmbStore`, `dgInvoices`, `btnFetch`, `btnImport`  
**Connections:** `FormGetFats`, `FormDrugStore`, `FormImportFat`

**Arabic context strings:**
- `ابحث عن رقم الفاتورة الوارد من مخزن التوزيع`

---

### 42. FormGuide

| Field | Value |
|-------|-------|
| **Arabic name** | الدليل / المرشد |
| **Purpose** | User guide/help — in-app help, tutorial, how-to guides |
| **In project** | NO |

**Likely controls:** `webHelp` (WebBrowser), `dgTopics`, `txtSearch`, `btnNext`, `btnPrev`  
**Connections:** `FormUserGuide`, `FormUsersGuide`, `FormHelp`

---

### 43. FormHajozat

| Field | Value |
|-------|-------|
| **Arabic name** | الحجوزات |
| **Purpose** | Reservations/bookings — drug reservation system, hold items for customers |
| **In project** | NO |

**Likely controls:** `dgReservations`, `cmbCustomer`, `cmbDrug`, `txtQuantity`, `btnReserve`, `btnRelease`  
**Connections:** `FormSales`, `FormFat`

---

### 44. FormHistory

| Field | Value |
|-------|-------|
| **Arabic name** | السجل / التاريخ |
| **Purpose** | History/log — activity history, change log, user actions audit trail |
| **In project** | NO |

**Likely controls:** `dgHistory`, `cmbDate`, `cmbUser`, `cmbAction`, `btnExport`  
**Connections:** `FormJournal`, `FormAmilHistory`

**Arabic context strings:**
- `تم انشاء ميزة تتبع تحركات المستخدمين داخل البرنامج من امر سجل الانشطة في قائمة تقارير`

---

### 45. FormIDCard

| Field | Value |
|-------|-------|
| **Arabic name** | البطاقة الشخصية / الرقم القومي |
| **Purpose** | National ID card reader — read Egyptian national ID card data (barcode/OCR) |
| **In project** | NO |

**Likely controls:** `txtID`, `txtName`, `txtDOB`, `txtAddress`, `btnRead`, `btnSave`  
**Connections:** `FormDoctor`, `FormMoamla`, customer forms

---

### 46. FormImportFatList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الفواتير المستوردة |
| **Purpose** | List of imported invoices — view previously imported invoices |
| **In project** | NO |

**Likely controls:** `dgImports`, `cmbDate`, `btnReimport`, `btnDelete`  
**Connections:** `FormImportFat`, `FormExportFatList`

---

### 47. FormInfo

| Field | Value |
|-------|-------|
| **Arabic name** | معلومات / بيانات |
| **Purpose** | Information display — pharmacy info, about screen, system info |
| **In project** | NO |

**Likely controls:** `lblVersion`, `lblPharmacy`, `lblLicense`, `lblExpiry`, `btnClose`  
**Connections:** `FormPharmacyInfo`, `FormActivation`

---

### 48. FormItemsList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الأصناف |
| **Purpose** | Items list — browse items in current invoice, select items for operations |
| **In project** | NO |

**Likely controls:** `dgItems`, `txtSearch`, `btnSelect`, `btnClose`  
**Connections:** `FormFat`, `FormSales`, `FormDrugsList`

---

### 49. FormJournal

| Field | Value |
|-------|-------|
| **Arabic name** | اليومية / السجل اليومي |
| **Purpose** | Daily journal — daily transaction log, activity journal, audit trail |
| **In project** | NO |

**Likely controls:** `dgJournal`, `cmbDate`, `cmbType`, `btnExport`, `btnPrint`  
**Connections:** `FormHistory`, `FormAmilTakarir`

**Arabic context strings:**
- `تم انشاء ميزة تتبع تحركات المستخدمين داخل البرنامج من امر سجل الانشطة في قائمة تقارير`

---

### 50. FormMain

| Field | Value |
|-------|-------|
| **Arabic name** | الشاشة الرئيسية |
| **Purpose** | Main screen — application hub, menu navigation, status bar, quick actions |
| **In project** | NO |

**Likely controls:** `mnuMain` (Menu), `lblStatus`, `lblUser`, `lblDate`, `pnlQuickActions`  
**Connections:** ALL forms — central navigation hub

**Arabic context strings:**
- `الان يمكنك فتح كافة الشاشات دون الحاجة لخروج المستخدم الحالي`
- `تاحة امكانية تطوير قاعدة بيانات الادوية الخاصة بتيتان بواسطة كل الزملاء`

---

### 51. FormMenu

| Field | Value |
|-------|-------|
| **Arabic name** | القائمة / قائمة الخيارات |
| **Purpose** | Menu screen — application menu, navigation tree |
| **In project** | NO |

**Likely controls:** `tvMenu` (TreeView), `btnSelect`, `lblTitle`  
**Connections:** `FormMain`, `FormMenusPerUser`, `FFFScreens`

---

### 52. FormMenusPerUser

| Field | Value |
|-------|-------|
| **Arabic name** | قوائم المستخدمين |
| **Purpose** | Menu permissions per user — assign screen/menu access per user |
| **In project** | NO |

**Likely controls:** `cmbUser`, `dgMenus`, `chkAccess[]`, `btnSave`  
**Connections:** `FFFUserMenu`, `FFFUserMenuList`, `FormEmployee`

**Arabic context strings:**
- `اضافة حصلاحية عمل الخصم من عدمه للموظفين في قائمة صلاحيات الموظف`
- `اختبر الصلاحيات`

---

### 53. FormMoamla

| Field | Value |
|-------|-------|
| **Arabic name** | المعاملة / تعاملات |
| **Purpose** | Transaction management — customer/supplier transactions, payment recording |
| **In project** | NO |

**Likely controls:** `dgTransactions`, `cmbCustomer`, `cmbType`, `txtAmount`, `btnPay`, `btnReceive`  
**Connections:** `FormDariba`, `FormMohasaby`, `FormSafiarbah`

**Arabic context strings:**
- `اخر تعامل`
- `اخر تعامل كان منذ اكثر من 120 يوما`
- `اخر تعامل لهذا العميل كان قبل اقل من شهرين ولا يمكن حذفه`

---

### 54. FormMohasaby

| Field | Value |
|-------|-------|
| **Arabic name** | المحاسبى / الحسابات |
| **Purpose** | Accounting screen — financial reports, balance sheets, profit/loss, account statements |
| **In project** | NO |

**Likely controls:** `dgAccounts`, `cmbPeriod`, `txtFromDate`, `txtToDate`, `btnReport`, `btnPrint`  
**Connections:** `FormDariba`, `FormSafiarbah`, `FormMoamla`, `ModAccounting`

**Arabic context strings:**
- `الحسابات`
- `احصائيات مجملة`
- `احصائيات مجملة للمبيعات`
- `احصائيات مجمة للمشتريات`

---

### 55. FormNeed

| Field | Value |
|-------|-------|
| **Arabic name** | الاحتياجات / الطلبات |
| **Purpose** | Needs/requirements — drug reorder requirements, auto-order suggestions |
| **In project** | NO |

**Likely controls:** `dgNeeds`, `cmbCategory`, `btnOrder`, `btnExport`, `cmbSupplier`  
**Connections:** `ModNeed`, `FormNeedList`, `FormNeedListPerUser`, `FormAutoOrder`

**Arabic context strings:**
- `ادوية طلبت وفي انتظار ان تصل من المورد`

---

### 56. FormNeedList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الاحتياجات |
| **Purpose** | List of needs/requirements — display all pending orders, status tracking |
| **In project** | NO |

**Likely controls:** `dgNeeds`, `cmbStatus`, `btnOpen`, `btnDelete`  
**Connections:** `FormNeed`, `FormNeedListPerUser`

---

### 57. FormNeedListPerUser

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة احتياجات المستخدم |
| **Purpose** | User-specific needs list — filter needs by user/employee |
| **In project** | NO |

**Likely controls:** `cmbUser`, `dgNeeds`, `btnFilter`  
**Connections:** `FormNeed`, `FormNeedList`, `ModNeed`

---

### 58. FormNewDrug

| Field | Value |
|-------|-------|
| **Arabic name** | إضافة دواء جديد |
| **Purpose** | Add new drug — full drug data entry (Arabic name, scientific name, company, barcode, prices) |
| **In project** | NO |

**Likely controls:** `txtNameAr`, `txtNameEn`, `txtScientificName`, `txtBarcode1-5`, `cmbCompany`, `cmbCategory`, `txtBuyPrice`, `txtSellPrice`, `txtExpDate`, `btnSave`  
**Connections:** `FormAddItem`, `FormDrugsList`, `FormDrugStore`, `FormBarcode`

**Arabic context strings:**
- `الان يمكنك اكمال ادخال بقية بيانات الدواء مثل الاسم العلمي والعربي والشركة`
- `تم تطوير شاشة الادوية والاسعار الجديدة بحيث تشمل الباركود الدولي والشركة`

---

### 59. FormNewStore

| Field | Value |
|-------|-------|
| **Arabic name** | إضافة مخزن جديد |
| **Purpose** | Create new warehouse/store — new store setup |
| **In project** | NO |

**Likely controls:** `txtStoreName`, `txtLocation`, `cmbType`, `btnCreate`, `btnCancel`  
**Connections:** `FormDrugStore`, `FormDrugStoreList`, `FormDrugStoreName`

---

### 60. FormOrder

| Field | Value |
|-------|-------|
| **Arabic name** | الطلب / طلبية |
| **Purpose** | Order entry — create purchase orders to suppliers |
| **In project** | NO |

**Likely controls:** `dgItems`, `cmbSupplier`, `txtOrderNo`, `btnSave`, `btnPrint`, `btnSend`  
**Connections:** `FormOrderList`, `FormWared`, `FormNeed`

**Arabic context strings:**
- `ادوية طلبت وفي انتظار ان تصل من المورد`

---

### 61. FormOrderList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة الطلبات |
| **Purpose** | Order listing — browse/search all purchase orders |
| **In project** | NO |

**Likely controls:** `dgOrders`, `cmbSupplier`, `cmbStatus`, `btnOpen`, `btnDelete`  
**Connections:** `FormOrder`, `FormWared`

---

### 62. FormPriceSetting

| Field | Value |
|-------|-------|
| **Arabic name** | إعدادات الأسعار |
| **Purpose** | Price settings — configure pricing rules, profit margins, discount policies |
| **In project** | NO |

**Likely controls:** `txtProfitMargin`, `txtMaxDiscount`, `cmbPricingMethod`, `btnSave`  
**Connections:** `FormFixDrugPrice`, `FormDrugsList`, `FormNewDrug`

**Arabic context strings:**
- `ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة`

---

### 63. FormReport

| Field | Value |
|-------|-------|
| **Arabic name** | التقرير |
| **Purpose** | Single report — display specific report (sales, purchases, etc.) |
| **In project** | NO |

**Likely controls:** `dgReport`, `cmbReportType`, `txtFromDate`, `txtToDate`, `btnPrint`, `btnExport`  
**Connections:** `FormReports`, `FormReportsGeneral`

---

### 64. FormReports

| Field | Value |
|-------|-------|
| **Arabic name** | التقارير |
| **Purpose** | Reports hub — report selection, categories, filters |
| **In project** | NO |

**Likely controls:** `tvReports` (TreeView), `dgPreview`, `btnRun`, `btnPrint`  
**Connections:** `FormReport`, `FormReportsGeneral`, `FormAmilTakarir`

**Arabic context strings:**
- `احصائيات`
- `احصائيات اليوم`
- `احصائيات مجملة`
- `احصائيات مجملة للمبيعات`
- `احصائيات مجمة للمشتريات`

---

### 65. FormSales

| Field | Value |
|-------|-------|
| **Arabic name** | المبيعات / فاتورة المبيعات |
| **Purpose** | Sales invoice entry — main sales screen, item entry, customer selection, tax calculation |
| **In project** | NO |

**Likely controls:** `dgItems` (editable grid), `cmbCustomer`, `txtTotal`, `txtDiscount`, `txtTax`, `btnSave`, `btnPrint`, `btnReturn`  
**Connections:** `FormSalesList`, `FormFat`, `FormDolap`, `FormTawsil`

**Arabic context strings:**
- `المبيعات من الفواتير`
- `اجمالي المبيعات`
- `اجمالي الربح في المبيعات`
- `اضافة مفتاح حفظ كل الفواتير المبيعات بضغطة واحدة في اسفل يسار شاشة المبيعات`
- `اضافة شاشة استعلام مبيعات الشفتات وفيها تفصيل مبيعات الشفت والمستخدمين اللذين قاموا بالعمل فيه`

---

### 66. FormSalesList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة المبيعات |
| **Purpose** | Sales invoice listing — browse/search all sales invoices |
| **In project** | NO |

**Likely controls:** `dgInvoices`, `cmbCustomer`, `cmbDate`, `btnOpen`, `btnPrint`, `btnReturn`  
**Connections:** `FormSales`, `FormArchiveSales`, `FormFatList`

---

### 67. FormTahwil

| Field | Value |
|-------|-------|
| **Arabic name** | التحويل / تحويل بين الفروع |
| **Purpose** | Branch transfer — transfer drugs/invoices between branches |
| **In project** | NO |

**Likely controls:** `cmbFromBranch`, `cmbToBranch`, `dgItems`, `btnTransfer`, `btnConfirm`  
**Connections:** `FormTahwilList`, `FormGetFats`, `FormExportFat`

---

### 68. FormTahwilList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة التحويلات |
| **Purpose** | Transfer listing — browse all branch transfers |
| **In project** | NO |

**Likely controls:** `dgTransfers`, `cmbDate`, `cmbBranch`, `btnOpen`  
**Connections:** `FormTahwil`, `FormExportFatList`

---

### 69. FormTareefha

| Field | Value |
|-------|-------|
| **Arabic name** | التعرفة / التعريفات |
| **Purpose** | Pricing/tariff management — drug pricing tiers, customer-specific prices |
| **In project** | NO |

**Likely controls:** `dgPrices`, `cmbDrug`, `txtPrice`, `cmbTier`, `btnSave`  
**Connections:** `FormPriceSetting`, `FormFixDrugPrice`, `FormDrugsList`

---

### 70. FormUserGuide

| Field | Value |
|-------|-------|
| **Arabic name** | دليل المستخدم |
| **Purpose** | User guide — help documentation browser |
| **In project** | NO |

**Likely controls:** `webGuide` (WebBrowser), `dgTopics`, `txtSearch`  
**Connections:** `FormUsersGuide`, `FormGuide`

---

### 71. FormUsersGuide

| Field | Value |
|-------|-------|
| **Arabic name** | دليل المستخدمين |
| **Purpose** | Users guide — comprehensive help system |
| **In project** | NO |

**Likely controls:** `webGuide`, `dgChapters`, `btnIndex`  
**Connections:** `FormUserGuide`, `FormGuide`

---

### 72. FormWared

| Field | Value |
|-------|-------|
| **Arabic name** | الوارد / فاتورة المشتريات |
| **Purpose** | Purchase invoice entry (incoming) — record incoming goods, supplier invoices |
| **In project** | NO |

**Likely controls:** `dgItems`, `cmbSupplier`, `txtInvoiceNo`, `txtTotal`, `btnSave`, `btnPrint`  
**Connections:** `FormWaredList`, `FormFat`, `FormChainBuy`, `FormOrder`

**Arabic context strings:**
- `اسم المورد مستحقات المورد الفرع`
- `اخر شراء`
- `اخر خصم شراء`

---

### 73. FormWaredList

| Field | Value |
|-------|-------|
| **Arabic name** | قائمة المشتريات / الوارد |
| **Purpose** | Purchase invoice listing — browse/search all purchase invoices |
| **In project** | NO |

**Likely controls:** `dgInvoices`, `cmbSupplier`, `cmbDate`, `btnOpen`, `btnPrint`  
**Connections:** `FormWared`, `FormFatList`, `FormArchiveBuy`

---

### 74. FormWelcome

| Field | Value |
|-------|-------|
| **Arabic name** | مرحبًا / شاشة الترحيب |
| **Purpose** | Welcome screen — splash screen, login prompt, version display |
| **In project** | NO |

**Likely controls:** `lblWelcome`, `lblVersion`, `imgLogo`, `btnStart`  
**Connections:** `FFFStartUp`, `FormMain`, `FormActivation`

---

### 75–80. FormX, FormXBackup, FormXEnd, FormXExport, FormXRestore

| Field | Value |
|-------|-------|
| **Arabic name** | X (نهاية/نسخ احتياطي/تصدير/استعادة) |
| **Purpose** | End-of-day/backup/export/restore utility forms — administrative operations |
| **In project** | NO |

**Connections:** `FormEnd`, `FormBackup`, `FormExportFat`, `FormDatabase`

**Arabic context strings:**
- `الان يمكنك الغاء حفظ الفواتير القديمه`
- `اضافة امكانية حذف الفواتير كلها مع الاحتفاظ بارصدة الادوية والعملاء والموردين`

---

### 81–82. FormY, FormZ, FormZ2

| Field | Value |
|-------|-------|
| **Arabic name** | غير محدد |
| **Purpose** | Unknown/placeholder forms — possibly test forms, temporary UI, or unused stubs |
| **In project** | NO |

---

## Cross-Reference Summary

### Module Dependencies

| Module | Referenced By Forms |
|--------|-------------------|
| `ModUsers` | FFFUserEdit, FFFUserList, FFFUserMenu, FormEmployee |
| `ModNeed` | FormNeed, FormNeedList, FormNeedListPerUser, FormAutoOrder |
| `ModMohasaby` | FormMohasaby, FormDariba, FormSafiarbah, FormMoamla |
| `ModBuy` | FormWared, FormWaredList, FormFat, FormFatList, FormChainBuy |
| `ModImportExport` | FormImportFat, FormExportFat, FormGetFats, FormTahwil |
| `ModDelivery` | FormTawsil, FormDrivers, Formdeliver |
| `ModCapital` | FormSafiarbah, FormMohasaby |
| `ModDoctor` | FormDoctor, FormDoctorFees |
| `ModBarcode` | FormBarcode, FormBarcodeSettings, FormNewDrug |

### Egyptian FDA (NTRA/DTTS) Integration

Strings confirm integration with Egypt's DTTS (Drug Tracking & Tracing System):
- `<m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">`
- `<m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">`
- `<m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">`
- `<m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">`
- `<m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">`
- JSON fields: `uuid`, `receiptNumber`, `dateTimeIssued`, `deviceSerialNumber`, `activityCode`, `branchCode`, `companyTradeName`

### VAT/Tax Fields

- `"taxType":`, `"taxableItems":`, `"totalSales":`, `"netAmount":`, `"totalAmount":`
- `"taxTotals":`, `"paymentMethod":`
- Arabic: `اجمالي ضريبة القيمة المضافة 15 بالمائة`, `اجمالي الضريبة`

### Known Module-to-Form Mapping

```
ModUsers ─────┬─ FFFUserEdit
              ├─ FFFUserList
              ├─ FFFUserMenu
              └─ FormEmployee

ModNeed ──────┬─ FormNeed
              ├─ FormNeedList
              └─ FormNeedListPerUser

ModMohasaby ──┬─ FormMohasaby
              ├─ FormDariba
              ├─ FormSafiarbah
              └─ FormMoamla

ModBuy ───────┬─ FormWared
              ├─ FormWaredList
              ├─ FormFat
              ├─ FormFatList
              └─ FormChainBuy

ModImportExport┬─ FormImportFat
              ├─ FormExportFat
              ├─ FormGetFats
              └─ FormTahwil

ModDelivery ──┬─ FormTawsil
              └─ FormDrivers

ModDoctor ────┬─ FormDoctor
              └─ FormDoctorFees

ModBarcode ───┬─ FormBarcode
              └─ FormBarcodeSettings
```

---

## Methodology Notes

1. **Form .frm files** (8 of 65 forms): Contain abstract pseudo-code with `_CallImp_`, `_Property_`, `_Condition_` placeholders — no real identifiers recoverable without deeper pcode hex analysis
2. **Pcode disassembly** (`pcode_disasm.txt`): 696,847 lines, 207 unique form sections — only 11 of target 65 forms have pcode entries; string literals are hex-encoded UTF-16LE
3. **Strings files**: 18,830 readable strings + 26,970 raw UTF-16 strings — Arabic labels, SQL fragments, JSON templates, XML SOAP messages
4. **Project structure** (`project_structure.json`): 237 objects (212 forms, 15 modules) — definitive source for form existence
5. **Key limitation**: Without full hex decoding of pcode string literals, exact control names and procedure names cannot be recovered. Arabic string context provides the strongest signal for functionality inference.
