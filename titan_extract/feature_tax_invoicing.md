# الفوترة الضريبية — Tax Invoicing (VAT / ZATCA / DTTS / ETA-DTTS)

**App:** TITAN.W1 (Phye.exe, VB6 p-code)
**Arabic name:** الفوترة الضريبية / الضريبة (الفوترة الالكترونية — Tax / E-Invoicing)
**Purpose:** Complete tax-invoicing subsystem covering (a) **VAT** computation and application on both sales and purchase invoices (ضريبة القيمة المضافة), (b) **Saudi ZATCA** e-invoicing (فواتير ZATCA — XML / QR / CSID digital signing via the Saturn companion tool), (c) **Egyptian DTTS / ETA** integration (ModDttsEgypt, ModEtaWrappper — Egyptian Tax Authority e-invoicing), and (d) the **tax return / VAT report** (تقرير الضريبة المضافة / فاتورة ضريبية). Tracks taxable vs exempt (غير خاضعة للضريبة) items, VAT% default **15%**, the live `<masrofat-vat>` XML tag, and produces VAT reports (monthly / quarterly / annual).

**Sources reused (READ-ONLY):** `zatca_complete.md`, `dtts_complete.md`, `schema_complete.sql`/`schema_complete.md`, `business_logic_complete.md`, `reports_complete.md`, `ui_complete.md`, `ui_forms.json`, `ui_strings_readable.txt`, `modules_gap_1.md`, `modules_gap_2.md`, `feature_sales_invoices.md`, `feature_purchases.md`. Ground truth: `titan_decompile/` (`strings_utf16.txt`, `strings_readable.txt`, `pcode_disasm.txt`) via `/tmp/opencode/pcode_strings.py`.

---

## 1. Objects

### 1.1 Tax/VAT modules, forms, and procs

