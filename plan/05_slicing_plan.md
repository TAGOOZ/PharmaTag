# 05 — Vertical Slicing Plan: Rebuilding TITAN.W1

**Scope:** Build-ready vertical slices + phased delivery roadmap for rebuilding the VB6
TITAN.W1 (Phye.exe) pharmacy ERP on a modern stack.
**Stack decision:** FastAPI + PostgreSQL (canonical, money-truth server) · Next.js web ·
Tauri + React desktop with a SQLite offline twin that syncs through the API.
**Style of the rewrite:** PHASED, CORE-FIRST. The money/stock/ledger truth is authoritative
(see SCHEMA_EVALUATION.md §3 bottom line); non-money, vendor, and dead features are deferred.
**Migration:** legacy `.phy` import is a dedicated workstream (Phase 6 — ⛔ BLOCKED, no
legacy data; **not scheduled**), toolchain already exists in `legacy_import/`.

Source documents consulted: `titan_extract/GAPS_REPORT.md`, `ui_complete.md`,
`business_logic_complete.md`, `SCHEMA_RESOLVED.md`, `SCHEMA_EVALUATION.md`,
`PHY_MIGRATION.md`, `schema/schema_design.md`, `schema/schema_postgres.sql`, and the
`feature_*.md` set.

---

## Reconciled 2026-08-16

Reconciliation of this plan against the locked decisions in `00_decisions_master.md`:

- **Phase 6 legacy migration is ⛔ BLOCKED** — the client has **no production `Files\DBI`
  copy and no SQL dump** (X01/X02). Phase 6 is **not scheduled**; it resumes when legacy
  data arrives. The G02 cutover-from-date contract stands — drug-master import + money
  history resume then.
- **P08 desktop-first:** the Tauri/SQLite offline desktop app is the **primary** slice
  target; web is secondary/server-backed (read-only dashboards first). Light-primary theme
  (P02) and low-spec POS hardware budget (A13) apply throughout.
- **Out of v1:** insurance/copay (deferred to Phase 2+, plugin skeleton) and HungerStation
  (skipped) are out of v1. E-invoicing scope = **ETA (Egypt)** per the official SDK spec,
  Phase 4; ZATCA stays a Saudi override only.
- §6 open decisions annotated: resolved items marked ✓, data-gated items left open.

---

## 1. Slice definition for this project

A **vertical slice** is one demonstrable end-to-end capability, not a layer. Each slice:

1. **Schema:** a forward migration + matching SQLite twin table (or a column-set change),
   implementing one resolved decision from `schema_postgres.sql` / `SCHEMA_EVALUATION.md`.
2. **API:** FastAPI router(s) with the business rule for that capability (invariants enforced
   in an API transaction: balanced journal, stock batch decrement, branch scoping, audit row).
3. **Screens:** desktop (Tauri, offline twin) is the **primary slice target** per P08; web
   (Next.js) is secondary/server-backed (read-only dashboards first) — one platform per
   slice, never both in one slice.
4. **Offline behavior:** what the Tauri/SQLite twin does when the network is down (write-local
   + outbox, then sync).
5. **Tests:** slice-level integration test that proves the end-to-end flow and the money
   invariant (journal balances, audit row present, branch correct).
6. **Audit & sync side-effects:** every money/stock mutation writes an `audit_log` row in the
   same transaction; chain/cloud effects go to the `sync_outbox`.

**A slice is DONE only when all six are true and demoable** — e.g. "log in as cashier, sell a
drug, watch stock decrement by batch, journal stays balanced, audit row recorded, invoice
visible in today's reports." No slice is shippable in isolation of its exit criteria.

**Anti-slices (explicitly not slices):** "the auth screen", "the schema migration", "the API
layer", "the reports module" — these are chunks of work that never ship a value alone.

---

## 2. Phase roadmap (Phase 0 → 6)

Each phase lists: **goal**, **slices**, **exit criteria**, **intentionally deferred + why**.

### Phase 0 — Skeleton, plumbing, and demo harness

