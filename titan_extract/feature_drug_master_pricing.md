# Feature: الدواء والأسعار — Drug Master & Pricing

**Purpose:** Manages the central drug catalog (الدواء) and its pricing (الأسعار) in TITAN.W1. Covers the drug-master tables (`wzdrugs`, `wzdrugs2`), the entry/editing forms, price-type and margin rules, price fixing/correction, expiry-date editing/fixing, drug-name unification, warehouse (مخزن) price margins, barcode handling (EAN/GS1, up to 5 barcodes per drug), GS1/DataMatrix/QR barcode reading, duplicate-barcode merging, and import from the external DrugEye (عين الدواء) drug database.

The drug master is the hub of the whole system: every stock batch (`wzgard`), every sales/purchase invoice line, and every chain-stock row references a drug by its unique `drugname`. Pricing has three principal levels — **سعر الجمهور (public), سعر الجملة (wholesale), سعر الشراء/التكلفة (cost/purchase)** — plus VAT.

---

## 1. Objects

### Forms (from decompiled string pool; `names` search)
| Object | Role |
|--------|------|
| `MDIForm FFFNewDrug` (many sub-procs, e.g. `@0x009edaf4` L375473, `@0x009d491c` L375625, `@0x00ac7114` L375777, `@0x00ac0004` L376469) | Main drug-master editor — add/edit a drug with all fields |
| `MDIForm FFFNewDrugServer` (`@0x00927a84` L658857, `@0x00a340d0` L658925, `@0x00a6b628` L659166) | Server-side drug master (chain sync) |
| `Form FormDrugPrice` (`@0x0092a2f4` L291049, `@0x009822cc` L291376, `@0x009f0dc4` L291835 — 21 strings, `@0x009c9388` L292070) | Drug price edit/view |
| `Form FormDrugsList` (`@0x009351e4` L500319 … `@0x00a78978` L502241 — 10 strings) | Drug catalog list/browse/search |
| `FormDrugsLists` (variant name in project; `FormDrugsList` per modules_gap_2 §27) | قائمة الأدوية/الأصناف |
| `Form FormDrugsDetails` (`@0x009cdf40` L179289, `@0x009b8cd0` L181384) | Drug detail card |
| `Form FormDrugHistory` (`@0x00addd88` L338136) | Drug price/change history |
| `Form FormDrugStckAtMonths` (`@0x0099ae38` L598069) | Stock-at-months view |
| `Form FormDrugFlow` (`@0x00b181ac` L189789) | Drug movement/flow |
| `Form FormDrugDrug` (`@0x00aeaffc` L285308) | Drug-interaction check |
| `Form FormFixDrugPrice` | تعديل سعر الدواء — fix/correct drug price (modules_gap_2 §39) |
| `Form FormPriceSetting` | إعدادات الأسعار — pricing/margin rules (modules_gap_2 §62) |
| `Form FormDrugStore` | المخزن/مستودع — warehouse stock + margin (modules_gap_2 §28) |
| `Form FormDrugStoreList` | قائمة المخازن (modules_gap_2 §29) |
| `Form FormDrugStoreName` | اسم المخزن (modules_gap_2 §30) |
| `Form FormNewStore` | إضافة مخزن جديد (modules_gap_2 §59) |
| `Form FormEditExpDate` | تعديل تاريخ الصلاحية (modules_gap_2 §31) |
| `Form FormFixExpDate` | تصحيح تاريخ الصلاحية (modules_gap_2 §40) |
| `Form FormExpiredDrugs` | أدوية منتهية الصلاحية |
| `Form FormBarcode` | Barcode entry/lookup |
| `Form FormBarcodeSettings` (`@0x009c5e50` L349722 … 14+ sub-procs) | Barcode-sticker print settings |
| `Form FormReapetedDrugMerge` (`@0x00a457f4` L689355) | Merge repeated drugs |

### Modules
| Module | Role |
|--------|------|
| `ModDrugsUnify` (`@0x009dbd20` L647184 … `@0x00ae14a4` L648431 — 20 strings) | Drug name unification / dedup (modules_gap_1 §20) |
| `ModDrgW` (`@0x0093ac40` L609064 … 20+ sub-procs) | Drug (master) window logic |
| `ModGS1Reader` (`@0x009e4034` L497505 … 24+ sub-procs) | GS1/EAN/DataMatrix/QR barcode parser (modules_gap_1 §12) |
| `ModMergeBarcodes` (`@0x00a2a350` L632088 … 15 procs) | Duplicate-barcode merging (modules_remaining_1 §19) |
| `ModBarCode128` (`@0x009a08a8` L348024, `@0x00ae7478` L348123 — 44 strings) | Code-128 barcode rendering for labels |

