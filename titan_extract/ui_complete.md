# TITAN.W1 Pharmacy Management System - Complete UI Specification

## Project Overview

| Property | Value |
|----------|-------|
| Project | TITAN.W1 (Phye.exe) |
| Type | VB6 Pharmacy Management System |
| Forms | 237 |
| Objects | 336 |
| Procedures | 6,192 |
| String Constants | 26,970 |
| API Calls | 124 |

---

## Step 1: Form-by-Form Extraction

### MDI Form Parents (19)

| MDI Form | Procedures | Purpose |
|----------|-----------|---------|
| FFFOutPut | 278 | Main output/reporting MDI parent |
| FFFNew | 165 | New drug entry MDI parent |
| FFFInPut | 173 | Input/purchasing MDI parent |
| FormFirstStart | 7 | First startup wizard |
| FFFDS | 76 | Drug stock management MDI |
| FormBadil | 8 | Alternative medicines management |
| FormPrinterSettings | 31 | Printer configuration |
| FFFAZ | 11 | AZ management form |
| FormStockNow | 6 | Current stock view |
| FFFPharm | 2 | Pharmacy main form |
| FFFGenChoose | 11 | General selection dialog |
| FFFNewDrug | 19 | New drug entry |
| FormRempteTitan | 13 | Remote Titan connectivity |
| FormSendChanges | 3 | Send changes to other pharmacies |
| FFFSilsilaStock | 7 | Chain pharmacy stock |
| FFFDrugEye | 22 | Drug eye monitoring |
| FormPrinterSettingFary | 28 | Fary printer settings |
| FFFNewDrugServer | 28 | New drug server entry |
| FormDrugsCompare | 8 | Drugs comparison |

### Child Forms by Category

#### System & Startup (10 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFStartUp | 252 | بدء التشغيل | Main startup/login form - the most complex form in the system |
| FFFGard | 2 | الحارس | Guard/security monitoring |
| FFFHelpStart | 5 | بدء المساعدة | Help start page |
| FFFHELP | 6 | المساعدة | Help screen |
| FFFMY | 4 | MY | MY form |
| FFFIB | 8 | IB | IB form |
| FFFDL | 8 | DL | DL form |
| FFFDIR | 5 | الدليل | Directory form |
| FFFMSGLONG | 4 | رسالة طويلة | Long message display |
| FormWait | 0 | انتظار | Wait/loading screen |

#### Drug Management (32 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFNames | 65 | اسماء الادوية | Drug names management |
| FFFNewDrug | 19 | دواء جديد | New drug entry |
| FFFNewDrugServer | 28 | دواء جديد سيرفر | New drug server entry |
| FFFDrugrasidCorrect | 28 | تصحيح رصيد الدواء | Drug balance correction |
| FormDrugsDetails | 51 | تفاصيل الدواء | Drug details card (second most complex) |
| FormDrugFlow | 32 | تدفق الدواء | Drug flow/movement tracking |
| FormParCode | 14 | باركود | Barcode management |
| FormExpiredDrugs | 21 | ادوية منتهية الصلاحية | Expired drugs report |
| FormExpireCorrect | 11 | تصحيح تاريخ الانتهاء | Expiry date correction |
| FormUpdateDrugParcode | 2 | تحديث باركود الدواء | Update drug barcode |
| FormLastEdited | 10 | آخر تعديل | Last edited drugs |
| FormNameLike | 7 | بحث بالاسم | Name similarity search |
| FormExpireDetails | 4 | تفاصيل الصلاحية | Expiry details |
| FormDrugDrug | 22 | تفاعل الدواء بالدواء | Drug-Drug interaction checker |
| FormDrugPrice | 18 | سعر الدواء | Drug pricing |
| FormDrugRasidCorrectCalc | 3 | حاسبة تصحيح الرصيد | Drug balance correction calculator |
| FormDrugsLastDate | 7 | آخر تاريخ للدواء | Drugs last date tracking |
| FormDrugHistory | 5 | تاريخ الدواء | Drug history |
| FormDrugMonthly | 7 | تقرير شهري | Monthly drug report |
| FormLastDrugUsed | 9 | آخر ادوية مستخدمة | Last drugs used |
| FormSimilars | 5 | الادوية المتشابهة | Similar drugs |
| FormReapetedDrugMerge | 10 | دمج الادوية المكررة | Repeated drug merge |
| FormDrugsLists | 15 | قوائم الادوية | Drug lists |
| FFFDRUGRUN | 12 | تشغيل الدواء | Drug runner |
| FFFDrugNameMaker | 8 | صانع اسم الدواء | Drug name generator |
| FormDrugNameUnify | 12 | توحيد اسم الدواء | Drug name unification |
| FormDrugsdataTrue | 8 | صحة بيانات الدواء | Drug data validation |
| FormDrugsHelper | 13 | مساعد الادوية | Drug helper/assistant |
| FormMoreBarcodes | 8 | باركودات اضافية | Additional barcodes |
| FormDrugeeyeUpadteFrom | 16 | تحديث من عين الدواء | Drug eye update |
| FormAutoExpire | 12 | انتهاء تلقائي | Auto expiry management |
| FormReadMonthlyData | 13 | قراءة بيانات شهرية | Read monthly data |