- **Goal:** standing system with one happy-path slice proving the whole slice definition.
- **Slices:**
  - S0.1 Dev bootstrap: FastAPI app, PostgreSQL + SQLite twin, Alembic + SQLite-mirror
    migrations, CI, lint, test harness.
  - S0.2 Web + desktop shells with login navigation shell (no auth yet).
  - S0.3 **First vertical slice: "Login + branch + drug master read"** — the smallest real
    capability that proves slices end-to-end (auth users seeded, branches from wzphar,
    drugs from wzdrugs; web shows drug list; desktop shows same offline from SQLite).
- **Exit criteria:** a new developer can run the whole stack from a README; a drug master
  record created via API appears on web AND on a disconnected desktop; CI green.
- **Deferred:** everything else. The point is proving the slice discipline early.

### Phase 1 — MVP (first sellable single-branch system)

- **Goal:** a pharmacy can run daily operations on one branch with real money, stock, and
  day-close — the minimal set a customer would pay for.
- **Slices (detailed in §3):**
  - S1.1 Auth, users, roles, permissions (8 user types, 1–9 levels)
  - S1.2 Drug master + barcodes + pricing (3 price levels + VAT, ≤6 barcodes)
  - S1.3 Sales invoicing ("oot") — save, print, stock decrement by batch, balances, audit
  - S1.4 Purchases ("inn") — stock up, supplier payable, payment splits
  - S1.5 Sales returns (600/800 conversion, reversal of stock/balance/money)
  - S1.6 Purchase returns
  - S1.7 Simple stock count + balance correction (with approval)
  - S1.8 Cash drawer + day close (drawer equation, deficit/surplus)
  - S1.9 Basic reports: day profit (ربح اليوم), sales/purchases summary, stock minimum
- **Exit criteria:** close a full simulated day (open shift → sells → returns → purchases →
  count → close) on a single branch; drawer equation balances; journal is balanced for every
  document; day-close can be rolled forward to the next day.
- **Deferred (why):** multi-branch/chain (Phase 5) — MVP is single-branch; receivables
  ledger beyond the basic customer/supplier balance (Phase 2) — the balances are tracked but
  the full customer statement is not; ETA e-invoicing (Egypt, Phase 4) — legal requirement
  but not needed to run the store; month close (Phase 2) — daily close is the hard invariant.

### Phase 2 — Money, ledger, balances, receivables, month close

- **Goal:** the accounting spine — chart of accounts per branch, journal entries, customer
  statement (كشف حساب), supplier payables, trial balance (ميزان), month close + archive.
- **Slices:**
  - S2.1 Chart of accounts (per-branch tree, wzaccfreetree) + account setup
  - S2.2 Manual journal entries (FormAccAddQueed) — balanced-check enforced
  - S2.3 Customer statement / supplier payables ledger (from journal_lines with
    branch/month/year)
  - S2.4 Receivables/credit (أجل) management + settlement (سند قبض/صرف)
  - S2.5 Trial balance + balance sheet (FormMizan)
  - S2.6 Month close + `month_open_balances` + archive (monthy\moves)
  - S2.7 Opening balances (cash, stock at cost, receivables, payables)
- **Exit criteria:** any money document (sale, return, purchase, manual journal, settlement)
  produces journal_lines where `SUM(debit) = SUM(credit)` per journal; per-branch trial
  balance reconciles to drawer + stock + customer/supplier balances; month can be closed and
  re-opened; a customer's statement is correct across multiple months.
- **Deferred (why):** year-end close (rare, one config flag); region/Governorate fields on
  parties (add later without migration pain — additive column); insurance/copay module
  (X08 — deferred to Phase 2+, plugin skeleton only, **out of v1**).

### Phase 3 — Reports & analytics breadth

- **Goal:** reproduce the 50+ legacy reports (RPT-xx) that customers actually print/export,
  including the money-critical ones.
