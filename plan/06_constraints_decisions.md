# TITAN.W1 Rebuild — CONSTRAINTS, NEEDS & DECISIONS (ground-truth plan)

**Role:** cross-cutting analyst — the "ground truth" doc every other plan (schema, migration, API,
UI, ETL) must respect.
**Product:** rebuild of TITAN.W1 (Phye.exe, VB6 Egyptian pharmacy ERP; 237 forms, 6,192 procs,
28 legacy SQL Server tables + a file-backed money ledger in `.phy`).
**Stack (fixed):** FastAPI + PostgreSQL (server) · Next.js (web) · Tauri + React + SQLite (desktop
POS, offline-first).
**Scope:** phased, core-first; legacy migration in scope.
**Date:** 2026-08-16. **Status:** planning/research — no code written.

---

## 0. Reading conventions

- **Citation caveat (GAPS_REPORT §1):** every `strings_*.txt:N` citation in the feature docs is off
  by **+3** (string index = 1-based line − 3). When a feature doc cites a line, read the real line
  at `N+3` (verified for 6 landmarks). Cross-file DDL citations are also sometimes wrong-file
  (e.g. feature_users_permissions_menus.md:236 cites `schema_complete.sql:245–256` for
  `TitanUserAction`; real DDL is at `:266–278`).
- **Authority order** (per schema_design.md): SCHEMA_EVALUATION.md → SCHEMA_RESOLVED.md →
  schema_complete.sql → PHY_MIGRATION.md → GAPS_REPORT.md.
- **The money truth is NOT in SQL.** There are no `wzmony`/`wzdaily`/`wzbank` tables — those names
  are shorthand. Real money lives in (a) the `farysales` SQL ledger and (b) serialized `.phy` daily
  files (`connections_overview.md:139`, `feature_sales_invoices.md:118`). Any plan that models only
  the SQL tables will lose the drawer/day-close history.
- **Schema contradictions are already adjudicated** in `SCHEMA_RESOLVED.md` (11 items, all resolved
  to the `schema_complete.sql` shapes). They are listed in §6 as *resolutions needing human
  confirmation*, not as new open decisions.

---

## 1. Hard constraints

Legend: **BLOCKER** = build cannot start/cut over without it. **REQUIRED** = must hold in the
delivered system. **RECOMMENDED** = strong preference, reversible with human sign-off.

### 1.1 Legal / regulatory

