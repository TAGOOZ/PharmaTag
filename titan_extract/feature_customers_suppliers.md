# Feature: العملاء والموردين (Customers & Suppliers / مراد)

**Purpose:** Full extraction of the customer & supplier master-data and management feature of TITAN.W1 (Phye.exe). Covers the two master tables (`wzcustomers` — customer/supplier accounts, `companies` — supplier master), the customer-supplier management screens (`ModMarid` مراد, `FormMoamla` معاملة, `FormMarid*` بيانات المريض, `FormCoData` بيانات الشركة, `FFFWaredMonsaref` المونسرف), how `typee` distinguishes a customer from a supplier, credit limits (`creditlimit`), opening balances (الارصدة الافتتاحية), address/phone/mobile capture, the customer sub-customer (عميل فرعي) and insurance-company (شركة تامين) customers, and how **credit (أجل) sales post to the `wzcustomers` balance** while **purchases post a payable (مستحقات الموردين) to `companies`**. Includes tables, fields, workflow, UI strings (Arabic), and business rules. Reuses the sales/purchases feature docs which drive these balances.

---

## 1. Objects

| Object | Type | Arabic | Role |
|--------|------|--------|------|
| `ModMarid` | Module (4 procs) | مراد | Customer/supplier (Marid) management core — lookup, search, selection, 107-field data-structure init (`modules_gap_1.md:36-54`). |
| `FormMoamla` | Form | المعاملة / تعاملات | Customer/supplier transaction & payment recording screen (`modules_gap_2.md:939-955`). |
| `FormMarid` | Form (5 procs) | وحدة المرضى | Patient/customer records (`ui_complete.md:174`). |
| `FormMaridData` | Form (15 procs) | بيانات المرضى | Patient/customer data management — writes `wzcustomers` (`schema_mapping.md:230`, `ui_complete.md:175`). |
| `FormMaridFat` | Form (4 procs) | فواتير المرضى | Patient/customer invoices (`ui_complete.md:176`). |
| `FormCoData` | Form (8 procs) | بيانات الشركة | Company (supplier) data — writes `companies` (`schema_mapping.md:231`, `ui_complete.md:177`). |
| `FFFWaredMonsaref` | Form (36 procs) | المونسرف / المستودع | Supplier/warehouse & supplier-settings screen — credit limits, opening dues, bank account, discounts, GLN (`feature_purchases.md:26,122`; `ui_complete.md:102`). |
| `ModUsers` | Module | — | Parent module owning customer/supplier tables `wzcustomers`, `companies` (`schema_mapping.md:53`). |
| `ModOrood` | Module (3 procs) | عروض | Promotions/offers (buy-X-get-Y) — quantity-based discount engine, shares discount-calc path (`modules_remaining_1.md:292-309`). |
| `ModMohasaby` / `FormMohasaby` | Module/Form | المحاسبى | Accounting screen; connects to `FormMoamla`, `ModAccounting` for balances (`modules_gap_2.md:957-969`). |

**Data mapping** (`schema_mapping.md:27-28`): `wzcustomers` PK = `randomid`; `companies` PK = `mobile`.

---

## 2. Step-by-step workflow

### 2.1 Add a customer / supplier (إضافة عميل / مورد)
1. From the main menu: قائمة رئيسية → الموردين → إضافة مورد جديد (add new supplier, `feature_purchases.md:123`); or `ModMarid` `Add a customer` / `Add a new supplier` (`modules_gap_1.md:51`).
2. Prompt for the name: `ادخل اسم العميل الجديد بحد ادني 6 احرف واقصي 30 حرف` (customer name 6–30 chars, readable:8457), `ادخل اسم المورد الذي تود اضافته` (readable:8462).
3. Name must be unique / distinguishable: `ادخل اسمه ويجب ان لا يكون متكررا فلو هناك عميل اخر بنفس الاسم فحاول ان تميزهما` (readable:8467).
4. Capture identifying fields: `ادخل رقم موبايل العميل` (mobile, readable:8567), `ادخل عنوان العميل` (address, readable:8587), `ادخل رقم السجل التجاري للعميل الحالي` (commercial register, readable:8437), `ادخل رقم التسجيل الضريبي للعميل الحالي` (tax reg, readable:8436).
5. Set financial attributes: `ادخل حد الائتمان لهذا العميل` (credit limit, readable:8527), `ادخل المديونية الحالية للعميل` (current debt, readable:8511), `ادخل نسبة الخصم المحلي لهذا العميل` (local discount %, readable:8629), `ادخل نسبة الخصم المستورد لهذا العميل` (importer discount %, readable:8630), `ادخل عدد النقاطك الحالية للعميل الحالي` (current loyalty points, readable:8584).
6. Save → INSERT into `wzcustomers` (randomid, phar, typee, writer, creditlimit, datee, namee) (`schema_complete.md:125`).

