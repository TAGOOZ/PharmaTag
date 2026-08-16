# SCHEMA_EVALUATION.md — Critical evaluation of the §2.3 replacement schema (money core)

Verdict: **NOT SAFE to adopt as-is** — it models a generic double-entry money core but drops the
pharmacy branch dimension, batch inventory, file-backed ledger truth, audit, approvals, shortages,
and e-invoice state that the legacy system depends on. Do not build the PostgreSQL DDL from §2.3
without the fixes in §3.

Sources: `connections_overview.html` §2.3 "Recommended replacement schema (money core)" (lines 449-471).
Ground truth: `schema_complete.sql` (28 tables), `SCHEMA_RESOLVED.md`, `GAPS_REPORT.md`,
`RECORD_LAYOUTS_daily_phy.md`, `EGYPT_ETA_DECOMPILED.md`, `ORPHAN_OBJECTS_VERIFIED.md`, 23 `feature_*.md`.
All line cites are `file:line`.

## §1 BAD — Design flaws / domain mismatches

### 1.1 Branch dimension is applied inconsistently — the proposal violates its own stated rule
- **Problem:** the §2.3 design rule says "every money row carries branch + date(+month/year) +
  creditdebit side + account path" (connections_overview.html:471), but the schema applies
  `branch_id` only to `journals`, `invoices`, `drawer_movements`, `daily_close`. `journal_lines`,
  `payment_splits`, `balances`, `monthly_close`, and `invoice_lines` have no `branch_id`.
