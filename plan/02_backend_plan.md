# Backend Plan — TITAN.W1 Modern Replacement

**Scope:** FastAPI + PostgreSQL canonical backend; Tauri/React desktop with SQLite offline twin (`schema/schema_sqlite.sql`); Next.js web client. Read-only on legacy; new transactions all go through this API.
**Authoritative sources:** `schema/schema_postgres.sql` (canonical DDL), `schema/schema_design.md`, `titan_extract/SCHEMA_RESOLVED.md`, `titan_extract/GAPS_REPORT.md`, `titan_extract/business_logic_complete.md`, `titan_decompile/` (ground truth).
**Citation rule (from GAPS_REPORT §1, VERIFIED):** every `strings_*.txt:N` citation in the feature docs is off by **+3** — read as line `N+3`. Where feature docs conflict with `titan_decompile/` or `schema_postgres.sql`, the schema/DDL wins.

## Reconciled 2026-08-16

Aligned to `plan/00_decisions_master.md` (locked decisions). What changed in this pass:

- **G01/G04/G05 — Egypt-first e-invoicing.** §6 rebuilt around the ETA (Egyptian Tax Authority) official standard, research-verified 2026-08-16: official SDK `https://sdk.invoicing.eta.gov.eg` (prod) / `https://sdk.preprod.invoicing.eta.gov.eg` (preprod); Invoice document v1.0 (JSON or XML); eReceipt v1.2 (JSON only, B2C; B2B under Ministerial Decision 188/2020); pre-clearance model (submit → validate → UUID + hash, real-time at issuance); CAdES-BES signing per ITIDA spec (canonicalize → SHA-256 → RSA `sha256WithRSAEncryption` → Base64-embedded signature; signer cert = ETA eSeal X.509, Class 2+); OAuth session token via ETA identity management; async submit + poll/notify; GS1 or Egyptian EGS product coding (GS1 Egypt partnership with EDA). The corpus's three "summer" JSON shapes were **ZATCA/Saudi + dead URLs — not the target**; ZATCA is kept as a reference note for a future Saudi override only.
- **G06 — per-line VAT.** VAT engine resolves each line's `tax_type` — medicines exempt (0%), medical devices 5%, other goods 14%. Retail prices VAT-inclusive; taxable net = total ÷ 1.14. (`branches.vat_inclusive_prices` flag.)
- **G07 — numbering.** `invoice_no` = internal per-branch source of truth; printed + ETA B2B numbers derived.
- **A05 — server rounding.** CONFIRMED (was already recommended).
- **Open decisions:** O-5, O-6, O-10 resolved/aligned to ETA; O-1–O-4, O-7–O-9 confirmed (see §8).
- Assumption #3/#4 updated: Egypt is the primary deployment; Saudi = future override.

Authority: `plan/00_decisions_master.md`.

**Assumptions:**
1. This is a fresh-build target: new installations run PostgreSQL; legacy `titan_extract/` data migration (`legacy_import/`) is a separate track and only affects backfill/seed tasks, not new transaction logic.
2. The canonical schema `schema_postgres.sql` is fixed as the contract for this plan. Any adjudicated legacy-table shape (titanksasales 9-vs-15-col, TitanUserAction DDLs, etc.) is already resolved inside it.
3. Egypt (VAT 14%, ETA) is the primary deployment; Gulf (SA, VAT 15%, ZATCA) is a config-variant / future override of the same code paths (G01).
4. ETA submission is integrated as an asynchronous, retryable, offline-tolerant job (ZATCA = future override only, see §6). No synchronous network call ever blocks saving an invoice.
5. Arabic is a first-class UI concern; every user-facing API returns both a machine error code and Arabic/English message strings.

---

## 1. Backend architecture (monolith)

A single FastAPI application, deployed as one service. Do **not** split microservices: the sale→stock→ledger→audit invariant (below) requires one database transaction per financial write, and the customer set is hundreds of pharmacies, not millions.

### Module boundaries (`app/`)

