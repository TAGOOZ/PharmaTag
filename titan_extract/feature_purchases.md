# TITAN.W1 — Feature: المشتريات (Purchases / Purchase Invoices)

**App:** TITAN.W1 (Phye.exe, VB6 p-code)
**Arabic name:** المشتريات / الشراء / الوارد (Purchases / Buying / Incoming)
**Purpose:** Record incoming drug stock from suppliers, track purchase cost, apply purchase discount & VAT, record payment (cash/visa/credit/agel), update stock upwards, and increase the supplier's payable (دائن / مستحقات) balance. Purchases are the mirror image of sales ("oot"/output); purchases are the "input" (وارد / شراء) side.
**Sources reused:** `schema_complete.sql`, `schema_complete.md`, `business_logic_complete.md`, `raz_complete.md`, `reports_complete.md`, `ui_complete.md`, `modules_gap_1.md`, `modules_gap_2.md`, `strings_utf16.txt`, `strings_readable.txt`.

---

## 1. Objects (Modules / Forms / Procedures)

### 1.1 Modules
| Module | Role | Evidence |
|--------|------|----------|
| `ModInn.bas` | **Purchase/inbound module** (71 procs). All purchase invoice processing, header/line writes, stock & financial side-effects. | `pcode_disasm.txt` ~line 2918+; procs at `@0x0099ee80` … `@0x009fa5b8` etc. |
| `ModStock.cls` | Stock side-effect: adds purchased quantity to `wzgard` / `titanksastock` / `titanstock`. | `business_logic_complete.md` §4 |
| `ModMony.bas` / `ModOot.bas` | Financial recording (cash/visa/agel), payable ledger updates. | `business_logic_complete.md` §6/§10 |
| `ModPrint.bas` | Purchase invoice printing (thermal/A4). | `raz_complete.md` §3.8 |
| `Raz.bas` | Shared helpers: `ReloadCurent500Inn` (load first 500 purchase items), `Titan ReCalculate_By_Value_inn`, `AutoId=`, `SilsilaId=`. | `pcode_strings.py search`; `english_purchase_strings.txt:122,616` |
| `ModTitanCloud` | Export purchase invoices to another pharmacy / cloud. | `arabic_purchase_strings.txt` "تحسين تصدير فاتورة مشتريات الي صيدلية اخري" |

### 1.2 Purchase screens (Forms)
| Form | Arabic | Role | Evidence |
|------|--------|------|----------|
| `FFFINPut` (MDI parent, 173 procs) | المشتريات | **Main purchase invoice MDI screen** — item entry, totals, save. | `ui_complete.md:125` |
| `FFFWaredMonsaref` (36 procs) | المونسرف / المستودع | Supplier/warehouse & supplier-settings management screen. | `ui_complete.md:102`; `modules_gap_2.md` |
| `FFFINNquant` / `FFFINNquantEG` | كميات المشتريات | Purchase quantity entry (incl. Egypt/E-invoice variant). | `raz_complete.md:830` |
| `FormInnSetVatAct` | ضريبة المشتريات | Set purchase VAT activation. | forms listing |
| `FormInnSum` | ملخص المشتريات | Purchase summary. | forms listing |
| `FormShiftInput` | شفت المشتريات | Shift (work-period) purchase records. | `ui_complete.md` |
| `FormInputtakarirSpeed` / `FFFInputTakarir` | تقارير المشتريات | Purchase report configuration/display. | `reports_complete.md:201` |
| `FormReadArcInn` | قراءة المشتريات المؤرشفة | Read archived purchase invoices. | `pcode` procs |
| `FormLiveBuyInfo` | معلومات الشراء المباشر | Live purchase info. | `ui_complete.md:124` |
| `FormChainBuy` / `FormChainBuyList` | سلسلة المشتريات | Chain/purchase series grouping. | `modules_gap_2.md` §3 |
| `FormOrder` / `FormOrderList` / `FormAutoOrder` / `FormNeedsAll` | أوامر/نواقص | Purchase orders to suppliers. | `modules_gap_2.md` |
| `FormImportFat` / `FormExportFat` / `FormGetFats` | استيراد/تصدير فواتير | Import/export purchase invoices. | `modules_gap_2.md` |
| `FormWared` / `FormWaredList` (legacy not in project) | الوارد / قائمة المشتريات | Legacy purchase entry/list. | `modules_gap_2.md` §72/73 |
| `FormArchiveBuy` / archive | أرشفة المشتريات القديمة | Archive old purchase invoices. | `modules_gap_2.md` §X |
| `FormPrintSales` | الطباعة | Shared invoice printing host (purchase print reuses print engine). | `business_logic_complete.md` |
| `ModTamin` / `FormTamin` | تأمين | Insurance-company purchases/claims (suppliers that are insurers). | `ui_complete.md` |