#### Inventory & Stock (18 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFNeed | 62 | النواقص | Needs/shortages management |
| FFFWaredMonsaref | 36 | المستودع / المونسرف | Warehouse/Monsaref management |
| FormMoared | 20 | نقل بين الصيدليات | Transfer between pharmacies |
| FFFDS | 76 | ادارة المخزون | Drug stock management |
| FormStockNow | 6 | المخزون الحالي | Current stock view |
| FFFSilsilaStock | 7 | مخزون السلسلة | Chain pharmacy stock |
| FFFNeedAuto | 44 | نواقص تلقائية | Automatic needs calculation |
| FormMinimumControl | 23 | التحكم بالحد الادني | Minimum stock control |
| FormNeedsDetails | 9 | تفاصيل النواقص | Needs details |
| FormNeedEntryShow | 4 | عرض ادخال النواقص | Needs entry display |
| FormRawakid | 10 | الرواكد | Rawakid management |
| FFFINNquant | 75 | كمية الادخال | Input quantity management |
| FFFINNquantEG | 47 | كمية الادخال مصر | Input quantity Egypt |
| FFFOUTQuant | 20 | كمية الاخراج | Output quantity |
| FormChainBuy | 6 | شراء السلسلة | Chain buying |
| FormOrood1 | 7 | اورود | Stock items |
| FormDolap | 12 | الخزانة | Cabinet/inventory |
| FormNeedsAll | 50 | كل النواقص | All needs management |

#### Purchasing (3 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FormLiveBuyInfo | 8 | معلومات الشراء المباشر | Live purchase info |
| FFFInPut | 173 | المشتريات | Input/purchasing MDI parent |
| FormNedBirbish | 6 | حساب النواقص | Needs calculation |

#### Sales (2 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FormSellTime | 9 | وقت البيع | Sales timing |
| FFFOutputTakarir | 16 | تقارير الاخراج | Output reports |

#### Finance & Money (14 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFMony | 13 | المال | Money/financial transactions |
| FFFMRD | 11 | MRD | MRD (installment customers) |
| FormMRDAgel | 7 | مدفوعات MRD | MRD installment payments |
| FormBonus | 3 | المكافآت | Bonus calculations |
| FormDisList | 3 | قائمة الخصومات | Discount list |
| FormMrdAmlManual | 9 | ادخال يدوي MRD | MRD manual employee entry |
| FormMonyDetails | 7 | تفاصيل المال | Money details |
| FormCorrecyMony | 4 | تصحيح المال | Money correction |
| FormUsersMony | 24 | اموال المستخدمين | User money management |
| FormStoreDiscount | 23 | خصم المتجر | Store discount management |
| FormRasMal | 2 | راس المال | Capital balance |
| FormDariba | 5 | الضريبة | Dariba (tax report) |
| FormDiscCorrect | 4 | تصحيح الخصم | Discount correction |
| FormMizanCreate | 33 | انشاء ميزان عمومات | Trial balance creation |

