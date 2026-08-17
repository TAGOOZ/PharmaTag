# 01 — Database & Data-Model Plan (FINAL)

**Role:** DB architect adjudication of the TITAN.W1 rebuild data model.
**Canonical sources (authority order):** `titan_extract/SCHEMA_EVALUATION.md` (primary spec, §1.1–1.12, §2, §3) → `titan_extract/SCHEMA_RESOLVED.md` (11 adjudications, adopted) → `titan_extract/schema_complete.sql` (28 legacy tables, ground truth) → `titan_extract/PHY_MIGRATION.md` + `titan_extract/RECORD_LAYOUTS_daily_phy.md` → `titan_extract/GAPS_REPORT.md` → `schema/schema_design.md`, `schema/schema_postgres.sql`, `schema/schema_sqlite.sql` (drafts under review).
**Citation caveat honored:** all feature-doc `strings_*.txt:N` refs are read as `N+3`; `schema_complete.sql` and `titan_decompile/` beat feature-doc DDL claims when they conflict.
**Status:** PLANNING. No code written. Every column decision below is final for Phase 1; the §6 open questions are resolved against `plan/00_decisions_master.md` (see the Reconciled note below).

## Reconciled 2026-08-16

Reconciled against **`plan/00_decisions_master.md`** (the locked-decision authority).
- **A08 — schema-per-plugin (PostgreSQL).** Core owns the `public` schema; plugin-owned tables ship in per-plugin schemas via their own migrations (`search_path`-registered). `einvoice_log`/`einvoice_counters` → `eta`; `monthly_close`/`month_open_balances` → `ledger`; `transfers`/`transfer_lines`/`needs`/`purchase_orders`/`branch_registry`/`drug_sync_outbox` → `chain`; `chain_buy_orders`/`dead_stock_exchange` → `logistics`; `drug_interactions` → `doctors`; `external_drug_catalog` → `drugdb`; `archive_imports`/`archive_exports` → `tools`; `user_drawer_money` → `hr`. Report catalog (`reports`) and receivables tables ship with their plugins. **Core Alembic rev 001 ships only the core truth tables (money/stock/audit/sync + auth/drug-master/parties) + the plugin host** (`app_plugins`, `plugin_dependencies`, `plugin_branch_grants`, `plugin_settings`) **+ core seeds** — not the full 51. SQLite offline twin: no plugin schemas → per-plugin ATTACHed SQLite files (`p_` prefix fallback). Consistent with `plan/08_app_architecture_plugins.md` §2.2.
- **G06 — VAT per-line `tax_type`.** Drug master + `invoice_lines` carry `tax_type` ∈ {exempt / 5% / 14%}; medicines VAT-exempt, medical devices 5%, other goods 14% (Egypt standard). VAT-inclusive retail; taxable lines split `net = total ÷ 1.14`. `branches.vat_inclusive_prices` flag.
- **G07 — invoice numbering.** Internal per-branch monotonic `invoice_no`; `UNIQUE(branch_id, invoice_no)`; returns are new documents.
- **§6:** open questions #1–#12 marked resolved (→ G01, A01, G12+G02, G07, G05/G04, A15, G08, A16, A04, G09, A17, A18). A02/A05/A19 also confirmed and reflected (expiry-FIFO COGS configurable; server-owned rounding §4; P1 single drawer + treasury toggle).

---

## 1. Verdict on `schema/schema_design.md` + DDL drafts

### 1.1 Verdict

**ADOPT the design, with 8 surgical corrections.** The draft is the correct response to SCHEMA_EVALUATION: it fixes all 12 §1 flaws (branch dimension everywhere money/stock lives, batch/expiry inventory, branch-identity map + sync outbox, per-branch accounting trees, `.phy` migration targets, audit-everything, approvals, shortages, e-invoice state, money typing, surrogate + preserved natural keys) and covers all 28 legacy tables plus every `.phy` money/state file. It is self-contained (51 tables, no dangling FKs; under A08 the plugin-owned subset now ships in per-plugin schemas — see §3). The remaining problems are precision bugs and one internal contradiction — none is structural.

### 1.2 What is SOLID (keep as-is)

| Decision | Where | Why it holds |
|---|---|---|
| `branch_id NOT NULL` on every money/stock/ledger row | design §1.1; both DDLs | Reproduces `farysales.mobile/phar`, per-branch ميزان/كشف حساب, and `farysales.monthe/yearo`. Direct fix of §1.1/§1.4. |
| `balances` PK `(branch_id, account_id, month, year)`; `monthly_close` PK `(branch_id, year, month)`; `month_open_balances` replaces `start_balances_json` | §1.1/§1.11 | Matches `monthy\moves` + `monthy\start-data` and the four opening-balance prompts (drawer / stock at cost excl. VAT / receivables / payables — feature_balances.md:72, idx 8487/8488). |
| Money typing + single rounding point | §1.2, §3.3 | `NUMERIC(18,2)` totals, `NUMERIC(18,4)` unit price/cost and qty, `NUMERIC(5,2)` rates; round-half-up at 2 dp at every line/payment boundary; legacy floats rounded once to 4 dp at import, never re-summed. Matches §1.11/§3.3 exactly. |
| `stock_batches` mirrors `wzgard` (typee enum, costvalue, oldstock, unique `(branch_id, drug_id, randomid)`) | §1.2 | FIFO/expiry sale selection, COGS, ربح اليوم, مخزون منتهي all require batch rows. |
| `audit_log` (← TitanUserAction 11-col) written in the same transaction as every money/stock mutation; `invoice_versions` for تعديل فواتير | §1.6 | Reproduces the legacy reverse-then-reapply edit; answers "who changed this balance?". |
| `sync_log` outbox (last-write-wins) + `branch_identities` alias map + `branches.is_main_device` | §1.3 | Reproduces "no-merge" replication (connections_overview.html:686) and the three legacy branch aliases (phar/pharmacyid/mobile). |
| E-invoice state in DB: `einvoice_log` + `einvoice_counters` (ship in the `eta` schema with `pharmatag-eta`, A08); no network submission to the dead Saudi/Egypt URLs | §1.10/§1.9 | QR/counter/hash chain in-DB; ETA JSON kept, dead URLs skipped (EGYPT_ETA_DECOMPILED.md). |
| `payment_splits.method` = cash/card/credit/manual_cash/manual_card + `payed + agel = totalvalue` | §1.11 | Reproduces idx 9883 daily totals and the split identity (idx 13344: مجموع الاجل والمدفوع يساوي سعر الفاتورة). |
| `daily_close` complete (manual_cash, manual_card, cost_of_sales, net_profit, discounts, drawer_start, shift_id, work_period_id), `UNIQUE (branch_id, datee)` | §1.11 | ربح اليوم + RPT-A04 drawer handover computable. |
| Approvals + shortages (`stock_correction_requests`, `shortage_flags`, `needs`, `purchase_orders`) | §1.7/§1.8 | Reproduces the three shortage sub-systems and the staff→manager gate. |
| All 10 GAPS §2 contradictions resolved to `schema_complete.sql` shapes | §2 below | Every "other" shape is a column list misattributed from wzdrugs/invoicedata/RawakidTablew/storediscount/farysales, or the older raw `schema.sql` lineage. |
| Balanced-journal invariant at the API layer + single-side CHECK on `journal_lines` | §1.11 | Cross-table CHECK is not expressible in plain DDL (documented in design §5). Correct engineering call. |