### 1.3 Key purchase logic procedures (Raz.bas / ModInn)
From `raz_complete.md` §3.2 (purchase logic) and §3.6/3.7/3.8:

| Address | Function |
|---------|----------|
| `@0x009c37b0` | Purchase invoice processing — main purchase workflow |
| `@0x009909d0` | Purchase item addition — adds drugs to purchase invoice |
| `@0x0097a07c` | Purchase total calculation |
| `@0x0095a100` | **Purchase stock update** (adds qty to stock) |
| `@0x0094c62c` | Purchase price update (cost) |
| `@0x00956178` | Purchase expiry date handling |
| `@0x0094a058` | Purchase invoice finalization |
| `@0x00949e78` | **Purchase return processing** |
| `@0x0093404c` | Purchase discount application |
| `@0x00938fd4` | **Purchase VAT calculation** |
| `@0x0093d948` | **Purchase payment processing** |
| `@0x0096d944` | Report generation — purchase reports |
| `@0x009644fc` | Report generation — supplier reports |
| `@0x0092ffd0`→`@0x00922c04` | (Sales price/stock/expiry — mirrored by purchases) |

---

## 2. Step-by-step workflow

1. **Open the purchase screen** (`FFFINPut`). From the main menu: *قائمة مشتريات → فاتورة مشتريات* (Purchases menu → Purchase invoice).
2. **Choose invoice type** — three states of purchase invoices (فواتير الشراء): **مشتريات** (purchase), **مرتجع مشتريات** (purchase return), **مرتجع الاكسبير** (expired-items return). File → *فاتورة مرتجع جديدة*. (`arabic_purchase_strings.txt:13445`)
3. **Select supplier (المورد)** — required first ("برجاء اختيار المورد اولا"). Dropdown lists suppliers; default option is **الشراء من غير الموردين** (purchase from non-suppliers / walk-in vendor). Also supports **الجرد الاولي** (initial stock) and **مورد غير معروف** (unknown supplier) as special supplier entries.
4. **Search/enter drugs** — by barcode reader, name, or list. Optionally "اختيار اخر صلاحية تم الشراء بها" (apply last-purchase expiry to current items) and "تطبيق خصم اخر شراء" (apply last purchase discount).
5. **For each item enter:** quantity (الكمية), purchase price (سعر الشراء — real or calculated), buy discount (خصم الشراء), expiry date (تاريخ الصلاحية), batch/serial (رقم التشغيلة / السيريال), VAT.
6. **VAT / totals** auto-calculate: cost value (تكلفة), VAT value (ضريبة), total with VAT (إجمالي شامل الضريبة). Total VAT may be manually overridden.
7. **Payment (المدفوع)** — enter amount paid cash (مدفوع نقدا), paid by network/visa (مدفوع شبكة), and the remainder becomes **أجل (credit / payable)**. Choose treasury source (خزينة الدرج or خزينة الصيدلية).
8. **Save invoice (F9)** — validates, writes header + line items, **adds qty to stock**, **increases supplier payable (مستحقات المورد / دائن)**.
9. **Print** the invoice (optional / auto-print on save setting). Open drawer if configured.
10. Stock and supplier balances are updated automatically from the purchases screen ("تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات").

### Fast keys / transfers
- F9 save, F12 unsave. Open a new invoice, or reach last purchase invoice.
- **تحويل الي مشتريات** (transfer sales → purchases), **تحويل الي مرتجع مشتريات** (→ purchase return). After a day is closed, an invoice can only be copied to a purchase-return invoice (cannot be unsaved).
- More than one purchase invoice can be open simultaneously.