| Module | Responsibility | Key tables | Legacy anchor |
|---|---|---|---|
| `app/auth/` | Login, token issuance/refresh, RBAC checks | `users`, `roles`, `permissions`, `role_permissions`, `user_roles` | FormUsers/FFFUserEdit, us.phy |
| `app/drugs/` | Drug master, barcodes (primary+5), units, costs, interactions | `drugs`, `drug_barcodes`, `unit_conversions`, `drug_costs`, `drug_interactions` | wzdrugs, wzdrugs2, tar.phy, DDI.Phy |
| `app/parties/` | Customers & suppliers (dual-identity merge into `parties`) | `parties` | wzcustomers, companies, wzsuppliers |
| `app/stock/` | Batches, per-branch stock, transfers, shortages/needs, PO, corrections, dead-stock exchange, chain buy | `stock_batches`, `branch_stock`, `transfers`+`transfer_lines`, `shortage_flags`, `needs`, `purchase_orders`, `stock_correction_requests`, `dead_stock_exchange`, `chain_buy_orders` | wzgard, titanstock/titanksastock, titaninn, titanneed, RawakidTablew, ChainBuyStore |
| `app/sales/` | Sales invoices, returns, void/edit, payment splits, pricing/discounts | `invoices` (kind=sale), `invoice_lines`, `invoice_versions`, `payment_splits` | invoicedata, ModOot, FFFOutPut |
| `app/purchases/` | Purchase invoices & returns | `invoices` (kind=purchase), `invoice_lines`, `invoice_versions` | titaninn, ModInn |
| `app/money/` | Ledger, journals, balances, manual entries, drawer, day/month close | `journals`, `journal_lines`, `balances`, `monthly_close`, `month_open_balances`, `manual_journal_entries`, `drawer_movements`, `daily_close`, `user_drawer_money` | farysales, wzmony, Daily.phy, MonyInfo.phy |
| `app/reports/` | Report catalog + SQL-backed queries | read-only over the above | FormReportsGeneral, ModPrint |
| `app/sync/` | Cross-branch LWW sync, drug server channel | `sync_log`, `drug_sync_outbox`, `branch_registry`, `branch_identities` | usersourceupdate, drgserver, titanpharmalist |
| `app/einvoicing/` | ETA jobs (ZATCA = future override), counters/hash chain, QR | `einvoice_log`, `einvoice_counters` | oot3.phy, netcounter |
| `app/cloud/` | Cloud import/export archives, external catalog | `archive_imports`, `archive_exports`, `external_drug_catalog`, `integration_config` | Archive\Input/Output, taronlineeg |
| `app/config/` | Country/currency/VAT config | `app_config` | config files |

### Cross-cutting foundations (shared, one module each)

- **`app/core/money.py`** — the **single rounding point**. `Decimal` everywhere. `round_half_up(x, 2)` for totals, `round_half_up(x, 4)` for per-unit. Sales formula (business_logic_complete §16.4) implemented here and only here:
  - `subtotal = Σ round4(qty × unit_price)` (per-line, then summed at 2dp is acceptable; but the documented canonical order is per-line `line_total = round2(round4(qty) × unit_price)`)
  - `discount = round2(subtotal × SellDisc/100)`
  - `vat = round2((subtotal − discount) × VAT%/100)` — legacy single-rate §16.4 reference; the canonical engine is per-line below
  - Per-line tax engine (G06): each line resolves `tax_type` (medicine = exempt 0%, medical device = 5%, other = 14%); `vat = Σ round2(line_total × tax_rate)` over taxable lines, exempt lines contribute 0. VAT-inclusive retail: taxable net derived as `total ÷ 1.14`.
  - `total = round2(subtotal − discount + vat)`
  - Never re-sum floats; legacy totals are imported once to 4dp and stored, never recomputed.