| # | Constraint | Grade | Source / rationale |
|---|---|---|---|
| C1 | **Do NOT ship DrugEye data.** DrugEye is proprietary freeware with no data-reuse license; scraping, `.phy` reuse, or API integration is legally risky. Use the CC0 `karem505/egyptian-drug-database` (25,070 meds, Ar/En, price, composition) + EDA/EDDB official registry + SFDA open data. | **BLOCKER** | drug_database_legal.md:5-7, :241-259. The legacy integration path is dead code anyway (the `.rar` is ROT-4 text, 0 p-code refs — connections_overview.md:369). |
| C2 | **E-invoicing is mandatory and per-country.** Saudi market → ZATCA e-invoicing (JSON + UUID + CSID signature + QR + invoice-hash chain + OAuth client_credentials) plus SFDA **DTTS** serialized-drug track & trace (SOAP: sale/cancel/dispatch/accept/return/transfer with GTIN/BN/SN/XD/GLN). Egypt → **ETA** e-invoice JSON (idx 228–267 fragments are LIVE; the submission URLs are DEAD 0-ref strings in this build). | **REQUIRED** | zatca_complete.md:17-45; api_integration.md:9-113, :186-233; EGYPT_ETA_DECOMPILED.md:5-16. Decision to keep JSON/QR generation but not build submission to dead Egypt URLs already made (schema_design §1.5). |
| C3 | **E-invoice state must be auditable and in-DB.** `einvoice_log` (← legacy `ZATCA`: invoiceid/uuid/status/hash/xml/response + `kind[zatca\|eta]` + QR cols) and DB-resident `einvoice_counters` (counter/hash chain moved off `counter.txt`/`hash.txt`/`oot3.phy`/`netcounter.phy` into the DB, updated atomically with each invoice). | **REQUIRED** | SCHEMA_EVALUATION §1.10; schema_design §1.5. |
| C4 | **VAT and currency are country-configurable.** Gulf default 15%, Egypt 14%; `app_config(country, currency, vat_default_rate)` + `branches.vat_default` override; the legacy has 15 currencies (EGP default, SAR…). | **REQUIRED** | SCHEMA_EVALUATION §1.11 (VAT 15 vs 14); business_logic_complete.md §27; `storediscount.country`. |
| C5 | **Drug pricing tiers must be preserved** (retail `price`, `PriceNow`, warehouse margin 1–6, public/جمهور price, Wasfaty price, temp price) and **abnormal-discount guards** (>25%…75% prompts) and **credit-sale/balance-edit permission gates** must be reproducible. | **REQUIRED** | business_logic_complete.md §18.5, §16.2; feature_users_permissions_menus.md:89,92 (صلاحية ≥7 for balance edits, credit-sale gate). |
| C6 | **Do NOT replicate the vendor-control / data-selling / backdoor channels:** `remotecontrol` (pushed `passedfunctions` = remote code execution), Nielsen data-selling feed (`nilsen2` + HTTP uploads), AnyDesk silent remote access, unsigned HTTP distribution of executables. | **REQUIRED** (a security constraint) | connections_overview.md:373, :377; SCHEMA_EVALUATION §2.1 (SKIP rows); schema_design §4. |
| C7 | **Egyptian drug registration data comes from EDA/EDDB** (official registry — names, reg#s, composition). Whether EDA data is truly public domain is **unconfirmed** (flagged; seek confirmation before commercial redistribution). | **REQUIRED** (with caveat) | drug_database_legal.md:163-169, :272-279. |

### 1.2 Architectural

| # | Constraint | Grade | Source / rationale |
|---|---|---|---|
| C8 | **Offline-first.** The desktop POS (Tauri + React + SQLite) must do a complete cash/stock/close day with zero connectivity; SQLite is the offline twin of the PostgreSQL schema (same column names; money as INTEGER minor units). Server sync is asynchronous. | **BLOCKER** | Task stack; schema_design §6. |
| C9 | **`branch_id NOT NULL` on every money/stock/ledger row** — `journal_lines`, `payment_splits`, `invoice_lines`, `balances`, `monthly_close`, `month_open_balances`, `stock_batches`, `branch_stock`, `transfers`, `needs`, `user_drawer_money`, `audit_log`, `sync_log`, `einvoice_log`, `price_change_log`. `balances` key `(branch_id, account_id, month, year)`; `monthly_close` key `(branch_id, year, month)`. This is what makes كشف حساب (customer ledger), per-branch ميزان (trial balance), and cross-branch consolidation reproducible from legacy `farysales.mobile/phar/monthe/yearo`. | **BLOCKER** | SCHEMA_EVALUATION §1.1, §1.4; schema_design §1.1. |
| C10 | **Exact-decimal money only. NEVER REAL/float for money.** PG `NUMERIC(18,2)` totals/balances, `NUMERIC(18,4)` unit price/cost/qty, `NUMERIC(5,2)` VAT/discount rates. SQLite stores integers in minor units (×100 / ×10000 / ×100 / ×10^scale — one uniform rule) so a double can never be inserted. | **BLOCKER** | SCHEMA_EVALUATION §1.11, §3.3; schema_design §1.2, §6. |
| C11 | **Single rounding rule: round-half-up to 2 dp at every line-total and every payment boundary** (`line_total = round(unit_price × qty × (1−disc) × (1+vat), 2)`). Unit prices/costs keep 4 dp internally, rounded only when multiplied into a total. One shared money module owns rounding (FastAPI server + Tauri). | **BLOCKER** | schema_design §1.2. |
| C12 | **Legacy float import rule: convert once, never re-sum.** Every VB6 Single/Double money field is rounded once to 4 dp at import and stored as NUMERIC; historical totals are NEVER recomputed from floats (legacy precision loss is baked into history). | **BLOCKER** | SCHEMA_EVALUATION §3.3; schema_design §1.2. |
| C13 | **Sync is last-write-wins, no merge** (legacy chain replication via the `titanksasales` GUID-loop and `usersourceupdate` 3000-row pull / delete-on-apply). Reproduce with a durable outbox: `sync_log` (+ `drug_sync_outbox` for `drgserver`) + `branch_identities` alias map (`phar`/`pharmacyid`/`mobile` → branch) for migration. | **REQUIRED** | connections_overview.md:383; SCHEMA_EVALUATION §1.3; schema_design §1.4. |
| C14 | **Audit-everything.** `audit_log` (← `TitanUserAction` 11-col) written in the SAME transaction as every money/stock/balance mutation; `invoice_versions` snapshots for invoice-edit reversal (تعديل فواتير reverses and re-applies money/.phy). | **REQUIRED** | SCHEMA_EVALUATION §1.6; schema_design §1.3. |
| C15 | **Day close is an immutable snapshot that locks a date per branch** (`daily_close UNIQUE (branch_id, date)`); the system date advances only via close; close ≥ 1 PM; idempotent. | **REQUIRED** | connections_overview.md:207; feature_account_closing.md:75,308. |
| C16 | **Balanced-journal invariant:** `SUM(debit)=SUM(credit)` per journal (enforced in the API transaction — not expressible as a table CHECK), `journals.description NOT NULL`, unique entry per `(branch_id, date, entry_no)`, single-side CHECK on `journal_lines`. | **REQUIRED** | feature_balances.md:328; SCHEMA_EVALUATION §1.11; schema_design §1.7. |
| C17 | **Invoice status enum must include the legacy states** Saved / Unsaved / **Un save** / Copy / transfer-to-sales-return / transfer-to-purchases / closed / archived / void; payment methods `cash|card|credit|manual_cash|manual_card` preserving `totalvalue = payed + agel`. | **REQUIRED** | SCHEMA_EVALUATION §1.11; schema_design §1.7. |
| C18 | **The branch-identity unification**: single `branch_id` surrogate; legacy `pharmacyid`/`phar`/`mobile` kept as unique indexed natural keys so ETL upserts idempotently. `companies.mobile` (a supplier phone) merges into `parties.mobile` — the dual customer/supplier identity is merged explicitly, not silently. | **REQUIRED** | schema_design §1.6, §3.1. |
| C19 | **Approval workflow for stock corrections** (staff request → manager accept/reject) via `stock_correction_requests`; the actual stock change applies only on approval. | **REQUIRED** | SCHEMA_EVALUATION §1.7; schema_design §1.8. |
| C20 | **Missing-layout `.phy` files degrade, never block**: unknown layouts are hex-dumped + recorded as `UNKNOWN_LAYOUT` in `archive_imports`; known-prefix files load mapped fields and keep `tail_raw`. Two hard blockers (Dailymax reclen, MonyInfo layout) require a production `Files\DBI` sample. | **REQUIRED** | schema_design §5; PHY_MIGRATION §1c, §1. |
| C21 | **Dead legacy modules are treated as dead:** `ModOOTTrans`, `Modhelp`, `ModCompany`, `Types`, `ModChanges`, `ZzBookMark` (empty stubs); no schema. | **RECOMMENDED** | GAPS_REPORT §4.2-4.3. |
| C22 | **Arabic-first UI/domain**: Arabic terms are the domain lingua franca (درج drawer, أجل credit, شبكة card, تقفيل day-close, ميزان trial balance, نواقص shortages, رواكد dead stock); drug Arabic names decode cp1256 (legacy); bilingual display where the domain requires. | **REQUIRED** | connections_overview.md:8; PHY_MIGRATION §0b (cp1256). |

---

## 2. Needs

### 2.1 Functional (must-run business flows)

Priority-ordered, core-first. "Core" = anything touching cash/stock/invoice/close; everything else
is phase-2.

1. **POS sale** (cash/شبكة/أجل split; qty/expiry selection; barcode (6-code) or name lookup; stock check "Not Enouph Stock"; expiry block; discount + abnormal-discount guard; credit-limit check; permission gates; drawer open; print-on-save).
2. **Purchase** (supplier, batch/expiry/unit-cost entry, buy discount, VAT, batch to `stock_batches`, farysales credit posting to موردين, opening stock via special purchase).
3. **Sales return / purchase return** (reverse batches, reverse chain rows, refund to/from drawer, tax return variant, معدوم/expiry-return flows).
4. **Invoice editing** (reverse-then-reapply with `invoice_versions` snapshot + audit; ETA/ZATCA re-submit on money-affecting edits).
5. **Day close / تقفيل** (drawer count, expected = opening + sales − outflows, عجز/زيادة, aggregates كاش/كاش يدوي/شبكة/شبكة يدوي/محسوب المبيعات/تكلفة مبيعات اليوم/ربح اليوم/خصومات اليوم/ضريبة اليوم/حركة مالية, shift close, archive, backup, advance date).
6. **Stock counting + corrections** (بالزيادة/بالعجز, manager approval, negative-balance repair between expiry batches).
7. **Shortages / needs / orders** (3 sub-systems: manual, half-auto minimum, sales-rate; `needs` ← titanneed; `purchase_orders` ← orders; inter-branch transfer `transfers` ← titaninn).
8. **Customers & suppliers** (single party master, credit limit, AR/AP, سند قبض/سند صرف settlements, كشف حساب).
9. **Accounting** (per-branch chart of accounts `accounts` ← wzaccfreetree; journal entries; manual entries (القيود اليدوية); trial balance ميزان; balance sheet; month close with `month_open_balances`).
10. **E-invoice** (ZATCA + ETA JSON/QR generation; UUID; signing; submission where live; `einvoice_log` + `einvoice_counters`; VAT reports quarterly/monthly/annual).
11. **Reports** (RPT-* families S/P/C/SUP/H/ST/D/A/F/DEL/CH/EXP/EI/OP/SP incl. RPT-A04 drawer handover, RPT-D01 expired, shortage reports).
12. **Users / permissions / menus** (user types + numeric صلاحية 1–9 gates, menu visibility, audit).
13. **Drug master & pricing** (6-barcode child table, unit conversions, price tiers, price-change log `price_change_log` ← storediscount, drug-sync outbox).
14. **Doctors & prescriptions** (DDI checks `drug_interactions` ← DDI.Phy, prescription → invoice lines).
15. **Backup / archive / import** (daily/monthly archives, `.phy` import ETL, restore, archive log).
16. **Shifts / user drawer money** (`shifts`/`work_periods` ← workperiod.phy; `user_drawer_money` ← usersmony.phy).
17. **Chain sync** (last-write-wins outbox for sales/stock/needs/transfers/orders; main-device gate `branches.is_main_device` ← ismaster.txt). *Scope decision open — see D14.*

Out of scope / skipped by decision: `remotecontrol`, Nielsen, DrugEye feed, drugeyedash2 mirror
(§1.1 C6, schema_design §4).

### 2.2 Non-functional

| Need | Detail |
|---|---|
| **Offline resilience** | Full sales/stock/close day on SQLite with zero connectivity; conflict-free because sync is LWW no-merge; outbox survives restarts; idempotent replay. |
| **Multi-branch** | Every money/stock/ledger row branch-scoped (C9); per-branch close/lock; cross-branch consolidation; per-branch accounts and account trees. |
| **Auditability** | Every money/stock mutation writes `audit_log` atomically; invoice edits versioned; e-invoice counter/hash chain tamper-evident; answer "who changed this balance and when". |
| **Performance** | Legacy batch-load caps (500-drug reloads, 3000-row pulls, day caps 40000/16000/44000) imply pagination + indexed lookups; barcode lookup by ANY of 6 codes must be an indexed unique lookup. |
| **Data fidelity** | Never re-sum legacy floats (C12); cp1256 Arabic decode; unknown-layout degrade not silent corruption. |
| **Arabic-first** | RTL UI, Arabic labels/shortcuts preserved, bilingual reports where legacy prints both. |
| **Security** | No vendor RCE/backdoor channels; secrets (ZATCA/ETA keys, FTP) in secured config, never in logs/repo. |
| **Maintainability** | Shared money module; SQLite/PG schema keep identical column names; single rounding rule (C11). |

---

## 3. Decision log

### 3.1 Decisions MADE (locked, must not be silently reversed)

| # | Decision | Status | Source |
|---|---|---|---|
| D01 | Stack: FastAPI + PostgreSQL, Next.js web, Tauri + React + SQLite offline desktop | MADE | Task brief |
| D02 | `branch_id NOT NULL` on every money/stock/ledger row; balances/monthly_close keyed by (branch, month, year) | MADE | schema_design §1.1 (SCHEMA_EVALUATION §1.1, §1.4) |
| D03 | Money typing: NUMERIC(18,2/18,4/5,2); SQLite INTEGER minor units; never REAL/float | MADE | schema_design §1.2, §6 |
| D04 | Rounding: round-half-up 2 dp at line/payment boundaries; 4 dp internal unit price/cost; one shared money module | MADE | schema_design §1.2 |
| D05 | Legacy floats rounded once to 4 dp at import; never re-summed | MADE | schema_design §1.2, §5 |
| D06 | Audit-everything: `audit_log` in same transaction; `invoice_versions` for edits | MADE | schema_design §1.3 |
| D07 | Sync: LWW no-merge outbox (`sync_log`, `drug_sync_outbox`), `branch_identities` alias map, `branches.is_main_device` | MADE | schema_design §1.4 |
| D08 | E-invoice state in-DB: `einvoice_log` + `einvoice_counters`; keep JSON/QR generation; do NOT build submission to the dead Egypt ETA URLs | MADE | schema_design §1.5; EGYPT_ETA_DECOMPILED.md |
| D09 | Surrogate ids everywhere; legacy natural keys kept unique & indexed for idempotent ETL | MADE | schema_design §1.6 |
| D10 | 11 schema contradictions adjudicated → adopt `schema_complete.sql` shapes (titanksasales 9-col; titanksastock 8-col; titanneed 6-col; TitanUserAction 11-col; usersourceupdate 6-col; ChainBuyUsers 12+id; invoicedata 17-col merged→split; wzphar.pharname; taronlineeg 7-col vs farysales 17-col; titaninn 7-col transfer; creditdebit→farysales) | ADJUDICATED (needs human confirm — §6) | SCHEMA_RESOLVED.md |
| D11 | Skip `remotecontrol`, `nilsen2`, `drugeyedash2`, DrugEye feed; do not ship DrugEye data | MADE | schema_design §4; drug_database_legal.md |
| D12 | `.phy` ETL degradation contract (scan→layout match by reclen+role→load→per-file degrade; `archive_imports` runbook log; reconciliation) | MADE | schema_design §5; legacy_import/README.md |
| D13 | Balanced-journal invariant enforced at API layer (not DDL CHECK); single-side line CHECK | MADE | schema_design §1.7, §5 note |

### 3.2 Decisions OPEN (need human confirmation before/at start of coding) — see §5

| # | Decision | Recommended option | Rationale |
|---|---|---|---|
| D14 | **Target market(s): Saudi, Egypt, or both?** | Egypt-first (product origin), but schema must be country-agnostic | Sets VAT default (14 vs 15), e-invoice regime (ETA vs ZATCA), DTTS in-scope, currency, pricing model. The schema already supports both (app_config). |
| D15 | **Legacy migration scope: full-history vs cutover-from-date?** | Cutover from a chosen date; import `tar.phy` drug master fully; import `.phy` money history best-effort with degradation | Full `.phy` history is blocked on undocumented layouts (MonyInfo, Dailymax, salesfull tail, customers.w). Producing a date-bound cutover removes the hard blocker while preserving running totals via balances. |
| D16 | **Chain/multi-branch sync in v1 or phase-2?** | Phase-2 (schema ready, feature flagged) | Core-first scope; single-branch deployments don't need the outbox. Locking D02 keeps the schema migration-safe. |
| D17 | **E-invoice network submission: reimplement natively, wrap legacy saturn/toolkit, or defer?** | Reimplement ZATCA/ETA submission natively (FastAPI worker) with proper key management (HSM/KMS/encrypted store); keep QR+JSON generation regardless | The legacy delegates signing to `saturn.exe`/`toolkit.exe` (BouncyCastle). Shipping legacy .exe wrappers is a security/portability liability; but native reimplementation needs the CSID/cert flow spec and a key-management decision. |
| D18 | **Drug-database content + license sign-off** | Confirm CC0 `karem505/egyptian-drug-database` (+ SFDA open data; EDA if public-domain confirmed); include prices from the CC0 set; no DrugEye data | Legal risk is the only blocker for the drug DB; everything else is trivial (schema `external_drug_catalog` + import job). |
| D19 | **VAT price model: are retail prices VAT-inclusive?** | Egypt retail = VAT-inclusive (price-Vat ops exist for reporting); make `branches.vat_inclusive_prices` config flag | Legacy supports both toggles (Price+vat / Price−vat). Wrong default → wrong tax line rounding across the chain. |
| D20 | **Invoice numbering: which is authoritative?** | `invoices.invoice_no` = internal running number (source of truth); printed paper number and ZATCA `invoice.b2b.number` derived/stored separately | Legacy distinguishes Titan internal number / printed number / b2b number (zatca_complete.md §13). |
| D21 | **Roles/permissions: replicate legacy 1–9 numeric or modernize to RBAC?** | Keep legacy semantics as a `permission_level` column (1–9) on `users` + granular `permissions` rows; gate features by level where legacy does (credit-sale, balance-edit ≥7) | Reproducing the exact gates is required for business continuity; full RBAC can layer on later. |
| D22 | **Report scope in v1** | Must-run: RPT-A04 drawer handover, RPT-D01 expired, day totals, shortage, sales/purchase/returns summaries, VAT report, trial balance. Full RPT catalog phase-2. | 45+ report types map to forms, not SQL; cannot all be rebuilt first. |
| D23 | **Which ZATCA "summer" JSON shape is real?** | Build one canonical ETA/ZATCA payload (merge api_integration.md §2.5 with zatca_complete.md §3) and discard the other two — confirm against saturn/toolkit args (`--generate-uuid`) | Three competing shapes in corpus (GAPS §5); undecidable from docs alone (needs the real saturn consumer or a live test). |

---

## 4. Risks & mitigations

| # | Risk | Likelihood / Impact | Mitigation |
|---|---|---|---|
| R1 | **Legacy data fidelity** — money truth in undocumented `.phy` files; only partial layouts (Daily.phy 614-B tail 0x3c..614 unknown; MonyInfo, Dailymax, delivery, salesfull, customers.w fields unmapped; this install has ~zero real money data). | High / High | D15 cutover-from-date; graceful-degradation contract (C20); production `Files\DBI` sample required to finish layouts; per-day reconciliation before cutover (legacy_import README §4); never re-sum floats (C12). |
| R2 | **Float money in legacy** — VB6 REAL/Single money across schema + `.phy`; re-summing floats silently corrupts totals. | High / High | C10–C12: exact decimal everywhere; round-once-at-import; SQL aggregation only on decimal columns; shared money module. |
| R3 | **Schema contradictions** — 11 tables conflicted; citation off-by-3 systematic. | Resolved (medium residual) / High | SCHEMA_RESOLVED.md adopted (D10); enforce N+3 rule on all citations; keep schema_complete.sql as single source of truth; GAPS §7.1. |
| R4 | **Sync conflicts** — LWW no-merge is the legacy behavior but loses data on concurrent edits (two branches change same drug price/stock). | Medium / Medium | Explicit LWW outbox + audit; per-entity conflict record in `sync_log` (status includes `skipped`); main-device gate for controlled writes (is_main_device). If the business needs merge semantics, that's a NEW decision (out of scope). |
| R5 | **E-invoice signer/key management** — CSID certificates, OAuth secrets, and the counter/hash chain are the only thing that makes invoices tamper-evident to the tax authority. | Medium / High | Native signing path (D17) with key isolation; `einvoice_counters` updated atomically with each invoice (C3); hash-chain verification on submit; status workflow pending→submitted→accepted/rejected + resubmission. |
| R6 | **Regulatory drift** — ZATCA/ETA schemas and SFDA SOAP contracts change; dead URLs in the corpus today. | Medium / Medium | Config-driven endpoints; versioned payload templates; outbox lets a change only affect new invoices; keep old payloads in `einvoice_log` for audit. |
| R7 | **Drug-DB legal exposure** — shipping DrugEye or non-licensed data → takedown/damages. | Medium / High | C1 hard block; only CC0/SFDA/EDA sources; record license provenance per catalog import. |
| R8 | **cp1256 / encoding corruption** — legacy Arabic stored as literal `?` in some installs; mixed encodings. | Medium / Medium | Decode cp1256 with padding strip (PHY_MIGRATION §0b); flag `?`-corrupt names; Arabic-first canonical encoding is UTF-8 in the new system. |
| R9 | **Migration of the dual customer/supplier identity** (companies.mobile vs wzcustomers.randomid) — wrong merge → wrong AR/AP. | Medium / High | Explicit merge via `parties` + `branch_identities`; don't auto-merge conflicting keys; report unmatched rows for manual adjudication (D-side human review). |
| R10 | **Cutover correctness** — day-close invariants, opening balances, and the "first invoice must be a purchase" rule during migration. | Medium / High | Seed opening balances explicitly (`month_open_balances`); reconciliation runbook; go-live checklist tied to RPT-A04/balance-sheet equality. |

---

## 5. Definitive numbered decisions the human must confirm BEFORE coding starts (order = impact)

> These are the gates. Numbering is by impact on architecture/schema — confirm D1–D3 before any DDL;
> D4–D9 before the ETL/cutover plan; D10 before the integration phase.

1. **D1 — Target market(s).** Egypt, Saudi, or both? This fixes VAT default (14 vs 15), the
   mandatory e-invoicing path (ETA vs ZATCA), whether SFDA DTTS serialized-drug tracking is in
   scope, default currency, and the pricing model. *Everything downstream keys off this.*
2. **D2 — Migration scope.** Full-history vs cutover-from-a-date. The `.phy` money files cannot be
   fully decoded without a production sample; a date-bound cutover with balance-seeding is the
   only way to unblock the schedule. Also confirms whether a production `Files\DBI` copy is
   obtainable (and its format).
3. **D3 — Drug-database content & license.** Confirm CC0/SFDA/EDA sources (no DrugEye) and whether
   prices/barcodes ship from the CC0 set. Blocker for the drug DB and the whole POS lookup UX.
4. **D4 — E-invoice submission strategy.** Native reimplementation (recommended) vs wrapping legacy
   saturn/toolkit vs deferring submission behind an outbox. Includes the CSID/key-management model.
5. **D5 — Confirm the 11 schema resolutions (SCHEMA_RESOLVED) against real-world knowledge.**
   In particular: is `titanksasales` truly a summary table in production (9-col) or were both shapes
   used across versions? Is `invoicedata` the real runtime invoice store (17-col header+line merged)?
   *(See §6 for the full contradiction list.)*
6. **D6 — VAT price model.** Retail prices VAT-inclusive (Egypt) vs exclusive (Gulf B2B) as the
   default; per-branch override. Wrong choice silently mis-rounds every line tax.
7. **D7 — Invoice numbering.** Internal running number as source of truth; printed and ZATCA b2b
   numbers derived. Confirms the numbering source during migration (gaps in legacy sequences).
8. **D8 — Roles/permissions model.** Keep legacy 1–9 numeric gates (recommended) vs full RBAC.
9. **D9 — Chain-sync scope.** Phase-2 flag (recommended) vs v1. Schema is built either way (D02/C9).
10. **D10 — ZATCA "summer" payload shape.** Which of the three corpus JSON shapes is the real one —
    confirm against saturn/toolkit or a live sandbox before building the e-invoice builder.
11. **D11 — Report scope in v1.** Confirm the must-run report list (§2.2 D22).
12. **D12 — `.phy` layout finish budget.** Approve the degrade-then-import contract (C20) and accept
    that Dailymax/MonyInfo/delivery/salesfull/customers fields may land as `UNKNOWN_LAYOUT` until a
    production sample arrives.

---

## 6. Internally contradictory items in the corpus — needing the human's real-world knowledge

Schema-level contradictions were *adjudicated from p-code* (SCHEMA_RESOLVED), not from real-world
data. Each "RESOLVED" row below is the adjudication; each is **pending your confirmation** because
the corpus cannot prove what a production DB actually contains:

| # | Item | Corpus says | Adjudicated (SCHEMA_RESOLVED) | What only you know |
|---|---|---|---|---|
| 1 | `titanksasales` | 9-col summary (schema_complete.sql:113-123) vs 15-col line-item (business_logic_complete.md:104-120) vs more (reports_complete.md:1033) | **9-col summary**; 15-col = invoicedata/RawakidTablew misattribution (guid insert loop live 3,564×). | Did production ever have both shapes across TITAN versions? Was chain sales ever line-level? |
| 2 | `invoicedata` | header-only (raw schema.sql) vs header+line merged (schema_complete.sql:168-187) | **17-col merged single table**; header + lines in one row (line-items INSERT live ×3). | Is `invoicedata` the real runtime store, or a legacy leftover superseded by `.phy`+`farysales`? Do purchases and sales share it? |
| 3 | `wzphar` | `pharname` (schema) vs `pharmacyname` (aggregate SQL) | **`wzphar.pharname`**; `pharmacyname` belongs to storediscount/titanpharmalist. | No conflict once named — confirm pharmacy-name field semantics for import matching. |
| 4 | `titanksastock` | 8-col vs 24-col "Primary Drug Table" | **8-col**; 24-col = wzdrugs. | Was chain stock ever denormalized with price/barcode in production? |
| 5 | `titanneed` | 5-col needs vs 7-col stock snapshot (disjoint) | **6-col needs** (id+drugname/quant/datee/sender/target); 7-col = titanksastock pasted. | Were needs ever used as a stock snapshot? |
| 6 | `TitanUserAction` | 11-col (SQL) vs 10-col ×2 (no id / different types) | **11-col with id**; `units INT`, `datee REAL`. | Was the audit log ever 10-col in older versions (affects old backups)? |
| 7 | `usersourceupdate` | 6 vs 9 vs 4 cols | **6-col** (`id,drugname,price,units,localimport,datee`); SELECT `top 3000 … Datee >` matches. | Which shape exists in production? The 9-col (raw schema.sql) is real — is it the newer one? |
| 8 | `ChainBuyUsers` | 12 vs 4 vs 1 cols | **12-col + id**; 4/1-col = raw lineage. | Is chain-buy actually used in your deployment? |
| 9 | `taronlineeg` vs `farysales` | reports_complete.md:1040 swapped the two tables' column lists | **taronlineeg = 7-col online catalog**; **farysales = 17-col branch ledger** (INSERT live ×3). | Confirmed by p-code, but confirm the ETA/online module intent in production. |
| 10 | `titaninn` | transfer (schema) vs purchases (business_logic) | **7-col transfer table** (fatid/itemsasstring/datee/source/silsilaid/target). | Purchases via titaninn never existed? Transfers only? |
| 11 | `creditdebit` | appears in report SQL, in no CREATE for titanksasales/invoicedata | **A real `farysales` column**; the sales-return discriminator. | Confirm `creditdebit` semantics ('debit'/'credit' per legacy) are what your accountants expect. |
| 12 | ZATCA "summer" JSON | 3 competing shapes (reports_complete.md:1193-1256, api_integration.md:216-328, zatca_complete.md:99-205) | **Unresolved** — needs the real saturn consumer | Which payload does the tax side actually accept? Do you have a sandbox/CSID to test against? |
| 13 | `wzmony`/`wzdaily`/`wzbank` | feature docs use these as SQL tables; no CREATE exists | Conceptual shorthand for `.phy` + `farysales` (connections_overview.md:139) | Do real tables exist in production DBs (dropped or never extracted)? If yes, get their DDL — they'd be the money schema. |
| 14 | `farysales` scope | "fary (branch) sales" but used for balances/purchases/returns as a general ledger | `journal_lines` + `balances` mapping | Do ALL journal entries land in farysales in production, or only sales/branch postings? |
| 15 | Supplier identity | `companies` (mobile/pass) + `wzcustomers` (typee) | merged into `parties` via explicit merge key | What is the real merge key — mobile or randomid — for your data? |
| 16 | `agel` | column meaning "age/type" | Undocumented (GAPS §4.5) | What does `agel` mean in your cash-flow logic — credit/deferred? It is the `أجل` (credit) counterpart of `payed`. |
| 17 | Sales-return discriminator | `creditdebit` exists in neither titanksasales nor invoicedata | It is a farysales column (§11 above) | How were returns distinguished in the `.phy` day ledger vs SQL in your install? |
| 18 | VAT price model | both inclusive/exclusive toggles exist | not resolved | Egypt retail is VAT-inclusive; confirm per-branch default (D6). |

---

## 7. Explicit assumptions

1. **Egypt is the primary deployment** (product origin, EGP default, EDA data) but the schema must
   support Saudi (ZATCA + DTTS + 15% VAT) without change — the corpus supports both, and the legacy
   targets both. Human decision D1.
2. **A production `Files\DBI` copy (or a backup containing it) is obtainable** and is the only way
   to finish `.phy` layouts; the current Wine install holds ~zero real money data (PHY_MIGRATION §0b).
3. **Schema `schema_postgres.sql` / `schema_sqlite.sql` are the current best expression of the locked
   decisions** and are not to be contradicted by later docs unless a human decision above changes them.
4. **`SCHEMA_RESOLVED.md` p-code adjudications are trustworthy** (evidence-graded, not asserted) —
   but each still needs your confirmation against real production data (§6).
5. **The `.phy`/file-backed money truth must be imported or reconciled**, never silently dropped;
   where layouts are unknown, graceful degradation + explicit `UNKNOWN_LAYOUT` records is the
   accepted behavior (C20, D12).
6. **Legacy `.rur`/`Phye.safer`/`xj` backup formats are opaque** — archived as blobs in
   `archive_exports`; no field-level import is attempted.
7. **No new money rounding rules** will be introduced beyond C11; any deviation (e.g. per-invoice
   rounding at VAT-account level) is a human decision.

---

## 8. The three things that block everything

1. **C1 — DrugEye data must not ship** (legal). The drug DB and the entire POS lookup UX depend on
   which licensed dataset(s) you approve (D3). This is the only legal blocker in the corpus.
2. **C10/C11/C12 — exact-decimal money + single rounding rule + never-re-sum floats.** Every schema,
   ETL, and report design depends on it; violating it silently corrupts the ledger.
3. **C9 — `branch_id` on every money/stock/ledger row** (with (branch, month, year) keys). Without
   it the per-branch ledger, كشف حساب, ميزان, and consolidation cannot be built at all.
   *Plus the migration reality: money truth lives in undocumented `.phy` files* — so D2 (migration
   scope) and a production `Files\DBI` sample are the schedule gate (R1).

---

## 9. Cross-plan obligations (what other plans must respect)

- **Schema plan:** must implement C9–C13, D02–D13 verbatim; must not reintroduce REAL/float money;
  must keep PG/SQLite column parity.
- **Migration/ETL plan:** C12 (round-once), C20 (degrade not block), D15 (scope), reconciliation
  runbook, `branch_identities` for the `phar`/`pharmacyid`/`mobile` aliases.
- **API plan:** balanced-journal invariant in the transaction (C16), audit rows in the same txn
  (C14), single rounding point in the shared money module (C11), LWW outbox writes (C13).
- **Frontend plans:** Arabic-first (C22), offline-first full day (C8), permission gates 1–9 (C5),
  drawer/cash/شبكة/أجل split semantics in the POS.
- **Integration plan:** e-invoice JSON/QR + in-DB counters (C3), native vs wrapper decision (D17),
  config-driven endpoints (R6), no vendor RCE/data-selling channels (C6).