#### Employees & Shifts (10 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFAML | 14 | العاملين | Employee management |
| FormAmilTakarir | 23 | تقارير العاملين | Employee reports |
| FormAmilShow | 9 | عرض الموظف | Employee display |
| FormAmilHistory | 3 | تاريخ الموظف | Employee history |
| FormAmilTamin | 16 | رواتب الموظفين | Employee salary |
| FormAmilTamin2 | 10 | رواتب v2 | Employee salary v2 |
| FormHodour | 16 | الحضور والانصراف | Attendance tracking |
| FormHodour19 | 35 | الحضور المتقدم | Attendance (advanced) |
| FormShiftFawateer | 9 | فواتير الوردية | Shift invoices |
| FormShiftInput | 9 | ادخال الوردية | Shift input |

#### Patients & Customers (5 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFTel | 14 | التلفون | Phone/telephone directory |
| FormMarid | 5 | المريض | Patient/customer disease records |
| FormMaridData | 15 | بيانات المريض | Patient data management |
| FormMaridFat | 4 | فواتير المريض | Patient invoices |
| FormCoData | 8 | بيانات الشركة | Company data |

#### Reports (18 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFOutputTakarir | 16 | تقارير الاخراج | Output reports |
| FFFInputTakarir | 16 | تقارير الادخال | Input reports |
| FormOutPuttakarirSpeed | 9 | تقارير سريعة | Fast output reports |
| FormInputtakarirSpeed | 5 | تقارير ادخال سريعة | Fast input reports |
| FormPharmHistory | 17 | تاريخ الصيدلية | Pharmacy history |
| FormExpiredDrugs | 21 | ادوية منتهية الصلاحية | Expired drugs report |
| FormDrugMonthly | 7 | تقرير شهري | Monthly drug report |
| FormBest100 | 2 | افضل 100 | Best 100 drugs |
| FormGardByRaf | 7 | حارس بالرف | Guard by shelf |
| FormDrugMoveMonthly | 6 | حركة شهرية | Monthly drug movement |
| FormInnSum | 13 | ملخص الادخال | Input summary |
| FormOotSum | 9 | ملخص الاخراج | Output summary |
| FormootThisDay | 11 | اخراج اليوم | Output this day |
| FormDrugsLastDays | 13 | اخر ايام الادوية | Drugs last days report |
| FormDrugsStckAtMonths | 12 | مخزون بالاشهر | Drug stock at months |
| FormDailyQuiod | 16 | حصة يومية | Daily quota |
| FormPeriodEhsa | 9 | احصاء الفترة | Period statistics |
| FormReportsGeneral | 61 | تقارير عامة | General reports (large) |

#### Settings (17 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FormPrinterSettings | 31 | اعدادات الطابعة | Printer configuration |
| FormPrinterSettingFary | 28 | اعدادات طابعة فاري | Fary printer settings |
| FormPharmacyInfo | 14 | معلومات الصيدلية | Pharmacy information/settings |
| FormAdvanced | 33 | متقدم | Advanced settings |
| FFFSHAPE | 8 | الشكل | Shape configuration |
| FormBarcodeSettings | 13 | اعدادات الباركود | Barcode settings |
| FFFColors | 4 | الالوان | Color settings |
| FormInternet | 7 | الانترنت | Internet settings |
| FormNetwasel | 2 | الاتصالات | Network connections |
| FFFScreens | 11 | الشاشات | Screen settings |
| FormStyles | 11 | الاساليب | Style settings |
| FormSounds | 22 | الاصوات | Sound settings |
| FormUploadOptions | 10 | خيارات الرفع | Upload options |
| FffSelectPrinter | 2 | اختيار الطابعة | Printer selection |
| FormEtaInfo | 9 | معلومات ETA | ETA information |
| FormCopyType | 0 | نوع النسخ | Copy type selection |

#### Tools & Utilities (10 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FormCalculator | 10 | الحاسبة | Calculator utility |
| FFFSODUKU | 36 | سودوكو | Sudoku game (Easter egg) |
| FFFPiano | 12 | بيانو | Piano utility |
| FormSaveFile | 3 | حفظ الملف | Save file dialog |
| FormOpenFile | 20 | فتح الملف | Open file dialog |
| FormPictureShow | 0 | عرض الصورة | Picture display |
| FormExecuteCode | 7 | تنفيذ الكود | Execute custom code |
| FormCopyMe | 3 | نسخ البيانات | Copy data |
| FormDownLoader | 3 | المحمل | File downloader |
| FormRemoteControl | 10 | التحكم عن بعد | Remote control |