- **Slices:**
  - S3.1 Report framework: template engine, A4/A5, export PDF/Excel, print queue
  - S3.2 Money reports: day profit (ربح اليوم), drawer handover (تسليم الدرج), daily totals
    (cash/manual/network/manual-network splits)
  - S3.3 Stock reports: current stock, movements, expired stock, minimum/auto-order needs
  - S3.4 Sales/purchase reports: invoices, returns, supplier/customer totals by period
  - S3.5 Accounting reports: trial balance, balance sheet, ledger by account, tax summary
- **Exit criteria:** the full legacy report catalogue is inventoried (RPT-xx → slice) and at
  least the money-critical ones match legacy totals on a migrated dataset (reconcile against
  .phy import).
- **Deferred (why):** dashboard/analytics charts (nice-to-have, new invention — not in
  legacy); Egypt ETA tax reports (Phase 4 owns them).

### Phase 4 — ETA e-invoicing (Egypt, tax compliance)

- **Goal:** tax-compliant **ETA (Egypt)** invoicing per the official SDK spec — ETA Invoice
  v1.0 JSON + eReceipt v1.2 (CAdES-BES signing, eSeal), driven by `einvoice_log` +
  DB-resident `einvoice_counters`. ZATCA (Saudi) is out of primary scope — kept as an
  override only.
- **Slices:**
  - S4.1 E-invoice record + counters: `einvoice_log`, `einvoice_counters`, QR generation,
    tax invoice templates (فاتورة ضريبية / مبسطة / أجل / مرتجع)
  - S4.2 ETA submission + status tracking + resubmission (preprod/prod per SDK spec)
  - S4.3 ETA Invoice v1.0 / eReceipt v1.2 JSON generation per the official SDK spec
    (CAdES-BES, SHA-256 QR hash) + submission — replaces the corpus's recovered shapes
    (G05 reframed)
- **Exit criteria:** a sales invoice produces a tax invoice with a QR; counter/hash chain is
  verifiable and atomic with the invoice; submission status is tracked and resubmittable;
  works offline (queued) then syncs.
- **Deferred (why):** actual network submission gate for launch (env-config toggle); legacy
  `ModEtaWrappper`/`ModTafqit`/Saturn integration is replaced by native implementation —
  the dead URLs are not called until configured; ZATCA = Saudi override only (not v1).

### Phase 5 — Chain / cloud sync, transfers & logistics

- **Goal:** multi-branch (chain) operations: inter-pharmacy transfers, needs/orders,
  last-write-wins replication of chain tables, "main device / sub device" roles.
- **Slices:**
  - S5.1 `branches` registry (wzphar/titanpharmalist) + main/sub device roles
  - S5.2 Inter-pharmacy transfers (titaninn) + `delivery.phy` state + transfer_lines
  - S5.3 Needs/orders (titanneed → needs, orders → purchase_orders), auto-order
  - S5.4 Chain sales sync (titanksasales GUID loop → sync_outbox), last-write-wins
  - S5.5 Cross-branch stock snapshot (titanksastock → branch_stock) + minimums
  - S5.6 Chain buy store/users (ChainBuyStore/ChainBuyUsers)
- **Exit criteria:** two branches can transfer stock, see each other's needs, and reconcile a
  chain sale; sync conflicts resolve last-write-wins and are recorded in `sync_log`; offline
  branch catches up on reconnect.
- **Deferred (why):** real-time chat/notifications (not in legacy core); dead-stock
  exchange (RawakidTablew) — rare, additive later.

### Phase 6 — Legacy `.phy` historical migration — ⛔ BLOCKED (not scheduled)

> **Status: BLOCKED — awaits legacy data.** The client has **no production `Files\DBI`
> copy and no SQL dump** (X01/X02). Phase 6 is **not scheduled**; it resumes only when
> legacy data arrives. The **G02 cutover-from-date contract stands** — drug-master import
> (S6.4) + money-history resume (S6.2/S6.3/S6.5) happen then, with seeded balances at
> cutover.

- **Goal:** bring real historical money truth from the production machine's `Files\DBI`
  into the new schema so the store can cut over without losing history. (On hold — no data.)
