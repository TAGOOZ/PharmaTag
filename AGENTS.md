# AGENTS.md

## Agent skills

### Issue tracker
GitHub issues on TAGOOZ/PharmaTag via the `gh` CLI (pass `--repo TAGOOZ/PharmaTag` explicitly — the repo is also the code repo). See `docs/agents/issue-tracker.md`.

### Triage labels
Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs
Multi-context: CONTEXT-MAP.md at root points to per-context CONTEXT.md files. See `docs/agents/domain.md`.

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

**Where code lives:** this workspace (project root `testTLS/`) IS the repo — its clone is `TAGOOZ/PharmaTag` (push/pull there; `TITAN.W1B.exe` is gitignored). Legacy corpus: `titan_extract/`, `titan_decompile/`, `legacy_import/`. Schema drafts: `schema/`. Build details per ticket references. The monorepo scaffold is built by tickets T01/T04 on top of this initial commit.

**Conventions:** decisions change only via `plan/00_decisions_master.md` (append, don't rewrite history); plans are reconciled, not regenerated; research claims cite sources.