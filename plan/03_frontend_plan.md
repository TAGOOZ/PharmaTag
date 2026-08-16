# TITAN.W1 Rebuild — FRONTEND ARCHITECTURE PLAN (03)

**Author role:** Frontend architect
**Targets:** Next.js web client **+** Tauri 2 desktop app (offline-first, SQLite)
**Companions:** `schema/schema_design.md`, `schema/schema_sqlite.sql`, `schema/schema_postgres.sql` (backend canonical = FastAPI + Postgres)
**Primary sources:** `titan_extract/ui_complete.md` (full), `ui_forms.json` (231 unique forms), `ui_strings.json`, `feature_sales_invoices.md`, `feature_purchases.md`, `feature_drug_master_pricing.md`, `feature_stock_counting.md`, `feature_reports_analytics.md`, `feature_account_closing.md`, `zatca_complete.md`, `legacy_import/README.md`, `GAPS_REPORT.md`.
**Citation caveat honored:** string-index citations in the feature docs are off by +3 (GAPS_REPORT §1); I relied on them only for form/object names and Arabic labels, never for line-level facts.

**Scope:** planning only. No code written. Deliverable is this document.

---

## Reconciled 2026-08-16

Synced to `plan/00_decisions_master.md`:

- **A13/A14 — low-spec constraint confirmed:** desktop-first Tauri (native, low RAM); web = React client-rendered (Next.js App Router client-only; Vite SPA swap is cheap since domain lives in shared `core`/`ui` packages); performance budget for POS hardware (code-split routes, small bundle, debounced search, indexed SQLite, avoid heavy deps). See new §1.5.
- **Theme/tokens:** look-and-feel is owned by `plan/09_brand_theme_pharmatag.md` — **light-primary** default (`:root`, `data-theme="dark"` = alternate), Thmanyah fonts (P05), bookmarkX token naming (`--background-*`, `--text-*`, `--accent-*`, `--priority-*`, `--space-*`, `--radius-*`, `--shadow-*`, `--transition-*`, `--z-*`). §3.3 fonts updated to reference plan/09.
- **§7 open questions now decided are marked resolved inline** with their decision IDs (#1 pnpm ✓, #2 client-rendered ✓, #3 TS-first ✓, #4 LWW+panel ✓, #5 device-owned ✓, #6 full offline ✓, #7 minimal reports ✓, #8 printer/drawer ✓, #9 ETA not ZATCA ✓, #11 legacy 1-9+RBAC ✓, #12 single drawer ✓, #13 single-first ✓, #14 keyboard-first ✓). #10 (Arabic string curation) stays open — content decision, not an architecture gate.

---

## 0. Executive summary — top decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Monorepo (pnpm + Turborepo)** with 3 shared packages (`ui`, `core`, `api-client`) + 2 apps (`web`, `desktop`). | Both apps share the React component library, domain logic, money module, and i18n. Prevents the classic "two diverging UIs" failure. |
| D2 | **The 4 legacy MDI parents (FFFNew/FFFInPut/FFFOutPut/FFFDS) become 4 primary route modules; FFFPharm becomes the app shell.** MDI child windows become routes + a **workspace tab system** for multi-open invoices. | Legacy MDI semantics (several open invoices, simultaneous users) are real requirements (feature_purchases §10.12, feature_sales_invoices §10.11) but must become web-safe tabs, not true MDI. |
| D3 | **Shared domain/repository layer with two implementations** — desktop = SQLite via `tauri-plugin-sql`, web = HTTP API client. Same Zod schemas, same validation, same money module on both. | The offline-first requirement must not fork the business rules. This is the single most important architecture decision. |
| D4 | **Offline sync = outbox + last-write-wins with a visible conflict surface.** Every mutation writes a `sync_log` row atomically in the same SQLite transaction; a worker pushes/pulls; LWW per entity; conflicts surface as a reviewable banner, not silent data loss. | Mirrors the legacy replication exactly (connections_overview: "last-write-wins, no merge") and satisfies the schema's outbox design (§1.4 of schema_design.md). |
| D5 | **Money is handled exclusively by a shared money module**: round-half-up at 2 dp totals / 4 dp unit; desktop converts to SQLite INTEGER minor units (×100 / ×10000 / ×100); web relies on server NUMERIC but the same module does display/input. | The schema mandates exact money (schema_design §1.2). The frontend must never render or compute money as JS `float`. |
| D6 | **Arabic-first RTL as the default; English is a secondary display toggle.** Typed i18n catalog generated from the legacy Arabic strings, not hand-written. | The corpus is 26,970 Arabic strings; the product is Arabic-first (تيتان is Egyptian pharmacy ERP). English exists for training/support. |
| D7 | **Keyboard-first POS preserved**: F9=Save, F12=Unsave, Enter-confirms in search, qty/expiry bar navigation, barcode scanner = HID keyboard input. | These are muscle-memory behaviors of real users (feature_sales_invoices §1.2, idx 4935 `F9=Save , F12 = Unsave`). Do not regress them. |
| D8 | **Low-spec performance budget (A13/A14)**: desktop-first Tauri (native, low RAM); web = React client-rendered, code-split routes, small bundle; debounced search, indexed SQLite, avoid heavy deps. | Target = budget POS hardware; the till must stay instant. Confirmed in 00 A13/A14; detailed in §1.5. |
| D9 | **Theme/tokens follow `plan/09`**: light-primary default, Thmanyah fonts, bookmarkX token naming. | P02/P05 in 00 master; plan/09 is the single source of truth for look-and-feel. |

**Biggest frontend risk:** **offline-first sync**, not the web client. The web client is a plain server-backed CRUD app. The desktop must reproduce the legacy "file-based money truth + LWW replication + day-close locking" semantics — invoice state machine (Saved/Unsave/Copy/transfer states), drawer/ledger integrity, per-branch isolation, and the counter/hash chain for e-invoicing — all across devices that may be offline for weeks. Second-tier risks: RTL grid/print rendering, garbage in the legacy Arabic string pool, cash-drawer/printer control from a webview.

---

## 1. Repo / package architecture

### 1.1 Monorepo layout (pnpm + Turborepo)

```
titan-rebuild/
  pnpm-workspace.yaml
  turbo.json
  package.json
  apps/
    web/            # Next.js 14+ (App Router) web client, server-backed
    desktop/        # Tauri 2 + React 18 + Vite, offline-first SQLite
  packages/
    ui/             # React component library (RTL-first), Tailwind, shadcn-style
    core/           # Domain logic: money, invoice math, stock rules, repos (interfaces + impl), Zod schemas, tafqit
    api-client/     # Typed HTTP client + endpoint contracts (web uses it; desktop uses it for sync)
    i18n/           # Message catalogs, RTL utils, number/date/currency formatting per country
    config/         # Shared TS/Biome/Tailwind presets
```

### 1.2 What each package owns — and the dependency rule

- **`packages/core`** — the only package that may implement business rules. Owns:
  - `money/` — `roundHalfUp(n, dp)`, `toMinorUnits(amount, scale)`, `fromMinorUnits`, safe add/sub/compare, per-line-total formula `round(unit × qty × (1−disc) × (1+vat), 2)`, invoice VAT computation (subtotal → discount → VAT → total, feature_sales_invoices §5).
  - `tafqit/` — Arabic number→words (legacy `ModTafqit`, used on receipts) ported to TS.
  - `repos/` — repository **interfaces** (DrugRepo, InvoiceRepo, StockRepo, PartyRepo, LedgerRepo, DrawerRepo, SyncRepo) + their shared validation via **Zod** schemas mirroring `schema_sqlite.sql` column semantics.
  - `engine/` — pure functions: invoice save/unsave state machine, credit-limit check (feature_sales_invoices §10.9), real-vs-calculated purchase price guard (feature_purchases §10.9), stock decrement eligibility ("Not Enouph Stock"), expiry selection rule ("اختر تاريخ الصلاحية اولا"), drawer math.
  - `sync/` — outbox producer/consumer logic, LWW merge rules, conflict records.
- **`packages/ui`** — presentational only. Receives data via props/hooks; never imports `core` logic. Tailwind design tokens (RTL), typography (Arabic fonts), and the component inventory in §5.
- **`packages/api-client`** — typed fetcher over the FastAPI OpenAPI; DTOs generated from the backend's OpenAPI schema (`openapi-typescript`). Web app uses it directly; desktop uses it ONLY for the sync push/pull endpoints.
- **`packages/i18n`** — typed message keys, `t(key, {lang})`, Arabic primary; date/number/currency formatters driven by `app_config` (`country`, `currency`, `vat_default_rate`).

**Dependency rule (enforced):** `apps/* → packages/*`; `packages/ui → core` is NOT allowed (props in, render out). `api-client` and `core` are peerless (no deps between them). This keeps the desktop's domain logic testable in Node/browser and lets CI run the same unit tests for web and desktop.

### 1.3 Desktop vs web divergence points (explicit)

| Concern | Web (Next.js) | Desktop (Tauri) |
|---|---|---|
| Data source | FastAPI + Postgres via `api-client` | Local SQLite via `tauri-plugin-sql` |
| Mutations | Direct API commit (server transaction) | Local SQLite transaction + `sync_log` outbox row in the same txn |
| Auth | Session/JWT via API | Local user/pass check (schema `users.pass_hash`) + optional remote sync auth |
| Printing | `window.print()` + CSS `@page` (A4/A5/thermal 80mm) + PDF/Excel export | Same CSS print, PLUS Rust-side native printer for cash drawer ESC/POS and label printers |
| Cash drawer | Not supported (browser limitation) — show "open drawer" as printable control code | Rust command sends ESC/POS open-drawer pulse |
| Barcode camera | `@zxing/browser` (mobile web) | HID scanner + camera fallback |
| File import/export | Browser download/upload | Tauri FS dialog + Rust-side bulk insert for `.phy`/Excel |
| Offline | Requires connection for write | Fully functional offline; queue syncs |

The two apps share the same routes, components, and logic; only the **data adapter** differs. Route-level "unavailable offline" guards are handled by the sync status context, not by different pages.

### 1.4 Shared API surface between apps

Define one React **data-access context** (`DataProvider`) in `packages/core/repos/react.tsx` that binds repository interfaces to the active adapter:
- `SqliteDataProvider` (desktop) — instantiates SQLite repos over `tauri-plugin-sql`, exposes online/offline status + pending-sync count.
- `ServerDataProvider` (web) — instantiates API repos over `api-client`.

All components consume `useRepos()` → `{ drugs, invoices, stock, ledger, drawer, sync }`. Switching providers is a bootstrap decision; **no component knows which backend it runs on**.

### 1.5 Low-spec performance budget (A13/A14 — confirmed in 00 master)

The rebuild must not regress the legacy app's tolerance for **budget POS hardware** (the VB6 era ran on 1 GB-RAM machines):

- **Desktop-first:** the Tauri desktop app is the native, low-RAM target (SQLite via `tauri-plugin-sql`, thin Rust shell, domain in `core`); the web app is the lighter client-rendered companion.
- **Web = client-rendered only** (Next.js App Router `'use client'` pages; no SSR/ISR). Since domain logic lives in shared `packages/core` + `packages/ui`, a **Vite SPA swap is cheap** if the Next.js overhead ever matters on low-end hardware.
- **Code-split routes** (dynamic `import()` per route in both apps); lazy-load heavy pieces (TanStack Table, recharts, `@zxing/browser`) only when opened.
- **Small bundle:** no heavy dependency frameworks beyond Radix + Tailwind; tree-shaking enforced; Biome/TS-strict CI gates on bundle size.
- **Debounced search** on every search-as-you-type surface (`DrugSearchCombobox`, party pickers, report filters) — no keystroke-driven queries.
- **Indexed SQLite** on desktop: indexes on the hot paths (drug name/barcode `LIKE`, invoices per `(branch_id, date)`, stock per batch) + WAL mode; all money math in `core/money` (integers, no float) so no post-hoc fix-up pass.

---

## 2. Screen inventory — 237 legacy forms → canonical screens

Consolidation method: group forms by purpose (the legacy app had ~230 form shells but dozens are one-purpose dialogs, report engines, or settings panels). The canonical list is **58 routes + ~18 shared dialogs/components**. Priority legend:
- **P1 = core-first slice** (must ship together with login)
- **P2 = phase 2** (reports/money/employees)
- **P3 = phase 3** (chain/integrations/deferred)

Route prefixes: `/drugs`, `/pos`, `/purchases`, `/stock`, `/money`, `/parties`, `/reports`, `/employees`, `/settings`, `/tools`.

### 2.1 System & Startup (→ 6 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/login` + `/activate` | FFFStartUp (252), FFFGard, FormActivation (23) | Login, day/date guard, activation/license gate | **P1** |
| `/setup` | FormFirstStart (7), FormSelectdataBase (12) | First-run wizard: pharmacy info, DB selection, opening balances | P1 |
| `/` (shell/dashboard) | FFFPharm, FFFMY, FFFIB, FFFDL, FFFDIR, FFFMSGLONG, FormWait, FormNews | Main shell; dashboard widgets (today's sales, shortages, drawer); the 4 legacy quick-tabs (المشتريات/النواقص/السجل/مبيعات اليوم) as widgets | **P1** |
| Day-close flow (part of `/money/day-close`) | FFFDay (18), FFFDay2, FormEnd (13), FFFDayEnd (25) | 1 PM guard, drawer count, advance system date, close shift | P1 |
| `/help` | FFFHelpStart, FFFHELP, FFFHelpNames, FFFHelpNamesLarge | Help | P3 |
| Shared dialogs (not routes) | FFFGenChoose, FFFList (35), FFFInputBoxMulti, FormPictureShow | Generic pickers, list management | P1 (as components) |

### 2.2 Drugs — master catalog (32 → 9 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/drugs` (list + search) | FFFNames (65), FormDrugsList, FormDrugsLists, FormNameLike, FormSimilars, FormLastEdited, FormDrugsLastDate, FormLastDrugUsed | Searchable catalog (name/barcode/generic/company, `*` wildcards); recent/edited views | **P1** |
| `/drugs/[id]` (editor) | FFFNewDrug (19), FFFNewDrugServer (28), FormDrugsDetails (51), FFFDrugNameMaker, FormDrugNameUnify, FormDrugsdataTrue, FormDrugsHelper | Add/edit drug card: AR/EN names, scientific, company, category, units, VAT, margins | **P1** |
| `/drugs/pricing` | FormDrugPrice (18), FFFPriceExtra, FormFixDrugPrice, FormPriceSetting, FormDrugStore | Price setting (public/wholesale/cost), margin rules (profit vs sales system), bulk price fix | P2 |
| `/drugs/barcodes` | FormParCode (14), FormUpdateDrugParcode, FormMoreBarcodes (8), FormBarcodeSettings (13), FormBarcode, FFFParseQR | 6-barcode management, GS1/EAN/QR/DataMatrix scan, barcode label printing config | **P1** (scan) / P2 (labels) |
| `/drugs/expiry` | FormExpiredDrugs (21), FormExpireCorrect (11), FormExpireDetails, FormExpiresControl, FormAutoExpire, FormExForceChanged, FormEditExpDate, FormFixExpDate | Expiry control, expired list, expiry date fix | P2 |
| `/drugs/interactions` | FormDrugDrug (22) | Drug–drug interaction checker | P3 |
| `/drugs/merge` | FormReapetedDrugMerge (10), FormDrugsCompare, FFFDRUGRUN | Dedup/merge repeated names & barcodes (unify) | P3 |
| `/drugs/drugeye` | FormDrugeeyeUpadteFrom, FFFDrugEye (22) | External catalog import — **deferred**, legal caveat (schema_design §4) | P3 |
| `/drugs/movement` | FormDrugFlow (32), FormDrugHistory, FormReadMonthlyData, FormDrugMonthly, FormDrugMoveMonthly, FormDrugStckAtMonths, FormDrugsLastDays | Movement/history/monthly reports | P2 |

### 2.3 Sales (→ 3 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/pos` (sale POS) | FFFOutPut (278 MDI), FFFOUTQuant (20), FormSellTime (9), FFFoutPutVertual, FormSafiarbah**→ money | Full POS: customer (incl. RANDOM CLIENT), barcode/manual/trade-name/invoice# add, qty+expiry bar, price verify, discount, VAT, payment split cash/card/credit, F9/F12, save→auto-print, returns via kind switch | **P1** |
| `/sales/invoices` | FormootThisDay (11), FormOotSum (9), FormReadArcOot (9), FFFOutputTakarir (16) | Today's invoices, sales summary, archived sales | P1 (today) / P2 (archive) |
| `/sales/invoice/[id]` | FormInvoiceTrackEditing (4), FormPrintSales (17) | Invoice view/edit-history, reprint | P2 |
| *(component)* print receipt | FormPrintSales | Receipt/A4/tax-invoice templates, Tafqit line | **P1** |

### 2.4 Purchases (→ 4 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/purchases` (purchase invoice) | FFFInPut (173 MDI), FFFINNquant (75), FFFINNquantEG (47), FormLiveBuyInfo (8), FormInnSetVatAct | Purchase invoice: supplier (or non-supplier/initial-stock), qty/price/disc/VAT/batch/expiry, real-vs-calculated price guard, cash/card/credit, treasury source, F9 | **P1** |
| `/purchases/invoices` | FormInnSum (13), FormReadArcInn (6), FFFInputTakarir, FormInputtakarirSpeed, Forminputtotal | Purchase list/summary, archived purchases | P2 |
| `/purchases/orders` | FormAutoOrder (43), FormOrder, FormOrderList, FormNeedsAll (50), FormNedBirbish (6) | Auto-order, needs→PO, chain buy | P2 |
| `/parties/suppliers` | FFFWaredMonsaref (36) | Supplier/warehouse management: opening dues, unified discount, GLN, bank acct, tax no | **P1** (list) / P2 (advanced fields) |

### 2.5 Stock & Inventory (18 → 8 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/stock` (current + batches) | FFFDS (76 MDI), FormStockNow, FormDolap (12), FormOrood1 | Current stock, batch/expiry view, branch stock | **P1** |
| `/stock/count` | FFFDrugrasidCorrect (28), FormDrugRasidCorrectCalc, FormRasidCorrectCalc | Physical count, corrections (increase/deficit), negative-balance repair, count sheet print, request/approve | **P1** |
| `/stock/needs` | FFFNeed (62), FFFNeedAuto (44), FormNeedsAll (50), FormNeedsDetails, FormNeedEntryShow, FormMinimumControl (23) | Shortages by minimum, manual/half-auto/sales-rate, min stock control | P1 (view) / P2 (auto) |
| `/stock/transfers` | FormMoared (20), FormSilsila (26), FFFSilsilaStock, FormTahwil, FormTahwilList, FormTawsil, Formdeliver | Inter-pharmacy transfers, chain stock, delivery | P2 |
| `/stock/rawakid` | FormRawakid (10) | Dead-stock exchange | P3 |
| `/stock/batches` (dialog) | FFFINNquant/EG batch/expiry picker, FFFOUTQuant | Shared batch/expiry selection dialog for sale/purchase | **P1** (as component) |
| Balance share (dialog) | مشاركة الارصدة (upload/view) | Seed sub-pharmacies from a main pharmacy | P2 |
| Chain stock | FFFSilsilaStock, FormSilsila | Chain pharmacy stock | P3 |

### 2.6 Money, Ledger & Day Close (25 → 11 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/money` (money ops) | FFFMony (13), FormMonyDetails, FormCorrecyMony, FormUsersMony (24) | Money movement, daily cash flow, user money | **P1** (view) / P2 (ops) |
| `/money/day-close` | FFFDayEnd (25), FormEnd (13), FormDailyQuiod (16), FormMonyDetails, FormTaslimReport (7) | Close day: drawer count, aggregation table (idx 9232 columns), diff reconcile, advance date, shift close, handover report | **P1** (core close) |
| `/money/journal` | FormDailyManual (6), FormDailyManual2 (5), FormAccAddQueed (5), FormAccReports (4) | Manual journal entries, accounting reports | P2 |
| `/money/mrd` | FFFMRD (11), FormMRDAgel, FormMrdAmlManual, FormMrdKashf | Installment customers, MRD payments | P2 |
| `/money/discounts` | FormDisList, FormDiscCorrect, FormStoreDiscount (23), FormBonus, FormSetAvoidDis | Discounts, store discounts, bonuses | P2 |
| `/money/balances` | FormRasMal (2), FormSafiarbah, FormMizan, FormMizanCreate (33), FormAccUploader (47), FFFBHisabatTree (18) | Capital, profit analysis, trial balance, accounts tree | P2 |
| `/money/vat` | FormVat (20), FormVat2 (38), FormDariba (5), FormVatfakeInvo (15) | Quarterly/GCC VAT reports, VAT config | P2 |
| `/money/drawer` | FormTaslimReport, FormCorrecyMony | Drawer handover, drawer corrections | P2 |
| `/money/shifts` | FormShiftFawateer (9), FormShiftInput (9) | Shift invoices, shift input | P2 |
| `/money/expenses` | خروج نقدية flows, FormUsersMony | Expense/cash-out reasons | P2 |
| `/money/checks` | شيك flows | Checks | P3 |

### 2.7 Customers & Patients (→ 3 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/parties/customers` | FFFTel (14), FormCoData (8), FFFCoChoose | Customer directory, credit limits, debt | **P1** |
| `/patients` | FormMarid (5), FormMaridData (15), FormMaridFat (4) | Patient records, patient invoices | P3 |
| `/patients/prescriptions` | FormDoctor, FormDoctorFees, FormWasfaty (27) | Prescriptions, Wasfaty integration | P3 |

### 2.8 Employees & Shifts (10 → 4 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/employees` | FFFAML (14), FFFAmil2, FormAmilShow, FormAmilHistory | Employee register | P2 |
| `/employees/salaries` | FormAmilTamin (16), FormAmilTamin2 (10) | Salaries v1/v2 | P3 |
| `/employees/attendance` | FormHodour (16), FormHodour19 (35) | Attendance, login time | P2 |
| `/employees/shifts` | FormShiftFawateer, FormShiftInput | Shift mgmt | P2 |
| `/employees/reports` | FormAmilTakarir (23), FormAmilReportsArchiv (6) | Employee reports | P2 |

### 2.9 Users & Permissions (→ 2 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/settings/users` | FFFUserEdit (18), FFFUserChoose (19), FormUserEhsa (12) | Users, per-user money | P2 |
| `/settings/permissions` | FormMenusPerUser, FormUserMenu, FFFUserMenuList | RBAC matrix (legacy permission ids 1–9) | P2 |

### 2.10 Reports (→ 3 screens + catalog)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/reports` (hub) | FormReportsGeneral (61), FormChart (19), FormPeriodEhsa (9) | 18 report categories, filters, print/export | P1 (subset) / P2 (full) |
| `/reports/history` | FormPharmHistory (17) | Pharmacy history + aggregation lists | P2 |
| Report engine definitions | FFFOutputTakarir, FFFInputTakarir, FormOutPuttakarirSpeed, FormInputtakarirSpeed, FormAmilTakarir | Implemented as a **declarative report-definition registry** (per RPT-xx: source query, filters, template, group-by) not per-form screens | P2 |
| *(component)* report view | FormBest100 (2), FormExpiredDrugs (21), FormDrugMonthly (7), FormGardByRaf (7), FormDailyQuiod (16), FormTaslimReport, FormPrintSales | The ~45 RPT-xx reports from `feature_reports_analytics.md` all render through ONE generic report component (filters → query → grid → template → print/export) | P2 |

**Reports decision:** legacy built one VB6 form per report engine, but `FormReportsGeneral` shows a single parameterized engine covers the majority. We build **one generic report screen** (`/reports/[slug]`) driven by a report catalog JSON. Every RPT-xx (S01–S15, P01–P07, C01–C04, SUP01–02, H01–03, ST01–06, D01–10, A01–06, F01–11, DEL01, CH01, EXP01–02, EI01–02, OP01–05, SP01–04) becomes a catalog entry. This collapses ~18 report forms into ~45 catalog rows.

### 2.11 Settings & Integrations (17+10 → 8 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/settings/pharmacy` | FormPharmacyInfo (14), FormCopyType | Pharmacy info, tax/CR numbers | **P1** |
| `/settings/advanced` | FormAdvanced (33), FormInternet (7), FormNetwasel (2), FormUploadOptions (10), FFFScreens (11), FormStyles (11), FormSounds (22), FFFColors (4), FFFSHAPE (8) | Advanced toggles, network, upload, appearance | P2 |
| `/settings/printers` | FormPrinterSettings (31), FormPrinterSettingFary (28), FffSelectPrinter (2) | Printer-per-purpose, paper sizes, margins, copies, drawer pulse, barcode label size | P2 (needed early for receipt printing) |
| `/settings/barcodes` | FormBarcodeSettings (13) | Barcode label paper/config | P2 |
| `/settings/backup` | FFFbackupAuto (7), FormBackRestore, FormRestore, FormXBackup | Auto/manual backup, restore | P2 |
| `/settings/maintenance` | FFFClean (36), FormUpdator (7), FormReadVer2 (14), FormDeleteOldVersions | Cleanup, updater | P3 |
| `/settings/integrations` (hub) | FormIntegrations (9), FormGovData, FormEcommerce, FormRempteTitan, FormSendChanges, FormSelectdataBase | Integration toggles | P3 |
| `/settings/integrations/zatca` | FormRsdDispatch (16), FormElectroniaChecker (14), ModZatca, ModZatca2Wraber, Modzatcasign | ZATCA e-invoicing: onboard, sign, submit-status, counter/hash | P3 (config only; live submission gated) |
| `/settings/integrations/eta` | FormEtaInfo (9) | Egypt ETA — **dead URLs in this build** (schema_design §1.5): keep generation, no live submit | P3 |
| `/settings/integrations/dtts` | Formdtts (26) | Track & Trace | P3 |
| `/settings/integrations/wasfaty` | FormWasfaty (27) | Prescription system | P3 |
| `/settings/integrations/farynet` | FormFaryNet (8) | Branch sales monitoring | P3 |

### 2.12 Import/Export & Tools (15 → 4 screens)

| New screen / route | Consolidates legacy forms | Purpose | Pri |
|---|---|---|---|
| `/tools/import` | FormImportFat (14), FormImportFromOtherDBI (19), FormImportFormOtherApps (11), FormImportFRomExcell (6) | Invoice/DB/Excel import; `.phy` historical import via `legacy_import` | P2 |
| `/tools/export` | FormExportdataBase (8), FormExportFat, FFFootEx (17) | Excel/PDF/DB export | P2 |
| `/tools/calculator` | FormCalculator (10) | Calculator | P3 |
| **Dropped** | FormExecuteCode (7), FormRemoteControl (10), FormChatAnydesk | Code exec + remote control = vendor RCE channel (schema_design §4 skips `remotecontrol`); **must not be replicated**. AnyDesk chat is out of scope | — |

**Easter eggs** (FFFSODUKU, FFFPiano): optional later; not in the canonical list.

### 2.13 Consolidation stats

- 231 unique legacy forms → **58 routes + ~18 dialogs/components**.
- **P1 (core-first) = 18 routes**: `/login`, `/activate`, `/setup`, `/` (shell), `/drugs`, `/drugs/[id]`, `/drugs/barcodes`, `/pos`, `/sales/invoices` (today), `/purchases`, `/parties/suppliers`, `/parties/customers`, `/stock`, `/stock/count`, `/stock/needs`, `/money` (view), `/money/day-close`, `/settings/pharmacy` + shared dialogs.
- P2 ≈ 20 routes; P3 ≈ 20 routes + dropped.

---

## 3. Navigation & layout model

### 3.1 Legacy MDI pattern → modern mapping

Legacy structure (ui_complete §2): `FFFStartUp → FFFPharm (main shell) → {FFFNew (drugs), FFFInPut (purchases), FFFOutPut (sales), FFFDS (stock), FormMoared, FFFMony, FormReportsGeneral, FormPharmacyInfo…}` — 4 real MDI parents + several "MDI-form" singletons, with child windows living inside a VB MDI client area.

New model:
```
[Login / activate / setup]
        │
[App Shell  =  legacy FFFPharm]
   ├─ App bar: pharmacy name + user + branch + date + sync status + language toggle
   ├─ Module rail (icons + Arabic labels):
   │      الرئيسية (Dashboard)  →  /
   │      الادوية (Drugs)       →  /drugs
   │      مبيعات (Sales/POS)    →  /pos
   │      المشتريات (Purchases) →  /purchases
   │      المخزون (Stock)       →  /stock
   │      المال (Money)         →  /money
   │      التقارير (Reports)    →  /reports
   │      الموظفين (Employees)  →  /employees
   │      الاعدادات (Settings)  →  /settings
   └─ Workspace tab bar (multi-open invoices):
         [فاتورة مبيعات #1042] [فاتورة مشتريات #88] [+]
```

### 3.2 Workspace tabs replace true MDI

Real requirements to preserve:
- **Multiple open sales invoices simultaneously** (feature_sales_invoices §10.11) and **multiple open purchase invoices** (feature_purchases §10.12).
- **Simultaneous users/writers** on separate machines (per-writer attribution on invoice).

Implementation: a `WorkspaceProvider` in `packages/ui` managing a set of open "tabs" — each tab is an invoice workspace instance keyed by `{kind, localId}`. Tabs are route-backed (`/pos?tab=…` deep-linkable, persisted in sessionStorage). Drag-reorder optional; close-guard prompts "فواتير غير محفوظة" (pending unsaved). The 4 legacy quick tabs (المشتريات / النواقص / السجل / مبيعات اليوم) become dashboard widgets with deep-links.

### 3.3 RTL / Arabic-first concerns

- `dir="rtl"` on `<html>` (both apps). All layout primitives use logical properties (`ms-*`/`me-*`/`start`/`end`, not `left`/`right`).
- **Fonts:** owned by `plan/09` (P05) — **Thmanyah family** (UI Sans 300–900, Serif Display headings, Serif Text body; fallback `'Thmanyah', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`), self-hosted in `packages/ui` (no Google Fonts CDN — offline-first desktop). Latin/digits via a mono face (`IBM Plex Mono`).
- **Numerals:** keep Western digits (0-9) for data entry and money (legacy prints Western digits; Arabic-Indic numerals in `Intl` cause data-entry confusion). Use `Intl.NumberFormat('ar-EG'|'ar-SA', {currency})` with `numberingSystem: 'latn'` explicitly forced.
- **Dates:** Gregorian (legacy VB6 serial → ISO-8601 UTC text per schema). Never render the raw serial. `Intl.DateTimeFormat('ar-EG')` for display.
- **Bilingual labels:** every label = Arabic primary + English secondary, per the extracted label pairs (`اسم الصنف` / Item; `الكمية` / Quantity; etc. from ui_forms.json `arabicUIText`). Stored as typed keys in `packages/i18n`; a `<Bilabel ar="…" en="…">` component shows Arabic with English as small muted caption under it (training mode) or via toggle.
- **Text inputs**: `autoComplete` off for drug names; barcode fields force `ltr` direction + monospace + numeric keypad.
- **Grids**: RTL-aware scrollbars, sticky first column on the **right** for RTL (row-number/action column anchored to the inline-end), column headers reorder logically.
- **Charts**: reverse x-axis for RTL where meaningful (money-over-time reads right→left).

### 3.4 Keyboard & scan-first behavior (non-negotiable)

| Key | Action | Source |
|---|---|---|
| F9 | Save invoice | idx 4935 `F9=Save` |
| F12 | Unsave | idx 4935 `F12 = Unsave` |
| Enter | Confirm search/picker; advance to next field in qty bar | legacy navigation |
| ↑ / ↓ | Select batch/expiry in the qty bar | «استخدم اتجاهات لوحة المفاتيح الاعلي والاسفل لاختيار تاريخ الصلاحية» |
| Global `/` | Command palette (search drug/invoice/customer/screen) | new, replaces the 237-form maze |
| Barcode scan | Focused scan field with suffix detection (ENTER/`\t` terminator); GS1 AI parsing (AI01 GTIN, AI10 batch, AI17 expiry, AI21 serial) | ModGS1Reader (§2.8 drug pricing doc) |

---

## 4. Offline-first data layer (Tauri) + web difference

### 4.1 Desktop: SQLite access

- **Bootstrap:** `tauri-plugin-sql` with sqlx; apply `schema/schema_sqlite.sql` at first run (migration #1), then semantic migrations (`migrations/`) for subsequent versions. DB path = app-data dir; **not** browser storage (must survive app restarts and be file-backable, like `Files\DBI`).
- **Money typing:** SQLite stores money as **INTEGER minor units** (schema_design §6): ×100 for totals, ×10000 for unit/qty, ×100 for rates. All conversion happens in `packages/core/money` — repositories read/write minor-unit integers and expose domain objects with decimals.
- **Access pattern:** repositories issue parameterized SQL through the plugin (`PRAGMA foreign_keys=ON`; every multi-table mutation in one `BEGIN…COMMIT`). The Rust side stays thin (bootstrap, migrations, native printer/drawer, file dialogs, bulk `.phy`/Excel import). Domain logic lives in TS and is unit-tested in Node.
- **Low-spec (A13/A14, §1.5):** keep SQLite **indexed** (hot paths — drug name/barcode `LIKE`, invoices per `(branch_id, date)`, stock per batch; WAL mode) and search **debounced** everywhere; no heavy deps in the render path.

### 4.2 The outbox + last-write-wins sync engine

Mirrors `sync_log` / `drug_sync_outbox` in schema_sqlite.sql §18 and schema_design §1.4.

**Write path (desktop):**
1. UI calls repo mutation → `core` engine validates (Zod + business rules).
2. One SQLite transaction writes: domain rows + `audit_log` row (schema_design §1.6 mandates same-txn audit) + `sync_log` row `{branch_id, entity, entity_id, action, payload(JSON), device_seq, created_at, status='pending'}`.
3. `device_seq` = monotonically increasing per-device counter (stored in `app_config`) — gives total order for LWW without wall-clock trust.

**Push:** worker (setInterval + on-network-reconnect via Tauri `online` event) sends `POST /api/sync/push {device_id, since_seq, batch:[…]}`; server applies LWW per entity (compare `updated_at`/`device_seq`), returns per-row `{accepted | superseded | conflict}`; client marks `applied` / `skipped`, writes conflicts to a local `sync_conflicts` table (extension table, or `sync_log` payload) for the UI.

**Pull:** `GET /api/sync/pull?after=<server_watermark>` returns server rows newer than watermark; client applies them to local SQLite, skipping any local row whose `device_seq`/`updated_at` is newer (LWW), else overwriting.

**Conflict surfacing (D4):** LWW is the default (legacy behavior), but the client keeps a **conflict panel** (`/settings/sync` and a banner on the shell): lists entities where local and remote both changed since last sync, showing `my value` vs `their value` with **Keep mine / Keep theirs / Auto (LWW)** — non-destructive default.

**What syncs (ordered):** drug master + price changes (`drug_sync_outbox`), chain stock (`branch_stock`/`titanksastock` equivalent), chain sales (`invoices` kind=sale via silsilaid), transfers/needs, party balances. **What does NOT sync:** local-only drawer/ledger aggregates (day-close rows lock per `(branch_id,date)` in schema) and `einvoice_counters` (per-device counter chain — device-owned).

### 4.3 Web client difference

- Repos bind to `api-client`; mutations are **direct API commits** (server transaction = single source of truth). No outbox, no device_seq, no LWW.
- `DataProvider` reports `online: true, pendingSync: 0, isLocal: false`.
- The shell hides sync-status UI and shows a server connection state instead.
- **Same pages, same components, same money module** — only the adapter differs. This is what makes the risk comparison concrete: the web build is "the easy 30% of the UI," the desktop is where the real complexity lives.

### 4.4 Migration/import relevance for the frontend

`legacy_import` produces JSONL → SQLite directly (README runbook). The desktop app reuses that output: first-run offers "استيراد بيانات قديمة (ملفات .phy)" which runs the import pipeline in-process (Rust bulk load), writing into the same SQLite. Frontend shows an `archive_imports`-style progress screen with per-file `OK/UNKNOWN_LAYOUT` status (graceful degradation contract from schema_design §5).

---

## 5. Component & pattern library

All in `packages/ui`, RTL-first, typed props, no internal business logic (props in / events out). Key inventory:

### 5.1 Shell & navigation
- `AppShell` — app bar, module rail, workspace tab bar, sync-status chip, user menu.
- `WorkspaceTabs` — open-invoice tab manager with unsaved-guard.
- `CommandPalette` — global search (drug/invoice/customer/screen/action), `/` hotkey.
- `Bilabel` / `LanguageToggle` — bilingual labels + en toggle.
- `StatusChip` — invoice states (Saved/Unsaved/Copy/…) with legacy colors.

### 5.2 Data display — grids/tables
- `DataGrid` — built on TanStack Table; virtualized rows (drug catalogs exceed 5k), RTL-aware sticky actions column, column chooser, filter bar, export menu (Excel/PDF/CSV/clipboard per feature_reports_analytics §4.4), totals row, grouped subtotals (report group-by).
- `InlineGridEditor` — inline qty/price/disc/VAT editing with per-cell money inputs; used inside invoice editor.

### 5.3 Invoice entry forms (the FFFMony/FFFOUTQuant family)
- `InvoiceWorkspace` — header bar (invoice no, date, writer, party, branch, kind badge), `InvoiceLinesGrid`, `TotalsStrip`, `PaymentSplitBar`, `SaveBar`.
- `QtyExpiryBar` — the legacy "شريط تحديد الكمية والصلاحية": quantity stepper (large touch buttons), unit toggle (الوحدة الوسطي vs whole packs), expiry picker (batch list, ↑/↓ to select, must choose expiry first — «اختر تاريخ الصلاحية اولا»), shows batch stock.
- `PaymentSplitBar` — cash / card(شبكة) / credit(أجل) amounts; enforces `payed + agel = totalvalue` (schema CHECK); credit requires permission; computes change («ادخل ما دفعه المريض ليتم حساب الباقي»).
- `InvoiceActionsBar` — Save (F9), Unsave (F12), Copy→sale/return, Transfer→purchase/return, Print, Delete-last-only guard («يمكنك فقط حذف اخر عملية ادخال»).
- `PriceGuard` — real vs calculated purchase-price gap warning (feature_purchases §5.1).

### 5.4 Lookup & input primitives
- `DrugSearchCombobox` — debounced search-as-you-type over name (`*` wildcards), generic, company, 6 barcodes; live similar-name hint to avoid duplicates (drug pricing doc §2.1); shows stock + last price + monthly qty.
- `BarcodeScannerField` — scan input (HID), GS1 parser (AI01/10/17/21), duplicate-barcode detection («باركود غير موجود», «باركود دولي مشترك»), camera fallback via `@zxing/browser`.
- `MoneyInput` / `QtyInput` / `PercentInput` — decimal-safe (use `core/money`), numeric pad option for touch, min/max guards, VAT-incl/excl toggle (سعر شامل الضريبة / قبل الضريبة).
- `PartyPicker` — customer/supplier search with debt/dues + credit-limit display; RANDOM CLIENT and special suppliers (غير الموردين، الجرد الاولي، مورد غير معروف).
- `BatchExpiryPicker` — per-drug batch/expiry selection dialog (shared by sale/purchase/count).

### 5.5 Printing (desktop-critical)
- `PrintService` — abstraction over: (a) webview `window.print()` with `@page` CSS (80mm thermal / A4 / A5 / letter), (b) Rust native printer (raw ESC/POS to named printer, cash-drawer pulse `ESC p`, label printers), (c) PDF/Excel/CSV export.
- `InvoiceTemplate` / `ReceiptTemplate` — A4/A5 sales invoice, tax invoice variants (ضريبية/مبسطة/أجلة/مرتجع), سند قبض/سند صرف/سند صرف لمورد, barcode labels (Zebra thermal + A4 6×24 + 3.8×1.2 shelf), بامداد Tafqit line (amount in words).
- `PrinterSettingsPanel` — FormPrinterSettings equivalent: ~30 settings (printer per purpose, paper, margins, copies, auto-print on save, open-drawer on print, barcode sticker dims) persisted to `app_config`.

### 5.6 Dashboards & reporting
- `DashboardGrid` — responsive (mobile-friendly — legacy had a mobile screen), stat cards: today's sales (مبيعات اليوم), shortages (النواقص), drawer position, low-stock, expired soon, recent invoices; the 4 legacy quick tabs as widget cards.
- `ReportView` — the generic report screen (§2.10): filter dialog → query (via repo) → `DataGrid` → template → print/export. Report catalog JSON defines every RPT-xx.
- `ChartCard` — recharts-based, RTL-aware (time series right→left), used for sales volume, profit, stock-at-months.

### 5.7 Feedback & dialogs
- `ConfirmDialog` — Arabic confirm patterns (هل تريد الحذف فعلا؟), destructive-action type-a-number guards (e.g., legacy "write 600" confirmations → replaced by typed confirmation).
- `ToastFeed` — legacy result messages (تم الادخال بنجاح / تم التعديل بنجاح / تم الحفظ بنجاح) reused verbatim from the corpus.
- `SyncConflictPanel` — LWW conflict review UI (§4.2).
- `LongTaskProgress` — replaces FormWait for counts/reports/imports.

---

## 6. Core-first slice — key screens to design first

Design order = dependency order. Each screen has a lead component, a data dependency (repo+Zod), and an acceptance behavior from the legacy doc.

1. **Login `/login` (+ activation gate)** — user + password (schema `users.pass_hash`), day/date banner, branch select, permission-aware nav reveal. Behavior: day-close date guard notice, "can't close today before 1 PM" shown contextually.
2. **App shell `/` dashboard** — module rail, workspace tabs, sync chip, the 4 quick-tab widgets. All other screens nest inside it.
3. **Drug master `/drugs` + `/drugs/[id]`** — the hub (every table references `drugs`). `DrugSearchCombobox`, `DataGrid`, editor with AR/EN names, 6 barcodes, VAT, units, margins, price history. Duplicate-name + duplicate-barcode guards. **Design first because every other screen needs the drug picker.**
4. **POS `/pos`** — `InvoiceWorkspace` + `QtyExpiryBar` + `PaymentSplitBar` + `BarcodeScannerField`; F9/F12; save side-effects (stock decrement, customer debt, drawer, audit) all via `core` engine in one txn; auto-print + drawer pulse (desktop). **Design second — it is the revenue screen and the integration test for the engine.**
5. **Purchase `/purchases`** — mirror of POS with supplier-first rule, real-vs-calculated price guard, batch/expiry entry, treasury source. Validates the same engine in the opposite direction.
6. **Stock count `/stock/count`** — count sheet (system balance vs counted, correction up/down), negative-balance repair, request/approve (schema `stock_correction_requests`), audit. Validate against feature_stock_counting §2.
7. **Balances `/money` + `/money/day-close`** — ledger view, drawer aggregation (idx 9232 column set), drawer count + diff, day close (advance date), handover report. This is the daily-accountability screen that makes the rest trustworthy.
8. **Party pickers** (customers/suppliers minimal) — because both POS and purchase need party selection first.

**Slicing rule:** P1 ships as vertical slices, each ending in "a pharmacist can complete the day": Drug → Purchase → Stock → Sale → Money/close. The invoice engine (`core/engine`) is built once and exercised by sale, purchase, returns, and count.

---

## 7. Open decisions — resolved 2026-08-16 (decision IDs in 00 master; #10 remains a team content choice)

Numbered, each with my recommendation.

1. **Monorepo package manager & toolchain.** Recommend **pnpm + Turborepo**, TypeScript strict, Biome (formatter+linter), Vitest for `core` unit tests, Storybook optional for `ui`. Alternative: npm workspaces + Nx. Confirm pnpm is acceptable in this org. — **✅ RESOLVED → A13** (pnpm + Turborepo, TS strict, Biome, Vitest).

2. **Next.js version / rendering strategy for web.** Recommend **Next.js 14 App Router, client-rendered pages** (this is an internal ERP with session state; SSR adds little). All data via TanStack Query. Confirm we're not doing SSR/ISR. — **✅ RESOLVED → A14** (App Router, client-rendered, no SSR/ISR; Vite SPA swap is cheap per §1.5).

3. **Tauri data-access pattern.** Recommend **`tauri-plugin-sql` (sqlx) with all domain logic in TS**; Rust only for bootstrap/migrations/native printer/drawer/file-import. Alternative: full Rust command layer (more native control, but duplicates domain logic in Rust). **Recommend the TS-first option** for logic reuse. — **✅ RESOLVED → A01** (TS-first via `tauri-plugin-sql`; Rust only for bootstrap/native printer).

4. **Sync conflict policy default.** Legacy is hard LWW. Recommend **LWW auto-resolve + non-destructive conflict panel** (user can review and override later). If the user prefers pure LWW with no UI, that's simpler; recommend keeping the panel for invoices specifically (invoice state + drawer math must not silently fork). — **✅ RESOLVED → G10** (LWW auto-resolve + non-destructive conflict review panel).

5. **Which entities are device-owned (never sync).** Recommend: `einvoice_counters` (ZATCA/ETA counter+hash chain is per-device), local day-close rows (locked per branch+date), `audit_log` (device-scoped). Confirm the server treats chain sales/stock as the only synced payloads for P1. — **✅ RESOLVED → A15 + G10** (per-device e-invoice counter/hash chain; local day-close + audit rows stay device-owned; synced payloads = chain stock/sales).

6. **Offline write admission.** Do we allow writes while offline for everything, or block money/stock writes offline (read-only mode) in P1? Recommend **allow everything offline (true offline-first)** since that's the product's raison d'être, but show a prominent "offline" banner and queue count. If the user prefers safety-first, we can gate mutations. — **✅ RESOLVED → G10** (true offline-first: all writes allowed offline, banner + queue count).

7. **Reports scope in P1.** Recommend P1 ships only: today's sales, shortages, expired drugs, drawer/balances, invoices lists — as catalog rows. Full 45+ RPT catalog in P2. Confirm the RPT priority order. — **✅ RESOLVED → G11** (minimal v1 report set; full RPT catalog later).

8. **Cash drawer & thermal printing.** Desktop can do it (Rust ESC/POS). Web cannot. Recommend: desktop-only drawer pulse + raw thermal; web falls back to CSS `@page: 80mm` PDF/receipt print. Confirm acceptable that the web client can't drive a physical drawer. — **✅ RESOLVED → P09** (desktop ESC/POS + drawer via Rust; web PDF/80mm fallback).

9. **E-invoicing (ZATCA/ETA) live submission.** The corpus shows dead URLs in this build and 3 conflicting JSON shapes. Recommend: **ship ZATCA as generate+QR+log locally, gate live submission behind a Phase-3 integration task** reusing the modern ZATCA SDK (not the Saturn EXE chain). Confirm we will not try to resurrect the legacy Saturn/toolkit binaries. — **✅ RESOLVED → G04** (ETA-first per official SDK spec; ZATCA = Saudi override out of primary scope; QR+JSON+log ship regardless; no Saturn/toolkit EXEs).

10. **Arabic string quality.** The corpus has garbled/half strings (some strings show mixed text like «طلب معلق يحتاج لل保存»). Recommend: i18n keys are **new curated Arabic + English** by our team for P1 screens (only ~300 strings), not a blind dump of the 26,970 legacy strings. Legacy strings inform wording but are not loaded verbatim. Confirm the team will review Arabic copy rather than auto-import. — *(stays open — team content decision, not an architecture gate; no decision ID in 00 master.)*

11. **RBAC model fidelity.** Legacy is "permission id 1–9" per user. Recommend: keep the schema's `roles/permissions` tables but seed them from the legacy 9 levels; the UI shows friendly Arabic permission names. Confirm whether to expose fine-grained permissions (per-screen) or keep coarse legacy levels in P1. — **✅ RESOLVED → G08** (legacy 1–9 `permission_level` + granular rows; RBAC layers later).

12. **Multiple warehouses/treasuries.** Legacy distinguishes الدرج (drawer) vs خزينة الصيدلية (treasury) and warehouse margins (1–6). Recommend: P1 = single drawer + treasury toggle on purchases (as legacy); multi-warehouse is P2. Confirm. — **✅ RESOLVED → A19** (P1 = single drawer + treasury toggle; multi-warehouse P2).

13. **Branch/chain feature scope.** Chain pharmacy (silsila), chain buying, dead-stock exchange, branch cash monitoring are P3. Confirm the product targets **single-pharmacy first** and multi-branch sync comes later (this heavily de-risks the sync engine). — **✅ RESOLVED → G09** (single-pharmacy first; branch-ready schema; chain Phase 2).

14. **Web target devices.** Is the web client meant for tablets/phones (touch, mobile-first) or desktop browsers (keyboard-first)? Recommend **keyboard-first desktop web** (matches POS reality) with responsive collapse for tablets; a dedicated mobile screen is out of P1. Confirm. — **✅ RESOLVED → P08** (keyboard-first desktop web + offline desktop; mobile out of P1).

---

## 8. Assumptions (stated explicitly)

1. Backend is the **canonical FastAPI + Postgres** design from `schema_postgres.sql`/`schema_design.md`; its API contracts (OpenAPI) are the source of truth for `api-client` DTOs.
2. The **SQLite schema file is final** for the desktop store (money-as-integer minor units, outbox tables, audit requirement) and will not be redesigned by the frontend.
3. Frontend does **not** re-derive accounting invariants (balanced journals) except as read/display; the balanced-journal CHECK is enforced server-side (desktop: in the repo write path).
4. Legacy `REAL` dates are converted once at import to ISO-8601; the frontend never renders VB6 serials.
5. Legacy money floats are never re-summed by the frontend; totals come from the DB or from `core/money` on already-rounded per-row decimals.
6. The 4 legacy "quick tabs" (المشتريات/النواقص/السجل/مبيعات اليوم) are dashboard widgets, not the app's primary nav.
7. Easter-egg and dead forms (FormExecuteCode, FormRemoteControl, FormChatAnydesk, sudoku/piano) are out of scope; not built.
8. Arabic-first with curated bilingual labels; legacy strings are reference material, not shipped verbatim.
9. Print is CSS-driven first, native printer second; a physical cash drawer only exists on desktop.
10. `remotecontrol`/`nilsen2`/`drugeyedash2`/DrugEye feed are **deliberately skipped** per schema_design §4; the frontend will not build UI for them.
11. **Low-spec budget (A13/A14, §1.5):** desktop is the native low-RAM target; web is client-rendered with code-split routes and a small bundle; search is debounced; SQLite is indexed (WAL).
12. **Theme/tokens per `plan/09`:** light-primary default (`:root`), `data-theme` switch (`system|light|dark`), Thmanyah fonts, bookmarkX token naming. `plan/09` is the source of truth for look-and-feel.

---

## 9. Build-order roadmap (phase gates)

- **Phase 0 — foundation (1–2 wks):** monorepo scaffold, `core/money` + tafqit + Zod, i18n package (curated P1 strings), `ui` tokens/fonts/RTL per `plan/09` (light-primary tokens, Thmanyah fonts, bookmarkX naming), both app shells, login/setup.
- **Phase 1 — core-first (6–8 wks):** drug master, POS, purchase, stock current/count, parties, balances view, day-close, printers, dashboard; desktop SQLite repos + outbox write path; web API repos. **Exit criterion:** an offline pharmacist can run a full day (buy, sell, count, close) with all money/stock/audit rows consistent, then sync cleanly.
- **Phase 2 (6–8 wks):** full report catalog (generic ReportView), MRD/installments, discounts/VAT, employees/attendance/salaries, needs/auto-order, transfers, month close, capital/trial balance, import/export, backup, settings/advanced.
- **Phase 3 (ongoing):** chain/network features, ZATCA live (via modern SDK), DTTS, Wasfaty, FaryNet, patients/prescriptions, updater, DrugEye (if legal clearance), easter eggs.

---

### Summary for the user

- **Top decisions:** pnpm monorepo with shared `ui`/`core`/`api-client`/`i18n`; the 4 legacy MDI parents → 4 route modules with a workspace-tab system; **one shared domain layer with SQLite and HTTP adapters**; offline sync = atomic outbox + LWW + non-destructive conflict panel; money only through a shared exact-decimal module (SQLite stores INTEGER minor units); Arabic-first RTL with curated bilingual labels; keyboard-first POS (F9/F12) preserved. **Confirmed 2026-08-16:** low-spec budget (A13/A14, §1.5) + light-primary theme, Thmanyah fonts, bookmarkX token naming per `plan/09` (P02/P05).
- **Biggest frontend risk:** **offline-first sync** — specifically invoice state + drawer/ledger integrity + per-device e-invoice counters across offline devices (web is a straightforward server-backed CRUD; the desktop must reproduce the legacy file-based money truth and LWW replication correctly). Mitigations: outbox-in-transaction, device_seq ordering, conflict panel, and single-branch-first phasing.
- **Open questions:** §7 resolved against 00 master (A01/A13/A14, G04/G08/G09/G10/G11, P08/P09, A15/A19); the only item without a decision ID is **#10 (Arabic string curation approach — team content decision, not an architecture gate).**