### 2.2 Edit / correct a customer or supplier
- Menu command `اختر امر تعديل عميل او تعديل مورد` (choose edit-customer or edit-supplier, readable:8379).
- `ادخل الاسم الجديد للمورد` (new supplier name, readable:8469).
- Manual debt correction: `تصحيح مديونية العميل الحالي` (correct current customer debt, readable:10182) / `التعديل اليدوي لارصدة العملاء` (manual customer-balance edit, readable:9258).
- Credit limit adjustable from the sales screen: `امكانية تعديل حد الائتمان لعميل من داخل شاشة المبيعات` (readable:9799).
- Delete guard based on recency: `اخر تعامل لهذا العميل كان قبل اقل من شهرين ولا يمكن حذفه` (cannot delete if dealt within 2 months, readable:8415).

### 2.3 Sales — credit (أجل) posts to customer balance
From `feature_sales_invoices.md:117`:
- For **credit (أجل)** sales, the customer's debt increases in `wzcustomers`.
- For **cash (نقدي)** customers, full payment is required: `هذه الفاتورة لعميل نقدي ويجب ان يكون الدفع بكامل المبلغ` (idx 13133).
- Customer debt auto-updates from the sales screen: `تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات` (idx 10712).
- The current invoice is included in the displayed customer debt even if unsaved: `اثناء عرض مديونية العميل في شاشة المبيعات يتم احتساب الفاتورة الحالية حتي لو غير محفوظة` (readable:8277).
- Saving is blocked when the resulting balance exceeds the credit limit: `اجمالي المتبقي من هذه الفاتورة ومديونية هذا العميل اكبر من الحد الائتماني له ولهذا فلا يمكن حفظ الفاتورة` (readable:8320).

### 2.4 Purchase — posts a payable (مستحقات الموردين) to suppliers
From `feature_purchases.md:139-143`:
- A purchase creates a **credit (دائن / payable)** to the supplier: accounting path `خصوم.خصوم متداولة.موردين` (Liabilities → Current Liabilities → Suppliers). This increases `مستحقات المورد / مستحقات الشركات`.
- Recording entry uses `farysales` with `creditdebit` = 'credit'/'debit' and `father/son` = the accounting-tree path (`feature_purchases.md:141`).
- Supplier type selection: مورد (supplier), شركة (company), فرد (individual), شركة تامين (insurance company) (`feature_purchases.md:117`).
- Paying a supplier reduces the payable: `سند صرف لمورد` (payment voucher, readable:275), `دفع مستحقات الشركات والمخازن`, `تسديدات المشتريات` (readable:10142), `خروج نقدية نتيجة الدفع للشركات` (readable:10762).
- Choose which company to pay: `اختر اسم الشركة او المخزن الذي تود تسديد مستحقاته` (readable:8371).

### 2.5 Customer/supplier transactions & payments (FormMoamla)
- `FormMoamla` المعاملة / تعاملات records customer/supplier transactions and payments (`modules_gap_2.md:943-948`).
- Controls: `dgTransactions`, `cmbCustomer`, `cmbType`, `txtAmount`, `btnPay`, `btnReceive` (`modules_gap_2.md:947`).
- Tracks last activity: `اخر تعامل` (last transaction, readable:8408) with aging thresholds 30/60/120/180/365/730 days (`اخر تعامل كان منذ اكثر من 30/60/120/180/365/730 يوما`, readable:8409-8414).