- **Slices (all blocked — resume when a production `Files\DBI` copy / SQL dump arrives):**
  - S6.1 Complete record-layout pass on remaining 12 files (MonyInfo, usersmony, closefary,
    fary.date, delivery, workperiod, oot3, netcounter, RasidCorrect, acctree, Dailymax,
    tarinfo) — needs a **real populated production copy** (fresh install has no money data;
    none available yet).
  - S6.2 Daily.phy family → `drawer_movements`/`daily_close` import + reconcile
  - S6.3 daily-manual/-2 → `manual_journal_entries`; usersmony → `user_drawer_money`
  - S6.4 wzdrugs/wzgard/titanstock legacy SQL → drugs/batches/branch_stock
  - S6.5 invoicedata/titanksasales → invoices/invoice_lines (split header+lines correctly
    per SCHEMA_RESOLVED.md §7) with branch_identities alias mapping
  - S6.6 Final reconciliation runbook: money files = source of truth; SQL DB is not.
- **Exit criteria (only once data arrives):** historical open balances match legacy reports
  to the cent; the store can run the new system in production on a single branch and every
  report reconciles.
- **Deferred (why):** BLOCKED — no production `Files\DBI` copy and no SQL dump exist
  (X01/X02). The money slices (Phase 1–2) define the target shapes first; the import needs
  the resolved schema AND real data. The earlier *"pull forward to Phase 4"* option is moot
  until data exists (see risk R3).

---

## 3. Phase 1 — slice-by-slice breakdown

Common entry for all MVP slices: Phase 0 done, CI green, dev env reproducible.

### S1.1 Auth, users, roles, permissions

- **Entry:** S0.3 schema present (users, roles, branch). 
- **Content:** 8 user types; numeric permission level 1–9; username = 17-digit numeric ID
  (legacy convention); per-user menu visibility; `TitanUserAction`-style audit on login and
  role change; password hashing (argon2) — legacy plaintext is migrated with forced reset.
- **Rules:** a sale requires `المبيعات` permission; day-close requires manager level;
  branch-scoped users.
- **Exit:** login as cashier sees only their menu; a permission-blocked action returns 403 on
  API and is hidden in UI; login attempt audited.

### S1.2 Drug master + barcodes + pricing

- **Entry:** S1.1 (permissions gate editing). 
- **Content:** drug CRUD (wzdrugs + wzdrugs2), up to 6 barcodes (drug_barcodes child table,
  unique index), unit + small-unit conversions, 3 price levels (public/wholesale/cost) +
  VAT % + configurable country VAT default, expiry field, `price_change_log` (storediscount
  lineage) on every price change.
- **Rules:** a drug is found by ANY barcode; price change writes audit + price_change_log;
  DrugEye-style bulk import deferred (S3/Phase 6) but the import endpoint shape is stubbed.
- **Exit:** add drug with 2 barcodes + 3 prices; scan barcode 2 on the sale screen later and
  it resolves; price change appears in the change log; all audit rows present.

### S1.3 Sales invoicing ("oot")

- **Entry:** S1.2 (drug lookup by barcode), S1.1 (permission).
- **Content:** new invoice → add lines (barcode lookup, qty, batch/expiry selection) →
  discount (SellDisc %) → VAT → totals; states Saved / Unsaved / Copy; F9-style save;
  `invoicedata` header+lines; stock decrement from `stock_batches` FIFO/expiry; journal
  entries (debit customer/drawer, credit sales) in one transaction; `audit_log` row;
  `sync_outbox` row for chain (idempotent, no-op in single branch); print tax invoice
  (basic A5); payment split cash / card / credit (أجل), invariant `totalvalue = payed + agel`.
- **Rules:** cannot save negative stock; cannot sell below a configurable floor; credit sale
  updates customer balance; cash updates drawer (Phase 1.8 ties drawer).
- **Exit:** full end-to-end sale demo (scan → save → print → stock down → journal balanced →
  audit row → balance updated); an invalid credit-over-limit is rejected with a clear
  Arabic message.

