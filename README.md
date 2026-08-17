# PharmaTag فارما تاج

Monorepo: Next.js web shell (`apps/web`), Tauri 2 desktop app (`apps/desktop`), shared UI/tokens (`packages/ui`), and a FastAPI core server (`server/`) with a PostgreSQL (Alembic) ↔ SQLite twin schema.

## Prerequisites

- **Node.js ≥ 20** (developed on 24) + **pnpm 10.14.0** (`corepack enable pnpm` or `npm i -g pnpm@10.14.0`)
- **Python ≥ 3.12** (developed on 3.14) + `python3-venv`
- **PostgreSQL ≥ 16** running locally

## 1. PostgreSQL

Create the test role/database (names are the defaults `server/app/core/config.py` expects):

```bash
psql -U postgres <<'SQL'
CREATE ROLE pharmatag_test LOGIN PASSWORD 'pharmatag_test';
CREATE DATABASE pharmatag_test OWNER pharmatag_test;
SQL
```

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

The web page logs in with the seed user and fetches
`GET /api/v1/drugs` (Bearer token) → `{ "branch": {id, pharmacyid, pharname},
"drugs": [{id, drugname, drugnamear, generic, classy, co, units, unitsmall,
price, price_now, tax_type, vat, active}] }`, scoped to the caller's branch.
The desktop never calls the API — `initDb()` seeds its local SQLite with the
same `003_drug_seeds` rows on first run and renders the identical list offline.

## 6. CI

`.github/workflows/ci.yml` runs on push to `main` and pull requests:

- **API job**: Python 3.14 + `pip install -r server/requirements-dev.txt`, spins up a
  `postgres:16` service container, `alembic upgrade head` on the fresh DB, schema twin
  parity check, then `pytest tests -q`.
- **Frontend job**: Node 24 + pnpm `--frozen-lockfile`, then `pnpm lint`, `pnpm typecheck`,
  `pnpm test`, `pnpm build`.