- **`app/core/audit.py`** — decorator/dependency that appends `audit_log` rows inside the same transaction for every money/stock/balance write. Tables with an `AUDIT:` COMMENT in the schema are non-negotiable. Also mirrors the TitanUserAction shape (drug_id, barcode, user) so the old audit UX can be reproduced.
- **`app/core/errors.py`** — error codes + Arabic/English messages; see §2.
- **`app/core/db.py`** — async SQLAlchemy session, transaction boundary helper `atomic()` that enforces the balanced-journal invariant (below).
- **`app/core/rbac.py`** — permission-check dependency; see §3.

### Transaction invariants (enforced in API transactions, not DDL)

1. **Sale atomicity:** create invoice + lines → decrement `stock_batches`/`branch_stock` (FIFO/expiry selection via `ix_stock_batches_expiry`) → post journal → update `balances` → insert `audit_log` — all or nothing. Partial failure rolls everything back.
2. **Balanced journal:** per `journal_id`, `SUM(debit) = SUM(credit)` (schema_postgres.sql:381-382; feature_balances.md:328). `journal_lines` already carries the single-side CHECK.
3. **Payment split identity:** `payed + agel = totalvalue` (CHECK on `invoices`); payment_splits must sum to `payed`.
4. **Day-close lock:** `UNIQUE (branch_id, datee)` on `daily_close` — a date closes once per branch; reopening writes a reversal (daily_close:497-500).
5. **Batch single movement:** each stock_batches row is one `typee` movement (wzgard); a sale can split across batches, each batch row written once with its own `oldstock` snapshot.

### Backend language/stack decisions

- **Python 3.12 + FastAPI + async SQLAlchemy 2 + Pydantic v2.** Rationale: the `.phy`/pcode migration tooling (`legacy_import/`) is already Python; one language for ETL and API keeps rounding/Decimal semantics identical.
- **PostgreSQL 16** with the canonical DDL as-is (JSONB already used for `invoice_versions.payload`, `sync_log.payload`, `einvoice_log.payload_json`).
- Migration tool: **Alembic**. Initial migration = `schema_postgres.sql` verbatim (kept in sync by regenerating the baseline, not hand-editing).
- Background jobs: **Celery + Redis** for einvoice submission and sync fan-out (see §7). Latency-sensitive sale paths never touch a worker.

---

## 2. API design conventions

### REST style

- Versioned under `/api/v1`. JSON body/response. UTF-8, `Content-Type: application/json; charset=utf-8`.
- Nouns in kebab-case: `/api/v1/sales/invoices`, `/api/v1/stock/batches`.
- `GET` = read, `POST` = create/action, `PATCH` = partial update, `DELETE` = void/archive (soft) — hard deletes are forbidden on any AUDIT table; legacy "delete" is `status='void'` or `is_active=false`.
- Actions as sub-resources: `POST /sales/invoices/{id}/return`, `POST /sales/invoices/{id}/void`, `POST /stock/batches/{id}/correct`.
- Idempotency: every financial POST accepts `Idempotency-Key` header; a repeat with the same key returns the original result. This is the countermeasure for the retail POS double-tap problem (F9 save).

### Pagination / filtering / ordering

- List endpoints: `limit` (default 25, max 200) + `cursor` (opaque base64 of `(datee, id)` composite key) — **cursor pagination only**, no `offset`, because invoices are inserted mid-list all day.
- Filtering: typed query params (`date_from`, `date_to`, `branch_id`, `party_id`, `drug_id`, `status`). Text search on drug name/barcode uses `ILIKE` for web and the SQLite FTS5 twin for desktop.
- Sorting: explicit `sort` param whitelisted per endpoint; default `datee DESC, id DESC`.
- Date handling: send `datee` as `YYYY-MM-DD`, `datetimee` as ISO-8601 with offset. VB6 serial dates are converted at the API boundary (never exposed).