### S1.4 Purchases ("inn")

- **Entry:** S1.3 (same invoice/journal machinery), S1.2 (drug exists or create-on-purchase).
- **Content:** purchase invoice → adds stock as NEW batch rows (wzgard) with cost/VAT/expiry;
  supplier payable (دائن) increases; payment split; purchase return analog.
- **Rules:** purchase raises `stock_batches` (new randomid) and never overwrites existing
  batch stock; opening stock can be entered as special purchase batches (see S2.7).
- **Exit:** buy a drug, verify new batch with cost; supplier statement shows the payable;
  journal balanced; reversing (purchase return) restores supplier balance and removes batch.

### S1.5 Sales returns (مرتجع بيع)

- **Entry:** S1.3 (must operate on saved invoices).
- **Content:** two routes (convert saved invoice via 600/800 code prompt; or new return
  invoice referencing original); return qty ≤ original qty; original must exist; reverses
  stock (new return batch), customer balance, drawer cash, journal, `invoicedata` reverse
  lines, `TitanUserAction` audit; tax return invoice (فاتورة ضريبية - مرتجع); paid vs
  credit return (مرتجع مدفوع vs credit).
- **Rules:** after day close, unsave disabled — only copy-to-return/purchase allowed;
  expiry returns (مرتجع اكسبير) flagged.
- **Exit:** return part of a saved sale; stock restored; customer balance corrected; drawer
  math (drawer = cash sales − cash returns + settlements) still balances; audit trail shows
  the reversal.

### S1.6 Purchase returns (مرتجع مشتريات)

- **Entry:** S1.4, S1.5 pattern.
- **Content:** reverse of purchase: remove/return batch quantity, reduce supplier payable,
  journal + audit. Expiry/purchase-return variant.
- **Exit:** return a purchased batch; supplier balance and batch qty correct; journal balanced.

### S1.7 Stock count + balance correction (with approval)

- **Entry:** S1.3/S1.4 (batches exist), S1.1 (manager role).
- **Content:** count screen (FormStockNow) → expected vs counted → correction request
  (بالزيادة/بالعجز) → manager approve/reject → on approval a `wzgard`-style movement row
  (`typee = count`) with cost+VAT; `stock_correction_requests` state machine;
  `audit_log`.
- **Rules:** no cashier can adjust a balance directly — manager approval required;
  corrections are batch movements, not blind overwrites.
- **Exit:** cashier submits count delta, manager approves, stock + audit correct; a rejected
  request changes nothing.

### S1.8 Cash drawer + day close

- **Entry:** S1.3–S1.6 (money flows), S1.1 (manager).
- **Content:** drawer register (user_drawer_money per user/shift); drawer equation
  (drawer = cash sales − cash returns + customer settlements + manual cash − expenses);
  day close (ModEnd): count drawer (عد الدرج), deficit/surplus (عجز/زيادة) reconciliation,
  advance the global system date, roll forward; `daily_close` with the FULL aggregate set
  (manual_cash, manual_card, cost_of_sales, net_profit ربح اليوم, discounts, drawer@start,
  shift_id).
- **Rules:** no new sale can post before the current day is closed if day-close is enabled;
  close is idempotent; drawer report (تسليم الدرج) printable.
- **Exit:** a full simulated day closes with a balanced drawer; deficit/surplus journaled;
  next day opens clean; close cannot be double-run.

### S1.9 Basic reports

- **Entry:** S1.3–S1.8 complete (they feed the numbers).
- **Content:** ربح اليوم (day profit), sales summary by period, purchases summary, stock
  current + minimum list, drawer handover (تسليم الدرج). RPT-xx mapped from legacy.
- **Rules:** numbers come from the same journal/drawer/stock sources, so they always agree.
- **Exit:** day-profit report matches drawer close arithmetic to the cent.

---

## 4. Dependency graph