---

## 3. Fields / data captured

### 3.1 Purchase invoice header (`invoicedata` — invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue)
| Field | Source column | Meaning |
|-------|---------------|---------|
| invoiceid | `invoiceid` | Purchase invoice number (auto, unique) |
| datee | `datee` | Date (VB6 serial) |
| silsilaid | `silsilaid` | Chain/series ID (links related purchase invoices) |
| pharmacyid | `pharmacyid` | Branch/pharmacy |
| payed | `payed` | Amount paid (cash+visa) |
| disc | `disc` | Discount |
| agel | `agel` | **Age/type discriminator** — for purchases stores the payable/credit remainder and/or invoice type; mirrors sales `agel`. |
| totalvalue | `totalvalue` | Invoice total (with VAT) |

### 3.2 Purchase line items (invoicedata line columns, mirror of `titanksasales`)
`IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price` (`business_logic_complete.md` §2.2/§5):
- `Quant` — quantity purchased
- `DrugName` — drug
- `SellDisc` — buy/purchase discount % (on purchase the field stores خصم الشراء)
- `price` — unit purchase price (cost)
- `Expire` — batch expiry date
- `Tips` — notes (batch no / serial)
- `IdDateTime` — item entry timestamp
- `Minimum` — minimum

### 3.3 Form-level purchase fields (screen)
- Supplier (المورد) + its current dues (مستحقات المورد)
- Item grid: الصنف | سعر | الرصيد | عدد شهري | قيمة شهرية | اخر شراء (drug, price, stock, monthly qty, monthly value, last purchase)
- Invoice fields: الفاتورة | الشفت | المستخدم | القيمة | المخصوم | شراء | الاجل | المدفوع
- Header summary: رقم الفاتورة | التاريخ | قيمة الفاتورة | تكلفة الفاتورة | الضريبة | مدفوع نقدا | مدفوع شبكة | اجل | الفرع (`strings_readable.txt:10895-10896`)
- **سعر الشراء الحقيقي** (real purchase price) and **سعر الشراء الحسابي** (calculated purchase price)
- **شراء الوحدة قبل الضريبة** (unit purchase before tax) / **شراء الوحدة شامل الضريبة** (unit purchase with tax)
- Invoice writer (كاتب الفاتورة), treasury source (خزينة الدفع: الدرج / خزينة الصيدلية)
- Supplier type selection: مورد (supplier), شركة (company), فرد (individual), شركة تامين (insurance company)

### 3.4 Supplier master (`companies`, `wzcustomers`)
- `companies` table: `mobile` (PK), `pass` — the supplier's registration/ID.
- `wzcustomers` table (supplier/customer accounts): `randomid, phar, typee, writer, creditlimit, datee, namee` — **`typee` distinguishes supplier vs customer**; `namee` = supplier name; `creditlimit` = allowed credit.
- Supplier settings screen (`FFFWaredMonsaref`) fields: supplier name, bank account (ادخل الحساب البنكي للمورد), opening balance of dues (ادخل الرصيد الافتتاحي لمستحقات الموردين), unified purchase discount (ادخل خصم شراء موحد), importer discount (ادخل خصم المستورد لهذه الشركة), tax registration no. / cloud link (ادخل رقم التسجيل الضريبي او رقم الربط السحابي اذا كان المورد صيدلية), supplier GLN (Inpu GLN for this supplier).
- Add new supplier: قائمة رئيسية → الموردين → إضافة مورد جديد.

---

## 4. Side-effects

### 4.1 Stock — `wzgard` (ADD on purchase, SUBTRACT on return)
Purchases write a stock-batch row and **add** the quantity to stock:
```
insert into wzgard (phar,randomid,writer,datee,datetimee,classy,quant,expire,price,oldstock,costvalue,vatvalue,totalwithvat,typee,drugname) values ( ... )
```
- `typee` indicates the movement direction/kind (purchase = in; purchase-return = out). `oldstock` records the prior stock, `costvalue`/`vatvalue`/`totalwithvat` record the cost & tax so stock can be valued at cost.
- The `titanksastock`/`titanstock` drug-card `stock` field is **incremented** by the purchased quantity (`raz_complete.md` §5.2 rule 4: "Add purchased quantity to current stock; update stock by batch/serial number; consider invoice as correct stock and inventoried").
- Purchases also set/update the drug card's **cost / unitcost** (wzdrugs2.unitcost is computed from wzgard) and the last purchase price.
- **الجرد الاولي** (initial stock) is entered through the purchase screen as a special "supplier".