---

## 2. Step-by-Step Workflow

### 2.1 Add / edit a drug (FormNewDrug / FFFNewDrug)
1. Open إضافة دواء جديد (add new drug). As you type the first letters of the name, the program live-searches similar existing drugs to avoid duplicate names (strings_readable.txt:8275 «اثناء كتابة اول احرف من الاسم فيقوم البرنامج بالبحث عن الادوية الشبييه حتي لا يحدث تكرار لنفس الاسم»).
2. Enter mandatory master fields: Arabic name (drugnamear), unique English/trade name (drugname), and later optionally scientific/generic name, company, category (classy), shape.
3. Enter the international barcode (الباركود الدولي) plus up to 4 additional barcodes (Barcode1–Barcode5). A barcode may be scanned in with a reader instead of typed (FormBarcode).
4. Enter price data: cost (سعر الشراء), then a selling price — either typed directly or auto-computed from expected profit percent (strings_readable.txt:8632 «ادخل نسبة ربحك المتوقعه و سيتم احتساب سعر البيع بناءا علي هذه النسبه و سعر الشراء»).
5. Enter units/unitsmall, VAT percent, expiry (صلاحية).
6. Save → row written to `wzdrugs` (and cost/expiry to `wzdrugs2`).

> «الان يمكنك اكمال ادخال بقية بيانات الدواء مثل الاسم العلمي والعربي والشركة» — continue entering scientific/Arabic name and company. «تم تطوير شاشة الادوية والاسعار الجديدة بحيث تشمل الباركود الدولي والشركة» — the new drug-and-price screen includes the international barcode and company (modules_gap_2:1030-1031).

### 2.2 Browse / search drugs (FormDrugsList)
- «ابحث عن الصنف بالاسم او الباركودج وعدل السعر والباركود عند الحاجة من اسفل الشاشة» — search by name or barcode and adjust price/barcode from the bottom of the screen (modules_gap_2:564, FormFixDrugPrice:749).
- Search supports trade name (with `*` wildcards), generic/scientific name, up to 5 barcode fields, company, shape (drugeye_complete.md:146-151).

### 2.3 Price setting & margin (FormPriceSetting)
- Configure pricing rules: expected profit/margin. «ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة» — enter warehouse profit margin, usually 1 to 6 (modules_gap_2:581,1089).
- Pricing system: «ادخل 1 لنظام الربح أو 2 لنظام المبيعات» — enter 1 for profit system or 2 for sales system (strings_readable.txt:8437). This switches between margin-based pricing and sales-price-based pricing.

### 2.4 Fix / correct price (FormFixDrugPrice)
- Search a drug, view old price, enter new price, apply (single or bulk via chkBulk). Price changes are logged (wzdrugs `history`, `pricechanged` flag) and require permission («لا تملك صلاحية لعرض سعر الشراء» — no permission to view cost, strings_readable.txt:11663).

### 2.5 Warehouse margin (FormDrugStore)
- Each warehouse/store has its own profit margin (1–6). «وهو نظام مخازن الجملة وهو يسمح ببيع الدواء بخصم الشراء مطروحا منه…» — wholesale-store system allows selling at purchase-discount minus…; each item's discount depends on its purchase discount (strings_readable.txt:12596-12600).

### 2.6 Edit / fix expiry date (FormEditExpDate / FormFixExpDate)
- «اختر تاريخ الاستحقاق» / «اختر تاريخ الصلاحية اولا» — choose the expiry/due date first (strings_readable.txt:824, 8379). Correct per-batch or in bulk (FormFixExpDate). Expiry read via barcode scan (GS1 AI 17). «لا يمكن تكرار الصلاحية» — expiry cannot be duplicated (11670).

