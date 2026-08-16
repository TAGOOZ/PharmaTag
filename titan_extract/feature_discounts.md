# TITAN.W1 (Phye.exe) — Feature: خصومات شركات ومخازن (Company & Warehouse Discounts)

**Purpose:** Full extraction of the discount subsystem of TITAN.W1 (Phye.exe, VB6 p-code) that models and applies **company** (supplier/شركة) discounts and **warehouse** (مخزن/المستودع) discounts — the negotiated per-drug discount percentages a pharmacy receives from suppliers or sells to warehouses across a multi-branch/network chain. Covers the `storediscount` data model, the `ModDisc` discount engine, the `FormStoreDiscount` setup screen, the warehouse-discount viewing permission, drug-price comparison and discount-correction screens, and how discounts feed pricing + VAT in sales/purchase invoices.

This document is **self-contained** and is built on (and cites) the existing extraction docs in `titan_extract/`: `schema_complete.sql`/`schema_complete.md`, `business_logic_complete.md` (§16/§19), `config_complete.md`, `permissions_complete.md`, `reports_complete.md`, `ui_complete.md`, `modules_gap_1.md`, `feature_sales_invoices.md`, `feature_purchases.md`, `feature_shortages.md`, plus the decoded p-code string tables (`titan_decompile/strings_utf16.txt`, `strings_readable.txt`) via `/tmp/opencode/pcode_strings.py`.

---

## 1. Objects (Modules / Forms / Procedures)

| Object | Kind | Addr(s) | Role |
|--------|------|---------|------|
| `ModDisc` | Module | `0x0093dbec`, `0x0093f26c`, `0x0091ad1c`, `0x0094d934`, `0x00971554`, `0x0094c800`, `0x008dfcfc`, `0x00989268`, `0x00929c58`, `0x00910478` (10 procs, `start=271412..271889`) | **Discount engine** — multi-tier discount calculation for sales/purchases: percentage-based, per-item, and cumulative stacking across invoice line items (`modules_gap_1.md:8-33`). |
| `FormStoreDiscount` | Form | `0x00a3de2c`..`0x009534d4` (26 procs, `start=488164..491436`) | **Company/warehouse discount setup + report** — UI to record/store negotiated discount agreements per store; also the تقرير خصومات المخازن report screen (`reports_complete.md:539-544`). |
| `FormDrugsCompare` | Form | `0x00a79cac` region (`start~682451`) | Compare drug prices across branches/regions; filters by `Mohafaza` (محافظة) — `' and Mohafaza LIKE N'%` (`proc FormDrugsCompare`). |
| `FormDiscCorrect` | Form | `0x00a79cac`, `0x009feebc`, `0x00907db8`, `0x009fce14` (4 procs, `start=357577..358108`) | **Discount correction** — correct/repair recorded discount values. |
| `FormDiscountControl` | Form | (found in inventory) | Discount control / management screen. |
| `ModOrood` | Module | — | Promotional offers/discounts (عروض: buy-X-get-Y) — separate, but shares the discount-calculation path (`modules_remaining_1.md:294-309`). |

Related sales/purchase engine objects (see `feature_sales_invoices.md`, `feature_purchases.md`):
- `ModOot` (sales/outbound, `business_logic_complete.md` §16) — applies `SellDisc`, `disc`, VAT in sales.
- `ModInn` (purchases/inbound) — records buy discount (خصم الشراء) into `storediscount`.
- `FFFWaredMonsaref` — supplier/warehouse settings screen (unified purchase discount, importer discount) (`feature_purchases.md:26,122`).

---

## 2. Step-by-Step Workflow