### 2.6 Supplier settings (FFFWaredMonsaref)
From `feature_purchases.md:122`:
- Supplier name, bank account `ادخل الحساب البنكي للمورد` (readable:8480), opening dues `ادخل الرصيد الافتتاحي لمستحقات الموردين` (readable:8488), unified purchase discount `ادخل خصم شراء موحد` (readable:8533), importer discount `ادخل خصم المستورد لهذه الشركة`, tax reg/cloud link `ادخل رقم التسجيل الضريبي او رقم الربط السحابي اذا كان المورد صيدلية` (readable:8541), supplier GLN `Inpu GLN for this supplier` (readable:5002).

### 2.7 Sub-customers & insurance companies
- Sub-customers (عميل فرعي) attached to a primary customer: `اضافة العملاء الفرعيين الملحقين بالعميل الاصلي مثل عملاء شركات التامين او افراد اسرة ملحقين باسم عميل رئيسي` (readable:8923); `العميل الفرعي هو عميل منبق عن عميل رئيسي` (readable:9473); `قم باختيار اسم العميل الفرعي رجاءا` (readable:11503).
- Insurance customers: `عملاء شركات التامين` (readable:11310), `طباعة لشركات التامين` (print for insurance cos, readable:11226). Purchases from insurance companies follow supplier flow but link to insurance-company customers/claims (`feature_purchases.md:393`).

### 2.8 Convert customers to cash (نقدي)
- `تحويل كل العملاء الي عملاء نقدي ما عدا من عليهم مديونيات` (convert all customers to cash except those with debts, readable:10120). Cash-customer flag `النقدي` / `عميل نقدي` (readable:9734,11325).

---

## 3. Fields / data captured

### 3.1 `wzcustomers` — customer/supplier account (customer & supplier discriminator)
From `schema_complete.md:111-127`, `feature_purchases.md:273-284`:
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `randomid` | NVARCHAR(50) | `''` | **PK** — unique ID |
| `phar` | NVARCHAR(15) | `''` | **FK→wzphar** — pharmacy (branch) |
| `typee` | NVARCHAR(50) | `''` | **Customer vs supplier discriminator** + customer type |
| `writer` | NVARCHAR(50) | `''` | Entered by |
| `creditlimit` | REAL | `0` | **Credit limit** (حد الائتمان) — ceiling checked on credit sales |
| `datee` | REAL | `0` | Creation date |
| `namee` | NVARCHAR(100) | `''` | Customer/supplier name |

**SQL Evidence:** `"insert into wzcustomers (randomid,phar,typee,writer,creditlimit,datee,namee) values("` ; `"if not exists( select * from wzcustomers where phar =N'"` (`schema_complete.md:125-126`).

### 3.2 `companies` — supplier master
From `schema_complete.md:131-142`, `feature_purchases.md:286-292`:
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `mobile` | NVARCHAR(15) | `''` | **PK** — supplier phone/ID |
| `pass` | NVARCHAR(50) | `''` | Password/pass code (supplier registration) |

**SQL Evidence:** `"insert into companies (mobile,pass) values ("` ; `"if not exists( select * from companies where mobile=N'"` (`schema_complete.md:140-141`).

### 3.3 Extended per-record fields (via supplier settings / customer definition screens)
Stored in UI/memory structures and supplier-settings: name, mobile, address (عنوان), commercial register (سجل تجاري), tax reg no. (تسجيل ضريبي), bank account (حساب بنكي), credit limit (حد الائتمان), local discount % (خصم المحلي), importer discount % (خصم المستورد), loyalty points (نقاط), opening balances (رصيد افتتاحي), GLN, cash-only flag (نقدي), sub-customer linkage (عميل فرعي), insurance-company linkage (شركة تامين). `ModMarid` initializes a 107-field customer/supplier record structure (`modules_gap_1.md:38,44`).

### 3.4 Balance/posting ledger — `farysales`
From `feature_purchases.md:294-308`: `mobile, grand, father, son, datee/datetimee/dateemanual, monthe, yearo, payed, creditdebit ('credit'/'debit'), typee, phar, randomid, tips, writer, classy` — records the supplier payable / customer receivable against the accounting tree.

---

## 4. Side-effects

