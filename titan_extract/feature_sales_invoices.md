# فواتير مبيعات — Sales Invoices ("oot")

**Purpose:** Full extraction of the sales-invoice feature of TITAN.W1 (Phye.exe) — the point-of-sale workflow by which a customer (or "RANDOM CLIENT") is served, drugs are added by barcode/manual/name/invoice#, quantities and prices confirmed, discount and VAT applied, the invoice saved (F9), printed (FormPrintSales), and the cash drawer opened. Includes the chain-sales record (`titanksasales`), per-line invoice data (`invoicedata`), inter-pharmacy transfer (`titanin`), stock/customer/money side-effects, all invoice states (Saved / Unsaved / Un save / Copy / Transfer to sales return / Transfer to purchases), and all Arabic UI strings.

Source: `titan_decompile/` (strings_utf16.txt, strings_readable.txt, pcode_disasm.txt), reused from `business_logic_complete.md` (§6, §16), `schema_complete.sql`, `reports_complete.md`, `ui_complete.md`, `raz_complete.md`.

---

## 1. Objects

### 1.1 Core modules / forms (from `pcode_strings.py names`, `ui_forms.json`)

| Object | Type | Procs | Role |
|---|---|---|---|
| **ModOot** | Module | 105 | Core sales/outbound engine (data structure, validation, returns, discount types). pcode start ~line 2813. |
| **FFFOUTPut** / **FFFOutPut** | MDIForm | 278 | Main output/reporting MDI parent — hosts the sales screens and shared sales logic. |
| **FFFStartUp** | Form | 252 | Application startup; contains the live chain-sales GUID (`a2a100e1-906b-44df-99c2-6e7c6098421e`, idx 7423) used 3,564× in the `titanksasales` insert loop, plus the `titanksasales`/`titaninn` insert templates. |
| **FormSellTime** | Form | 9 | Sales timing (وقت البيع) — time-of-day for sales entries. |
| **FormPrintSales** | Form | 17 | Sales printing — prints sales invoices/receipts (reports_complete). |
| **FormInvoiceTrackEditing** | Form | 4 | Invoice edit tracking — logs modifications to sales invoices (reports_complete RPT-SP03). |
| **FormReadArcOot** | Form | 9 | Read archived output (قراءة المبيعات المؤرشفة) — reads archived sales invoices. |
| **FFFOOTQuant** | Form | 20 | Sales quantity/expiry selection model (نموذج FFFOOTQuant). |
| **FFFoutPutVertual** | Form | 10 | Virtual output — offline/queued sales. |
| **ModOOTTrans** | Module | 1 | Output transactions — currently an empty stub (only ExitProc). |
| **FormootThisDay** | Form | 11 | Output this day (اخراج اليوم / فواتير مبيعات اليوم) — today's invoices. |
| **FormOotSum** | Form | 9 | Output summary (ملخص الاخراج) — sales summary, data source `invoicedata`. |
| **FormLastEdited** | Form | 10 | Last edited drugs (اخر الادوية المعدلة يدويا) — reports RPT-D05. |
| **ModOuterConnections** | Module | 18 | External connections / network integration (api_integration). |
| **Modfarynet** | Module | 2 | FaryNet network protocol (branch sales sync). |
| **FormFaryNet** | Form | 8 | FaryNet network form — remote branch sales monitoring. |

### 1.2 Key live strings by index

| idx | String | Meaning |
|---|---|---|
| 7423 | `a2a100e1-906b-44df-99c2-6e7c6098421e` | Live chain-sales GUID — used 3,564× in the `titanksasales` insert loop in FFFStartUp/FFFOutPut. |
| 8019 | `invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue ) values (` | `titanksasales` column list for INSERT. |
| 4935 | `F9=Save  ,  F12 = Unsave` | Save / Unsave shortcut keys. |
| 6263 | `Save - Unsave` | Toggle. |
| 9092 | `ادخل 800 لتحويل الفاتورة الي مبيعات ... او 600 لتحويلها الي مرتجع مبيعات` | Conversion prompt: 800=sales, 600=sales-return. |
| 12045 | `فاتورة ضريبية -  مرتجع` | Tax invoice label — return variant. |

---

