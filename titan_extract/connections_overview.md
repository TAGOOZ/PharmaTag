# TITAN.W1 (Phye.exe) — Master Connections Overview
**Consolidated cross-feature / cross-table / cross-file connectivity map**

System: Saudi/Egyptian multi-branch pharmacy management system (VB6, Phye.exe, ~6,192 procedures / 237 forms).
Database: SQL Server via ADODB (28 tables) **+ a large file-backed ledger** (`.phy` files).
Docs connected here: the 20 `feature_*.md` docs + `schema_complete.md/.sql`, `business_logic_complete.md`, `reports_complete.md`, `permissions_complete.md`, `config_complete.md`, `ui_complete.md`, `network_complete.md`, `zatca_complete.md`, `dtts_complete.md`, `drugeye_complete.md`, `nielsen_complete.md`, `phycodsystems_complete.md`, `api_integration.md`, `drug_database_legal.md`.

Target readers: engineers designing a modern replacement — **FastAPI + PostgreSQL** (backend/ledger), **Tauri + React + SQLite** (desktop POS), **Next.js** (web/dashboard). Arabic terms are kept beside English everywhere because the domain language (درج = drawer, أجل = credit/deferred, شبكة = network/card, تقفيل = day-close, ميزان = trial balance, نواقص = shortages, رواكد = dead stock, موردين = suppliers, مرتجع = return) is the lingua franca of the existing data.

---

## 0. Reading guide (how to use this doc)

| Section | What it answers |
|---|---|
| §1 | One picture of ALL persistent state (SQL tables + `.phy` files) and the relationships between them |
| §2 | Where money actually lives and what a modern cash/ledger design must replace |
| §3 | The shared side-effect chains (one sale, purchase, return, stock-correction, day-close → everything touched) |
| §4 | Per-feature "connects to" matrix — the cross-links individual docs lack |
| §5 | Plain-language end-to-end story of a drug through the whole system |
| §6 | External world: ZATCA, DTTS/ETA, DrugEye, Nielsen, Phycod cloud, FTP/remote-control |
| §7 | Gaps, unknowns, and open questions for the replacement |

Terminology notes used throughout: **"chain"** = مجموعة / سلسلة (the pharmacy group); **"fary"** = branch (فرع); **`silsilaid`** = chain/group ID stamped on nearly every transaction; **`phar`/`pharmacyid`/`mobile`** are the three aliases used for "which pharmacy" (all three resolve to `wzphar`).

---

## 1. Master data-model diagram (28 SQL tables + file ledger)

### 1.1 The one picture

```
LEGEND
  [PK]   = documented primary key        (schema_complete.md table sections)
  ════   = explicit SQL join / documented FK arrow (per schema_complete.md:716-757)
  ----   = inferred relationship (same-name column / naming convention; NOT proven by SQL)
  .phy   = file-backed data (not SQL)
  ◆      = every table ALSO keyed to a pharmacy via phar/pharmacyid/mobile

                       ┌───────────────────────────────┐
                       │  wzphar  (pharmacy master)    │  [PK id]  pharmacyid, pharname, adress, mobile
                       └───────────────┬───────────────┘
    pharmacy alias used by most tables: phar  /  pharmacyid  /  mobile
```

```
                                   wzdrugs  (drug master)                        [PK drugname]
   drugname ─ barcode/Barcode1..5, vat, units, Unitsmall, classy, generic, price,
   PriceNow, stock, titanid, disco, pricechanged, localimport, wareprice3, history, agel
        │
        │ drugname
        ├══════► wzdrugs2 (cost/expiry ext.)                 1:1   [JOIN wzdrugs2 d INNER JOIN wzgard g]
        ├══════► wzgard   (stock batches)                    1:many  phar──►wzphar
        ├══════► titanksastock (chain stock/phy)             1:many  pharmacyid──►wzphar, silsilaid
        ├══════► titanstock (phy-level stock)                1:many  pharmacyid──►wzphar
        ├══════► titanneed  (needs)                          1:many  sender/target──►wzphar
        ├══════► drgserver (shared server drug list)         1:many  mobile──►wzphar, silsila
        ├══════► storediscount (discount history)            1:many  (by pharmacyname/adress)
        ├══════► usersourceupdate (sync queue)               1:many
        ├══════► TitanUserAction (audit log)                 1:many  mobile──►wzphar
        ├══════► taronlineeg (online catalog)                1:many  mobile──►wzphar
        ├══════► invoicedata  (invoice header+lines)         1:many  pharmacyid──►wzphar
        ├══════► drugeyedash2 (DrugEye dashboard)            1:many
        ├──────► nilsen2 (Nielsen staging)                   1:many  (drugname,data)
        └──────► ChainBuyStore / ChainBuyUsers / RawakidTablew  1:many (DrugName / PharmacistTel)

   wzphar (pharmacy master)
        ├══════► wzgard.phar, wzcustomers.phar, titanstock.pharmacyid,
        ├══════► titanksastock.pharmacyid, titanksasales.pharmacyid,
        ├══════► invoicedata.pharmacyid, orders.pharmacyid,
        ├══════► titaninn.source/target, titanneed.sender/target
        ├══════► titanpharmalist.mobile (1:1), remotecontrol.mobile,
        ├══════► drgserver.mobile, wzaccfreetree.mobile
        └──────► farysales.mobile / .phar (branch ledger)

   ACCOUNTING / MONEY (ledger side)
        wzaccfreetree (chart-of-accounts: mobile, master, fary)   mobile──►wzphar
        farysales     (per-branch ledger: mobile,grand,father,son,datee,monthe,yearo,
                       payed,creditdebit,typee,phar,randomid,tips,writer,classy)  mobile/phar──►wzphar
        titanksasales (chain sales: invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue)
        invoicedata   (invoice header + line items; the universal invoice store)
        ZATCA         (Saudi e-invoice log: invoiceid,uuid,status,hash,xml,response)

   CHAIN / INTER-PHARMACY
        titaninn     (transfers + purchase orders: fatid, itemsasstring, source, silsilaid, target)
        titanneed    (needs: drugname, quant, sender, target)
        orders       (purchase orders: orderid, orderdate, status NULL|'saved', pharmacyid)
        titanpharmalist (registered pharmacies: mobile [PK], pharmacyname, barcode, apptype)
        ChainBuyStore / ChainBuyUsers / RawakidTablew  (group buy + dead-stock exchange)
        remotecontrol (pushed function payloads: mobile, copyid, passedfunctions)

   PARTIES
        wzcustomers  (customers AND suppliers, typee discriminates: randomid, phar, creditlimit, namee)
        companies    (supplier master: mobile [PK], pass)

   FILE-BACKED LEDGER (the real money store — NOT SQL)
        Files\DBI\Daily.phy         day transaction/money-movement log
        Files\DBI\Dailyline.phy     day line items
        Files\DBI\Dailymax.phy      daily maximums
        Files\DBI\MonyInfo.phy      money/balance snapshot
        Files\DBI\usersmony.phy     per-user money
        Files\DBI\daily-manual.phy / daily-manual-2.phy   manual journal entries
        Files\DBI\fary.date.phy / Files\DB\closefary.phy  branch date + branch close flag
        Files\DBI\acctree.phy / acctree2.phy   chart-of-accounts mirror of wzaccfreetree
        Files\DBI\RasidCorrect.phy balance corrections
        Files\DBI\workperiod.phy / delivery.phy / oot3.phy / netcounter.phy
        Files\Accounting\moves\             journal moves
        Files\Archive\monthy\moves\         month-close journal
        Files\Archive\monthy\start-data\    month-close opening balances
        Files\DB\DDI.Phy                    drug–drug interaction database
        Labirdo\Titan3-Backup\xj\Phye.safer\  compressed safe backups
        C:\saturn\zatca\...\counter.txt / hash.txt    ZATCA counters (NOT in DB)
```