- **Customer balance (`wzcustomers`)** — credit (أجل) sales increase customer debt; cash customers must pay in full (`feature_sales_invoices.md:117`); returns reverse it (`feature_sales_returns.md:71`). Auto-updates from sales & purchases screens (`idx 10712`).
- **Supplier payable (`farysales` / `companies`)** — purchases create credit (دائن) payables under `خصوم.موردين`; `مستحقات المورد / مستحقات الشركات` increase (`feature_purchases.md:140-142`). Paying issues `سند صرف لمورد` and reduces the payable.
- **Money / daily files** — cash sales added to drawer (قبض), credit recorded; serialized daily files `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy` (`feature_sales_invoices.md:118`). Purchases expense cash out of the drawer/treasury (الدرج / خزينة الصيدلية).
- **Chain record** — `titanksasales` row per invoice via GUID loop (`feature_sales_invoices.md:119`).
- **Per-line data** — `invoicedata` row per sold/purchased drug (`feature_sales_invoices.md:120`).
- **Accounting tree** — `اصول.متداولة.عملاء` (customer receivables) and `خصوم.متداولة.موردين` (supplier payables) aggregate from these balances (`feature_balances.md:224,240`).
- **Audit** — `TitanUserAction` write on invoice ops (`feature_sales_invoices.md:122`).

---

## 5. Pricing + VAT

- Customer/supplier discounts: local discount (خصم المحلي) and importer discount (خصم المستورد) are per-customer fields (readable:8629,8630,8964); `خصم المحلي و وخصم المستورد` (readable:10773).
- Unified purchase discount and importer discount negotiated per supplier via `FFFWaredMonsaref` (`feature_purchases.md:122`; `feature_discounts.md:64`).
- Discount engine shared with promotions (ModOrood buy-X-get-Y) (`feature_discounts.md:18,216`).
- VAT 15% default; `موردين معينين تم استثناء فواتيرهم من احتساب الضريبة` (certain suppliers exempt from VAT, readable:9718).

---

## 6. Payment methods

- **cash (كاش / نقدا)** · **visa/network (فيزا / شبكة)** · **credit/أجل (اجل)** (`feature_sales_invoices.md:151`).
- `payed` = cash+visa paid; `agel` = deferred; `totalvalue = payed + agel`; `يجب ان يكون مجموع الاجل والمدفوع مساويا لسعر الفاتورة` (idx 13344).
- Paying customer debt naturally from the مدفوع (paid) field at invoice bottom: `اذا اردت ان تسدد جزء من مديونية العميل او كلها بشكل طبيعي فيجب ان يتم ذلك من حقل مدفوع اسفل الشاشة` (readable:8675).
- VISA customer payments selectable from customer list: `تسجيل مدفوعات الفيزا من خلال اختيار عميل فيزا من قائمة العملاء` (readable:8940).
- Supplier payable settled via `سند قبض` (receipt voucher, readable:11013) / `سند صرف` (payment voucher, readable:11012).

---

## 7. Printing

- Insurance company sales print: `طباعة لشركات التامين` / `Printing for insurance companies` (`reports_complete.md:146`; readable:11226).
- Customer/supplier balance columns: `اسم العميل مديونية العميل الفرع` (readable:100), `اسم المورد مستحقات المورد الفرع` (readable:101).
- Print templates 500/600/700/800 selector (`feature_balances.md:65`).
- Account statements & trial balance feed customer/supplier balances (`feature_balances.md:60,132`).

---

## 8. Tables

### 8.1 `wzcustomers` — customer & supplier accounts
```sql
CREATE TABLE wzcustomers (
    randomid    NVARCHAR(50) DEFAULT '',    -- PK
    phar        NVARCHAR(15) DEFAULT '',    -- pharmacy (FK->wzphar)
    typee       NVARCHAR(50) DEFAULT '',    -- supplier vs customer + type
    writer      NVARCHAR(50) DEFAULT '',
    creditlimit REAL DEFAULT 0,             -- credit limit (حد الائتمان)
    datee       REAL DEFAULT 0,             -- creation date
    namee       NVARCHAR(100) DEFAULT ''    -- customer/supplier name
);
```
(schema_complete.md:111-127; feature_purchases.md:275-283)

