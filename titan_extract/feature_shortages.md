# Feature: Shortages / Out-of-Stock Detection (نواقص)

## Purpose
The shortages feature continuously detects drugs that are **out of stock** or **below
their minimum level**, and supports **generating order lists** (auto-order) to
restock them. Titan implements **three shortage systems** (manual, half-automatic
minimum-level, and automatic sales-rate), which in later versions are combined into a
single screen (النواقص المجمعة).

---

## 1. Objects

| Object | Type | # procs | Address | Role |
|---|---|---|---|---|
| `ModStock` | Class | ~165 | `0x00ad4a50`+ | Stock engine; evaluates `stock` vs `minimum` |
| `ModNed` | Class | several | (search `Class ModNed`) | Needs/shortage calculation engine |
| `ModStorage` | Module | many | — | Storage helpers feeding stock/minimum data |
| `FormMinimumControl` | Form | 23 | `0x009ca240`+ | Set the minimum stock level (حد الطلب / حد ادني) per drug |
| `FormAutoOrder` | Form | 43 | `0x0097b6fc`+ | Automatic order / restock list generation |
| `FormNeedsAll` | Form | 50 | `0x00972d14`+ | All-needs management (النواقص المجمعة), combined systems |
| `FormNeedsDetails` | Form | 9 | `0x00962af4`+ | Per-drug needs details |
| `FormNedBirbish` | Form | 6 | `0x009c040c`+ | Needs calculation helper |
| `FormStockNow` | MDIForm | several | `0x009bea80`+ | Current stock view (drives shortage detection) |
| `FormSilsila` / `FFFSilsilaStock` | Form/MDIForm | 26 / 2 | `0x009d4058`+ / `0x009e2fcc`+ | Chain pharmacies & chain stock (branch shortages) |
| `ModStockTest` | Module | — | — | Stock test helpers |

---

## 2. Step-by-step workflow

### 2.1 The three shortage systems
Titan's needs system is described as **3 systems** (idx 13017):
`نظام النواقص في تيتان يشتمل علي 3 انظمة`.

1. **Manual system (النظام اليدوي)** — the pharmacist manually registers shortages in
   a notebook screen (كشكول النواقص). `كشف النواقص بنظام التسجيل اليدوي`.
2. **Minimum-level / half-automatic (الحد الادني / نصف الالي)** — a minimum is set per
   drug; if `stock < minimum` the drug is flagged a shortage
   (idx 13225/13362: `يعتبر الدواء ناقصا اذا قل رصيده عن الحد الادني الموجود في شاشة تعديل بيانات الادوية`).
3. **Sales-rate automatic (معدلات الصرف / تلقائي)** — shortages are computed from
   recent sales rates (كشف النواقص بنظام معدلات الصرف).

Later versions combined all three into one screen (النواقص المجمعة, idx 13113).

### 2.2 Automatic detection (استكشاف النواقص تلقائيا)
- **استكشاف النواقص تلقائيا** (idx 9415) — automatic shortage discovery command.
- **التعرف التلقائي علي نواقص اخر شهر** (idx 9905) — automatically identify the
  shortages of the last month.
- The command **حصر كافة الادوية التي يقل رصيدها الحالي عن الحد الادني ولم يتم وضعه في
  احدي صفحات النواقص** (idx 13371) — gather all drugs below minimum that are not yet
  on any shortage page.

### 2.3 Setting the minimum level (FormMinimumControl)
- The user sets the minimum per drug:
  `ادخل الحد الادني - الحد الذي اذا قل الرصيد عنه يجب الشراء` (idx 9123).
- Setting a drug's minimum to **0** removes it from the shortage list
  (idx 12183: `اضغط علي الصنف الذي تود تعديل الحد الادني له وادخل صفر وبالتالي لن يظهر لك مجددا في قائمة الادوية الناقصة`).
- **حظر ظهور صنف في النواقص** (idx 9588) — option to block a drug from appearing in
  shortages at all.

### 2.4 Generating an order list (auto-order)
- From the shortage list, the user generates an **automatic order** (FormAutoOrder)
  to restock. Orders can be **saved to sales** (`Save Order To sales`, idx 6261).
- The order is stored in `orders` (status NULL = pending, `saved` = done) and/or
  `titanneed` for inter-pharmacy needs (sender/target).
- Shortage pages are paginated; there is a maximum number of shortage drugs per page
  (idx 11054: `تم الوصول الي الحد الاقصي من الادوية الناقصة ... سجل في صفحة اخري`).