### 4.2 Supplier payable (money) — دائم / مستحقات المورد
- A purchase creates a **credit (دائن / payable)** to the supplier: accounting path `خصوم.خصوم متداولة.موردين` (Liabilities → Current Liabilities → Suppliers). This **increases مستحقات المورد / مستحقات الشركات**.
- Recording entry uses the `farysales` accounting table: `(mobile,grand,father,son,datee,datetimee,dateemanual,monthe,yearo,payed,creditdebit,typee,phar,randomid,tips,writer,classy)` — with `creditdebit` = 'credit'/'debit' and `father/son` = the accounting-tree path (خصوم.موردين).
- Paying a supplier reduces the payable: **سند صرف لمورد** (payment voucher to supplier), "دقع مستحقات الشركات والمخازن", "تسديدات المشتريات", "خروج نقدية نتيجة الدفع للشركات". Opening payable is entered as "الرصيد الافتتاحي لمستحقات الموردين" (opening dues, افتتاحي دائن).
- Purchases payment draws from the **drawer** (الدرج) or **pharmacy treasury** (خزينة الصيدلية): "شاشة المشتريات اصبحت تتعامل مع خزينة الدرج فقط مع امكانية ترحيل نقدية من الخزينة".

### 4.3 Money in/out summary
- `وارد` (in) / `صادر` (out) cash and network columns appear in financial/day reports; purchases contribute to "مشتريات اليوم" (today's purchases), "الضريبة في المشتريات اليوم" (VAT in today's purchases), "تكلفة المبيعات" (cost of goods — derived from purchase cost).
- Cash is **expensed** (تخرج من الدرج) when a purchase is paid in cash; network/visa paid purchases reduce network (شبكة) balance.

### 4.4 Other side-effects
- Updates `storediscount` (per-item purchase discount history) — `insert into storediscount (...)`.
- Updates drug card `PriceNow`/cost if purchase price differs; "تم تحديث اسعار قاعدة بيانات الادوية من اخر 100/400 فاتورة شراء".
- Purchase price is used to compute **تكلفة المبيعات (COGS)** and **الربح** (profit) at day close.
- Logs user actions to `TitanUserAction`.
- E-invoice/DTTS integration: purchase invoices support batch (تشغيلة) and serial numbers, uploaded to tracking system.

---

## 5. Pricing + VAT

### 5.1 Purchase price types
| Type | Arabic | Meaning |
|------|--------|---------|
| **Real purchase price** | سعر الشراء الحقيقي | The net amount written on the supplier invoice — what you actually pay (or add to the account). "هو المبلغ الصافي الوارد في فاتورة الشراء وهو الذي ستدفعه فعليا الي المورد او يضاف الي الحساب". |
| **Calculated purchase price** | سعر الشراء الحسابي | Derived by the program from entered discounts + VAT + extra discounts. Depends on accurate discount/tax entry. |
| **Unit purchase before tax** | شراء الوحدة قبل الضريبة | Cost per unit excluding VAT. |
| **Unit purchase with tax** | شراء الوحدة شامل الضريبة | Cost per unit including VAT. |

Validation: a large gap between real and calculated purchase price is blocked: "الفرق كبير بين سعر الشراء الحسابي والحقيقي من فضلك راجع مدخلات الفاتورة", "لا يمكن ان يكون الفارق بين سعر الشراء الحقيقي وسعر الشراء الحسابي بمثل هذه الدرجة".

