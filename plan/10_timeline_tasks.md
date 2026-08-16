# 10 — PharmaTag فارما تاج — Timeline & Task Breakdown

Consolidated from `plan/05_slicing_plan.md` (slices/phases/exit criteria) + `plan/03`
(phase durations) + `plan/01/02` (task-level detail). All decisions per
`plan/00_decisions_master.md`.

**Assumptions:** 2–3 engineers (backend + frontend/desktop + shared lead). Durations are
working weeks and include testing + review, excluding external waits (called out where they
apply). Single-shift, no heroics. Everything scales roughly linearly with team size.

---

## 1. Master timeline (weeks, sequential-per-phase)

| Phase | Content | Duration | Cumm. | Status |
|-------|---------|----------|-------|--------|
| **P0** | Skeleton + slice discipline | 2 wks | wk 2 | 🔜 next |
| **P1** | **MVP** — single-branch daily ops (9 slices) | 9 wks | wk 11 | |
| **P2** | Money/ledger/balances/month-close | 7 wks | wk 18 | |
| **P3** | Reports & analytics | 5 wks | wk 23 | |
| **P4** | ETA e-invoicing (Egypt) | 4 wks | wk 27 | needs ETA eSeal cert (external) |
| **P5** | Chain/cloud sync + logistics | 6 wks | wk 33 | optional for single-pharmacy |
| **P6** | Legacy `.phy` migration | ⛔ 0 | — | **BLOCKED** — no legacy data (X01/X02) |

**v1 (sellable single-branch, no chain/ETA-submit): P0–P2 ≈ 18 wks.** Full single-branch
with tax e-invoicing: **≈ 27 wks.** Chain adds **≈ 6 wks.**