## 2. Step-by-step workflow

From `business_logic_complete.md` §16.1 (sales flow) expanded with string evidence:

1. **Customer selection** — pick an existing customer (بحث عن عميل) or use **RANDOM CLIENT** (بيع لغير العملاء). The sales screen shows the customer's current debt (مديونية العميل) and monthly draw rate; debt is computed including the current unsaved invoice (idx 8925).
2. **Drug search / add** — one of:
   - Barcode reader (اضافة دواء بواسطة قارئ الباركود / "Add an item by barcode reader")
   - Manual search (الباحث اليدوي / "Add an item by Manual search")
   - Trade name search ("Search by trade name")
   - Invoice number search (بحث برقم الفاتورة; entering `50000` jumps to last sales invoice, idx 10125)
3. **Quantity entry** — using the quantity/expiry selection bar (شريط تحديد الكمية والصلاحية / FFFOOTQuant). Expiry must be chosen first (اختر تاريخ الصلاحية اولا, idx 1056). Quantity must be > 0. Unit-selection supports retail units (الوحدة الوسطي) vs whole packs (idx 10433, 12391).
4. **Price verification** — price confirmed against the drug card; abnormal price/discount triggers warnings (سعر احد الاصناف غير منطقية idx 11659; "Abnormal Discount").
5. **Discount** — per-item SellDisc and/or whole-invoice discount (ادخل نسبة خصم علي اجمالي الفاتورة idx 9086; discounts applied via قائمة خصم).
6. **VAT** — computed per §5 below; tax-tag `<masrofat-vat>` is live.
7. **Save (F9)** — `F9=Save`; auto-print option (طباعة الفاتورة تلقائيا مع الحفظ). Cannot print an unsaved invoice (لا يمكن طباعة فاتورة غير محفوظة).
8. **Print** — FormPrintSales; templates in reports_complete §3.1 (A4/A5 sales invoice).
9. **Drawer open** — optional on print (فتح الدرج عند الطباعة, reports_complete config item 25).

Saving is a two-phase commitment: the invoice is stored as a chain-sales record (`titanksasales`) via the GUID insert loop, and per-line data via `invoicedata` / the `titanksasales` + `titanin` flows, while stock is decremented in `wzgard` and money recorded in the daily files.

---

## 3. Fields / data captured

### 3.1 Sales line data (ModOot structure + `invoicedata`)

```
(IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price)
```
- `invoiceid` — invoice number (REAL)
- `IdDateTime` — item entry timestamp (DATETIME)
- `Quant` — quantity sold
- `DrugName` — FK to `wzdrugs`
- `SellDisc` — sale discount percent
- `Tips` — notes/comments
- `Expire` — expiry date of the sold batch (VB6 serial REAL)
- `Minimum` — minimum stock at time of sale
- `price` — unit price

### 3.2 Chain-sales record (`titanksasales`) — the live GUID insert

```
invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue
```
- `invoiceid` — invoice number (REAL, unique)
- `datee` — date (REAL, VB6 serial)
- `silsilaid` — chain/series ID (NVARCHAR 15)
- `pharmacyid` — pharmacy ID (NVARCHAR 15)
- `payed` — amount paid (REAL)
- `disc` — total discount (REAL)
- `agel` — deferred/credit (أجل) portion (REAL) — also called type/age
- `totalvalue` — invoice grand total (REAL)

### 3.3 Invoice header fields (business_logic §6.1)

- `PharmacistTel` — pharmacist identifier
- Customer (or RANDOM CLIENT), writer/كاتب الفاتورة, datee/time, invoice #.

### 3.4 Form-level fields

- Customer selector + current debt + credit limit (حد ائتمان)
- Writer (كاتب الفاتورة) selector — multiple simultaneous users (idx 10454)
- Payment fields: مدفوع نقدا / مدفوع فيزا / اجل (cash / visa / credit)
- Qty+expiry bar, price, SellDisc, VAT, total.

---

## 4. Side-effects

On save of a sales invoice the following change:

- **Stock (`wzgard`)** — batch quantity `quant` decremented; `oldstock` records prior stock; `typee` = sale. Stock check before allowing ("Not Enouph Stock"); sales with insufficient stock blocked by default (منع البيع إذا كان الرصيد غير كاف), configurable in advanced settings.
- **Customer balance (`wzcustomers`)** — for credit (أجل) sales, customer debt increases; for cash customers full payment required (هذه الفاتورة لعميل نقدي ويجب ان يكون الدفع بكامل المبلغ idx 13133). Customer debt auto-updates from sales screen (تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات idx 10712).
- **Money / daily (`wzmony`-equivalent)** — cash added to the drawer (قبض); credit/debit flag recorded. Money is stored in serialized daily files (`Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`) rather than SQL (strings_readable 6735–6777, 6748). Daily totals include: كاش / كاش يدوي / شبكة / شبكة يدوي / محسوب المبيعات / تكلفة مبيعات اليوم / ربح اليوم / خصومات اليوم / ضريبة المبيعات اليوم / حركة مالية (idx 9883).
- **Chain record (`titanksasales`)** — one row per invoice via the GUID insert loop.
- **Per-line invoice data (`invoicedata`)** — one row per sold drug.
- **ZATCA (`ZATCA`)** — tax invoice logged when linked to Zakat/Tax authority (فاتورة ضريبية).
- **User action audit (`TitanUserAction`)** — writes `INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)`.

Reverse side-effects occur on **Transfer to sales return** (see `feature_sales_returns.md`).

---

## 5. Pricing + VAT

From `business_logic_complete.md` §16.4:

```
Subtotal      = Σ (Quantity × Unit Price)
Discount      = Subtotal × (SellDisc / 100)
VAT           = (Subtotal − Discount) × (VAT% / 100)
Total         = Subtotal − Discount + VAT
```

- VAT default 15% (ضريبة 15% in print template). VAT tag `<masrofat-vat>` is a live reference.
- Prices can be displayed شامل الضريبة (incl. VAT) or غير شامل الضريبة (excl. VAT) — idx 11661, 11662.
- `Total VAT` = ضريبة ق مضافة Total VAT.
- Discount types (business_logic §6.4): Disc in (input), Disc out (output), cash discount, wholesale discount, tax-item sale discount.
- SellDisc cannot be zero — `لا يمكن ان يكون خصم البيع مساويا لصفر استخدم 1 او اعلي` (idx 12386); must be ≥ 1 if any discount intended.
- "Abnormal Discount" detection for outlier discounts.
- Staff can have per-user max sale-discount (وضع حد اقصي لعمل خصم بيع لكل موظف idx 13251).

---

## 6. Payment methods

Payment split across: **cash (كاش / نقدا)** · **visa/network (فيزا / شبكة)** · **credit/أجل (اجل)**.

- `payed` = cash+visa paid portion; `agel` = deferred (أجل) portion; `totalvalue = payed + agel` (idx 13344: `يجب ان يكون مجموع الاجل والمدفوع مساويا لسعر الفاتورة`).
- Strings: `اجمالي المدفوع فيزا اليوم` (idx 8969), `اجمالي الاجل اليوم` (8950), `اجل العملاء` (8947), `المتبقي في الاجل` (10280), `قيمة الاجل` (12225).
- **Credit (أجل) requires permission** — `لا تملك صلاحية البيع الاجل ...` (idx 1117). Permission granted per-user from تعديل اعدادات العاملين; `السماح بالبيع الاجل` (idx 10043).
- Cash/network splitting: `مسدد نقدا مبيعات` / `مسدد شبكة مبيعات` (reports_complete RPT-P04/P05 pattern).
- On credit sale exceeding customer credit limit — invoice cannot be saved (idx 8968: `اجمالي المتبقي من هذه الفاتورة ومديونية هذا العميل اكبر من الحد الائتماني ... فلا يمكن حفظ الفاتورة`).
- Payment entry allows entering what the patient paid to compute change (idx 12527: `ادخل ما دفعه المريض ليتم حساب الباقي بعد خصم قيمة الفاتورة`).
- Payment may be made on an empty invoice by filling it with a phantom 1-piaster item (idx 13354).
- Error check: `خطأ في حسابات هذه الفاتورة من فضلك راجع قيم المدفوع والاجل` (idx 11466).

---

## 7. Printing