### 5.2 VAT (ضريبة القيمة المضافة)
- Standard VAT 15% (Egypt) — "اجمالي ضريبة القيمة المضافة 15 بالمائة".
- VAT is calculated on **taxable** items; non-taxable purchases excluded.
- **Certain suppliers are exempt**: "الموردين التليين تم استثناء فواتيرهم من احتساب الضريبة" (an exception list of suppliers whose invoices are excluded from VAT). Non-taxable sources include initial stock (الجرد الاولي), معدوم (expired/damaged), unknown supplier, own branches.
- Total VAT may be **manually overridden** in purchases: "امكانية تعديل قيمة اجمالي ضريبة القيمة المضافة يدويا في المشتريات" and per-item "تعديل قيمة ضريبة القيمة المضافة لهذا الصنف".
- "تعديل طريقة حساب ضريبة القيمة المضافة في فاتورة المشتريات" — purchase VAT calculation method is configurable/upgradable.
- Purchase VAT is reportable separately: "ضريبة المشتريات خلال الفتره", RASD XML tags `<purchases-vat>`, `<purchases-with-vat>`, `<purchases-taxable>`, `<purchases-non-taxable>`.

### 5.3 Purchase discount (خصم الشراء)
- Per-item **buy discount** (خصم الشراء / SellDisc) entered on purchase; stored in `storediscount`.
- System can apply **last purchase discount** per item ("تطبيق خصم اخر شراء", "جعل خصم شراء الدواء هو اخر خصم").
- **Unified purchase discount** per supplier ("ادخل خصم شراء موحد") and per-company importer discount.
- Discount affects the calculated purchase price and thus the cost basis and later selling-price / points.

### 5.4 Totals
```
Subtotal        = Σ (Quant × unit purchase price)
Discount        = Σ buy-discount
VAT (ضريبة)     = VAT% applied to taxable items (15%)
Total with VAT  = Subtotal − Discount + VAT
Cost value      = purchase cost (for COGS / stock valuation)
```
Columns on purchase invoice: قيمة الفاتورة (invoice value) | تكلفة الفاتورة (invoice cost) | الضريبة (VAT) | مدفوع نقدا (cash paid) | مدفوع شبكة (network paid) | اجل (credit remainder).
Formulas per `wzgard` columns: `costvalue`, `vatvalue`, `totalwithvat`.

---

## 6. Payment methods

| Method | Arabic | Handling |
|--------|--------|----------|
| Cash | مدفوع نقدا / كاش | Paid from drawer (الدرج); reduces cash drawer, expensed. |
| Network / Visa | مدفوع شبكة / فيزا | Paid via card/network; reduces شبكة (network) balance. |
| Credit / Payable | اجل / أجل المشتريات | Unpaid remainder posted as supplier payable (مستحقات المورد / دائن). Reported by "فات المشتريات" (outstanding purchases) and "اجل المشتريات" (credit purchases). |
| Payable payment voucher | سند صرف لمورد | Later cash/visa settlement of supplier dues. |
| Opening payable | الرصيد الافتتاحي لمستحقات الموردين | Initial supplier dues balance (افتتاحي دائن). |

- **الشراء من غير الموردين** (purchase from non-suppliers) is **cash only**: "لا يمكن الشراء من غير الموردين الا نقدا".
- Payment = cash + visa; remainder = أجـل. Payment validation: "خطأ في حسابات هذه الفاتورة من فضلك راجع قيم المدفوع والاجل".
- Treasury source selection: "ابحث عن حقل خزينة الدفع وحدد اذا كان الدرج او خزينة الصيدلية مع التاكد من ان الرصيد كافي".
- Purchases paid from the **pharmacy treasury (خزينة الصيدلية)**; the screen deals primarily with the **drawer (الدرج)** with the ability to transfer cash from treasury to drawer.

---

## 7. Printing

- Purchase invoices are printed through the shared print engine (`ModPrint`, `FormPrintSales` host; `raz_complete.md` §3.8: Print main / Print receipt / Print A4).
- **طباعة الفاتورة تلقائيا مع الحفظ** (auto-print on save) is configurable; **سيتم طباعة فاتورة مع كل عملية حفظ**.
- "لا يمكن طباعة فاتورة غير محفوظة" — only saved invoices can be printed.
- "عند طباعة فاتورة دفع لعميل تخرج بصورة سند دفع" — supplier payment prints as a payment voucher (سند صرف لمورد).
- Optional barcode printing of any individual item from the purchase screen: "اتاحة طباعة باركود اي صنف منفرد من شاشة المشتريات".
- "هل تود طباعة تاريخ شراء الصنف علي ملصقة الباركود" — optionally print purchase date on the barcode label.
- The drawer (الدرج) may be opened on saving/printing (shared sales/purchase setting).

