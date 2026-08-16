# 08 — App Architecture: Core App + Plugin / Add-On Modules

**Role:** APP ARCHITECT — product architecture for PharmaTag فارما تاج (the TITAN.W1 rebuild).
**Stack (fixed):** FastAPI + PostgreSQL backend · Next.js web · Tauri 2 + React + SQLite desktop (offline-first). Monorepo, phased core-first, legacy `.phy` migration in scope.
**Status:** PLANNING. No code written. This document is the build-ready spec for the core-vs-plugin architecture.
**Date:** 2026-08-16.

**Sources read and aligned with:** `plan/01_db_plan.md` (table tiers [C]/[S], money typing, DDL lock), `plan/02_backend_plan.md` (monolith, transactional invariants, event-adjacent jobs, sync/einvoicing), `plan/03_frontend_plan.md` (monorepo, shared `ui`/`core`/`api-client`/`i18n`, shell + module rail, report catalog), `plan/04_features_plan.md` (M01–M23 priorities), `plan/05_slicing_plan.md` (S0–S6), `plan/06_constraints_decisions.md` (C1–C22, D01–D23), `plan/07_migration_plan.md`; `titan_extract/ui_complete.md`, `titan_extract/GAPS_REPORT.md`, `feature_*.md` set, `schema/schema_postgres.sql`, `schema/schema_design.md`.

**Citation caveat honored:** all `strings_*.txt:N` refs elsewhere are `N+3`; irrelevant here (no new field claims).

## Reconciled 2026-08-16

Reconciled against `plan/00_decisions_master.md` (A07–A12, X07/X08). **A08 adopted: schema-per-plugin on PostgreSQL** — core = `public`, each plugin owns a schema registered via `search_path` at runtime; the SQLite offline twin has no plugin schemas → per-plugin ATTACHed SQLite files (`p_` prefix fallback if ATTACH proves problematic). **Q3 resolved:** plugin-owned tables (`einvoice_log`/`einvoice_counters`, report catalog, ledger/month-close, receivables, and the former `[S]` set) ship in their plugin schemas/migrations; core rev 001 ships core truth tables + the plugin host (`app_plugins`, `plugin_dependencies`, `plugin_branch_grants`, `plugin_settings`). **A09** (best-effort default, eta strict), **A10** (pilot = `pharmatag-eta` + `pharmatag-ledger`), **A11** (signed enablement, no DRM, eta bundled regionally), **A12** (bundle-all) confirmed as authored. **X07:** HungerStation SKIPPED. **X08:** insurance DEFERRED to Phase 2+ (skeleton only). Q1–Q10 all resolved — see §7.

---

## 0. Explicit assumptions

1. **State-and-invariant vs surface is the boundary rule.** Anything that must hold for the money truth (C9 branch-scoping, C10–C12 exact money, C13 sync outbox, C14 audit-everything, C15 day-close lock, C16 balanced journal) is **core** and cannot be a plugin. Anything that *presents, manages, extends, or converts that state* is plugin material. A plugin may add tables, screens, jobs, reports — but never weaken a core invariant.
2. **Schema lock holds (01_db_plan §5.1), restated per A08:** core Alembic revision 001 ships the **core truth tables** (`[C]` tier) + the **plugin host** (`app_plugins`, `plugin_dependencies`, `plugin_branch_grants`, `plugin_settings`) in the `public` schema (PG) / the base SQLite twin. The [C] vs [S] tier in 01_db_plan §3 means **behavioral ownership, not DDL timing** — plugin-owned tables (the former `[S]` set + brand-new: patients, prescriptions, installment plans, einvoice state, report catalog, ledger/month-close, receivables) ship in the owning plugin's schema/migration when the plugin installs, not in core rev 001. PostgreSQL: each plugin owns a schema; SQLite offline twin: per-plugin ATTACHed files (`p_` prefix fallback if ATTACH proves problematic).
3. **Plugins are in-process modules of the one FastAPI monolith** (02_backend_plan §1). No microservices, no HTTP-between-plugins. "Distributed plugin" is out of scope for v1.
4. **Money/audit/branch/sync rules apply to plugin tables too.** A plugin table carrying money must use the exact money types, carry `branch_id`, and write `audit_log` through core's `write_mutation` in the same transaction. Enforced by the **plugin schema contract** (§2.2.4) and the twin-parity CI (01_db_plan §4.3).
5. **Single installer ships all plugin code; enablement is data + license, not build config.** Per-branch "which plugins does this branch have" is a DB row, so it is cheap, reversible, and testable. Licensing is **enablement, not DRM** (§4.4).
6. **Primary deployment is Egypt-first, Gulf supported** (06 D1 assumption). `pharmatag-eta` is legally mandatory where deployed, so it is **regionally bundled** in the edition — but it remains a separable module, not welded into core.
7. **The plugin manager itself is core infrastructure**, built in Phase 0 alongside the skeleton (S0.1/S0.2). It is not a plugin of itself.

---

## 1. Definition of core vs plugin for THIS product

### 1.1 The rule (single test)

> A capability is **CORE** if removing it breaks either (a) a money/stock/audit invariant the schema enforces, or (b) the Phase-1 exit criterion "a pharmacist can run a full day — buy, sell, count, close, reconcile". Everything else — every screen, report, job, workflow, or table set that *adds value on top of that truth* — is a **PLUGIN** that can be installed, enabled, disabled, or sold separately.

Two corollaries that resolve the tricky cases in the existing plans:

- **(a) The journal/balances engine is core; the accounting module is a plugin.** Every sale/purchase/return *posts* a balanced journal and updates `balances` in-transaction (02 §4, C16). That posting engine is core — day-close computes ربح اليوم from it. The `pharmatag-ledger` plugin adds the *surfaces* that manage/extend it: chart-of-accounts editing, manual journal entry, trial balance, balance sheet, P&L, month/year close, deep account statements. Same data, owned by core; presented by the plugin.
- **(b) Daily day-close stays core; "account closing" (monthly/year-end) is the plugin.** S1.8 (drawer equation, عجز/زيادة, advance date) is the daily accountability gate — core. تقفيل الشهر, closing entries, archive-at-close are `pharmatag-ledger`. (This resolves the user example "account closing = plugin" against 05's Phase-1 day-close — see **Q1 → A07** in §7.)

### 1.2 Core (irremovable spine — what PharmaTag is without any add-on)

| # | Core capability | Legacy anchors | Core-owned tables | Why it is core |
|---|---|---|---|---|
| C-1 | Auth, users, RBAC, menu gating, audit-on-login | M16 (F16.1, F16.2, F16.5), FFFStartUp | `users`, `roles`, `permissions`, `role_permissions`, `user_roles`, `audit_log` | Gates every other action; C14 |
| C-2 | Drug master + 6-barcode lookup + units + pricing tiers + price change log | M14 (F14.1–F14.4), wzdrugs, tar.phy | `drugs`, `drug_barcodes`, `unit_conversions`, `drug_costs`, `price_change_log` | The POS lookup UX and the sale's pricing basis |
| C-3 | Parties (customer/supplier) with credit-limit check on sale | M15 (F15.1–F15.2), wzcustomers, companies | `parties` | Sale/purchase invariants (AR/AP, credit gate) |
| C-4 | Sales + sales returns + invoice state machine + payment splits | M01, M02 (F01, F02) | `invoices`, `invoice_lines`, `payment_splits` | Primary POS; `payed+agel=totalvalue` CHECK |
| C-5 | Purchases + purchase returns + batch/expiry intake | M03, M04 | `invoices` (kind=purchase), `invoice_lines`, `stock_batches` | Stock comes in here; batch identity |
| C-6 | Stock: batches, branch stock, count + corrections (approval), shortages flagging (intra-branch) | M05, M06 (F05.1–F05.3, F06.1–F06.3) | `stock_batches`, `branch_stock`, `stock_correction_requests`, `shortage_flags`, `needs`, `purchase_orders` | FIFO/expiry selection, COGS, count-and-correct with approval (C19) |
| C-7 | **Money engine:** automatic journal posting + `balances` materialization + drawer + shifts/work-periods | M09 engine, M10 day-close | `accounts`, `journals`, `journal_lines`, `balances`, `drawer_movements`, `daily_close`, `shifts`, `work_periods`, `manual_journal_entries`(store) | Balanced-journal + ربح اليوم + drawer equation (C16, C15) — the sale/purchase side-effect |
| C-8 | **Daily day-close:** drawer count, deficit/surplus, advance date, auto-backup before close | M10 (F10.1–F10.2), M22 basic | `daily_close`, `drawer_movements`, `archive_exports` | S1.8 exit criterion |
| C-9 | VAT calculation (per-line, incl./excl.) + basic VAT output | M18 (F18.1–F18.2 basic) | `app_config`, `branches.vat_default` | Money math is core; full tax reporting is the eta plugin |
| C-10 | Invoice editing (reverse-then-reapply) + versioning | M17 (F17.1–F17.3) | `invoice_versions` | C14 audit continuity |
| C-11 | Audit + sync infrastructure (outbox) | M16.5, M01 chain row | `audit_log`, `sync_log`, `drug_sync_outbox`, `branch_identities` | C13/C14; the seams plugins ride on |
| C-12 | Basic reports (S1.9 set): ربح اليوم, sales/purchases summaries, stock + minimum, drawer handover | RPT subset | read-only over core | The close-day outputs; the full catalog is the reports plugin |
| C-13 | **Plugin host + lifecycle manager** (this plan) | new | `app_plugins`, `plugin_dependencies`, `plugin_branch_grants`, `plugin_settings` | The seam-set core ships from day 1 (§6) |

### 1.3 Plugins (separable add-on modules)

Every plugin has a **slug** (the package name), a stable **id**, a **name (ar/en)**, a **manifest** (§2.1), and an owner table set. Recommended build target for v1 delivery in parentheses.

| Plugin slug | Name (ar / en) | What it adds | Legacy anchors (04_features) | Owns behavior on | New tables (plugin migrations) | Phase |
|---|---|---|---|---|---|---|
| `pharmatag-eta` *(v1)* | الفوترة الإلكترونية / E-invoicing (ETA · ZATCA · DTTS) | Serializer/signer/submission jobs for ETA+ZATCA+DTTS, QR + counter/hash chain use, tax invoice print templates, quarterly/GCC/Egypt VAT reports, e-invoice checker | M18 (F18.3–F18.4), M23 (F23.1–F23.2), ZATCA/ModEta | `einvoice_log`, `einvoice_counters` (state tables in the `eta` schema — ship with the plugin migration, A08/Q3) | `eta_credentials`, `eta_submission_queue` | 4 |
| `pharmatag-chain` *(v1)* | السلسلة والمزامنة / Chain & Cloud Sync | Multi-branch LWW sync consumer, inter-branch transfers, needs→transfer handoff, purchase orders, branch registry, cross-branch stock, main/sub device | M07 (F07.1), M05/M06 chain half, M23 (F23.6) | `transfers`, `transfer_lines`, `needs`, `purchase_orders`, `branch_registry`, `drug_sync_outbox` | `chain_sync_policy`, `transfer_shipments` | 5 |
| `pharmatag-logistics` | التوصيل واللوجستيات / Delivery & Logistics | Delivery/drivers, chain-buy orders (Mohafaza/Markaz), rawakid dead-stock exchange. **HungerStation platform integration SKIPPED (X07)** — legacy delivery/drivers only | M07 (F07.2–F07.4) | `chain_buy_orders`, `dead_stock_exchange` | `drivers`, `deliveries`, `delivery_stops` | 5 |
| `pharmatag-reports` *(v1)* | حزمة التقارير / Reports Pack | The full RPT-xx catalog (S/P/C/SUP/H/ST/D/A/F/DEL/CH/EXP/EI/OP/SP), dashboards/analytics, advanced exports | M20, M22 (F22.1 export) | read-only over core + other plugins' tables | `report_definitions` (catalog rows), `report_schedules` | 3 |
| `pharmatag-ledger` *(v1)* | المحاسبة / Accounting & Ledger | Full COA tree management, manual journal entry (القيود اليدوية), trial balance, balance sheet, P&L, month close (تقفيل الشهر), year-end, account statements, accounting upload/export | M08, M09 (F09.1–F09.4), M10 (F10.3) | `monthly_close`, `month_open_balances`, `accounts` (mgmt), `manual_journal_entries`(workflow) | `accounting_periods`, `closing_entries` | 2 |
| `pharmatag-receivables` | التحصيل والآجل / Receivables & MRD | MRD/installment customers, installment plans, سند قبض/سند صرف settlement vouchers, collections, credit management, statements | M11 (F11.1–F11.3) | `parties` (credit), `balances`, `journal_lines` | `installment_plans`, `installment_payments`, `settlement_vouchers` | 2 |
| `pharmatag-doctors` | الأطباء والوصفات / Doctors & Prescriptions | Patient records, prescription capture from POS, DDI/disease/patient safety checks, Wasfaty. **Insurance (تأمين) copay/coverage DEFERRED to Phase 2+ (X08) — skeleton only** | M13 (F13.1–F13.3) | `drug_interactions` | `patients`, `patient_diseases`, `prescriptions`, `prescription_lines`, `insurance_companies` *(deferred)*, `insurance_contracts` *(deferred)* | 3 |
| `pharmatag-hr` | الموظفين / HR & Shifts | Employee register, salaries v1/v2, attendance (Hodour), shift mgmt UI | M16 (F16.3–F16.4), M19 | `shifts`/`work_periods`(mgmt), `user_drawer_money` | `employees`, `employee_salaries`, `attendance_logs` | 3 |
| `pharmatag-tools` | الأدوات والنسخ / Import-Export & Maintenance | Advanced archive/backup/restore, invoice & DB import/export, Excel import, database cleanup, one-file export | M22 (F22.2–F22.5) | `archive_imports`, `archive_exports` | `cleanup_jobs`, `import_mappings` | 3 |
| `pharmatag-drugdb` | قاعدة بيانات الأدوية / Drug Database | External catalog import (CC0 `karem505`/SFDA/EDA — **never DrugEye**, C1), dedupe/merge, similarity | M14 (F14.5), M23 (F23.3), `external_drug_catalog` | `external_drug_catalog` | `catalog_imports`, `drug_merge_batches` | 3 |
| `pharmatag-offers` | العروض / Promotions & Offers | Promotional offer engine (buy-X-get-Y, sell-X-discount-Y), bonuses | M12 (F12.3), M19 | `invoices`/`invoice_lines` (offer applier hook) | `offers`, `offer_rules`, `offer_applications` | 2 |
| `pharmatag-mobile` | الجوال والكلاود / Mobile & Cloud (L) | Mobile/cloud companion hooks, remote dashboards | M21 (F21.4) | read-mostly | `mobile_sessions`, `cloud_webhooks` | later |

**Deliberately NOT a plugin (never rebuilt):** `remotecontrol`, `nilsen2`, `drugeyedash2`, DrugEye feed, FormExecuteCode/AnyDesk backdoor (C6, 06 §4; ui_complete Tools/Integrations) — a plugin must not be the vehicle for resurrecting vendor RCE/data-selling channels.

### 1.4 Table ownership map (01_db_plan §3 tiers → owner)

| Tier (01 §3) | Meaning | Owned by |
|---|---|---|
| `[C]` core tables | DDL + behavior ship in core rev 001 (in `public` / the base SQLite twin) | core |
| `[S]` supporting tables | **behavior is plugin-owned and the DDL ships in the owning plugin's schema/migration** (A08/Q3 — no longer in core rev 001) | the plugin named in §1.3 column "Owns behavior on" |
| new plugin tables | created only by the plugin's own migration when installed | that plugin |

Examples that would otherwise look contradictory:
- `einvoice_log` / `einvoice_counters` carry the e-invoice state contract (C3, D08: state must be in-DB and auditable) → **the state tables ship in the `eta` schema with the `pharmatag-eta` migration; `pharmatag-eta` owns all behavior** (serializers, signers, jobs, QR templates). Core keeps a thin generic `einvoice` service the plugin extends.
- `transfers` / `needs` / `chain_buy_orders` / `dead_stock_exchange` are `[S]` → no screen or workflow exists until `pharmatag-chain` / `pharmatag-logistics` installs; their DDL ships in the owning plugin's schema/migration (not core rev 001).
- `monthly_close` / `month_open_balances` are `[S]` → ship with `pharmatag-ledger`; behavior only with `pharmatag-ledger`.
- `drug_interactions` is `[S]` → ships with `pharmatag-doctors`.

---

## 2. Backend plugin architecture (FastAPI)

### 2.1 Manifest & registry

A plugin is an installable Python package exposing one entry point. The manifest is a frozen Pydantic model; the registry loads it at startup from the DB (which plugins are installed+enabled) and from the filesystem (what code exists).

```python
# pharmatag/plugins/base.py
class PluginManifest(BaseModel):
    slug: str                       # "pharmatag-eta"
    version: str                    # semver "1.4.0"
    name_ar: str
    name_en: str
    core_requires: str              # ">=0.9.0,<1.0.0"
    sdk_version: str                # the shared plugin-SDK contract version
    depends_on: list[Dependency]    # [Dependency(slug="pharmatag-chain", min="1.0", max="<2.0")]
    tables: list[str]               # tables this plugin owns (new or [S] behavior)
    permissions: list[str]          # new permission codes to seed, e.g. ["einvoice.submit", "einvoice.manage"]
    settings_schema: type[BaseModel]|None
    router_factory: Callable[[PluginContext], APIRouter]
    hooks: dict[str, list[HookSpec]]  # event_name -> [handler, phase, strict]
    jobs: list[JobSpec]             # Celery beat tasks owned by the plugin
    ui: UIManifest                  # frontend contribution (routes/menu/slots/print templates)
    strict_by_default: bool         # in-txn hook failure policy (see §2.4.4)
```

**Registry** (`pharmatag/plugins/registry.py`) is the single mutable object every worker holds. Sequence at startup:

1. Read `app_plugins` (+ `plugin_branch_grants`, `plugin_settings`) from DB.
2. Load each installed plugin package via entry point `pharmatag.plugins`.
3. Validate: core version range, SDK version, `depends_on` graph (topological, cycle-checked), compatibility matrix (§5.4). On failure → `status='error'` + message, plugin not activated.
4. In dependency order: register routers, subscribe hooks, seed permission codes (already migrated), mount Celery jobs, refresh feature-flag cache.
5. Enabled=false or license-expired → skipped entirely (no router, no hooks, no jobs).

Runtime install/enable/disable writes DB **first**, then triggers a registry refresh. In-process refresh is fine for single-worker dev; for multi-worker production the registry is rebuilt at worker startup and a graceful-reload signal (or restart) applies it. **Recommendation: DB is the source of truth; the registry is rebuilt from DB at startup and on a `POST /api/v1/system/plugins/reload`.** (Simplest safe v1: enable/disable is a management operation that also restarts workers.)

Management endpoints (core): `GET/POST /system/plugins`, `POST /system/plugins/{slug}/install`, `POST /system/plugins/{slug}/enable|disable`, `GET /system/plugins/{slug}/status`, `POST /system/plugins/{slug}/upgrade`, `POST /system/plugins/{slug}/purge`. All audited (`audit_log`, action `plugin_install|plugin_enable|...`).

### 2.2 DB extension strategy

#### 2.2.1 Plugin-manager tables (core rev 001 — the plugin host)

These are **core tables** (C-13) — same DDL in PG and SQLite (INTEGER minor-unit rule irrelevant — no money here).

```sql
-- PostgreSQL (core rev 001, schema public); SQLite twin uses TEXT/INTEGER per schema_sqlite.sql conventions
CREATE TABLE app_plugins (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug          VARCHAR(60)  NOT NULL UNIQUE,          -- "pharmatag-eta"
    name_ar       VARCHAR(120) NOT NULL,
    name_en       VARCHAR(120) NOT NULL,
    version       VARCHAR(20)  NOT NULL,                 -- installed version
    core_requires VARCHAR(60)  NOT NULL,                 -- e.g. ">=0.9.0,<1.0.0"
    sdk_version   VARCHAR(20)  NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'installed'
                  CHECK (status IN ('installed','enabled','disabled','error')),
    license_status VARCHAR(20) NOT NULL DEFAULT 'unlicensed'
                  CHECK (license_status IN ('unlicensed','trial','licensed','expired')),
    license_expires_at TIMESTAMPTZ,
    installed_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE plugin_dependencies (
    plugin_id     BIGINT NOT NULL REFERENCES app_plugins(id),
    depends_on    VARCHAR(60) NOT NULL,                  -- slug
    min_version   VARCHAR(20) NOT NULL,
    max_version   VARCHAR(20),
    PRIMARY KEY (plugin_id, depends_on)
);

CREATE TABLE plugin_branch_grants (                       -- per-branch enablement
    plugin_id     BIGINT NOT NULL REFERENCES app_plugins(id),
    branch_id     BIGINT NOT NULL REFERENCES branches(id),
    enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (plugin_id, branch_id)
);

CREATE TABLE plugin_settings (
    branch_id     BIGINT NOT NULL REFERENCES branches(id),
    plugin_id     BIGINT NOT NULL REFERENCES app_plugins(id),
    key           VARCHAR(80) NOT NULL,
    value         JSONB,                                   -- SQLite: TEXT JSON
    encrypted     BOOLEAN NOT NULL DEFAULT FALSE,          -- secrets stored encrypted app-side (integration_config precedent)
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (branch_id, plugin_id, key)
);
```

All four tables are parity-checked by the existing twin-parity CI (01 §4.3). `app_config` gains `plugins_enabled` flag (global kill-switch).

#### 2.2.2 Plugin-owned tables — schema-per-plugin on PostgreSQL (decision, A08)

**Decision (A08, reconciled 2026-08-16): schema-per-plugin on PostgreSQL.** Core owns the `public` schema; every plugin owns a schema named after its slug (e.g. `eta`, `ledger`, `chain`, `reports`). Plugin tables (the former `[S]` set + brand-new) are created in that schema by the plugin's own migration. The registry registers each plugin's schema on the connection's `search_path` at runtime (core `public` is always on the path), so unqualified SQL from a plugin resolves against its own schema while core tables resolve against `public`. Rationale:

- Clean ownership boundary: the schema *is* the namespace — no name-prefixing needed, and cross-plugin name collisions are impossible.
- plugin→core FKs are ordinary FKs across schemas (`eta.einvoice_log.branch_id → public.branches.id`); cross-schema transaction locks behave like same-schema locks in this one-process monolith (02 §1 — hundreds of customers, not millions).
- The SQLite offline twin has **no schemas** → per-plugin ATTACHed SQLite files (one file per plugin, e.g. `ATTACH 'eta.db' AS eta`), preserving twin parity by mapping each PG schema to an attached DB. If ATTACH proves problematic in the Tauri/SQLite runner, fall back to `p_<slug>_` prefixes in the offline twin only (A08).
- Twin-parity CI (01 §4.3) asserts the *set* of plugin tables matches across dialects; the SQLite twin mirrors schema boundaries as attached DBs (or `p_` prefixes).

The pre-A08 alternative (single shared schema + `p_<slug>_` prefixes) is kept only as the SQLite fallback above; it is not the primary model. (Resolved → **Q2 → A08**.)

**Collision rule:** on PG, no plugin may create a table outside its own schema and no plugin may `ALTER` a core (`public`) table; on the SQLite twin, no un-prefixed plugin table and no `ALTER` of core tables. The plugin schema contract (§2.2.4) enforces both in CI.

#### 2.2.3 Migration mechanics on install

- **PostgreSQL (Alembic):** each plugin ships Alembic revisions that `CREATE SCHEMA <slug>` (if absent) and create the plugin's tables in that schema (`op.create_table(..., schema='eta')`); `down_revision` is the plugin's declared minimum core revision. On install, Alembic computes a linearization/merge across heads; CI validates there is never more than one head. Convention: revision ids are `p<slug>_<n>` (e.g. `p_eta_001`). Because installs happen at different times, the chain branches at install time and Alembic's merge is recorded — standard multi-branch Alembic, verified per-release by the compatibility CI.
- **SQLite (desktop, sequential runner):** each plugin ships `migrations/<n>_<name>.sql`; the desktop runner applies pending scripts against the plugin's ATTACHed DB at startup (03 §4.1 pattern), versioned per plugin in a `plugin_migrations` table. With the `p_` prefix fallback, scripts target the main twin instead.
- **Transactional:** each plugin migration applies inside one transaction (PG) / one `BEGIN…COMMIT` (SQLite). A failed migration rolls back and leaves `app_plugins.status='installed'` (not enabled) — the plugin never half-exists.
- Money/branch/audit rules are checked by the contract test against every plugin migration.

#### 2.2.4 Plugin schema contract (CI-enforced)

A pytest suite (mirrored for the twin) asserts, for every table a plugin owns or behaviorally uses:

1. `branch_id` present on any table that stores money/stock/ledger (C9).
2. Money columns use the exact types (PG `NUMERIC(18,2|18,4|5,2)`; SQLite INTEGER minor units) — never REAL/float (C10).
3. Every money/stock write path calls core `write_mutation(...)` → audit_log row in same txn (C14). Test: for each plugin write, exactly one audit_log row.
4. Chain-relevant plugin writes enqueue `sync_log` through the core outbox service (C13) — plugins don't write the outbox directly.
5. No core (`public`) table DDL modification; on PG every plugin table lives in the plugin's own schema; on the SQLite twin, no un-prefixed plugin table.
6. OpenAPI contract: plugin routers conform to the API conventions (error model, money-as-string, pagination) — the contract-test harness mounts every enabled plugin and runs the standard checks.
7. Twin parity for every plugin table (same names/constraints, scale mapping).

### 2.3 API extension

- Each plugin's `router_factory(ctx)` returns an `APIRouter` mounted by the registry at `/api/v1/<namespace>` where namespace defaults to the slug's suffix (e.g. `/api/v1/eta/invoices/{id}/submit`, `/api/v1/chain/transfers`, `/api/v1/reports/rpt/…`). Prefix collisions fail at registry validation.
- **Permissions flow through the core RBAC:** the plugin declares new `permissions.code` rows (migrated + seeded on install); core's `require_permission(code)` dependency works unchanged; `perm` bitmask in the JWT is extended on enable (tokens re-issued or checked against a versioned permission list — use the existing `pass_change_at`-style revocation claim).
- **Response extension:** core never embeds plugin fields in its schemas (keeps the core OpenAPI stable and the twin DTOs unchanged). Plugin data is served by plugin endpoints; the frontend plugin UI fetches it separately and renders it into core-provided *slots* (§3.3). Exception: generic envelopes like `invoice_view` may include an `extensions: {namespace: href}` map of links, which is a core-owned field.
- **Money as strings / error model / cursor pagination** apply to plugin endpoints identically (contract §2.2.4.6) — a plugin that returns `float` money fails CI.

### 2.4 Events / hooks (the heart of the seam)

Core publishes **domain events**; plugins subscribe. This is how ZATCA hooks the sale, how the ledger sees a payment, how the chain sees a transfer.

#### 2.4.1 Two-phase emission

Every event is emitted **twice**, with different guarantees:

| Phase | When | Handler constraints | DB state |
|---|---|---|---|
| `in_txn` | **inside** the core transaction, before commit | must write only DB rows (own tables + `audit_log`/`sync_log`/`einvoice_log`/`balances` via core services); **no I/O, no network, no Celery** | sees uncommitted rows |
| `after_commit` | after the transaction commits (a `session`-level hook / `event_bus.on_commit`) | anything: enqueue Celery, HTTP, logging | sees committed rows |

Core service pattern (from `app/core/events.py`):

```python
ctx = SaleContext(session=db, branch_id=..., user=..., invoice=..., lines=..., payments=...,
                  pending=[])                       # post-commit actions collected
await bus.emit("invoice_saved", ctx, phase="in_txn")        # plugin handlers run here
await db.commit()                                             # core commits
await bus.emit("invoice_saved", ctx, phase="after_commit")   # plugins enqueue jobs
```

`pending` is a per-context list the core fills with default jobs (e.g. `sync.push`); plugins append their own. This keeps a single commit boundary and makes the async surface explicit.

#### 2.4.2 Event catalog (v1)

| Event | Phases | Core emits from | Typical subscribers |
|---|---|---|---|
| `invoice_saved` | in_txn, after_commit | S1.3 sale, S1.4 purchase, returns | eta (einvoice_log+counters, submit job), ledger (posting is already core; plugin may refine), chain (sync row), doctors (attach prescription), reports (KPI), offers (apply offer lines before commit — use `invoice_draft_finalized` instead) |
| `invoice_draft_finalized` | in_txn | POS just before totals/lines are locked | offers (line-level discounts), eta (checking eligibility) |
| `invoice_voided` | in_txn, after_commit | void/cancel | eta (cancel einvoice), chain (reverse sync), ledger |
| `invoice_edited` | in_txn, after_commit | M17 reverse-then-reapply | eta (resubmit via invoice_versions), chain |
| `payment_received` | in_txn, after_commit | settlement, MRD payment, cash in/out | receivables (installment allocation), ledger, reports |
| `day_closed` | after_commit | S1.8 | reports (snapshot), chain (close propagation), ledger (month-ready), backup |
| `month_closed` / `month_reopened` | in_txn, after_commit | pharmatag-ledger | ledger, reports, chain |
| `stock_corrected` | in_txn | approval apply | chain (stock sync), reports |
| `price_changed` | in_txn | drug pricing | chain (drug channel), reports |
| `data_synced` | after_commit | sync engine | chain (post-sync reconciliation), reports |
| `plugin_installed` / `plugin_enabled` / `plugin_disabled` | after_commit | plugin manager | audit tooling, notifications |

Event names are **core-owned constants** (`app/core/events.py`), versioned as part of the SDK contract (an event name is a stable API — plugins pin `sdk_version`).

#### 2.4.3 Ordering & idempotency

- Handlers for one event run in **plugin dependency order** (topological; e.g. chain before logistics, core before any plugin).
- `in_txn` handlers run exactly once per emission because they are inside the same transaction as the document — a rolled-back sale rolls back its plugin rows too (no orphan einvoice_log).
- `after_commit` handlers **must be idempotent**: the job queue uses `Idempotency-Key` semantics (02 §2) and per-plugin job-status rows (in the plugin schema on PG; `p_<slug>_*_job` tables in the SQLite twin) so retries/worker restarts never double-submit. E.g. eta submission is a Celery task keyed on `(branch_id, kind, invoice_id, counter)`.

#### 2.4.4 Failure modes (strict vs best-effort) — how atomicity stays intact

Each in-txn handler is declared **strict** or **best-effort** (default from `strict_by_default`, overridable per handler):

- **Strict (e.g. eta counter/hash chain):** the handler's exception aborts the whole core transaction → the sale fails, nothing committed. Correct for mandatory e-invoicing: an invoice that cannot obtain its einvoice counter/hash must not exist. This is exactly C3 ("counters updated atomically with each invoice").
- **Best-effort (e.g. reports KPI, offers, analytics):** the exception is caught, logged, the plugin records its own error state (e.g. `einvoice_log.status='failed'` for the resubmit queue, or an `audit_log` row), and the core transaction commits normally. The product degrades: core remains fully correct; the plugin is degraded and self-heals via its retry job.

**Net answer to "does core atomicity still hold when a plugin is installed":** yes — the *document's* transaction is extended by plugin `in_txn` handlers that write plugin rows through core services, and anything the plugin can't safely do in-txn (network, signing, third-party calls) is deferred to `after_commit`/Celery with idempotent keys. Core never waits on a plugin, and a plugin never holds the commit hostage except where the plugin itself declares strictness (mandatory legal state).

### 2.5 Concrete walkthrough — sale with `pharmatag-eta` and `pharmatag-ledger` installed

```
POST /api/v1/sales/invoices
 1. core sale service validates (stock/expiry/price/credit gates)             [core]
 2. core computes money via money.py (single rounding point)                  [core]
 3. invoice_draft_finalized (in_txn)  → offers hook adjusts lines              [plugin]
 4. core stages invoices + invoice_lines + payment_splits                     [core]
 5. core posts journal + updates balances (balanced-journal assert)           [core]
 6. invoice_saved (in_txn):
      eta.strict   → insert einvoice_log(kind, status='pending') + atomically
                     increment einvoice_counters + compute hash/QR            [plugin, in txn]
      ledger       → (no-op in v1; posting already done by core engine)        [plugin]
      chain        → enqueue sync_log row (payload = snapshot)                 [core service]
 7. core writes audit_log rows (write_mutation) + commits                     [core]
 8. invoice_saved (after_commit):
      eta          → enqueue Celery submit_pending (idempotent key)            [plugin]
      chain        → sync worker pushes outbox                                  [core]
 9. return invoice; UI renders; eta plugin UI slot shows QR + status            [plugin UI]
```

If step 6-eta raises (counter conflict), the sale rolls back entirely (strict) — nothing on disk, no half-invoice, no orphan einvoice state. If the network dies at step 8, the invoice is saved, `einvoice_log.status='pending'`, and the retry job submits later — the legacy "save never blocks on network" rule (02 §6) is preserved.

### 2.6 Settings, feature flags, licensing

- **Plugin settings** → `plugin_settings` (per branch, JSONB, encrypted flag for secrets — ZATCA CSID, ETA tokens, FTP creds; precedent: `integration_config` "secrets encrypted at app layer", 01 §3.8).
- **Core feature flags** stay in `app_config` (e.g. `day_close_requires_1pm`, `vat_inclusive_prices`, `plugins_enabled`) — plugins read the same config service, never hardcode.
- **License model (no DRM):** `app_plugins.license_status` + `license_expires_at`; a small core `LicenseService` validates a signed license string (public-key verify — cheap, not obfuscation) before enabling. Licensed feature = enabled rows; expired/trial → soft-disable with a visible notice and a grace window. **Explicitly non-goal:** code-level protection of the Python package (worthless server-side) or disabling core. (Resolved → **Q6 → A11**: signed enablement, no DRM; eta bundled regionally.)

---

## 3. Frontend plugin architecture (Next.js web + Tauri desktop)

### 3.1 Shared plugin SDK

Both apps consume plugins through one contract package, **`packages/plugin-sdk`** (03 monorepo). It owns:

- Typed `PluginManifest` (mirrors backend `UIManifest`) — Zod-validated so a malformed plugin fails fast on both web and desktop.
- `definePlugin(manifest)` — the single export every plugin's `src/index.ts` calls.
- React contexts: `PluginHostProvider`, `usePluginHost()` (installed/enabled list, license state), `usePermission(code)`, `useRepos()` (core repos; 03 §1.4), and slot-rendering helpers (`PluginSlot`).
- Contract types shared with the backend OpenAPI for plugin namespaces (money-as-string, error model).

Dependency rule (03 §1.2): `packages/ui` never imports a plugin; plugins may import `ui`, `core`, `api-client`, `i18n`, `plugin-sdk`. The shell (`apps/web`, `apps/desktop`) imports the plugin host, which imports installed plugins **lazily**.

### 3.2 Loading model — bundle-all + runtime gate (decision)

**Recommendation: ship all plugin frontends in the bundle; activation is runtime + license, not build config.** Each plugin's routes/menus are lazy chunks (`React.lazy` / Next `dynamic`), so a disabled plugin contributes zero nav, zero routes, zero jobs — but its code exists locally.

- **Why not true runtime remote-loading (import maps / module federation)?** The desktop is offline-first — remote plugin fetching breaks the core C8 promise; and the monorepo already compiles all code. Dynamic remote-loading is a non-goal for v1. (Resolved → **Q9 → A12**: bundle-all + runtime gate.)
- **Desktop offline:** enabled-plugin list is cached in local `app_config`/`app_plugins` (SQLite twin); the host renders enabled plugins even fully offline; license cached with grace window.

### 3.3 Menu, route, and slot registration

The core shell (03 §3.1 module rail + workspace tabs) is rebuilt to render from a **merged nav model**: core sections + enabled plugins' sections. Each plugin manifest declares:

```ts
ui: {
  routes: [ { path: "/p/eta", lazy: () => import("./routes/Overview"), label_ar: "الفوترة الإلكترونية", icon: "receipt" },
            { path: "/p/eta/invoice/:id", ... } ],
  menu: [ { id: "eta", parent: "settings", label_ar: "الفوترة الإلكترونية", route: "/p/eta" } ],
  slots: {
    "pos.invoiceExtras":   () => import("./slots/PosEinvoicePanel"),   // QR + status inside POS
    "pos.actions":         () => import("./slots/AttachPrescription"), // doctors
    "dashboard.widgets":   () => import("./slots/ChainSyncCard"),      // chain
    "report.catalog":      () => import("./slots/ReportCatalogRows"),  // reports pack
    "settings.integrations": () => import("./slots/EtaSettings"),
    "print.templates":     () => import("./slots/TaxInvoiceTemplates"),
  },
  permissions: ["einvoice.submit", "einvoice.manage"],
}
```

**Slots are the composition seam** — fixed, core-owned insertion points in core screens:

| Slot | In core screen | Rendered by |
|---|---|---|
| `pos.invoiceExtras` | POS totals strip / right panel | eta (QR, submit status, "resubmit"), doctors ("attach prescription") |
| `pos.actions` | POS action bar | doctors, offers (offer lines) |
| `purchase.batchExtras` | purchase batch/expiry picker | chain (chain-buy), drugdb (catalog match) |
| `dashboard.widgets` | dashboard grid | chain (sync state), reports (KPI cards), eta (failed submissions) |
| `report.catalog` | `/reports` hub (03 §2.10 generic report engine) | reports pack (adds RPT rows), eta (VAT reports), ledger (accounting reports) |
| `money.actions` | `/money` screens | receivables (settlement vouchers), ledger (month close) |
| `settings.integrations` | `/settings/integrations` hub (03 §2.11) | every integration plugin (eta, chain, wasfaty, drugdb) |
| `print.templates` | `PrintService` template registry (03 §5.5) | eta (tax invoice A5/ضريبية/مبسطة/مرتجع), reports |
| `shell.quicktabs` | dashboard quick-tabs (03 §3.1) | chain (النواقص→transfers), reports |

**POS example end-to-end:** sale saves → core returns invoice → eta plugin UI subscribed to the `invoice_saved` stream (via a lightweight client event mirror of the backend events, or just refetch on status change) renders QR + status in the `pos.invoiceExtras` slot, and its settings live under `settings.integrations`. The core POS screen never imports eta code — the slot renders whatever plugins registered.

### 3.4 Plugin data access (both apps)

- **Web:** plugin repos use `api-client` (typed, plugin namespaces) exactly like core screens.
- **Desktop:** plugins get repos through the same `DataProvider` (03 §1.4). Plugin **mutations still go through core services** (`useRepos().sales.save(...)`, `stock.correct(...)`, core `write_mutation`), so audit + sync_log + twin correctness hold even for plugin-driven writes (e.g. receivables recording a settlement uses the core settlement service; the plugin only adds installment allocation rows). A plugin that bypasses core repos to write money/stock rows fails the contract test (mirrors §2.2.4).
- **Offline:** plugin-owned tables live in per-plugin ATTACHed SQLite files (fallback: `p_<slug>_` prefix on the main twin) with the same migration runner; plugin writes enqueue outbox rows through core so sync covers plugin entities too (chain plugin's `sync_log` consumption is the generic outbox — plugins declare which of their entities replicate).

---

## 4. Packaging & delivery

### 4.1 Monorepo layout

```
pharmatag/
  package.json / pnpm-workspace.yaml / turbo.json / docker-compose.yml
  apps/
    web/            # Next.js 14 App Router (03 §1.1)
    desktop/        # Tauri 2 + React + Vite, offline SQLite
  packages/
    ui/  core/  api-client/  i18n/  config/        # shared (03 §1.1)
    plugin-sdk/                                     # NEW — plugin contract (§3.1)
  server/
    app/            # FastAPI core: auth, drugs, parties, stock, sales, purchases,
                    #   money, sync, einvoice(core state svc), config, plugins/
    alembic/        # core revisions 001 (schema + plugin host), 002 (seeds)
    pyproject.toml  # core version, e.g. 0.9.x
  plugins/
    pharmatag-eta/    { pyproject.toml, alembic/p_eta_*.py, app/, src/(TS frontend),
                        manifest/plugin.json, migrations/(sqlite), tests/, README.md }
    pharmatag-chain/  ...
    pharmatag-reports/ ... pharmatag-ledger/ ... pharmatag-receivables/ ...
    pharmatag-doctors/ ... pharmatag-hr/ ... pharmatag-tools/ ... pharmatag-drugdb/ ...
    pharmatag-offers/ ... pharmatag-logistics/ ... pharmatag-mobile/ ...
  compat/
    compatibility.json   # core version ↔ plugin/SDK version matrix (CI-validated)
```

Each plugin is a self-contained workspace package: Python package (backend), TS package (frontend), its migrations, manifest, and tests. The pnpm workspace links plugin TS; the Python env installs plugin packages from the monorepo (`pip install -e ./plugins/pharmatag-eta`).

### 4.2 Versioning & dependency model

- **Core:** semantic versioning; API minor = additive, major = breaking (02 §8). Core version is the compatibility anchor.
- **Plugins:** semver; manifest `core_requires`, `sdk_version`, `depends_on[]` with min/max ranges. Resolution is strict-but-explicit: an incompatible combination **blocks install** with a clear Arabic/English message (never a silent half-install). (Resolved → **Q10 confirmed**: strict block; the CI-verified matrix keeps blocks rare.)
- **SDK contract:** `plugin-sdk` (TS) + `app/core/events.py` + backend manifest model share one version — a plugin's `sdk_version` must match the core's supported SDK range. This single number gates both sides.

### 4.3 Per-branch installability

- "Which plugins a branch has" = rows in `app_plugins` (global, per deployment/DB) + `plugin_branch_grants` (per-branch on/off). Enabled globally with a branch override for chain main/sub device semantics.
- A fresh deployment's installer applies core migrations (rev 001 includes the plugin host) and can pre-enable a bundle (e.g. `--bundle egypt-edition` = core + eta + ledger + receivables + reports + tools + drugdb). Bundles are named sets, not special code.
- Desktop offline: enabled set is replicated to the twin at sync; the desktop host honors it (a branch disabled for chain won't show chain UI even offline).

### 4.4 Licensing / sell-separately implications

- **Core is the free base**; plugins are the sellable SKUs. Pricing/bundling is a business decision, but the architecture supports: per-plugin SKU, regional editions (Egypt/KSA bundle the legally-required `pharmatag-eta`), trial flags, and per-branch grants for chain deployments.
- **No DRM** (§2.6). Trust boundary = the deployment owner; the license is a signed enablement, not code hardening.
- One **product consequence to flag:** `pharmatag-eta` is mandatory by law in the target markets, so "sell separately" is marketing fiction there — bundle it into the edition and sell on the rest. Document this in pricing, not in code.

---

## 5. Lifecycle & governance

### 5.1 Install

1. Upload/register package → dependency + compatibility check (§4.2) → fail with message if unsatisfied.
2. Run plugin migrations (PG: Alembic merge; SQLite: sequential runner) in one transaction; failure → rollback, `status='installed'`, no activation.
3. Seed permission codes, seed `plugin_settings` defaults from manifest, write `app_plugins` row.
4. `audit_log` row (`action='plugin_install'`). Status remains `installed` (not `enabled`) until the operator enables.

### 5.2 Enable / disable (safe while running)

- **Enable:** DB status → `enabled`; registry refresh (workers restart in prod); routes/hooks/jobs activate; token permission lists extended; `audit_log`.
- **Disable (the important one):** DB status → `disabled` **first** → registry stops mounting the router, unsubscribes hooks, and Celery jobs check `enabled` before running (no job runs while disabled) → UI hides menus/routes/slots (frontend host reads the same status) → permissions revoked → `audit_log`. **Data is retained**; no `DROP`. In-flight `after_commit` jobs already queued finish or are marked `skipped` by the enabled-check. Disabling is always safe because no plugin code runs without its enabled bit.

### 5.3 Upgrade / downgrade

- **Upgrade:** compatibility check → apply delta migrations (transactional) → run plugin-owned data backfill job (e.g. eta re-hash on a rule change) → bump `app_plugins.version` → audit. Old rows are never rewritten silently; `einvoice_log`/`invoice_versions` precedent: preserve history, derive new behavior forward.
- **Downgrade:** **default = soft-disable + version pin, not DDL downgrade.** Money/audit-adjacent plugin tables are never dropped on downgrade (C14/C20 culture: data is truth). A hard "purge" (`DROP SCHEMA <slug> CASCADE` on PG; `DROP p_<slug>_*` on the SQLite twin) is a separate, explicit, backup-first operation with typed confirmation — and is refused if rows reference core documents. (Resolved → **Q8 confirmed**: soft-disable + version pin is the policy.)

### 5.4 Compatibility matrix

`compat/compatibility.json` — generated and verified in CI: for every released core version, the set of plugin versions + SDK versions that were tested together (the CI matrix installs the combination, runs contract tests + a smoke sale with every enabled plugin, asserts parity). Runtime install checks against the matrix and blocks mismatches. The matrix is shipped with core and fetched by the installer.

### 5.5 Auditing & observability

Every lifecycle action is an `audit_log` row; every plugin job failure writes its own status row; a `POST /system/plugins/status` returns per-plugin `{version, status, license, migrations: applied/pending, last_job_error}` for support.

---

## 6. Impact on the slicing plan (05) — core vs plugin, and the day-1 seams

### 6.1 What changes

| 05 slice | Now | Because |
|---|---|---|
| Phase 0 (S0.1, S0.2) | **Add seam work:** plugin-manager tables + registry + backend event bus (S0.1); frontend plugin host + nav-merge + slots (S0.2); `plugin-sdk` package | The seams must exist before the first money slice so plugins are never retrofitted |
| Phase 1 S1.1–S1.8 | **All core** (unchanged) | Money/stock/close invariants are core by definition (§1.1) |
| S1.9 basic reports | core | day-close outputs |
| Phase 2: S2.1–S2.7 (COA, manual journal, statements, MRD, trial balance, month close, opening balances) | **Becomes plugin `pharmatag-ledger` + `pharmatag-receivables`** (S2.4 MRD → receivables; S2.1/2.2/2.5/2.6 → ledger). The posting *engine* stays core (it already exists from S1.3); only the surfaces move | State/invariant vs surface rule |
| Phase 3: full report catalog | **Becomes `pharmatag-reports`**; S3.1 report *framework* (catalog-driven generic ReportView) stays core as the seam | catalog registry is the seam |
| Phase 4: e-invoicing | **Becomes `pharmatag-eta`**; S4.1's `einvoice_log`/`einvoice_counters` ship in the `eta` schema with the plugin migration (A08/Q3); serializer/signer/jobs/UI are the plugin | e-invoice state is in-DB + auditable (C3); the tables live with the plugin |
| Phase 5: chain | **Becomes `pharmatag-chain` (+ `pharmatag-logistics`)**; `sync_log` outbox stays core; transfers/needs tables ship in the chain plugin's schema/migration | outbox is the seam; chain tables are [S] (A08) |
| Phase 6: migration | core (unchanged) — the ETL imports into core + plugin tables; plugin-owned tables that don't exist yet import into staging | 07 §5.1 order intact |

Phase-gate impact is **schedule-neutral**: the same build order, but Phase 1 now *also* proves the seams by shipping zero plugins and one event subscriber that is exercised by the S1.3 integration tests (a test-only "probe" plugin that asserts it sees `invoice_saved` in-txn). That single test is the cheapest insurance that ZATCA can hook the sale later.

### 6.2 The plugin-ready seams the core must expose from day 1

These are deliberate seams — build them in Phase 0/1, not as an afterthought:

1. **`app/core/events.py` — the two-phase domain event bus** (`in_txn` / `after_commit`, `SaleContext`, strict/best-effort). First consumer: S1.3 sale. **← the #1 seam.**
2. **`app/plugins/` — manifest + registry + lifecycle manager** + `app_plugins`/`plugin_dependencies`/`plugin_branch_grants`/`plugin_settings` tables (core rev 001). **← the #2 seam.**
3. **Frontend plugin host + nav-merge + slot registry** (`PluginHostProvider`, merged nav model, `PluginSlot`, `definePlugin` in `packages/plugin-sdk`), exercised by the shell in S0.2. **← the #3 seam.**
4. **Extensible permissions:** `permissions` seeded + plugin codes added by migration; `require_permission(code)` already code-driven — no RBAC change needed when a plugin adds a code.
5. **Generic report catalog:** S3.1's `/reports/[slug]` engine reads a catalog registry; plugins append catalog rows (`report.catalog` slot).
6. **Generic sync outbox service:** `sync_log` enqueue goes through one service; plugins declare their entities replicate — the outbox doesn't hardcode entity lists (02 §5 already treats entities generically; formalize as a seam).
7. **Job/worker registration:** a Celery beat registry plugins append to (02 §7), so plugins add jobs without editing core task files.
8. **Core money/audit services as the only write path:** `money.py`, `write_mutation`, journal/balances engine are public core services plugins call — enforced by the contract test (§2.2.4).

**The three most important (the ones you cannot retrofit cheaply):** **(1) the two-phase event bus**, **(2) the plugin manifest/registry + lifecycle tables**, **(3) the frontend plugin host + slot model.** Everything else is a smaller seam that mostly already exists as a clean service boundary in 02/03.

---

## 7. Open decisions → resolved (Q1–Q10, per 00_decisions_master)

All ten questions are resolved against the master decision log (2026-08-16); the original recommendation text is kept for traceability.

1. **Confirm the boundary rule and the day-close split.** Is "daily day-close stays core while monthly/year-end close is `pharmatag-ledger`" acceptable, or must تقفيل اليوم itself be a sellable module? **Recommendation:** day-close is core (it is the Phase-1 accountability gate and S1.8 exit criterion); monthly/year-end close is the plugin. ✅ **RESOLVED → A07** (day-close core; reopen only manager perm ≥7; monthly/year-end close = `pharmatag-ledger`).
2. **DB extension strategy.** Single shared schema with `p_<slug>_` prefixed plugin tables vs schema-per-plugin. **Recommendation (as locked, A08):** **schema-per-plugin on PostgreSQL** (`public` = core, per-plugin schema via `search_path` at runtime); the SQLite offline twin has no schemas → per-plugin ATTACHed files, `p_` prefix fallback if ATTACH proves problematic. ✅ **RESOLVED → A08** (⚠ deviates from this plan's earlier prefix recommendation).
3. **Keep `einvoice_log`/`einvoice_counters` and all `[S]` tables in core rev 001** vs moving them into plugin migrations. **Recommendation (as locked, A08/Q3):** plugin-owned tables (`einvoice_log`/`einvoice_counters`, report catalog, ledger/month-close, receivables, and the former `[S]` set) move into their plugin schemas/migrations; core rev 001 ships core truth tables + the plugin host. ✅ **RESOLVED → A08/Q3**.
4. **Strictness default for in-txn hooks.** Strict for mandatory-state plugins (eta counters — fail the sale rather than produce an un-hashable invoice) and best-effort for everything else. **Recommendation:** adopt `strict_by_default=False`, eta explicitly strict; confirm that a broken eta installation may block a sale (that is the point of strict). ✅ **RESOLVED → A09**.
5. **Plugin delivery model.** Single installer with all plugin code + runtime/license enablement (recommended) vs per-branch trimmed builds. **Recommendation:** single installer, enablement is data + license. ✅ **RESOLVED → A11**.
6. **Licensing depth.** Signed-enablement license, no DRM (recommended) vs full key-management/crypto protection. And: do legally-mandatory plugins (eta) get bundled into regional editions and sold as part of the base? **Recommendation:** signed enablement, no DRM; bundle eta regionally. ✅ **RESOLVED → A11**.
7. **First real plugins to build (to prove the seams end-to-end).** Recommend `pharmatag-eta` (legally required, exercises the in-txn strict hook + after-commit async + slot UI) and `pharmatag-ledger` (exercises surface-only plugin). Confirm these two as the pilot plugins. ✅ **RESOLVED → A10** (pilot = `pharmatag-eta` + `pharmatag-ledger`).
8. **Downgrade/purge policy.** Soft-disable + version pin for downgrades; purge is explicit + backup-first and refused for data referencing core documents. Confirm this is acceptable vs hard rollback on a failed upgrade. ✅ **RESOLVED** (accepted under the A03–A06/A11–A12 default-acceptance; §5.3 stands as the policy).
9. **Frontend loading model.** Bundle-all + runtime gate (recommended — offline-first) vs true runtime remote-loading (import maps / module federation). Confirm no runtime plugin download requirement. ✅ **RESOLVED → A12** (bundle-all; no remote module loading).
10. **Compatibility strictness.** Block install on any core/plugin/SDK mismatch (recommended) vs warn-and-run with a degraded flag. **Recommendation:** strict block; the matrix is CI-verified so blocks should be rare. ✅ **RESOLVED** (strict block accepted under the default-acceptance).

---

## Bottom line (concise)

- **Core-vs-plugin split:** Core = the money/stock/audit **truth and its daily operation** — auth/RBAC, drug master, parties, sales+returns, purchases+returns, stock/count/shortages, the automatic journal→balances→drawer engine, daily day-close, VAT calc, invoice editing+audit, the sync outbox, the basic day-close reports, and the plugin host itself. Everything *presenting or extending* that truth ships as a plugin: `pharmatag-eta`, `pharmatag-chain`, `pharmatag-logistics`, `pharmatag-reports`, `pharmatag-ledger`, `pharmatag-receivables`, `pharmatag-doctors`, `pharmatag-hr`, `pharmatag-tools`, `pharmatag-drugdb`, `pharmatag-offers`, `pharmatag-mobile` (HungerStation out — X07; insurance skeleton-only — X08). Plugin-owned tables (former `[S]` set + new) ship in **their plugin schemas/migrations** (A08); core rev 001 ships core truth tables + the plugin host.
- **The 3 most important plugin seams in the core** (build in Phase 0/1, never retrofit): **(1)** the **two-phase domain event bus** (`in_txn`/`after_commit`, strict/best-effort) that lets ZATCA hook the sale transaction atomically while network work stays async and idempotent; **(2)** the **plugin manifest + registry + lifecycle manager** with `app_plugins`/`plugin_dependencies`/`plugin_branch_grants`/`plugin_settings` tables (core rev 001) and per-plugin schema migrations; **(3)** the **frontend plugin host + merged-nav + slot registry** (`packages/plugin-sdk`, `definePlugin`, `PluginSlot`) so plugins add routes, menus, and in-screen panels (POS e-invoice QR, report catalog rows, settings entries) without core screens importing plugin code.
- **Resolved 2026-08-16:** Q1→A07, Q2→A08, Q3→A08, Q4→A09, Q5→A11, Q6→A11, Q7→A10, Q8/Q10→default-acceptance, Q9→A12. No open plugin decision gates the first code.