#### Integrations (10 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| Formdtts | 26 | DTTS | DTTS (track and trace) |
| FormGovData | 5 | بيانات الحكومة | Government data |
| FormWasfaty | 27 | وصفتي | Wasfaty integration |
| FormRsdDispatch | 16 | ارسال RSD | RSD dispatch |
| FormFaryNet | 8 | فاري نت | FaryNet integration |
| FormIntegrations | 9 | التكامل | Integration settings |
| FormEcommerce | 6 | التجارة الالكترونية | E-commerce integration |
| FormElectroniaChecker | 14 | فاحص الفواتير الالكترونية | Electronic invoice checker |
| FormRempteTitan | 13 | ربط تيتان | Remote Titan connectivity |
| FormSelectdataBase | 12 | اختيار قاعدة البيانات | Database selection |

#### Import/Export (5 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FormImportFat | 14 | استيراد الفواتير | Import invoices |
| FormImportFromOtherDBI | 19 | استيراد من قاعدة بيانات اخري | Import from other DBI |
| FormImportFormOtherApps | 11 | استيراد من تطبيقات اخري | Import from other applications |
| FormImportFromExcell | 6 | استيراد من اكسل | Import from Excel |
| FormExportdataBase | 8 | تصدير قاعدة البيانات | Export database |

#### Maintenance & Backup (6 forms)

| Form | Procedures | Arabic Label | Purpose |
|------|-----------|-------------|---------|
| FFFClean | 36 | تنظيف | Database cleanup |
| FFFbackupAuto | 7 | نسخ احتياطي تلقائي | Automatic backup |
| FormBackRestore | 4 | استعادة النسخة | Backup/restore |
| FormRestore | 6 | الاستعادة | Data restore |
| FormUpdator | 7 | المحدث | Software updater |
| FormReadVer2 | 14 | قراءة نسخة 2 | Read version 2 data |

---

## Step 2: Navigation Structure

### Main Navigation Flow

```
FFFStartUp (Login)
    ├── FFFPharm (Main Pharmacy Screen)
    │   ├── FFFNew (Drug Entry MDI)
    │   │   ├── FFFNames (Drug Names)
    │   │   ├── FFFNewDrug (New Drug)
    │   │   ├── FFFNewDrugServer (New Drug Server)
    │   │   ├── FormDrugsDetails (Drug Details)
    │   │   └── FormParCode (Barcodes)
    │   ├── FFFInPut (Purchasing MDI)
    │   │   ├── FFFInputTakarir (Input Reports)
    │   │   ├── FFFINNquant (Input Quantity)
    │   │   └── FormLiveBuyInfo (Live Buy Info)
    │   ├── FFFOutPut (Sales/Output MDI)
    │   │   ├── FFFOutputTakarir (Output Reports)
    │   │   ├── FFFOUTQuant (Output Quantity)
    │   │   └── FormSellTime (Sales Timing)
    │   ├── FFFDS (Stock Management MDI)
    │   │   ├── FormStockNow (Current Stock)
    │   │   ├── FFFNeed (Needs/Shortages)
    │   │   ├── FFFSilsilaStock (Chain Stock)
    │   │   ├── FFFDrugEye (Drug Eye)
    │   │   └── FormDolap (Cabinet)
    │   ├── FormMoared (Transfers)
    │   ├── FormAmilShow (Employees)
    │   ├── FFFMony (Finance)
    │   ├── FormReportsGeneral (Reports)
    │   ├── FormSelectdataBase (Database Selection)
    │   ├── FormRempteTitan (Remote Connection)
    │   ├── FFFHelp (Help)
    │   └── FormPharmacyInfo (Settings)
    │       ├── FormPrinterSettings
    │   ├── FormBarcodeSettings
    │   ├── FormAdvanced
    │   └── FormInternet
    └── FormActivation (License)
```

### Arabic Navigation Tabs

| Tab | Arabic Label | English |
|-----|-------------|---------|
| 1 | المشتريات | Purchases |
| 2 | النواقص | Shortages |
| 3 | السجل | Record |
| 4 | مبيعات اليوم | Today's Sales |

---