### 8.2 `companies` — supplier master
```sql
CREATE TABLE companies (
    mobile NVARCHAR(15) DEFAULT '' NOT NULL, -- supplier ID (PK)
    pass   NVARCHAR(50) DEFAULT ''           -- pass code
);
```
(schema_complete.md:131-142; feature_purchases.md:288-291)

### 8.3 `farysales` — money/accounting entry (payable/receivable side-effect)
From `feature_purchases.md:296-307`: `id PK, mobile, grand, father, son, datee/datetimee/dateemanual, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy`.

---

## 9. UI strings (Arabic)

From `strings_readable.txt`:

**Add / edit customer & supplier:**
- `ادخل اسم العميل الجديد بحد ادني 6 احرف واقصي 30 حرف` (:8457)
- `ادخل اسم المورد الذي تود اضافته` (:8462)
- `ادخل اسمه ويجب ان لا يكون متكررا فلو هناك عميل اخر بنفس الاسم فحاول ان تميزهما` (:8467)
- `اختر امر تعديل عميل او تعديل مورد` (:8379)
- `ادخل رقم موبايل العميل` (:8567) · `ادخل عنوان العميل` (:8587)
- `ادخل رقم السجل التجاري للعميل الحالي` (:8437) · `ادخل رقم التسجيل الضريبي للعميل الحالي` (:8436)
- `ادخل حد الائتمان لهذا العميل` (:8527) · `حد الائتمان` (:10655)
- `ادخل المديونية الحالية للعميل` (:8511) · `ادخل المديونية الفعلية حاليا` (:8512)
- `ادخل نسبة الخصم المحلي لهذا العميل` (:8629) · `ادخل نسبة الخصم المستورد لهذا العميل` (:8630)
- `تصحيح مديونية العميل الحالي` (:10182) · `التعديل اليدوي لارصدة العملاء` (:9258)
- `امكانية تعديل حد الائتمان لعميل من داخل شاشة المبيعات` (:9799)
- `اخر تعامل لهذا العميل كان قبل اقل من شهرين ولا يمكن حذفه` (:8415)

**Balances / aging:**
- `اسم العميل مديونية العميل الفرع` (:100) · `اسم المورد مستحقات المورد الفرع` (:101)
- `اجل العملاء` (:8299) · `اجمالي مديونية` (:8342) · `المديونية` (:9654) · `رصيد العميل` (:10873)
- `تتغير ارصدة الشركات والعملاء تلقائيا من شاشتي المبيعات والمشتريات` (:10712)
- `اخر تعامل` (:8408) · `اخر تعامل كان منذ اكثر من 30/60/120/180/365/730 يوما` (:8413-8414,:8409-8412)
- `التسلسل الزمني للارصدة والعملاء` (:9252) · `تقرير تتبع تصحيح الارصدة تلقائيا` (:8913)

**Opening balances:**
- `ادخل الرصيد الافتتاحي لمديونيات العملاء` (:8487) · `ادخل الرصيد الافتتاحي لمستحقات الموردين` (:8488)
- `الارصدة الافتتاحية` (:9105) · `افتتاحي دائن` (:9058) · `افتتاحي مدين` (:9059)

**Payments / posting:**
- `سند صرف لمورد` (:275) · `سند صرف` (:11012) · `سند قبض` (:11013)
- `تسديدات المشتريات` (:10142) · `خروج نقدية نتيجة الدفع للشركات` (:10762)
- `اختر اسم الشركة او المخزن الذي تود تسديد مستحقاته` (:8371)
- `مدفوع نقدا` (:9647) · `مدفوع شبكات` (:9645) · `قيمة الاجل` (:11548) · `المدفوع` (:12032)
- `خطأ في حسابات هذه الفاتورة من فضلك راجع قيم المدفوع والاجل` (:10806)

**Supplier settings:**
- `ادخل الحساب البنكي للمورد` (:8480) · `ادخل خصم شراء موحد` (:8533) · `ادخل خصم المستورد لهذه الشركة`
- `ادخل رقم التسجيل الضريبي او رقم الربط السحابي اذا كان المورد صيدلية` (:8541) · `ربط سحابي` (:10863)
- `Inpu GLN for this supplier` (:5002) · `ادخل 555 لرفع اسماء الموردين الي كل الفروع` (:8433)