### 2.1 Setting up a company / warehouse discount agreement (FormStoreDiscount)
1. Open **FormStoreDiscount** (تقرير خصومات المخازن / Store Discount setup).
2. Identify the **branch/address** (`adress`) and **store name** (`storename`) being configured (a warehouse مخزن or pharmacy that is a trading partner).
3. Identify the **pharmacy name(s)** involved (`pharmacyname`, `pharmacyname2` — e.g. the pharmacy granting and the pharmacy receiving the discount).
4. Pick the **drug** (`drugname`, FK → `wzdrugs`) and its **barcode** (`barcode`).
5. Enter the **price** (`price`) and the negotiated **discount %** (`disco`).
6. Enter **units** (`units`) and **quantity** (`quant`), plus `tips` (notes/type) and `datee`.
7. The record is upserted: `if not exists (select * from storediscount ...)` then `insert into storediscount (adress,storename,pharmacyname,pharmacyname2,datee,tips,titanver,country,drugname,barcode,price,disco,units,pricechanged,localimport,quant) values(...)` (`schema_complete.md:361-366`).

### 2.2 Applying a discount during a sale (ModOot / ModDisc)
1. As items are added to a sales invoice, the engine queries the drug's configured discount(s).
2. ModDisc computes the applicable discount % using `MulR8`/`DivR8`/`SubVar` arithmetic on percentages; discount *types* are discriminated (mode compare vs `1`,`2`,`3`; code `0x00DF`/223 as a type discriminator) (`modules_gap_1.md:13-17`).
3. Per-line **sale discount** `SellDisc` is set; a whole-invoice discount may also be applied (`feature_sales_invoices.md:57`).
4. **Price/discount sanity check** — "Abnormal Discount" detection and `سعر احد الاصناف غير منطقية` warning for outlier values (`feature_sales_invoices.md:56,144`).
5. **Discount, then VAT** — Discount is computed on the subtotal BEFORE VAT (see §5).
6. Save invoice (F9) — writes `titanksasales` (header with `disc`) and `invoicedata` (per line with `SellDisc`).

### 2.3 Viewing warehouse discounts in your governorate (network/multi-branch)
- A permission toggle exists: **اتاحة الاطلاع علي خصومات المخازن في محافظتك** = "Allow viewing warehouse discounts in your governorate" (`strings_readable.txt:8266`).
- Related subscription gating: **التعرف علي خصومات المخازن للمشتركين فقط** = "Knowing warehouse discounts for subscribers only" (`strings_readable.txt:9258`), and column/term **خصومات المخازن** (`strings_readable.txt:10796`).
- The shortages screen lets a user click a drug to see **today's discounts in warehouses**: `في النواقص يمكنك الضغط علي الصنف لمعرفة خصوماته في المخازن اليوم` (idx 12126, `feature_shortages.md:73-74`).

### 2.4 Comparing drug prices (FormDrugsCompare)
- Browse/compare a drug's price across branches, filtered by governorate (`Mohafaza LIKE N'%'`). Useful to see the differing discount/price agreements negotiated with each warehouse in the region.

### 2.5 Correcting discounts (FormDiscCorrect)
- Adjust/correct recorded discount values (repairs a previously saved `storediscount`/invoice discount). Low-string proc (`رابعا` idx 11519, `Start` idx 6399), i.e. the bulk of logic is arithmetic/code, few user-visible strings.

---

## 3. Fields / Data Captured

### 3.1 FormStoreDiscount fields
Company/warehouse, store, pharmacy names, drug, barcode, price, discount %, units, quantity, date, notes/type, version, country, price-changed flag, import flag — mapped 1:1 onto the `storediscount` columns below.

### 3.2 Supplier settings (FFFWaredMonsaref) — company discount agreement fields
- Supplier name, bank account, opening dues balance.
- **Unified purchase discount** (ادخل خصم شراء موحد).
- **Importer/company discount** (ادخل خصم المستورد لهذه الشركة).
- Tax registration no. / cloud link (if the supplier is itself a pharmacy), supplier GLN.
(`feature_purchases.md:122`)

---

## 4. Side-effects