Source for the arrow set: relationships diagram `schema_complete.md:716-757`; table definitions `schema_complete.md:13-713`. `wzdrugs2↔wzgard` is the **only** SQL JOIN proven by extracted code (`schema_complete.md:771`); every other arrow is either explicitly drawn in the relationships diagram or inferred from repeated same-name columns (marked `----`).

### 1.2 Explicit vs inferred FKs — the honest ledger

| Relationship | Evidence class | Where |
|---|---|---|
| `wzdrugs2.drugname` → `wzdrugs` | JOIN in SQL (`INNER JOIN wzgard g AND d.drugname = g.drugname`) | schema_complete.md:54,72 |
| `wzgard.drugname` → `wzdrugs`, `wzgard.phar` → `wzphar` | drawn in diagram | schema_complete.md:100,86,721,734 |
| `titanksasales.pharmacyid`, `titanksastock.pharmacyid`, `titanstock.pharmacyid`, `invoicedata.pharmacyid`, `orders.pharmacyid` → `wzphar` | drawn | schema_complete.md:738-740 |
| `titaninn.source/target`, `titanneed.sender/target` → `wzphar` | drawn | schema_complete.md:747-753 |
| `titanpharmalist.mobile`, `remotecontrol.mobile`, `drgserver.mobile`, `wzaccfreetree.mobile` → `wzphar` | drawn | schema_complete.md:742-745 |
| `farysales.mobile/phar`, `wzcustomers.phar` → `wzphar` | naming convention only | schema_complete.md:674,116 |
| `invoicedata.DrugName`, `titanksastock.drugname`, `titanstock.drugname`, `titanneed.drugname`, `drgserver.drugname`, `storediscount.drugname`, `usersourceupdate.drugname`, `TitanUserAction.drugname` → `wzdrugs` | naming convention only | schema_complete.md:278,202,226,248,382,350,453,427 |
| `ChainBuyStore/Users` & `RawakidTablew` keyed by `PharmacistTel` (→ `titanpharmalist.mobile`) | naming convention only | schema_complete.md:516-595 |

### 1.3 Which tables are real vs reconstructed

- `schema_complete.md:763-774` — evidence inventory: only **5 CREATE TABLE** statements recovered (`titaninn`, `titanksasales`, `titanksastock`, `titanneed`, `TitanUserAction`); **8 tables inferred from context only**. Inferred tables (columns marked `[INFERRED]` inside the docs): `farysales` (feature_account_closing.md:210-233), `wzaccfreetree` (feature_balances.md:182-186), `nilsen2` (schema_complete.md:469-482), `drugeyedash2` (schema_complete.md:598-612), `companies` (schema_complete.md:131-143), `taronlineeg` (schema_complete.md:486-509), `titanpharmalist` (schema_complete.md:634-651), `orders` (schema_complete.md:295-313).
- Divergent reconstructions to be aware of: `titanksasales` and `titaninn` appear as **full line-item tables** in `business_logic_complete.md:102-125` but as **summary tables** in `schema_complete.md:172-193`; `invoicedata` is a hybrid **header+line in one table** (`schema_complete.md:263-291`).

---

## 2. Money / ledger resolution (where does the money actually live?)

**Headline: there are no `wzmony` / `wzdaily` / `wzbank` SQL tables.** The docs use those names as conceptual shorthand; the real money store is (a) the `farysales` SQL ledger and (b) the serialized `.phy` daily files. This is the single most important fact for the replacement's data model.

### 2.1 The evidence

