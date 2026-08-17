# Agent skill: system design — patterns & standards

The PharmaTag codebase follows the patterns big tech uses for money/stock
systems. Keep them in mind when building a slice; when in doubt, match an
existing seam instead of inventing a parallel one. Cross-reference the 
`plan/00_decisions_master.md` tables (G/A/P/X) — those are the *what*, these are
the *how*.

## Layered router → service → core

- A **router per resource** (`app/<domain>/router.py`) — thin: request parsing,
  authz dependency, response shaping. No business logic.
- A **service per use-case** (`app/<domain>/service.py`) — orchestrates the
  use-case. Split into focused modules once a file grows past one job
  (e.g. `app/sales/{service,builder,pricing,payments,payload,replay}.py`,
  `app/sales/{journal,numbering,stock}.py`).
- **Core primitives in dedicated modules** (`app/core/money.py`, `audit.py`,
  `db.py`, `events.py`) — shared, invariant-bearing, low-level. No feature code
  reaches into a peer feature's internals.

## Money & stock invariants (non-negotiable)

- Exact `Decimal` everywhere; round half-up to 2dp (totals) / 4dp (unit cost).
  All canonical money flows through `app/core/money.py`.
- **G12 atomicity:** every mutation writes its `audit_log` row AND enqueues its
  `sync_log` outbox row in the SAME transaction via `atomic()` — mutation,
  audit, and replication intent live or die together.
- **Transactional outbox + replay:** writes never call remote stores inline;
  they enqueue a JSON-primitive payload, and `sync.replay_pending` applies it
  idempotently (dedupe via unique keys like `uq_invoices_branch_no`). Replays
  reproduce exact batches/costs — they never re-run heuristics like FIFO.
- **Invariant tests** ride along every money/stock slice: journal balanced
  (SUM debit = SUM credit), header reconciles to the per-line VAT engine,
  audit + outbox rows land atomically, stock never goes negative.

## Concurrency & numbering

- **Advisory lock per branch** serializes numbering and intra-branch writes
  (`app/sales/numbering.acquire_branch_lock`).
- `SELECT ... FOR UPDATE` on the rows being decremented prevents oversell under
  parallelism; verified by a concurrent-sale test.
- Unique constraints (`uq_invoices_branch_no`, `uq_journals_entry`,
  `uq_stock_batches`) are the backstop that makes replay/concurrency safe.

## Events

- **Two-phase in-process bus** (`app/core/events.py`): `IN_TXN` handlers run
  inside the transaction, `AFTER_COMMIT` only after it commits. Plugins attach
  to the `sale.saved` seam via this bus — never by editing core.

## RBAC

- Legacy `permission_level` 1–9 PLUS granular `permissions` rows. Enforced
  centrally in `app/auth/rbac.py` (`require_permission`, `require_level`);
  every write endpoint depends on it via FastAPI dependency injection.
- Access tokens are stamped with `kind: access`; refresh tokens are rejected as
  bearer credentials.

## Twin parity guard

- The canonical schema lives in alembic; a SQLite twin mirrors it for the
  offline desktop app. Every migration updates BOTH, and
  `server/scripts/parity_check.py` proves table/column parity in CI.

## Small files over big ones

- A file owns one job (see SRP rule in AGENTS.md). The `models` package is
  one domain per module with a re-exporting `__init__.py` so `from app.models
  import X` keeps working. Tests mirror the app: one themed file per concern,
  shared helpers in a `tests/<domain>_utils.py`.