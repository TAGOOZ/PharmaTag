# TITAN.W1 → Modern Replacement — Database Schema Design

**Scope:** canonical PostgreSQL schema (FastAPI backend) with a SQLite-dialect twin
(Tauri + React desktop, offline-first) and a Next.js web client that reads/writes via the
FastAPI API. This document is the design companion to:
- `schema_postgres.sql` — complete ordered PostgreSQL DDL
- `schema_sqlite.sql` — same design, SQLite dialect (Tauri offline store)

**Sources (in order of authority):**
1. `titan_extract/SCHEMA_EVALUATION.md` — §1 design flaws (1.1–1.12), §2 coverage checklist (§2.1 all 28 tables, §2.2 all .phy files), §3 ranked fixes. **Primary spec.**
2. `titan_extract/SCHEMA_RESOLVED.md` — 11 DDL contradictions adjudicated; all 11 adopted as-is (the `schema_complete.sql` shapes win).
3. `titan_extract/schema_complete.sql` — the 28 legacy tables with real column types.
4. `titan_extract/PHY_MIGRATION.md` — .phy record lengths/layouts + the Wine-verified file-size factorisation method.
5. `titan_extract/GAPS_REPORT.md` — stack confirmation (line 5) and residual gaps.

Citation convention used throughout: `SCHEMA_EVALUATION §n ← legacy_entity`.

---

## 1. Cross-cutting decisions

### 1.1 Branch dimension EVERYWHERE money/stock lives (SCHEMA_EVALUATION §1.1, §1.4)
The §2.3 skeleton applied `branch_id` to only `journals`/`invoices`/`drawer_movements`/
`daily_close`. Here `branch_id NOT NULL` is carried on **every** money/stock/ledger row:
`journal_lines`, `payment_splits`, `invoice_lines`, `balances`, `monthly_close`,
`month_open_balances`, `stock_batches`, `branch_stock`, `transfers`, `needs`,
`user_drawer_money`, `audit_log`, `sync_log`, `einvoice_log`, `price_change_log`. This is
what makes the customer ledger (كشف حساب), the per-branch trial balance (ميزان), and
cross-branch consolidation reproducible from `farysales.mobile/phar/monthe/yearo`
(schema_complete.sql:411-431).
- `balances` key = `(branch_id, account_id, month, year)` → reproduces `farysales.monthe/yearo`.
- `monthly_close` key = `(branch_id, year, month)` → per-branch تقفيل الشهر (monthy\moves).
- `month_open_balances(branch_id, account_id, debit, credit)` replaces the JSON anti-pattern
  `monthly_close.start_balances_json` (§1.11).

### 1.2 Money typing discipline + rounding rule (SCHEMA_EVALUATION §1.11, §3.3)
- **All money is exact decimal.** PostgreSQL: `NUMERIC(18,2)` for monetary totals and
  balances; `NUMERIC(18,4)` for per-unit cost/price and quantities; `NUMERIC(5,2)` for
  VAT/discount **rates** (percent). `REAL`/`float`/`double` are **never** used for money.
- **Rounding rule:** round-**half-up** to 2 decimal places at every line-total and every
  payment boundary (i.e., `line_total = round(unit_price × qty × (1 − disc) × (1 + vat), 2)`).
  Per-unit prices/costs keep 4 decimal places internally and are only rounded to 2 dp when
  multiplied into a total. This is the single rounding point; the app layer (FastAPI for the
  server, a shared money module in the Tauri app) is the only place rounding happens.