### Error model

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message_en": "Not Enough Stock",
    "message_ar": "الكمية غير كافية",
    "field": "qty",
    "details": { "drug_id": 123, "available": 5, "requested": 7 }
  }
}
```
- HTTP status: 400 validation, 401 unauthenticated, 403 unauthorized, 404 not found, 409 conflict (invoice-number dup, batch dup, day-close lock), 422 business rule (see code table below), 503 external-system unavailable (only for explicit outbound probes).
- All business rules from business_logic_complete §16.2/§17.2/§18.3 are mapped to stable codes (e.g. `NOT_ENOUGH_STOCK`, `PRODUCT_EXPIRED`, `ABNORMAL_DISCOUNT`, `DRUG_PASSIVE`, `DRUG_PROHIBITED`, `BATCH_DUP_EXPIRE`, `COMPANY_NOT_FOUND`, `NAME_TOO_SHORT`).

### Request/response shape

- Snapshot-style writes: sale-create takes the full invoice (header + lines + payments) in one body; the server owns rounding and derives `subtotal/discount/vat/total` — clients do not send totals.
- Responses for money entities return both `value` (string Decimal) and typed fields — **never raw floats** in the JSON wire format for money. Represent money as strings in JSON to survive JS float corruption; web clients parse to int minor units or use `Decimal`-safe libs.
- Locale/RTL: every list/detail response carries `name_ar`/`name_en` where the entity has both (drugs, accounts, parties). Reports accept `Accept-Language`.

---

## 3. Auth & RBAC

### Legacy model to preserve (business_logic_complete §21; feature_users_permissions_menus)

- 8 legacy user classes seeded as `roles`: Super Admin, Admin, Pharmacy Manager, Technical Support, Operations Account, Management Account, Normal User, Cashier.
- Legacy numeric `صلاحية` level 1–9 maps to a `permissions` seed set (schema_postgres.sql:110 comment); keep the 1–9 numeric level as a coarse "power floor" for backward compatibility of permissions ≥ 7 (balance edits) in addition to fine-grained codes.
- Username = 17-digit numeric ID (legacy login). Mobile `us.phy`/`usersmony.phy` linkage stays via `users.mobile`.

### Token flow

- **JWT access (short, 30 min) + refresh (rotating, 30 days).** Access token carries `sub` (user id), `branch_id` (default branch), `roles`, `perm` (permission codes, compacted as int bitmask for fast middleware checks without a DB hit on every request).
- Login endpoint `/api/v1/auth/login` (username+password → token pair), `/api/v1/auth/refresh`. No session table; revocation via `pass_change_at` claim + audit.
- Branch context: most money endpoints require `branch_id` in path or header `X-Branch-Id`; the RBAC dependency asserts the token's `branch_id` (or an explicit grant) matches. Legacy is per-branch (phar/pharmacyid/mobile); cross-branch access is a permission, not a default.

### Authorization checks

- `require_permission(code)` dependency for area actions (sales.create, sales.void, prices.change, users.add, ...). Permission ≥ 7 numeric floor gates: balance edits, stock correction approval, day-close reopen.
- Stock correction approval requires a manager permission; the actual `stock_batches`/`branch_stock` mutation is applied **only on approval** in the same transaction as `audit_log` (stock_correction_requests:609).
- All auth decisions are also recorded to `audit_log` (action `login`/`login_failed`) — legacy audit culture demands it.

---

## 4. Business-logic engine

### 4.1 Sale (sale → stock → ledger → audit atomically)

1. Validate: stock check (`NOT_ENOUGH_STOCK`), expiry (`PRODUCT_EXPIRED`), price (abnormal discount guard), drug status (passive/prohibited), qty > 0, invoice_no unique (G07: `invoice_no` = internal per-branch source of truth; printed number and ETA B2B number are derived, stored separately).
2. Compute money via `app/core/money.py` (single rounding point). Discount types from §19.2 are represented as structured `disc` fields (percent of total, percent of profit, fixed amount), each resolved before VAT.
3. Pick batches FIFO/expiry (`ix_stock_batches_expiry`); decrement each `stock_batches.qty`, decrement `branch_stock.qty`, record `oldstock` per batch.
4. Write `invoices` + `invoice_lines` + `payment_splits`; enforce `payed + agel = totalvalue`.
5. Post journal: debit/credit entries (customer AR or cash, sales income, VAT payable, COGS) → `journals` + `journal_lines` (balanced invariant) → update `balances` (balance = debit − credit).
6. Insert `audit_log` for each money/stock write. Enqueue `sync_log` row (payload = full snapshot).
7. If party has `agel > 0`, this is a credit sale (أجل) → updates MRD receivable pipeline (feature_receivables_mrd; `parties.receivable_account_id`).
8. Optional: enqueue einvoice job (see §6).
9. Return the invoice + payments + totals (strings for money).

### 4.2 Purchase / purchase return

- Purchase: supplier check (`COMPANY_NOT_FOUND`), batch-uniqueness per (drug, randomid) with `BATCH_DUP_EXPIRE`, no self-purchase. Adds qty to `stock_batches`/`branch_stock` (ModStock side-effects: wzgard/titanksastock/titanstock), posts AP journal + balances, audit.
- Return mirrors the sale-return path (see below) with purchase signs reversed.

### 4.3 Return logic

- Sale return = reversal: re-add to stock, post negative sale journal (or `sale_return` source), update balances, audit. `invoice_versions` records the pre-edit snapshot; returns reference the original invoice (ref_invoice_id on journal).
- `creditdebit` discriminator (reports use it) is resolved: our model uses `journal_source = 'sale_return'/'purchase_return'` — legacy ambiguity (GAPS §4.6) is settled here, not replicated.

### 4.4 Stock correction / count

- Count: `stock_correction_requests` (delta ±, reason, staff requester, manager approval). On approval: adjust `stock_batches` + `branch_stock`, audit with action `count`/`correction`, journal `correction` source. Legacy `CorrectStockForAll`/`ReloadRasidCorrect500` semantics (threshold-based) are re-implemented as a report + approval flow, not hidden magic.

### 4.5 Day / month close (ModEnd, FormEnd)

- Day close (`daily_close`): snapshot drawer start, expected vs counted cash, `difference = counted − expected`, manual cash/card, net cash/network, purchases, expenses, COGS, net profit, VAT columns. `UNIQUE (branch_id, datee)` lock. Writes audit; reopening writes reversal.
- Month close (`monthly_close`): `month_open_balances` seeding from closing balances; prevents further journal posts to closed (branch, month) — the API rejects journal writes where `monthly_close.status='closed'` for that month.
- System date advances (legacy تقفيل اليوم) become a computed "open work period" concept; manual `manual_journal_entries` link to `journals` when posted.

### 4.6 Price change & VAT

- Every price/discount change → `price_change_log` (storediscount 16-col shape) **and** `audit_log`. Price-change jobs (copy to item card, restore pre-invoice price, re-apply VAT) are idempotent endpoints over `invoice_versions` + `price_change_log`.
- **VAT engine (G06, Egypt-first):** per-line `tax_type` carried on the drug master and on each `invoice_lines` row — medicines exempt (0%), medical devices 5%, other goods 14%. Each line resolves its own rate; `vat = Σ round2(line_total × tax_rate)` over taxable lines (exempt lines contribute 0). Egypt retail is VAT-**inclusive**; for taxable lines the net is derived as `total ÷ 1.14`, never double-taxed, gated by `branches.vat_inclusive_prices` (per-branch default `branches.vat_default`, country-dependent — Egypt 14%). Config lives in `app_config` (`country`, `currency`, `vat_default_rate`, `rounding`).

---

## 5. Sync engine (offline-first chain)

Design goal: desktop clients work fully offline on SQLite, then reconcile with the PostgreSQL canonical store (and each other) via last-write-wins.

### Core: `sync_log` outbox (schema_postgres.sql:716-729)

- Every mutating write that must replicate enqueues a `sync_log` row in the same transaction: `entity`, `entity_id`, `action`, `payload` (full JSONB row snapshot), `source_device_id` (branch).
- Syncer reads pending rows ordered by `created_at`, applies to peers, sets `status='applied'` + `synced_at`. Failures → `failed` + retry with backoff.
- **LWW resolution:** per (entity, entity_id), highest `updated_at`/`last_edited_at` wins. Legacy anchor: `usersourceupdate` `SELECT top 3000 WHERE Datee > '<ts>'` incremental pull (strings_readable.txt:5873 → +3 → 5876) and `titanksasales` chain insert loop with GUID `a2a100e1-906b-44df-99c2-6e7c6098421e`. Chain sales summary (`titanksasales` 9-col) is a **projection**, regenerated from canonical `invoices`, not a sync source of truth — this resolves the 9-vs-15 col contradiction (GAPS §2.1).
- `branch_registry` (← titanpharmalist) is the participant list for chain sync; `branch_identities` maps every legacy alias (phar/pharmacyid/mobile) to one `branches.id` so a branch is never duplicated.

### Channels

1. **Desktop↔Cloud:** client `sync` endpoint pulls its own pending rows + pushes local `sync_log`; pushes go through the same idempotency/`synced_at` guards so re-sync is safe.
2. **Drug master / price channel:** `drug_sync_outbox` (← drgserver) carries drug/price/units/vat/barcode to branches; applied to `drugs`/`drug_barcodes` with audit. Price changes carry `price_change_log` + audit.
3. **Cloud export/import archives:** `archive_exports`/`archive_imports` for bulk moves (legacy Titan3-Backup/Archive trees), tracked per-file with `note` recording `OK`/`UNKNOWN_LAYOUT` so unknown legacy formats degrade gracefully.

### Ordering & delivery

- Pull/push loop every 30s while online (Celery beat or embedded timer on desktop). Nothing depends on the loop for correctness — save succeeded already.
- External catalog (`external_drug_catalog`, ← taronlineeg) is legal-safe: **CC0/SFDA data only, never DrugEye** (GAPS §7.8; drug_database_legal.md). The DrugEye feed is ROT-4 text + dead download path — do not resurrect.

---

## 6. E-invoicing (ETA — Egypt-first, research-verified 2026-08-16)

### Policy

- Invoice save never blocks on network. Submission is a background job per `einvoice_log` row (`status` chain: pending → submitted → accepted | rejected | failed, retry with backoff, resubmit on edit via `invoice_versions`).
- `einvoice_counters` (branch_id, kind) keeps the DB-resident counter+hash chain (← oot3/netcounter/counter.txt+hash.txt); updated atomically with each invoice so the QR/hash chain is gapless.
- QR generation is local (payload built from the invoice, hash from the chain); `qr_data`/`qr_hash`/`qr_counter` stored for later generation without re-submission.
- Numbering (G07): the printed number and the ETA B2B number are **derived** from the internal `invoice_no` chain, never independently generated.

### ETA (Egypt) — official standard

- **SDK:** `https://sdk.invoicing.eta.gov.eg` (prod), `https://sdk.preprod.invoicing.eta.gov.eg` (preprod). Build `app/einvoicing/` against the SDK spec (sign off on the serializer before it reaches the sale path). Dead in legacy build — the corpus submission URLs have zero p-code references (`C:\eToolKit\`, `C:\eta-qr\` are dead strings, EGYPT_ETA_DECOMPILED §4); we implement it fresh.
- **Document types:** Invoice v1.0 — JSON or XML; eReceipt v1.2 — **JSON only** (B2C; B2B e-invoice under Ministerial Decision 188/2020).
- **Pre-clearance model:** submit → ETA validates → returns **UUID + hash**; real-time at point of issuance. `einvoice_log` stores the returned ETA UUID + hash for audit/QR.
- **Signing — CAdES-BES per ITIDA spec:** canonicalize the document (ETA serialization algorithm) → SHA-256 → RSA `sha256WithRSAEncryption` → Base64-embedded signature. Signer cert = ETA eSeal X.509 (Class 2+ from an approved provider). Implemented as a pure-Python signer (`app/einvoicing/signer.py`); eSeal private key stored per-branch, loaded only by the worker. No EXE wrapping.
- **Auth:** OAuth session token via ETA identity management; REST; refresh before expiry.
- **Flow:** async submit + poll/notifications (ETA webhook) → mark `einvoice_log` accepted/rejected; rejected → retry with backoff. Egypt VAT 14% comes from `app_config`/`branches.vat_default`, not hardcoded.
- **Required product coding:** GS1 or Egyptian EGS codes (GS1 Egypt partnership with EDA). The drug master carries barcode/GS1/EGS; the serializer maps them into the ETA `items` block.

