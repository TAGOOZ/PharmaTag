# PharmaTag فارما تاج — Master Decision Log

Consolidation of every open question from the 9 planning agents (plan/01..09).
Deduplicated from ~107 raw questions to the unique decisions below. Each carries the
source plan(s) and the agents' recommendation. Tier 0 gates must be answered before
coding; Tier 1 before Phase-1 schema lock; Tier 2 are product/brand picks; Tier 3 need
external input (data samples / vendor specs).

---

## Tier 0 — GATES (answer first; everything keys off these)

| ID | Decision | Recommendation | Sources |
|----|----------|----------------|---------|
| G01 | **Target market**: Egypt, Saudi, or both? | Egypt-first; keep schema country-agnostic (VAT default 14%, ETA regime, currency EGP; Saudi = override) | 01#1, 06 D14/D1, 05#1, 02 O-10, 04 OQ-07 |
| G02 | **Migration scope**: full-history vs cutover-from-a-date | Cutover from a chosen date; import tar.phy drug master fully; money history best-effort (unblocks on undocumented .phy layouts) | 06 D15/D2, 07#1-3, 05#7, 01#3 |
| G03 | **Drug database source + license** | CC0 `karem505/egyptian-drug-database` + SFDA open data; NEVER DrugEye data (legal) | 06 D18/D3, 04 OQ-10, 02 §8 |
| G04 | **E-invoice submission strategy** | Reimplement natively (FastAPI worker + proper key mgmt); don't wrap saturn/toolkit EXEs; QR+JSON+log ship regardless | 02 O-6, 03#9, 04 OQ-08, 06 D17/D4 |
| G05 | **ZATCA/ETA canonical payload** | Merge api_integration §2.5 + zatca_complete §3 into ONE canonical JSON (ETA for Egypt, ZATCA XML via payload_xml); discard the other 2 shapes; sign off before serializer | 01#5, 02 O-5, 04 OQ-07, 06 D23/D10 |
| G06 | **VAT price model** | Egypt retail = VAT-inclusive; `branches.vat_inclusive_prices` config flag | 06 D19/D6 |
| G07 | **Invoice numbering authority** | `invoices.invoice_no` = internal source of truth; per-branch monotonic; UNIQUE(branch_id, invoice_no); returns are NEW documents | 01#4, 06 D20/D7 |
| G08 | **Roles/permissions** | Keep legacy 1–9 `permission_level` on users + granular permissions rows; RBAC layers on later | 01#7, 03#11, 05#9, 06 D21/D8 |
| G09 | **Chain/multi-branch scope** | Phase-2 (schema ready, feature-flagged); single-pharmacy first. Topology: one shared PG + offline SQLite cache | 01#10, 03#13, 06 D16/D9, 04 OQ-14, 05#1 |
| G10 | **Offline write admission + conflict policy** | True offline-first (allow all writes offline, banner + queue count); LWW auto-resolve + non-destructive conflict panel | 03#4,#6, 05#6,#10 |
| G11 | **Reports scope v1** | Minimal set (A04 drawer handover, D01 expired, day totals, shortage, sales/purch/returns, VAT, trial balance); full RPT catalog later | 03#7, 05#8, 06 D22/D11, 04 OQ-13 |
| G12 | **invoicedata granularity** | One row per invoice line (header cols duplicated), grouped by (pharmacyid, invoiceid); confirm on a production dump | 01#3, 04 OQ-02, 06 D5 |

---

## Tier 1 — ARCHITECTURE (decide before Phase-1 lock)