| Object | Type | Procs | Arabic | Role |
|---|---|---|---|---|
| **ModVatReport** | Module | 3 | — | VAT report engine (used by FormVat2 / تقرير الضريبة المضافة). `ui_complete.md`, `reports_complete.md:551-555` |
| **FormVat** | Form | 20 | — | GCC / Gulf VAT report form (تقرير ضريبة القيمة المضافة لدول الخليج). `zatca_complete.md:8`, `reports_complete.md:565` |
| **FormVat2** | Form | 38 | — | Extended VAT form — quarterly VAT report (تقرير الضريبة المضافة الربع سنوي), export to ZATCA/Excel/PDF. `zatca_complete.md:9`, `reports_complete.md:551-563` |
| **FormVatfakeInvo** | Form | 15 | — | Fake-invoice VAT handling (بدون ترويسة/حالة خاصة). `zatca_complete.md:10` |
| **FormDariba** | Form | 5 | الضريبة | Tax/duty report (وحدة الضريبة). `ui_complete.md:150`; procs `@0x008db590`, `@0x009248f0`, `@0x00924bc0`, `@0x009a40e4`, `@0x009e1c84` |
| **FormFat** | Form | — | الفاتورة (مشتريات/مرتجعات) | Purchase/return invoice entry — main purchase invoice screen (item grid `dgItems`, supplier `cmbSupplier`, totals `txtTotal/txtDiscount/txtTax`, save/print/delete). `modules_gap_2.md:704-721` |
| **FormFatList** | Form | — | قائمة الفواتير | Invoice listing/browse — all purchase invoices filtered by date/supplier. `modules_gap_2.md:724-733` |
| **FormInnSetVatAct** | Form | — | ضريبة المشتريات | Set purchase-VAT activation. `feature_purchases.md:29` |
| **ModZatca** | Module | 14 | — | Core Saudi ZATCA integration (invoice build, send, response). `zatca_complete.md:7` |
| **ModZatca2Wraber** | Module | 24 | — | Extended ZATCA functions (field mapping, validation, report generation). `zatca_complete.md:8` |
| **Modzatcasign** | Module | 3 | — | ZATCA XML/JSON digital signing (BouncyCastle). `zatca_complete.md:9` |
| **ModSaturn** | Module | 24 | — | Wrapper for the external `saturn.exe` signing/CSID tool (launch, params, response read, counter/hash verify). `modules_gap_1.md:679-713`, `zatca_complete.md:9` |
| **ModEtaWrappper** | Module | 7 | — | Egyptian Tax Authority (ETA) e-invoicing wrapper (XML build, submission, UUID, validation/retry). `modules_gap_1.md:367-396`, `zatca_complete.md:12` |
| **ModDttsEgypt** | Module | 2 | — | Egyptian DTTS variant (ETA endpoints, `C:\eta-qr\`, eToolKit). `dtts_complete.md:802-823`; procs `@0x009b3cb4`, `@0x00aa5278` |
| **ModDTTS** | Module | 48 | — | SFDA Drug Track & Trace (Saudi RSD SOAP services). `dtts_complete.md:4` |
| **ModTafqit** | Module | 4 | — | Arabic number-to-words (تقطيع) for amounts on invoices. `zatca_complete.md:13` |
| **FormRsdDispatch** | Form | 16 | — | RSD dispatch (connects ZATCA with drug tracking of dispatched items). `zatca_complete.md:11`, `dtts_complete.md:6` |
| **FormGovData** | Form | 5 | — | Government data form (seller/buyer GLN, gov tax registration). `zatca_complete.md:12`, `dtts_complete.md:9` |
| **FormEtaInfo** | Form | 9 | — | Egypt ETA link status (حالة ربط ETA) / submission status. `dtts_complete.md:8`, `reports_complete.md:640-644` |

Live-string anchors: sales chain GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` = idx 7423 (referenced 3,564× in SQL-concat loops); VAT tags `<masrofat-vat>`, `<sales-vat>`, `<purchases-vat>`, `<drug-stock>` are live references (`feature_notes.md:22`; `business_logic_complete.md:1116-1119`).

---

## 2. Step-by-step workflow

### 2.1 VAT on a Sales invoice (`oot`)
1. Customer selected (or **RANDOM CLIENT**); drug added (barcode / manual / name / invoice#).
2. Quantity (شريط تحديد الكمية والصلاحية / FFFOOTQuant) + expiry chosen first (`اختر تاريخ الصلاحية اولا` idx 1056).
3. Unit price verified (سعر رسمي vs سعر بيع); per-item **SellDisc** and/or whole-invoice discount (`ادخل نسبة خصم علي اجمالي الفاتورة` idx 9086).
4. **VAT computed** (`business_logic_complete.md:786-792`):
   ```
   Subtotal  = Σ (Quantity × Unit Price)
   Discount  = Subtotal × (SellDisc / 100)
   VAT       = (Subtotal − Discount) × (VAT% / 100)   [VAT% default 15]
   Total     = Subtotal − Discount + VAT
   ```
5. Prices may be displayed شامل الضريبة (VAT-inclusive) or غير شامل الضريبة (VAT-exclusive) — idx 11661/11662, `ui_strings_readable.txt:1360-1361,2294-2295`.
6. Save (F9) → `titanksasales` chain row (GUID insert) + per-line `invoicedata` + stock decrement in `wzgard` + money in daily files.
7. If ZATCA/ETA linked, the tax invoice is emitted as a **فاتورة ضريبية** (see 2.3/2.4).

### 2.2 VAT on a Purchase invoice (`وارد`)
1. Supplier (المورد) required first (`برجاء اختيار المورد اولا`); or الجرد الاولي / مورد غير معروف / الشراء من غير الموردين.
2. Items entered: quantity, **real purchase price** (سعر الشراء الحقيقي) and **calculated purchase price** (سعر الشراء الحسابي), buy discount (خصم الشراء), expiry, batch/serial (تشغيلة/سيريال).
3. **VAT auto-calculated** on taxable items at 15%; `costvalue`, `vatvalue`, `totalwithvat` recorded per `wzgard` row (`feature_purchases.md:5.2,8.2`).
4. Total VAT may be **manually overridden** (`تعديل قيمة اجمالي ضريبة القيمة المضافة يدويا في المشتريات`; per-item `تعديل قيمة ضريبة القيمة المضافة لهذا الصنف`).
5. Save → stock **added** (`typee` = in), supplier payable (دائن / مستحقات المورد) increased via `farysales` credit entry (خصوم.موردين).
6. Some suppliers are **exempt** from VAT — `الموردين التليين تم استثناء فواتيرهم من احتساب الضريبة` (idx 1210).

### 2.3 Saudi ZATCA e-invoicing flow (`zatca_complete.md:723-743`)
```
Invoice created in Titan
  → JSON built (seller, buyer, items, taxTotals, netAmount, qr)
  → UUID generated:  toolkit.exe --generate-uuid --input-json-path summer_without_uuid.json --output-json-path summer_with_uuid.json
  → JSON-with-UUID → Saturn (saturn.exe) signs with BouncyCastle → signed.xml
  → QR Code generated (MessagingToolkit.QRCode.dll / QR server / Google chart API)
  → Response: zatca-response → Zatca-response.txt
  → Stored: C:\saturn\zatca\computer-1\invoices\
  → Counter updated: counter.txt ; Hash updated: hash.txt
  → DB row in ZATCA table (uuid, status, hash, xml, response)
```

### 2.4 Egyptian ETA/DTTS flow (`modules_gap_1.md:367-396`, `dtts_complete.md:802-823`)
```
Purchase/sales invoice
  → ModEtaWrappper builds XML (header, items, tax totals, UUID)
  → POST to https://api.invoicing.eta.gov.eg  (prod) / https://api.preprod.invoicing.eta.gov.eg (preprod)
  → parse response (status, UUID, errors); retry/validate (proc 7)
  → track uuid in titanksasales; status shown in FormEtaInfo (حالة ربط ETA)
  → QR stored under C:\eta-qr\
```

### 2.5 Tax return / VAT report generation
1. Period chosen (quarterly الربع سنوي / monthly شهري / annual سنوي).
2. FormVat2 sums sales & purchase VAT (`business_logic_complete.md:968-974`).
3. Output written to `\Files\Accounting\Vat-reports\` as `VatFile-<date>` + `VatFile-Result.txt`.
4. Export to ZATCA format / Excel / PDF (`reports_complete.md:563`).

---

## 3. Fields / data captured

### 3.1 ZATCA JSON invoice fields (`zatca_complete.md:95-206`, `reports_complete.md:1191-1255`)
```
Top level: uuid, previousUUID, referenceUUID, referenceOldUUID,
           deviceSerialNumber, invoiceCounter, invoiceNumber,
           invoiceType{invoiceType,invoiceTypeAll}, seller{}, buyer{},
           invoiceItems[], taxTotals[], netAmount, qr
Seller:    seller-name, seller-name-arabic, seller-vat-number, seller-street,
           seller-building-number, seller-plot-id, seller-city, seller-district,
           seller-postal-zone, seller-region, seller-crn
Buyer(B2B): buyer-name, buyer-vat-number, buyer-street, buyer-building-number,
           buyer-plot-id, buyer-city, buyer-district, buyer-postal-zone,
           buyer-region, buyer-crn;  buyer-data-in-case-of-b2b-invoice-only
Item:      item-name, quantity, tax-percent, total-value,
           taxableItems[{taxType,taxRate,taxAmount,taxableAmount}]
Tax totals: taxTotals[{taxType,taxAmount}]
Discounts: commercialDiscountData[], itemDiscountData[], extraReceiptDiscountData[]
```
Reports section adds (ETA-style camelCase): `header{dateTimeIssued,receiptNumber,uuid,type,typeVersion,currency,exchangeRate}`, `seller{name,vatNumber,crNumber,activityCode,branchAddress{...}}`, `buyer{name,vatNumber,id}`, `documentType{receiptType,documentUseReason}`, `itemData[]{itemCode,internalCode,description,quantity,unitType,unitPrice,currency,taxableItems[]{taxType,amount,rate,subType},commercialDiscountData,itemDiscountData}`, `taxTotals[]{taxType,amount}`, `totalSales,totalCommercialDiscount,totalItemsDiscount,netAmount,totalAmount,paymentMethod,extraReceiptDiscountData`.

### 3.2 ZATCA DB table (`schema_complete.sql:434-447`, table 28)
```sql
CREATE TABLE ZATCA (
    id              INT IDENTITY(1,1),   -- PK
    invoiceid       REAL DEFAULT 0,      -- invoice number
    uuid            NVARCHAR(100) DEFAULT '',  -- ZATCA UUID
    datee           REAL DEFAULT 0,      -- date (VB6 serial)
    pharmacyid      NVARCHAR(15) DEFAULT '',
    status          NVARCHAR(50) DEFAULT '',   -- submission status
    hash            NVARCHAR(200) DEFAULT '',  -- invoice hash
    xml             NVARCHAR(MAX) DEFAULT '',  -- raw XML
    response        NVARCHAR(MAX) DEFAULT ''   -- ZATCA response
);
```

### 3.3 VAT in stock/cost (`schema_complete.sql:70-71`, `wzgard`)
```
costvalue    REAL  -- cost value (excl. or basis for COGS)
vatvalue     REAL  -- VAT value on the batch
totalwithvat REAL  -- total including VAT
```
Drug card `wzdrugs` also has a `vat` percentage column (`schema_complete.sql:23`).

### 3.4 FormFat / purchase-invoice fields (`modules_gap_2.md:704-721`)
- Controls: `dgItems` (editable grid), `cmbSupplier`, `txtInvoiceNo`, `txtTotal`, `txtDiscount`, `txtTax`, `btnSave`, `btnPrint`, `btnDelete`.
- Strings: `اجمالي الفاتورة`, `اجمالي الشراء`, `اجمالي الشراء قبل الضريبة`, `GD` (فاتورة).

---

## 4. Side-effects

- **ZATCA table** — one row per linked tax invoice (uuid/status/hash/xml/response) (`schema_complete.sql:434-447`).
- **titanksasales / invoicedata** — sales/purchase VAT is carried through `disc`, `agel`, `totalvalue`; ETA tracks `uuid` against `titanksasales` (`modules_gap_1.md:380-395`).
- **wzgard** — each batch stores `vatvalue` + `totalwithvat` so stock can be valued incl./excl. VAT; drives COGS (تكلفة المبيعات) and profit at day close.
- **farysales** — purchase credit entry (خصوم.موردين) incl. VAT portion (`feature_purchases.md:4.2`).
- **Daily money files** — day report includes `الضريبة في المبيعات اليوم`, `الضريبة في المشتريات اليوم`, `الضريبة في المصروفات اليوم` (`ui_strings_readable.txt:1177`).
- **Saturn files** — `counter.txt` (invoice counter), `hash.txt` (hash) under `C:\saturn\zatca\computer-1\lastdata\`; invoices under `...\invoices\`; `netcounter.phy` for network counter (`modules_gap_1.md:692-711`).
- **QR files** — `\Files\qr\`, `\qr.jpg`, `C:\eta-qr\` (`zatca_complete.md:344-348`).
- **User action audit** — `TitanUserAction` for manual VAT/price/discount edits.

---

## 5. Pricing + VAT

### 5.1 Core formulas (`business_logic_complete.md:786-792`; `feature_sales_invoices.md:5`)
```
Subtotal  = Σ (Quantity × Unit Price)
Discount  = Subtotal × (SellDisc / 100)
VAT       = (Subtotal − Discount) × (VAT% / 100)     [VAT% default 15%]
Total     = Subtotal − Discount + VAT
```
Purchase mirror (`feature_purchases.md:5.4`): `Total with VAT = Subtotal − Discount + VAT`, with `costvalue`/`vatvalue`/`totalwithvat` stored per batch.

### 5.2 VAT% and rates
- Default **VAT 15%** (ضريبة 15% print template; `اجمالي ضريبة القيمة المضافة 15 بالمائة`).
- `Vat%` percentage; `Vat.No` tax invoice number (`business_logic_complete.md:939-940`).
- Configurable via VAT config screen (`FormVat` / FormVat2), GCC Gulf report, rate per country.

### 5.3 VAT-inclusive vs VAT-exclusive
- Prices can be toggled شامل الضريبة / غير شامل الضريبة (idx 11661/11662; `ui_strings_readable.txt:1360-1361,2294-2296`).
- `Price+vat` = VAT-inclusive; `Price-Vat` = VAT-exclusive (`business_logic_complete.md:1339-1340`).
- Item pricing: `ادخل السعر الرسمي الجديد لهذا الدواء شامل الضريبة` / `...غير شامل الضريبة` (`ui_strings_readable.txt:311-312`).

### 5.4 VAT operations (`business_logic_complete.md:921-933`)
- `Add or Remove Vat`, `Change Vat status`, `Change tax value`, `Change value of VAT for tax items`, `Changing tax value with final price`, `Cancellation of the vat with an increase in the price of items`, `Copy the VAT as it is to the item cards for the current invoice`, `Manually resetting the Vat value in old invoices`, `Re-apply vat on invoices`, `Reset-old-vat`.
- Arabic: `الغاء الضريبة مع رفع سعر الاصناف` (512), `تغيير قيمة الضريبة المضافة لاصناف الضريبة` (638), `اعادة ضبط قيمة الضريبة في الفوانتير القديمة يدويا` (2308), `ادخل 500 لاحتساب الضريبة او 750 لعدم الاحتساب` (2299).

### 5.5 Taxable vs exempt
- Taxable items get VAT; **non-taxable** excluded: exempt suppliers (الموردين التليين تم استثناء فواتيرهم من احتساب الضريبة idx 1210), initial stock (الجرد الاولي), معدوم (expired/damaged), unknown supplier, own branches (`feature_purchases.md:5.2,10.8`).
- Non-vatted pricing: `TttNotVatedUnit` (non-vatted unit price), `TttNotvatedAll` (non-vatted total) (`business_logic_complete.md:937-938`).
- `صافي الصنف ق الضريبة` (net item excl. tax) — `ui_strings_readable.txt:756`.

---

## 6. Payment methods
Tax-invoicing does not change the sales/purchase payment model — see `feature_sales_invoices.md:6` (كاش / فيزا / شبكة / أجل) and `feature_purchases.md:6` (سند صرف لمورد / الرصيد الافتتاحي). ZATCA/ETA JSON captures `paymentMethod` per invoice (`reports_complete.md:1253`). Purchase tax side: payment cash/visa, remainder أجـل posted to supplier payable incl. the VAT amount.

---

## 7. Printing
- Invoice print variants include **فاتورة بيع**, **فاتورة ضريبية**, **فاتورة ضريبية اجلة**, **فاتورة ضريبية مبسطة**, **فاتورة ضريبية - مرتجع**, **فاتورة محولة** (idx 12043–12050; `ui_strings_readable.txt:1404-1407`).
- Print templates show header with **tax number / رقم التسجيل الضريبي** and footer **VAT 15% / ضريبة 15%** (`feature_sales_invoices.md:7`).
- ZATCA QR printed on the receipt; `Old QR code printing` / `Best QR reader` (`zatca_complete.md:351-354`).
- VAT report prints/export via FormVat2 to ZATCA format / Excel / PDF (`reports_complete.md:563`).
- Arabic amounts rendered via **ModTafqit** (تحويل المبالغ الي كلمات عربية) on printed invoices (`zatca_complete.md:13`).
- FormDariba (وحدة الضريبة) provides the tax/duty print surface (`ui_complete.md:150`).

---

## 8. Tables

### 8.1 ZATCA (Saudi e-invoice log) — `schema_complete.sql:434-447`
```sql
CREATE TABLE ZATCA (
    id              INT IDENTITY(1,1),
    invoiceid       REAL DEFAULT 0,
    uuid            NVARCHAR(100) DEFAULT '',
    datee           REAL DEFAULT 0,
    pharmacyid      NVARCHAR(15) DEFAULT '',
    status          NVARCHAR(50) DEFAULT '',
    hash            NVARCHAR(200) DEFAULT '',
    xml             NVARCHAR(MAX) DEFAULT '',
    response        NVARCHAR(MAX) DEFAULT ''
);
```

### 8.2 wzgard (stock batch with VAT) — `schema_complete.sql` / `feature_sales_invoices.md:8`
```sql
CREATE TABLE wzgard (
    phar NVARCHAR(15) DEFAULT '', randomid NVARCHAR(50) DEFAULT '',
    writer NVARCHAR(50) DEFAULT '', datee REAL DEFAULT 0, datetimee DATETIME,
    classy NVARCHAR(35) DEFAULT '', quant REAL DEFAULT 0, expire REAL DEFAULT 0,
    price REAL DEFAULT 0, oldstock REAL DEFAULT 0,
    costvalue REAL DEFAULT 0, vatvalue REAL DEFAULT 0, totalwithvat REAL DEFAULT 0,
    typee NVARCHAR(50) DEFAULT '', drugname NVARCHAR(100) DEFAULT ''
);
```

### 8.3 invoicedata / titanksasales (invoice header+lines carrying VAT totals)
```sql
-- header: invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue
-- lines:  IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price
--         (agel/totalvalue carry the VAT-inclusive total; ETA uuid tracked against titanksasales)
```
See `feature_sales_invoices.md:8` / `feature_purchases.md:8.1` for full DDL.

### 8.4 wzdrugs (drug card `vat` %)
```sql
-- wzdrugs.vat REAL DEFAULT 0        -- VAT percentage per drug (schema_complete.sql:23)
```

### 8.5 File-based artifacts (not SQL)
- `\Files\Accounting\Vat-reports\VatFile-<date>` + `VatFile-Result.txt` (VAT report output).
- `C:\saturn\zatca\computer-1\lastdata\counter.txt` / `hash.txt`; `Files\DBI\netcounter.phy`.
- `\Files\qr\`, `C:\eta-qr\`.

---

## 9. UI strings (Arabic)

### ZATCA / e-invoice
- فاتورة ضريبية (1404) · فاتورة ضريبية - مرتجع (1405) · فاتورة ضريبية اجلة (1406) · فاتورة ضريبية مبسطة (1407)
- حالة رفع الفواتير الالكترونية (E-Invoice submission status) — `reports_complete.md:635`
- حالة ربط_eta (Egypt ETA link status) — `reports_complete.md:642`
- برجاء اكمال بيانات الفاتورة الالكترونية (10560) — "complete the e-invoice data"

### VAT computation / pricing
- شامل الضريبة / غير شامل الضريبة (11661/11662, 1360/1361, 2294/2295)
- ادخل السعر الرسمي الجديد لهذا الدواء شامل الضريبة / غير شامل الضريبة (311/312)
- ادخل 500 لاحتساب الضريبة او 750 لعدم الاحتساب (2299) · ادخل الرقم السري الخاص بتغيير الضريبة للفئات (2300)
- الغاء الضريبة مع رفع سعر الاصناف (512) · تغيير قيمة الضريبة المضافة لاصناف الضريبة (638)
- ادخل خصم بيع ثابت لكل اصناف الضريبة (316) · عمل خصم بيع لاصناف الضريبة (783)
- هل تود تعميم هذه القيمة علي كل اصناف الضريبة؟ (986)
- صافي الصنف ق الضريبة (756) · فارق الضريبة (2334) · مستحق الضريبة (2340)
- اجمالي الضريبة (1919) · اجمالي الشراء قبل الضريبة (1665)
- شراء الوحدة شامل الضريبة / قبل الضريبة (1731/1732)
- الاصناف شاملة الضريبة (475) · السعر شامل الضريبة (2294) · السعر قبل الضريبة (2295)

### VAT reporting
- تقرير الضريبة المضافة الربع سنوي (2098) — Quarterly VAT report
- تقرير ضريبة القيمة المضافة لدول الخليج العربي — GCC VAT report (`reports_complete.md:567`)
- الضريبة في المبيعات اليوم / الضريبة في المشتريات اليوم / الضريبة في المصروفات اليوم (1177)

### Purchase-tax
- الموردين التليين تم استثناء فواتيرهم من احتساب الضريبة (1210)
- تعديل قيمة اجمالي ضريبة القيمة المضافة يدويا في المشتريات · تعديل قيمة ضريبة القيمة المضافة لهذا الصنف (`feature_purchases.md:5.2`)

---

## 10. Business rules / edge cases

1. **Default VAT 15%** applied to **taxable** items on both sales and purchases; the rate is configurable and per-Gulf-country (FormVat/GCC report).
2. **Taxable vs exempt**: exempt sources (الجرد الاولي, معدوم, unknown supplier, own branches) and exempt suppliers are excluded from VAT; non-vatted pricing uses `TttNotVatedUnit`/`TttNotvatedAll`.
3. **Manual override**: total VAT on a purchase may be overridden manually and per-item (`تعديل قيمة ضريبة القيمة المضافة لهذا الصنف`).
4. **VAT add/remove price adjustment**: `Add or Remove Vat`, `Cancellation of the vat with an increase in the price of items` keeps the selling price stable by folding VAT into price.
5. **Legacy re-application**: `Re-apply vat on invoices`, `Manually resetting the Vat value in old invoices`, `Reset-old-vat` allow recomputing VAT across old invoices (`التاكد من وجود قيمة الضريبة علي سعر البيع في كل الفواتير` — `ui_strings_readable.txt:1178`).
6. **ZATCA validation** (`zatca_complete.md:547-592`): seller/buyer GLN must be 13 digits; seller deactivated blocked; product GTIN/expiry validated; AUTHORIZATION/LEGAL/MARKETING/PRODUCT_CONTROL/STATUS must not be empty.
7. **ZATCA signing** requires the Saturn companion service (`saturn.exe`), CSID via `xmlauth3.txt` + onboarding (`zatca.onboarding.form.xlsx`), UUID via `toolkit.exe`, QR via `MessagingToolkit.QRCode.dll`; signed output `signed.xml` (`Entry %1 has invalid signature`, `Failed to sign document`).
8. **Hash integrity**: `Hash Check Failed` / `HashDigestLength`; counter/hash files maintained under `C:\saturn\...\lastdata\`; `Re-start upload counter` / `Restart upcounter`.
9. **Invoice type codes** (ZATCA): `b2b-normal/b2b-credit/b2b-debit/b2c-normal/b2c-credit/b2c-debit`; internal classes include Sales, Purchases, returns, Fake-invoice, E-Invoice (`zatca_complete.md:60-90`).
10. **Egypt ETA**: submission to `api.invoicing.eta.gov.eg` (prod) / `api.preprod...` (preprod) with retry/validation (proc 7); status tracked per invoice (حالة ربط ETA).
11. **VAT reporting**: quarterly (FormVat2) and GCC (FormVat) reports compute `Net VAT Payable = VAT on Sales − VAT on Purchases`; output to `VatFile-*`; exportable to ZATCA/Excel/PDF.
12. **Permissions**: changing tax/VAT for categories requires a secret number (`ادخل الرقم السري الخاص بتغيير الضريبة للفئات`); price/VAT view/edit permission (`business_logic_complete.md:1049`).
13. **Invoice date limits**: e-receipt upload rejects invoices older than 24h (`feature_sales_invoices.md:10.12`).
14. **VAT is embedded in money reports** at day close (الضريبة في المبيعات/المشتريات/المصروفات اليوم) and in COGS/profit via `wzgard.vatvalue`.
15. **Purchase price integrity** with VAT: real vs calculated purchase price must not diverge greatly; VAT method configurable (`تعديل طريقة حساب ضريبة القيمة المضافة في فاتورة المشتريات`).

---

*Generated from TITAN.W1 VB6 P-code decompilation + extraction docs (zatca_complete.md, dtts_complete.md, schema_complete.sql, business_logic_complete.md, reports_complete.md, ui_complete.md, feature_sales_invoices.md, feature_purchases.md). Some fields may be initialized at runtime from INI/registry/DB.*