---

## 8. Tables

### 8.1 `invoicedata` — purchase/sales invoice header + line items
```sql
CREATE TABLE invoicedata (
    id              INT IDENTITY(1,1),      -- PK
    invoiceid       REAL DEFAULT 0,         -- invoice number
    datee           REAL DEFAULT 0,         -- date
    silsilaid       NVARCHAR(15) DEFAULT '',-- chain ID
    pharmacyid      NVARCHAR(15) DEFAULT '',-- branch
    payed           REAL DEFAULT 0,         -- amount paid
    disc            REAL DEFAULT 0,         -- discount
    agel            REAL DEFAULT 0,         -- payable/credit remainder + type
    totalvalue      REAL DEFAULT 0,         -- total with VAT
    -- line items (mirror of titanksasales):
    IdDateTime      DATETIME,               -- entry timestamp
    Quant           REAL DEFAULT 0,         -- quantity
    DrugName        NVARCHAR(100) DEFAULT '',-- drug
    SellDisc        REAL DEFAULT 0,         -- buy discount %
    Tips            NVARCHAR(50) DEFAULT '',-- notes / batch
    Expire          REAL DEFAULT 0,         -- expiry
    Minimum         REAL DEFAULT 0,         -- minimum
    price           REAL DEFAULT 0          -- unit purchase price
);
```

### 8.2 `wzgard` — stock batches (purchase side-effect: ADD)
```sql
CREATE TABLE wzgard (
    phar        NVARCHAR(15) DEFAULT '',    -- pharmacy
    randomid    NVARCHAR(50) DEFAULT '',    -- batch unique id
    writer      NVARCHAR(50) DEFAULT '',    -- entered by
    datee       REAL DEFAULT 0,             -- date (VB6 serial)
    datetimee   DATETIME,                   -- datetime
    classy      NVARCHAR(35) DEFAULT '',    -- category
    quant       REAL DEFAULT 0,             -- qty (+ on purchase, − on return)
    expire      REAL DEFAULT 0,             -- expiry (VB6 serial)
    price       REAL DEFAULT 0,             -- price
    oldstock    REAL DEFAULT 0,             -- previous stock
    costvalue   REAL DEFAULT 0,             -- cost value
    vatvalue    REAL DEFAULT 0,             -- VAT value
    totalwithvat REAL DEFAULT 0,            -- total with VAT
    typee       NVARCHAR(50) DEFAULT '',    -- type: purchase/return direction
    drugname    NVARCHAR(100) DEFAULT ''    -- FK→wzdrugs
);
```

### 8.3 `wzcustomers` — supplier & customer accounts (typee discriminates)
```sql
CREATE TABLE wzcustomers (
    randomid    NVARCHAR(50) DEFAULT '',    -- PK
    phar        NVARCHAR(15) DEFAULT '',    -- pharmacy
    typee       NVARCHAR(50) DEFAULT '',    -- supplier vs customer
    writer      NVARCHAR(50) DEFAULT '',
    creditlimit REAL DEFAULT 0,             -- credit limit
    datee       REAL DEFAULT 0,             -- creation date
    namee       NVARCHAR(100) DEFAULT ''    -- supplier/customer name
);
```

### 8.4 `companies` — supplier master
```sql
CREATE TABLE companies (
    mobile NVARCHAR(15) DEFAULT '' NOT NULL, -- supplier ID (PK)
    pass   NVARCHAR(50) DEFAULT ''           -- pass code
);
```

### 8.5 `farysales` — money/accounting entry (payable side-effect)
```sql
CREATE TABLE farysales (
    id INT IDENTITY(1,1),                  -- PK
    mobile NVARCHAR(15) DEFAULT '',        -- pharmacy phone
    grand  REAL DEFAULT 0,                 -- grand total
    father NVARCHAR(100) DEFAULT '',       -- parent account (خصوم/موردين)
    son    NVARCHAR(100) DEFAULT '',       -- child account
    datee/datetimee/dateemanual, monthe, yearo,  -- date + month/year
    payed  REAL DEFAULT 0,                 -- amount paid
    creditdebit NVARCHAR(20) DEFAULT '',   -- 'credit'/'debit'
    typee  NVARCHAR(50) DEFAULT '',        -- type
    phar/randomid/tips/writer/classy
);
```