### ZATCA (Saudi) — reference for a future override only

- The corpus's three "summer" JSON shapes (reports_complete vs api_integration vs zatca_complete) were **ZATCA/Saudi + dead URLs — NOT the ETA target**. Kept as reference notes for a future Saudi override only; not part of the v1 serializer.
- Endpoints (reference only): Production `https://api.zatca.gov.sa`, Preprod `https://api.preprod.zatca.gov.sa`. OAuth2 client-credentials → CSID → signed invoice XML/JSON → submission.

### DTTS (SFDA)

- SOAP endpoints (`PharmacySaleService` etc., api_integration §1.1); GS1 AI parsing for the 6 DTTS fields (AI 01/10/17/21) reimplemented in `app/einvoicing/dtts.py` (GAPS §4.8 note: no AI-element map was published — build the map from GS1 spec and verify against SFDA docs).

---

## 7. Background jobs, testing, API contract generation

### Jobs (Celery)

| Beat task | Interval | Purpose |
|---|---|---|
| `sync.pull_peers` | 30s | LWW sync outbox fan-out |
| `einvoice.submit_pending` | 60s | ETA submit + retry/backoff |
| `einvoice.resubmit_edited` | 5m | Rebuild from `invoice_versions` on edited invoices |
| `stock.shortage_sweep` | 15m | Flag `branch_stock.qty < minimum` → `shortage_flags` (methods manual/half_auto/sales_rate) |
| `report.daily_snapshot` | daily | Pre-compute daily KPIs (net profit, VAT) for reports |
| `archive.import_watch` | 1h | Scan `Archive\Input` → `archive_imports` ETL |
| `db.vacuum_analyze` | nightly | Maintain plan quality on live tables |

