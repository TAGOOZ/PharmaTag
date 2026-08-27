# ADR-0003: S5.5 chain-stock projection + per-branch minimum (titanksastock → branch_stock)

Date: 2026-08-27 · Status: Accepted · Informs: #35 (S5.5) · Research: Compuscope Egypt pharmacy-ERP chain overview (2024), NeptonTech multi-branch stock sync note (2023), Azure Architecture Center — Offline-first LWW/CQRS pattern (docs.microsoft.com, 2024), Odoo Inventory — Reordering Rules / minimum stock (odoo.com/docs, 2024), Pharmasync chain-shortage dashboard teardown (2024)

## Context

S5.5 must replace the legacy `titanksastock` per-chain stock-snapshot table (8-col
`id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock` — SCHEMA_RESOLVED §2,
raz_complete.md §8, 3 live CREATE+INSERT fragments) with the single-source `branch_stock`
projection already used for shortages (A06). Open questions left unpinned by `#35`:

* Is the chain view a synced table or a live projection?
* Where does `minimum` live, how is it edited, who may edit it, how is it validated?
* How does a minimum change propagate offline (outbox, replay, idempotency)?
* Which filters/sorts does the cross-branch snapshot need, and which branches/drugs are visible?
* Is there any GL / value posting when viewing chain stock?
* How do existing stock mutations (sale, purchase, returns, transfers) keep the chain view fresh?
* How do the SQLite twin and desktop bundle stay in sync?

Legacy `titanstock`/`titanksastock` were both updated on every ModStock side-effect
(purchase increments, sale decrements, `CorrectStockForAll`, `Transfer`), but the network
modules (`ModNetwork`, `ModInn`) then re-replicated the 8-col rows by GUID insert loops —
duplicative and not the canonical qty (SCHEMA_EVALUATION §1.3#7: `titanstock` is the
authoritative qty; `branch_stock.qty` is that qty collapsed from `stock_batches`).

## Decisions

1. **Q1 — Projection, not a synced table (A06 precedent).** The chain snapshot is a
   read-only projection over canonical `branch_stock` regenerated on demand — never a
   second table to sync. Mirrors `titanksasales → chain_sales` (S5.4) and avoids the
   dual-write drift that plagued `titanksastock`/`titanstock`. Legacy's `silsilaid`/`classy`
   columns survive on `branch_stock` for traceability but the 8-col replication is dead.

2. **Q2 — `minimum` is the per-branch reorder point, editable and independently LWW.**
   `branch_stock.minimum` carries the threshold (`titanksastock.minimum`, reports RPT-ST03
   `WHERE stock < minimum`). `PATCH /stock/minimum` sets it for `(caller_branch, drug_id)`:
   creates the `branch_stock` row with `qty=0` when absent, validates exact-decimal 4dp
   (`money.dec`/`round4`), non-negative, rejects NaN/Infinity/overflow (`≥10¹⁴`), and writes
   `audit_log(field=minimum)` + `sync_log(entity=branch_stock, payload {branch_id,drug_id,qty,minimum,silsilaid,classy})`
   atomically under the per-branch advisory lock (G12). Value stays 4dp string on the wire.

3. **Q3 — Permission `stock.manage`, legacy floor 3.** One granular code `stock.manage`
   (إدارة المخزون) gates minimum edits, seeded to `admin/pharmacist/manager` (`roles 1,2,5`)
   and covered by the stock-area legacy floor `permission_level ≥ 3` (same tier as
   `stock.adjust`/`transfers.manage`/`drugs.manage`). Reads (`GET /stock/cross-branch` and
   the `chain_stock` report) are authenticated-only, no granular gate — every staff member
   may reconcile chain shortages (Compuscope's chain dashboards are read-open; NeptonTech's
   "every cashier sees sister stock").

4. **Q4 — Branch-stock outbox is absolute-value LWW, idempotent and complete.** Payloads
   carry absolute `qty` (+ optional `minimum` after Q2) so last writer wins and re-apply
   is a no-op. Replay (`app/sync/service.py`) creates the row when missing, updates
   `qty`/`minimum`/`silsilaid`/`classy` independently (partial payloads for stock-only vs
   minimum-only writes), and stamps `lastedit=now()`. A missing `Drug` records `failed`
   (G10, never silently dropped). Rev 034 enqueues from **every** stock mutation site:
   sale decrement, sale-return increment, purchase increment, purchase-return decrement,
   transfer dispatch+receive (+ shortfall auto-return), and minimum edits — so the
   projection converges even when a branch is offline (Azure offline-first LWW pattern).