**Form:** FormPrintSales (17 procs). Config in reports_complete §4.

- Invoice templates (A4/A5) per reports_complete §3.1: header (pharmacy name/address/phone/tax number/commercial registration), invoice # + date, customer, employee, payment type (□ Cash □ Credit □ Card), items grid (#, drug, qty, unit price, batch, expiry, disc, VAT, line total), footer (subtotal, discount, after discount, VAT 15%, total, paid, remaining, customer credit status), barcode, writer.
- Variants: `فاتورة بيع`, `فاتورة ضريبية`, `فاتورة ضريبية اجلة`, `فاتورة ضريبية مبسطة`, `فاتورة ضريبية - مرتجع`, `فاتورة محولة` (idx 12043–12050).
- Cash receipt (سند قبض) and disbursement receipt (سند صرف) layouts (reports_complete §3.2/3.3).
- Auto-print on save (طباعة الفاتورة تلقائيا مع الحفظ idx 11743; config `طباعة تلقائية` item 22).
- Drawer open on print (config item 25).
- Cannot print unsaved invoice (idx 12416).
- Barcode printing per-item and A4 6×24 label sheets (reports_complete §3.4).
- `تم ارسال الفاتورة الي الطابعة` (idx 11007).
- Delivery note / وصفة طبية template (§3.6).

---

## 8. Tables

From `schema_complete.sql`. Sales-invoice feature touches:

```sql
-- Chain sales master (live GUID insert):
CREATE TABLE titanksasales (
    id              INT IDENTITY(1,1),
    invoiceid       REAL  DEFAULT 0,      -- invoice number (unique)
    datee           REAL  DEFAULT 0,      -- date (VB6 serial)
    silsilaid       NVARCHAR(15) DEFAULT '',
    pharmacyid      NVARCHAR(15) DEFAULT '',
    payed           REAL  DEFAULT 0,      -- paid (cash+visa)
    disc            REAL  DEFAULT 0,      -- total discount
    agel            REAL  DEFAULT 0,      -- deferred (أجل)
    totalvalue      REAL  DEFAULT 0       -- grand total
);

-- Per-line invoice data:
CREATE TABLE invoicedata (
    id              INT IDENTITY(1,1),
    invoiceid       REAL  DEFAULT 0,
    datee           REAL  DEFAULT 0,
    silsilaid       NVARCHAR(15) DEFAULT '',
    pharmacyid      NVARCHAR(15) DEFAULT '',
    payed           REAL  DEFAULT 0,
    disc            REAL  DEFAULT 0,
    agel            REAL  DEFAULT 0,
    totalvalue      REAL  DEFAULT 0,
    IdDateTime      DATETIME,             -- item entry timestamp
    Quant           REAL  DEFAULT 0,      -- quantity
    DrugName        NVARCHAR(100) DEFAULT '',
    SellDisc        REAL  DEFAULT 0,      -- sale discount
    Tips            NVARCHAR(50)  DEFAULT '',
    Expire          REAL  DEFAULT 0,      -- expiry
    Minimum         REAL  DEFAULT 0,
    price           REAL  DEFAULT 0       -- unit price
);

-- Inter-pharmacy transfer / chain (titanin) — insert template:
--   insert into titaninn (fatid,itemsasstring,datee,source,silsilaid,target) VALUES (...)
CREATE TABLE titaninn (
    id              INT IDENTITY(1,1),
    fatid           INT           DEFAULT 0,      -- fat (group) ID
    itemsasstring   NVARCHAR(4000) DEFAULT '',    -- serialized items
    datee           INT           DEFAULT 0,
    source          NVARCHAR(100) DEFAULT '',     -- source pharmacy
    silsilaid       NVARCHAR(15)  DEFAULT '',
    target          NVARCHAR(100) DEFAULT ''      -- target pharmacy
);

-- Stock batch (decremented on sale):
CREATE TABLE wzgard (
    phar        NVARCHAR(15)  DEFAULT '',
    randomid    NVARCHAR(50)  DEFAULT '',   -- unique batch
    writer      NVARCHAR(50)  DEFAULT '',   -- user
    datee       REAL          DEFAULT 0,    -- date (VB6 serial)
    datetimee   DATETIME,
    classy      NVARCHAR(35)  DEFAULT '',   -- category
    quant       REAL          DEFAULT 0,    -- quantity
    expire      REAL          DEFAULT 0,    -- expiry
    price       REAL          DEFAULT 0,
    oldstock    REAL          DEFAULT 0,    -- previous stock
    costvalue   REAL          DEFAULT 0,    -- cost value
    vatvalue    REAL          DEFAULT 0,    -- VAT value
    totalwithvat REAL         DEFAULT 0,    -- total with VAT
    typee       NVARCHAR(50)  DEFAULT '',   -- type (e.g., purchase, return, sale)
    drugname    NVARCHAR(100) DEFAULT ''    -- FK to wzdrugs
);

-- Customer (debt changes on credit sales):
CREATE TABLE wzcustomers (
    randomid    NVARCHAR(50)  DEFAULT '',
    phar        NVARCHAR(15)  DEFAULT '',
    typee       NVARCHAR(50)  DEFAULT '',
    writer      NVARCHAR(50)  DEFAULT '',
    creditlimit REAL          DEFAULT 0,    -- credit limit
    datee       REAL          DEFAULT 0,
    namee       NVARCHAR(100) DEFAULT ''
);

-- Tax invoice log:
CREATE TABLE ZATCA (
    id              INT IDENTITY(1,1),
    invoiceid       REAL          DEFAULT 0,
    uuid            NVARCHAR(100) DEFAULT '',
    datee           REAL          DEFAULT 0,
    pharmacyid      NVARCHAR(15)  DEFAULT '',
    status          NVARCHAR(50)  DEFAULT '',
    hash            NVARCHAR(200) DEFAULT '',
    xml             NVARCHAR(MAX) DEFAULT '',
    response        NVARCHAR(MAX) DEFAULT ''
);
```

