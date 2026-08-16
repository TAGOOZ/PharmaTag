# TITAN.W1 — التحويلات واللوجستيات (Inter-Pharmacy Transfers & Logistics)

**System**: Saudi/Egyptian Pharmacy Management System (VB6 desktop application, 237 forms, 6,192 procedures)
**Database**: SQL Server (ADODB)
**Scope**: How drugs move between branch pharmacies, the inter-branch transfer order lifecycle (request → approve → ship → receive), delivery/توصيل to customers (FormTawsil), chain buy/شراء جماعي (FormChainBuy), needs/orders between pharmacies (titanneed), and rawakid (رواكد) dead-stock exchange.

**Primary source modules/forms**: `ModNetwork`, `ModFTP`, `ModTitanCloud`, `ModFarWay` (branch sync), `FormTahwil`, `FormTahwilList`, `FormTawsil`, `FormDrivers`, `Formdeliver`, `Moddelivery`, `FormChainBuy`, `FormChainBuyList`, `FormCopyMe`, `FormOrder`, `FormOrderList`, `FormRawakid`, `FormHajozat`, `FormNeedEntryShow`, `FormNeedsDetails`, `FormNeedsAll`, `FormSilsila`.

---

## 1. Objects

### 1.1 Transfer / Branch-Movement Forms & Modules

| Object | Role | Notes |
|--------|------|-------|
| `FormTahwil` | التحويل / تحويل بين الفروع | Branch transfer — move drugs/invoices between branches (modules_gap_2.md:1159) |
| `FormTahwilList` | قائمة التحويلات | Transfer listing/browse (modules_gap_2.md:1172) |
| `ModNetwork` (65 procs) | Core network/FTP/cloud operations | network_complete.md:4 |
| `ModTitanCloud` (16 procs) | Cloud storage + chain sync | network_complete.md:6 |
| `ModFarWay` (4 procs) | Remote branch file sync (Titanfary.exe) | modules_remaining_1.md:388 |
| `ModOrood` / `FormOrood1` | عرض الطلبيات (order display) | order-related view |
| `FormGetFats` | Fetch invoices | import/conversion for transfer (modules_gap_2.md:1304) |
| `FormImportFat` / `FormExportFat` | Import/export invoices | cross-branch invoice movement |

### 1.2 Delivery / توصيل Forms

| Object | Role | Notes |
|--------|------|-------|
| `FormTawsil` | التوصيل / الدليفري | Delivery management (modules_gap_2.md:308) |
| `FormDrivers` | السائقين / عمال التوصيل | Delivery driver directory (modules_gap_2.md:536) |
| `Formdeliver` | Deliveries | Delivery list/tracking (modules_remaining_2.md:49) |
| `Moddelivery` | Delivery service mgmt | modules_remaining_2.md:174 |

### 1.3 Chain Buy / شراء جماعي Forms

| Object | Role | Notes |
|--------|------|-------|
| `FormChainBuy` | سلسلة المشتريات | Purchase series / group buy (modules_gap_2.md:82) |
| `FormChainBuyList` | قائمة سلاسل المشتريات | List of purchase chains (modules_gap_2.md:481) |
| `FormRawakid` | الرواكد | Dead/slow-moving stock publish + exchange (FormRawakid @0x00a96804) |

### 1.4 Needs / Orders Forms

| Object | Role | Notes |
|--------|------|-------|
| `FormOrder` | الطلب / طلبية | Purchase order entry to suppliers (modules_gap_2.md:1048) |
| `FormOrderList` | قائمة الطلبات | Order listing (modules_gap_2.md:1064) |
| `FormNeedEntryShow` / `FormNeedsDetails` / `FormNeedsAll` | النواقص | Shortage/needs entry & details (FormNeedEntryShow @0x00a588ec) |
| `FFFNeed` / `FFFNeedAuto` | Needs | Manual / auto shortage systems |
| `FormSilsila` | السلسلة | Chain reports (modern) (reports_complete.md:40) |

### 1.5 Other

| Object | Role | Notes |
|--------|------|-------|
| `FormCopyMe` | نسخ لي | Copy/duplicate + transfer invoices to another customer (modules_gap_2.md:108) |
| `FormHajozat` | الحجوزات | Drug reservations for customers (modules_gap_2.md:795) |

---

## 2. How Drugs Move Between Branch Pharmacies (Concept)

Titan supports a multi-branch/chain model. Branches are pharmacies in a **group (المجموعة)** linked by a **cloud-link number (رقم الربط السحابي)**. Movement of drugs/invoices between branches is governed by:

1. **Cloud-link (الربط السحابي)** — the primary mechanism. Main + branch instances exchange serialized data over the network/cloud. Each branch is identified by a mobile/cloud number.
   - UI: "رقم موبايل الربط السحابي للمجموعة" (group cloud-link mobile number), "رقم الموبايل الربط السحابي الحالية" (current cloud-link mobile) — strings_readable.txt:10906,10912.
   - "^^ جاري الان الربط السحابي .. شكرا لوقتك" (cloud linking in progress) — strings_readable.txt:637.
   - "تطوير وتسريع تقنية الربط السحابي من حيث الرفع والاستدعاء" (improve cloud-link upload/recall) — strings_readable.txt:10222.
   - "تم تطوير الية الربط السحابي وتغيير بنية البيانات المتداولة" (cloud-link mechanism and data structure updated) — strings_readable.txt:10416.
   - Branch stock visibility only when the group is linked: "رصيد الاصناف في الفروع متاحة فقط في حالة ربط المجموعه" — strings_readable.txt:10869.