## Step 3: Arabic UI Text

### Pharmacy Information Fields

| Field | Arabic Label | English |
|-------|-------------|---------|
| Name | اسم الصيدلية | Pharmacy Name |
| Address | عنوان الصيدلية | Pharmacy Address |
| Phone | تلفون الصيدلية | Pharmacy Phone |
| Commercial Register | السجل التجاري | Commercial Register |
| Tax Number | رقم التسجيل الضريبي | Tax Registration Number |
| Current User | المستخدم الحالي | Current User |

### Customer/Supplier Labels

| Field | Arabic Label | English |
|-------|-------------|---------|
| Customer Name | اسم العميل | Customer Name |
| Customer Number | رقم العميل | Customer Number |
| Customer Debt | مديونية العميل | Customer Debt |
| Address | العنوان | Address |
| Phone | الهاتف | Phone |
| Sales Rep | المندوب | Sales Representative |
| Supplier Name | اسم المورد | Supplier Name |
| Supplier Dues | مستحقات المورد | Supplier Dues |

### Drug Labels

| Field | Arabic Label | English |
|-------|-------------|---------|
| Drug | الصنف | Item/Drug |
| Quantity | الكمية | Quantity |
| Date | التاريخ | Date |
| Units | الوحدات | Units |
| Price with VAT | السعر شامل الضريبة | Price Including VAT |
| Price without VAT | السعر قبل الضريبة | Price Before VAT |
| Value with VAT | القيمة شامل الضريبة | Value Including VAT |
| Exchange | الصرف | Exchange |

### Financial Labels

| Field | Arabic Label | English |
|-------|-------------|---------|
| Credit | الاجل | Credit |
| Remaining | الباقي | Remaining |
| Paid | المدفوع | Paid |
| Value | القيمة | Value |
| Time | الوقت | Time |
| Discount | خصم | Discount |
| Invoices | فواتير | Invoices |
| Total Credit | اجمالي الاجل | Total Credit |
| Total Discounted | اجمالي المخصوم | Total Discounted |
| Total Cash Paid | اجمالي المدفوع نقدا | Total Cash Paid |
| Total | الاجمالي | Total |

### Navigation Tabs

| Tab | Arabic Label | English |
|-----|-------------|---------|
| 1 | المشتريات | Purchases |
| 2 | النواقص | Shortages |
| 3 | السجل | Record |
| 4 | مبيعات اليوم | Today's Sales |

### Button Labels

| Button | Arabic Label | English |
|--------|-------------|---------|
| Add Employee | اضافة موظف جديد | Add New Employee |
| Add Expense | اضافة مصروف | Add Expense |
| Change Permissions | تغيير صلاحيات موظف | Change Employee Permissions |
| Manual Shortages | كشف النواقص بنظام التسجيل اليدوي | Manual Registration Shortages |
| Employee Invoices | فواتير مبيعات موظف | Employee Sales Invoices |
| Total Hours | اجمالي ساعات الموظفين في الفترة | Total Employee Hours in Period |
| Total Purchases | اشتيات شاملة | Total Purchases |
| Total Purchase (G) | شراء غ شامل | Total Purchase (G) |
| Withdraw | صرف | Withdraw |
| Receive | قبض | Receive |
| Supplier Payment | سند صرف لمورد | Supplier Payment Voucher |

---

## Step 4: Properties & Metadata

### Form Complexity Rankings (by procedure count)

| Rank | Form | Procedures | Category |
|------|------|-----------|----------|
| 1 | FFFStartUp | 252 | System |
| 2 | FormDrugsDetails | 51 | Drugs |
| 3 | FormReportsGeneral | 61 | Reports |
| 4 | FFFNames | 65 | Drugs |
| 5 | FFFINNquant | 75 | Inventory |
| 6 | FormNeedsAll | 50 | Inventory |
| 7 | FFFDS | 76 | Stock |
| 8 | FormAccUploader | 47 | Finance |
| 9 | FFFINNquantEG | 47 | Inventory |
| 10 | FFFNeedAuto | 44 | Inventory |

### Form Category Statistics