### 8.6 `titaninn` — inter-pharmacy transfers / purchase orders
```sql
CREATE TABLE titaninn (
    id INT IDENTITY(1,1),                   -- PK
    fatid INT DEFAULT 0,                    -- group id
    itemsasstring NVARCHAR(4000) DEFAULT '',-- serialized items
    datee INT DEFAULT 0,                    -- date
    source NVARCHAR(100) DEFAULT '',        -- source pharmacy
    silsilaid NVARCHAR(15) DEFAULT '',      -- chain id
    target NVARCHAR(100) DEFAULT ''         -- target pharmacy
);
```

### 8.7 Related tables
- `titanksastock` / `titanstock` — drug-card stock (incremented on purchase).
- `wzdrugs` / `wzdrugs2` — drug card; `wzdrugs2.unitcost`/`costvalue` (computed from wzgard), `expire`.
- `storediscount` — per-item purchase discount history.
- `titanneed` — purchase requests/orders to suppliers.
- `TitanUserAction` — audit log of purchase edits.
- `ChainBuyStore` / `ChainBuyUsers` / `RawakidTablew` — chain purchasing.

---

## 9. UI strings (Arabic)

### Menu / navigation
- المشتريات (Purchases) — menu title
- فاتورة مشتريات (Purchase invoice), قائمة مشتريات (Purchases menu)
- تقارير المشتريات / تقارير مشتريات (Purchase reports)
- التعامل مع الموردين (Dealing with suppliers), تعديل اعدادات الموردين (Modify supplier settings)
- تسديدات المشتريات (Purchase settlements), مستحقات الشركات (Company dues), مستحقات المورد (Supplier dues)
- الشراء من غير الموردين (Purchase from non-suppliers), الجرد الاولي (Initial stock), مورد غير معروف (Unknown supplier)
- تقرير الواردات و المصروفات (Imports & expenses report), سند صرف لمورد (Payment voucher to supplier)

### Invoice columns
- الصنف (Item) | سعر (Price) | الرصيد (Balance) | عدد شهري (Monthly qty) | قيمة شهرية (Monthly value) | اخر شراء (Last purchase)
- رقم الفاتورة (Invoice no.) | التاريخ (Date) | قيمة الفاتورة (Invoice value) | تكلفة الفاتورة (Invoice cost) | الضريبة (Tax) | مدفوع نقدا (Cash paid) | مدفوع شبكة (Network paid) | اجل (Credit) | الفرع (Branch)
- المورد (Supplier) | اسم المورد (Supplier name) | مستحقات المورد (Supplier dues) | المورد او العميل (Supplier or customer)
- شراء (Buy) | المخصوم (Discounted) | القيمة (Value) | الاجل (Credit) | المدفوع (Paid) | الشفت (Shift) | المستخدم (User)
- سعر الشراء الحقيقي (Real purchase price) | سعر الشراء الحسابي (Calculated purchase price) | شراء الوحدة قبل الضريبة / شامل الضريبة
- خصم الشراء (Buy discount) | اخر خصم شراء (Last buy discount)

### Errors / validations
- برجاء اختيار المورد اولا (Please choose the supplier first)
- الفرق كبير بين سعر الشراء الحسابي والحقيقي من فضلك راجع مدخلات الفاتورة (Large gap between calculated and real purchase price — review entries)
- لا يمكن ان يكون الفارق بين سعر الشراء الحقيقي وسعر الشراء الحسابي بمثل هذه الدرجة (Gap cannot be this large)
- لا يمكن الشراء من غير الموردين الا نقدا (Cannot purchase from non-suppliers except in cash)
- خطأ في حسابات هذه الفاتورة من فضلك راجع قيم المدفوع والاجل (Invoice accounting error — review paid & credit values)
- هذا المورد موجود مسبقا (This supplier already exists)
- لم نعثر علي اي فاتورة شراء تحمل رقم التوريد/الدائم هذا (No purchase invoice found with this supply/permanent number)
- لا يمكنك طباعة فاتورة غير محفوظة (Cannot print an unsaved invoice)
- لا تملك صلاحية لعرض سعر الشراء (No permission to view purchase price)
- المشتريات: يجب ان تكون اول فاتورة مشتريات بها ادوية ومحفوظة (First purchase invoice must contain drugs and be saved)
- برجاء التوجه الي شاشة المشتريات لحفظها (Please go to the purchase screen to save it)