```
Phase 0 ──► S1.1 ──► S1.2 ──► S1.3 ──► S1.4 ──► S1.5 ──► S1.6
                │        │         │         │         │
                │        │         ├─────────┴──┬──────┘
                │        │         ▼            ▼
                │        └────► S1.7      S1.8 (drawer/close) ──► S1.9
                │                        (needs S1.3–S1.6)
                ▼
        S2.1 ──► S2.2 ──► S2.3 ──► S2.5 ──► S2.6
          │            └──────────► S2.4
          └────────────► S2.7 (opening balances; can start early if desired)

Phase 3: S3.1 (framework) ⟂ S3.2 (needs S1.8/S2) · S3.3 (needs S1.7) ·
         S3.4 (needs S1.3–S1.6) · S3.5 (needs S2)

Phase 4: S4.1 (needs S1.3 + counters) ──► S4.2/S4.3 ETA (Egypt, per official SDK spec)

Phase 5: S5.1 (branches registry) ──► S5.2 transfers ──► S5.3 needs/orders
         ├──► S5.4 chain-sales sync (needs S1.3 outbox + S5.1)
         ├──► S5.5 branch_stock snapshots
         └──► S5.6 chain buy

Phase 6: ⛔ BLOCKED — awaits legacy data (no production `Files\DBI` copy / SQL dump);
         S6.1 (layout pass) ──► S6.2–S6.6 resume when it arrives
         (S6.4/S6.5 need SCHEMA_RESOLVED.md shapes; S6.6 reconciliation runbook)
```

**Key parallelization:** Phase 1 S1.1–S1.2 strictly sequential (permissions gate the drug
editor); S1.3→S1.4 share the invoice/journal machinery so do them back-to-back; S1.5/S1.6
are cheap follow-ons; S1.7 and S1.8 can be built in parallel once S1.3–S1.6 land, but S1.8
must precede S1.9. Phase 2 S2.1–S2.2 strictly sequential; S2.3/S2.4 depend on the journal
line shape; S2.5/S2.6 stack on S2.3. Phase 3 slices are independent once their feeders land.
Phase 4 S4.1 must land before S4.2/S4.3.

---

## 5. Sequencing risks

- **R1 — Money invariants are the whole ballgame.** A sale that silently unbalances the
  journal or drops an audit row must be caught in S1.3's integration tests. Mitigation:
  write the invariant tests FIRST (TDD) for S1.3/S1.4/S1.5/S1.8; freeze the money-typing
  rule (`NUMERIC`, round-half-up, no REAL/float) in code review.
- **R2 — Branch dimension omission (SCHEMA_EVALUATION §1.1).** If `branch_id` is not on
  `journal_lines`/`balances`/`monthly_close` from day one, Phase 5 and Phase 2 ledger work
  are retrofits. Mitigation: Phase 0 DDL includes `branch_id NOT NULL` everywhere money/
  stock lives; single-branch Phase 1 just always uses branch 1.
- **R3 — Legacy migration BLOCKED on real data.** The client has **no production
  `Files\DBI` copy and no SQL dump** (X01/X02); MonyInfo.phy and 11 more layouts need a real
  populated production copy. Mitigation: Phase 6 is BLOCKED / **not scheduled** — resumes
  when legacy data arrives; until then the `.phy`-to-table mapping stays a stub. The G02
  cutover-from-date contract stands (drug-master import + money history resume then). Never
  ship cutover without the reconciliation runbook (S6.6).
- **R4 — invoicedata header+lines-in-one-row split (SCHEMA_RESOLVED §7).** The legacy table
  fuses header and line in one row; naive import corrupts invoice lines. Mitigation: S6.5
  uses the resolved 17-col shape; split into `invoices`+`invoice_lines` with tests against
  real rows before cutover.
- **R5 — Money-typing rounding.** Legacy stores REAL/Single; re-summing floats as NUMERIC
  silently changes totals. Mitigation: define rounding at import (round-half-up at 2 dp on
  line-total and payment boundaries) and verify against legacy reports (S6.6).
