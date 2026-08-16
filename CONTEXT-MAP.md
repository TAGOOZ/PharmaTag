# CONTEXT-MAP.md

PharmaTag فارما تاج is a multi-context monorepo. Each context owns one `CONTEXT.md` (domain language + glossary) and `docs/adr/` for context-scoped decisions; system-wide ADRs live in `docs/adr/` at the root.

> **Scaffold status:** the monorepo layout below is planned (see `plan/03_frontend_plan.md`, `plan/08_app_architecture_plugins.md`). CONTEXT.md files are created lazily as code lands (per `/grill-with-docs`); plan and decision docs live in `plan/` until then. Root ADR-0001 will be seeded from `plan/00_decisions_master.md`.

| Context | Path | Domain |
|---------|------|--------|
| Core (domain truth) | `packages/core/CONTEXT.md` | Money/stock/ledger truth, audit, sync outbox, rounding, VAT/tax_type |
| Desktop (offline twin) | `apps/desktop/CONTEXT.md` | Tauri + SQLite offline store, POS, printers |
| Web client | `apps/web/CONTEXT.md` | Next.js client-rendered dashboards |
| Plugin: ETA | `plugins/eta/CONTEXT.md` | Egyptian e-invoicing / eReceipt (ETA), CAdES-BES, counters |
| Plugin: Ledger | `plugins/ledger/CONTEXT.md` | Chart of accounts, month/year close, receivables, trial balance |
| Plugin: Chain | `plugins/chain/CONTEXT.md` | Branch registry, transfers, needs/orders, LWW sync |
| Plugin: Reports | `plugins/reports/CONTEXT.md` | Report framework + RPT catalog |