# ADR-0001: Single VAT account with derived input/output direction

Date: 2026-08-23 · Status: Accepted · Informs: issue #44, enables #27 (S3.5 tax summary)

## Context

Egyptian VAT returns (Form 10, نموذج 10 ق.ض.ق.م) require output VAT (ضريبة المخرجات) and
input VAT (ضريبة المدخلات) presented separately per rate. The chart of accounts seeds a single
`2100` VAT account; every journal since day one posts against it — sale legs credit `2100`,
purchase legs debit it, returns post the opposite side of their kind.

Two ways to make reports present output vs input:

1. **Split the chart** into e.g. `2100` (output) + `2105` (input) now.
2. **Keep one account and derive direction** from journal provenance (`source` + invoice kind).

## Decision

Option 2. The tax summary reads `journal_lines` on `2100` filtered by the joined journal's
source: `sale`/`sale_return` → output side; `purchase`/`purchase_return` → input side.
Rate-level breakdowns come from `invoice_lines.tax_type` (exempt / 5% / 14%), never from the
chart. The report presents output and input as separate sections whatever the ledger structure.

## Consequences

- No historical migration: every posted journal keeps its account row; opening balances,
  month closes, and the SQLite twin stay untouched.
- Reversible: if a split is ever mandated (e.g. an accountant demands separate GL control
  accounts), lines migrate deterministically by source — the report shape does not change.
- The summary must always be reconciled against the `2100` delta in tests so a mis-derived
  direction cannot ship silently.
- Egyptian pharmacy fit: output is mostly exempt (medicines, G06), so a heavyweight chart
  split buys little today while costing migration risk now.

## Alternatives considered

- **Split now** — cleaner GL semantics for large mixed-tax retailers; rejected because the
  historical backfill (by source) plus seeds/twin/opening-balance churn outweighed the benefit
  for this market segment, and nothing in ETA Phase 4 requires it.