- `feature_sales_invoices.md:118` — "Money is stored in serialized daily files (`Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`) rather than SQL". The same doc labels it "Money / daily (`wzmony`-equivalent)" — i.e. the doc **itself** flags the SQL names as approximate.
- `feature_sales_invoices.md:282` — "Money/daily data is file-based (`.phy`): `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`, `usersmony.phy`".
- `feature_account_closing.md:33-51` & `:256` — the day-close reads/writes exactly these files; "Day-close file backing (not SQL)".
- `feature_reports_analytics.md:328` — the RPT-F01 cash flow / RPT-H01 history reports read "`wzmony` / `wzdaily` / `wzbank` | Money/daily/bank records" — but those reports are fed from the `.phy` files (`feature_reports_analytics.md:341` lists `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `workperiod.phy`, `delivery.phy`, `oot3.phy`, `daily-manual.phy`, `daily-manual-2.phy`).
- `feature_invoice_editing.md:65-68,130-133,201,263` — editing a posted invoice "reverses and re-applies" the `wzmony`/`wzdaily` rows; this is the same reverse-then-rewrite pattern the system uses on `.phy` files and on `wzgard`. The SQL names in these docs are conventions, not CREATE TABLE evidence.
- `feature_doctors_prescriptions.md:129` — a table that repeats the `wzmony`/`wzdaily`/`wzbank` labels **as a summary of `business_logic_complete.md` §16** — same shorthand.
- The only real SQL ledger tables are `farysales` (schema_complete.md:655-687) and `invoicedata`/`titanksasales` (invoice amounts). `farysales` is the per-branch/per-account posting ledger: `father`/`son` map to chart accounts, `creditdebit` marks debit/credit, `payed` the amount, `monthe`/`yearo` enable monthly aggregation (feature_balances.md:192).

### 2.2 The drawer (الدرج) model — cash / شبكة / أجل splits

The **drawer** is the physical cash box; **شبكة** (network/card) and **أجل** (credit/deferred) are book balances, not physical cash. The invoice always splits `totalvalue = payed (cash+visa) + agel (credit)` (feature_sales_invoices.md:153, idx 13344; also feature_sales_invoices.md:149-160).

| Side | Source | Effect on drawer |
|---|---|---|
| Cash sale | sales invoice, `payed` cash portion | **in** (قبض) — drawer up |
| Card/شبكة sale | sales invoice, `payed` visa/شبكة portion | **not** drawer cash; tracked as شبكة balance |
| Credit/أجل sale | sales invoice, `agel` portion | **not** drawer; customer debt up (wzcustomers) |
| Cash return | sales return | **out** of drawer (خروج نقدية نتيجة ارتجاع ادوية في المبيعات, idx 11421) — feature_sales_returns.md:72,99 |
| Cash purchase | purchase invoice paid from drawer | **out** — "تخرج من الدرج" (feature_purchases.md:143,147) |
| Supplier refund | purchase return refunded | **in** — دخول نقدية نتيجة ارتجاع الدفع من الشركات (feature_purchase_returns.md:91) |
| Customer settlement / سند قبض | receivable payment | **in** |
| Supplier payment / سند صرف | payable payment | **out** |
| Expenses / مصروفات | حركة مالية screen | **out** — must be moved drawer→treasury before close (feature_account_closing.md:71,312) |

Drawer accounting identity (three equivalent statements in the docs):
- `drawer = cash sales − cash returns + customer settlements` (feature_sales_invoices.md:338, idx 12675/8956)
- `expected drawer = current drawer − drawer at period start + cash that left during the period` (feature_account_closing.md:65, idx 8305)
- Sales vs drawer: "if you sell 2×500 EGP and buy 300 EGP of drugs, sales total is 500 while the drawer is only 200" (feature_account_closing.md:311, idx 8336/9963) — **expenses drawn from the drawer do not reduce sales totals**.

### 2.3 How sales/purchases/returns/expenses flow into `farysales`

`farysales` is the SQL **posting journal** the accounting feature writes, while `.phy` files are the **cash/day register** the close reconciles:
- Sales cash/visa/أجل → day register (`.phy`) + `titanksasales`/`invoicedata`; accrual accounts (اجل العملاء) post to balances via `wzcustomers` (feature_balances.md:132).
- Purchases → **credit (دائن)** posting to `farysales` with `father/son` = `خصوم.خصوم متداولة.موردين` and `creditdebit='credit'` (feature_purchases.md:140-142; feature_customers_suppliers.md:54,113).
- Purchase returns → **debit** posting `creditdebit='debit'` against the same account (feature_purchase_returns.md:87,145).
- Manual entries (القيود اليدوية) → `daily-manual.phy`/`-2.phy` and via FormDailyManual2 selecting a master account from `wzaccfreetree` (feature_account_closing.md:73; feature_balances.md:54,58).
- Day close aggregates all buckets (كاش/شبكة/مصروفات/مشتريات/ضريبة...) and rolls balances into the next day (feature_account_closing.md:67,75,163).

### 2.4 What a modern replacement needs (concrete recommendation)

Replace the `.phy` free-for-all with real tables. Recommended PostgreSQL/SQLite schema:

```
parties(id, kind[customer|supplier], code, name, credit_limit, ...)
accounts(id, code, parent_id, name_ar, name_en, type[asset|liability|equity|income|expense])
      -- legacy wzaccfreetree + acctree.phy → normalized chart of accounts (feature_balances.md:211-271)
journals(id, branch_id, date, entry_no, description, status, source, ref_invoice_id)
journal_lines(id, journal_id, account_id, debit, credit, contra_party_id)
      -- legacy farysales rows (father/son/creditdebit/payed) + \Files\Accounting\moves\
invoices(id, kind[sale|purchase|sale_return|purchase_return|transfer], branch_id, invoice_no,
         party_id, date, subtotal, discount, vat, total, status[open|saved|closed|archived])
invoice_lines(id, invoice_id, drug_id, batch_id, qty, unit_price, cost, disc, vat, line_total)
payment_splits(id, invoice_id, method[cash|card|credit], amount, received_at)
      -- legacy payed/agel/totalvalue columns + كاش/شبكة/أجل split
drawer_movements(id, branch_id, date, direction[in|out], reason[cash_sale|cash_return|supplier_pay|expense|settlement|transfer],
                 amount, method[cash|network], shift_id, ref_invoice_id, user_id)
      -- legacy Daily.phy / Dailyline.phy / حركة مالية (feature_account_closing.md:130-136)
daily_close(id, branch_id, date, expected_cash, counted_cash, difference, net_cash, net_network,
            purchases, expenses, vat_sales, vat_purchases, vat_expenses, status, closed_at)
      -- legacy MonyInfo.phy snapshot + RPT-H02 day-close columns (feature_account_closing.md:96-121)
monthly_close(id, year, month, start_balances_json)   -- legacy \Files\Archive\monthy\start-data\
balances(id, account_id, date, debit, credit, balance) -- materialized for trial balance / ميزان
```

Key design rules taken from the legacy: every money row carries **branch** (fary), **date** (+month/year for aggregation), **creditdebit side**, and **account path**; day close is an **immutable snapshot** that locks a date; the global system date is advanced only by the close (feature_account_closing.md:75,308 — "غير مسموح بتغير التاريخ الا بهذه الطريقة حفاظا علي الحسابات الدقيقة للبرنامج", idx 12032).

---

## 3. Shared side-effect chains (trace one transaction through the whole system)

Each arrow = "writes to / feeds". Source feature doc + line refs are given. These are the cross-cutting invariants a replacement must reproduce atomically.

### 3.1 One SALE (فاتورة بيع)

**Primary write (feature_sales_invoices.md:112-124,63):**
```
SAVE SALES INVOICE
 ├── wzgard          quant−, oldstock=prior, typee='sale'      (stock check "Not Enouph Stock" first)   sales:116
 ├── wzcustomers     debt+ (أجل portion only); cash customers must pay full      (idx 13133)           sales:117
 ├── money (.phy)    cash→drawer (قبض); creditdebit recorded; Daily.phy etc.     (strings_readable 6735-6777)
 ├── titanksasales   one row per invoice via the live GUID insert loop           (idx 7423; sales:36,119)
 ├── invoicedata     one row per drug (IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)   sales:120
 ├── ZATCA           tax invoice row (uuid/status/hash/xml) when linked           (sales:121; tax:149)
 └── TitanUserAction audit row (drugname,old/new,user,price,units,datee)          (sales:122)
```
**Downstream consumers (what it feeds):**
- `feature_account_closing.md:160-161` — `titanksasales` + `invoicedata` feed the day totals (محسوب المبيعات, تكلفة مبيعات اليوم, ربح اليوم, ضريبة المبيعات اليوم).
- `feature_balances.md:132-138` — customer accrual (اجل العملاء) → balance sheet; cash → أصول.نقدية.كاش; شبكة → نقدية.شبكة.
- `feature_shortages.md` — sale decrements `titanstock`/`titanksastock`; when `stock < minimum` (titanksastock.minimum) the item enters نواقص (transfers_logistics.md:159,512).
- `feature_stock_counting.md` — the sale is part of counted stock movement (wzgard rows).
- `feature_discounts.md:79` — discounted net total is what settles to the money side; `storediscount` logs per-item discount (sales:142, feature_discounts.md:16 counts).
- `feature_tax_invoicing.md` — the sale is the source of the فاتورة ضريبية (ZATCA/ETA JSON, sales:58).
- `feature_reports_analytics.md` — RPT-Sxx sales reports + RPT-A04 drawer handover + RPT-F01 cash flow (reports:178,325,328).

### 3.2 One PURCHASE (فاتورة مشتريات)

**Primary write (feature_purchases.md:127-155):**
```
SAVE PURCHASE INVOICE
 ├── wzgard          new batch row, quant+, oldstock, costvalue/vatvalue/totalwithvat, typee='purchase'   pur:129-135
 ├── titanstock / titanksastock  stock field + (drug-card stock)        (raz §5.2 rule 4; pur:135)
 ├── wzdrugs2        unitcost recomputed from wzgard (costvalue/quant); last purchase price             pur:136,382
 ├── farysales       credit posting father/son=خصوم.موردين, creditdebit='credit', payed              pur:140-142
 ├── companies/wzcustomers  supplier dues (مستحقات المورد) +; payment via سند صرف reduces               pur:142
 ├── money (.phy)    cash paid → out of drawer (خروج نقدية نتيجة الدفع للشركات, idx 10759)              pur:143,147
 ├── storediscount   insert per-item purchase discount                                                   pur:150
 ├── TitanUserAction audit                                                                               pur:153
 └── (DTTS/e-invoice) batch (تشغيلة) + serial numbers uploaded                                           pur:154
```
**Downstream:** cost basis drives **تكلفة المبيعات (COGS)** and **ربح اليوم** at day close (pur:152, account_closing:67); supplier payables feed balances/ميزان and تسديدات المشتريات (feature_customers_suppliers.md:113); first invoice must be a saved purchase (pur:378) — i.e. **opening stock enters through purchases** (الجرد الاولي, pur:137,379).

### 3.3 One RETURN (sales return / purchase return)

**Sales return — reverse of sale (feature_sales_returns.md:181-182,72):**
```
RETURN (sales)
 ├── wzgard          quant+ back (reverse of sale)                sales_returns:181
 ├── wzcustomers     customer debt− (أجل reversed)                 sales_returns:181
 ├── money (.phy)    cash refund out of drawer (idx 11421,13032)   sales_returns:72,99
 ├── titanksasales   reverse chain row                             sales_returns:181
 ├── invoicedata     reverse line(s)                               sales_returns:181
 └── ZATCA           فاتورة ضريبية - مرتجع (tax return invoice, idx 12045)  sales:41, tax_invoicing:56
```
**Purchase return (feature_purchase_returns.md:87-91,145):** reverses the wzgard batch, posts **debit** to `farysales` against `خصوم.خصوم متداولة.موردين`, and if the supplier refunds cash, **cash returns to drawer/treasury** (دخول نقدية نتيجة ارتجاع الدفع من الشركات). The 3 purchase invoice states are مشتريات / مرتجع مشتريات / مرتجع الاكسبير (pur:387; transfers:12371-side text in feature_sales_invoices states). Returns factor into day close: `اجمالي مرتجع المبيعات` (sales_returns:72, idx 8991).

### 3.4 One STOCK CORRECTION / COUNT (جرد + تصحيح ارصدة)

**Primary write (feature_stock_counting.md:20,75,201,232,235):**
```
STOCK COUNT / CORRECTION
 ├── wzgard / titanstock / titanksastock  stock adjusted up (بالزيادة) / down (بالعجز)
 ├── RasidCorrect.phy   correction log (Files\DBI\RasidCorrect.phy)      stock_counting:232
 ├── farysales          branch valuation rows (costvalue/totalwithvat)   stock_counting:201, shortages:171
 ├── money (.phy)       opening drawer cash set at setup (الرصيد الافتتاحي للخزينه, idx 9130)   stock_counting:75
 └── approval flow      staff request → manager accept/reject (idx 8837/9945)  feature_balances.md:70
```
Feeds `feature_balances.md:70,334` (تصحيح الارصدة بالزيادة/بالعجز, idx 10174/10175; audit في RasidCorrect.phy) and the "negative balances" command in the counting menu (balances:335). This is also how opening stock/جرد is reconciled with purchases (الجرد الاولي enters via purchases, pur:137).

### 3.5 One DAY-CLOSE (تقفيل اليوم)

**Primary write (feature_account_closing.md:156-167,59-83):**
```
DAY CLOSE
 ├── system date      advanced +1 day (idx 883); cannot close before 1 PM (idx 887); idempotent (idx 890)
 ├── Daily.phy / MonyInfo.phy   day ledger + balances snapshot written
 ├── titanksasales / invoicedata  read as source of day totals (محسوب المبيعات, تكلفة, ربح, ضريبة)
 ├── drawer count     physical count entered; expected = opening + sales − outflows (idx 8305)
 ├── difference       عجز/زيادة recorded; adjustable from pharmacy-date screen (idx 10365)
 ├── farysales / fary.date.phy / closefary.phy   branch-level close flag
 ├── Archive          old sales/purchase invoices archived (تخزين فواتير المبيعات/المشتريات القديمة)
 ├── Backup           Titan3-Backup\Daily\ daily archive (+ per-day balance-history folder, idx 9224)
 ├── Shift            shift closed together with the day (idx 10251); drawer handover report
 └── Month close (تقفيل الشهر): \Files\Archive\monthy\moves\ + start-data\ (next month opening balances)
```
**Feeds:** `feature_balances.md:72` (month-end start-data → opening balances), `feature_backup_archive_import.md:170` (daily backup keeps a per-day balance history; .phy set is part of the backup), `feature_reports_analytics.md:178` (RPT-A04 drawer handover), `feature_users_permissions_menus.md:122` (money-per-user feeds the close).

---

## 4. Per-feature "connects to" matrix

Table-mention counts are from a scan of the 20 feature docs (file → table, `rg -c`). Read/write direction is stated where the source doc is explicit; otherwise the table name alone indicates connectivity. `.phy`/file columns are from the same docs.

| # | Feature (عربي) | SQL tables touched (count) | `.phy`/files | Feeds | Consumes |
|---|---|---|---|---|---|
| 1 | **Sales invoices** فواتير مبيعات | `titanksasales`(10), `invoicedata`(6), `wzgard`(3), `wzcustomers`(2), `titaninn`(5), `farysales`(1), `ZATCA`(2) | `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`, `usersmony.phy` (sales:118,282) | accounting/close, balances, shortages, stock counting, discounts, tax invoicing, reports | drug master, customer debt, drawer |
| 2 | **Sales returns** مرتجع بيع | `wzgard`(6), `titanksasales`(6), `invoicedata`(4), `wzcustomers`(4), `ZATCA`(2), `farysales`(1), `titaninn`(2) | daily money files (reversed) (returns:72) | cash-out reasons at close (returns:72) | sales invoice that is reversed |
| 3 | **Purchases** مشتريات | `wzgard`(10), `invoicedata`(4), `wzcustomers`(4), `companies`(5), `farysales`(3), `titanstock`(3), `titanksastock`(3), `storediscount`(3), `TitanUserAction`(3), `orders`(3), `titaninn`(2), `ChainBuy*`(2), `RawakidTablew`(1) | drawer/treasury money files (pur:143,147) | COGS/profit at close (pur:152), supplier payables, storediscount, drug cost | supplier master, opening stock, DTTS |
| 4 | **Purchase returns** مرتجع مشتريات | `wzgard`(7), `invoicedata`(3), `storediscount`(3), `TitanUserAction`(3), `farysales`(2), `titanksastock`(3), `titanstock`(2), `wzdrugs2`(2) | cash-in to drawer on refund (returns:91) | farysales debit (returns:87,145) | the purchase invoice reversed |
| 5 | **Invoice editing** تعديل فواتير | `wzgard`(8), `invoicedata`(3), `titanksasales`(3), `TitanUserAction`(5), `farysales`(2), `wzaccfreetree`(2), `wzcustomers`(2) | money/journal `.phy` reversed+re-applied (edit:65-68,130-133,263) | ZATCA/ETA re-submit after money-affecting edit | sales/purchase/return invoices |
| 6 | **Account closing** تقفيل حسابات | `farysales`(5), `invoicedata`(3), `titanksasales`(2), `wzaccfreetree`(6), `ZATCA`(1), `companies`(1) | `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`, `daily-manual.phy/-2`, `fary.date.phy`, `closefary.phy`, `acctree.phy`, `RasidCorrect.phy`, Archive\monthy\moves + start-data, Titan3-Backup\Daily (closing:33-51,256) | balances (opening balances), backup/archive, reports | every day's invoices, money files, shifts |
| 7 | **Balances** ارصدة | `wzaccfreetree`(5), `farysales`(5), `invoicedata`(2), `titanksasales`(2), `wzcustomers`(2), `wzdrugs`(2), `titanstock`(2), `titanksastock`(1) | `acctree.phy`, `acctree2.phy`, `MonyInfo.phy`, `RasidCorrect.phy`, `\Files\Accounting\moves\`, Archive\monthy\start-data (balances:40-46,207) | ميزان/trial balance, balance sheet, كشف حساب, capital | sales+purchases accruals, stock counts, day close |
| 8 | **Stock counting** جرد ارصدة | `wzgard`(9), `wzdrugs`(4), `wzdrugs2`(2), `TitanUserAction`(4), `titanstock`(2), `titanksastock`(2), `farysales`(1), `invoicedata`(1), `orders`(1) | `RasidCorrect.phy` (count:232); opening drawer (count:75) | balances corrections, shortages | drug cards, stock batches |
| 9 | **Shortages** نواقص | `titanneed`(4), `titanksastock`(3), `titanstock`(3), `orders`(4), `wzdrugs`(2), `companies`(1), `storediscount`(1), `farysales`(1) | — | orders + transfers (transfers:159) | sales stock decrements, minimum levels |
| 10 | **Discounts** خصومات شركات ومخازن | `storediscount`(16), `wzdrugs`(3), `titanksasales`(3), `invoicedata`(3), `wzcustomers`(1), `wzphar`(1), `titanstock`(1), `drgserver`(1) | money `.phy` (settled net total) (disc:79) | purchases (buy discount), sales (SellDisc), price changes | drug cards, warehouse margin (FormDrugStore) |
| 11 | **Customers & suppliers** عملاء وموردين | `wzcustomers`(13), `companies`(13), `farysales`(4), `titanstock`(1), `drgserver`(1) | money files for settlements (customers:114) | sales debt / purchase payables | balances, day close, reports |
| 12 | **Drug master & pricing** دواء وأسعار | `wzdrugs`(11), `wzdrugs2`(7), `wzgard`(6), `drgserver`(5), `titanksastock`(3), `storediscount`(2), `drugeyedash2`(2), `usersourceupdate`(2), `TitanUserAction`(3), `titanneed`(2), `titanstock`(2), `titaninn`(1) | DrugEye `.phy` catalog (`fromdrugeye.phy`, `DRUGS.PHY`) (external:72-75) | pricing/VAT for sales+purchases, shortages (price), discounts | DrugEye/cloud updates, purchases (cost) |
| 13 | **Transfers & logistics** تحويلات ولوجستيات | `orders`(19), `titaninn`(17), `titanneed`(9), `titanksastock`(8), `ChainBuyStore`(7), `ChainBuyUsers`(7), `RawakidTablew`(8), `titanstock`(6), `titanksasales`(3), `wzphar`(2), `titanpharmalist`(1) | `delivery.phy` (transfers:345), FarWay `\Files\FarWay\FarData\...` (transfers:73-78) | sales (branch transfers), purchases (chain buy), shortages (needs), warehouse | cloud-link network, sub-devices |
| 14 | **Tax invoicing** فوترة ضريبية ZATCA/DTTS | `ZATCA`(31), `titanksasales`(5), `invoicedata`(3), `wzgard`(7), `wzdrugs`(3), `farysales`(2) | `counter.txt`/`hash.txt` (C:\saturn\...), `\Files\qr\`, `C:\eta-qr\`, `netcounter.phy` (tax:154-155) | government (ZATCA/ETA), VAT reports, QR printing | sales + purchase invoices, drug cards (VAT%) |
| 15 | **Users / permissions / menus** مستخدمون وصلاحيات | `TitanUserAction`(17), `usersourceupdate`(16), `ChainBuyUsers`(5), `titanpharmalist`(3), `taronlineeg`(2), `invoicedata`(3), `wzcustomers`(1), `companies`(1), `drgserver`(1), `remotecontrol`(1), `farysales`(1) | users/permissions config; money-per-user feeds close (users:122) | permission gates on every feature; audit trail | login, tech-support roles, mobile registration |
| 16 | **Backup / archive / import** نسخ وأرشفة واستيراد | `titaninn`(13), `remotecontrol`(16), `usersourceupdate`(16), `farysales`(3), `drgserver`(3), `TitanUserAction`(4), `wzdrugs`(2), `wzcustomers`(2), `titanksastock`(1), `titanstock`(2), `storediscount`(1) | `Labirdo\Titan3-Backup\{Daily,Monthly,Export,xj}\`, `xj\Phye.safer\`, `Files\DBI\*.bak`, `Files\Archive\Input\ + Output\`, daily balance-history folder (backup:90,170,257) | restore, cloud/Internet backup, rollback | day close (backup at close), transfers (imported fats) |
| 17 | **Doctors & prescriptions** أطباء وروشتات | `wzdrugs`(1), `wzgard`(2), `TitanUserAction`(1), `companies`(3), `wzcustomers`(2), `titaninn`(1), `titanneed`(1), `titanksasales`(2), `invoicedata`(2), `wzphar`(1) | `Files\DB\DDI.Phy` drug-interaction DB (presc:27,66; config:15) | prescriptions feed sales invoice lines | DDI checks, patient data |
| 18 | **Reports & analytics** تقارير وتحليلات | `titanksasales`(9), `ZATCA`(7), `titanksastock`(4), `titanstock`(1), `TitanUserAction`(3), `storediscount`(2), `invoicedata`(2), `farysales`(1), `wzphar`(1), `titanneed`(1), `wzaccfreetree`(1), `nilsen2`(1), `titanpharmalist`(2) | `.phy` daily files (reports:341), `workperiod.phy`, `oot3.phy` | RPT-S/P/C/SUP/H/ST/D/A/F/DEL/CH/EXP/EI/OP/SP report families (reports:251) | every feature's data |
| 19 | **External integrations** تكاملات | `remotecontrol`(26), `usersourceupdate`(23), `drgserver`(20), `ZATCA`(7), `nilsen2`(6), `titanstock`(3), `titanksastock`(4), `titanpharmalist`(3), `titaninn`(3), `TitanUserAction`(4) | DrugEye `.phy`/`.rar`, `nilsen2` staging, `myftp.phy`, cloud paths (external:291-302,310) | ZATCA, ETA/DTTS, DrugEye, Nielsen, cloud sync, remote control | local sales/stock (upload), drug catalog (download) |
| 20 | **Misc modules** وحدات متنوعة | `titaninn`(4), `titanksasales`(4), `titanksastock`(6), `titanstock`(3), `titanneed`(3), `taronlineeg`(3), `farysales`(3), `storediscount`(2), `usersourceupdate`(1), `drgserver`(2), `remotecontrol`(2), `ZATCA`(3), `wzaccfreetree`(2), `ChainBuyUsers`(1), `RawakidTablew`(1), `wzphar`(1) | `.phy` files per misc feature (misc:…), netcounter.phy | loyalty/points, e-commerce (HungerStation), mobile data, country/currency | shared Raz helpers |

Sources for counts: direct `rg -c` scan of `feature_*.md`; authoritative tables per feature also in each doc's "Tables" section (e.g. sales:180-283, purchases:226-330, balances:175-208, account_closing:205-257, transfers:90-320, tax:118-155, external:415-483).

---

## 5. Cross-feature flow narrative (end-to-end, plain language)

**Purchased → stocked → priced → sold → returned → counted → short-flagged → discounted → taxed → posted → closed → balanced → archived/backed up → reported → synced → exported.**

1. **Purchased.** A purchase invoice is the entry point of everything (pur:378: the first invoice must be a saved purchase). Opening stock (الجرد الاولي) is entered as a special purchase. Stock batches are written to `wzgard` with cost + VAT; `wzdrugs2.unitcost` is derived; the drug card stock in `titanstock`/`titanksastock` is incremented; a credit posting to `farysales` under `خصوم.موردين` raises the supplier payable; the supplier's `companies`/`wzcustomers` balance updates. If the supplier is another pharmacy (identified by tax reg or cloud-link number), the goods arrive via `titaninn` transfers instead (transfers:125).
2. **Stocked.** Batch/expiry tracking lives in `wzgard`; chain visibility lives in `titanksastock` (per pharmacy + `silsilaid` + `minimum`); physical/warehouse stock (مخزن) has add/withdraw operations (transfers:320). Drugs below `minimum` become نواقص (shortages) through one of three systems — manual, half-automatic (minimum level), or sales-rate (transfers:163-168) — and produce `titanneed` rows and `orders` to suppliers.
3. **Priced.** Prices and VAT% live on the drug card (`wzdrugs.price/PriceNow/vat/disco`). Prices are refreshed from the last 100/400 purchase invoices and from DrugEye/cloud via `usersourceupdate`/`drgserver` (pur:394, external:115-126). Discount changes log to `storediscount`. Warehouse margin (1-6) is applied at the store (FormDrugStore, external:501).
4. **Sold.** A sales invoice (cash/شبكة/أجل split) decrements `wzgard` and `titanstock`/`titanksastock`, posts one `titanksasales` row + `invoicedata` lines, adds customer debt for أجل, records cash to the drawer `.phy` files, emits a tax invoice (`ZATCA`/ETA) when linked, audits to `TitanUserAction`, and opens the cash drawer on print. A sale that crosses the credit limit is blocked (sales:157, idx 8968).
5. **Returned.** Sales returns reverse stock, customer debt, chain rows, invoice lines, and cash-out of the drawer; purchase returns reverse stock and post a debit to `farysales`, with cash-in on supplier refund. Both emit tax return variants (فاتورة ضريبية - مرتجع).
6. **Counted.** Stock counts and corrections (بالزيادة/بالعجز) adjust `wzgard`/`titanstock`, log to `RasidCorrect.phy`, revalue branches in `farysales`, and flow through a manager approval gate. Opening balances (drawer cash, stock at cost excl VAT, customer receivables, supplier payables) are seeded at setup (balances:72).
7. **Short-flagged.** Shortages (`titanneed`) + orders (`orders`, pending while `status IS NULL`) drive replenishment and inter-branch needs; dead stock (رواكد) is published via `RawakidTablew`/`ChainBuyStore` and exchanged between pharmacies from the sales screen (transfers:312-316).
8. **Discounted.** Invoice discounts (SellDisc / خصم الشراء / cash / wholesale / tax-item) reduce the settled money and are logged to `storediscount`; abnormal discounts are blocked (sales:144, pur:168).
9. **Taxed.** VAT (default 15%) is computed per invoice; daily buckets split ضريبة المبيعات/المشتريات/المصروفات; ZATCA (KSA) signs via Saturn/toolkit and logs to the `ZATCA` table with uuid/counter/hash; Egypt ETA/DTTS submits XML and tracks uuid against `titanksasales` (tax:66-86).
10. **Posted.** Accounting: the chart of accounts (`wzaccfreetree` + `acctree.phy`) and the `farysales` journal (father/son, creditdebit) record double-entry moves; manual entries (القيود اليدوية) post via `daily-manual.phy`. Journal moves live under `\Files\Accounting\moves\`.
11. **Closed.** Day close counts the drawer, aggregates the day (sales/purchases/expenses/VAT/profit), reconciles عجز/زيادة, advances the system date, closes the shift, archives old invoices, backs up to `Titan3-Backup\Daily\`, and writes `MonyInfo.phy`. Month close rolls opening balances into `start-data\` for the next month.
12. **Balanced.** Trial balance (ميزان المراجعة), balance sheet (الميزانية), account statements (كشف حساب), capital/P&L (راس المال، ارباح وخسائر) are generated from the account tree + `farysales` + balances; the chronological balance sequence is validated (balances:331).
13. **Archived / backed up.** Daily/monthly archives, `xj\` compressed backups, `Phye.safer\`, restore via `Restore.exe`, import/export of fats via `titaninn` (backup:90,172).
14. **Reported.** RPT-* families (S/P/C/SUP/H/ST/D/A/F/DEL/CH/EXP/EI/OP/SP) render from the tables above (reports:251).
15. **Synced across branches.** Cloud-link (الربط السحابي), FarWay file sync (`Titanfary.exe`, FromMain/ToMain folders), full-link sub-devices, `ModSqlLink` remote SQL, FTP/HTTP upload: chain tables `titanstock`, `titanksastock`, `titanksasales`, `titaninn`, `titanneed`, `titanpharmalist`, `usersourceupdate`, `remotecontrol`, `orders` are replicated (network_complete.md:602-615; transfers:528).
16. **Exported.** Drug master exported to DrugEye (`\Files\Export\DrugEye\`); pharmacy sales data aggregated over 6 months, RAR-compressed and uploaded to `titan-users/data-for-sale/...` for Nielsen; ZATCA/ETA submissions go to the tax authorities (external:77-80,193,201-213).

---

## 6. Integration & external connections

### 6.1 ZATCA — Saudi e-invoicing (feature_tax_invoicing.md:66-76; zatca_complete.md)

Flow: build JSON invoice → generate UUID (`toolkit.exe --generate-uuid`) → sign (`saturn.exe`/BouncyCastle) → POST → response to `Zatca-response.txt` → store under `C:\saturn\zatca\computer-1\invoices\` → update `counter.txt` + `hash.txt` → **write one `ZATCA` row (uuid, status, hash, xml, response)** (tax:118-129,154). VAT report exports to ZATCA/Excel/PDF via FormVat2 (tax:93). VAT default 15%; `<masrofat-vat>` tag live in expense pipeline (sales:139, account_closing:175).

### 6.2 DTTS / ETA — Egypt tax + drug track & trace (feature_tax_invoicing.md:79-86; dtts_complete.md)

`ModEtaWrappper` builds XML (header/items/taxTotals/UUID), POSTs to `https://api.invoicing.eta.gov.eg` (prod) or `preprod`, parses status/UUID, retries/validates, tracks `uuid` against `titanksasales`, shows status in FormEtaInfo, QR under `C:\eta-qr\`. Saudi side has a separate **SFDA RSD SOAP** track & trace (`ModDTTS`, `https://rsd.sfda.gov.sa:443/ws/PharmacySaleService/...`, dispatch/accept/return/transfer; FormRsdDispatch) (external:399-401; api_integration.md:13-18). Purchase invoices carry batch (تشغيلة)/serial numbers for this tracking (pur:154,392).

### 6.3 DrugEye — drug database (feature_external_integrations.md:55-156; drugeye_complete.md)

Downloads `drugeye.update.titan.rar` from the Phycod server, extracts `.phy` files into `\Files\DB\`/`\Files\DBI\`, copies `DRUGS.PHY` to root (external:69-73). Master reference catalog = `drugeye-for-titan.phy`; import working copy = `fromdrugeye.phy`. Export direction: `\Files\Export\DrugEye\`. Chain sharing via `drgserver` (per-pharmacy drug list keyed by `silsila`+`mobile`) and the `usersourceupdate` queue (pull capped at 3000 rows, delete-by-id ack) (external:103-126; business_logic:1247). Dashboard via `drugeyedash2`. **Legal caveat**: DrugEye is proprietary freeware with no data-reuse license; do not import without written permission — use EDA/CC0/SFDA datasets instead (external:150-155; drug_database_legal.md:23-42,83-101,251-259).

> **⚠️ VERIFIED 2026-08-15 — the download path is dead code.** Live download of the URL proved `drugeye.update.titan.rar` is **not a RAR**: it is a **ROT-4-obfuscated text feed** (23,452 records; decode = shift every letter/digit −4, keep `$ . , ( ) & - /`/space literal; format `<barcode>x<BRAND>$<product>$<form>$<strength>...x<PRICE>x<QTY>x`). Decoded copy: `/tmp/opencode/drugeye.update.titan.decoded.txt`. In p-code, the URL, filenames, and ALL drugeye SQL (`drgserver`, `usersourceupdate`, `wzdrugs`/`wzdrugs2`, `drugeyedash2`) have **0 references**; the only live drugeye string is `http://www.drugeye.pharorg.com` (21 refs, web-service call). Drug data actually enters through **native VB6 fixed-record `.phy` I/O** (`OpenFile`/`GetRecOwn4`/`PutRecOwn4`; `ModDrgW`, `FFFDrugEye`, `Files`, `FormImportFromOtherDBI`, `ModDRGEXChange`) — not SQL, not the ROT-4 feed. See drugeye_complete.md §7A, §9.

### 6.4 Nielsen — data selling (feature_external_integrations.md:159-236; nielsen_complete.md)

Opt-in "التكامل مع نيلسن": collect per-drug sales (name, barcode, qty, price, discount, units, stock) + per-pharmacy + per-sale data → stage into `nilsen2` (cleared frequently) → aggregate over 6-month windows → `;`-delimited payload → RAR via WinRAR → `curl.exe` upload to `titan-users/data-for-sale/...` (egypt/saudi/world) → response must exceed 3 chars → download `numbers.rar` report. **This is a monetized data-selling channel; not recommended to replicate** — if analytics are wanted, opt-in, anonymized, HTTPS (external:229-235).

### 6.5 PhycodSystems vendor cloud (feature_external_integrations.md:239-274; phycodsystems_complete.md)

Three hosted servers (site12/16/17 on `htempurl.com`); ~15 auto-downloaded executables (`saturn.exe`, `toolkit.exe`, `curl.exe`, `anydesk.exe`, `Titanfary.exe`, `server.connector.exe`, ...); hardware-fingerprint licensing via `ModWMI` (BIOS/CPU/OS/NIC); online license validation; AnyDesk silent remote access; HTTP-not-HTTPS distribution, unsigned binaries, remote code execution channel via `remotecontrol.passedfunctions`, and vendor lock-in. **All flagged as inadvisable to replicate** (external:266-273,520-529).

### 6.6 Network / cloud / FTP / remote-control (feature_external_integrations.md:277-392; network_complete.md)

- `ModNetwork` (65 procs): WinInet FTP + XMLHTTP/ServerXMLHTTP; config `myftp.phy`; PowerShell WebClient STOR; curl `--ftp-pasv --retry 3`.
- `ModSqlLink` (19 procs): remote SQL Server linking (`Driver={SQL Server}`), bulk sync over `drgserver`, `remotecontrol`, `titanpharmalist`, `titanksasales`, `titanksastock`, `titaninn`; LAN via `net share Titan.master`.
- `ModTitanCloud` (16 procs): `Upload allinone`, `Upload zipped DBI`, `Upload the drug database to the cloud storage`, cloud paths `/titan-users/allinone/data/`, `/titan-users/titan-mobile/files/`, `/titan-users/fary-net/`, etc. **Last-write-wins, no merge** (external:324).
- `ModMobile` / `ModFarWay`: mobile data sync; file-based master–slave branch sync (`FromMain\`, `ToMain\Inn\`, `ToMain\Oot\`, heartbeat `i-am-runing.txt`).
- `remotecontrol` table: server pushes `passedfunctions` (serialized VB6 function code) polled via `datee > lastcheck`, executed, then deleted — effectively vendor remote code execution (external:338-392). `usersourceupdate` is the sibling queue for drug price/unit updates.

### 6.7 API endpoint inventory (api_integration.md:397-411, feature_external_integrations.md:395-411)

ZATCA OAuth + submit; SFDA RSD SOAP; ETA `api.invoicing.eta.gov.eg`; HungerStation (`hungerstation.partner.deliveryhero.io`, token at `hungerstation.token.txt`); country/currency SOAP; QR `api.qrserver.com`; Google Charts; DrugEye `rsd-api/start.aspx`; news `TitanNews.txt`.

---

## 7. Gaps & open questions

1. **`wzmony` / `wzdaily` / `wzbank` — do real SQL tables exist?** No CREATE TABLE evidence anywhere in the corpus (schema_complete.md:763-774 lists only 5 CREATE TABLE statements). The feature docs use these names as shorthand for the `.phy`-backed money store (feature_sales_invoices.md:118 explicitly writes "`wzmony`-equivalent"; feature_reports_analytics.md:328, feature_invoice_editing.md:65-68,201, feature_discounts.md:79, feature_doctors_prescriptions.md:129 repeat the labels). **Open question:** in the deployed DB are there actually `wzmony`/`wzdaily`/`wzbank` tables (dropped or not extracted), or is all money purely `.phy` + `farysales`? The replacement should design explicit tables regardless (see §2.4).
1b. **RESOLVED 2026-08-15 — "the DrugEye download URL" is dead code.** Live download + corrected string-index decoder (2-byte `b0=0x40|idx>>8,b1=idx&0xFF`; 4-byte `idx=b1|b2<<8|b3<<16`) showed the URL, filenames, and all drugeye SQL have 0 p-code refs, and `drugeye.update.titan.rar` is a **ROT-4 text feed, not a RAR**. Drug data enters via **VB6 fixed-record `.phy` I/O** (see §6.3, drugeye_complete.md §7A/§9). (Formerly misread as a live download feature.)
2. **8 tables inferred from context only** (schema_complete.md:773-774): `farysales` (columns marked `[INFERRED]`, feature_account_closing.md:210-233), `wzaccfreetree` (feature_balances.md:182-186), `nilsen2` (schema_complete.md:469-482), `drugeyedash2` (schema_complete.md:598-612), `companies` (only `mobile`+`pass` — supplier master is under-extracted; feature_purchases.md:119-121 shows suppliers also live in `wzcustomers`), `taronlineeg`, `titanpharmalist`, `orders`. Column-level layout of these is reconstruction, not extracted DDL.
3. **`titanksasales` / `titaninn` schema divergence** between business_logic_complete.md:102-125 (line-item layout) and schema_complete.md:172-193,146-168 (summary layout). Both may be true across versions (the GUID insert loop predates a schema migration).
4. **`invoicedata` is a header+line hybrid** — invoice header and line items share one table (schema_complete.md:263-291). Whether `invoicedata` holds both purchases and sales (or is duplicated per kind) is inferred.
5. **`.phy` binary formats are undocumented and proprietary** ("created by titan www.pharorg.com/phye", drug_database_legal.md:83-101). Daily.phy / MonyInfo.phy / acctree.phy field layouts must be reverse-engineered or replaced wholesale; they cannot be parsed from this corpus.
6. **Day ledger scope of `farysales`**: named "fary (branch) sales" but used by balances, purchases, and returns as a general ledger (feature_balances.md:192). Whether *all* journal entries land there or only sales/branch postings is unproven.
7. **ZATCA counters/hashes live in files, not DB** — `counter.txt`/`hash.txt` under `C:\saturn\...` and `netcounter.phy` (tax:154). If a replacement must be audit-proof, the counter must move into the DB atomically with the invoice.
8. **DTTS ambiguity**: "DTTS" refers to both the **Saudi SFDA RSD SOAP** track & trace (`ModDTTS`, 48 procs) and the **Egyptian ETA DTTS** wrapper (`ModDttsEgypt`, 2 procs) — two different integrations under one acronym (tax:30-31; external:399-401).
9. **Supplier identity is two tables**: `companies` (mobile/pass) plus `wzcustomers` (typee discriminates supplier/customer). The exact merge key (mobile vs randomid) is not proven (feature_purchases.md:119-123).
10. **Money-per-user (`FormUsersMony`)**: per-user sales/money feeds the day close (feature_users_permissions_menus.md:122) but its storage (usersmony.phy? derived?) is partially documented.
11. **Legal/security red flags documented but unresolved for the replacement**: DrugEye data reuse (drug_database_legal.md:23-42), Nielsen data selling + HTTP-only uploads (phycodsystems_complete.md:740-750), AnyDesk silent access + `passedfunctions` RCE (phycodsystems_complete.md:712-716), unsigned HTTP distribution, hardware-fingerprint privacy (external:520-529).
12. **Country gating**: "Export to current country is forbidden" and per-country `.phy` drug files (external:516) — the exact country→file mapping is only partially extracted (feature_misc_modules.md:487 exchangeRate per country).

---

## Appendix A — File:line index of the strongest citations

- Schema tables + relationships: schema_complete.md:13-713, :716-757, evidence :763-774
- Business rules / modules: business_logic_complete.md:45-64 (overview), :228-363 (stock/inn/oot), :486-570 (ModMony/Backup/Amil), :746-792 (sales rules), :796-831 (purchase rules), :917-975 (price/VAT), :1136-1186 (backup & cloud), :1409-1420 (.phy file list)
- Sale chain: feature_sales_invoices.md:63, :112-124, :149-160, :275-283, :338
- Purchase chain: feature_purchases.md:127-155, :226-330, :375-395
- Returns: feature_sales_returns.md:72, :99, :181-182; feature_purchase_returns.md:87, :91, :145
- Day close: feature_account_closing.md:33-51, :59-83, :96-121, :156-167, :205-257
- Balances/accounting: feature_balances.md:40-46, :54, :70-72, :132-138, :175-208, :211-271, :326-340
- Stock counting: feature_stock_counting.md:20, :75, :201, :232-235
- Transfers: feature_transfers_logistics.md:86-138, :140-208, :210-236, :238-321, :524-532
- Tax: feature_tax_invoicing.md:56, :66-86, :118-155, :193-202
- External: feature_external_integrations.md:55-156 (DrugEye), :159-236 (Nielsen), :239-274 (Phycod), :277-392 (network/remote), :395-411 (endpoints), :520-529 (legal)
- **DrugEye feed = ROT-4 text, not RAR; download path is dead code (verified 2026-08-15):** drugeye_complete.md §7A (7A.1-7A.4), §9 "Verified dead code", §15.1; decoded feed `/tmp/opencode/drugeye.update.titan.decoded.txt` (23,452 records)
- Network chain tables: network_complete.md:602-615
- wzmony/wzdaily/wzbank shorthand: feature_sales_invoices.md:118; feature_invoice_editing.md:65-68,130-133,201,263; feature_reports_analytics.md:328; feature_discounts.md:79; feature_doctors_prescriptions.md:129