| ID | Decision | Recommendation | Sources |
|----|----------|----------------|---------|
| A01 | Tauri data layer | TS-first via `tauri-plugin-sql`; Rust only for bootstrap/native printer; SQLite money = INTEGER minor units | 01#2, 03#3 |
| A02 | COGS method | Expiry-FIFO (per-batch cost stored; COGS additive, never recomputed from floats) | 02 O-3, 05#5 |
| A03 | Journal granularity | One balanced journal per invoice; payment splits summarized | 02 O-2 |
| A04 | Balances/branch_stock | Materialized tables (not views) + nightly reconciliation job | 01#9 |
| A05 | Rounding authority | Server owns all money math (`money.py`); clients send raw qty/price/disc | 02 O-1 |
| A06 | titanksasales (chain summary) | Projection / materialized view, NOT a synced table | 02 O-4 |
| A07 | Day-close reopen policy | Reopen only by manager (perm ≥7), writes reversal + audit; core = day-close, plugin = monthly/year-end | 02 O-7, 08 Q1 |
| A08 | Plugin DB extension | Single shared schema + `p_<slug>_` prefixed tables (twin parity); keep [S] tables in core rev 001 | 08 Q2/Q3 |
| A09 | Plugin hook strictness | `strict_by_default=False`; eta is explicitly strict (may block sale) | 08 Q4 |
| A10 | Pilot plugins | `pharmatag-eta` + `pharmatag-ledger` prove the seams end-to-end | 08 Q7 |
| A11 | Plugin delivery/licensing | Single installer + signed enablement (no DRM); eta bundled regionally | 08 Q5/Q6 |
| A12 | Plugin loading model | Bundle-all + runtime gate; no remote module loading (offline-first) | 08 Q9/Q10 |
| A13 | Monorepo toolchain | pnpm + Turborepo, TS strict, Biome, Vitest | 03#1 |
| A14 | Next.js rendering | App Router, client-rendered (internal ERP, no SSR/ISR) | 03#2 |
| A15 | einvoice counter/hash | Per-(branch,kind) monotonic counter, never reset in fiscal year; SHA-256 QR hash; idempotent resubmission | 01#6 |
| A16 | Suppliers/party branch scoping | `parties.branch_id NOT NULL`; migrated suppliers → main branch; shared supplier re-created per branch | 01#8 |
| A17 | Cash-sale party | `party_id` nullable; post to drawer_movements + cash account | 01#11 |
| A18 | wzdrugs.agel column | Drop until semantics confirmed | 01#12 |
| A19 | Warehouse/treasury scope | P1 = single drawer + treasury toggle; multi-warehouse P2 | 03#12 |

---

## Tier 2 — PRODUCT & BRAND

| ID | Decision | Recommendation | Sources |
|----|----------|----------------|---------|
| P01 | Logo mark + tagline | Option A (pharmacy cross + tag), tagline #1 "صيدليتك، متوّجة بالدقة"; splash "دقة. سرعة. تاج." | 09#2 |
| P02 | Default theme | Dark by default on BOTH platforms; system|dark|light setting | 09#3 |
| P03 | Derived WCAG tokens | Approve ~10 additive derived hexes (palette keeps AA after layer) | 09#4 |
| P04 | POS density | sm=28px invoice rows, md=34px lists, lg=48px touch | 09#6 |
| P05 | Fonts | IBM Plex Sans Arabic + Cairo (self-hosted), IBM Plex Mono for digits | 09#7, 03#3 |
| P06 | Focus ring / print / bilingual | Focus = accent-hover; print always black-on-white; bilingual behind toggle | 09#8,#9,#10 |
| P07 | Legacy users/password | Force reset on first login; 17-digit usernames survive | 05#3 |
| P08 | Web vs desktop priority | Keyboard-first desktop web + offline desktop; POS desktop-first, web dashboards read-only first | 03#14, 05#2, 04 OQ-16 |
| P09 | Printer/drawer + OS | Desktop: ESC/POS thermal + drawer (Rust); web: PDF/80mm fallback; Windows/Linux desktop | 03#8, 05#12, 04 OQ-17 |
| P10 | Currency | Single-currency default; VAT country config additive | 05#4 |

---

## Tier 3 — NEED EXTERNAL INPUT (not decidable from corpus)