| Category | Forms | Total Procedures |
|----------|-------|-----------------|
| Drugs | 32 | 412 |
| Reports | 18 | 243 |
| Inventory | 18 | 547 |
| Finance | 14 | 177 |
| Settings | 17 | 232 |
| Employees | 10 | 140 |
| Integrations | 10 | 130 |
| System | 10 | 273 |
| Tools | 10 | 63 |
| Patients | 5 | 38 |
| Import/Export | 5 | 58 |
| Maintenance | 6 | 74 |
| Sales | 2 | 17 |
| Purchasing | 3 | 89 |
| **TOTAL** | **160** | **2,563** |

### Module Statistics (Top 10 by Procedure Count)

| Module | Procedures | Purpose |
|--------|-----------|---------|
| Raz | 379 | Main module |
| ModStorage | 154 | Storage/stock |
| ModOot | 105 | Output |
| MD | 94 | Main |
| ModInn | 71 | Input |
| ModPrint | 70 | Printing |
| ModNetwork | 65 | Network |
| FLXMod | 55 | FlexGrid |
| ModEta | 48 | ETA |
| ModDTTS | 48 | DTTS |

---

## Step 5: Feature Mapping

### Core Features

#### 1. Drug Management
- Drug entry with barcode support (Code128, GS1)
- Drug details with Arabic/English names
- Drug-Drug interaction checking
- Expiry date tracking and alerts
- Price management (with/without VAT)
- Drug flow/movement tracking
- Similar drugs identification
- Drug classification and grouping
- Multiple barcode support
- Drug history tracking
- Monthly drug reports
- Drug name unification

#### 2. Inventory Management
- Current stock monitoring
- Needs/shortages calculation
- Minimum stock level control
- Warehouse management
- Transfer between pharmacies
- Chain pharmacy stock synchronization
- Cabinet/inventory organization
- Rawakid (dead stock) management
- Automatic needs calculation
- Stock at months reporting

#### 3. Purchasing
- Purchase order creation
- Supplier management
- Purchase reporting
- Live purchase information
- Chain buying support
- Input quantity management (Egypt variant)

#### 4. Sales
- Sales invoicing
- Credit sales management
- Sales timing tracking
- Output reports
- Daily sales tracking
- Best sellers reporting

#### 5. Finance
- MRD (installment customers) management
- Money/cash management
- Discount management
- VAT/Tax reporting
- Trial balance creation
- User money management
- Store discount management
- Capital balance tracking
- Money correction

#### 6. Employee Management
- Employee registration
- Shift tracking
- Attendance and absence tracking
- Salary calculation
- Permission management
- Employee reports
- Employee history

#### 7. Reporting
- Sales reports
- Purchase reports
- Stock reports
- Financial reports
- Employee reports
- Tax reports (VAT)
- Daily/monthly/periodic reports
- Custom report generation
- Report archiving

#### 8. System Administration
- User management
- Permission control
- Database backup/restore
- Printer configuration
- Barcode settings
- Internet/network settings
- Sound/color customization
- Screen settings
- Software activation
- Remote control

#### 9. Integrations
- ZATCA (Saudi tax authority)
- DTTS (Track and Trace)
- Wasfaty (prescription system)
- FaryNet
- E-commerce
- Electronic invoicing
- Government data
- Remote Titan connection

#### 10. Import/Export
- Excel import
- Database import/export
- Invoice import
- Cross-database import
- Data export

### Error Messages (Arabic)

| Message | Context |
|---------|---------|
| طلب معلق يحتاج لل保存 | Pending request needs save |
| تم اذالة عدد اصناف | Number of items deleted |
| لا تملك صلاحية البيع الاجل | No credit sale permission |
| لا يمكن تقفيل اليوم الحالي الا بعد الواحدة ظهرا | Cannot close day before 1 PM |
| لقد تم تقفيل اليوم فعليا | Day already closed |
| برجاء اعادة ادخال رقم المرور | Please re-enter password |
| الماحة علي القرص الصلب اصبحت قليلة | Low disk space |
| تم الادخال بنجاح | Entry successful |
| تم التعديل بنجاح | Edit successful |
| تم الحذف بنجاح | Delete successful |
| هل تريد الحذف فعلا؟ | Confirm delete? |
| لا يوجد بيانات | No data available |
| خطأ في الاتصال | Connection error |
| تم الحفظ بنجاح | Save successful |