**Live insert templates (strings_readable):**
- `insert into titanksasales (` (line 719) → columns `invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue ) values (` (idx 8019)
- `insert into titaninn (fatid,itemsasstring,datee,source,silsilaid,target)VALUES (` (line 718)
- `select invoiceid from titanksasales where ...` (line 781), `update titanksasales set ...` (806)
- `select * from farysales where mobile = N'` (line 764) — branch sales
- `select * from titaninn where source/target = N'` (765–766) — transfer lookup

Money/daily data is file-based (`.phy`): `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`, `usersmony.phy` (strings_readable 6735–6854).

---

## 9. UI strings (Arabic)

### 9.1 Buttons / actions
- حفظ الفاتورة (11378) · حفظ-الغاء الحفظ (11388) · حفظ/الغاء الحفظ (11389)
- الغاء الحفظ (10130) · F9=Save, F12=Unsave (4935)
- نسخ الفاتورة (13005) · نسخ الفاتورة الي فاتورة بيع (13007) · نسخ الفاتورة الي فاتورة ارتجاع بيع (13006)
- تحويل الفاتورة الي صيدلية اخري (10770) · تم تحويل الفاتورة (11072)
- حذف الدواء من الفاتورة (11333) · حذف الفاتورة (11335) · حذف كامل الفاتورة (11340) · حذف محتويات الفاتورة فقط (11344)
- طباعة الفاتورة الحالية علي شكل فاتورة بيع (11889) · طباعة الفاتورة تلقائيا مع الحفظ (11890)
- بحث برقم الفاتورة (10526) · بيع لغير العملاء (بيع لغير العملاء)
- عرض مديونية العميل (تلقائيا اثناء اضافة الاصناف)

### 9.2 Column headers
- `رقم الفاتورة   التاريخ   قيمة الفاتورة    الضريبة    مدفوع نقدا    مدفوع شبكة    اجل    المورد   الفرع` (11562)
- `فاتورة   رقم   اسم الصنف   الكمية   سعر   خصم   اجمالي   عميل   مستخدم   تاريخ` (12041)
- `رقم الفاتورة-الاصناف الاولي من الفاتورة-الاجمالي-الضريبه-العدد` (11569)
- `مسلسل   تاريخ   سعر رسمي   سعر بيع   مدفوع كاش   مدفوع فيزا   اجل   عميل` (12798)