| ID | Item | Why | Sources |
|----|------|-----|---------|
| X01 | Production `Files\DBI` copy | Dailymax reclen, MonyInfo/Dailyline/fary.date/closefary/acctree/RasidCorrect/workperiod layouts | 07#1,#2, 04 OQ-06, 06 D2 |
| X02 | 28-table SQL dump (format + timing) | No .bak/.csv present; gates ETL | 07#3 |
| X03 | delivery.phy status semantics | transfers.status placeholder | 07#4 |
| X04 | Daily 40000-cap wrap confirmation | record→date serial mapping | 07#5 |
| X05 | customers.w `?` charset rule | cp1256 vs normalize | 07#7 |
| X06 | Archive granularity + MRDINFO + safer/counter/hash | import vs archive-untouched | 07#8,#9,#10 |
| X07 | HungerStation v2/chains contract | OAuth + request/response spec or drop | 04 OQ-12 |
| X08 | Insurance companies/contract model | copay/coverage engine scope | 04 OQ-15 |
| X09 | Nielsen ingest source | parity or drop | 04 OQ-11 |
| X10 | CorrectStockForAll semantics | stock-correction thresholds | 04 OQ-05 |
| X11 | creditdebit/payed return discriminator | chain debt semantics | 04 OQ-03,OQ-09 |
| X12 | taronlineeg vs farysales confirm | which INSERT targets which | 04 OQ-04 |
| X13 | Corpus count 23 vs 28 | locate the missing feature docs | 04 OQ-01 |

---

## Recorded decisions (as of decision session)

| ID | Decision | Status |
|----|----------|--------|
| G01 | Egypt-first; schema country-agnostic; VAT default 14%, EGP, ETA regime; Saudi = override | ✅ CONFIRMED |
| G02 | Cutover-from-date migration; drug master fully; money history best-effort from cutover with seeded balances | ✅ CONFIRMED |
| G03 | Drug DB seed = `karem505/egyptian-drug-database` (CC0-1.0, 25k meds, EGP prices). Reject `mahmoudfalous/eg-drugs` (non-commercial license). EDA EDDB = verification only. Legacy barcodes come from own `.phy`/`wzdrugs`. | ✅ LOCKED (research-verified 2026-08-16) |
| G04 | Native reimplement of ETA eInvoicing (Egypt-first). Standard = ETA Invoice v1.0 JSON + eReceipt v1.2 (JSON-only), CAdES-BES signing (ITIDA spec), SHA-256, RSA sha256WithRSAEncryption, eSeal X.509, REST + OAuth, async submit/poll/notify. ZATCA = Saudi variant, out of primary scope (kept as override). | ✅ LOCKED (research-verified) |
| G05 | Canonical payload = ETA Invoice v1.0 schema from official SDK (preprod + prod), NOT the corpus's 3 "summer" shapes (those were ZATCA/Saudi + dead URLs). | ✅ REFRAMED — G05 superseded by official spec |