**External waits (start early, don't block code):**
- ETA eSeal X.509 cert + CSID onboarding: 2–6 wks of ETA/approvals — kick off **during P1** so P4 isn't stalled.
- EDA/CC0 drug-catalog download + import job: 1 wk (do in S1.2).
- Branch legal/entity data for seeds: gather during S0.3/P1.

---

## 2. Critical path & parallelization

```
P0 (2w) ─► S1.1 auth ─► S1.2 drug master ─► S1.3 sales ─► S1.4 purchases ─► ... P1 ─► P2 ─► P3 ─► P4
     \                     ▲
      └─ plugin seams (event bus, manifest) MUST be in P0/S1.1 — never retrofit (plan/08)
```
- **Can run in parallel within a phase:** schema+API (back end) vs screens (front end) for a slice — but never *two platforms* for the same slice (plan/05 §1 rule 3).
- **Must be sequential:** S1.3 sales requires S1.1+S1.2; S1.8 day-close requires S1.3; P2 requires P1 (journal lines); S2.6 month-close requires S2.1–S2.5.
- **Foundational, do first in P0:** core rev 001 schema (public schema + plugin host tables), `money.py` rounding, `audit_log` plumbing, outbox (`sync_log`) — every later slice builds on these.

---

## 3. Phase-by-phase task breakdown

Legend: 🔧 schema · 🛠 API/service · 📱 desktop · 🌐 web · 🧪 tests · 📋 docs

### Phase 0 — Skeleton (2 wks)
- 🔧 Core rev 001 schema (Postgres public + SQLite twin) + Alembic + SQLite-mirror migrations + seeds (branches, users, chart-of-accounts stub, `tax_type` values)
- 🛠 FastAPI app shell, config, auth scaffold (JWT), `app/core/money.py` (Decimal, round-half-up, per-line VAT), `app/core/audit.py`
- 🔧 Plugin host tables (`app_plugins`, `plugin_dependencies`, `plugin_branch_grants`, `plugin_settings`) + two-phase event bus (`in_txn`/`after_commit`) — plan/08 seams
- 📱🌐 Desktop (Tauri) + web (Next.js client-rendered) shells, login nav, RTL + light-primary theme (plan/09), Thmanyah fonts, tokens
- 🧪 CI (lint Biome, tests Vitest/pytest), slice harness, README runbook
- **Exit (S0.3):** drug-master record via API appears on web AND on a disconnected desktop; CI green.

### Phase 1 — MVP (9 wks; slices S1.1–S1.9, ~1 wk each)
- **S1.1 Auth/users/roles:** users table, 1–9 permission_level + permissions rows, login, force-password-reset-on-first-login; 🧪 auth integration tests
- **S1.2 Drug master:** drugs + barcodes(≤6) + 3 price levels + `tax_type` (exempt/5%/14%) + CC0 drug-catalog import job (lookup layer) + search-as-you-type; 🧪 pricing/tax math
- **S1.3 Sales invoicing ("oot"):** invoice save → batch stock decrement (expiry-FIFO default) → journal → balances → audit (one transaction); print 80mm/A5; offline write + outbox; 🧪 money invariant test (the hard one)
- **S1.4 Purchases ("inn"):** stock up by batch, supplier payable, payment splits; VAT-inclusive net split; 🧪
- **S1.5 Sales returns:** reverse stock/balance/money; returns = new invoice number; `invoice_versions` snapshot for edits
- **S1.6 Purchase returns**
- **S1.7 Stock count + correction** (approval-gated; `audit_log` + `price_change_log`)
- **S1.8 Cash drawer + day close:** drawer equation, deficit/surplus, reopen = manager-only (perm ≥7) + reversal + audit; 🧪
- **S1.9 Basic reports:** day profit (ربح اليوم), sales/purchases summary, stock minimum, drawer handover
- **Exit:** close a full simulated day (open → sell → return → purchase → count → close); journal balanced for every document; drawer equation balances.

### Phase 2 — Money/ledger (7 wks)
- S2.1 Chart of accounts per branch (wzaccfreetree) · S2.2 Manual journal entries (balanced-check) · S2.3 Customer statement / supplier payables · S2.4 Receivables (أجل) + settlements (سند قبض/صرف) · S2.5 Trial balance + balance sheet (ميزان) · S2.6 Month close + `month_open_balances` + archive · S2.7 Opening balances
- **Exit:** every money document ⇒ `SUM(debit)=SUM(credit)` per journal; per-branch trial balance reconciles to drawer + stock + balances; month close/reopen works.

### Phase 3 — Reports (5 wks)
- S3.1 Report framework (template engine, A4/A5, PDF/Excel export, print queue, always black-on-white) · S3.2 Money reports · S3.3 Stock reports · S3.4 Sales/purchase reports · S3.5 Accounting reports (tax summary, ledger by account)

### Phase 4 — ETA e-invoicing (4 wks, starts on cert availability)
- S4.1 `einvoice_log` + `einvoice_counters` (per branch+kind, SHA-256) + QR + tax-invoice templates
- S4.2 ETA submission + status tracking + resubmission (preprod→prod, per official SDK)
- S4.3 ETA Invoice v1.0 / eReceipt v1.2 JSON generation, CAdES-BES signing (eSeal), GS1/EGS codes
- **Exit:** sale ⇒ tax invoice with QR; counter/hash atomic with invoice; offline queue syncs; status tracked + resubmittable.

### Phase 5 — Chain (6 wks, optional)
- S5.1 Branch registry + main/sub roles · S5.2 Transfers (titaninn) · S5.3 Needs/orders · S5.4 Chain sales sync (LWW outbox) · S5.5 Cross-branch stock snapshot · S5.6 Chain buy store/users

### Phase 6 — Legacy migration (⛔ BLOCKED, ~4–6 wks when data arrives)
- On receipt of a production `Files\DBI` copy and/or 28-table SQL dump: run `legacy_import/` factorisation (catalogue priors), finish the 8 unknown `.phy` layouts (Dailymax, MonyInfo, Dailyline, fary.date, closefary, acctree, RasidCorrect, workperiod), cutover-from-date contract (G02), reconciliation gate.

---

## 4. Parallel workstreams after P0

| Workstream | Owner | Runs during |
|------------|-------|-------------|
| Core schema + API (money invariants) | Backend | P1–P4 continuous |
| Desktop app (Tauri offline twin) | Frontend | P1–P4 |
| Web dashboards (read-only first) | Frontend | P1 (low) → P3 |
| ETA cert/onboarding + preprod account | Ops/Lead | **start P1** |
| Drug catalog (CC0) import + Arabic copy review | Any | P1 S1.2 |
| Legacy migration tooling (kept warm) | Backend | on data arrival |

---

## 5. Definition of done (applies to every slice)
1. Schema migration + SQLite twin landed · 2. API route with the business rule + invariants ·
3. Desktop screen (or web) demoable · 4. Offline behavior proven · 5. Integration test green ·
6. `audit_log` (and outbox where relevant) written atomically · 7. One demo sentence possible.

**Gate before P1 start:** P0 exit met + the four must-have decisions from
`plan/00_decisions_master.md` (A08 schema-per-plugin, A09 hook strictness, A10 pilots) are
already locked — no blockers remain.