2. **FarWay (تيتان فاري)** — file-based master-slave sync for remote/offline branches. A separate instance `Titanfary.exe` runs on the branch and exchanges data files with the main instance via `FarData` folders (modules_remaining_1.md:390-406):
   - `\Files\FarWay\Titanfary.exe` — remote branch executable
   - `\Files\FarWay\FarData\FromMain\` — data pushed from main to branch
   - `\Files\FarWay\FarData\ToMain\Inn\` — purchase (inbound) data from branch to main
   - `\Files\FarWay\FarData\ToMain\Oot\` — sales (outbound) data from branch to main
   - `\Files\FarWay\i-am-runing.txt` — heartbeat/online indicator

3. **Full branch mode (طريقة الربط الكاملة)** — the same program runs on every sub-device; sub-devices can open new sales/purchase invoices directly (strings_readable.txt:9391,9393,10005,10475,10477).

4. **Export/Import invoice files** — "تحسين خدمة تصدير الفواتير ما بين افرع الصيدليات" (improve invoice export between branch pharmacies) — strings_readable.txt:10094. "يمكنكم الان تمرير الطلبيات من صيدلية الي اخري اونلاين" (you can now pass orders from one pharmacy to another online) — strings_readable.txt:12734.

---

## 3. Transfer Order Lifecycle (titaninn / FormTahwil)

The **inter-pharmacy transfer** is modelled by the `titaninn` table (Titan "in" — inbound to the receiving pharmacy). A transfer is a batch identified by `fatid` and carrying a serialized item list.

### 3.1 Table: `titaninn` (Inter-Pharmacy Transfers / Purchase Orders)

From schema_complete.md:146-168 and strings_readable.txt:669-812:

```sql
CREATE TABLE titaninn (
    id            INT IDENTITY(1,1)  PRIMARY KEY,
    fatid         INT          DEFAULT 0,       -- group/batch transfer ID
    itemsasstring NVARCHAR(4000) DEFAULT '',     -- serialized item list (the actual drug lines)
    datee         INT          DEFAULT 0,        -- date (integer format)
    source        NVARCHAR(100) DEFAULT '',       -- source pharmacy
    silsilaid     NVARCHAR(15)  DEFAULT '',       -- chain/series ID
    target        NVARCHAR(100) DEFAULT ''        -- target pharmacy
)
```

**Key SQL operations** (strings_readable.txt:718, 774-812):
```sql
insert into titaninn (fatid,itemsasstring,datee,source,silsilaid,target) VALUES (...)
select * from titaninn where source = N'...'       -- list outgoing transfers
select * from titaninn where target = N'...'       -- list incoming transfers
select fatid from titaninn where ...               -- find transfer batch
update titaninn set target = N''                   -- clear/complete target (received)
delete from titaninn
drop table titaninn;
```

**Lifecycle** (request → approve → ship → receive):
1. **Request/Compose** — The sender selects the target branch by its cloud-link number: "ادخل رقم الربط السحابي للفرع المراد التحويل اليه" (enter the cloud-link number of the branch to transfer to) — strings_readable.txt:8541. Or via the customer page: "توجه الي صفحة العميل وادخل رقم الصيدلية المطلوب تحويل الاصناف اليها" (go to the customer page and enter the number of the pharmacy to transfer items to) — strings_readable.txt:10507.
2. **Serialise lines** — Drug lines are serialized into `itemsasstring` (NVARCHAR(4000)) — the payload of the transfer.
3. **Ship / place in transfer list** — "تم النقل الي قائمة التحويل" (moved to the transfer list) — strings_readable.txt:10397.
4. **Invoice transfer** — "تم تحويل الفاتورة" (invoice transferred) — strings_readable.txt:10413. The invoice is converted to a **transferred order**: "تحويل الي طلبية محولة" (convert to a transferred order) — strings_readable.txt:10113; "تحويل الفاتورة الي صيدلية اخري" (transfer the invoice to another pharmacy) — strings_readable.txt:10112.
5. **Monitor** — "متابعة التحويلات ما بين الصيدليات" (follow transfers between pharmacies) — strings_readable.txt:11988; "متابعة الطلبيات المحولة" (follow transferred orders) — strings_readable.txt:11990.
6. **Receive** — The receiving branch imports the transferred invoice: "استيراد فاتورة محولة من مستودع او صيدلية اخري" (import a transferred invoice from a warehouse or another pharmacy) — strings_readable.txt:8783. Stock is credited on the receiving side (inbound) and `target` is cleared on completion (`update titaninn set target = N''`).

**Supplier-as-pharmacy**: When the supplier is itself a pharmacy, the tax registration OR cloud-link number is used as the supplier identifier: "ادخل رقم التسجيل الضريبي او رقم الربط السحابي اذا كان المورد صيدلية" (enter the tax registration or cloud-link number if the supplier is a pharmacy) — strings_readable.txt:8538.

**Sub-device receive flow**: "توجه الي الجهاز الفرعي وشغل البرنامج نفسه واضغط علي امر جديد" (go to the sub-device, run the same program, and press the new command) — strings_readable.txt:10501; "توجه الي اعدادات العميل وحوله الي فرع او صيدلية" (go to customer settings and convert it to a branch or pharmacy) — strings_readable.txt:10500. Main device pulls branch-sent invoices with the dollar key: "تم اضافة مفتاح علامة الدولار في شاشة المبيعات لجلب الفواتير المرسلة من الاجهزة الفرعية بنقرة واحدة" (added the dollar key to fetch invoices sent from sub-devices in one click) — strings_readable.txt:10371.

### 3.2 Fields captured by FormTahwil (likely controls)

| Control | Purpose |
|---------|---------|
| `cmbFromBranch` / `cmbToBranch` | Source / destination branch selectors (modules_gap_2.md:1167) |
| `dgItems` | Items to transfer |
| `btnTransfer` / `btnConfirm` | Execute and confirm the transfer |
| transfer batch `fatid` | Groups the transfer lines |

---

## 4. Needs Between Pharmacies — titanneed (FormNeed*)

### 4.1 Table: `titanneed` (Inter-Pharmacy Needs / Orders)

From schema_complete.md:243-259 and strings_readable.txt:7607:

```sql
CREATE TABLE titanneed (
    id       INT IDENTITY(1,1) PRIMARY KEY,
    drugname NVARCHAR(100) DEFAULT '',   -- FK -> wzdrugs
    quant    REAL DEFAULT 0,             -- quantity needed
    datee    REAL DEFAULT 0,             -- date
    sender   NVARCHAR(20) DEFAULT '',    -- requesting pharmacy
    target   NVARCHAR(20) DEFAULT ''     -- fulfilling pharmacy
)
insert into titanneed (drugname,quant,datee,sender,target) values (...)
DROP table titanneed;
```

Needs model the "shortage/request" between pharmacies: one pharmacy (`sender`) requests quantity of a drug (`quant`) from another (`target`). Combined with the stock table `titanksastock` (which carries `minimum` per pharmacy per chain) this drives the shortage detection.

### 4.2 The three shortage (نواقص) systems

Titan has three shortage systems (strings_readable.txt:5416-5421, 9726-9728, 10229, 10060):
1. **Manual system (نظام يدوي)** — "Add to needs - manual system", "Add to the manual needs page" (strings_readable.txt:3535-3536). Manually register items in the كشكول النواقص (shortage notebook).
2. **Half-automatic / minimum-level system (نصف الالي - الحد الادني)** — requires a minimum stock level per drug; when stock falls below minimum the item becomes a shortage (strings_readable.txt:10229, "الكمية التي طلبتها اقل من الحد الادني للطلب" — the quantity you requested is below the minimum order level, 9602).
3. **Automatic / sales-rate system (وفقا للمبيعات)** — detects shortages based on sales rates (strings_readable.txt:5419).

The single combined screen shows all three systems (strings_readable.txt:10060, 10215).

**Needs entry prompts**: "ادخل الكمية التي تود طلبها" (enter the quantity you want to order) — strings_readable.txt:8503; "ادخل الكمية المطلوبة" (enter the required quantity) — 8504.

**Live orders awaiting supplier**: "أدوية طلبت وفي انتظار ان تصل من المورد" (drugs ordered and waiting to arrive from the supplier) — strings_readable.txt:8251. This is the `orders` table.

### 4.3 `titanksastock` — Chain Stock (per pharmacy, per chain)

From schema_complete.md:197-219 (table 8) and business_logic_complete.md:70-100:

```sql
CREATE TABLE titanksastock (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    drugname   NVARCHAR(100) DEFAULT '',
    datee      REAL DEFAULT 0,
    silsilaid  NVARCHAR(15) DEFAULT '',   -- chain ID
    minimum    REAL DEFAULT 0,            -- minimum stock level (drives shortages)
    pharmacyid NVARCHAR(15) DEFAULT '',   -- FK -> wzphar
    classy     NVARCHAR(35) DEFAULT '',
    stock      REAL DEFAULT 0
)
```

### 4.4 `titanstock` — Stock (per pharmacy, drug-level)

From schema_complete.md:221-241 (table 9):

```sql
CREATE TABLE titanstock (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    drugname   NVARCHAR(100) DEFAULT '',
    lastedit   DATETIME,
    pharmacyid NVARCHAR(15) DEFAULT '',
    price      REAL DEFAULT 0,
    stock      REAL DEFAULT 0,
    barcode    VARCHAR(16) DEFAULT '',
    titanid    INT DEFAULT 0              -- chain sync ID
)
```

---

## 5. Orders — `orders` Table (FormOrder / FormOrderList)

### 5.1 Table: `orders`

From schema_complete.md:295-313 (table 12):

```sql
CREATE TABLE orders (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    orderid    NVARCHAR(50) DEFAULT '',   -- order identifier
    orderdate  DATETIME,                  -- order date
    datee      REAL DEFAULT 0,            -- date (VB6 serial)
    status     NVARCHAR(50) NULL,          -- NULL = pending, 'saved' = completed
    pharmacyid NVARCHAR(15) DEFAULT ''     -- FK -> wzphar
)
```

**Status lifecycle**:
- `status IS NULL` → pending order ("طلبية معلقة"): "طلب معلق يحتاج للحفظ" (a pending order needs saving) — strings_readable.txt:870.
- `status = 'saved'` → completed: `update orders set status='saved' where pharmacyid = N'...' and orderid=N'...'` (schema_complete.md:310).
- Query pattern: `FROM orders where status is null and orderdate= '...'` and `GROUP BY orderid, orderdate, datee, status` (schema_complete.md:308-309).

**Order entry** (FormOrder): create purchase orders to suppliers; pending items awaiting arrival are shown ("ادوية طلبت وفي انتظار ان تصل من المورد") — strings_readable.txt:8251. Order can be converted to a dispensed order: "برجاء تحويل نوع الفاتورة الي طلبية منصرفة من قائمة تحرير اولا" (please convert the invoice type to a dispensed order from the Edit menu first) — strings_readable.txt:9920.

**Group/chain ordering**: "ادخل رقم المجموعة" (enter group number) — 8549; "ادخل رقم جوال موحد لمجموعة صيدلياتك" (enter a unified mobile number for your group of pharmacies) — 8558. This links a pharmacy into a chain/group for joint ordering.

---

## 6. Chain Buy / شراء جماعي (FormChainBuy, ChainBuyStore, ChainBuyUsers, RawakidTablew)

### 6.1 `ChainBuyStore` — Chain Buy Store (table 21)

From schema_complete.md:512-535:

```sql
CREATE TABLE ChainBuyStore (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    DrugName       NVARCHAR(100) DEFAULT '',   -- drug name
    StoreName      NVARCHAR(100) DEFAULT '',   -- store name
    PharmacistTel  NVARCHAR(15)  DEFAULT '',   -- pharmacist phone
    Expire         REAL DEFAULT 0,
    IdDateTime     DATETIME,
    Quant          REAL DEFAULT 0,
    SellDisc       REAL DEFAULT 0,             -- sale discount
    Mohafaza       NVARCHAR(50) DEFAULT '',    -- governorate
    Markaz         NVARCHAR(50) DEFAULT '',    -- center/district
    price          REAL DEFAULT 0
)
INSERT INTO ChainBuyStore ...
SELECT * FROM ChainBuyStore ORDER BY DrugName DESC;
```

### 6.2 `ChainBuyUsers` — Chain Buy Users (table 22)

From schema_complete.md:538-563:

```sql
CREATE TABLE ChainBuyUsers (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    PharmacistTel  NVARCHAR(15) DEFAULT '',
    Expire         REAL DEFAULT 0,
    IdDateTime     DATETIME,
    Quant          REAL DEFAULT 0,
    DrugName       NVARCHAR(100) DEFAULT '',
    SellDisc       REAL DEFAULT 0,
    Mohafaza       NVARCHAR(50) DEFAULT '',
    Markaz         NVARCHAR(50) DEFAULT '',
    Tips           NVARCHAR(50) DEFAULT '',    -- notes
    RequisterTel   NVARCHAR(15) DEFAULT '',    -- requester phone
    country        NVARCHAR(50) DEFAULT '',
    price          REAL DEFAULT 0
)
INSERT INTO ChainBuyUsers ...
SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%...'
```

### 6.3 `RawakidTablew` — Rawakid Table (multi-pharmacy order items) (table 23)

From schema_complete.md:566-595:

```sql
CREATE TABLE RawakidTablew (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    PharmacistTel    NVARCHAR(15) DEFAULT '',
    Expire           REAL DEFAULT 0,
    IdDateTime       DATETIME,
    Quant            REAL DEFAULT 0,
    DrugName         NVARCHAR(100) DEFAULT '',
    SellDisc         REAL DEFAULT 0,
    Mohafaza         NVARCHAR(50) DEFAULT '',
    Markaz           NVARCHAR(50) DEFAULT '',
    SourceIdDateTime DATETIME,
    price            REAL DEFAULT 0,
    Tips             NVARCHAR(50) DEFAULT '',
    RequisterTel     NVARCHAR(15) DEFAULT '',
    country          NVARCHAR(50) DEFAULT ''
)
INSERT INTO RawakidTablew ...
SELECT * FROM RawakidTablew
SELECT * FROM RawakidTablew WHERE PharmacistTel = N'...'
```

**Rawakid (رواكد = dead/slow-moving stock) workflow**:
- Detect dead stock: "الكشف عن الرواكد" (detect the dead stock) — strings_readable.txt:9599; "تطوير الية الكشف عن الرواكد لتصبح اكثر واقعية" (improve dead-stock detection to be more realistic) — 10212.
- Publish your pharmacy's rawakid via the Rawakid screen in the chain menu: "يمكنك الان نشر رواكد صيدليتك عبر شاشة الرواكد في قائمة السلسة في الشاشة الرئيسية" (you can now publish your pharmacy's dead stock via the Rawakid screen in the chain menu on the main screen) — strings_readable.txt:12709.
- Report dead stock: "يمكنك من خلال هذه الشاشة ان تبلغ عن الادوية الراكدة في الصيدلية" (through this screen you can report the dead stock in the pharmacy) — strings_readable.txt:12732.
- Exchange dead stock between pharmacies from the sales screen: "اضافة خدمة تبدال الرواكد ما بين الصيدليات في شاشة المبيعات" (added a service to exchange dead stock between pharmacies in the sales screen) — strings_readable.txt:8911.

**Group buying / chain purchase** (FormChainBuy): links related purchase invoices into a series (modules_gap_2.md:82-100); lists chains in FormChainBuyList (modules_gap_2.md:481-490). It is connected to `FormWared`, `FormWaredList`, `ModBuy`. Store/warehouse settlement: "اختر اسم الشركة او المخزن الذي تود تسديد مستحقاته" (choose the company or warehouse you want to settle dues for) — strings_readable.txt:8368.

**Warehouse (مخزن) stock operations**: add to warehouse — "برجاء ادخال الكمية التي تود اضافتها الي المخزن" (9907?/9897); withdraw from warehouse — "برجاءادخال الكمية التي تود سحبها من المخزن" (9928); "الكمية المتبقية من الرصيد الكلي خارج المخزن لا تكفي" (the remaining quantity of the total stock outside the warehouse is not enough) — 9605; "المخزن" (warehouse) — 9638.

---

## 7. Delivery / توصيل (FormTawsil, FormDrivers, Formdeliver, Moddelivery)

Delivery is the **توصيل (delivery)** of sold items to customers via delivery drivers (طيار الدليفري / عمال التوصيل).

### 7.1 FormTawsil — Delivery management

- **Arabic name**: التوصيل / الدليفري (modules_gap_2.md:312).
- **Purpose**: assign delivery drivers, track delivery status, schedule deliveries, assign customer deliveries (modules_gap_2.md:313).
- **Likely controls** (modules_gap_2.md:318-326): `cmbDriver` (driver selector), `dgDeliveries` (delivery list grid), `txtAddress` (delivery address), `cmbStatus` (delivery status), `btnAssign` (assign driver), `btnTrack` (track delivery), `txtPhone` (customer phone), `btnPrint` (print delivery note).
- **Connections**: `FormDrivers`, `Formdeliver`, `FormSales`, `ModDelivery` (modules_gap_2.md:328).

### 7.2 FormDrivers — السائقين / عمال التوصيل

- Driver directory with availability and contact info (modules_gap_2.md:536-544).
- Controls: `dgDrivers`, `txtName`, `txtPhone`, `cmbStatus`, `btnAdd`, `btnEdit`.
- Connections: `FormTawsil`, `Formdeliver`.

### 7.3 Formdeliver / Moddelivery

- Formdeliver (5 procs) and Moddelivery (3 procs) handle the delivery list and delivery service operations (modules_remaining_2.md:49, 174-184).
- Service label: `خدمة توصيل` (delivery service) — strings_readable.txt:10755; `توصيل` — 10511; `*خدمة*توصيل*` — 1713.
- Data file: `\Files\DBI\delivery.phy` (strings_readable.txt:6781).
- Loading string: `delivery loading ..` (strings_readable.txt:7307).

### 7.4 Driver selection & workflow

- Choose driver: "اختر طيار" (choose driver) — strings_readable.txt:8390.
- Enter driver name first: "ادخل اسم الطيار اولا" (enter the driver name first) — 8453; "اختر عامل اولا" (choose the worker first) — 333?/modules_gap_2.md:332.
- Select the delivery driver by name from the sales screen next to the notes key: "اختيار طيار الدليفري بالاسم من شاشة المبيعات بجوار مفتاح ملاحظات" — strings_readable.txt:8401.
- Query driver work by date and name: "امكانية الاستعلام عن اعمال طيار الدليفري بالتاريخ وبالاسم من قائمة مبيعات ثم امر تقارير التوصيل" (query the delivery driver's work by date and name from the sales menu then the delivery reports command) — strings_readable.txt:9790.

### 7.5 Delivery Reports

From reports_complete.md:595-602:
- **RPT-DEL01: Delivery Reports — تقارير التوصيل**
- **Form**: FormTawsil
- **Columns**: Delivery Date, Customer, Address, Items, Status, Driver, Amount
- English equivalents: `Delivery man` (4314), `Delivery report` (4315), `Cash delivery reports between work periods` (3993).

---

## 8. FormCopyMe — Copy/Transfer Invoices

- **Arabic name**: نسخ لي (copy for me) (modules_gap_2.md:108-128).
- **Purpose**: duplicate an invoice, copy items between invoices, or create a template from an existing invoice.
- Connected to `FormFat`, `FormFatList`, `FormSales`, `FormSalesList`.
- Transfer invoices to another customer: "اختر العميل الذي سيتم نقل الفواتير اليه" (choose the customer to whom the invoices will be transferred) — modules_gap_2.md:128 / strings_readable.txt:8549?.
- Used for converting a saved invoice into a sales-return copy: "يمكنك الغاء حفظ اي فاتورة في اي وقت الا اذا قمت بتقفيل اليوم فلا تملك الا نسخها الي فاتورة مرتجع مشتريات وذلك من قائمة تحرير ثم نسخ" (you can cancel any saved invoice anytime, except after closing the day, then you can only copy it to a purchase-return invoice from the Edit menu then Copy) — strings_readable.txt:12717.

---

## 9. FormHajozat — الحجوزات (Reservations)

- **Purpose**: drug reservation system — hold items for customers (modules_gap_2.md:795-804).
- **Likely controls**: `dgReservations`, `cmbCustomer`, `cmbDrug`, `txtQuantity`, `btnReserve`, `btnRelease`.
- Connections: `FormSales`, `FormFat`.
- Related strings: "هذا الرقم محجوز" (this number is reserved) — strings_readable.txt:12392; "هذا الرقم مسجل باسم مريض اخر" (this number is registered to another patient) — 12393.
- Balance-adjustment requests can be accepted/rejected by the manager: "اصبح من المتاح ان يقوم اي مستخدم بتقديم طلب تعديل الرصيد ويمكن للمدير قبول الطلب او رفضه" (it is now possible for any user to submit a balance-adjustment request and the manager can accept or reject it) — strings_readable.txt:8837; "بعد ان تم تقديم الطلب حدث تعديل علي الرصيد لا يمكن قبول الطلب" (after the request was submitted the balance changed, the request cannot be accepted) — 9945; "الرسالة قادمة فيها نقص في المعلومات ولن يتم قبول الطلب" (the incoming message lacks information and the request will not be accepted) — 9364.

---

## 10. Fields / Data Captured (Summary)

**Transfer (titaninn)**: id, fatid (batch), itemsasstring (serialized lines), datee, source, silsilaid, target.
**Needs (titanneed)**: id, drugname, quant, datee, sender, target.
**Chain stock (titanksastock)**: id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock.
**Stock (titanstock)**: id, drugname, lastedit, pharmacyid, price, stock, barcode, titanid.
**Orders (orders)**: id, orderid, orderdate, datee, status (NULL/'saved'), pharmacyid.
**Chain buy store (ChainBuyStore)**: id, DrugName, StoreName, PharmacistTel, Expire, IdDateTime, Quant, SellDisc, Mohafaza, Markaz, price.
**Chain buy users (ChainBuyUsers)**: + Tips, RequisterTel, country.
**Rawakid (RawakidTablew)**: + SourceIdDateTime.
**Delivery**: delivery.phy; FormTawsil columns (Date, Customer, Address, Items, Status, Driver, Amount); driver directory (name, phone, status).

---

## 11. Side-effects

- **Stock (wzgard / titanstock / titanksastock)**: A transfer/needs fulfillment debits the source pharmacy's stock and credits the target pharmacy's stock. Stock corrections across all pharmacies: "تيتان CorrectStockForAll" (business_logic_complete.md:215). Stock update pattern: `UPDATE titanksastock SET stock = [new] WHERE drugname='[name]'` (business_logic_complete.md:242).
- **Warehouse stock (مخزن)**: add/withdraw quantities to/from the distribution warehouse (strings_readable.txt:9897, 9928).
- **Customer/sub-customer balance**: branch transfers may affect the client balance ("حساب نسبة التحمل للعميل الفرعي" — compute the sub-customer cost-share percentage, strings_readable.txt:10703; "تم اضافة نسبة التحمل للعميل الفرعي من قيمة الفاتورة" — 10372).
- **Inbound invoice archive**: transferred invoices are recorded as inbound (`titaninn`, `titanksasales`); FarWay pushes `ToMain\Inn` and `ToMain\Oot` from branch to main (modules_remaining_1.md:404-405).
- **Sales aggregation per branch**: reports group by `الفرع` (branch) for customers/suppliers/totals (strings_readable.txt:96,100,101).

---

## 12. Pricing + VAT

- **Chain drug pricing**: drugs carry a `price`/`PriceNow` selling price and `vat` percentage per `pharmacyid`; `titanksastock` stores `SellDisc` (sale discount) and `wareprice3` (warehouse price reference).
- **Warehouse margin**: "ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة او غيرها" (enter the warehouse profit margin, usually 1 to 6) — strings_readable.txt:8635.
- **Branch value summary**: the chain screen computes the total value of all drugs at public price: `<div>قيمة كل ادوية الصيدلية بسعر الجمهور = </div>` (value of all pharmacy drugs at public price) — strings_readable.txt:3327 (used in ModFarWay/FormChainBuy).
- **VAT on transfers**: inbound/outbound transfers carry `vatvalue` and `totalwithvat` on `wzgard` stock batches (schema_complete.md:97-98); invoice totals show "اجمالي ض.ق.مضافة" and "اجمالي ضريبة القيمة المضافة 15 بالمائة" (strings_readable.txt:8321 area).
- Price adjustments are shared between the group: "استيراد تعديلات الاسعار من المجموعة" (import price adjustments from the group) — strings_readable.txt:8780.

---

## 13. Payment

- Delivery/invoice settlement uses the standard Titan payment methods (cash/visa/credit أج) captured in `titanksasales` (`payed`, `disc`, `agel`, `totalvalue`) — schema_complete.md:172-193.
- Delivery reports can show cash delivered between work periods: `Cash delivery reports between work periods` — strings_readable.txt:3993.
- Warehouse/company dues settlement: "اختر اسم الشركة او المخزن الذي تود تسديد مستحقاته" — strings_readable.txt:8368.

---

## 14. Printing

- **Delivery note**: `btnPrint` prints the delivery note for the selected delivery (modules_gap_2.md:326).
- **Receipt & barcode on sub-devices**: "اضافة امكانية طباعة الريسيت والباركود من الاجهزة الفرعية" (added the ability to print receipt and barcode from sub-devices) — strings_readable.txt:8943; "الطباعة في الاجهزة الفرعية" (printing in sub-devices) — 9458.
- **Transfer/delivery reports**: FormTawsil prints تقارير التوصيل (reports_complete.md:597-601). Chain reports via FormSilsila (reports_complete.md:607).

---

## 15. UI Strings (Arabic + English labels)

### Transfer (التحويل)
| Arabic | English | Ref |
|--------|---------|-----|
| تحويل | Transfer | strings_readable.txt:10109 |
| تحويل واسترجاع الاصناف | Transfer & return items | 10110 |
| تحويل الفاتورة الي صيدلية اخري | Transfer the invoice to another pharmacy | 10112 |
| تحويل الي طلبية محولة | Convert to a transferred order | 10113 |
| متابعة التحويلات ما بين الصيدليات | Follow transfers between pharmacies | 11988 |
| متابعة الطلبيات المحولة | Follow transferred orders | 11990 |
| تم النقل الي قائمة التحويل | Moved to the transfer list | 10397 |
| تم تحويل الفاتورة | Invoice transferred | 10413 |
| ادخل رقم الربط السحابي للفرع المراد التحويل اليه | Enter cloud-link number of branch to transfer to | 8541 |
| استيراد فاتورة محولة من مستودع او صيدلية اخري | Import transferred invoice from warehouse/pharmacy | 8783 |
| ادخل رقم التسجيل الضريبي او رقم الربط السحابي اذا كان المورد صيدلية | Enter tax reg/cloud-link if supplier is a pharmacy | 8538 |
| تحسين خدمة تصدير الفواتير ما بين افرع الصيدليات | Improve invoice export between branches | 10094 |
| تمرير الطلبيات من صيدلية الي اخري اونلاين | Pass orders between pharmacies online | 12734 |

### Cloud-link (الربط السحابي)
| Arabic | English | Ref |
|--------|---------|-----|
| الربط السحابي | Cloud linking | 9356 |
| رقم موبايل الربط السحابي للمجموعة | Group cloud-link mobile | 10912 |
| جاري الان الربط السحابي | Cloud linking in progress | 637 |
| رصيد الاصناف في الفروع متاحة فقط في حالة ربط المجموعه | Branch stock available only if group linked | 10869 |
| يمكنك الان اضافة فواتير علي نسخ الربط السحابي | Add invoices on cloud-link copies | 12707 |

### Needs (النواقص)
| Arabic | English | Ref |
|--------|---------|-----|
| النواقص | Shortages / Needs | 9734 |
| Needs - Manual system | النواقص - نظام يدوي | 5419 |
| Needs - Half manual system | النواقص - نصف الالي | 5418 |
| Needs - salses rate system (automatic) | النواقص - نظام معدل المبيعات | 5420 |
| ادخل الكمية التي تود طلبها | Enter the quantity you want to order | 8503 |
| الكمية التي طلبتها اقل من الحد الادني للطلب | Requested quantity below minimum order level | 9602 |
| أضافه الي النواقص | Add to shortages | 8923/8926 |

### Orders (الطلبيات)
| Arabic | English | Ref |
|--------|---------|-----|
| الطلب / طلبية | Order | modules_gap_2.md:1052 |
| قائمة الطلبات | Order list | 1068 |
| أدوية طلبت وفي انتظار ان تصل من المورد | Drugs ordered awaiting supplier | 8251 |
| طلب معلق يحتاج للحفظ | Pending order needs saving | 870 |
| طلبية منصرفة | Dispensed order | 9920 |

### Delivery (التوصيل)
| Arabic | English | Ref |
|--------|---------|-----|
| توصيل | Delivery | 10511 |
| خدمة توصيل | Delivery service | 10755 |
| تقارير التوصيل | Delivery reports | 10300 |
| اختر طيار | Choose driver | 8390 |
| ادخل اسم الطيار اولا | Enter driver name first | 8453 |
| اختر عامل اولا | Choose the worker first | modules_gap_2.md:332 |
| طيار الدليفري | Delivery driver | 8401 |
| Delivery man | السائق / رجل التوصيل | 4314 |
| Delivery report | تقرير التوصيل | 4315 |

### Rawakid (الرواكد)
| Arabic | English | Ref |
|--------|---------|-----|
| الرواكد | Dead stock | — |
| الكشف عن الرواكد | Detect dead stock | 9599 |
| نشر رواكد صيدليتك عبر شاشة الرواكد | Publish your dead stock via Rawakid screen | 12709 |
| تبدال الرواكد ما بين الصيدليات | Exchange dead stock between pharmacies | 8911 |
| ابلاغ عن الادوية الراكدة | Report dead drugs | 12732 |

---

## 16. Business Rules / Edge Cases

1. **Branch group linkage required** — branch stock is only visible/transferable when the pharmacy belongs to a linked group (المجموعة): strings_readable.txt:10869. Group numbers are entered via "ادخل رقم جوال موحد لمجموعة صيدلياتك" (8558).
2. **Cloud-link copies are read-only for sales** — the cloud-link copy cannot be used to create sales invoices: "يمكنك الان اضافة فواتير علي نسخ الربط السحابي" but "التمييز ما بين النسخة الاصلية ونسخة الربط السحابي حيث ستم منع عمل فواتير البيع علي نسخة الاستدعاء" (distinguish original vs cloud-link copy; sales invoicing is blocked on the recall copy) — strings_readable.txt:9266; "يبدو انك تحاول استمرار عملك علي نسخة مخصصة للربط السحابي وهذا غير مسموح لامان بياناتك" (continuing work on a cloud-link copy is not allowed for data safety) — 12609.
3. **Transfer target cleared on completion** — `update titaninn set target = N''` indicates the transfer is received (strings_readable.txt:810).
4. **Minimum-level shortage rule** — an item is a shortage when `stock < minimum`; requested quantity below minimum order level is rejected (9602). "هذا الصنف ممنوع من الظهور في النواقص" (this item is blocked from appearing in shortages) — strings_readable.txt:12422; "هذا الصنف متاح للظهور للنواقص فعلا" (this item is actually available to appear in shortages) — 12420.
5. **Manager approve/reject for balance adjustments** — requests to adjust balance are accepted/rejected by the manager (8837); if the balance changed after submission the request is rejected (9945).
6. **Transferred invoice conversion** — an invoice must be converted to a dispensed/transferred order before transfer ("برجاء تحويل نوع الفاتورة الي طلبية منصرفة من قائمة تحرير اولا", 9920).
7. **FarWay heartbeat** — the branch writes `i-am-runing.txt` as an online indicator; data flows FromMain and ToMain (Inn/Oot) for file-based offline sync (modules_remaining_1.md:402-406).
8. **Sub-device availability** — sub-devices can create sales/purchase invoices only if the full-link mode is enabled ("السماح بالاجهزة الفرعية في طريقة الربط الكاملة بانشاء فواتير مبيعات جديدة", 9391); main device pulls branch invoices with the dollar key (10371).
9. **Supplier = pharmacy** — when a supplier is another pharmacy (not a warehouse), the tax registration or cloud-link number identifies it (8538).
10. **Order status** — an order is pending while `status IS NULL`; setting `status='saved'` completes it (schema_complete.md:303, 310).
11. **Warehouse stock limits** — the remaining total stock outside the warehouse must be sufficient when transferring/withdrawing (9605).
12. **Rawakid publication** — dead stock is published via the chain menu and exchanged between pharmacies from the sales screen (12709, 8911).

---

## 17. Network/Chain Sync Endpoints (how branches actually exchange data)

- **Data flow** (network_complete.md:653-662): Local Titan data → export CSV/XML → FTP/HTTP upload → cloud storage → other Titan instance downloads → import into local DB.
- **Cloud user data paths** for branch sync (network_complete.md:339-359): `/titan-users/allinone/data/`, `/titan-users/titan-mobile/files/`, `/titan-users/send-to/`, `/titan-users/fary-net/`.
- **Chain tables synced** (network_complete.md:602-615): `titanstock`, `titanksastock`, `titanksasales`, `titaninn`, `titanneed`, `titanpharmalist`, `usersourceupdate`, `remotecontrol`, `orders`.
- **Silsila (السلسلة)**: every transaction carries a `silsilaid` chain ID used by FormSilsila chain reports and group aggregation (reports_complete.md:607-612; schema_complete.md).
- **Group pharmacy registration**: "اضافة صيدليات المجموعة" (add group pharmacies) — strings_readable.txt:8912; "اضف صيدليات المجموعة من قائمة متقدم" (add group pharmacies from the advanced menu) — 9009; "الغاء ربط الصيدلية الحالية بالمجموعة" (unlink current pharmacy from the group) — 9484.
- **Multi-branch stock reporting**: "تم تطوير الية رفع ارصدة الادوية لصيدليات المجموعة لتشمل كل الادوية حيث كانت قاصرة سابقا علي الادوية التي تم بيعا في المبيعات" (improved raising drug balances for group pharmacies to include all drugs, previously only sold drugs) — strings_readable.txt:10417.

---

## References (file:line)

- schema_complete.md:146-168 (titaninn), 197-219 (titanksastock), 221-241 (titanstock), 243-259 (titanneed), 295-313 (orders), 512-535 (ChainBuyStore), 538-563 (ChainBuyUsers), 566-595 (RawakidTablew)
- network_complete.md:602-615 (chain tables), 322-359 (cloud sync), 653-662 (data flow)
- business_logic_complete.md:70-138 (chain tables), 160-163 (ChainBuy), 236-254 (stock ops)
- reports_complete.md:595-602 (delivery reports), 605-612 (chain reports), 349-398 (shortage reports)
- modules_gap_2.md:82-100 (FormChainBuy), 108-128 (FormCopyMe), 308-328 (FormTawsil), 481-490 (FormChainBuyList), 536-544 (FormDrivers), 795-804 (FormHajozat), 1048-1073 (FormOrder/List), 1159-1181 (FormTahwil/List)
- modules_remaining_1.md:388-409 (ModFarWay)
- modules_remaining_2.md:49 (FormDeliver), 174-184 (Moddelivery)
- strings_readable.txt:637, 870, 3327, 3535-3536, 3993, 4314-4315, 5416-5421, 6781, 7307, 7607, 8251, 8262, 8390, 8401, 8453, 8503-8505, 8538, 8541, 8549, 8558, 8635, 8783, 8911, 8912, 8943, 9009, 9391, 9393, 9458, 9484, 9602, 9605, 9638, 9790, 9897, 9920, 9928, 9945, 10005, 10060, 10094, 10109-10118, 10211, 10212, 10215, 10222, 10300, 10371, 10372, 10397, 10413, 10416, 10417, 10475, 10477, 10500-10501, 10507, 10511, 10703, 10755, 10860, 10869, 10906, 10912, 11988-11990, 12420, 12422, 12609, 12707, 12709, 12717, 12732, 12734