| G06 | VAT-inclusive retail + per-line tax treatment. Egypt: 14% standard, 5% medical devices, **medicines VAT-exempt (0%)**. EDA prices are final (inclusive); taxable lines split net = total ÷ 1.14. Drug master carries a per-line `tax_type` (exempt/14%/5%). `branches.vat_inclusive_prices` flag. | ✅ LOCKED (research-verified 2026-08-16) |
| G07 | `invoices.invoice_no` = internal per-branch monotonic source of truth; UNIQUE(branch_id, invoice_no); returns = new documents. | ✅ CONFIRMED |
| G08 | Legacy 1–9 `permission_level` + granular permissions rows; RBAC layers later. | ✅ CONFIRMED |
| G09 | Single-pharmacy first; branch-ready schema; chain/outbox UI Phase 2. | ✅ CONFIRMED |
| G10 | True offline-first (all writes allowed offline, banner + queue count); LWW + non-destructive conflict review panel. | ✅ CONFIRMED |
| G11 | Minimal v1 reports (day totals, drawer handover, shortages, expired, sales/purch/returns, VAT, trial balance); full RPT catalog later. | ✅ CONFIRMED |
| G12 | Legacy invoicedata = one row per invoice line (header cols duplicated), grouped by (pharmacyid, invoiceid); confirm on production dump. | ✅ CONFIRMED |
| A01 | Tauri data layer TS-first (tauri-plugin-sql, domain logic in TS, Rust only for bootstrap/native printer; SQLite money = INTEGER minor units). | ✅ CONFIRMED |
| A02 | COGS = per-branch setting: default **expiry-FIFO**, strict-FIFO and average available; manual batch pick on POS stays. Selling price is EDA-fixed; COGS affects profit/tax only. | ✅ CONFIRMED (configurable) |
| A07 | Day-close is CORE; reopen only manager (perm ≥7) with reversal + audit; monthly/year-end close = `pharmatag-ledger` plugin. | ✅ CONFIRMED |
| A08 | **Schema-per-plugin on PostgreSQL** (search_path); offline SQLite twin has no plugin schemas → per-plugin ATTACHed SQLite files or `p_` prefix fallback in the offline twin only. ⚠ deviates from 08 Q2 rec; DB plan (01) + plugin plan (08) must be updated. | ✅ CONFIRMED w/ caveat |
| A09 | Event hooks best-effort by default; e-invoicing counters STRICT (broken ETA install may block a sale — no un-hashable invoices). | ✅ CONFIRMED |
| A10 | Pilot plugins: `pharmatag-eta` + `pharmatag-ledger`. | ✅ CONFIRMED |
| A13/A14 | pnpm + Turborepo, TS strict, Biome, Vitest; **low-spec-friendly**: desktop-first Tauri (native, low RAM), web = React client-rendered (Next.js App Router client-only; Vite SPA swap is cheap since domain lives in shared `core`/`ui` packages). Performance budget for POS hardware (code-split routes, small bundle, debounced search, indexed SQLite). | ✅ CONFIRMED (low-spec constraint) |
| A03–A06, A11–A12, A15–A19 | All agent-recommended defaults accepted (one journal/invoice; materialized balances + nightly reconcile; server-owned rounding; titanksasales as projection; signed enablement no DRM; bundle-all plugins; ETA counter/hash per branch+kind SHA-256; parties.branch_id NOT NULL; cash-sale party_id nullable; drop wzdrugs.agel; P1 single drawer + treasury toggle). | ✅ CONFIRMED |
| P01 | Logo Option A "Tag-Cross" (accent tag + pharmacy cross, favicon-safe); tagline #1 `صيدليتك، متوّجة بالدقة`; splash `دقة. سرعة. تاج.` | ✅ CONFIRMED |
| P02 | **Light is the PRIMARY theme** (brand default on web + desktop); dark = supported alternate. ⚠ deviates from 09 D1/D5 (dark default); theme switch architecture unchanged. | ✅ CONFIRMED (user override) |
| P03 | Approve ~10 derived WCAG tokens per theme (palette passes AA after derived layer). | ✅ CONFIRMED |
| P04 | Dense POS: 28px invoice rows, 34px lists, 48px touch. | ✅ CONFIRMED |
| P05 | **Fonts = Thmanyah family** (UI Sans 300–900, Serif Display headings, Serif Text body) per shared style-guide at `bookmarkX/docs/style-guide.md`; covers Arabic + Latin. Fallback IBM Plex Sans Arabic / Noto Kufi. ⚠ replaces 09 D4. **PharmaTag reuses the bookmarkX token architecture** (`data-theme`, `--background-primary`, `--text-muted`, `--accent-color`, priority trio, logical properties, component recipes) with light-primary override. | ✅ CONFIRMED (from user's style guide) |
| P06–P10 | Focus ring = accent; print always black-on-white; bilingual Arabic/English behind toggle (Arabic-only default POS); force password reset on first login; keyboard-first desktop web + offline desktop; PDF/80mm web print fallback; single currency EGP default. | ✅ CONFIRMED |
| X13 | Corpus feature-doc count = **23** (glob-verified), not 28. The "~28" in the brief was an estimate; no missing docs. | ✅ RESOLVED |
| X01/X02 | **No production `Files\DBI` copy and no SQL dump available yet.** Migration workstream is BLOCKED on data → Phase 6 stays deferred. Cutover-from-date contract (G02) stands; drug-master import + money history resume when data arrives. Reconciliation/verify steps are data-gated (X03–X06, X10–X12). | ⛔ BLOCKED (data required) |
| X07 | HungerStation integration **SKIPPED** (removed from feature inventory / plugin scope). | ✅ CONFIRMED |
| X08 | Insurance/copay module **DEFERRED** to Phase 2+; plugin skeleton only. | ✅ CONFIRMED |

---

## Tier 3 — still open (all gated on legacy data or vendor specs)

| ID | Item | Status |
|----|------|--------|
| X03 | delivery.phy status semantics | awaits DBI sample |
| X04 | Daily 40000-cap wrap | awaits DBI sample |
| X05 | customers.w `?` charset | awaits DBI sample |
| X06 | Archive granularity + MRDINFO + safer/counter/hash | awaits DBI/SQL data |
| X10 | CorrectStockForAll stock-correction rule | awaits data or pcode deep-dive |
| X11 | creditdebit/payed return discriminator | awaits data |
| X12 | taronlineeg vs farysales INSERT confirm | awaits pcode deep-dive |

## Decisions that require plan updates (reconcile pass)

- **plan/02 backend** — ETA eInvoicing module per official SDK spec (JSON v1.0, eReceipt v1.2, CAdES-BES, eSeal); G06 per-line tax_type; G07 numbering; A05 server rounding.
- **plan/01 db** — A08 schema-per-plugin on PG + SQLite twin caveat; G06 add `tax_type` to drug master/lines; A04 materialized balances; ETA counter/hash per branch+kind.
- **plan/03 + plan/09** — P02 light-primary; P05 Thmanyah fonts; reuse bookmarkX token architecture (`data-theme`, `--background-*` naming, component recipes); A13 low-spec budget.
- **plan/08 plugins** — A08 schema-per-plugin replaces prefixes; X07 HungerStation dropped.
- **plan/05 slicing** — Phase 6 migration BLOCKED (no data); P08 desktop-first; insurance/HungerStation out of v1.
- **plan/04 features** — mark HungerStation + insurance as deferred; ETA module aligned to official spec.

**Implication for plan/02 backend:** build the einvoice module against the ETA SDK spec directly (JSON serializer, CAdES-BES via a crypto lib, eSeal key storage in einvoice_log/einvoice_counters as designed). The corpus ZATCA docs stay as reference for a future Saudi override only.

---

## Suggested resolution order

1. Answer **G01 → G04** (market, migration, drug DB, e-invoice) — these reshape the schema and phasing.
2. Answer **G05 → G12** (payload, VAT, numbering, RBAC, chain, offline, reports, invoicedata).
3. Lock **A01 → A19** in a Phase-1 design review.
4. Picks **P01 → P10** anytime (brand).
5. **X01/X02** are asks for the data owner; the rest are small confirmations.

## Process decisions (append-only log)

- **2026-08-16 — Repo home:** `TAGOOZ/PharmaTag` doubles as the code repo. The `testTLS/` workspace (plans, AGENTS.md, docs, schema drafts, legacy corpus) is its initial commit; `TITAN.W1B.exe` is gitignored (source of truth is `titan_decompile/`). Tickets T01/T04 scaffold the monorepo on top.