- **`storediscount`** — the primary write target on every purchase (and setup): per-drug purchase discount history is inserted (`feature_purchases.md:150`).
- **`titanksasales` / `invoicedata`** — sales/return headers record `disc` (total) and per-line `SellDisc`.
- **`wzgard` (stock)** — stock cost with/without VAT (cost basis reflects the discount already applied at purchase).
- **`wzcustomers` (customer balances)** — invoice totals net of discount drive accrued balances.
- **`wzmony`/`wzdaily`/`wzbank` (money)** — the discounted net total is what is settled.
- **Purchase returns** — return reverses the storediscount history for the returned items (`feature_purchase_returns.md:97,146,184`).
- **Account closing** — خصومات اليوم (today's discounts) is one of the daily aggregates in the closing report (`feature_account_closing.md:67,107`).

---

## 5. Pricing + VAT formulas

Core sale-line arithmetic (same in sales, returns, and purchases; see `feature_sales_invoices.md:134-136`, `feature_sales_returns.md:86-88`):

```
Line     = Qty × price                       (per drug line)
Subtotal = Σ Line
Discount = Subtotal × (SellDisc / 100)      ← applied BEFORE VAT
VAT      = (Subtotal − Discount) × (VAT% / 100)
Total    = Subtotal − Discount + VAT
```

For the whole invoice, `disc` (REAL) is the total discount; the invoice footer prints subtotal → discount → after discount → VAT → total (`reports_complete.md:748-777`).

### 5.1 Discount types (ModOot §6.4 / business_logic §3.3)
- **Disc in (input / شراء)** — purchase discount.
- **Disc out (output / بيع)** — sale discount.
- **Cash discount** — for cash payment.
- **Wholesale discount** — bulk purchase margin.
- **Warehouse discount** (`werehouse discounts`) — warehouse-level (`business_logic.md:142-145`).
- **Tax-item sale discount** — "Apply a sale discount for tax items" (`config_complete.md:95`).
- **Last-purchase discount** — "Apply the discount of the last purchase", "جعل خصم شراء الدواء هو اخر خصم" (idx 11268) (`modules_gap_1.md:27`, `feature_purchases.md:69`).
- **Unified supplier / importer-company discount** — per-supplier constant (`feature_purchases.md:181`).
- **Discount modes**: `Discount by currency`, `Discount by percent of profit value`, `Discount by percent of total value` (`modules_gap_1.md:26`).
- Arithmetic tags used in generated HTML/XML discount summaries: `<purchases-disco>`, `<sales-disco>`, `<sales-with-vat-no-disc>` (`modules_gap_1.md:31`).

### 5.2 VAT interplay
- VAT rate configurable per item (Egypt 14%, Saudi 15%; default 15% in reports) — discount is subtracted before VAT is computed, so **VAT is not charged on the discounted portion** (`business_logic_complete.md` §19 / `business_logic.md:434-487`).
- Setting: "Apply a sale discount for tax items" controls whether discount reduces the tax base.

---

## 6. Payment methods

Discounts are orthogonal to payment method. The discounted net total (`Total` above) is then settled by the normal methods — cash (كاش), card/network (شبكة), or credit/deferred (أج) — as in the standard sales flow (`feature_sales_invoices.md:158`; `business_logic_complete.md` §16). Payment entry prompts: `ادخل ما دفعه المريض ليتم حساب الباقي بعد خصم قيمة الفاتورة` (idx 12527).

---

## 7. Printing

- **FormPrintSales** prints the invoice template (A4/A5) whose footer includes **Subtotal قبل الخصم / Discount الخصم / After Discount بعد الخصم / VAT / Total** (`feature_sales_invoices.md:168`, `reports_complete.md:748-777`).
- **FormStoreDiscount** doubles as the **تقرير خصومات المخازن** (Store/warehouse Discounts Report) — columns: Store, Drug, Discount Type, Discount Value, Effective Date (`reports_complete.md:539-544`).
- Aggregate queries supporting the report (`schema_complete.md:363-365`):
  - `select drugname,count(*),max(disco),min(disco),max(datee) from storediscount where adress=`
  - `select pharmacyname,adress,count(*),max(datee) from storediscount`
  - `select storename,count(*) from storediscount where adress=`

---

## 8. Tables

### `storediscount` — Discount Records (17 columns, table 14) (`schema_complete.md:335-368`, `schema_complete.sql:213-233`)

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `adress` | NVARCHAR(200) | `''` | Branch/address (the store whose discount is recorded) |
| `storename` | NVARCHAR(100) | `''` | Store name (الفرع/المخزن) |
| `pharmacyname` | NVARCHAR(100) | `''` | Pharmacy name (granting pharmacy) |
| `pharmacyname2` | NVARCHAR(100) | `''` | Pharmacy name (alt / receiving pharmacy) |
| `datee` | REAL | `0` | Date (OLE serial) |
| `tips` | NVARCHAR(50) | `''` | Notes/type (خصم شراء/بيع discriminator) |
| `titanver` | NVARCHAR(50) | `''` | Titan version |
| `country` | NVARCHAR(50) | `''` | Country |
| `drugname` | NVARCHAR(100) | `''` | **FK → wzdrugs** |
| `barcode` | VARCHAR(16) | `''` | Barcode |
| `price` | REAL | `0` | Price (at which discount applies) |
| `disco` | REAL | `0` | **Discount %** (the negotiated percent) |
| `units` | INT | `0` | Units |
| `pricechanged` | BIT | `0` | Price changed flag |
| `localimport` | INT | `0` | Import flag |
| `quant` | REAL | `0` | Quantity |

**SQL evidence:** `insert into storediscount (adress,storename,pharmacyname,pharmacyname2,datee,tips,titanver,country,drugname,barcode,price,disco,units,pricechanged,localimport,quant) values(...)`; `select * from storediscount where adress=`; `if not exists (select * from storediscount ...)`; `order by drugname desc, disco desc` (`schema_complete.md:359-368`).

Relations: `wzdrugs.drugname ──< storediscount.drugname` (1:many discount records); `wzphar.pharmacyid ──< storediscount.pharmacyname` (1:many per pharmacy) (`schema_complete.sql:457,468`).

### Related tables
- **`titanksasales`** — sales header: `disc` (total discount REAL) + `SellDisc` (sale discount %) per line in `invoicedata` (`feature_sales_invoices.md:193,212`; `feature_purchases.md:237,244`).
- **`titanstock`** — stock with `disco` field; `order by drugname desc, disco desc` (`modules_gap_1.md:22`).
- **`companies`** — suppliers (موردين) the company-discount agreements are negotiated with (`schema_complete.md:131-141`; columns include `mobile, pass` per evidence).
- **`drgserver`** — server drug list (`vat`, `units`, `price`, `barcode`) for network/chain price sharing (`schema_complete.md:372-389`).

---

## 9. UI strings (Arabic)

From `strings_readable.txt` / `strings_utf16.txt` (index = line − 3) and extracted docs:

**Permissions / network:**
- `اتاحة الاطلاع علي خصومات المخازن في محافظتك` (readable:8266) — "Allow viewing warehouse discounts in your governorate".
- `التعرف علي خصومات المخازن للمشتركين فقط` (readable:9258) — "Knowing warehouse discounts for subscribers only".
- `خصومات المخازن` (readable:10796) — "Warehouse discounts".

**Engine / config labels:**
- `نظام احتساب خصم الشراء` (خصم/نسبة) — "Purchase discount calculation system" (`modules_gap_1.md:32`).
- `Discount by currency`, `Discount by percent of profit value`, `Discount by percent of total value` (`modules_gap_1.md:26`).
- `Apply a sale discount for tax items`, `Apply the discount of the last purchase`, `Cancel discount`, `Clean sale discount for all items`, `Abnormal Discount`, `Add. Disc`, `Local discount`, `No Extra Discount`, `Imports discount`, `Fave disc`, `contain discount` (`modules_gap_1.md:27-30`).
- `جعل خصم شراء الدواء هو اخر خصم` (idx 11268) — "Make the drug's purchase discount the last discount".

**Sales/limits:**
- `ادخل نسبة خصم علي اجمالي الفاتورة` (idx 9086) — "Enter a discount % on the invoice total".
- `لا يمكن ان يكون خصم البيع مساويا لصفر استخدم 1 او اعلي` (idx 12386) — "Sale discount cannot be zero, use 1 or higher".
- `لقد تجاوزت حد الخصم المحدد لك - يمكن تغيير هذا الحد من شاشة تعديل اعدادات العاملين` (idx 12542) — "You exceeded your discount limit — change it in the staff settings screen" (per-user max sale discount; `feature_sales_invoices.md:145`).
- `وضع حد اقصي لعمل خصم بيع لكل موظف` (idx 13251) — "Set a maximum sale discount per employee".
- `سعر احد الاصناف غير منطقية` (idx 11659) — "One of the items' prices is illogical".
- `ادخل ما دفعه المريض ليتم حساب الباقي بعد خصم قيمة الفاتورة` (idx 12527) — change calc prompt.

**Supplier/company discount agreement (FFFWaredMonsaref):**
- `ادخل خصم شراء موحد` — "Enter a unified purchase discount".
- `ادخل خصم المستورد لهذه الشركة` — "Enter the importer discount for this company".
(`feature_purchases.md:122`)

**Shortages:**
- `في النواقص يمكنك الضغط علي الصنف لمعرفة خصوماته في المخازن اليوم` (idx 12126) — click a shortage drug to see its warehouse discounts today (`feature_shortages.md:73-74`).

**Report columns (خصومات المخازن):** Store, Drug, Discount Type, Discount Value, Effective Date (`reports_complete.md:543`).

---

## 10. Business rules / edge cases

1. **Discount-before-VAT**: `Discount = Subtotal × (SellDisc/100)` is applied BEFORE VAT, so VAT base = `Subtotal − Discount` (`feature_sales_invoices.md:134-136`).
2. **Non-zero SellDisc**: if a discount is intended, `SellDisc` must be ≥ 1 — cannot be zero (idx 12386) (`feature_sales_invoices.md:143`).
3. **Abnormal discount/price detection**: outlier discounts/prices trigger "Abnormal Discount" / `سعر احد الاصناف غير منطقية` warnings before save (`feature_sales_invoices.md:56,144`).
4. **Per-employee discount cap**: staff have a configurable maximum sale discount (idx 13251 / 12542) enforced by `ModDisc` (`feature_sales_invoices.md:145`).
5. **Multi-branch governorate scoping**: warehouse discounts are visible/queryable per **محافظة (governorate)** and gated by the permission **اتاحة الاطلاع علي خصومات المخازن في محافظتك** and, for network users, the "subscribers only" flag (readable:8266/9258).
6. **Discount types are discriminated** by mode (compare vs `1`,`2`,`3`) and code `0x00DF`(223) — item-level vs invoice-level / buy vs sell / cash vs wholesale (`modules_gap_1.md:15-17`).
7. **storediscount upsert**: records are inserted only if `not exists` (dedup per drug/store) (`schema_complete.md:366`).
8. **Purchase side writes storediscount**: every purchase logs its per-drug buy-discount into `storediscount`; purchase returns reverse/remove those entries (`feature_purchases.md:150`, `feature_purchase_returns.md:97,184`).
9. **Last-purchase / unified / importer discounts**: the system can auto-apply the last purchase discount, a supplier's unified purchase discount, or a company importer discount (`feature_purchases.md:180-181`, `modules_gap_1.md:27`).
10. **Promotions (ModOrood) share the calc path**: buy-X-get-Y offers and quantity-based discounts route through the same discount engine (`modules_remaining_1.md:294-309`).
11. **Cost basis**: stock cost reflects the discounted purchase price (cost with/without VAT, `drugs-stock-cost-withvat` / `-novat`), keeping profit/report figures consistent (`business_logic.md:453-456`).

---

### Quick reference
- **Core table:** `storediscount` (17 cols: id, adress, storename, pharmacyname, pharmacyname2, datee, tips, titanver, country, drugname, barcode, price, disco, units, pricechanged, localimport, quant).
- **Engine:** `ModDisc` (10 procs) + `ModOot`/`ModInn` apply it in sales/purchases.
- **Setup/report UI:** `FormStoreDiscount` (= تقرير خصومات المخازن).
- **Key formula:** Discount before VAT; Total = Subtotal − Discount + VAT.
- **Permission:** اتاحة الاطلاع علي خصومات المخازن في محافظتك (warehouse-discount viewing per governorate).