### Confirmations / info
- تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات (Supplier/customer balances update automatically)
- انواع فواتير المشتريات (Purchase invoice types) — مشتريات / مرتجع مشتريات / مرتجع الاكسبير
- يتم ادخال ارصدة ادوية الصيدلية من خلال شاشة المشتريات (Opening drug stock is entered via the purchase screen)
- ادخل الرصيد الافتتاحي لمستحقات الموردين (Enter opening supplier-dues balance)
- بامكانك فتح اكثر من فاتورة مشتريات في نفس الوقت (Open multiple purchase invoices)
- جاري تحميل بيانات الموردين (Loading supplier data), جاري اعادة تحميل فواتير المشتريات

---

## 10. Business rules / edge cases

1. **Supplier required first** — a purchase invoice must have a supplier selected before items can be finalized ("برجاء اختيار المورد اولا"); reminders prompt to enter the supplier.
2. **First invoice must be a saved purchase invoice with drugs** — "المشتريات: يجب ان تكون اول فاتورة مشتريات بها ادوية ومحفوظة" (opening stock is established through purchases).
3. **Opening stock (الجرد الاولي)** is entered as a special purchase from a special "initial stock" supplier; it may be non-taxable.
4. **Non-supplier purchases are cash-only** — credit (أجل) is not allowed from "الشراء من غير الموردين".
5. **Stock side-effect**: purchases **ADD** to stock (wzgard typee = in); each batch tracked with oldstock, costvalue, vatvalue, totalwithvat.
6. **Cost basis**: purchases set the drug's unit cost (wzdrugs2.unitcost from wzgard), which drives COGS (تكلفة المبيعات) and profit at day close.
7. **Payable side-effect**: purchase → **دائن** (credit) to supplier (خصوم.موردين), increasing مستحقات المورد; payment (سند صرف) reduces it; opening dues are seeded via افتتاحي دائن.
8. **VAT 15%** on taxable purchase items; exempt suppliers (استثناء من الضريبة) and non-taxable sources (initial stock, معدوم, unknown supplier, own branches); total VAT may be manually overridden.
9. **Price integrity**: real vs calculated purchase price must not diverge greatly (blocked otherwise).
10. **Apply last-purchase defaults**: expiry date and discount from the last purchase can be applied to current invoice items.
11. **Three purchase invoice states**: مشتريات (purchase), مرتجع مشتريات (purchase return), مرتجع الاكسبير (expired-items return).
12. **Multiple open invoices** supported; invoice can be transferred (تحويل) to/from sales, or to a purchase return.
13. **Archiving**: old purchase invoices are archived (أرشفة المشتريات القديمة) to keep DB small; archived invoices readable via FormReadArcInn. Max invoice count enforced (e.g. must exceed 1005/3005 invoices before certain operations).
14. **Treasury**: purchases draw from drawer (الدرج) primarily; cash transfer from treasury (خزينة) supported; supplier payments also via treasury.
15. **Permissions**: viewing purchase price (سعر الشراء) requires permission; editing supplier dues requires justification ("لقد قمت بتغيير مديونية المورد... اذكر لماذا").
16. **Batch/serial (تشغيلة/سيريال)**: purchase invoices upgraded to support batch and serial numbers for e-invoice/DTTS tracking.
17. **Insurance suppliers**: purchases from شركة تامين (insurance companies) follow supplier flow but link to insurance-company customers/claims.
18. **Price sync**: drug prices updated from the last 100/400 purchase invoices.
19. **Audit**: all manual balance/discount changes logged (TitanUserAction; user-action journal for suppliers).