**Sub-customers & insurance:**
- `اضافة العملاء الفرعيين الملحقين بالعميل الاصلي مثل عملاء شركات التامين او افراد اسرة ملحقين باسم عميل رئيسي` (:8923)
- `العميل الفرعي هو عميل منبق عن عميل رئيسي` (:9473) · `عميل فرعي` (:11324)
- `عملاء شركات التامين` (:11310) · `طباعة لشركات التامين` (:11226)
- `تعديلات علي الية خصم شركات التامين مما يسمح بتعديل نسبة خصم المستورد` (:10262)

**Cash customers & points:**
- `تحويل كل العملاء الي عملاء نقدي ما عدا من عليهم مديونيات` (:10120) · `عميل نقدي` (:11325) · `النقدي` (:9734)
- `النقاط` (:9733) · `نقاط العميل` (:12341) · `اضافة نظام جديد لنقاط العملاء خاص بالمبيعات` (:8999)
- `اذا كان خصم الشراء الصنف هو 60% فان الية احتساب النقاط تعتبره 35% فقط` (:8695)
- `اصبحت النقاط تمنح للعملاء المسجلين فقط وليس العملاء العابرين` (:8842)

---

## 10. Business rules / edge cases

1. **`typee` discriminates customer vs supplier** — one `wzcustomers` account holds both, distinguished by `typee` (`feature_purchases.md:121`); `namee` = name, `creditlimit` = allowed credit.
2. **Credit limit enforcement** — credit sale blocked if `متبقي الفاتورة + مديونية العميل > الحد الائتماني` (readable:8320).
3. **Cash-only customers** must pay in full (`feature_sales_invoices.md:117`; idx 13133). Bulk convert to cash except debtors (readable:10120).
4. **Auto balance updates** from sales & purchases screens (idx 10712); current unsaved invoice included in displayed debt (readable:8277).
5. **Minimum name length** 6, max 30 chars; names must be distinguishable/non-duplicate (readable:8457,8467).
6. **Delete guard** — cannot delete a customer transacted within ~2 months (readable:8415); aging buckets 30–730 days (readable:8409-8414).
7. **Manual debt correction** allowed (`تصحيح مديونية العميل الحالي` readable:10182); balance corrections tracked (`تصحيح ارصدة` readable:10175).
8. **Supplier payable = accounting credit** under `خصوم.متداولة.موردين`; opening dues entered as `افتتاحي دائن` (opening credit, readable:9058); customer receivables under `اصول.متداولة.عملاء` (`feature_balances.md:224,240`).
9. **VAT exemption** for specific suppliers (readable:9718); VAT 15% default elsewhere.
10. **Sub-customers** (عميل فرعي) link to a primary customer — used for insurance-company customers and family members (readable:8923).
11. **Points (نقاط)** awarded only to registered customers, not walk-ins (readable:8842); points replace part of discount (readable:10376); purchase-discount points capped (e.g. 60%→35%, readable:8695).
12. **Deprecated payables** — purchases paid from drawer or pharmacy treasury with `ترحيل نقدية` option (`feature_purchases.md:143`); cash out of drawer must be logged externally or transferred (readable:9847).

---

## Key references
- `schema_complete.md:111-142` (tables 4 wzcustomers, 5 companies)
- `feature_purchases.md:117-123, 139-143, 273-308` (supplier master, payable posting, tables)
- `feature_sales_invoices.md:117-122, 149-154` (credit → customer balance, payment split)
- `feature_sales_returns.md:71,136,181` (customer balance reversal on return)
- `feature_balances.md:60-72,132,200-201,224,240,291-296` (opening balances, chart accounts)
- `modules_gap_1.md:36-54` (ModMarid), `modules_gap_2.md:939-955` (FormMoamla)
- `modules_remaining_1.md:292-309` (ModOrood)
- `schema_mapping.md:27-28,53,230-231` (table→form mapping)
- `feature_discounts.md:18,64,216` (supplier discount agreements, promotions)