### 1.3 What to CHANGE (8 corrections)

1. **SQLite money typing contradicts the design itself (BLOCKER).** `schema_design.md` §6 mandates **INTEGER minor units** ("a double can never be inserted"); `schema_sqlite.sql:9-18` instead declares money as **NUMERIC affinity + app-side rounding** — the exact float hazard the design eliminates. **Fix:** regenerate `schema_sqlite.sql` so every decimal column is `INTEGER` storing `value × 10^scale`. See §4.
2. **`drug_costs` fabricates a branch dimension.** Legacy `wzdrugs2` (schema_complete.sql:48-53) has **no branch column** — one row per drug, global. Draft PK `(branch_id, drug_id)` would duplicate global rows per branch or invent data. **Fix:** `drug_costs(drug_id PRIMARY KEY, unitcost, costvalue, expire)`; per-branch cost lives in `stock_batches.cost` (already branch-scoped). Consistent with the legacy comment "unitcost computed from wzgard".
3. **`invoices` has no uniqueness on `invoice_no`.** Legacy identity is `(pharmacyid, invoiceid)`; the new schema must make the invoice document addressable. **Fix:** add `UNIQUE (branch_id, invoice_no)`; keep the `(branch_id, datee)` index. Returns are separate documents with new numbers (§6 Q4 → G07).
4. **`drug_barcodes` unique index collides on empty barcode.** Draft `CREATE UNIQUE INDEX … ON drug_barcodes (barcode)` (schema_postgres.sql:161) rejects the second drug with no barcode entered (`barcode=''`). **Fix:** partial unique index `WHERE barcode <> ''`. Same hazard for `drugs.drugname` (empty-name legacy rows) — partial unique `WHERE drugname <> ''` plus a migration dedup pass. See §5.2.
5. **`app_config` seeds SA/SAR/15% (schema_postgres.sql:898-902).** The stated target is an Egyptian pharmacy ERP (ETA). **Fix:** seed `country=EG, currency=EGP, vat_default_rate=14.00` and `branches.vat_default DEFAULT 14.00`; keep the config override so a Saudi/ZATCA deployment is a one-row change (§6 Q1 → G01).
6. **`drug_sync_outbox` drops `drgserver.silsila` and `mobile`** (schema_complete.sql:241-242). **Fix:** add `silsila VARCHAR(50)` and `mobile VARCHAR(15)` passthrough columns — the chain drug-server channel is keyed by silsila.
7. **`branch_stock.qty` authoritative source is ambiguous.** Legacy has two stock truths: `titanstock.stock` (current per-drug) and `wzgard` (batch movement history). **Fix:** import `branch_stock.qty` from `titanstock` (authoritative current), `stock_batches` from `wzgard` (history), and run a reconciliation pass flagging `SUM(stock_batches.qty) <> branch_stock.qty` into `archive_imports.note`. Never let the ETL silently pick one.
8. **`invoices` `CHECK (payed + agel = totalvalue)` will reject migrated float data.** Legacy `payed/agel/totalvalue` are REAL; rounding each once can break the identity by a piastre (`100.005 → 100.01` vs `50.002 + 50.003 → 50.00 + 50.00`). **Fix:** keep the CHECK for new data; the ETL **final normalization pass** sets `payed = totalvalue − agel` per invoice (residual into the cash split) so every imported row satisfies the invariant exactly. No tolerance hack; the invariant is enforced, not relaxed.

**Minor notes (non-blocking):** `journal_lines` should carry `datetimee` (farysales.datetimee) as a passthrough column; `balances`/`month_open_balances` column order should align to `(branch_id, account_id, year, month)`; `einvoice_log.invoice_id NOT NULL` needs an orphan rule in the ZATCA ETL (skip rows whose invoiceid maps to no invoice, or create a placeholder); the raw PG `BEGIN/COMMIT` DDL must become Alembic revision 001 (re-runnable), per §5.1.

---

## 2. Adjudication of the REMAINING GAPS §2 contradictions (10 items)

Every ruling below is **final**. Each confirms SCHEMA_RESOLVED.md (p-code evidence) and states what the draft does with it. **Decision rule:** when docs disagree, the ground-truth CREATE TABLE + live INSERT/SELECT fragments in `schema_complete.sql`/`titan_decompile/` win; feature-doc column lists are read at +3 and trusted only when they match a real table.