### 2.7 Barcode print settings (FormBarcodeSettings)
- Configure barcode-label paper, sticker size (length/width e.g. 3.8 × 1.2), label printer. «اجعل طابعة الباركود هي طابعة الليزر» (8293), «اختر طابعة الباركود اولا» (8386), «انواع ورق الباركود المتوافق مع تيتان» / «اوراق الباركود المتوافقة» (9832/9840). Code-128 labels rendered by ModBarCode128.

### 2.8 GS1 / EAN barcode reading (ModGS1Reader)
- Reads international barcodes: EAN-13 (1D), GS1-128, DataMatrix (2D), and QR («اصبح البرنامج يدعم قارئات الباركود كيو ار وداتا ماتريكس بجانب الباركود العادي» — now supports QR and DataMatrix alongside normal barcode, strings_readable.txt:8834).
- Parses GS1 Application Identifiers: GTIN, batch (AI 10), expiry (AI 17), serial (AI 21). Adds the drug by barcode reader (8963).

### 2.9 Merge duplicate barcodes (ModMergeBarcodes / ModDrugsUnify / FormReapetedDrugMerge)
- «ازالة تكرار الباركود للاصناف» — remove duplicate barcodes (8748); «تنظيف تكرار الباركود» — clean duplicate barcode (10487).
- «امكانية توحيد قاعدة بيانات الاصناف ما بين صيدلياتي حيث سيتم توحيد اسم الصنف والباركود وكود الصنف وذا رغبت سيتم توحيد الاسعار» — unify drug database across pharmacies: unify drug name, barcode, item code, and optionally prices (9799). «يجب ان يتم هذا الاجراء فقط من الصيدلية الرئيسية» — only from the main pharmacy (12638). «غير متاح حذف صنف في حالة توحيد قاعدة البيانات» — deleting an item is unavailable while unification is active (11353).
- Name dedup: «اسماء مكررة بنفس الصيغة» — duplicate names with same formula (8812), «تلك الادوية مكررة» — these drugs are duplicated (12415).