- **Evidence:** connections_overview.html:450-470. Legacy keys every money/stock row by a pharmacy
  identity: `wzgard.phar`, `wzcustomers.phar` (schema_complete.sql:59,81); `titanstock.pharmacyid`
  (:146); `titanksasales.pharmacyid` (:118); `invoicedata.pharmacyid` (:173);
  `farysales.mobile` + `farysales.phar` (:413,:426); `wzaccfreetree.mobile` (:390);
  `titanpharmalist.mobile` (:400). Monthly close is per-branch (`\Files\Archive\monthy\`,
  feature_account_closing.md:81,193-194) yet `monthly_close` has no branch_id.
- **Why it breaks:** without branch on `journal_lines`/`balances` you cannot reproduce the customer
  ledger (كشف حساب), supplier payables, or the per-branch trial balance (ميزان); cross-branch
  consolidation is impossible. Per-branch month/year balances (`farysales.monthe/yearo`) are lost.
- **Fix:** add `branch_id NOT NULL` to `journal_lines`, `payment_splits`, `invoice_lines`,
  `balances`, `monthly_close`. Make `balances` key `(branch_id, account_id, month, year)` and make
  `monthly_close` key `(branch_id, year, month)`.

### 1.2 No batch/expiry table — `invoice_lines.batch_id` references a table that does not exist
- **Problem:** §2.3 declares `invoice_lines(..., batch_id, ...)` (connections_overview.html:459) but
  defines no `batches` table anywhere in the 11-table proposal. Legacy inventory is batch/expiry
  based in `wzgard`: `phar, randomid, datee, quant, expire, price, oldstock, costvalue, vatvalue,
  totalwithvat, typee, drugname` (schema_complete.sql:58-74); `typee` discriminates
  sale|purchase|return|count.
- **Evidence:** purchase chain writes a NEW batch row to wzgard (connections_overview.html:501);
  sales decrement batches; sales returns add quantity back (connections_overview.html:518);
  negative-balance repair moves units between expiry batches (feature_stock_counting.md:257);
  opening stock enters as special purchase batches (connections_overview.html:512).
- **Why it breaks:** no batch table means no FIFO/expiry sale selection, no cost-value per batch
  (COGS and ربح اليوم at close depend on `costvalue`), no expiry tracking (مخزون منتهي), and no
  `oldstock` audit trail per movement.
- **Fix:** add `stock_batches(id, branch_id, drug_id, randomid, qty, expire, cost, vat, price,
  oldstock, typee[sale|purchase|return|count], created_by, created_at)` mirroring wzgard, with a
  unique key on `(branch_id, drug_id, randomid)`.

### 1.3 "Which pharmacy?" has three legacy aliases (phar / pharmacyid / mobile) — the proposal unifies but ignores the migration mapping and cross-branch sync semantics
- **Problem:** legacy code uses three different column names for the branch identity across tables
  (connections_overview.html:372: `phar`/`pharmacyid`/`mobile`), and cross-branch sync is
  "last-write-wins, no merge" (connections_overview.html:686). The proposal's single `branch_id` is
  the right unification, but nothing defines (a) the alias→branch mapping for migration, or (b) a
  sync/replication conflict record.
- **Evidence:** `farysales.mobile` is the branch key but `farysales.phar` also exists
  (schema_complete.sql:413,426); `wzaccfreetree.mobile` (a chart-of-accounts row) uses mobile;
  `companies.mobile` is a SUPPLIER phone (PK) — mobile means pharmacy in some tables and supplier in
  others. `titaninn.source/target` are free-text NVARCHAR(100) not FKs (schema_complete.sql:105-107).
  Chain sync writes `titanksasales` via the GUID loop (SCHEMA_RESOLVED.md:41) and is "no merge".
- **Why it breaks:** without an explicit branch-identity table the migration cannot decide which
  legacy column maps to which branch; without a sync/log table the replacement cannot reproduce
  multi-branch replication or the "main device" / sub-device roles (الجهاز الرئيسي guards,
  feature_operational_utilities.md:34).
- **Fix:** add `branch_identities(legacy_table, legacy_column, legacy_value, branch_id)` for
  migration, and a `sync_log(branch_id, entity, entity_id, action, payload, synced_at, status)`
  outbox to reproduce last-write-wins replication.

### 1.4 Account model: journals/journal_lines cannot reproduce the legacy ledger without branch + month/year + per-branch account trees
- **Problem:** legacy accounting stores (a) chart of accounts per branch
  (`wzaccfreetree(mobile, master, fary)`, schema_complete.sql:388-393) and (b) ledger rows with
  `father/son/creditdebit/payed/monthe/yearo/mobile/phar` (`farysales`, schema_complete.sql:411-431).
  The proposal's `accounts(id, code, parent_id, ...)` has no branch dimension and `balances` has no
  month/year key; the customer ledger (كشف حساب), supplier payables and trial balance (ميزان) are
  computed from farysales per branch AND per month/year.
- **Evidence:** feature_accounting_ledger.md:126-127 "entries are per-branch ... journal entries
  write farysales (per branch)"; farysales INSERT is LIVE in 3 procs with the full 17-col list
  including `monthe, yearo, creditdebit` (SCHEMA_RESOLVED.md:196-200); trial balance/balance sheet
  feeds from balances with "chronological balance sequence validated" (connections_overview.html:635).
  Manual journal entries require a description first (feature_balances.md:301, idx 8637) — the
  proposal's `journals.description` must be required, not optional.
- **Why it breaks:** a generic double-entry pair without branch/month/year keys cannot reproduce
  كشف حساب (per-customer over months), the monthly ميزان, or monthy\moves + start-data archival.
  Per-branch account trees (each branch defines its own fary/masters) are flattened.
- **Fix:** add `branch_id` to `accounts` (or `branch_id, parent_id` composite for the tree), add
  `(month, year)` keys to `balances` and `journal_lines` (denormalized from date), and add a
  `monthly_close_lines` table for monthy\moves instead of a JSON blob.

### 1.5 No .phy migration path — the money truth is in serialized files, not SQL
- **Problem:** the proposal puts `drawer_movements`/`daily_close` in SQL, but the legacy truth is
  `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`, `daily-manual.phy/-2`,
  `fary.date.phy`, `closefary.phy`, `acctree.phy/-2`, `RasidCorrect.phy`, `usersmony.phy`,
  `workperiod.phy`, `delivery.phy`, `oot3.phy`, `netcounter.phy`, `myftp.phy`, `DDI.Phy`,
  `Accounting\moves\`, `monthy\moves + start-data`, `Phye.safer` (connections_overview.html:389).
  There is no import/ETL strategy in §2.3.
- **Evidence:** Daily.phy layout is now known — record length 614 B, loop cap 40000, load loop
  16000, date base 44000 (RECORD_LAYOUTS_daily_phy.md:27,46-50,52-66); daily-manual 52 B,
  daily-manual-2 56 B (:29-32). But MonyInfo, usersmony, closefary, fary.date, delivery, workperiod,
  oot3, netcounter, RasidCorrect, acctree layouts are NOT mapped (RECORD_LAYOUTS_daily_phy.md:81-82;
  connections_overview.html:700).
- **Why it breaks:** the replacement claims to own the drawer/close history but cannot import a
  single day's history without a per-file record map; money-per-user (usersmony) and close flags
  (closefary) have no SQL home at all.
- **Fix:** define a migration plan mapping each .phy file to a target table and document that
  Daily*.phy (614/52/56 B, caps 40000/16000/44000) map to `drawer_movements`+`daily_close`;
  schedule a layout pass for the remaining 12 files as a release-blocking task before cutover.

### 1.6 No audit trail — TitanUserAction is a real, live table the proposal omits
- **Problem:** the proposal has zero audit tables. Legacy logs drug/price/balance changes to
  `TitanUserAction` (11 cols: drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode,
  curprice, units, datee + id; schema_complete.sql:266-278). Invoice editing (تعديل فواتير) reverses
  and re-applies money/journal .phy and must be traceable (connections_overview.html:576).
- **Evidence:** TitanUserAction is written on sales, purchases, returns, stock counts, balance
  corrections and manual changes (connections_overview.html:489,508; feature_purchases.md:395;
  feature_stock_counting.md). Its INSERT column list matches the schema (SCHEMA_RESOLVED.md:101).
- **Why it breaks:** without who/what/when/old→new (per drug and per money row) the replacement
  cannot answer "who changed this balance?" which the legacy can, and invoice edits become
  un-auditable.
- **Fix:** add `audit_log(id, branch_id, user_id, entity, entity_id, field, old_value, new_value,
  drug_id, barcode, action, created_at)` and require every money/stock mutation to write one row in
  the same transaction. Add `invoice_versions` (or soft-delete + reversal rows) for editing.

### 1.7 No approval workflow — staff-request → manager accept/reject for stock corrections
- **Problem:** legacy stock counts/corrections flow through a manager approval gate
  (connections_overview.html:541: "APPROVAL · staff request → manager accept/reject");
  feature_stock_counting describes تصحيح الارصدة commands (بالزيادة/بالعجز) and the count screen.
- **Why it breaks:** allowing any cashier to adjust balances directly removes a real internal
  control the legacy enforces; the replacement must reproduce the pending/approved/rejected state.
- **Fix:** add `stock_correction_requests(id, branch_id, drug_id, batch_id, delta, reason, requested_by,
  status[pending|approved|rejected], approved_by, decided_at)`; the actual wzgard/titanstock change
  is applied only on approval.

### 1.8 Shortages (نواقص) — three sub-systems + titanneed/orders are absent
- **Problem:** legacy shortage detection is three systems (manual / half-auto / sales-rate) that
  flag drugs below minimum into `titanneed` and drive `orders` (connections_overview.html:625;
  feature_shortages.md). Neither titanneed nor orders nor a shortage flag table appears in §2.3.
- **Evidence:** titanneed = `id, drugname, quant, datee, sender, target` (schema_complete.sql:156-163,
  LIVE CREATE ×2 SCHEMA_RESOLVED.md:80-83); orders = pending while status NULL
  (schema_complete.sql:192-199); sale chain feeds shortages (connections_overview.html:493);
  per-branch minimums live in titanksastock.minimum (schema_complete.sql:133).
- **Why it breaks:** reorder automation and inter-branch needs are core pharmacy workflows; without
  them the replacement cannot run نواقص reports (RPT-ST01) or auto-POs.
- **Fix:** add `shortage_flags(branch_id, drug_id, current_qty, minimum, method, flagged_at)`,
  `needs(id, branch_id, drug_id, qty, status, created_at)` ← titanneed, and `purchase_orders`
  ← orders.

### 1.9 Non-money file-backed state has no home in the replacement
- **Problem:** §2.3 covers drawer money and accounting only. These legacy files are not money but
  the replacement must own their state: `workperiod.phy` (work periods/shifts), `delivery.phy`
  (transfers), `DDI.Phy` (drug-drug interactions), `oot3.phy`/`netcounter.phy` (counters/hash for
  ZATCA QR), `myftp.phy` (FTP config), `usersmony.phy` (money per user/shift), `acctree.phy/-2`
  (chart-of-accounts mirror), `RasidCorrect.phy` (balance-correction log), `fary.date.phy`/
  `closefary.phy` (per-branch close flags), `Phye.safer` (backup).
- **Evidence:** connections_overview.html:389; feature_reports_analytics.md:302 (FormPrinterSettings
  branch twin); feature_sales_invoices.md:118 (usersmony); feature_accounting_ledger.md:36-38.
  `drawer_movements.shift_id` is declared (connections_overview.html:463) but no `shifts` table
  exists.
- **Why it breaks:** shift handover (تسليم الدرج RPT-A04), drug-interaction checks for prescriptions
  (feature_doctors_prescriptions), ZATCA counter/hash integrity, and per-user money all lose their
  storage; `shift_id` is a dangling reference.
- **Fix:** add `shifts(id, branch_id, work_period_id, opened_by, opened_at, closed_at)` ←
  workperiod.phy; `drug_interactions(drug_a, drug_b, severity, note)` ← DDI.Phy;
  `einvoice_counters(branch_id, kind, last_counter, last_hash)` ← oot3/netcounter (moved INTO the DB,
  see connections_overview.html:702 "move counter into DB atomically with invoice");
  `user_drawer_money(branch_id, user_id, shift_id, date, cash, card, ...)` ← usersmony.

### 1.10 E-invoice state is entirely missing — ZATCA log table + Egypt ETA JSON are live
- **Problem:** the proposal omits any e-invoice/outbox table. Legacy `ZATCA` is a real log:
  `invoiceid, uuid, datee, pharmacyid, status, hash, xml, response` (schema_complete.sql:436-446).
  The ETA/ZATCA invoice JSON fragments (idx 228-267) and QR generation ARE live and used even though
  the network submission URLs are dead (EGYPT_ETA_DECOMPILED.md:5-16; connections_overview.html:675).
- **Evidence:** sale chain emits a tax invoice row (connections_overview.html:488-489,523); the ZATCA
  row is written per invoice (connections_overview.html:673); Egypt ETA must be implemented from
  scratch using the recovered JSON shapes (connections_overview.html:675). The proposal's `invoices`
  table has no e-invoice status/hash/xml.
- **Why it breaks:** the replacement cannot re-submit, track uuid/hash, or produce QR codes without
  a per-invoice e-invoice record; audit of "was this invoice submitted to the tax authority?" is lost.
- **Fix:** add `einvoice_log(id, invoice_id, branch_id, kind[zatca|eta], uuid, status,
  hash, payload_xml, payload_json, response, submitted_at)` ← legacy ZATCA; add a resubmission
  workflow. Do NOT build network submission to the dead Saudi/Egypt URLs, but keep the JSON/QR
  generation.

### 1.11 Other objective flaws (types, missing columns, config)
- **Money types:** legacy stores money as VB6 REAL/Single/R8 (`payed REAL`, `agel REAL`,
  schema_complete.sql:119,121; Daily.phy Single/R8 fields, RECORD_LAYOUTS_daily_phy.md:58-64). The
  proposal shows no column types. The replacement MUST use NUMERIC(18,x), never REAL/float, for
  money — and must define rounding rules because the legacy precision loss is baked into historical
  data (migration must not re-sum floats).
- **payment_splits.method enum is too small:** legacy splits cash/شبكة/أجل AND tracks manual cash
  and manual شبكة (كاش يدوي / شبكة يدوي in the daily totals, feature_sales_invoices.md:118; idx
  9883). `method[cash|card|credit]` cannot represent "manual cash" vs "card terminal" vs "أجل".
  Add `cash|card|credit|manual_cash|manual_card` (+ the legacy `payed/agel` split rule
  totalvalue = payed + agel, connections_overview.html:418).
- **daily_close is missing half the day's aggregates:** legacy daily totals include
  كاش/كاش يدوي/شبكة/شبكة يدوي/محسوب المبيعات/تكلفة مبيعات اليوم/ربح اليوم/خصومات اليوم/
  ضريبة المبيعات اليوم/حركة مالية (idx 9883, feature_sales_invoices.md:118). The proposal's
  `daily_close` has net_cash, net_network, purchases, expenses, vat_sales/purchases/expenses but NO
  manual_cash, manual_card, cost_of_sales, net_profit, discounts, drawer@start-of-period, or
  shift_id — the profit day report (ربح اليوم) and RPT-A04 drawer handover cannot be computed.
- **No invoice statuses / states:** legacy invoices have Saved/Unsaved/Un save/Copy/Transfer to
  sales return/Transfer to purchases (feature_sales_invoices.md:3). The proposal's
  `status[open|saved|closed|archived]` covers some but drops Copy, "Un save", and the transfer
  states; and `invoices.kind[transfer]` implies a transfer table that does not exist.
- **No opening-balances entity:** legacy seeds opening drawer cash, opening stock at cost excl. VAT,
  opening customer receivables, opening supplier payables (feature_balances.md:72, idx 8482-8485),
  and "assume balances correct" special purchase invoices (feature_stock_counting.md:67-72,146-147).
  `monthly_close.start_balances_json` is a JSON anti-pattern and there is no per-account opening
  balances table.
- **No region dimension:** legacy codes governorate:district (Mohafaza/Markaz in ChainBuyUsers,
  schema_complete.sql:330-331,347-348; "اسيوط:البداري" list in FormAccAddQueed,
  feature_accounting_ledger.md:55). The proposal has no region field for branches/parties.
- **No currency/VAT config:** VAT default 15% (Gulf) vs Egypt 14% must be country-configurable
  (connections_overview.html:708; feature_balances.md:147; `storediscount.country`,
  schema_complete.sql:224). The proposal hard-codes nothing but also models nothing.
- **Unit conversions dropped:** wzdrugs has `units` (pack) and `Unitsmall` (schema_complete.sql:24-25);
  purchases/sales/transfers convert units ↔ small units. `invoice_lines.qty` needs a unit field and
  a unit-conversion table.
- **Barcode multiplicity:** wzdrugs has `barcode` + `Barcode1..5` (schema_complete.sql:17-22) — a
  drug is found by ANY of up to 6 barcodes. The proposal's `invoices.drug_id` lookup needs a
  `drug_barcodes(drug_id, barcode)` child table with a unique index, otherwise scans by the
  alternate codes break.
- **Parties have no branch:** `wzcustomers.phar` and `companies.mobile` mean a customer/supplier is
  branch-scoped (schema_complete.sql:81,93). `parties` needs branch_id (or a branch_party link) and
  the dual identity (companies.mobile vs wzcustomers.randomid) must be merged explicitly
  (connections_overview.html:704).
- **Trial-balance invariant:** ModAccounting enforces debit = credit per journal (feature_balances.md:
  328). The proposal must add a CHECK constraint per journal that SUM(debit)=SUM(credit) and a
  unique journal entry sequence per (branch_id, date).

### 1.12 Referenced-but-undefined tables — the proposal is not self-contained
- **Problem:** `invoice_lines.drug_id`, `invoice_lines.batch_id`, `drawer_movements.user_id` and
  `drawer_movements.shift_id` all reference tables that do not exist in the 11-table list
  (connections_overview.html:450-470). There is no `branches`, `drugs`, `batches`, `users`, or
  `shifts` table anywhere in the proposal.
- **Evidence:** `parties/accounts/journals/journal_lines/invoices/invoice_lines/payment_splits/
  drawer_movements/daily_close/monthly_close/balances` = 11 tables; `branch_id` is used as a FK in
  four of them but `branches` is never declared; `drug_id` is used but no drug master; legacy drug
  master is `wzdrugs` (schema_complete.sql:14-43) and users/roles/permissions gate every feature
  (feature_users_permissions_menus.md, الصلاحية 1-9 at :84).
- **Why it breaks:** a builder cannot create the DDL — FK targets are undefined; users and
  permissions (which control sale/edit/close rights) have no storage.
- **Fix:** add `branches` (← wzphar, PK branch_id; keep legacy pharmacyid/phar/mobile as natural-key
  columns for migration), `drugs` (← wzdrugs with barcode1..5 child table), `users` +
  `role_permissions` (← FormUsers/FFFUserEdit), `shifts` (see 1.9), and `stock_batches` (see 1.2).

## §2 MISSED — Legacy table / .phy file coverage checklist

Legend: **Covered** = proposal table can absorb it (with the caveats in §1); **MISSING** = no home;
**SKIP** = do not replicate (vendor/legal). Evidence col cites `schema_complete.sql` (§n) or the feature doc.

### 2.1 SQL tables (28 from schema_complete.sql + GAPS orphans)

| Legacy table | Covered by proposal table? | Gap | Suggested replacement entity |
|---|---|---|---|
| `wzdrugs` (§1) | MISSING — no drug master | `drug_id` has no target; barcode1..5, units/Unitsmall, vat, PriceNow, history lost | `drugs` + `drug_barcodes` + `unit_conversions` |
| `wzdrugs2` (§2) | MISSING | unitcost/costvalue/expire extension | `drug_costs(branch_id, drug_id, unitcost, expire)` |
| `wzgard` (§3) | MISSING — only `invoice_lines.batch_id` string | no batch table at all; oldstock/costvalue/vatvalue/totalwithvat/typee lost | `stock_batches` (see 1.2) |
| `wzcustomers` (§4) | ~ `parties` | typee discriminator + `phar` branch scoping + creditlimit; dual identity with companies | `parties(branch_id, kind, typee, credit_limit)` |
| `companies` (§5) | ~ `parties` | PK mobile (a *supplier phone*) clashes with branch mobile aliases; merge key undefined (connections_overview.html:704) | `supplier_master` or fold into parties with explicit merge |
| `titaninn` (§6) | MISSING | transfer+PO queue, `itemsasstring` serialized lines, source/target free text; `invoices.kind[transfer]` has no transfer table | `transfers` + `transfer_lines` |
| `titanksasales` (§7) | ~ `invoices` | chain-sales replication outbox (GUID loop), silsilaid | `sync_outbox` / chain sales view |
| `titanksastock` (§8) | MISSING | per-chain-branch stock + `minimum` | `branch_stock(branch_id, drug_id, qty, minimum, silsilaid)` |
| `titanstock` (§9) | MISSING | per-branch drug stock levels, lastedit | `branch_stock` |
| `titanneed` (§10) | MISSING | needs requests (sender/target) | `needs` (see 1.8) |
| `invoicedata` (§11) | ~ `invoices`+`invoice_lines` | header+lines hybrid in ONE row; migration must split correctly (SCHEMA_RESOLVED.md:150-161) | `invoices` + `invoice_lines` |
| `orders` (§12) | MISSING | pending-while-NULL status | `purchase_orders` (see 1.8) |
| `wzphar` (§13) | MISSING — no `branches` | the whole branch hub is absent (see 1.12) | `branches` |
| `storediscount` (§14) | MISSING | price/discount change log with country, pharmacyname | `price_change_log` (or fold into audit_log) |
| `drgserver` (§15) | MISSING | server drug list / chain drug sync | `drug_sync_outbox` |
| `remotecontrol` (§16) | SKIP | vendor RCE channel (connections_overview.html:687) — do NOT replicate | none |
| `TitanUserAction` (§17) | MISSING | real audit table (see 1.6) | `audit_log` |
| `usersourceupdate` (§18) | MISSING | sync log, 3000-row pull, delete-on-apply | `sync_log` (see 1.3) |
| `nilsen2` (§19) | SKIP | data-selling (connections_overview.html:679) — do NOT replicate | none |
| `taronlineeg` (§20) | MISSING | online EG drug catalog (7-col; SCHEMA_RESOLVED.md:190-193) | `external_drug_catalog` |
| `ChainBuyStore` (§21) | MISSING | store-level chain buy orders | `chain_buy_orders` |
| `ChainBuyUsers` (§22) | MISSING | user-level chain buy orders + Mohafaza/Markaz region | `chain_buy_orders` |
| `RawakidTablew` (§23) | MISSING | dead-stock (رواكد) exchange | `dead_stock_exchange` |
| `drugeyedash2` (§24) | SKIP/optional | dashboard mirror of an external MySQL DB (GAPS_REPORT.md:91) | optional cache |
| `wzaccfreetree` (§25) | ~ `accounts` | per-branch tree (mobile), master/fary parent-child (see 1.4) | `accounts(branch_id, code, parent_id, ...)` |
| `titanpharmalist` (§26) | MISSING | registered-pharmacy registry (PK mobile) | `branch_registry` / sync participants |
| `farysales` (§27) | ~ `journal_lines`+`balances` | LIVE 17-col ledger; monthe/yearo, creditdebit, per branch (see 1.4) | `journal_lines`+`balances` with (branch_id, month, year) |
| `ZATCA` (§28) | MISSING | e-invoice log (see 1.10) | `einvoice_log` |
| `wzsuppliers` (feature_reports_analytics.md:327) | ~ `parties` | docs-only alias for supplier side of wzcustomers | `parties(kind='supplier')` |

### 2.2 .phy / file-backed state (money + non-money)

| File | Covered by proposal table? | Gap | Suggested replacement entity |
|---|---|---|---|
| `Daily.phy` (614 B) | ~ `drawer_movements`+`daily_close` | no import path; layout partially known (RECORD_LAYOUTS_daily_phy.md:52-66); offsets 0x3c..614 UNKNOWN | migrate→drawer_movements (see 1.5) |
| `Dailyline.phy` / `Dailymax.phy` | ~ `drawer_movements` | migrated successors, layout unobserved (RECORD_LAYOUTS_daily_phy.md:21) | migrate→drawer_movements |
| `MonyInfo.phy` | ~ `daily_close` | snapshot file; no SQL home today | daily_close snapshot columns |
| `daily-manual.phy` / `daily-manual-2.phy` (52/56 B) | MISSING | manual journal entries (feature_account_closing.md:73) | `manual_journal_entries` / journal source='manual' |
| `fary.date.phy` | MISSING | per-branch date/close flag (connections_overview.html:554) | `daily_close.status` / branch calendar |
| `closefary.phy` | MISSING | branch close flag (feature_account_closing.md) | `daily_close.status` |
| `acctree.phy` / `acctree2.phy` | ~ `accounts` | chart-of-accounts mirror (feature_accounting_ledger.md:126) | derived from accounts; migration source |
| `RasidCorrect.phy` | MISSING | balance-correction log (feature_stock_counting.md:201) | `stock_correction_requests` (see 1.7) |
| `usersmony.phy` | MISSING | money per user/shift (feature_sales_invoices.md:118; FormUsersMony) | `user_drawer_money` (see 1.9) |
| `workperiod.phy` | MISSING | work periods / shifts (feature_reports_analytics.md) | `shifts`/`work_periods` (see 1.9) |
| `delivery.phy` | MISSING | transfer delivery state (feature_transfers_logistics.md) | `transfers.status` |
| `oot3.phy` / `netcounter.phy` | MISSING | ZATCA QR counter/hash (feature_tax_invoicing.md) | `einvoice_counters` in DB (see 1.9) |
| `myftp.phy` | MISSING | FTP config (feature_external_integrations.md) | `integration_config` |
| `DDI.Phy` | MISSING | drug interactions (feature_doctors_prescriptions.md) | `drug_interactions` (see 1.9) |
| `Accounting\moves\` | ~ `journal_lines` | journal file store (feature_accounting_ledger.md:37) | journal_lines source |
| `monthy\moves` + `monthy\start-data` | ~ `monthly_close` | per-branch opening balances; JSON blob is wrong shape (see 1.11) | `month_open_balances(branch_id, account_id, debit, credit)` |
| `Archive\Input` + `Archive\Output` | MISSING | fat import/export archive | `archive_imports`/`archive_exports` |
| `Titan3-Backup\{Daily,Monthly,Export,xj}` | MISSING | close-time backups, Phye.safer | backup job config + archive log (feature_backup_archive_import.md) |
| `Phye.safer` | MISSING | encrypted safety backup | backup store (format UNKNOWN) |
| `counter.txt` + `hash.txt` (C:\saturn) | MISSING | ZATCA chain (connections_overview.html:389) | `einvoice_counters` (see 1.9) |
| `ismaster.txt` | MISSING | main-device flag (feature_invoice_editing.md:202) | `branches.is_main_device` |
| `LastEdited.phy` | MISSING | last-edited invoice list (feature_invoice_editing.md:202) | `invoices.last_edited_at` index |
| `drugeye-for-titan.phy` / `fromdrugeye.phy` / `DRUGS.PHY` | SKIP/optional | DrugEye feed; ROT-4 text, legal caveat (connections_overview.html:677) | external catalog import (optional) |

## §3 Priority — top fixes by severity (ranked)

1. **Add the missing core tables (blocker):** `branches`, `drugs`(+`drug_barcodes`), `stock_batches`
   (← wzgard), `users`+permissions, `shifts`. Without them `branch_id`/`drug_id`/`batch_id`/`user_id`/
   `shift_id` are dangling FKs and the DDL cannot be created (§1.12, §1.2).
2. **Add `branch_id` everywhere** money/stock lives: `journal_lines`, `payment_splits`,
   `invoice_lines`, `balances`, `monthly_close` — and make balances/monthly_close carry
   `(branch_id, year, month)` to reproduce farysales monthe/yearo and per-branch ميزان/كشف حساب (§1.1, §1.4).
3. **Design the .phy migration path now** — it decides the whole ETL. Daily*.phy layouts are partially
   known (614/52/56 B, caps 40000/16000, base 44000); the remaining 12 money/state files
   (MonyInfo, usersmony, closefary, fary.date, delivery, workperiod, oot3, netcounter, RasidCorrect,
   acctree, PIFary, drugeye) need a layout pass before cutover; never re-sum legacy REAL/floats as
   NUMERIC without rounding rules (§1.5, §1.11).
4. **Add an audit trail** `audit_log` (← TitanUserAction) written atomically with every money/stock/
   balance mutation, plus invoice-edit reversal versions (§1.6).
5. **Add e-invoice state** `einvoice_log` (← ZATCA) + DB-resident `einvoice_counters` for the ZATCA
   QR counter/hash; keep ETA/ZATCA JSON/QR generation, skip the dead submission URLs (§1.10, §1.9).
6. **Add approvals + shortages:** `stock_correction_requests` (staff→manager), `shortage_flags`,
   `needs` (← titanneed), `purchase_orders` (← orders) (§1.7, §1.8).
7. **Fix `payment_splits.method`** to cover cash/card/credit/manual_cash/manual_card and preserve the
   `payed`/`agel` split identity totalvalue = payed + agel (§1.11).
8. **Complete `daily_close`:** add manual_cash, manual_card, cost_of_sales, net_profit (ربح اليوم),
   discounts, drawer@start, shift_id, work_period_id (§1.11).
9. **Define the cross-branch identity + sync model:** `branch_identities` alias map
   (phar/pharmacyid/mobile) and a `sync_log` outbox reproducing last-write-wins replication for
   titanksasales/titanstock/titanksastock/usersourceupdate/titaninn (§1.3, §2.1).
10. **Replace `monthly_close.start_balances_json`** with `month_open_balances(branch_id, account_id,
    debit, credit)` seeded from opening stock/payables/receivables/drawer (idx 8482-8485) and
    monthy\start-data; add region + currency/VAT-country config (§1.11).
11. **Add the chain/inter-pharmacy tables** the money core touches: `transfers`+`transfer_lines`
    (← titaninn), `branch_stock` (← titanstock/titanksastock), `chain_buy_orders`
    (← ChainBuyStore/Users/RawakidTablew), and decide the status enum for invoices including
    Copy/"Un save"/transfer states (§1.11, §2.1).

## Bottom line
The §2.3 core is a reasonable skeleton for the drawer/ledger money path, but it is not a deployable
schema: it omits the entities its own FKs reference, drops the branch dimension on half the money
rows, and has no home for batches, audit, approvals, shortages, e-invoices, shifts, or any of the
`.phy` files that are the actual legacy source of truth. Fix the top 10 (§3) before writing DDL.