### 2.5 Shortage list UX
- Drugs are ordered by the time they were added to the shortage table
  (idx 12003: `عند اضافة دواء الي جدول النواقص فان تيتان يحتفظ بهذا الوقت كمعلومة يتم علي اثرها ترتيب عرض الادوية`).
- Clicking a shortage drug shows today's discounts in warehouses
  (idx 12126: `في النواقص يمكنك الضغط علي الصنف لمعرفة خصوماته في المخازن اليوم`).
- Shortage items that are already ordered from companies form a separate read-only
  list (idx 13145-13146).
- In sales invoices, shortage drugs are highlighted **red** (idx 13041), and drugs
  with messages are **purple/violet** (idx 13239).

---

## 3. Fields / data captured

### Minimum / needs fields
- **Drug name** (drugname)
- **Current stock** (stock / الرصيد الحالي)
- **Minimum level** (minimum / الحد الادني)
- **Shortage / deficit** = `minimum - stock`
- **Monthly quantity & monthly value** (عدد شهري / قيمة شهرية)
- **Last purchase** date (اخر شراء)
- **Sales rate** (معدل الصرف) for the automatic system
- **Days** parameter for "shortages of recent days" (idx 9223: `ادخل عدد الايام ثم اضغط عرض النواقص`)

### `titanstock` / `titanksastock` `minimum` column
- `titanksastock.minimum` and `titanstock` carry the minimum threshold per drug
  (schema idx 912 insert, idx 960 `minimum real default '0'`).

### `titanneed` (inter-pharmacy needs)
| Column | Meaning |
|---|---|
| `id` | identity PK |
| `drugname` | FK → wzdrugs |
| `quant` | quantity needed |
| `datee` | date |
| `sender` | requesting pharmacy |
| `target` | fulfilling pharmacy |

### `orders` (auto-order)
| Column | Meaning |
|---|---|
| `id` | identity PK |
| `orderid` | order identifier |
| `orderdate` / `datee` | order date |
| `status` | NULL = pending, `saved` = done |
| `pharmacyid` | pharmacy |

---

## 4. Side-effects

### Stock
- Shortage detection is **read-only** on stock: it evaluates `stock` vs `minimum`
  and does not modify `wzgard`.
- When an order is fulfilled/restocked, normal purchase processing posts to `wzgard`.

### Money
- Auto-order may be **saved to sales** (`Save Order To sales`), which then follows the
  sales/purchase money flows documented in business_logic_complete.md §16.

### Chain / branch
- `titanneed` records needs between pharmacies (sender→target).
- Branch shortages can be aggregated in one screen (تجميع كل نواقص الصيدليات التابعة لك
  في شاشة واحدة, idx 10716).

### Audit / coloring
- Drugs flagged as shortages are colored in sales screens (red) and message-bearing
  drugs are colored violet — a cosmetic side-effect on sales views.

---

## 5. Pricing + VAT
- Auto-order quantities are computed from `minimum - stock` and/or sales rates; the
  resulting order is valued at the drug's purchase price + VAT when converted to a
  purchase/sales order.
- Shortage report columns include the price (السعر شامل الضريبة) and totals.

---

## 6. Payment
- Shortage detection does not itself create payments. If an auto-order is **saved to
  sales**, payment follows the standard cash/visa/credit (أج) flow of a sales invoice.

---

## 7. Printing
- **تقارير النواقص** (Shortage reports, idx 10962) — see reports_complete.md RPT-ST01..ST06.
- Report layouts use print-form numbers (500/600/700/800).
- Column header used: `مسلسل | الصنف | السعر | الخصم | اجمالي المباع | تكلفة المباع | الرصيد الحالي | ...`.
- HTML shortage dashboards exist (divneed = النواقص وفقا للحد الادني, idx 3318).

---

## 8. Tables

- `wzdrugs` (`stock`, `price`, `vat`) — source of current stock & price
- `titanstock` / `titanksastock` (`minimum`, `stock`) — threshold & current balance
- `titanneed` — inter-pharmacy needs
- `orders` — auto-order list
- `invoicedata` (`Minimum`, `Quant`, `DrugName`) — invoice-level minimum snapshot
- `wzgard` — stock ledger (fulfillment side)
- `farysales` — branch valuation

---

## 9. UI strings (Arabic)