| # | Legacy table | Conflict | FINAL DECISION | Rationale (evidence) | Draft mapping |
|---|---|---|---|---|---|
| 1 | `titanksasales` | 9 vs 15 cols | **9-col summary** `id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue` | INSERT template idx 8016 matches the 9-col exactly; live UPDATE (FFFStartUp) + live SELECT (FFFOutPut); the 9-col insert runs inside the chain-sync GUID loop (`a2a100e1…` used 3,564×). The 15-col shape is invoicedata/RawakidTablew's line-item list; the reports extras are farysales (SCHEMA_RESOLVED §1, §7, §9). | `invoices` (kind='sale', `silsilaid`) + a `sync_log` outbox row. Correct. |
| 2 | `titanksastock` | 8 vs 24 cols | **8-col stock snapshot** `id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock` | CREATE live ×3 (FFFOutPut×2, FFFDRUGRUN) with assembled column fragments (pharmacyid/shape/silsilaid/stock REAL); INSERT template idx 912 = 7-col body + id. The 24-col "Primary Drug Table" is `wzdrugs`. | `branch_stock` (qty, minimum, silsilaid, classy, price, barcode, lastedit). Correct. |
| 3 | `titanneed` | 5 vs 7 cols, disjoint | **6-col needs/request** `id, drugname, quant, datee, sender, target` | CREATE live ×2 (FFFOutPut) + "table titanneed created!" live; INSERT idx 8006 = 5-col body + id; `sender/target NVARCHAR(20)` fragments confirm inter-pharmacy request, not stock. The 7-col shape is titanksastock's list. | `needs` with `sender_branch_id`/`target_branch_id` FKs + `legacy_sender`/`legacy_target` text. Correct. |
| 4 | `TitanUserAction` | 11 vs 10 vs 10 cols | **11-col audit log** `id, drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee`; `units INT`, `datee REAL`, `curbarcode VARCHAR(15)` | INSERT template idx 5252 = 10-col body + `id` IDENTITY = 11. The 10-col variants drop the PK and change types; they match the older raw `schema.sql` lineage, not runtime. | `audit_log` (entity/entity_id/field/old_value/new_value/drug_id/barcode/action/namee/typevalue). Correct. |
| 5 | `usersourceupdate` | 6 vs 9 vs 4 cols | **6-col sync row** `id, drugname, price, units, localimport, datee` | INSERT template idx 8007 matches 6-col; live `SELECT top 3000 … WHERE Datee >` (idx 6210) matches 6/9-col, not 4-col; live `DELETE … WHERE id=` proves the `id` PK and rules out the 4-col form. 9-col = raw schema.sql lineage. | `sync_log` outbox (entity, payload JSONB, status) + `drug_sync_outbox` for the drug-list channel. Correct. |
| 6 | `ChainBuyUsers` | 12 vs 4 vs 1 cols | **12-col + id chain-buy row** `PharmacistTel, Expire, IdDateTime, Quant, DrugName, SellDisc, Mohafaza, Markaz, Tips, RequisterTel, country, price` | Column-list template idx 5939 matches exactly; the sibling 10-col (idx 5938) is the RawakidTablew variant (SourceIdDateTime vs Tips/RequisterTel/country). 4-col/1-col = raw schema lineage. | `chain_buy_orders` (region columns, both tel fields, country). Correct. |
| 7 | `invoicedata` | header vs merged | **17-col merged hybrid; normalized into `invoices` + `invoice_lines`** `id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue, IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price` | The line-item INSERT `(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)` is LIVE ×3 (FFFOutPut, FFFInPut, Raz); the header INSERT idx 8016 is assembled at runtime; `IdDateTime = '` filter live. The p-code has NO separate line table — header and lines live in one row. The new schema splits it (normalization); the migration groups rows by `(pharmacyid, invoiceid)`. | `invoices` (header cols) + `invoice_lines` (line cols). **Adopt; the grouping assumption is explicit in §6 Q3.** |
| 8 | `wzphar` | `pharname` vs `pharmacyname` | **Both correct, on different tables.** `wzphar.pharname` (pharmacy master); `pharmacyname` belongs to `storediscount`, `titanpharmalist` (+ their aggregates). | The only wzphar SQL fragment is `select distinct pharname from wzphar` (idx 999); every `pharmacyname` fragment targets storediscount (`group by pharmacyname,adress` idx 928; 16-col INSERT idx 7435) or titanpharmalist (INSERT idx 8104). | `branches.pharname`; `price_change_log.pharmacyname`; `branch_registry.pharmacyname`. Correct. |
| 9 | `taronlineeg` / `farysales` | swapped column lists | **`taronlineeg` = 7-col online catalog** `id, CreateDate, mobile, NameEnglish, NameArabic, drugname, price, barcode`. **`farysales` = 17-col per-branch ledger** `id, mobile, grand, father, son, datee, datetimee, dateemanual, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy` | The live 17-col INSERT idx 396 (FFFNew, ModStock, ModDTTS) matches `farysales` exactly in schema_complete.sql order — the reports doc swapped the two tables. `taronlineeg` has only SELECT/UPDATE fragments (idx 814-817, 1033), no INSERT. | `external_drug_catalog` ← taronlineeg; `journal_lines` + `balances` ← farysales (father/son → account_id, payed → debit/credit, creditdebit → side, monthe/yearo → month/year). Correct. |
| 10 | `titaninn` | transfer vs purchases | **7-col inter-pharmacy transfer** `id, fatid, itemsasstring, datee, source, silsilaid, target` | The "purchases" reading is a docs error. Evidence: live DELETE (ModDTTS, Raz), live SELECT `select fatid from titaninn where` ×3, live DROP (FFFOutPut); ModDTTS assembles the CREATE from the exact columns (L484176-484332); the source/target/silsilaid/itemsasstring field set is the transfer-record shape; purchases go to invoicedata/titanstock. | `transfers` + `transfer_lines` (source/target as branch FKs + legacy text kept; status ← delivery.phy). Correct. |

**Bottom line:** all 10 GAPS §2 items are definitively resolved — 9 in SCHEMA_RESOLVED.md, 1 (invoicedata) as a deliberate normalization decision. The draft's adoption is faithful; the only follow-on edits are the §1.3 corrections (invoicedata grouping, drug_costs, money-CHECK normalization).
---

## 3. Final table inventory (51 tables, grouped — core vs plugin-owned per A08)

**Conventions:** `[C]` = core — ships in **core Alembic revision 001** in the `public` schema (PG) / the base SQLite twin (money/stock/audit/sync + auth/drug-master/parties + the plugin host, §3.9). `[S]` = plugin-owned — **no longer part of core rev 001**; the DDL ships in the owning plugin's schema/migration (A08), owner and schema per `plan/08_app_architecture_plugins.md` §1.3/§1.4 (schema = plugin slug: `eta`, `chain`, `ledger`, `reports`, …). Tables marked `→ schema` below live in that plugin's schema on PG; the SQLite offline twin maps each plugin schema to a per-plugin ATTACHed DB file (`p_` prefix fallback — §4.3). Every money/stock/ledger table carries `branch_id NOT NULL` + the "AUDIT:" write-atomicity contract. Legacy natural keys are kept as unique indexed columns for idempotent ETL. Column lists live in the DDL files; this section fixes ownership and tiers only.