### Testing

- **Unit:** `money.py` rounding table-driven (half-up at 2dp/4dp; every line from §16.4 formula); `errors.py` code mapping; permissions floor logic.
- **Integration (DB-level, transactional):** sale atomicity rollback test (force stock failure mid-sale → assert zero side effects); balanced-journal invariant; day-close lock; idempotency-key replay returns original invoice.
- **Contract tests:** OpenAPI generated from Pydantic schemas; a `contract/` fixture dir with locked JSON examples for invoice create/return/void and einvoice payloads (ETA Invoice v1.0 JSON + eReceipt v1.2), validated against ETA preprod.
- **Offline-twin tests:** SQLite vs Postgres produce identical Decimal results for the same sale input (the twin shares `money.py` via a pure-Python module, no DB-specific rounding).
- **Legacy golden files:** fixtures drawn from `titan_extract/` decoded data (e.g. `/tmp/opencode/drugeye.update.titan.decoded.txt` equivalent, price_change_log rows) to regression-test import + report outputs.

### API contract generation

- Pydantic v2 models + `pydantic-settings`; FastAPI emits OpenAPI 3.1. Desktop (Tauri) consumes the same spec via `openapi-typescript`; web (Next.js) uses generated typed client from the same spec. One schema file set under `app/schemas/`, shared by contract tests.
- Versioning: `major.minor` in URL; additive changes are minor; breaking changes (renamed field, changed rounding) are major and get a migration shim.