| String | idx | Meaning |
|---|---|---|
| النواقص | 13043/10382 | Shortages (title) |
| نواقص الفاتورة الحالية | 13044 | Shortages of current invoice |
| النواقص وفقا للمبيعات | 10383 | Shortages by sales |
| النواقص وفقا للحد الادني | 3318 | Shortages by minimum level |
| استكشاف النواقص تلقائيا | 9415 | Discover shortages automatically |
| التعرف التلقائي علي نواقص اخر شهر | 9905 | Auto-identify last-month shortages |
| كشف النواقص بنظام التسجيل اليدوي | 1109 | Shortages – manual registration |
| كشف النواقص بنظام حد الطلب | 12263 | Shortages – order-limit system |
| كشف النواقص بنظام معدلات الصرف | 12264 | Shortages – sales-rate system |
| نظام النواقص في تيتان يشتمل علي 3 انظمة | 13017 | Three shortage systems |
| النظام الثالث يعتمد علي الادخال اليدوي في شاشة كشكول النواقص | 10374 | System 3 = manual notebook entry |
| النظام الثاني يعتمد علي ادخال حد الطلب لكل الاصنف ... | 10376 | System 2 = minimum/order-limit |
| ادخل الحد الادني - الحد الذي اذا قل الرصيد عنه يجب الشراء | 9123 | Enter minimum level |
| الحد الادني | 1113 | Minimum level |
| يعتبر الدواء ناقصا اذا قل رصيده عن الحد الادني | 13362 | Drug is short if stock < minimum |
| حد الطلب | 9618 | Order limit |
| معدلات الصرف | 10088 | Sales rates |
| الادوية الناقصة | 9747 | Short drugs |
| ناقص عمومي | 12635 | Generally short (flag 1) / available-in-market-but-out-of-stock (0) |
| الشاشة العامة للنواقص / النواقص المجمعة | 13113/11764 | Combined shortage screen |
| اضافة الي النواقص - النظام اليدوي | 9574 | Add to shortages – manual |
| اضافة نواقص | 9645 | Add shortage |
| تمت اضافة هذا الدواء الي النواقص | 11116 | Drug added to shortages |
| تمت اضافته الي النواقص مؤخرا | 11117 | Recently added to shortages |
| حظر ظهور صنف في النواقص | 9588 | Block drug from shortages |
| هذا الصنف ممنوع من الظهور في النواقص فعلا | 13085 | Drug is actually blocked |
| هذا الصنف متاح للظهور للنواقص فعلا | 13080 | Drug is actually allowed |
| Not Enouph Stock | 439 | Not enough stock |
| لقد وجد البرنامج اكثر من 500 دواء ناقص ... | 12561 | More than 500 shortage drugs warning |
| ادخل رقم صفحة النواقص | 9180 | Enter shortage page number |
| ادخل عدد الايام ثم اضغط عرض النواقص | 9223 | Enter days then show shortages |
| تقارير النواقص | 10962 | Shortage reports |
| Save Order To sales | 6261 | Save order to sales |
| منعت تصحيح صلاحيات الاصناف تلقائيا | — | Auto power-correction off (edge) |

---

## 10. Business rules / edge cases

1. **A drug is "short" when `stock < minimum`** (idx 13362). The minimum is set in the
   drug-edit screen and via FormMinimumControl.
2. **Setting minimum to 0 removes a drug** from the shortage list (idx 12183).
3. **Blocks are honored** — a drug can be blocked from appearing in shortages
   (idx 9588); the UI confirms actual block/allowed state (idx 13080/13085).
4. **Three independent systems** — manual, minimum-level (half-auto), sales-rate
   (auto) each run in their own screen, and later are combined in النواقص المجمعة.
5. **Automatic monthly discovery** — التلقائي علي نواقص اخر شهر scans for the previous
   month's shortages.
6. **Pagination & cap** — shortage pages cap at a max; more than ~500 shortage drugs
   triggers a warning (idx 12561, 11054).
7. **Ordering preserves recency** — list order is based on when the drug was added to
   the shortage table (idx 12003).
8. **Auto-order → sales conversion** — an order can be saved to sales, linking
   shortages to the purchasing/sales money flow.
9. **Sales-rate method needs sales history** — for the automatic method, Titan shows
   only drugs whose balance dropped within the recent days/period (idx 9317).
10. **Coloring** — shortage drugs are red in sales; message-bearing drugs are violet
    (idx 13041, 13239); coloring can be toggled off (idx 13380).