5. **Q5 — Chain-stock report shape (RPT-ST03 parity).** `app/reports/chain_stock.py`
   enumerates `branch_stock ⨝ branches ⨝ drugs` where `branches.is_active` and
   `drugs.active`, computes `shortage = greatest(minimum - qty, 0)` (4dp), sorts
   `shortage DESC, drugname ASC, pharmacyid ASC` (Pharmasync's shortage-first board;
   Odoo's "ordered by virtual shortage"), caps at 1000 rows with `count` whole-range +
   `truncated` flag, foot stays whole-chain. Grid columns: الفرع / الصنف / الباركود /
   الرصيد / الحد الأدنى / العجز, read-only, no journal/stock/outbox writes. Row also
   surfaces `silsilaid`/`classy`/`lastedit` for the cross-branch API but the grid hides them.

6. **Q6 — Cross-branch API filters and RBAC.** `GET /stock/cross-branch` (S5.5 #35)
   supports `drug_id`, free-text `q` across `drugname/drugnamear/generic/barcode`
   (barcode via `drug_barcodes` subquery — Odoo's multi-barcode lookup), `only_shortage
   (= qty < minimum)`, and `include_inactive` (default excludes `!is_active` branches and
   inactive drugs; callers needing audit history opt in). Sorted identically to the
   report; capped 1000 with `count/truncated`; returns parallel `pharmacyid/pharname`,
   `barcode` (primary preferred), `qty/minimum/shortage` as 4dp strings. No permission
   gate beyond `get_current_user` — shortage detection is a daily cashier workflow.

7. **Q7 — No GL posting (T3 precedent).** Viewing or editing chain stock never posts
   a journal: quantities move via `stock_batches`/`branch_stock` (FEFO allocations,
   preserved cost/expiry on transfers), stock VALUE stays on the source book per
   per-branch COA. The projection is a quantity snapshot, not a valuation — a
   transit-account / valuation ledger remains a dedicated future decision (same gate
   as transfers T3, triggered when a chain customer reconciles per-branch ميزان stock values).

8. **Q8 — Twin parity and bundle.** PG rev `034_stock_chain_snapshot` seeds
   `stock.manage` + `chain_stock` catalog row (`chain`, sort 210, `A4`, `[]` params).
   SQLite twin `034_stock_chain_snapshot.sql` mirrors the same two seeds; the
   desktop bundle `schema/schema_sqlite.sql` (= `apps/desktop/src/resources/schema_sqlite.sql`)
   is **unchanged** for this slice — `report_catalog` is data, not schema, so
   `parity_check.py` (tables/columns/constraints only) stays `PARITY OK` without a
   rebuild, matching the twin design for all `chain_*` catalog rows (033/034) and
   for earlier permission-only seeds (026, 031). Offline chain-stock reads are
   local `branch_stock` rows after sync replay — no extra ATTACH file.

## Consequences

- `stock.manage` appears in `permissions`/`role_permissions`; `report_catalog` gains
  `chain_stock` (inert until `app/reports/views.py` registers it — done in this slice).
- `branch_stock` gains no columns; `minimum` semantics and `lastedit` were already present.
- Every sale/purchase/return/transfer path now carries a trailing `enqueue_sync`
  (`branch_stock`) inside the same `atomic()` as its audit row — G12 preserved, replay
  stays idempotent.
- Offline peers converge: a minimum raised on branch A while B is offline lands on B as
  an absolute write after replay; concurrent minimum edits on both sides resolve LWW
  (last outbox delivery wins, not timestamp merge).
- The 8-col `titanksastock` and its GUID replication are retired for this feature;
  future imports (Phase 6 S6.4) mapping `titanksastock → branch_stock` stay 1:1 on
  `(pharmacyid→branch_id, drugname→drug_id, stock→qty, minimum→minimum)`.

## Alternatives considered

- **Keep a synced chain table** — rejected: doubles the store of record and reintroduces
  the `titanstock` vs `titanksastock` drift the schema fix (SCHEMA_RESOLVED §2) removed;
  a projection is cheaper and always consistent with `branch_stock`.
- **Central `minimum` table keyed by drug only** — rejected: reorder points are branch-
  specific; Aswan's sell-through and Cairo's are not comparable (Compuscope multi-site
  study: per-site par levels vary 3×).
- **Gate reads by `stock.manage`** — rejected: NeptonTech field notes and Compuscope chain
  UX both show shortage checks as a cashier/clerk task; restricting reads would push staff
  to informal spreadsheets.
- **Delta-quantity outbox** (`+3`/`−2`) — rejected: not idempotent; absolute LWW survives
  duplicate delivery and out-of-order replay (Azure LWW guidance for inventory shadows).
- **Valuation in the chain grid** — deferred: per-branch COAs make a single mixed-branch
  journal impossible without a transit account; shipping a quantity-only snapshot first
  avoids blocking S5.5 on an unsettled ledger design (Odoo separates `stock.quant` from
  `account.move` for the same reason).

## References

- Compuscope — Egypt pharmacy chain ERP overview: chain inventory distribution, per-site
  minimums, daily replenishment cadence (2024).
- NeptonTech — Multi-branch stock synchronisation (blog, 2023): visibility of sister-
  pharmacy stock, last-write-wins replication.
- Microsoft Azure Architecture Center — Offline-first app pattern: outbox + LWW conflict
  resolution, idempotent replay (2024).
- Odoo Inventory Documentation — Reordering Rules (minimum / maximum stock, per-warehouse)
  and stock projection vs accounting separation (2024).
- Pharmasync — Chain shortage dashboard teardown: shortage-first sorting, cross-branch
  stock lookup UX (2024).
