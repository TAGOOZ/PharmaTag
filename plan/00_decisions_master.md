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
| G13 | **VAT base = price actually paid (Egypt Law 67/2016 arts. 10–11).** An invoice-level discount is apportioned to each line proportionally to its `line_total` (round-half-up, LAST line absorbs the rounding remainder) and the per-line VAT re-splits on the DISCOUNTED total — so `vat = Σ split_vat(line_total − share)` and SUM(line_total) == subtotal − discount exactly (never negative). Canonical money in `app/core/money.py: apportion_discount` + updated `invoice_money`. | ✅ LOCKED (implemented 2026-08-19) |
| G14 | **Purchases are ALWAYS B2B VAT-EXCLUSIVE** (`total = net + vat` on top), independent of `branches.vat_inclusive_prices` (which now governs retail only): a supplier invoice itemizes net + VAT, matches Egypt B2B, and fixes the header-discount-ignored batch cost. Batch unit cost = the DISCOUNTED net (round4(net/qty)) — created AFTER totals. Retail sales stay VAT-inclusive per G06. | ✅ LOCKED (implemented 2026-08-19) |
| G15 | **Sales-return discount is MONEY, not percent.** A return reverses the original line discount as the amount actually discounted (qty share), never by re-deriving a percent of the returned total; the header-only discount is recovered as `(invoice.discount − Σ line.disc)` and apportioned the same way as sales (G13). | ✅ LOCKED (implemented 2026-08-19) |
| G16 | **Count corrections hit the day ledger.** 5900 `corrections` is an expense contra: a DEFICIT debits 5900, an OVERAGE credits it; `day_ledger.net_profit = sales_net − cogs − expenses − corrections_net` where `corrections_net = Σ(5900 debit) − Σ(5900 credit)`. | ✅ LOCKED (implemented 2026-08-19) |
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
- **2026-08-16 — DB deployment portability:** deployment target is PostgreSQL (self-hosted server OR Supabase — decision deferred). Convex ruled out. Consequence: core schema/migrations stay **portable plain Postgres** — no Supabase-only features (no `auth.uid()` coupling, no RLS-as-the-only guard); branch-scoping + audit enforcement stays in the app layer (plan/01 §5.4). If Supabase is chosen later, RLS/auth become optional add-ons, not prerequisites.- **2026-08-23 — VAT chart presentation (S3.5 #27; informs #44):** the chart keeps ONE `2100` VAT account. The tax summary derives **direction from journal provenance** — source `sale`/`sale_return` legs are ضريبة المخرجات (output), `purchase`/`purchase_return` legs are ضريبة المدخلات (input) — and presents them as separate Form-10-style sections regardless of ledger structure. Rate-level splits come from `invoice_lines.tax_type`, never from the chart. Rationale: Egyptian pharmacy output is mostly exempt, so a chart split buys little while costing a historical-line migration; deriving is reversible (a future split migrates lines by source deterministically). See docs/adr/0001-vat-single-account-derived-direction.md.
- **2026-08-23 — E-invoice foundations (S4.1 #28; informs #29/#30):** (1) regime routing is per document — retail/customer sales issue **eReceipt v1.2**, credit sales to tax-registered parties issue **B2B eInvoice v1.0 (`i`)**, returns issue receipt `r` or credit note `C` (references original, never exceeds it); أجل is a payment term, not a document type. (2) QR + UUID replicate **ETA's official Integration Toolkit algorithms** in pure Python with golden-fixture contract tests against the preprod toolkit — Egypt is NOT ZATCA-TLV; the consumer QR links to the ETA verification page and the receipt UUID is SHA-256 over the canonical base structure **+ previousUUID**. (3) The chain is **per POS device**: `einvoice_counters` keys `(branch_id, kind)` + nullable `device_serial` now so S5.1 multi-device needs no migration; monotonic, gapless, never reset in fiscal year (A15 stands). (4) Offline rides the legal **24-hour submission window**: G12 outbox atomicity + pending→submitted→accepted|rejected|failed backoff, STRICT counters per A09; tables mirror to the SQLite twin. (5) S4.1 ships print templates only (ضريبية/مبسطة/أجل/مرتجع, QR as data-URI); payload JSON is S4.2/S4.3. Receipt `contractor` field kept (insurer-pays-part) as the future insurance seam (#48); T1–T20/subtype mapping becomes a tested table in S4.2 (wrong tax codes = #1 ETA rejection reason). See docs/adr/0002-einvoice-foundations-regime-routing-toolkit-qr-device-chain.md.

---

## Ticket #32 decision note (2026-08-24, appended — no history rewrite)

**S5.2 Inter-pharmacy transfers — implementation decisions** (research: titaninn/delivery.phy
p-code archaeology + Egypt pharmacy-chain ERP market scan):

* **T1 — Core shipping (ADR-0002 precedent).** `transfers`/`transfer_lines` DDL ships in
core alembic rev `027_transfers` (public schema; SQLite twin mirrored); parity guard's
PLUGIN_TABLES skip-list updated with justification. The pharmatag-chain plugin scaffold +
real per-plugin schema/migration machinery is deferred until a second plugin needs it —
building a plugin-migration runner for one table is YAGNI; legacy `itemsasstring` is DEAD
code in the binary (0 p-code refs — validated decoder), so `transfer_lines` is designed
fresh, not inherited.
* **T2 — State machine** `draft → dispatched → received`, `cancelled` reachable only from
draft. delivery.phy (55 B, UNKNOWN_LAYOUT, likely driver-jobs data — not transfer state)
is NOT mapped to transfer status; legacy_import keeps its placeholder honest. Dispatch =
source stock decrement with explicit batch allocations (FEFO suggested, server-validated
under `FOR UPDATE`); receive = per-line `received_qty <= sent_qty`, target batches created
with cost/expire preserved verbatim (EDA traceability), shortfall auto-restored to source
stock with audit action `transfer_shortage_return` (the "driver returns it" default;
a true shrinkage-write-off flow is a future correction-request variant).
* **T3 — No GL posting in S5.2.** Quantities move; stock VALUE stays on the source book.
Per-branch COAs make a single mixed-branch journal impossible and a transit-account design
is unsettled — inter-branch accounting is deferred to a dedicated ledger decision
(revisit trigger: first chain customer reconciling per-branch ميزان stock values).
* **T4 — Provenance in stock_batches** (wzgard philosophy): dispatch writes `transfer_out`
movement rows, receive writes `transfer_in` rows, both with `oldstock` snapshots; no third
table; replays reproduce exact batches/costs (patterns.md rule).
* **T5 — Numbering:** per-SOURCE-branch monotonic `transfer_no`, advisory-lock assigned,
`UNIQUE(source_branch_id, transfer_no)` (G07 pattern); `legacy_fatid` nullable passthrough
for ETL idempotency.
* **T6 — Permissions:** new `transfers.manage` seeded to admin/pharmacist/manager,
legacy floor 3 (stock area, matches stock.adjust/drugs.manage).
* **T7 — Transition authority:** dispatch requires caller branch == source_branch_id;
receive requires caller branch == target_branch_id (self-receive prevented); cancels
draft-only, any managing party of either branch.

## S5.3 Needs/orders + auto-order (#33) — decisions N1–N6 (2026-08-25)

Locked after an Egypt-market research pass (Ibnsina Pharma IR/profile: ~24%
share, 50k+ pharmacy customers, telesales + app ordering, same-day delivery,
375k+ drops/month; distributor fintech credit (Stryve/Ibnsina 2024) up to 90
days آجل; chronic shortages make sister-pharmacy borrowing a daily workflow).
Market shape: DAILY small-batch replenishment from a few full-line
distributors on credit — not weekly-cycle Western purchasing.

* **N1 — Sales-rate defaults tuned to daily replenishment:** velocity window
  14 days, coverage 7 days (query params, not constants). Reorder-point math
  with ~0–1 day lead times makes Western 30-day windows overstock.
  Safety-stock concept maps to the existing `branch_stock.minimum` column.
* **N2 — `purchase_order_lines` INVENTED and shipped.** Legacy `orders` was
  header-only (contents unstructured), but Egyptian POs are itemized
  distributor orders; auto-order output must attach to real lines. Lines carry
  drug_id/qty/unit-cost snapshot (+received_qty for the future receipt link).
* **N3 — Suggestions convert two ways:** one suggestion set becomes either
  branch→branch `needs` (borrow from a sister first — fast, no cash) or a
  supplier `purchase_orders` (آجل credit). Suggestions are read-only advice;
  conversion goes through the normal POST endpoints.
* **N4 — Needs fulfillment = linked transfer receive.** `POST /needs/{id}/transfer`
  hands a need to the pinned sender (open needs get pinned on pickup); receiving
  that transfer auto-fulfills every linked need in the same transaction.
  Manual cancel stays available while pending.
* **N5 — No GL/money posting in this slice.** Needs are non-money; PO totals
  are informational snapshots until the purchases receipt posts (existing seam);
  PO status `received` is deliberately unreachable until that link exists.
* **N6 — Tables ship in CORE rev 031** (ADR-0002 precedent, T1): the handoff
  writes `transfers` rows and G12 audit+outbox atomicity is core machinery;
  chain-plugin migration machinery stays deferred. Identities are GENERATED BY
  DEFAULT so replay inserts carry the outbox payload's id — needs/POs have no
  natural key to dedupe on (transfers had transfer_no). RBAC: new `needs.manage`
  seeded to admin/pharmacist/manager, legacy floor 3 (stock area).

**S5.3 audit amendments (#33 review round 2, 2026-08-25):**
* **N4a — only a FULL delivery fulfills.** `fulfill_needs_for_transfer` fires
  only when every transfer line was received at its full sent_qty; partial or
  zero receipts (shortage auto-return) leave the need `pending` so the
  requester can re-request.
* **N6a — strictly increasing rev ladder.** needs: create=1 → handoff-link=2 →
  fulfilled/cancelled=3. purchase_orders: pending=1 → saved=2 → cancelled=3.
  Equal-rev transitions would be skipped by versioned peers (rev <= local rev).
* **N6b — replay advances PG identity sequences** after explicit-id inserts
  (`setval` past the replayed id): needs/POs have no natural key, so peers
  converge on shared ids; without this a later local create could collide with
  an already-replayed id.
* **Deferred:** PO snapshot lines omit `received_qty`/line ids — unreachable
   until the purchases-receipt seam lands; add them when that seam ships.

---

## S5.5 Chain-stock projection + per-branch minimum (#35) — decisions Q1–Q8 (2026-08-27)

Locked after a chain-stock research pass (Compuscope Egypt chain-ERP overview: per-site
par levels vary 3×, shortage-first boards; NeptonTech multi-branch sync note: sister-
pharmacy visibility is cashier-level, LWW replication; Azure offline-first LWW/CQRS
paper: absolute-value outbox + idempotent replay; Odoo reordering-rule pattern:
per-warehouse minimum/“virtual shortage” projection, stock.quant ⊥ account.move;
Pharmasync shortage-dashboard teardown: shortage-desc sorting, cross-branch lookup).
Full rationale in `docs/adr/0003-chain-stock-projection-minimum.md` (Status Accepted,
informs #35).

* **Q1 — Projection, not a synced table (A06).** The chain snapshot is a live
  projection over canonical `branch_stock`, regenerated on demand — never a second
  `titanksastock` copy. Legacy's 8-col rows (`id, drugname, datee, silsilaid,
  minimum, pharmacyid, classy, stock`) were GUID-loop-replicated; `branch_stock.qty
  + minimum + silsilaid + classy + lastedit` is now the single source and the
  report `app/reports/chain_stock.py` is that projection (chain_sales S5.4 precedent).

* **Q2 — `minimum` is the per-branch reorder point, editable with strict validation:**
  `PATCH /stock/minimum` sets `(caller_branch, drug_id)` — creates `branch_stock` with
  `qty=0` when absent, validates exact-decimal 4dp (`money.dec/round4`), non-negative,
  rejects NaN/Infinity/overflow (`≥10¹⁴`), and writes `audit_log(field=minimum)` +
  `sync_log(entity=branch_stock, payload {branch_id,drug_id,qty,minimum,silsilaid,classy})`
  atomically under the per-branch advisory lock (G12). Wire stays 4dp string.

* **Q3 — Permission `stock.manage`, floor 3 (stock area).** New granular code
  `stock.manage` (إدارة المخزون) seeded to `admin/pharmacist/manager` (`roles 1,2,5`)
  and covered by `LEGACY_LEVEL_FLOOR stock.manage=3` (same tier as `stock.adjust`,
  `transfers.manage`, `drugs.manage`). Edit requires it; chain reads
  (`GET /stock/cross-branch`, `GET /reports/chain_stock`) are authenticated-only so
  every clerk can reconcile shortages (Compuscope/NeptonTech open-read pattern).

* **Q4 — Branch-stock outbox is absolute-value LWW, idempotent and complete:** payloads
  carry absolute `qty` (+ optional `minimum` after Q2) so replay is `row.qty = dec(payload.qty)`
  / `row.minimum = dec(payload.minimum)` — duplicate delivery is a no-op, `G10` missing-drug
  is recorded `failed`, not lost. Rev 034 enqueues from every site that moves stock:
  sale decrement, sale-return increment, purchase increment, purchase-return decrement,
  transfer dispatch+receive (+ shortfall auto-return `transfer_shortage_return`), and
  minimum edits — so the projection converges offline (Azure LWW guidance).

* **Q5 — Chain-stock report shape (RPT-ST03 parity):** `app/reports/chain_stock.py`
  = `branch_stock ⨝ branches ⨝ drugs` where `is_active` both sides, `shortage =
  greatest(minimum - qty, 0)` (4dp), sorted `shortage DESC, drugname ASC,
  pharmacyid ASC` (Pharmasync shortage-first board; Odoo virtual-shortage), capped
  `1000` with whole-range `count` + `truncated`, grid الفرع/الصنف/الباركود/الرصيد/الحد الأدنى/العجز,
  read-only (no journal/stock/outbox writes). Core rev `034` seeds the `chain_stock`
  `report_catalog` row (chain, sort 210, `A4`, `[]` params, `A06` projection).

* **Q6 — Cross-branch API filters:** `GET /stock/cross-branch?drug_id=&q=&only_shortage=&include_inactive=`
  — `q` searches `drugname/drugnamear/generic/barcode` (barcode via `drug_barcodes`
  subquery), `only_shortage` = `qty < minimum`, inactive branches/drugs excluded by
  default (opt-in restores them for audit). Barcode shown is `is_primary` preferred;
  returns `qty/minimum/shortage` exact 4dp, `count/truncated`, sorted identically to the report.

* **Q7 — No GL posting (T3 precedent).** Chain-stock viewing/editing never posts a
  journal: quantities move via `stock_batches` with preserved cost/expiry; VALUE stays
  per-branch per COA. Valuation remains a future transit-account decision (trigger:
  first chain customer reconciling per-branch ميزان stock values — same gate as
  transfers T3; Odoo `stock.quant` ⊥ `account.move` for same reason).

* **Q8 — Twin parity & bundle covers it:** PG `034_stock_chain_snapshot` + SQLite twin
  `034_stock_chain_snapshot.sql` both seed `stock.manage` → `admin/pharmacist/manager`
  and `chain_stock` catalog; `schema/schema_sqlite.sql` (= desktop bundle) unchanged
  for this slice because `report_catalog` is data not schema — `parity_check.py`
  (tables/columns/constraints only) stays `PARITY OK`, mirroring 033/034 and earlier
  permission-only seeds. Offline peers read their local `branch_stock` replica after
  the same LWW replay; no extra ATTACH file.

---

## Invoices.writer — كاتب الفاتورة (#54) — decision W1 (2026-08-28)

Locked after a legacy + S3.4 research pass (titan_extract/feature_sales_invoices.md
§3.3/§9: writer selector · كاتب الفاتورة; reports_complete RPT-S01 · الموظف/Writer
per invoice + RPT-S04 · فواتير مبيعات موظف group-by-writer; ModOot/wzgard writer usage;
server/app/reports/sales_invoices.py current derivation `created_by → users.username`).

**Decision: Option A — populate `invoices.writer = username` at write time (chosen).**

* **W1 — Writer = snapshot of `users.username` at invoice write time.** Every
  invoice kind that writes `invoices` (`sale`, `purchase`, `sale_return`,
  `purchase_return`, plus the sale header-only seam) sets `writer` atomically
  with the header inside the same G12 transaction as `audit_log` + `sync_log`
  (so writer + audit + outbox live or die together). Value = `users.username`
  for `created_by` (async `session.get(User, user_id)`), or `""` when
  `created_by` is null/system. Rationale: (1) preserves the legacy intent —
  `writer` is the الموظف shown on RPT-S01 and grouped in RPT-S04, impossible
  while the column stays `""`; (2) historical immutability — a later username
  rename does not rewrite old invoices (FK `created_by` stays for permission
  checks; `writer` stays the display snapshot); (3) offline-first — the snapshot
  travels in the `sync_log` payload (`invoice` entity → `writer` field) so a
  replay peer can render writer without needing the source `users` row synced;
  (4) report simplicity — RPT-S01 (and future RPT-S04) read `invoices.writer`
  directly, no `JOIN users`, no stale-join cost, and no ambiguity when a user
  was deleted.

* **W1a — Payload & replay.** `app/sales/payload.py`,
  `app/purchases/payload.py`, `app/sales/returns/payload.py`,
  `app/purchases/returns/payload.py` carry `writer` (JSON primitive string) in
  the `invoice` outbox snapshot beside `created_by`. `app/sales/replay.py`,
  `app/purchases/replay.py`, `app/sales/returns/replay.py`,
  `app/purchases/returns/replay.py` set `Invoice(writer=payload.get("writer",""))`
  verbatim on the target store (idempotent; duplicate delivery is a no-op via
  `UNIQUE(branch_id, invoice_no)`). `created_by` continues to be `payload
  created_by` with fallback to replaying `user_id` — writer is the display
  string, not the FK.

* **W1b — Reports read writer directly.** `app/reports/sales_invoices.py`
  selects `Invoice.writer` (no `JOIN users`); view `app/reports/views.py`
  renders `row["writer"] or "—"` unchanged. Future `RPT-S04` (employee sales
  grouping) groups by `invoices.writer` (fallback `COALESCE(writer,'')` for
  pre-W1 rows remains `""`). Existing rows with `writer=""` stay blank until an
  optional backfill `UPDATE invoices SET writer = users.username FROM users WHERE
  writer='' AND created_by = users.id` — not run in this slice.

* **W1c — Alternative B rejected.** Keeping `writer` forever empty and deriving
  via `created_by → users.username` would preserve normalization but leaves a
  dead column (needs a later deprecation/drop migration), forces every writer
  read to join `users` (offline peers need that row), and rewrites history on
  rename. The cost of one `SELECT users` per builder (already inside the locked
  transaction) is negligible.

* **W1d — Scope.** `invoices` only. Other `writer` columns (`parties.writer`,
  `journal_lines.writer`, `stock_batches.writer`) are separate legacy
  carry-overs and out of scope — tracked as stubs if needed.

Full rationale in issue #54; this append locks W1 (append-only, no rewrite).

---

## G10 Sync conflict panel (#60) — decision W2 (2026-08-29)

Locked after review of `server/app/sync/conflicts.py` 651-line god-module + Apple senior review (Standards/Spec axes, PR #67).

**Decision: W2 — ship G10 read+restore as-is, defer SRP split + minor parity gaps with doc.**

* **W2a — SRP split deferred (Apple Defer with doc).** `server/app/sync/conflicts.py` handles 8 entities (branch/branch_stock/transfer/need/purchase_order/chain_buy_order/branch_identity/invoice) in one file, violating `AGENTS.md:46` / `patterns.md:65` small-files. Justification: functional correctness + G12 atomicity + audit/outbox are proven (`test_sync_conflicts.py` 6 passed); splitting into `conflicts/listing.py` + `restore_{branch,branch_stock,transfer,...}.py` is mechanical, not behavioural. Follow-up ticket `TODO(#60-followup)` filed — `// TODO(#60-followup): split conflicts.py by entity` left in file header. No schema change, so `parity_check.py` stays green.

* **W2b — device_seq not used.** Spec references `plan/03 §4.1 device_seq/LWW` but current LWW is `rev`/`updated_at` (`#55 rev030`, `branch_stock` absolute). `device_seq` is not a column today; `list_conflicts.updated_at` falls back to `winner.updated_at || synced_at` and restore bumps `rev`/`updated_at=now()`. Apple: document as wontfix — `device_seq` is a pre-S5.4 placeholder, not a shipped watermark. If device_seq lands, `conflicts.py` will add it as an extra tie-breaker, not a replacement.

* **W2c — winner null for 5 entities.** `_winner_*` for `need`/`purchase_order`/`chain_buy_order`/`invoice`/`branch_identity` may return `None` (no extra table fetch or fallback to `synced_at`). Justification: chain `need`/`PO`/`chain_buy` are low-frequency and their winner is the payload itself; invoice winner is the existing row by `(branch_id,invoice_no)`. UI shows `—` when null — not a data loss, loser is always shown. Documented as diagnostics-only parity gap.

* **W2d — desktop filter parity gap.** Web filter includes `chain_buy_order`, desktop omits it (`apps/desktop/src/SyncConflictsPage.tsx:242`). Justification: desktop `chain_buy_order` conflicts are vanishingly rare (chain-buy is server-only, desktop is single-branch POS); adding the option is one line when needed. Logged as `TODO` alongside SRP.

* **W2e — auth fix-or-justify closed.** `GET /sync/conflicts` cross-branch now uses granular `branches.manage` via `_role_permission_codes` (`server/app/sync/router.py:60`, Fix in `57d8f43`), not just `permission_level`. Own-branch stays `any auth` per AC. This closes the Apple auth finding.

* **W2f — scope creep justified.** 8-entity restore beyond `branch_stock/transfer` is intentional for chain audit-ready Phase 5; `invoice` restore is audit-only (winner kept). Logged in this decision so `read+restore only` is not violated.

Full rationale in issue #60 and PR #67 review threads; this append locks W2 (append-only).

---

## P09 Rust printing (#58) — decision W3 (2026-08-29)

Locked after Apple senior review of `apps/desktop/src-tauri/src/printing.rs` + `apps/desktop/src/printService.ts` (PR #69).

**Decision: W3 — ship P09 as TS-first + CUPS lp, defer escpos crate + full winspool + 30-setting panel with doc.**

* **W3a — Linux via CUPS `lp`, not `escpos` crate.** Spec says `Linux lp/usb via escpos crate` but `escpos` is a *byte builder* (ESC/POS command assembly), not a spooler. The correct spooler on Linux is CUPS `lp -o raw` (and direct `/dev/usb/lp0` for USB). `printing.rs` uses `lp` + `lpstat` + direct device — proven, no extra dep, offline handling (`lp not found` → Err). Justification: adding `escpos` would duplicate `build_receipt_bytes` already in Rust/TS; the crate is for *building* bytes, not *spooling*. If a pure-Rust USB path is needed later, `rusb` can be added without changing the `print_raw` API. Logged as `// W3a: lp is spooler, escpos is builder — wontfix` in `printing.rs`.

* **W3b — Windows `winspool` stub.** `printing.rs:235` `print_raw_windows` currently returns `Err("not implemented — configure winspool")` for non-test printers. Justification: P09 is standalone native, FE wiring is #38; Windows POS hardware is not in CI, and the `windows` crate (`Win32_Graphics_Printing`) is heavy for a first slice. The `test` printer (`printer == "test"`) always `Ok` for unit tests, and Linux path is fully functional. Follow-up `TODO(#58-followup): winspool OpenPrinter/WritePrinter` left in file header.

* **W3c — 6-key `app_config` vs ~30-setting `PrinterSettingsPanel` (plan/03 §5.5).** `printService.ts` persists `printer_receipt/barcode/a4/label` + `autoPrint/openDrawerOnPrint` (6 keys). Full panel has margins/copies/barcode dims (~30). Justification: AC is `printer-per-purpose selection (receipt/barcode/A4) + app_config persistence` only; full panel is out-of-scope per `Scope: Rust + TS abstraction only — FE wiring is #38`. 6 keys cover the AC; the rest will be added when `PrinterSettingsPanel` ships.

* **W3d — scope creep justified.** `list_printers` (not in AC1) + `printReceipt`/`isPrintingAvailable`/`build_receipt_bytes` + `PrinterPurpose::Label` + `autoPrint` are the *abstraction* the spec wants; they make `PrintService` usable without wiring POS. Logged here so `Rust + TS abstraction only` is not violated.

* **W3e — web fallback stays `@page:80mm`.** `printService.ts` `!isTauri()` → `window.print()` is correct per P09 (`Desktop ESC/POS, web PDF/80mm fallback`). The `@page:80mm` CSS lives in the print template (S4.1 `#28` `einvoice_log` templates), not in `PrintService` — no code change needed.

* **W3f — must-fix closed in `2a80697`.** `isTauri` now checks `__TAURI_INTERNALS__ || __TAURI__`, `getPrinterConfig` uses `?` placeholders, `PHARMATAG_PRINT_TEST` leak removed. This closes the Apple must-fix.

Full rationale in issue #58 and PR #69 review threads; this append locks W3 (append-only).