- **R6 — No approval gate for corrections.** Allowing cashiers to adjust balances directly
  (SCHEMA_EVALUATION §1.7) would be a regression against legacy controls. Mitigation: S1.7
  enforces manager approval; tests assert a rejected request mutates nothing.
- **R7 — Audit and e-invoice state are easy to defer into oblivion.** `audit_log` and
  `einvoice_log` must exist before the features that write them. Mitigation: the slice
  definition (item 6) makes audit part of every money slice; S4.1 lands counters before
  submission.
- **R8 — Scope creep toward "everything legacy did".** The legacy system has vendor/sketchy
  features (remotecontrol, nilsen2 data-selling) that must NOT be rebuilt. Mitigation: an
  explicit SKIP list (SCHEMA_EVALUATION §2) is kept in the plan; new feature requests get
  checked against it. HungerStation (X07 — skipped) and insurance/copay (X08 — deferred to
  Phase 2+, out of v1) are recorded there.

---

## 6. Numbered open decisions (✓ = resolved per `00_decisions_master.md`)

1. **Single-branch vs chain-first order: ✓ Egypt** (G01). Egypt-first with a
   country-agnostic schema — VAT default 14%, ETA regime, EGP; Saudi = override only.
   Phase 5 stays after Phase 4; no swap needed.
2. **Desktop vs web priority per slice: ✓ Desktop-first** (P08). The Tauri/SQLite offline
   desktop app is the primary slice target; web is secondary/server-backed (read-only
   dashboards first). Apply the light-primary theme (P02) and low-spec POS budget (A13).
3. **Legacy user/password migration:** legacy plaintext credentials — force reset on first
   login vs import-with-reset; and do legacy 17-digit numeric usernames survive as-is?
4. **Currency & country config: ✓ Single currency** (P10/G01). Single-currency default
   (EGP); VAT country config is additive — accepted as an additive column (G06 keeps
   `branches.vat_inclusive_prices`), no separate Phase 0 model.
5. **Batch/expiry sale selection: ✓ Expiry-FIFO, configurable** (A02). Per-branch COGS
   defaults to expiry-FIFO; strict-FIFO and average also available; manual batch pick on
   POS stays. Affects S1.3 UI (config flag).
6. **Chain-sales sync conflict rule: ✓ LWW + panel** (G10). True offline-first; LWW
   auto-resolve + non-destructive conflict review panel; `sync_log` records the loss.
7. **MonyInfo.phy and the 11 unknown layouts: ✓ Migration BLOCKED** (X01/X02). No
   production `Files\DBI` copy and no SQL dump — Phase 6 is BLOCKED / **not scheduled**;
   Phase 1–4 ship with no historical import, migration resumes when data arrives (no static
   mapping possible — PHY_MIGRATION §1).
8. **Reports scope: ✓ Minimal set** (G11). S1.9 minimal set (day totals, drawer handover,
   shortages, expired, sales/purch/returns, VAT, trial balance) + Phase 3 framework is
   acceptable; full 50+ RPT catalog later.
9. **Auth/OAuth: ✓ 1–9 + RBAC** (G08). Single internal users table with legacy 1–9
   `permission_level` + granular permissions rows; RBAC layers on later. No SSO/role
   provider in v1.
10. **Offline write conflicts on invoices:** when two branches sell the same drug offline
    and reconcile, stock is last-write-wins — is that acceptable, or must offline invoice
    numbers be reserved by range to avoid collision?
11. **Who owns the legacy SQL Server migration** (wzdrugs/titanksasales etc.) — same
    `legacy_import` workstream, or a separate DBA-run ETL? Affects S6.4/S6.5 ownership.
    **Still open — data-gated** (awaits the X02 SQL dump).
12. **Printing approach: ✓ Desktop ESC/POS + PDF web** (P09). Desktop: ESC/POS thermal +
    drawer (Rust); web: PDF/80mm fallback. Windows/Linux desktop in v1.

**Remaining open:** #3 (password-import mechanics) and #10 (offline invoice-number range
reservation) — not resolved in the decision log; #11 is data-gated (X02).