### 9.3 Errors / confirmations
- `لا تملك صلاحية البيع الاجل ...` (1117)
- `خطأ في حسابات هذه الفاتورة من فضلك راجع قيم المدفوع والاجل` (11466)
- `هذه الفاتورة محفوظة ولا تقبل التعديل ... الغاء الحفظ اولا ...` (13135)
- `هذه الفاتورة لعميل نقدي ويجب ان يكون الدفع بكامل المبلغ` (13133)
- `هذه الفاتورة لغير العملاء ويجب ان يكون الدفع بكامل المبلغ` (13134)
- `لا يمكن طباعة فاتورة غير محفوظة` (12416)
- `لا يمكن حذف فاتورة محفوظة` (12413) · `لا يمكن حذف اول فاتورة` (12412) · `يجب ان تكون الفاتورة المراد حذفها هي اخر فاتورة` (13331)
- `لا يمكن ان يكون خصم البيع مساويا لصفر استخدم 1 او اعلي` (12386)
- `فشل حفظ الفاتورة برجاء التوجه للمبيعات وحفظها` (12075)
- `برجاء اكمال بيانات الفاتورة الالكترونية` (10560)
- `تم ارسال الفاتورة الي الطابعة` (11007)

---

## 10. Business rules / edge cases

1. **Stock check** — `Not Enouph Stock`; by default sales are blocked if stock insufficient; the user can enable negative-stock selling in advanced settings (idx 10457, 10606, 13412).
2. **Expiry check** — cannot sell expired products ("Any product cannot be sold to the person registered as dead"); `بعض الادوية الموجودة في الفاتورة منتهية الصلاحية` (10607).
3. **Prohibited drugs** — `Drugs prohibited for sale` / `هذا الصنف ممنوع بيعه ...` (13084); block barcode from usage (idx 4096).
4. **Price sanity** — "Abnormal Discount", `سعر احد الاصناف في هذه الفاتورة غير منطقية` (11659), `قيمة غير طبيعية لهذه الفاتورة ...` (12245/12246), `كميات احد الاصناف غير منطقية` (12318).
5. **Invoice number uniqueness** — must be unique.
6. **Save/Unsave (F9/F12)** — a saved invoice cannot be edited except by its writer on the same day after Unsave; unsave permission limited to the writer or the manager (12377, 13125/13126, 13135); unsave of old invoices disabled for safety (12628).
7. **States** (idx 6781, 6280, 6263): `Saved`, `Unsaved`, `Unsave`, `Copy` (Copy me to another location 4403 / Copy the invoice to sales invoice 4407), `Transfer to purchases` (6711), `Transfer to a transferred invoice` (6709), `Transfer to sales return` (نسخ الفاتورة الي فاتورة ارتجاع بيع 13006 / تحويل الفاتورة الي مرتجع مبيعات 12929).
8. **Conversion prompt** — `ادخل 800 لتحويل الفاتورة الي مبيعات ... او 600 لتحويلها الي مرتجع مبيعات` (9092): 800 → sales, 600 → sales-return.
9. **Credit limit** — invoice with agel that pushes customer debt over credit limit cannot be saved (8968).
10. **Change computation** — `ادخل ما دفعه المريض ليتم حساب الباقي` (12527).
11. **Multi-user** — multiple users can build sales invoices simultaneously; each has a writer; adding an item to another's invoice can be prevented (12962).
12. **Deadline** — invoice date/time beyond 24h of creation invalid for e-receipt upload (10695/10696).
13. **Batch/expiry selection** — expiry must be selected first; supports local barcode / QR / DataMatrix (9485, 9405).
14. **Archiving** — old sales invoices archived (أرشفة المبيعات القديمة 8899); active sales invoices kept < 50k (12492).
15. **Barcode duplicate** — duplicate international barcode prevented (1143, 8909, 9399).
16. **Wholesale/retail** — wholesale systems sell at purchase-discount margin (13289); retail uses unit price for divisible units (10433).
17. **Offers/campaigns** — offers apply automatically on invoices with offer items (11711); group/selling groups (مجموعة بيعية 12703).
18. **Drawer math** — drawer = cash sales − cash returns + customer settlements, excluding intraday disbursements (idx 12675, 8956).
