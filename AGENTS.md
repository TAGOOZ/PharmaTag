# AGENTS.md

## Agent skills

### Issue tracker
GitHub issues on TAGOOZ/PharmaTag via the `gh` CLI (pass `--repo TAGOOZ/PharmaTag` explicitly — the repo is also the code repo). **Read issues via the REST API (`gh api repos/TAGOOZ/PharmaTag/issues/N`) — NOT `gh issue view`, whose GraphQL path fails on this repo.** See `docs/agents/issue-tracker.md`.

### Triage labels
Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs
Multi-context: CONTEXT-MAP.md at root points to per-context CONTEXT.md files. See `docs/agents/domain.md`.

### TDD
Test-driven development via the `tdd` skill. Use it for every slice that has logic to verify (money, stock, events, ETA, reports). See `docs/agents/tdd.md`.

### System design patterns
The patterns & standards the codebase follows (router→service layering, G12 atomic audit+outbox, transactional outbox + idempotent replay, advisory-lock numbering, twin parity, events, RBAC). Read it before building or extending a feature seam. See `docs/agents/patterns.md`.

## Getting started for agents

Before touching any code or filing anything, read in this order:

1. `plan/00_decisions_master.md` — the single authority for every locked decision (G/A/P/X tables: ETA standard, VAT rules, offline/LWW, permissions, plugins, brand). Treat it as the provisional domain source until `CONTEXT.md` files exist.
2. `plan/10_timeline_tasks.md` — phase durations and task ordering (P0→P6).
3. `plan/05_slicing_plan.md` — the vertical-slice discipline every ticket follows.

Each ticket on the tracker (TAGOOZ/PharmaTag) is self-contained (what + acceptance criteria + blocked-by) and lists its `**References:**` (plan docs) at the bottom.

**Picking work:** grab any open issue labeled `ready-for-agent` whose `**Blocked by:**` is `None` or fully closed. Do not work around a blocker.

**Working discipline (non-negotiable, from plan/00):**
- Every money/stock mutation writes its `audit_log` row in the same transaction (plan/00 G12, `invoicedata` = one row per invoice line).
- Money is exact-decimal; VAT-inclusive net = total ÷ 1.14 with per-line `tax_type` (exempt/5%/14%).
- Offline-first: writes enqueue `sync_log` outbox rows atomically; conflicts are LWW + recorded, never lost.
- Legacy `permission_level` 1–9 plus granular permission rows; day-close reopen requires perm ≥7 with reversal + audit.
- **Edge-case pass before every close:** after ACs are green, enumerate + test the slice's edge cases (empty/missing data, dupes, boundary values, auth/permission failures, offline/API-down, and for money/stock: rounding, zero/negative qty, concurrency, atomic audit+outbox, idempotent replay) and fix what the tests expose. Full checklist in `docs/agents/issue-tracker.md`. List covered cases in the close comment.
- **Known-stub inventory (README §6):** keep it current in the same commit as the work — add a row when you create a placeholder screen/endpoint, remove it when your slice replaces a stub with real functionality. Never present a stub as shipped.
- **Small, task-specific files (SRP / separation of concerns):** no big god-modules or giant files. Each file owns one specific job — a router per resource, a service per feature/use-case, a dedicated module per job (e.g. money, audit, importer, rbac) — with high cohesion and low coupling. Split when a file grows past a single clear responsibility; prefer several small focused files over one long one so future agents and maintainers can navigate and reason about each piece in isolation.

**Testing discipline (tdd skill):**
- Every slice with logic to verify is built test-first: RED→GREEN→refactor, one test → one implementation, repeated vertically (tracer bullets). No horizontal "write all tests then all code."
- Tests verify behavior through public interfaces — integration-style, reads like a spec; they must survive internal refactors. No mocking collaborators just to isolate internals; no testing private methods.
- Money/stock/ETA slices carry invariant tests (e.g. SUM debit = SUM credit, journal balanced, audit + outbox rows written atomically).
- Never refactor while RED. Confirm with the user which behaviors matter most before writing tests.

**Where code lives:** this workspace (project root `testTLS/`) IS the repo — its clone is `TAGOOZ/PharmaTag` (push/pull there; `TITAN.W1B.exe` is gitignored). Legacy corpus: `titan_extract/`, `titan_decompile/`, `legacy_import/`. Schema drafts: `schema/`. Build details per ticket references. The monorepo scaffold is built by tickets T01/T04 on top of this initial commit.

**Local throwaway Postgres DBs (recurring agent failure — READ BEFORE CREATING ONE):**
- There is NO postgres superuser password on this machine. Do NOT try `sudo -S -u postgres psql` interactively; it is not needed.
- The `pharmatag_test` role has CREATEDB, so create/drop throwaway DBs directly and non-interactively:
  - `PGPASSWORD=pharmatag_test createdb -h localhost -U pharmatag_test -T template0 <name>`
  - `PGPASSWORD=pharmatag_test dropdb -h localhost -U pharmatag_test <name>`
- The collation-version `HINT` printed by `createdb` is a WARNING, not an error — exit code 0 means success. Proceed.
- Migrate the throwaway DB with `PHARMATAG_DB_URL="postgresql+psycopg://pharmatag_test:pharmatag_test@localhost:5432/<name>" .venv/bin/alembic upgrade head` (run from `server/`).
- Alternative (if a superuser is ever required, e.g. for an extension): `printf 'Mustafa_Mu@@@\n' | sudo -S -u postgres psql -c "CREATE DATABASE <name> TEMPLATE template0"` — but you shouldn't need it for tests.

**Conventions:** decisions change only via `plan/00_decisions_master.md` (append, don't rewrite history); plans are reconciled, not regenerated; research claims cite sources.