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

## 6. Known stubs (not finished work)

Keep this inventory honest: a screen/endpoint listed here is a **placeholder**, not
a shipped feature. Slices replace entries as they land; agents must update this
list in the same commit as the work (add when a placeholder is created, remove
when a slice replaces it). Where a placeholder is already tracked on the issue
tracker (TAGOOZ/PharmaTag) the **Ticket** column names it — the row stays until
the ticket ships.

| Area | Item | Status | Ticket |
| --- | --- | --- | --- |
| web `/pos` `/purchases` `/stock` `/money` `/reports` `/employees` | module screens | stubs — show "built in the corresponding slice" | #38 |
| web `/settings` | module screen | change-password form works (ticket #37); the rest of the settings module is a stub | #38 |
| web `/` | dashboard (home) | stub — static shell, today-summary not wired | #38 |
| desktop | module screens (`App.tsx` STUBS) | stubs — same as web | #38 |
| desktop | login / sync / branch bootstrap | not implemented — SQLite is seeded directly | #39 |
| API | money, reports endpoints | drawer + day close are real (`/api/v1/drawer/*`, ticket #14); reports + the rest of the money API remain stubs | #14 (S2/S3 slices later), #15 |
| API | settings endpoints | not implemented — no branch-settings API exists | #38 |
| data | CC0 drug catalog download | documented, not bundled — the importer (`server/app/drugs/importer.py`, CLI `python -m app.drugs.importer <file>`) is real and de-dupes/idempotent, but the 24k-medicine source (CC0 `karem505/egyptian-drug-database`) is fetched at import time, not shipped. A sample fixture lives in `server/tests/fixtures/cc0_catalog_sample.csv`. | #8 (shipped) |

Real so far: `/api/v1/auth/*` (login, me, reset-password), `/api/v1/drugs`
(read + CRUD + search-as-you-type + CC0 catalog import; writes gated by
`drugs.manage`), `/api/v1/users` (user CRUD, roles/permissions, manager password
reset), plugin registry, sales invoicing (create/list/detail/80mm print +
offline outbox replay; gated by `sale.create`), sales returns (partial/full
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
new movements until reopened) — and the web + desktop **الأدوية** screens, the web forced-reset
(first-login) and voluntary change-password flows (ticket #37).

## 7. CI

`.github/workflows/ci.yml` runs on push to `main` and pull requests:

- **API job**: Python 3.14 + `pip install -r server/requirements-dev.txt`, spins up a
  `postgres:16` service container, `alembic upgrade head` on the fresh DB, schema twin
  parity check, then `pytest tests -q`.
- **Frontend job**: Node 24 + pnpm `--frozen-lockfile`, then `pnpm lint`, `pnpm typecheck`,
  `pnpm test`, `pnpm build`.