### 2.10 Import from DrugEye (عين الدواء)
- TITAN downloads `drugeye.update.titan.rar` from `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar`, extracts and copies `DRUGS.PHY` to the program folder (drugeye_complete.md:167-170). **⚠️ VERIFIED 2026-08-15: the file is NOT a RAR — it is a ROT-4-obfuscated text feed of 23,452 drug records, and this download path is dead code in the analyzed build (0 p-code refs); the live path is `drugeye.pharorg.com` web-service + native `.phy` record I/O (drugeye_complete.md §7A, §9).** Drug master data imported via `fromdrugeye.phy` into the working DB. Export to DrugEye goes to `\Files\Export\DrugEye\` (drugeye_complete.md:172-184).

---

## 3. Fields / Data Captured

### 3.1 `wzdrugs` — Drug Master (schema_complete.sql:14-43)
| Column | Type | Meaning |
|--------|------|---------|
| `drugname` | nvarchar(100) NOT NULL | Unique trade name (PK / key) |
| `drugnamear` | nvarchar(100) NOT NULL | Arabic name |
| `barcode` | varchar(16) NOT NULL | Main international barcode |
| `Barcode1..Barcode5` | varchar(16) | Additional barcodes (up to 5) |
| `vat` | real | VAT percentage |
| `units` | int | Units in pack |
| `Unitsmall` | int | Small units |
| `classy` | nvarchar(35) | Drug category/form |
| `generic` | nvarchar(120) | Generic/scientific name |
| `pharmacology` | nvarchar(200) | Pharmacology class |
| `co` | nvarchar(100) | Company/manufacturer |
| `unitsclass` | nvarchar(50) | Unit classification |
| `price` | real | Selling price |
| `PriceNow` | real | Current price |
| `lastedit` | datetime | Last-edit timestamp |
| `pharmacyid` | nvarchar(15) | Pharmacy identifier |
| `stock` | real | Current stock |
| `titanid` | int | Internal ID for chain sync |
| `disco` | real | Discount percentage |
| `pricechanged` | bit | Price-change flag |
| `localimport` | int | Import-source flag |
| `wareprice3` | nvarchar(50) | Warehouse price reference |
| `history` | nvarchar(max) | Change history |
| `agel` | real | Age-related flag |

### 3.2 `wzdrugs2` — Cost / Extended Data (schema_complete.sql:48-53)
| Column | Type | Meaning |
|--------|------|---------|
| `drugname` | nvarchar(100) | FK to `wzdrugs` (1:1) |
| `unitcost` | real | Unit cost (computed from `wzgard`) |
| `costvalue` | real | Cost value |
| `expire` | real | Expiry date (VB6 date serial) |

### 3.3 FormNewDrug controls (modules_gap_2:1026)
`txtNameAr`, `txtNameEn`, `txtScientificName`, `txtBarcode1-5`, `cmbCompany`, `cmbCategory`, `txtBuyPrice`, `txtSellPrice`, `txtExpDate`, `btnSave`.

### 3.4 FormDrugsList controls (modules_gap_2:560)
`dgDrugs`, `txtSearch`, `cmbCategory`, `cmbCompany`, `btnAdd`, `btnEdit`, `btnDelete`.

### 3.5 FormDrugStore controls (modules_gap_2:576)
`dgStock`, `cmbDrug`, `txtQuantity`, `cmbLocation`, `btnTransfer`, `btnAdjust`.

### 3.6 FormFixDrugPrice controls (modules_gap_2:745)
`cmbDrug`, `txtOldPrice`, `txtNewPrice`, `btnApply`, `chkBulk`, `dgDrugs`.

### 3.7 FormPriceSetting controls (modules_gap_2:1085)
`txtProfitMargin`, `txtMaxDiscount`, `cmbPricingMethod`, `btnSave`.

### 3.8 FormEditExpDate controls (modules_gap_2:619)
`cmbDrug`, `txtBatchNo`, `txtOldExpiry`, `txtNewExpiry`, `btnSave`, `btnCancel`.

### 3.9 DrugEye import fields (drugeye_complete.md:95-114, 207-212)
`drugname`, `Barcode/Barcode1-5`, `price`, `PriceNow`, `disco`, `units`, `Unitsmall`, `shape` (int drug form), `stock`, `company/CompanyName`, `Expire`, `pack/packs`, `vat`, `localimport`, `classy`, `pharmacyid`, `lastedit`, `titanid`. The `drgserver` table rows carry `datee, silsila, mobile, drugname, price, barcode, units, vat, shape, localimport`.

---

## 4. Side-effects

- **Stock (`wzgard`)**: Every purchase/return/sale batch row carries `drugname` (FK), `quant`, `expire`, `price`, `costvalue`, `vatvalue`, `totalwithvat`, `oldstock` (schema_complete.sql:58-74). Drug master `stock` mirrors totals; `wzdrugs2.unitcost` is computed from `wzgard`.
- **Chain stock**: `titanksastock` and `titanstock` rows reference `drugname` and sync via `titanid`, `pharmacyid`, `lastedit` (`INSERT … (drugname,lastedit,pharmacyid,price,stock,barcode,titanid)`).
- **Needs / purchases**: `titanneed` and `storediscount` reference `drugname`.
- **Audit trail**: `TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)` logs price/barcode changes (business_logic_complete.md:449).
- **History**: `wzdrugs.history` (nvarchar max) and FormDrugHistory store price-change log («تاريخ التعديل الصنف التعديل سعر البيع خصم الشراء قيمة التعديل الفرع» — strings_readable.txt:139).
- **Unification**: merging drug names/barcodes rewrites references across `wzdrugs`, `titanksastock`, `titanksastock`, `drgserver`; blocks item deletion while active.

---

## 5. Pricing + VAT Formulas

### 5.1 Price types (strings_readable.txt)
- **سعر الجمهور (public price)** — shelf/retail price (10993). Used for valuation «قيمة كل ادوية الصيدلية بسعر الجمهور» (2969) and «المبيعات بسعر الجمهور» (9625).
- **سعر الجملة (wholesale price)** — الجملة (9274), with currency variants «الجملة بالدولار» (9275), «الجملة بالدينار» (9276). Wholesale discount system: «خصم الجملة» (10767), «النظام الرابع خصم الجملة» (9729). «يعتمد خصم كل صنف علي قيمة خصم الشراء» (12600).
- **سعر الشراء / التكلفة (cost/purchase price)** — three sub-types (business_logic_complete.md:303-309):
  - **سعر الشراء الحقيقي (actual/real)** — net amount on the purchase invoice, actually paid to supplier (strings_readable.txt:12345).
  - **سعر الشراء الحسابي (calculated)** — system-computed from inputs (discounts, sales VAT, extra discounts) (strings_readable.txt:10008).
  - **Real vs calculated** — «الفرق كبير بين سعر الشراء الحسابي والحقيقي» warns when the gap is large (9510); «لا يمكن ان يكون الفارق بين سعر الشراء الحقيقي وسعر الشراء الحسابي بمثل هذه الدرجة» (11697).

### 5.2 Margin / profit rules (FormPriceSetting)
- Margin-based pricing: «ادخل نسبة ربحك المتوقعه و سيتم احتساب سعر البيع بناءا علي هذه النسبه و سعر الشراء» (8632).
- System selection: «ادخل 1 لنظام الربح أو 2 لنظام المبيعات» (8437).
- Warehouse margin: «ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة» (8635) — typically 1–6.
- «نسبة هامش الربح في المبيعات» (12305).

### 5.3 VAT
- `wzdrugs.vat` stores the drug's VAT percentage. Invoice formulas (business_logic_complete.md:788-791):
  - `Subtotal = Σ(Quantity × Unit Price)`
  - `VAT = (Subtotal − Discount) × (VAT% / 100)`
  - `Total = Subtotal − Discount + VAT`
- Vat types: `TttNotVatedUnit` (non-vatted unit price), `TttNotvatedAll` (non-vatted total), `Vat%`, `Vat.No` (business_logic_complete.md:936-941).
- VAT price modes: «سعر البيع شامل الضريبة / غير شامل الضريبة», «سعر الجمهور», «مبيعات بسعر الجمهور شامل الضريبه» (strings_readable.txt:10990-10993, 11982).
- Price must be > 0 on change; «New Price for [drug]» / «Input new Price for [drug]» (business_logic_complete.md:880-882).

---

## 6. Payment Methods
Payment applies at the invoice level (sales/purchases), not the drug master. Referenced payment modes: **كاش (cash)**, **شبكة/فيزا (network/visa)**, **أجل (credit)** — «مسدد نقدا مشتريات / مسدد شبكة مشتريات / اجل المشتريات» (strings_readable.txt:897). The drug master's prices feed these invoice totals; discount methods include fixed-currency discount, discount by % of profit, and discount by % of total (business_logic_complete.md:956-966).

---

## 7. Printing
- **Barcode labels**: FormBarcodeSettings — choose label paper (انواع ورق الباركود المتوافق مع تيتان), set printer (اختر طابعة الباركود اولا), sticker size 3.8 × 1.2 (strings_readable.txt:8386, 8684, 9041). ModBarCode128 renders Code-128. «امكانية الطباعة علي ملصقة الباركود غير المقسومة» — printing on non-divided label rolls (9793). «اضافة امكانية طباعة الريسيت والباركود من الاجهزة الفرعية» — print receipt and barcode from sub-devices (8943). «اتاحة طباعة باركود اي صنف منفرد من شاشة المشتريات» — print a single item's barcode from purchases screen (8268).
- **Drug labels/reports**: FormDrugsList / FormDrugPrice support printing drug cards and price lists. Print model numbers 500/600/700/800 referenced in the form strings («ادخل رقم نموذج الطباعه من القيم الاتيه 500 600 700 800» — FFFNewDrug L376607).

---

## 8. Tables
- **`wzdrugs`** — drug master (see §3.1). Related tables referencing it: `wzdrugs2`, `wzgard`, `titanksastock`, `titanstock`, `titanneed`, `drgserver`, `storediscount` (schema_complete.sql:451-457).
- **`wzdrugs2`** — cost/expiry extension, 1:1 with `wzdrugs` (see §3.2).
- **`wzgard`** — per-pharmacy stock batches (schema_complete.sql:58-74).
- **`drgserver`** — drug server/shared list (`datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport`) for chain sync via DrugEye (drugeye_complete.md:207-212).
- **`usersourceupdate`** — cloud sync queue for drug price/stock updates (drugeye_complete.md:190-201).
- **`drugeyedash2`** — DrugEye dashboard/analytics source (schema_complete.sql:378-387).
- **`TitanUserAction`** — change audit log (business_logic_complete.md:449).

---

## 9. UI Strings (Arabic)
From `strings_utf16.txt` / `strings_readable.txt` (line refs below are `strings_readable.txt` unless noted):

**Search / list:**
- «ابحث عن الصنف بالاسم او الباركودج وعدل السعر والباركود عند الحاجة من اسفل الشاشة» (:8263)
- «بحث بالاسم التجاري او الباركود او الرقم» (:9866)
- «كل الادوية» (FFFNewDrug L376859)
- «ادوية بلا باركود» (:8644), «ادوية لها اكثر من باركود دولي» (:8653), «ادوية ليس لها باركود دولي» (:8656)
- «ادوية كل او جزء من كميتها يتبقي علي انتهاء صلاحيتها اقل من ثلاثة اشهر» (:8651)

**Barcodes:**
- «الباركود الدولي احد اهم العناصر في تيتان حيث ان عمليات تحديث قاعدة بيانات الادوية تتم من خلال التعرف علي الباركود الدولي لكل دواء» (:9177)
- «الباركود الطبيعي طوله 13 رقم فهل انت متاكد من دخوله بشكل سليم» (:9182)
- «الباركود الذي ادخلته يتطابق مع الباركود الذي تخلقه الطابعة حيث يتكون من ثمانية ارقام ويبدا برقم 8 او 9 من فضلك لا تستخدم هذا الباركود كباركود دولي» (:9181)
- «باركود دولي ذو بنية غير سليمة» (:9855), «باركود دولي مشترك بين اكثر من دواء» (:9856), «باركود غير موجود» (:9857)
- «الباركود الدولي الذي تم ادخاله غير مرتبط باي دواء في قاعدة البيانات» (:9178)
- «برجاء توجه الي شاشة تعديل بيانات الادوية لتربط هذا الباركود بالدواء المناسب» (:9922)
- «اضافة دواء بواسطة قارئ الباركود» (:8963), «اذا تعثر اضافة دواء بواسطة قارئ الباركود فقم باضافاه بطريقة الباحث اليدوي» (:8680)
- «الغاء التحويل الاجباري للغة الانجليزية عند تمرير الباركود في مصر وابقائها في السعودية للتوافق مع نظام رصد» (:9475)
- «اختبار الباركود الدولي» (:8361)
- «ادخل رقم 1 لعمود الباركود الدولي و 0 لتجاهله» (:8533)

**Pricing:**
- «ادخل سعر الشراء» (:8569)
- «ادخل نسبة ربحك المتوقعه و سيتم احتساب سعر البيع بناءا علي هذه النسبه و سعر الشراء» (:8632)
- «ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة او غيرها» (:8635)
- «ادخل 1 لنظام الربح أو 2 لنظام المبيعات» (:8437)
- «سعر البيع» (:10990), «سعر الجمهور» (:10993), «سعر الشراء» (:10996), «سعر الشراء الحسابي» (:10997), «سعر الشراء الحقيقي» (:10998)
- «الاصناف بسعر البيع» (:9139), «الاصناف بسعر الشراء» (:9140)
- «مبيعات بسعر الجمهور» (:9625), «مبيعات بسعر التكلفة» (:9623)
- «لا تملك صلاحية لعرض سعر الشراء» (:11663)
- «نسبة هامش الربح في المبيعات» (:12305)
- «الفرق كبير بين سعر الشراء الحسابي والحقيقي من فضلك راجع مدخلات الفاتورة» (:9510)
- «تطوير طريقة ادخال قيمة سعر الشراء وسعر البيع مباشرة في فواتير البيع والشراء» (:10220)

**Expiry:**
- «اختر تاريخ الصلاحية اولا» (:824), «اختر تاريخ الاستحقاق» (:8379)
- «ادخل الصلاحية كما تنطقها او تسعمها» (:8492)
- «لا يمكن تكرار الصلاحية» (:11670)
- «بعض الادوية الموجودة في الفاتورة منتهية الصلاحية» (:9952)
- «اذا كنت تقف في حقل تاريخ الصلاحية وتود تغييره اثناء اضافة دواء الي فاتورة» (:8701)
- «استخدم اتجاهات لوحة المفاتيح الاعلي والاسفل لاختيار تاريخ الصلاحية» (:8752)

**Unification / merge:**
- «ازالة تكرار الباركود للاصناف» (:8748), «تنظيف تكرار الباركود» (:10487)
- «امكانية توحيد قاعدة بيانات الاصناف ما بين صيدلياتي حيث سيتم توحيد اسم الصنف والباركود وكود الصنف وذا رغبت سيتم توحيد الاسعار» (:9799)
- «يجب ان يتم هذا الاجراء فقط من الصيدلية الرئيسية في حالة توحيد قاعدة البيانات» (:12638)
- «غير متاح حذف صنف في حالة توحيد قاعدة البيانات» (:11353)
- «اسماء مكررة بنفس الصيغة» (:8812), «هذه الادوية مكررة :: للسماح بتكرار الادوية برجاء تفعيل الخاصية في شاشة اعدادات متقدمة» (:12415)
- «تم تطوير الية منع تكرار الباركود الدولي ليشمل الحقول الاضافية» (:10419)

**GS1:**
- «اصبح البرنامج يدعم قارئات الباركود كيو ار وداتا ماتريكس بجانب الباركود العادي» (:8834)
- «تحسين قراءة الباركود وزيادة سرعته» (FFFNewDrug L376733)

**Warehouse:**
- «المخزن» (modules_gap_2:580), «ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة» (modules_gap_2:581)
- «وهو نظام مخازن الجملة وهو يسمح ببيع الدواء بخصم الشراء مطروحا منه» (:12596)

---

## 10. Business Rules / Edge Cases

1. **Unique names**: drugname must be unique; live search prevents duplicate names; «لا يمكن تكرار نفس الاسم لاكثر من عميل» (11715) applies similarly to catalog.
2. **Barcode uniqueness**: a barcode may not repeat across drugs; «ولا يمكن تكرار الباركود لاكثر من دواء» (12577). Duplicates are detected («يوجد لهذه الادوية نفس الباركود الدولي لادوية اخري موجودة فعلا في القائمة» — 911) and must be merged/cleaned.
3. **Barcode structure validation**: EAN-13 length check (13 digits); internal Code-128 printer barcodes (8 digits starting 8/9) must not be used as international barcodes (9181-9182).
4. **Cost accuracy**: real vs calculated purchase cost must not diverge abnormally; system warns and blocks when gap is extreme (9510, 11697). «نقصد بسعر الشراء الحقيقي هو المبلغ الصافي الوارد في فاتورة الشراء…» (12345).
5. **Permission gate**: viewing/editing cost price requires permission («لا تملك صلاحية لعرض سعر الشراء»); price edits logged and flagged (`pricechanged`, `history`, `TitanUserAction`).
6. **Expiry integrity**: expiry cannot be duplicated per batch (11670); invalid/expired entries flagged («بعض الادوية دخلت بغير تاريخ صلاحية صحيح» — 9953).
7. **Unification constraints**: while unification active, item deletion is blocked; operation restricted to the main pharmacy; periodic maintenance recommended (weekly — «نرجو تكرار تنفيذ هذا الامر مرة واحدة كل اسبوع» — 11116).
8. **Insufficient stock**: if stock is insufficient, item isn't added silently — barcode reader sound only (8693); expiry picker appears when dispensing quantity exceeding stock is allowed (9350).
9. **Price types & valuation**: drug catalog valued at public price (سعر الجمهور) for pharmacy-total reports (2969, 9226).
10. **VAT on sale price**: system verifies VAT is present on sale price in all invoices («التاكد من وجود قيمة الضريبة علي سعر البيع في كل الفواتير» — 9234).
11. **Wholesale vs retail**: wholesale stores price using purchase-discount-driven scheme; each item's discount = its purchase discount (12596-12600).

---

## Sources
- `schema_complete.sql` / `schema_complete.md` — tables 1 (`wzdrugs`), 2 (`wzdrugs2`), 3 (`wzgard`), 24 (`drugeyedash2`).
- `drugeye_complete.md` — external DrugEye DB, import/export, `drgserver`, `usersourceupdate`, `.phy` files, drug shapes.
- `drug_database_legal.md` — licensing of external drug data.
- `business_logic_complete.md` §19 (Price & VAT) and §20 (Expiry).
- `modules_gap_1.md` §12 (ModGS1Reader), §20 (ModDrugsUnify).
- `modules_gap_2.md` §27-32, §39-40, §58-59, §62 (forms).
- `modules_remaining_1.md` §19 (ModMergeBarcodes).
- `strings_readable.txt` / `strings_utf16.txt` — UI strings and business-rule text.
- `pcode_strings.py names/proc` — object inventory and per-proc decoded strings.