### 3.1 Auth / permissions
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `branches` | wzphar + ismaster.txt | id; `UNIQUE(pharmacyid)`, `UNIQUE(mobile)`, phar alias | C |
| `users` | FormUsers/FFFUserEdit + ShogUser.phy | id; `UNIQUE(username)`; mobile (usersmony linkage) | C |
| `roles` | new | id; `UNIQUE(name)` | C |
| `permissions` | legacy الصلاحية 1-9 | id; `UNIQUE(code)` | C |
| `role_permissions` | new | (role_id, permission_id) | C |
| `user_roles` | new | (user_id, role_id) | C |

### 3.2 Drug master
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `drugs` | wzdrugs + tar.phy (EN@0x00/AR@0x34 cp1256, verified) | id; `drugname` partial-unique (see §1.3#4); `tax_type` exempt/5%/14% (G06) | C |
| `drug_barcodes` | wzdrugs.barcode + Barcode1..5 | id; partial-unique `barcode` WHERE <> '' | C |
| `unit_conversions` | wzdrugs.units/Unitsmall | id | C |
| `drug_costs` | wzdrugs2 | id; `UNIQUE(drug_id)` (branch removed — §1.3#2) | C (rev 001 — drug master, 08 §1.2 C-2) |
| `drug_interactions` | DDI.Phy (1300 B) | id; `UNIQUE(drug_a, drug_b)` + ordered CHECK | S → doctors |
| `external_drug_catalog` | taronlineeg (7-col) | id; barcode | S → drugdb |

### 3.3 Inventory / stock
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `stock_batches` | wzgard | id; `UNIQUE(branch_id, drug_id, randomid)`; FIFO index (branch_id, drug_id, expire) | C |
| `branch_stock` | titanstock + titanksastock (8-col) | `(branch_id, drug_id)`; minimum, silsilaid | C |
| `drug_sync_outbox` | drgserver | id; **add silsila + mobile** (§1.3#6) | S → chain |

### 3.4 Sales / purchases / returns
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `invoices` | invoicedata header cols + titanksasales (9-col) | id; `UNIQUE(branch_id, invoice_no)` (new); silsilaid; kind sale/purchase/sale_return/purchase_return/transfer | C |
| `invoice_lines` | invoicedata line cols (17-col split) | id; invoice_id; branch_id; drug_id; batch_id; unit; 4-dp price/cost/qty; `tax_type` + per-line vat_amount (G06) | C |
| `invoice_versions` | feature_invoice_editing | id; `UNIQUE(invoice_id, version_no)`; JSONB snapshot | C (rev 001 — 08 §1.2 C-10) |
| `payment_splits` | payed/agel split | id; method cash/card/credit/manual_cash/manual_card; CHECK amount > 0 | C |
| `purchase_orders` | orders (NULL→'pending') | id; orderid | S → chain |

### 3.5 Money / ledger / balances
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `accounts` | wzaccfreetree + acctree.phy | id; `UNIQUE(branch_id, code)`; parent tree | C |
| `journals` | feature_balances / farysales | id; `UNIQUE(branch_id, datee, entry_no)`; description NOT NULL | C |
| `journal_lines` | farysales 17-col LIVE + Accounting\moves | id; branch_id; account_id; month/year; single-side CHECK; creditdebit/randomid/writer/tips/classy (+ datetimee passthrough) | C |
| `balances` | farysales monthe/yearo | `(branch_id, account_id, month, year)`; CHECK balance = debit − credit | C |
| `monthly_close` | monthy\moves | `(branch_id, year, month)`; status open/closed/reopened | S → ledger |
| `month_open_balances` | monthy\start-data | `(branch_id, account_id, year, month)` (align column order) | S → ledger |
| `drawer_movements` | Daily.phy (614 B) | id; direction/reason/method; shift_id FK resolves | C |
| `daily_close` | MonyInfo.phy + Daily.phy totals + idx 9883 | id; `UNIQUE(branch_id, datee)`; complete money fields | C |
| `user_drawer_money` | usersmony.phy (318 B) | id; record_no; user_id; shift_id | S → hr |
| `manual_journal_entries` | daily-manual.phy (52/56 B) | id; record_no; datee; amount | C (rev 001 — store; ledger owns workflow, 08 §1.2 C-7) |
| `shifts` + `work_periods` | workperiod.phy | id; cash_start; closed_at ≥ opened_at CHECK | C |

### 3.6 Chain-sync
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `transfers` + `transfer_lines` | titaninn (7-col) + delivery.phy (55 B) | id; source/target branch FKs + legacy text; itemsasstring | S → chain |
| `needs` | titanneed (6-col) | id; sender/target branch FKs + legacy text | S → chain |
| `shortage_flags` | §1.8 | id; method manual/half_auto/sales_rate | C (rev 001 — intra-branch, 08 §1.2 C-6) |
| `stock_correction_requests` | §1.7 + RasidCorrect.phy | id; status pending/approved/rejected; CHECK pending ⇔ decided_at NULL | C |
| `dead_stock_exchange` | RawakidTablew | id; region + both tel fields | S → logistics |
| `chain_buy_orders` | ChainBuyStore + ChainBuyUsers (12-col) | id; region | S → logistics |
| `branch_registry` | titanpharmalist | id; `UNIQUE(mobile)`; pharmacyname | S → chain |
| `sync_log` | usersourceupdate (6-col) | id; entity/entity_id/payload/status; source_device_id | C |

### 3.7 ETA / ZATCA
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `einvoice_log` | ZATCA | id; invoice_id; kind zatca/eta; uuid; status; hash; qr_counter/qr_hash/qr_data; payload_xml/json; response | S → eta (pharmatag-eta migration) |
| `einvoice_counters` | oot3/netcounter/counter.txt+hash.txt | `(branch_id, kind)`; last_counter/last_hash | S → eta (pharmatag-eta migration) |

**Note (A08):** both e-invoice state tables live in the `eta` schema, shipped with the `pharmatag-eta` migration; core keeps a thin generic `einvoice` service the plugin extends (08 §1.4).

### 3.8 Audit / sync / ops
| Table | Legacy source | PK / natural key | Tier |
|---|---|---|---|
| `audit_log` | TitanUserAction (11-col) | id; entity/entity_id; drug_id; barcode; action; old/new_value | C |
| `branch_identities` | §1.3 alias map | `(legacy_table, legacy_column, legacy_value)` → branch_id | C (rev 001 — 08 §1.2 C-11; migration-time) |
| `price_change_log` | storediscount (16-col) | id; pharmacyname + pharmacyname2 + country | C (rev 001 — drug master, 08 §1.2 C-2) |
| `integration_config` | myftp.phy | id; `UNIQUE(branch_id, key)`; secrets encrypted at app layer | C (rev 001 — app-level config; plugin_settings precedent) |
| `archive_imports` / `archive_exports` | Archive\Input + Output, Titan3-Backup, Phye.safer | id; status pending/running/done/failed; note = ETL runbook log | S → tools |
| `app_config` | §1.11 | key PK; seed EG/EGP/14% (§1.3#5) | C |

### 3.9 Plugin host (core rev 001 — schema `public`)

| Table | Source | PK / natural key | Tier |
|---|---|---|---|
| `app_plugins` | 08 §2.2.1 | id; `UNIQUE(slug)`; status/license enums | C |
| `plugin_dependencies` | 08 §2.2.1 | `(plugin_id, depends_on)` | C |
| `plugin_branch_grants` | 08 §2.2.1 | `(plugin_id, branch_id)` | C |
| `plugin_settings` | 08 §2.2.1 | `(branch_id, plugin_id, key)` | C |

`app_config` gains the `plugins_enabled` global kill-switch (08 §2.2.1). Brand-new plugin tables (e.g. `eta_credentials`/`eta_submission_queue` in `eta`; `report_definitions`/`report_schedules` — the report catalog — in `reports`; `installment_plans`/`installment_payments`/`settlement_vouchers` in `receivables`; `chain_sync_policy` in `chain`) are defined in 08 §1.3 and ship with their plugin migrations, **not** in core rev 001.

**Skipped (documented in design §4):** `remotecontrol` (RCE hazard), `nilsen2` (data-selling), `drugeyedash2` (external MySQL mirror), DrugEye `.phy` feed (legal caveat — use CC0/SFDA catalogs into `external_drug_catalog`).

---

## 4. Money typing + rounding + the PG↔SQLite twin strategy

### 4.1 PostgreSQL (canonical) — exact decimal

| Class | PG type | Used for |
|---|---|---|
| money/totals/balances | `NUMERIC(18,2)` | totalvalue, payed, agel, subtotal, discount, vat (amounts), credit_limit, drawer/daily_close fields, balances, journal_lines.debit/credit, shift cash_start |
| per-unit / quantity | `NUMERIC(18,4)` | unit_price, cost, qty, stock, minimum, price/price_now, delta |
| rate (%) | `NUMERIC(5,2)` | vat rates, disco/sell_disc, branches.vat_default |
| conversion factor | `NUMERIC(18,6)` | unit_conversions.factor |

**Rounding rule (single point of truth, one shared module):** round-half-up to 2 dp at **every line-total and every payment boundary** — `line_total = round(unit_price × qty × (1 − disc/100), 2)` plus per-line VAT; **VAT per line is computed per line and summed (never computed on the aggregate — Egypt ETA requires per-line VAT).** Per-unit prices/costs keep 4 dp internally and are rounded only when multiplied into a total. **G06 tax model:** Egypt retail is **VAT-inclusive**; every drug-master and `invoice_lines` row carries `tax_type` ∈ {`exempt` (medicines, 0%), `5%` (medical devices), `14%` (other goods)}. On a taxable line the stored price is inclusive, so `vat_amount = round(total × vat_rate ÷ (1 + vat_rate), 2)` and `net = total − vat_amount` (i.e. `net = total ÷ 1.14` at the 14% rate); exempt lines post `vat_amount = 0`. `branches.vat_inclusive_prices` controls the mode (Saudi override may be exclusive). **REAL/float/double is never used for money in PG.**

**Legacy import rule:** each legacy REAL/R4/R8 money field is rounded **once** to 4 dp (`round(float, 4)`) and stored as NUMERIC; historical totals are **never re-summed from floats** — each stored row is a fixed decimal; aggregation happens in SQL on the decimal columns. The ETL normalization pass (§1.3#8) then fixes `payed = total − agel` per invoice.

### 4.2 SQLite (Tauri offline twin) — INTEGER minor units

**Decision (overrides `schema_sqlite.sql`):** every decimal column becomes `INTEGER` storing `value × 10^scale`. Rationale: SQLite's `NUMERIC` affinity stores fractional values as IEEE double — the exact hazard §1.2 eliminates. Integer minor units make money exactness a schema invariant (a double can never be inserted into an INTEGER column under honest review), at the cost of one ×10^scale conversion at the app boundary, which the shared money module owns.

| PG type | SQLite storage | scale | example |
|---|---|---|---|
| `NUMERIC(18,2)` | `INTEGER` | ×100 (piastre/halala) | 123.45 → 12345 |
| `NUMERIC(18,4)` | `INTEGER` | ×10000 | 12.3456 → 123456 |
| `NUMERIC(5,2)` | `INTEGER` | ×100 | 14.00 → 1400 |
| `NUMERIC(18,6)` | `INTEGER` | ×1000000 | 1.5 → 1500000 |

Uniform rule: **PG `NUMERIC(n,s)` ↔ SQLite `INTEGER` storing `value × 10^s`.**

Consequences (all mechanical):
- All existing CHECKs survive unchanged because they are scale-invariant: `payed + agel = totalvalue`, `difference = counted_cash − expected_cash`, `balance = debit − credit`, `amount > 0`, `(status='pending') = (decided_at IS NULL)` all hold in minor units.
- `app_config` seeds become integers: `vat_default_rate` 14.00 → 1400; `branches.vat_default` → INTEGER.
- `rounding='half-up-2dp'` seed is a config row, not a column type.
- SQLite `PRAGMA foreign_keys = ON` stays; timestamps stay `TEXT` ISO-8601 UTC.
- **Plugin tables (A08):** these live **outside** the base twin — each plugin's tables go in a per-plugin ATTACHed SQLite DB file (e.g. `ATTACH 'eta.db' AS eta`), or with a `p_<slug>_` prefix on the main twin if ATTACH proves problematic (§4.3). The base SQLite twin contains only core tables + the plugin host (§3.9).

### 4.3 Twin-drift control

1. **One money module** (`round_half_up`, `to_minor(x, scale)`, `from_minor(m, scale)`), shared by the FastAPI layer and the Tauri app (as a Rust crate with identical tests, or a Python sidecar). Column names identical in both DDLs; only the type differs (NUMERIC vs INTEGER).
2. **Parity CI test:** a script parses `schema_postgres.sql` and `schema_sqlite.sql` and asserts the same table/column/constraint set, plus the scale mapping above. Runs in CI on every schema PR so the twins cannot drift again (the current NUMERIC-vs-INTEGER contradiction is exactly such a drift).
3. **Migration direction:** SQLite → PG preserves values verbatim (`INTEGER / 10^s` → NUMERIC — exact); PG → SQLite snapshots multiply by the scale. No lossy conversion in either direction.
4. **Alternative (preferred if Tauri uses a Python data layer):** SQLAlchemy models are the single source of truth and BOTH DDLs are generated. (Superseded — A01: TS-first via `tauri-plugin-sql`; SQLAlchemy DDL generation not adopted.)
5. **Plugin tables & schemas (A08):** the PG twin has per-plugin schemas; SQLite has none → each plugin's tables live in a **per-plugin ATTACHed SQLite DB file** (e.g. `ATTACH 'eta.db' AS eta`), preserving parity by mapping each PG schema to an attached DB. If ATTACH proves problematic in the Tauri/SQLite runner, fall back to `p_<slug>_` prefixes on the offline twin only. Parity CI asserts the *set* of plugin tables matches across dialects, and that no plugin table lives in `public` (PG) / unprefixed in the base twin (SQLite).
---

## 5. Migration path

### 5.1 DDL management

- **PostgreSQL: Alembic.** Convert `schema_postgres.sql` into Alembic revision 001 (hand-written to match the DDL exactly — do not `autogenerate` a first revision against an empty DB). Thereafter `autogenerate` from SQLAlchemy models. Enums become `sqlalchemy.Enum` backed by the PG `ENUM` types; all FKs/indexes/comments carried over, including the AUDIT: comments.
- **SQLite: versioned schema file** `schema_sqlite.sql` (INTEGER minor units, §4.2) applied at Tauri startup via a small migration runner (schema version table; apply pending scripts in order). If Q2 opts for a shared Python data layer, both DDLs are generated from the models and the SQLite file becomes an artifact.
- **Phasing (A08):** core revision 001 ships **only** the core truth tables (§3 `[C]`, in `public`) + the plugin host (`app_plugins`, `plugin_dependencies`, `plugin_branch_grants`, `plugin_settings`, §3.9) + core seeds (§5.2). Plugin-owned tables (`[S]`) ship in the owning plugin's schema/migration when the plugin installs (08 §2.2.2/§2.2.3) — **no longer part of core rev 001**. Each plugin ships Alembic revisions that `CREATE SCHEMA <slug>` and create its tables in that schema (`p<slug>_<n>` revision ids). Core-first phasing stays an app concern; the **core** schema is whole from day one so migration targets never move.

### 5.2 Seed data (revision 002)

| Seed | Content |
|---|---|
| `branches` | One row: main branch; `pharmacyid`/`phar`/`mobile` from legacy `wzphar` (or a fresh default when migrating a new install); `is_main_device=true`; `vat_default=14.00`; `vat_inclusive_prices=true` (G06). |
| `users` | `admin` superuser (bcrypt hash, role=admin). Legacy users come from `ShogUser.phy` (name field only — opaque beyond that; PHY_MIGRATION §0b) so users are re-created with default role in the ETL, not copied verbatim. |
| `roles` / `permissions` / `role_permissions` | Roles: `admin`, `pharmacist`, `cashier`, `accountant`, `manager`. Permissions seeded from the legacy الصلاحية 1-9 surface (feature_users_permissions_menus.md:84) plus module-level codes (sale, edit invoice, close day, adjust stock, approvals, reports, users). admin → all. |
| `accounts` (default chart of accounts per branch) | A default COA template matching the legacy tree (feature_balances.md:240): اصول.متداولة.عملاء (AR), اصول.متداولة.خزينة/درج, اصول.متداولة.مخزون, اصول.ثابتة, خصوم.متداولة.موردين (AP), خصوم.ضريبة.مبيعات/مشتريات, حقوق ملكية.راس المال, ايرادات.مبيعات, مصروفات, تكلفة المبيعات. Per-branch rows generated on branch create; a real legacy install migrates `wzaccfreetree` (mobile→branch, master/fary→parent/child) instead. |
| `app_config` | `country=EG`, `currency=EGP`, `vat_default_rate=14.00`, `rounding=half-up-2dp`, `vat_inclusive_prices=true`, `plugins_enabled=true` (§1.3#5, G06, A08). |
| `parties` | opening receivables/payables seeded as `month_open_balances` debit/credit via opening journal entries (idx 8482-8485) — NOT hardcoded into `parties`. |

### 5.3 Indexing (beyond PKs/unique)

| Table | Index | Why |
|---|---|---|
| `invoices` | `(branch_id, datee)`, `(branch_id, party_id)`, `(last_edited_at)`, `UNIQUE(branch_id, invoice_no)` | date/day-close scans; per-customer ledger; LastEdited.phy parity; document identity |
| `invoice_lines` | `(invoice_id)`, `(branch_id, drug_id)`, `(batch_id)` | line fetch; drug flow (حركة الدواء); batch COGS |
| `stock_batches` | `(branch_id, drug_id, expire)` (FIFO), `(randomid)` | expiry-first sale selection; ETL randomid upsert |
| `branch_stock` | PK `(branch_id, drug_id)` | point stock lookups |
| `journal_lines` | `(branch_id, account_id, month, year)`, `(journal_id)` | كشف حساب, monthly ميزان, journal fetch |
| `balances` | PK `(branch_id, account_id, month, year)` | monthly aggregation |
| `audit_log` | `(entity, entity_id)`, `(drug_id)`, `(branch_id, created_at)`, `(created_at)` | entity history; drug audit; per-branch timeline |
| `sync_log` | `(branch_id, status)`, `(status, created_at)` | outbox pull (3000-row delete-on-apply parity) |
| `einvoice_log` | `(invoice_id)`, `(kind, status)`, `(branch_id, created_at)` | resubmission queue; per-branch submission timeline |
| `parties` | `(branch_id, namee)`, `(branch_id, mobile)` | customer search, phone lookup |
| `transfers` | `(source_branch_id)`, `(target_branch_id)` | chain transfer lists |
| `needs` | `(sender_branch_id, status)`, `(target_branch_id, status)` | نواقص screens |
| `drug_barcodes` | partial-unique `(barcode) WHERE barcode <> ''`, `(drug_id)` | ANY-of-6 lookup without empty-string collisions |
| `drugs` | partial-unique `(drugname) WHERE drugname <> ''` | legacy PK; tar.phy upsert |

### 5.4 Enforcement of `branch_id` / `audit_log` / `sync_log`

**branch_id — enforced 4 ways (defense in depth):**
1. `NOT NULL` FK on every money/stock/ledger table (DDL).
2. FastAPI dependency injects the caller's branch from the auth token; service-layer write helpers stamp `branch_id` and reject a mismatched body.
3. Repository guard asserts `row.branch_id == session.branch_id` on every write (catches multi-branch smuggling).
4. Read scoping: every query builder filters by `branch_id` from the dependency. (PG Row-Level Security is deferred — the legacy model is one app instance per branch with a shared server DB; RLS is Q10-adjacent, optional later.)

**audit_log — one repository wrapper, one contract:** every money/stock/balance mutation goes through `write_mutation(entity, entity_id, field, old, new, drug_id, barcode, action)` which inserts the audited row **and** the `audit_log` row in the **same DB transaction**. The balanced-journal invariant (SUM(debit)=SUM(credit) per journal) is asserted inside that same transaction on `journals`+`journal_lines`. No DB triggers: they would duplicate the logic in the SQLite twin and are hard to keep in sync (Q2). The test suite asserts that every money-table write produces exactly one audit_log row.

**sync_log — outbox in the same wrapper:** any chain-relevant mutation (invoices with silsilaid, branch_stock, drugs price) also enqueues a `sync_log` row (`payload` = full row snapshot JSON). The syncer polls `pending` rows ordered by `created_at`, applies to peer branches last-write-wins, marks `applied` (or `failed`/`skipped`), preserving the legacy 3000-row pull + delete-on-apply semantics of `usersourceupdate`. `einvoice_counters` are updated atomically with each einvoice_log insert (QR counter/hash chain, §1.9).

### 5.5 Data migration (legacy → new), staged

The `.phy` files are the money truth; the SQL Server DB holds only client/other data (legacy_import/README.md).

- **Stage 0 — freeze:** byte-identical copy of `Files\DBI` + SQL Server export (if any). Do not open/save files in the legacy app first.
- **Stage 1 — .phy ETL (`legacy_import/`):** `tar.phy` → `drugs` (856 B, 18,100 real records, cp1256 — verified); `customers.w.phy` → `parties` (157 B, names corrupt on this install); `ShogUser.phy` → `users` (1114 B, name-only); `Daily.phy` → `drawer_movements`/`daily_close` (614 B, known 0x00..0x3c, tail opaque); `daily-manual(.2).phy` → `manual_journal_entries` (52/56 B); `usersmony.phy` → `user_drawer_money` (318 B); `delivery.phy` → `transfers.status` (55 B); `oot3/netcounter` + counter/hash.txt → `einvoice_counters`. Unknown layouts → hex dump + `UNKNOWN_LAYOUT`, never blocking the batch.
- **Stage 2 — SQL tables:** per §2/§3 mapping, using the preserved natural keys for idempotent upsert. `invoicedata` grouped by `(pharmacyid, invoiceid)` → `invoices`+`invoice_lines` (Q3); `wzgard` → `stock_batches`; `titanstock` → `branch_stock` (authoritative qty, §1.3#7); `wzcustomers`/`companies` → `parties` (suppliers → main branch, Q8); `farysales` → `journal_lines`+`balances`; `TitanUserAction` → `audit_log`; `ZATCA` → `einvoice_log` (orphan rule); `usersourceupdate`/`titanksasales`/`titanksastock` → `sync_log` + aggregate tables.
- **Stage 3 — money normalization + reconcile:** round each float once to 4 dp; per-line totals to 2 dp; final `payed = total − agel` pass; `branch_stock.qty` vs `SUM(stock_batches.qty)` reconciliation flagged in `archive_imports.note`; per-day totals checked against legacy day-close figures before cutover.
- **Release-blocking items (from PHY_MIGRATION §3):** `MonyInfo.phy` layout (runtime-built, 0 refs), `Dailymax.phy` reclen, full 614-B Daily tail, populated `salesfull.phy`/`customers.w.phy` field maps — all need a production `Files\DBI` sample; until then they degrade to best-effort/UNKNOWN_LAYOUT.

---

## 6. Open decisions needing the user (numbered, with my recommendation)

All 12 below are **resolved** against `plan/00_decisions_master.md` (2026-08-16); the original recommendation text is kept for traceability.

1. **Default country/currency/VAT.** Draft seeds SA/SAR/15%. The stated target is an Egyptian ERP (ETA). **Recommendation: default `EG / EGP / 14%`;** keep the ZATCA/Saudi config as an override row. (I've provisionally changed the seed in §1.3#5.) ✅ **RESOLVED → G01** (Egypt-first; schema country-agnostic; VAT default 14%; Saudi = override).
2. **Tauri data-layer language.** Rust (SQLx/Diesel) vs a Python sidecar. **Recommendation: Rust + SQLx, INTEGER minor units, hand-maintained twins + parity CI test.** If a Python sidecar is acceptable, generate both DDLs from SQLAlchemy models instead (preferred: eliminates twin drift). This decides whether §4.3#4 is adopted. ✅ **RESOLVED → A01** (TS-first via `tauri-plugin-sql`; SQLite money = INTEGER minor units; §4.3#4 SQLAlchemy generation superseded).
3. **`invoicedata` granularity (the one unverified assumption).** The rebuild treats invoicedata as **one row per invoice line** (header cols duplicated), grouping by `(pharmacyid, invoiceid)`. The p-code proves header+lines share one table but not the exact row cardinality. **Recommendation: adopt the per-line assumption** — it degrades gracefully (single-line invoices are groups of 1) and matches the line-item INSERT being live while the header INSERT is template-only. Confirm with a production invoicedata dump during Stage 2. ✅ **RESOLVED → G12 + G02** (one row per invoice line, grouped by `(pharmacyid, invoiceid)`; final confirmation on a production dump is data-gated, per G02 cutover).
4. **Invoice numbering + returns.** **Recommendation:** per-branch monotonic sequence; `UNIQUE(branch_id, invoice_no)` across all kinds; returns (sale_return/purchase_return) are new documents with new numbers; "transfer to sales return" = a new return invoice + an `invoice_versions` reversal snapshot. Do NOT reuse numbers across kinds. ✅ **RESOLVED → G07** (adopted verbatim: internal per-branch monotonic `invoice_no`; `UNIQUE(branch_id, invoice_no)`; returns = new documents).
5. **ZATCA vs ETA canonical payload.** Three competing JSON shapes exist (GAPS §5). **Recommendation:** pick ETA as the canonical JSON for the primary (Egypt) deployment, ZATCA as XML via `payload_xml`, and do not submit to the dead URLs. One integrator must sign off on the exact shape before the einvoice serializer is built. ✅ **RESOLVED → G05/G04** (canonical payload = official ETA Invoice v1.0 schema + eReceipt v1.2, reframed per G05; native reimplementation per G04; the corpus "summer" shapes are ZATCA/Saudi + dead URLs).
6. **`einvoice_counters` rollover + hash format.** Legacy `counter.txt`/`hash.txt` format is undocumented. **Recommendation:** counter = per-`(branch_id, kind)` monotonic int, never reset within a fiscal year; `qr_hash` = SHA-256 over the invoice canonical string; resubmission reuses the same counter/hash (idempotent). Document before implementing the QR chain. ✅ **RESOLVED → A15** (per-(branch,kind) monotonic counter, never reset in fiscal year; SHA-256 QR hash; idempotent resubmission).
7. **RBAC fidelity.** Legacy الصلاحية 1-9 vs fresh role model. **Recommendation:** fresh RBAC (roles/permissions), seeding the legacy 1-9 as permissions; do not try to re-model the legacy grid verbatim (its exact semantics are partially recovered only). ✅ **RESOLVED → G08** (keep legacy 1–9 `permission_level` on users + granular permissions rows; RBAC layers later).
8. **Supplier branch scoping.** `companies` has no branch; `wzcustomers.phar` is per-branch. **Recommendation:** `parties.branch_id NOT NULL`; migrated suppliers assigned to the main branch; a supplier shared across branches is re-created per branch with `branch_identities` linkage. Simplest consistent model; revisit only if supplier-level consolidation is a hard requirement. ✅ **RESOLVED → A16** (`parties.branch_id NOT NULL`; suppliers → main branch; shared supplier re-created per branch).
9. **`balances`/`branch_stock` materialization.** Keep them materialized tables maintained by the posting transaction (they mirror farysales monthe/yearo and titanstock exactly), with a nightly reconciliation job that recomputes them from journals/batches and flags drift. **Recommendation: materialized, not views** — matches legacy semantics and keeps كشف حساب fast. ✅ **RESOLVED → A04** (materialized tables + nightly reconciliation job).
10. **Deployment topology of the chain.** Do all branches point at one FastAPI+PostgreSQL, or is each branch a standalone SQLite device syncing up? **Recommendation: one shared PostgreSQL with per-branch rows + offline SQLite caching for resilience** (FastAPI remains the write path when online). If instead a fully distributed write model is wanted, `sync_log` becomes the primary write mechanism — a bigger design change; decide before Phase 1 lock. ✅ **RESOLVED → G09** (single-pharmacy first, branch-ready schema; one shared PG + offline SQLite cache; chain feature-flagged Phase 2).
11. **Party/account defaults for cash sales.** Anonymous cash sales have `party_id NULL` and no AR posting; the cash side posts to the branch drawer account. **Recommendation: keep `party_id` nullable** (matches legacy cash-sale path) and post cash sales to `drawer_movements` + cash account only; create a default "cash customer" party only if reporting needs it. ✅ **RESOLVED → A17** (`party_id` nullable; post to `drawer_movements` + cash account).
12. **`agel` semantics on `wzdrugs`** (schema_complete.sql:42, "age-related flag"; meaning unconfirmed, GAPS §4.5). **Recommendation: drop the column** from `drugs` until semantics are confirmed; do not carry unknown flags into the new master. ✅ **RESOLVED → A18** (drop `wzdrugs.agel` until semantics confirmed).

---

## Bottom line

The schema is **approved with 8 surgical corrections** (§1.3) and all **10 GAPS §2 contradictions are settled** (§2). The money discipline is exact-decimal on PostgreSQL and **integer minor-units on SQLite** (§4). **A08** moves the plugin-owned (`[S]`) tables into per-plugin schemas/migrations, so core rev 001 ships only core truth tables + the plugin host + seeds (§3, §5.1). The migration path is staged and mostly tooled (§5); the two hard blockers are **production `.phy` samples** (MonyInfo/Dailymax/full Daily tail) and **data-gated confirmations** (G12 invoicedata dump). All 12 open questions in §6 are **resolved** against `plan/00_decisions_master.md` (see the Reconciled note above); no column decision remains open before Phase 1 lock.
---

## Ticket #8 decision note (2026-08-17, appended — no history rewrite)

**3 price levels on `drugs`, not a separate table.** plan/00 F14.3 defines three
selling-price levels (سعر الجمهور / سعر الجملة / سعر الشراء-التكلفة) but plan/01
did not model them. Implemented decision (ticket #8 / S1.2):

* `drugs.price` = public level (existing), **new `drugs.price_wholesale`** and
  **`drugs.price_cost`** columns (NUMERIC(18,4), server_default `0`, CHECK
  `price >= 0 AND price_wholesale >= 0 AND price_cost >= 0`) — rev `005_drug_price_levels`.
  Rationale: the levels are drug attributes (not journal entries); a separate
  `drug_price_levels` table adds indirection without benefit until a future price-
  list slice needs history-per-level (that slice can normalize then).
* `drug_costs` remains the wzdrugs2 legacy ETL mirror (purchase-cost line for
  stock batches), NOT the CRUD surface for price levels.
* VAT-inclusive net = total ÷ 1.14 with per-line `tax_type` (exempt / 5% / 14%),
  per G06; `price_now` (current price) tracks the public price unless explicitly set.
* Money stays exact decimal, API surfaces 2-dp half-up strings (`money.format2`);
  float input rejected (A05).
* New granular permission `drugs.manage` (الأصناف والمخزون) gates drug writes,
  legacy level floor 3 (plan/02 §3).
