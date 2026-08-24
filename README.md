# PharmaTag فارما تاج

Monorepo: Next.js web shell (`apps/web`), Tauri 2 desktop app (`apps/desktop`), shared UI/tokens (`packages/ui`), and a FastAPI core server (`server/`) with a PostgreSQL (Alembic) ↔ SQLite twin schema.

## Prerequisites

- **Node.js ≥ 23.4** (recommended: 24) + **pnpm 10.14.0** (`corepack enable pnpm` or `npm i -g pnpm@10.14.0`) — the desktop tests import `node:sqlite`, which is not on Node 20
- **Python ≥ 3.12** (developed on 3.14) + `python3-venv`
- **PostgreSQL ≥ 16** running locally
- **Rust toolchain + Tauri system deps** (desktop only): `pnpm --filter @pharmatag/desktop tauri dev` needs `cargo` and, on Linux, `webkit2gtk-4.1` + `libappindicator3` (see the [Tauri 2 prerequisites](https://tauri.app/start/prerequisites/)); other OSes need the equivalent per-OS deps

## 1. PostgreSQL

Create the test role/database (names are the defaults `server/app/core/config.py` expects). `CREATEDB` is required — the migration tests create/drop throwaway databases as this role:

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE pharmatag_test LOGIN CREATEDB PASSWORD 'pharmatag_test';
CREATE DATABASE pharmatag_test OWNER pharmatag_test;
SQL
```

(If your user has a peer-login `postgres` superuser session, plain `psql -U postgres` works too; the `sudo -u postgres psql` variant covers the common case.)

## 2. API server (`server/`)

```bash
cd server
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# migrate the DB (also seeds: branch 1 MAIN, admin user, roles/permissions,
# chart of accounts, plugin rows — server/alembic/versions/002_seeds.py)
PHARMATAG_DB_URL=postgresql+psycopg://pharmatag_test:pharmatag_test@localhost:5432/pharmatag_test \
  .venv/bin/python -m alembic upgrade head

# run the API (defaults: http://localhost:8000, /healthz)
.venv/bin/python -m uvicorn app.main:app --reload
```

Run tests (unit + integration against Postgres):

```bash
PHARMATAG_DB_URL=postgresql+psycopg://pharmatag_test:pharmatag_test@localhost:5432/pharmatag_test \
  .venv/bin/python -m pytest tests -q
```

**Non-dev deployments:** set `PHARMATAG_JWT_SECRET` to a strong random value — the compiled-in default (`server/app/core/config.py`) is a dev-only placeholder.

**ETA eSeal key management (S4.3, #30; plan/06 R5/D17):** the CAdES-BES signer
loads PEM key + X.509 cert from two settings paths — `PHARMATAG_ETA_KEY_PATH`
and `PHARMATAG_ETA_CERT_PATH` — pointing at files on the shop server
(recommended: `/etc/pharmatag/eta/eseal.{key,crt}`, root-owned dir, chmod 600
files). Key material lives ONLY in `app/einvoicing/signer.py`; it is never in
the DB. With no key configured (or an unreadable/malformed/non-RSA one) the
submission worker refuses the whole pass: due rows are deferred ~1 minute with
an audit row, retry budgets untouched, and the loop keeps running. Until the
real eSeal arrives, development runs against the pinned self-signed test pair
in `server/tests/fixtures/einvoicing/pinned-test-*`.

**SQLite twin + parity guard** (the desktop uses the SQLite twin; keep it in sync):

```bash
.venv/bin/python sqlite/runner.py                # apply sqlite/migrations/*.sql
.venv/bin/python scripts/parity_check.py         # asserts PG <-> SQLite schema twin match
```

## 3. Frontend (web + desktop)

```bash
pnpm install
pnpm lint        # biome check apps packages
pnpm typecheck   # tsc --noEmit across packages
pnpm test        # vitest (ui + desktop)
pnpm build       # next build + desktop vite build (CI-safe, no tauri release)
```

Run dev servers:

```bash
pnpm --filter @pharmatag/web dev        # Next.js dev server
pnpm --filter @pharmatag/desktop dev    # Vite dev server (HMR)
pnpm --filter @pharmatag/desktop tauri dev   # full Tauri window (needs system webkit deps)
```

## 4. Reproducing fixtures & seeds

- **Database seeds** come from `server/alembic/versions/002_seeds.py` (Postgres) and
  `server/sqlite/migrations/002_seeds.sql` (SQLite twin). `alembic upgrade head` on a
  **fresh** database reproduces them deterministically (branch 1 `MAIN`, `admin`
  superuser `permission_level 9`, roles/permissions, chart of accounts, plugin rows).
- **Tests create their own state** — `server/tests/*.py` insert and clean up their own
  throwaway rows (drugs, branch_stock, invoices) and only rely on seeded branch 1 +
  user 1. A fresh `alembic upgrade head` + `pytest tests -q` is the documented repro.
- **Slice harness**: `server/scripts/parity_check.py` regenerates the PG schema via
  Alembic offline SQL and asserts the SQLite twin matches (no REAL/FLOAT money, no
  plugin tables in core). It must stay green on every change.

## 5. Demo (S0.3: login + branch + drug-master read)

> Login as `admin` / `changeme`, open **الأدوية** on the web
> (`http://localhost:3000/drugs`), or launch the desktop app and open **الأدوية**:
> both show the seeded MAIN-branch drug master (5 VAT-exempt medicines from
> `003_drug_seeds`).

```bash
# 1. API on :8000  (server/)
PHARMATAG_DB_URL=postgresql+psycopg://pharmatag_test:pharmatag_test@localhost:5432/pharmatag_test \
  .venv/bin/python -m uvicorn app.main:app
# 2. web on :3000  (repo root)
pnpm --filter @pharmatag/web dev
# 3. or the offline desktop (disconnected, reads SQLite — no API needed)
pnpm --filter @pharmatag/desktop tauri dev
```

The web **الأدوية** page asks you to sign in first (the login form keeps your
token in localStorage; `must_reset_password` from the seed admin blocks entry
until the password is changed via `/api/v1/auth/reset-password`). It then
fetches `GET /api/v1/drugs` (Bearer token) → `{ "branch": {id, pharmacyid,
pharname}, "drugs": [{id, drugname, drugnamear, generic, classy, co, units,
unitsmall, price, price_wholesale, price_cost, price_now, tax_type, vat,
barcodes, active}] }`, scoped to the caller's branch (a deleted branch → 404,
an inactive branch → 403; results paginated, `limit` default 200 / cap 500).
The desktop never calls the API — `initDb()` seeds its local SQLite with the
same `003_drug_seeds` rows on first run (seed-set-aware, idempotent) and
renders the identical list offline.

Drug-master **writes** (ticket #8) live on the same API: `POST /api/v1/drugs`,
`PATCH /api/v1/drugs/{id}`, `GET /api/v1/drugs/{id}` (all gated by the
`drugs.manage` permission — legacy level ≥ 3 or admin role), plus
`GET /api/v1/drugs/search?q=` (name AR/EN or barcode prefix, open to any
authenticated user) and `POST /api/v1/drugs/import` (CSV body, CC0 catalog —
see §6). Prices are exact decimal strings, rounded half-up to 2 dp.

The web **التقارير** page (ticket #23) is the generic ReportView: it reads the
catalog menu grouped by category, asks only for the selected report's params
(date inputs) + paper (A4/A5), renders any entry through the same grid the
printable page uses, and offers عرض / طباعة (browser print of the black-on-white
page) / PDF / Excel downloads and إضافة لقائمة الطباعة with a
"تم الطباعة" queue drain. Sign in from الأدوية first — the page links there
when no token is stored.

## 6. Known stubs (not finished work)

Keep this inventory honest: a screen/endpoint listed here is a **placeholder**, not
a shipped feature. Slices replace entries as they land; agents must update this
list in the same commit as the work (add when a placeholder is created, remove
when a slice replaces it). Where a placeholder is already tracked on the issue
tracker (TAGOOZ/PharmaTag) the **Ticket** column names it — the row stays until
the ticket ships.

| Area | Item | Status | Ticket |
| --- | --- | --- | --- |
| web `/pos` `/purchases` `/stock` `/money` `/employees` | module screens | stubs — show "built in the corresponding slice" | #38 |
| web `/settings` | module screen | change-password form works (ticket #37); the rest of the settings module is a stub | #38 |
| web `/` | dashboard (home) | stub — static shell, today-summary not wired | #38 |
| desktop | module screens (`App.tsx` STUBS) | stubs — same as web | #38 |
| desktop | login / sync / branch bootstrap | not implemented — SQLite is seeded directly | #39 |
| API | money endpoints | drawer + day close are real (`/api/v1/drawer/*`, ticket #14), except `vat_expenses`, which snapshots 0 — no expense-VAT data source exists yet (documented in `app/drawer/movements.py`); manual journal entries are real (`/api/v1/journals/manual`, ticket #17); كشف حساب + supplier payables are real (`/api/v1/parties/{id}/statement` + `/api/v1/parties/payables`, ticket #18); receivables + settlement vouchers (سند قبض/صرف) are real (`/api/v1/receivables/*`, ticket #19); ميزان المراجعة + الميزانية العمومية are real (`/api/v1/accounts/trial-balance` + `/api/v1/accounts/balance-sheet`, JSON or A4 HTML via `format=html`, ticket #20); month close + month_open_balances (تقفيل الشهر, `month_open_balances` start-data) are real (`/api/v1/months/*`, ticket #21): `POST /months/{year}/{month}/close` (gated by `months.close`, legacy floor 7 — admin/accountant/manager) snapshots `monthly_close` + seeds the next month's opening debit/credit per account from cumulative `journal_lines` through the end of the closed month (the `monthy\start-data` archive) + audit; a closed month rejects further journal posts at the shared engine (sales/purchases/returns/settlements/manual journals, 409) until a manager (perm ≥7) reopens (`POST /months/{year}/{month}/reopen`) with a reversal audit — re-close regenerates the start-data; `GET /months` (list), `GET /months/{y}/{m}` (detail + next open balances) and `GET /months/{y}/{m}/open-balances` (the FOR-month start-data) are branch-scoped reads open to any authenticated user; opening balances (الأرصدة الافتتاحية, `month_open_balances` cutover, ticket #22) are real (`/api/v1/opening-balances/{year}/{month}`): `POST` (gated by `opening_balances.manage`, legacy floor 7) creates a balanced `journals` entry (source=opening, dated day-before-opening-month so the مزان shows it as افتتاحي) + a `month_open_balances` snapshot for that month, atomically with audit under the branch advisory lock; a target month that is already `closed` or already has an opening rejects 409; `GET` (single period or list) and `DELETE` (manager ≥7, 409 if month closed) are branch-scoped; the مزان and `GET /months/.../open-balances` both reflect the opening (trial-balance `opening_debit/credit` per code and the archive start-data) | #22 |
| API | settings endpoints | not implemented — no branch-settings API exists | #38 |
| API | e-invoice submission (`/api/v1/einvoicing/*`) | status listing + manual resubmit + background submit/poll worker are real (#29); the wire layer is REAL since #30: `app/einvoicing/wire.py` emits the field-perfect eReceipt v1.2 / Invoice v1.0 documents (golden-fixture pinned) and `app/einvoicing/signer.py` attaches the CAdES-BES signature per ITIDA — but B2B invoice/credit-note rows still ride #29's receipt-submission chain (routing them to `documentsubmissions` + taxpayer OAuth is deferred), and preprod sandbox acceptance is gated on Ops delivering the real eSeal X.509; live ETA calls are additionally gated OFF until `PHARMATAG_ETA_SUBMIT_ENABLED=true` + OAuth credentials are configured (preprod hosts via `PHARMATAG_ENVIRONMENT=preprod`) | #30 (transport follow-up) |
| data | CC0 drug catalog download | documented, not bundled — the importer (`server/app/drugs/importer.py`, CLI `python -m app.drugs.importer <file>`) is real and de-dupes/idempotent, but the 24k-medicine source (CC0 `karem505/egyptian-drug-database`) is fetched at import time, not shipped. A sample fixture lives in `server/tests/fixtures/cc0_catalog_sample.csv`. | #8 (shipped) |

Real so far: `/api/v1/auth/*` (login, me, reset-password), `/api/v1/drugs`
(read + CRUD + search-as-you-type + CC0 catalog import; writes gated by
`drugs.manage`), `/api/v1/accounts` (per-branch chart of accounts: tree +
flat list + detail + CRUD; the rev-009 seed builds the hierarchical legacy
tree from the flat chart, writes gated by `accounts.manage` — legacy level ≥ 7
or accountant role — with posting-safety guards on referenced accounts and a
company-wide code/type rule (a branch account for a code in the inherited
chart must keep that code's type); plus
ميزان المراجعة + الميزانية العمومية `/api/v1/accounts/trial-balance` +
`/api/v1/accounts/balance-sheet`, JSON or A4 HTML, open to any authenticated
user — the same code-shadowing aggregation the statement/receivables reads use,
with opening/period/closing columns and the balance-sheet identity
assets = liabilities + equity checked live, equity splitting the opening
retained earnings from the period's own net income),
`/api/v1/users` (user CRUD, roles/permissions, manager password
reset), plugin registry, sales invoicing (create/list/detail/80mm print +
offline outbox replay; gated by `sale.create`; every full sale/return also
issues a tax document atomically — S4.1, ticket #28: per-(branch, kind)
gapless counter + SHA-256 UUID chain + consumer QR replicating the ETA
Integration Toolkit (`app/einvoicing/toolkit.py`, contract-pinned against the
official SDK serialization sample), regime-routed receipt 's' / return
receipt 'r' / B2B invoice 'I' / credit note 'C' per ADR-0002, rows in
`einvoice_log` stay `pending` for the S4.2 submitter within ETA's 24-hour
window, and `GET /api/v1/sales/{id}/tax-document/print` renders the four
legacy templates (ضريبية / مبسطة / أجل / مرتجع) with QR data-URI, RIN block,
counter and VAT-by-rate breakdown), sales returns (partial/full
return of a saved sale — reverses stock via a new return batch + branch_stock,
reverses money/journal/balances at the original prices with a proportional
refund split, snapshots the original into `invoice_versions`, new invoice_no,
offline outbox replay; gated by `sale.create`), purchases (supplier invoice +
new stock batches at net cost, supplier payable + payment splits, balanced
journal + offline outbox replay; gated by legacy level ≥ 2), purchase returns
(partial/full return of a saved purchase — decrements the original purchase
batch + branch_stock, reverses money/AP/payments at the original prices with a
proportional refund split, snapshots the original into `invoice_versions`, new
invoice_no, offline outbox replay; gated by legacy level ≥ 2), parties
(supplier/customer create/list, branch-scoped; gated by legacy level ≥ 4),
stock counting (submit a physical count, manager approve/reject — approval
applies the signed correction to stock_batches + branch_stock atomically with a
balanced 1200↔5900 journal, audit + sync outbox + price_change_log (G12); the
journal is valued at the cost of the units ACTUALLY moved (FIFO take × cost, or
the target batch's cost), the ledger date is the business date in the configured
timezone (`PHARMATAG_TIMEZONE`, default `Africa/Cairo`), and 5900 is an expense
so a deficit debits it while an overage credits it; a count-sheet
`GET /stock/current` lists every branch drug with its system qty and
expiry batches; gated by legacy level ≥ 7 to decide),
`/healthz`, cash drawer + day close (`/api/v1/drawer/movements` + `/day-close`:
every sale / sale-return / purchase / purchase-return payment split lands as a
`drawer_movements` row in the same transaction, manual movements gated by
`drawer.manage` (legacy floor 3), day close computes the drawer equation
`expected = drawer_start + (Σcash_in − drawer_start) − Σcash_out` — the opening
float counts once, via `drawer_start`, never twice — and snapshots the day totals
(net cash/network, manual cash/card, purchases, expenses, COGS, net profit,
VAT, discounts) into `daily_close` per (branch, datee), gated by `day.close`;
`vat_expenses` is snapshotted as 0 — the schema has no expense-VAT source yet
(the expense ledger exists, but the slice writes no expense VAT); reopen is
legacy level ≥ 7 with a reversal + audit, and a closed day rejects
new movements until reopened) — and the report framework (`/api/v1/reports`,
ticket #23: the catalog lives in the `report_catalog` table (rev 015) so later
report slices add rows, not code; `GET /reports` lists active rows (code,
bilingual titles, params, paper), `GET /reports/{code}` renders ANY catalog
entry through one generic engine — JSON by default, `format=grid` for the web
ReportView, or a black-on-white printable page with `format=html&paper=A4|A5`
(`@page` size); `GET /reports/{code}/export?format=xlsx|pdf&paper=A4|A5`
downloads real files — .xlsx via openpyxl (RTL sheet, money cells kept as
exact-decimal strings, never float) and PDF via fpdf2 with the bundled OFL
IBM Plex Sans Arabic + HarfBuzz shaping so Arabic prints shaped on any
machine; a durable branch-scoped print queue (`POST /reports/{code}/print-queue`
enqueue with params snapshot + paper, `GET /reports/print-queue` newest-first,
`POST /reports/print-queue/{id}/done` queued→done exactly once); everything is
branch-scoped and gated by the `reports` permission (admin level-9 or
accountant role). The money reports (ticket #24) share one bucket engine
(`drawer/movements.py`: `day_ledgers` batches four GROUP BY queries per
window, `period_ledger` sums the linear buckets, `day_ledger` = the
single-day window) so the grid, the ranged totals and each day's close can
never disagree — and they reconcile against `journal_lines` (net revenue =
Δ4000, COGS = Δ6000, VAT = Δ2100, drawer-in/out = Δ1000 by source). The v1
reports keep their literal aliases:
`GET /reports/day-profit` (ربح اليوم — net revenue, COGS, expenses, net profit,
VAT, discounts; one day via `datee` or across a period via
`date_from`/`date_to` — no params means the business day, mixing `datee`
with a range is 400),
`GET /reports/day_totals` (الإجماليات اليومية — one row per day with the
payment splits: cash/network sales and returns, manual cash/card, expenses,
supplier payments, expected cash, plus purchases/discounts/VAT/COGS/net
profit per day, totals foot),
`GET /reports/period-totals` (ملخص المبيعات والمشتريات — counts + totals per
sale/return/purchase/return kind over a date range, returns netted),
`GET /reports/stock-minimum` (النواقص — drugs below the reorder point, shortage
= minimum − qty, sorted desc), `GET /reports/drawer-handover` (تسليم الدرج —
per-cashier opening/cash/card/returns/expenses/net over a period) — plus manual journal entries (`/api/v1/journals/manual`:
a `journals.manage` holder (admin, accountant, or manager role — legacy level ≥ 7)
posts a dated, described, balanced قيد riding the journal engine (journal +
balanced lines + balances + audit + a `manual_journal_entries` reference,
atomic under the branch advisory lock, entry numbers monotonic per branch/datee);
imbalanced entries, single-line, zero, negative, and double-sided lines, blank
descriptions, and unknown or deactivated accounts are all 400 with nothing
half-written; list/detail are branch-scoped reads open to any authenticated user;
`POST /manual/{id}/reverse` posts the opposite-signed balanced reversal journal
linked via `reverses_entry_id`, A07-style — reversing a reversal is 409) —
plus كشف حساب and supplier payables (`/api/v1/parties/{id}/statement` +
`/api/v1/parties/payables`: a party's AR/AP ledger built purely from
`journal_lines` — customers run on AR (debit-positive), suppliers on AP
(credit-positive), `kind='both'` defaults to AR with a `side` override; opening
balance = the party's lines before the period, movements carry a running
balance, closing = opening + movements; period is month/year (canonical, like
the legacy monthe/yearo) or a date range — passing both or an inverted range is
a 400; reads are branch-scoped and open to any authenticated user, JSON by
default and a black-on-white A4 page with `format=html`) — plus receivables
and settlement vouchers (`/api/v1/receivables/*`: a `receivables.manage` holder
(admin, manager, or accountant role — legacy level ≥ 7) posts a سند قبض
(receipt: Dr cash/network, Cr AR) or سند صرف (payment: Dr AP, Cr cash/network)
as a dated, described, balanced journal riding the journal engine with a
`settlement_vouchers` reference row + drawer movement atomically under the
branch advisory lock, entry numbers monotonic per branch/datee; `method=card`
lands as a `network` drawer movement; receipts reduce a customer's AR statement
balance and payments a supplier's AP payable, overpayment goes negative
(advance) in the register; `POST /vouchers/{id}/reverse` posts the
opposite-sided reversal journal pinned to the same AR/AP accounts — reversing a
reversal is 409; credit sales check the customer's `credit_limit` (0 =
unlimited) in the sale's own transaction, so a sale can never push the AR debt
past the limit; voucher list/detail + `GET /receivables` (customers sorted desc
  by debt, with totals, JSON or A4 HTML) are branch-scoped reads open to any
authenticated user) — plus month close + month_open_balances (`/api/v1/months/*`: `POST /months/{year}/{month}/close` — `months.close` (admin/accountant/manager, legacy floor 7) snapshots `monthly_close` + seeds the next month's opening per-account debit/credit from cumulative `journal_lines` and writes an audit; `POST /months/{year}/{month}/reopen` — manager (perm ≥7) flips to `reopened` + audit so the month can accept new posts and be re-closed (re-close regenerates the start-data); a closed month rejects every journal post (sale/purchase/return/settlement/manual/journal correction) at the engine with 409; `GET /months` + `GET /months/{y}/{m}` + `GET /months/{y}/{m}/open-balances` are branch-scoped reads open to any authenticated user) — plus opening balances (`/api/v1/opening-balances/{year}/{month}`: `POST` — `opening_balances.manage` (floor 7) balanced entry per account/branch (cash/stock/receivables/payables — idx 8482-8485) as `journals` source=opening dated day-before-opening-month + `month_open_balances` snapshot, atomic + audit + branch lock; 409 if period already has opening or target month closed; `GET` (single/list) open to any authenticated user, `DELETE` manager ≥7; trial-balance `opening_debit/credit` and the archive `open-balances` both reflect the cutover) — plus the branch registry (S5.1, ticket #31: `/api/v1/branches` — list open to any authenticated user; create/edit/soft-delete + identity-map attach/list/detach gated by `branches.manage` (rev 026, admin+manager, legacy floor 7); new branches are always sub devices, the single-main-device invariant (legacy ismaster.txt) is enforced with an atomic `POST /branches/{id}/promote` role transfer under a global advisory lock; the main device can never be deactivated; `branch_identities` maps legacy (table, column, value) aliases — phar/pharmacyid/mobile — to one canonical branch via `resolve_branch` (the seam chain replay #34/#35 calls); every mutation writes audit + `entity='branch'` outbox rows atomically for peer convergence) — plus inter-pharmacy transfers (S5.2, ticket #32: `/api/v1/transfers` — the `titaninn` transfer table rebuilt as core rev 027 (`transfers` + `transfer_lines`, parity skip-list updated per T1/ADR-0002 precedent); state machine `draft → dispatched → received` with draft-only cancel, delivery state tracked on the header; `POST` drafts an outbound from the caller's branch (per-source monotonic `transfer_no` under a branch advisory lock + UNIQUE backstop, `legacy_fatid` ETL passthrough), `POST /{id}/dispatch` — source branch only — decrements source batches + branch_stock under FOR UPDATE with FEFO-suggested or client-nominated explicit allocations snapshotted to `alloc_json` for replay-exact receive; `POST /{id}/receive` — target branch only — lands per-line `received_qty ≤ sent_qty` as `typee='transfer_in'` lots at preserved cost/expiry VERBATIM (one lot per sent lot — expiry never merged) and auto-returns any shortfall to the exact source batches (`transfer_shortage_return` audit); `POST /{id}/cancel` by either party while draft; writes gated by new `transfers.manage` (rev 027 seed to admin/pharmacist/manager, legacy floor 3) + T7 branch authority, reads branch-scoped to participating branches; every transition writes audit + `entity='transfer'` outbox rows for BOTH branches atomically; no GL posting in this slice (T3 — stock value stays on the source book until the transit-account ledger decision)) — plus the web +
desktop **الأدوية** screens, the web forced-reset
(first-login) and voluntary change-password flows (ticket #37).

## 7. CI

`.github/workflows/ci.yml` runs on push to `main` and pull requests:

- **API job**: Python 3.14 + `pip install -r server/requirements-dev.txt`, spins up a
  `postgres:16` service container, `alembic upgrade head` on the fresh DB, schema twin
  parity check, then `pytest tests -q`.
- **Frontend job**: Node 24 + pnpm `--frozen-lockfile`, then `pnpm lint`, `pnpm typecheck`,
  `pnpm test`, `pnpm build`.