- **Legacy import:** VB6 `Single`/`Double` (R4/R8) money fields in the .phy files and
  `schema_complete.sql` `REAL` columns are converted **once** at import time by rounding the
  float to 4 dp (`round(float, 4)`), then stored as NUMERIC. Historical totals are **never
  re-summed from floats** — each stored row is a fixed decimal; aggregation happens in SQL on
  the decimal columns (§3.3: "never re-sum legacy REAL/floats as NUMERIC without rounding
  rules").
- **SQLite (offline twin):** SQLite has no exact decimal type; `NUMERIC` affinity degrades to
  IEEE double for fractional values. Therefore every decimal column in the SQLite dialect is
  stored as `INTEGER` in **minor units** — `value × 10^scale`. Amounts/totals (PG
  `NUMERIC(18,2)`) are stored ×100; unit prices/costs and quantities (PG `NUMERIC(18,4)`)
  are stored ×10000; rates (PG `NUMERIC(5,2)`) ×100; conversion factors (PG
  `NUMERIC(18,6)`) ×1000000. Rationale: **integers make money exactness a schema invariant**
  (no double can ever be inserted), at the cost of a single ×10^scale conversion at the app
  boundary — which the shared money module already owns. See §6.

### 1.3 Audit-everything (SCHEMA_EVALUATION §1.6, §3.4)
`audit_log` (← `TitanUserAction`, 11-col, SCHEMA_RESOLVED §4) is written **in the same
transaction** as every money/stock/balance mutation: sale, purchase, return, count,
correction, manual change. Every money/stock table in both DDL files carries a comment:
*"every write MUST also insert a row into `audit_log` atomically."* Invoice edits (تعديل
فواتير) additionally push a full pre-edit snapshot into `invoice_versions` so the
reverse-then-reapply pattern of the legacy .phy edit is reconstructable.

### 1.4 Sync model — last-write-wins outbox (SCHEMA_EVALUATION §1.3, §3.9)
Cross-branch replication in the legacy is "last-write-wins, no merge"
(connections_overview.html:686), with three legacy aliases for the branch identity
(`phar` / `pharmacyid` / `mobile`). Two tables reproduce this:
- `branch_identities(legacy_table, legacy_column, legacy_value, branch_id)` — the
  alias→branch map used by the migration (e.g. `farysales.mobile='05xxx'` → branch 3).
- `sync_log(branch_id, entity, entity_id, action, payload, synced_at, status)` — a
  durable outbox; each mutating write also enqueues an outbox row; the syncer applies rows
  to peer branches last-write-wins and marks `applied` (← `usersourceupdate` 3000-row pull /
  delete-on-apply). Chain sales (`titanksasales` 9-col, GUID loop) and chain stock
  (`titanksastock`) replicate through the same outbox with `silsilaid` preserved.
- `drug_sync_outbox` (← `drgserver`) covers the server drug-list channel.
- `branches.is_main_device` (← `ismaster.txt`) reproduces the الجهاز الرئيسي gate.

### 1.5 E-invoice state lives IN the DB (SCHEMA_EVALUATION §1.10, §1.9)
- `einvoice_log` (← legacy `ZATCA`: invoiceid/uuid/datee/pharmacyid/status/hash/xml/response)
  adds `branch_id`, `kind[zatca|eta]`, `payload_json`, `submitted_at`, plus QR-gen support
  columns `qr_counter`/`qr_hash`/`qr_data`.
- `einvoice_counters(branch_id, kind, last_counter, last_hash)` moves the ZATCA
  counter/hash chain (`oot3.phy`/`netcounter.phy`/`counter.txt`+`hash.txt`) into the DB,
  updated atomically with each invoice (connections_overview.html:702).
- Per EGYPT_ETA_DECOMPILED.md the Egypt ETA URLs are **dead** in this build: we keep the
  JSON/QR generation but do **not** build network submission to the dead Saudi/Egypt URLs.

### 1.6 Surrogate ids + preserved legacy natural keys (SCHEMA_EVALUATION §1.12)
Every table gets a surrogate `id`; legacy natural keys are kept as **unique, indexed
columns** so the ETL can upsert idempotently:
- `branches.pharmacyid` (unique) + `phar` + `mobile` (unique).
- `drugs.drugname` (unique) — legacy PK and tar.phy English-name key.
- `parties.randomid` (unique per branch) — `wzcustomers.randomid`.
- `stock_batches` unique `(branch_id, drug_id, randomid)` — `wzgard` batch identity.
- `accounts` unique `(branch_id, code)`; `balances` PK `(branch_id, account_id, month, year)`.

### 1.7 Other §1.11 fixes adopted
- **Barcode multiplicity:** `drug_barcodes(drug_id, barcode, is_primary)` child of `drugs`,
  with a unique index on `barcode` alone so a drug is found by ANY of the 6 codes
  (wzdrugs.barcode + Barcode1..5).
- **Unit conversions:** `unit_conversions(drug_id, from_unit, to_unit, factor)` ←
  wzdrugs.units/Unitsmall; `invoice_lines.unit` names the conversion key.
- **Parties:** `parties(branch_id, kind[customer|supplier|both], typee, credit_limit, ...)`
  merges the dual identity explicitly (wzcustomers.randomid vs companies.mobile); a company
  that is both customer and supplier gets `kind='both'` with one `receivable_account_id`
  and one `payable_account_id`.
- **Region:** `governorate` (Mohafaza) + `district` (Markaz) on `branches`, `parties`,
  `chain_buy_orders`, `dead_stock_exchange` (ChainBuyUsers 12-col, schema_complete.sql:338-353).
- **VAT/currency country config:** `app_config` rows (`country`, `currency`,
  `vat_default_rate`) defaulting 15% (Gulf) vs 14% (Egypt); `branches.vat_default` overrides
  per branch (storediscount.country).
- **Invoice statuses:** enum `invoice_status` includes the legacy
  Saved / Unsaved / **Un save** / Copy / transfer-to-sales-return / transfer-to-purchases /
  closed / archived / void states (feature_sales_invoices.md:3).
- **Payment methods:** `payment_splits.method[cash|card|credit|manual_cash|manual_card]`,
  preserving the legacy split identity `totalvalue = payed + agel` via a CHECK on `invoices`
  (connections_overview.html:418).
- **Trial-balance invariant:** `journals.description` is `NOT NULL` (feature_balances.md:301),
  entry sequence unique per `(branch_id, date, entry_no)`, and the per-journal
  `SUM(debit) = SUM(credit)` invariant is enforced in the API transaction (see §5 note on
  why it is not a table CHECK) plus a single-side CHECK on `journal_lines`.

### 1.8 Approvals + shortages (SCHEMA_EVALUATION §1.7, §1.8)
- `stock_correction_requests(id, branch_id, drug_id, batch_id, delta, reason, requested_by,
  status[pending|approved|rejected], approved_by, decided_at)` — the actual
  stock_batches/branch_stock change is applied only on approval (تصحيح الارصدة
  بالزيادة/بالعجز).
- `shortage_flags`, `needs` (← titanneed), `purchase_orders` (← orders, NULL→'pending')
  reproduce the three shortage sub-systems and reorder automation.

---

## 2. Table-by-table rationale

Grouped by domain; each entry cites the legacy source and the SCHEMA_EVALUATION § that
mandates it. Column-level mapping is in §3.

### A. Core hubs (SCHEMA_EVALUATION §1.12)
| Table | Source | Rationale |
|---|---|---|
| `branches` | wzphar (§2.1, §1.12) | The branch hub. Keeps legacy natural keys `pharmacyid` (unique), `phar`, `mobile` (unique). Adds region, `country`, `currency`, `vat_default`, `is_main_device` (ismaster.txt). |
| `users` | FormUsers/FFFUserEdit + ShogUser.phy (§1.12) | Users gate every feature (الصلاحية 1-9). `mobile` kept for usersmony legacy linkage. |
| `roles` / `permissions` / `role_permissions` / `user_roles` | FormUsers/FFFUserEdit (§1.12) | RBAC. `permissions.code` mirrors legacy permission ids; seed rows documented in §2. |
| `drugs` | wzdrugs (§1.12, §2.1) | Drug master. `drugname` unique (legacy PK + tar.phy EN name). Keeps vat%, units, Unitsmall, PriceNow, history, disco. |
| `drug_barcodes` | wzdrugs.barcode+Barcode1..5 (§1.11) | 6-barcode lookup; unique on barcode alone. |
| `unit_conversions` | wzdrugs.units/Unitsmall (§1.11) | pack↔small-unit conversions for purchases/sales/transfers. |
| `drug_costs` | wzdrugs2 (§2.1) | Per-branch unitcost/costvalue/expire extension. |
| `stock_batches` | wzgard (§1.2) | Batch/expiry inventory. Mirrors wzgard 15 cols; `typee` enum extends legacy sale/purchase/return/count with transfer_in/transfer_out/opening/correction. Unique `(branch_id, drug_id, randomid)`. FIFO/expiry index for sale selection, COGS (costvalue), ربح اليوم, and مخزون منتهي. |

### B. Parties (SCHEMA_EVALUATION §1.11, §2.1)
| Table | Source | Rationale |
|---|---|---|
| `parties` | wzcustomers + companies + wzsuppliers (§2.1) | Single party table, `kind[customer|supplier|both]`, `typee` discriminator, `credit_limit`, branch-scoped, with AR/AP account FKs and region. companies.mobile (supplier phone) merges here as `mobile`; `wzsuppliers` is just `kind='supplier'`. |

### C. Accounting (SCHEMA_EVALUATION §1.4, §2.1)
| Table | Source | Rationale |
|---|---|---|
| `accounts` | wzaccfreetree + acctree.phy (§1.4, §2.1) | Per-branch chart of accounts (master/fary parent-child); unique `(branch_id, code)`. |
| `journals` | feature_balances.md / farysales (§1.4, §1.11) | `description NOT NULL`; unique entry per `(branch_id, date, entry_no)`; balanced-journal invariant enforced at API layer. |
| `journal_lines` | farysales 17-col LIVE ledger + Accounting\moves (§1.1, §1.4, SCHEMA_RESOLVED §9) | Carries `branch_id`, denormalized `(month, year)`, single-side CHECK, legacy `creditdebit/randomid/writer/tips/classy`. |
| `balances` | farysales monthe/yearo (§1.1, §1.4) | PK `(branch_id, account_id, month, year)`; `balance = debit − credit` CHECK. |
| `monthly_close` | monthy\moves (§1.1, §1.4) | PK `(branch_id, year, month)`, status open/closed/reopened. |
| `month_open_balances` | monthy\start-data (§1.11, §3.10) | Per-account opening debit/credit per branch-month; replaces start_balances_json; seeded from opening stock/receivables/payables/drawer. |

### D. Sales/purchase core (SCHEMA_EVALUATION §1.1, §1.11)
| Table | Source | Rationale |
|---|---|---|
| `invoices` | invoicedata 17-col hybrid + titanksasales (§2.1, SCHEMA_RESOLVED §1, §7) | Normalized header from the hybrid. `kind[sale|purchase|sale_return|purchase_return|transfer]`, full `invoice_status` enum, `payed+agel=totalvalue` CHECK, `silsilaid`, `last_edited_at` (LastEdited.phy). |
| `invoice_lines` | invoicedata line-items (§1.1, §1.11) | `branch_id NOT NULL`, `drug_id`, `batch_id` FK, `unit`, 4-dp unit_price/cost, expiry, minimum. |
| `invoice_versions` | feature_invoice_editing (§1.6) | Full snapshot per edit for reversal + re-apply. |
| `payment_splits` | payed/agel split (§1.1, §1.11) | `method[cash|card|credit|manual_cash|manual_card]`. |
| `drawer_movements` | Daily.phy (§1.1, §1.5) | Per-branch drawer in/out; `shift_id` FK now resolves (shifts exists). |
| `daily_close` | MonyInfo.phy + Daily.phy + idx 9883 totals (§1.11) | COMPLETE close: manual_cash, manual_card, cost_of_sales, net_profit (ربح اليوم), discounts, drawer_start, shift_id, work_period_id; UNIQUE `(branch_id, date)` — locks a date per branch. |

### E. Stock / transfer / shortage (SCHEMA_EVALUATION §1.2, §1.7, §1.8, §2.1)
| Table | Source | Rationale |
|---|---|---|
| `branch_stock` | titanstock + titanksastock (§2.1) | Per-branch drug levels + `minimum` + `silsilaid`; PK `(branch_id, drug_id)`. |
| `transfers` / `transfer_lines` | titaninn (§2.1, §1.9) | `source_branch_id`/`target_branch_id` FKs + legacy free-text retained; `itemsasstring` kept; `status` ← delivery.phy. |
| `shortage_flags` | §1.8 | Manual / half-auto / sales-rate flagging. |
| `needs` | titanneed (§1.8) | Inter-pharmacy request; sender/target as branch FKs + legacy text. |
| `purchase_orders` | orders (§1.8) | legacy NULL=pending → 'pending'. |
| `stock_correction_requests` | §1.7 + RasidCorrect.phy | Approval workflow. |
| `dead_stock_exchange` | RawakidTablew (§2.1) | رواكد exchange offers with region + seller/requester tel. |
| `chain_buy_orders` | ChainBuyStore + ChainBuyUsers (§2.1) | Store-level and user-level chain buy orders (Mohafaza/Markaz). |

### F. E-invoice (SCHEMA_EVALUATION §1.10, §1.9)
| Table | Source | Rationale |
|---|---|---|
| `einvoice_log` | ZATCA (§1.10) | Per-invoice e-invoice record with uuid/hash/xml/json/response + QR columns; resubmission workflow. |
| `einvoice_counters` | oot3/netcounter/counter.txt+hash.txt (§1.9, §3.5) | DB-resident ZATCA/ETA counter+hash chain. |

### G. Audit & sync (SCHEMA_EVALUATION §1.6, §1.3)
| Table | Source | Rationale |
|---|---|---|
| `audit_log` | TitanUserAction 11-col (§1.6, SCHEMA_RESOLVED §4) | who/what/when/old→new per entity + drug/barcode; written atomically. |
| `invoice_versions` | §1.6 | edit reversal snapshots. |
| `sync_log` | usersourceupdate 6-col + outbox (§1.3, §2.1) | last-write-wins outbox; `status[pending|applied|failed|skipped]`. |
| `branch_identities` | §1.3 | legacy alias→branch map for migration. |
| `drug_sync_outbox` | drgserver (§2.1) | chain drug-server list channel. |

### H. Operational / state files → SQL (SCHEMA_EVALUATION §1.9, §2.2)
| Table | Source | Rationale |
|---|---|---|
| `work_periods` / `shifts` | workperiod.phy (§1.9) | Work periods + shift handover (تسليم الدرج RPT-A04); `cash_start` = drawer@start. |
| `user_drawer_money` | usersmony.phy 318-B (§1.9, PHY_MIGRATION §1b) | Per-user/per-shift drawer money; `record_no` + `source_file`. |
| `drug_interactions` | DDI.Phy (§1.9) | drug_a/drug_b/severity/note, ordered CHECK. |
| `integration_config` | myftp.phy (§1.9) | FTP/API config key/value + JSON. |
| `archive_imports` / `archive_exports` | Archive\Input + Output, Titan3-Backup (§2.2) | import/export runs; also the ETL runbook log (graceful degradation, §5). |
| `external_drug_catalog` | taronlineeg 7-col (§2.1, SCHEMA_RESOLVED §9) | online EG catalog (CreateDate/mobile/NameEnglish/NameArabic/drugname/price/barcode). |
| `price_change_log` | storediscount 16-col (§2.1, SCHEMA_RESOLVED §8) | price/discount change log w/ country + pharmacyname. |
| `manual_journal_entries` | daily-manual.phy/-2 (52/56 B) (§2.2) | manual journal money rows (القيود اليدوية); `journal_id` link. |
| `branch_registry` | titanpharmalist (§2.1) | registered-pharmacy registry, PK mobile. |
| `app_config` | storediscount.country / §1.11 | country/currency/VAT config rows. |

### I. Deliberately SKIPPED (see §4)
`remotecontrol`, `nilsen2`, `drugeyedash2`, `drugeye-for-titan.phy` feed.

---

## 3. Legacy → new entity mapping

### 3.1 Legacy SQL tables (28 from `schema_complete.sql` + docs alias `wzsuppliers`)

| Legacy table (§ in schema_complete.sql) | Replacement entity | Notes / decision (SCHEMA_EVALUATION §) |
|---|---|---|
| `wzdrugs` (§1) | `drugs` + `drug_barcodes` + `unit_conversions` | §2.1. drugname unique; 6 barcodes → child; units/Unitsmall → conversions; vat%, PriceNow, history kept. |
| `wzdrugs2` (§2) | `drug_costs(branch_id, drug_id, unitcost, costvalue, expire)` | §2.1. Per-branch extension; expire converted from VB6 serial. |
| `wzgard` (§3) | `stock_batches` | §1.2/§2.1. phar→branch_id, randomid, quant→qty(4dp), expire, costvalue→cost, vatvalue, totalwithvat, oldstock, typee enum. |
| `wzcustomers` (§4) | `parties` | §2.1. typee discriminator, phar branch scoping, creditlimit, randomid natural key. |
| `companies` (§5) | `parties(kind='supplier'/'both')` | §2.1/§1.3. PK mobile (supplier phone) merges as parties.mobile; dual identity resolved via branch_identities + kind. |
| `titaninn` (§6) | `transfers` + `transfer_lines` | §2.1/§1.9 (SCHEMA_RESOLVED §10: transfer, not purchases). itemsasstring→lines; source/target become FKs with legacy text kept; status ← delivery.phy. |
| `titanksasales` (§7) | `invoices` (chain-originated) + `sync_log` outbox | §2.1 (SCHEMA_RESOLVED §1: 9-col summary). silsilaid kept; replicated via outbox GUID loop. |
| `titanksastock` (§8) | `branch_stock` | §2.1 (SCHEMA_RESOLVED §2: 8-col). minimum, silsilaid, pharmacyid→branch_id, classy. |
| `titanstock` (§9) | `branch_stock` | §2.1. price, barcode, lastedit merged into branch_stock. |
| `titanneed` (§10) | `needs` | §2.1/§1.8 (SCHEMA_RESOLVED §3: 6-col). sender/target → branch FKs + legacy text; quant→qty. |
| `invoicedata` (§11) | `invoices` + `invoice_lines` | §2.1/§1.11 (SCHEMA_RESOLVED §7: 17-col hybrid split correctly: header cols → invoices, line cols → invoice_lines). |
| `orders` (§12) | `purchase_orders` | §2.1/§1.8. legacy status NULL=pending → 'pending'. |
| `wzphar` (§13) | `branches` | §2.1/§1.12. pharname/adress/pharmacyid/mobile natural keys; is_main_device added. |
| `storediscount` (§14) | `price_change_log` | §2.1 (SCHEMA_RESOLVED §8: pharmacyname belongs here). country, disco, pricechanged kept. |
| `drgserver` (§15) | `drug_sync_outbox` | §2.1. server drug list / chain drug sync. |
| `remotecontrol` (§16) | — **SKIP** | §2.1. Vendor RCE channel; see §4. |
| `TitanUserAction` (§17) | `audit_log` | §1.6/§2.1 (SCHEMA_RESOLVED §4: 11-col). oldvalue/newvalue/curprice/units → old_value/new_value + typevalue/namee retained. |
| `usersourceupdate` (§18) | `sync_log` | §1.3/§2.1 (SCHEMA_RESOLVED §5: 6-col). 3000-row pull + delete-on-apply → outbox with status. |
| `nilsen2` (§19) | — **SKIP** | §2.1. Data-selling; see §4. |
| `taronlineeg` (§20) | `external_drug_catalog` | §2.1 (SCHEMA_RESOLVED §9: 7-col CreateDate/mobile/Name/…). |
| `ChainBuyStore` (§21) | `chain_buy_orders` | §2.1. Store-level chain buy + Mohafaza/Markaz. |
| `ChainBuyUsers` (§22) | `chain_buy_orders` | §2.1/§1.11 (SCHEMA_RESOLVED §6: 12-col). PharmacistTel/RequisterTel/country region. |
| `RawakidTablew` (§23) | `dead_stock_exchange` | §2.1/§1.9. رواكد exchange; SourceIdDateTime→source_iddatetime. |
| `drugeyedash2` (§24) | — **SKIP/optional cache** | §2.1. External MySQL mirror; see §4. |
| `wzaccfreetree` (§25) | `accounts` | §1.4/§2.1. mobile→branch_id, master/fary → parent/child tree. |
| `titanpharmalist` (§26) | `branch_registry` | §2.1. PK mobile, pharmacyname, barcode, apptype. |
| `farysales` (§27) | `journal_lines` + `balances` | §1.1/§1.4/§2.1 (SCHEMA_RESOLVED §9, §11: 17-col LIVE ledger incl. creditdebit). monthe/yearo→(month,year) denormalized. |
| `ZATCA` (§28) | `einvoice_log` + `einvoice_counters` | §1.10/§2.1. invoiceid/uuid/datee/pharmacyid/status/hash/xml/response + QR columns + counters in-DB. |
| `wzsuppliers` (docs-only, feature_reports_analytics.md:327) | `parties(kind='supplier')` | §2.1. Supplier alias of the party master. |

### 3.2 `.phy` / file-backed state (money + non-money)

| File (record length) | Replacement entity | Status (SCHEMA_EVALUATION §2.2 / PHY_MIGRATION) |
|---|---|---|
| `Daily.phy` (614 B) | `drawer_movements` + `daily_close` | Layout partial (0x00..0x3c known, 0x3c..614 opaque); import known fields, tail preserved raw. |
| `Dailyline.phy` / `Dailymax.phy` | `drawer_movements` | Successors of Daily; **Dailymax reclen UNRESOLVED** → degrade (§5). |
| `MonyInfo.phy` | `daily_close` | **BLOCKED** (runtime-built filename, 0 refs, no layout/sample) → degrade (§5). |
| `daily-manual.phy` (52 B) / `daily-manual-2.phy` (56 B) | `manual_journal_entries` | Known money@0x00; tail opaque. |
| `fary.date.phy` | `daily_close.status` | 0-ref, runtime-built → degrade (§5). |
| `closefary.phy` | `daily_close.status` | Same → degrade (§5). |
| `acctree.phy` / `acctree2.phy` | `accounts` (migration source) | Chart mirror; derived from accounts post-import. |
| `RasidCorrect.phy` | `stock_correction_requests` | 0-ref → degrade; corrections also land in audit_log. |
| `usersmony.phy` (318 B) | `user_drawer_money` | §1b DONE: idx@0x00 I2, money@0x04 R4, name@0x08, variants 0x0c/0x38, flag@0x268. |
| `workperiod.phy` | `work_periods` + `shifts` | 0-ref → degrade; schema ready. |
| `delivery.phy` (55 B) | `transfers.status` | Rec len NEW (Moddelivery); fields TODO → import status only. |
| `oot3.phy` / `netcounter.phy` | `einvoice_counters` | Move counter/hash in-DB; import as last-known values. |
| `myftp.phy` | `integration_config` | FTP config. |
| `DDI.Phy` (1300 B record) | `drug_interactions` | ModDDI role; field layout follow-up. |
| `Accounting\moves\` | `journal_lines` (source) | Journal file store. |
| `monthy\moves` + `monthy\start-data` | `monthly_close` + `month_open_balances` | start-data → per-account opening debit/credit. |
| `Archive\Input` + `Archive\Output` | `archive_imports` / `archive_exports` | Import/export runs (also ETL runbook log). |
| `Titan3-Backup\{Daily,Monthly,Export,xj}` | `archive_exports` + backup log | `.rur`/`.zip` formats undocumented → store as blob/exports. |
| `Phye.safer` | archive/backup store | Format UNKNOWN → degrade (§5). |
| `counter.txt` + `hash.txt` (C:\saturn) | `einvoice_counters` | Chain values; rollover spec missing → store raw last values. |
| `ismaster.txt` | `branches.is_main_device` | Main-device flag. |
| `LastEdited.phy` | `invoices.last_edited_at` + index | Last-edited invoice list. |
| `tar.phy` (856 B × 32000, **VERIFIED** EN@0x00 + AR@0x34 cp1256) | `drugs` (drug master import) | PHY_MIGRATION §0b; cp1256 decode; tail opaque. |
| `salesfull.phy` (997 B × 50000) | `invoices` (historical) / `archive_exports` | Size-derived reclen verified; fields need populated sample → degrade. |
| `customers.w.phy` (157 B × 30000) | `parties` | Size-derived reclen verified; names corrupt ('?') in this install; fields need sample → degrade. |
| `ShogUser.phy` (1114 B × 49) | `users` / `shifts` | Record 1 placeholder only; fields beyond name opaque → degrade. |
| `drugeye-for-titan.phy` / `fromdrugeye.phy` / `DRUGS.PHY` | — **SKIP/optional** external catalog import | ROT-4 text feed, legal caveat (drug_database_legal.md) → see §4. |

---

## 4. Deliberately skipped entities

| Legacy artifact | Why skipped |
|---|---|
| `remotecontrol` (SCHEMA_EVALUATION §2.1, §16) | Vendor remote-code-execution channel (connections_overview.html:687). Security hazard; must NOT be replicated. Any legitimate remote admin goes through the new app's own audited admin API. |
| `nilsen2` (SCHEMA_EVALUATION §2.1, §19) | Data-selling aggregation feed for Nielsen (connections_overview.html:679). Not a pharmacy function; ingestion path was undocumented (GAPS §3.1). Skip. |
| `drugeyedash2` (SCHEMA_EVALUATION §2.1, §24) | Dashboard mirror of an external MySQL DB (`db_9ffe55_apifordrugeye`, GAPS_REPORT.md:91). Read-only external dependency; an optional cache view if ever needed, not a schema table. |
| `drugeye-for-titan.phy` / `fromdrugeye.phy` / `DRUGS.PHY` (§2.2) | Proprietary DrugEye feed is ROT-4 text with a legal caveat (drug_database_legal.md; connections_overview.html:677). Do not ship DrugEye data — use CC0/SFDA open catalogs via `external_drug_catalog` instead. |
| `ModOOTTrans`, empty stub modules (`Modhelp`, `ModCompany`, `Types`, `ModChanges`, `ZzBookMark`) | Dead placeholders (GAPS §4.2-4.3); treated as dead, no schema needed. |

---

## 5. Still-blocked entities + graceful degradation (ETL)

### Blocked by missing .phy layouts
| Entity | Blocker | Resolution path |
|---|---|---|
| `Dailymax.phy` | reclen UNRESOLVED — 1,099,648 B is not a clean multiple of 614/856 (PHY_MIGRATION §1c) | Factor a populated production copy (`reclen × nrecs = filesize`), or find the OpenFile+`LitI2` pair in ModDailyQuiod-family procs. Until then import as `drawer_movements` best-effort. |
| `MonyInfo.phy` | runtime-built filename, 0 static refs, no layout; not present on Wine install (PHY_MIGRATION §1) | Needs a live sample from production `Files\DBI`; infer layout from 318-B usersmony pattern + day-close fields. Target `daily_close`. |
| `fary.date.phy` / `closefary.phy` | 0-ref runtime-built close-flag files | Map to `daily_close.status`; close flags come from the app's own close workflow in the new system. |
| `RasidCorrect.phy`, `workperiod.phy`, `oot3.phy`, `netcounter.phy`, `acctree.phy`, `PIFary.phy` | 0-ref runtime-built; record length from §0 catalogue but fields unmapped | Pair module role + record length; layouts finalized from a production copy. Schema targets exist (`stock_correction_requests`, `shifts/work_periods`, `einvoice_counters`, `accounts`). |
| `Phye.safer` | encrypted safety backup, format UNKNOWN | Store as opaque archive blob in `archive_exports`; no field-level import. |
| `salesfull.phy` (997), `customers.w.phy` (157) | fields need a populated production copy (fresh install is ~all zeros) | Import record counts + raw bytes; split header/line fields once a real sample exists. |
| `delivery.phy` (55) | rec len NEW; fields beyond 0x00 TODO | Import as `transfers.status` (records → status transitions); full fields follow-up. |

### Graceful-degradation story (driven by `legacy_import/`)
The ETL pipeline in `legacy_import/` (README runbook) already implements the degradation
contract, and the schema supports it:
1. **Scan phase** — every `.phy` in `Files\DBI` is opened; a layout is matched from
   `layouts.py` by **record length + module role** (the filename string-index method is
   unreliable per PHY_MIGRATION §1). Known layout → decode to JSONL; unknown layout →
   write a hex dump of the first 6 records and mark `UNKNOWN_LAYOUT`.
2. **Record-length factorisation** — when a layout is unknown, `reclen × nrecs = filesize`
   (verified for tar 856×32000, salesfull 997×50000, customers.w 157×30000, ShogUser
   1114×49) resolves the length without disassembly; sparse files still reveal `reclen`.
3. **Load phase** — each decoded JSONL maps to its target table per §3.2; every import run
   writes a row into `archive_imports` with `status` (pending/running/done/failed) and a
   `note`, so a partially-mapped file set is visible and re-runnable.
4. **Per-file degradation** — files with a known prefix (e.g. Daily.phy 0x00..0x3c) load
   only the mapped fields and preserve the rest as a `tail_raw` blob; files with no layout
   at all are recorded but skipped (`UNKNOWN_LAYOUT`), never blocking the rest of the batch.
5. **Money conversion rule** — every R4/R8 money field is rounded once to 4 dp → NUMERIC;
   totals are never re-summed from floats (SCHEMA_EVALUATION §3.3). The `migration_report.json`
   records row counts + `NO_MAPPING`/`OK`/`UNKNOWN_LAYOUT` per file for reconciliation.
6. **Reconciliation** — per-day totals are checked against `daily_close`-style figures before
   cutover (README §4). The two remaining hard blockers (Dailymax reclen, MonyInfo layout)
   are marked release-blocking in PHY_MIGRATION §3 and degrade to best-effort import until a
   production `Files\DBI` sample exists.

### Note on the balanced-journal CHECK
A cross-table `CHECK (SUM(debit)=SUM(credit))` is not expressible in plain DDL (Postgres
CHECKs cannot reference other tables without a trigger). It is therefore enforced in the
FastAPI transaction that inserts `journals`+`journal_lines` atomically (and in the Tauri
SQLite write path), and flagged with a comment in both DDL files. The single-side CHECK on
`journal_lines` (`debit=0 OR credit=0`) IS a table constraint.

---

## 6. SQLite dialect notes (Tauri offline-first twin)

The SQLite file (`schema_sqlite.sql`) is the same design, loadable by `sqlite3`, with
these dialect mappings (each stated in the file header and applied consistently):

| PostgreSQL | SQLite |
|---|---|
| `BIGINT GENERATED ALWAYS AS IDENTITY` | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| `NUMERIC(18,2)` (amounts/totals/balances) | `INTEGER` **minor units ×100** (halala/piastre — exact; a real value `123.45` is stored as `12345`) |
| `NUMERIC(18,4)` (unit prices/costs, qty) | `INTEGER` ×10000 |
| `NUMERIC(5,2)` (VAT/discount rates) | `INTEGER` ×100 |
| `NUMERIC(18,6)` (conversion factor) | `INTEGER` ×1000000 |
| `NUMERIC(18,x)` in general | `INTEGER` value ×10^x — **one uniform rule** |
| enums (`CREATE TYPE ...`) | `TEXT` + `CHECK (col IN (...))` |
| `TIMESTAMPTZ` / `DATE` | `TEXT` ISO-8601 (UTC `YYYY-MM-DD HH:MM:SS` / `YYYY-MM-DD`); lexicographic sort == chronological sort |
| `BOOLEAN` | `INTEGER` 0/1 |
| `JSONB` | `TEXT` (JSON document) |
| `CREATE SCHEMA` | none (single main schema) |
| `now()` default | `CURRENT_TIMESTAMP` |

**Money choice rationale:** SQLite's `NUMERIC` affinity stores fractional values as IEEE-754
double, which reintroduces the exact float hazard we are eliminating (§1.2). Storing **cents
(minor units) as INTEGER** makes money exactness a schema invariant — a double can never be
inserted — at the cost of a ×10^scale conversion at the application boundary, which the
shared money module already centralizes. The PG and SQLite schemas share column names, so
the app layer maps 1:1; only the scale conversion differs (server: implicit; desktop:
×10^scale in the money module).

`PRAGMA foreign_keys = ON` is set at the top of the SQLite script; all money/stock tables
carry the same audit-everything comment as PostgreSQL.