---

## 8. Open decisions (numbered, with recommendation)

All resolved against `plan/00_decisions_master.md` — see "## Reconciled 2026-08-16" at the top.

1. **O-1 — Client vs server rounding authority.** Legacy clients compute totals; we want one source of truth. **Recommendation:** server owns all rounding via `money.py`; clients send raw qty/price/disc only. Flag for any partner app that must display live totals pre-save (web can compute a *preview* using a mirrored client-side Decimal lib, but the server value always wins on save). → ✅ **CONFIRMED (A05).**
2. **O-2 — Sale→ledger posting granularity.** Post one balanced journal per invoice, or one per payment split? **Recommendation:** one journal per invoice (clean MRD/أجل linkage via `journal_lines.contra_party_id`), payment splits summarized into cash/card/AR lines. Revisit only if AR reporting needs split-level tracing. → ✅ **CONFIRMED (A03).**
3. **O-3 — COGS method.** FIFO by expiry (`ix_stock_batches_expiry`) vs strict FIFO by purchase date vs average. **Recommendation:** expiry-FIFO (matches wzgard batch selection + daily cost_of_sales), with per-batch `cost` stored so COGS is additive, never recomputed from floats. → ✅ **CONFIRMED (A02, configurable).**
4. **O-4 — Chain sales summary (`titanksasales`) as projection vs table.** **Recommendation:** projection (regenerate on demand / cache in a materialized view), never a synced table. Eliminates the 9-vs-15 col conflict and keeps one writer per invoice. → ✅ **CONFIRMED (A06).**
5. **O-5 — Canonical e-invoice payload schema.** Three conflicting shapes in corpus. **Recommendation:** adopt api_integration.md §2.5 full shape, lock with a JSON Schema fixture, verify against preprod before release (see §6). → ✅ **RESOLVED — superseded by the ETA official spec:** Invoice v1.0 JSON (preprod + prod SDK, `sdk.preprod.invoicing.eta.gov.eg`), locked as a fixture during integration testing. The corpus ZATCA shapes are reference-only (future Saudi override).
6. **O-6 — Signing implementation.** **Recommendation:** wrap `saturn.exe`/`toolkit.exe` first (proven, fast), pure-Python BouncyCastle signer as second milestone; both behind one `Signer` interface. → ✅ **RESOLVED — ETA CAdES-BES (ITIDA spec):** canonicalize → SHA-256 → RSA `sha256WithRSAEncryption` → Base64-embedded signature; signer cert = eSeal X.509. Pure-Python signer, **no** EXE wrapping.
7. **O-7 — Day-close reopen policy.** Allow full reopen + reversal, or a post-close adjustment window? **Recommendation:** reopen allowed only by permission ≥ 7 manager, always writes reversal + audit; a closed (branch, date) never silently receives new drawer movements. → ✅ **CONFIRMED (A07).**
8. **O-8 — Offline-twin consistency for balances.** Should SQLite keep full `balances` or compute them on read? **Recommendation:** keep full `balances`/`journal_lines` in the twin (schema_sqlite.sql already has them) — but read-only convenience; any mutation is re-derived from the canonical store, never edited locally. → ✅ **CONFIRMED.**
9. **O-9 — Batch write concurrency.** One `stock_batches` row per movement vs aggregated running quantity. **Recommendation:** one row per movement (wzgard model, audit-friendly), branch_stock as the fast-running total. Locks: `SELECT ... FOR UPDATE` on `branch_stock` + affected `stock_batches` rows during sale. → ✅ **CONFIRMED.**
10. **O-10 — ETA vs ZATCA on same invoice.** A branch could theoretically face both regimes (multi-country chain). **Recommendation:** support both `kind` rows in `einvoice_log` per invoice; counters per (branch, kind); one submission job per kind. Low cost, avoids a rebuild later. → ✅ **RESOLVED — ETA primary; ZATCA kept only as a future override.** `einvoice_log.kind` / `einvoice_counters` stay per (branch, kind) as recommended.

---

### What is deliberately NOT in this backend

- `.phy`/pcode runtime compat (that's the migration track, `legacy_import/`).
- DrugEye ingestion (legal risk; use CC0/SFDA catalog).
- ZATCA (Saudi) submission: out of scope for v1. The corpus ZATCA toolchain/EXEs (`saturn.exe`/`toolkit.exe`) and the three "summer" JSON shapes are reference-only for a future Saudi override (§6).
- Client-side offline state machine (lives in Tauri, uses this API's `sync_log` contract).
- Windows-only features: PowerShell FTP scripts, `Win32_NetworkAdapter` detection, installer/branding.