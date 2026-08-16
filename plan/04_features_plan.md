# TITAN.W1 → Modern Replacement — Canonical Feature Inventory Plan

**Feature analyst deliverable** for rebuilding TITAN.W1 (Phye.exe, VB6 p-code) as:
FastAPI + PostgreSQL backend, Tauri + React desktop (offline-first, SQLite twin), Next.js web client.

**Sources read (complete corpus):** 23 `feature_*.md` docs + `modules_gap_1.md`, `modules_gap_2.md`,
`modules_remaining_1.md`, `modules_remaining_2.md`, `reports_complete.md`, `ui_complete.md`,
`schema_complete.sql`, `GAPS_REPORT.md`. Target schema companion: `schema/schema_design.md`,
`schema/schema_postgres.sql`, `schema/schema_sqlite.sql`.

**Ground-truth authority (when docs conflict):** `titan_decompile/` (strings_readable.txt 18,972
lines, strings_utf16.txt, pcode_disasm.txt, objects.txt) → `schema_complete.sql` (28 tables) →
`GAPS_REPORT.md` adjudications. **Citation rule:** every `strings_*.txt:N` citation in the feature
docs must be read as **N+3** (GAPS §1, verified). `[VERIFIED]` marks independently verified claims.

**Scope notes / assumptions (explicit):**
1. Field-level truth is the corpus's weakest layer (GAPS §8). This plan adjudicates at the
   **feature/workflow** layer, which is well-covered (~80–90%). Any field-level decision below
   defers to `schema_design.md` / `SCHEMA_RESOLVED.md` (all 11 DDL contradictions already resolved
   there with `schema_complete.sql` shapes winning).
2. **Core-first phasing:** drug master → users/permissions → sales → purchases → stock → returns →
   balances/ledger/close → receivables → reports → chain/integrations.
3. Money is exact decimal (NUMERIC(18,2) totals, 18,4 unit; SQLite minor-units ×10^scale), rounded
   half-up at each line/payment boundary (schema_design §1.2).
4. Every money/stock mutation writes `audit_log` atomically in the same transaction (←
   `TitanUserAction`). Invoice edits additionally snapshot into `invoice_versions`.
5. Sync is last-write-wins via a durable outbox (`sync_log`, `drug_sync_outbox`,
   `branch_identities` alias map) reproducing the legacy `usersourceupdate` pull/delete pattern.
6. **Integrations follow locked decisions (`00_decisions_master.md`):** Egypt ETA e-invoicing is
   **CORE** and rebuilt natively against the ETA official SDK (G04/G05): Invoice v1.0 JSON/XML,
   eReceipt v1.2 JSON, CAdES-BES signing, eSeal X.509 cert, pre-clearance, GS1/EGS codes. The
   legacy dead Saudi/Egypt URLs (EGYPT_ETA_DECOMPILED.md) are reference-only; ZATCA = future Saudi
   override. HungerStation dropped (X07); insurance deferred (X08).

---

## Reconciled 2026-08-16

Locked decisions from `00_decisions_master.md` applied to this plan (full log lives there). Net
effect on features:

- **G01/G04/G05 — ETA e-invoicing is CORE and canonical:** native reimplement (FastAPI worker) per
  the Egyptian Tax Authority official SDK — Invoice v1.0 JSON/XML, eReceipt v1.2 JSON, CAdES-BES
  signing, eSeal X.509 cert, pre-clearance, GS1/EGS codes. The corpus's "3 summer shapes" were
  ZATCA/Saudi + dead URLs (ADJ-18 reframed); ZATCA stays as a future Saudi override.
- **X07 — HungerStation SKIPPED:** delivery-platform integration dropped; manual delivery only.
- **X08 — Insurance DEFERRED:** copay/coverage engine → Phase 2+; `pharmatag-insurance` plugin
  skeleton only.
- **G09 — Chain = Phase-2, single-pharmacy-first:** chain-only features moved to P2.
- **Resolved open questions:** OQ-01 (23 docs), OQ-07 (ETA spec), OQ-08 (native reimplement),
  OQ-10 (CC0 drug DB), OQ-14 (single-first), OQ-15 (deferred), OQ-16 (keyboard-first desktop web),
  OQ-17 (ESC/POS desktop + PDF web). **Data-gated (awaiting dump/vendor specs):** OQ-02..OQ-06,
  OQ-09, OQ-11, OQ-13.

---

## 1. Canonical feature inventory

**23 canonical module groups**, mapped 1:1 to the 23 `feature_*.md` docs. (The earlier working
count of "22" predated confirmation of the last doc; the corpus actually contains 23 feature docs —
see OQ-01.) Each module lists its canonical features with purpose, key legacy entities/screens,
core business rules, dependencies, and build priority.

Priority legend: **CORE** = required for the app to function as a pharmacy POS/back-office
replacement (build order 1–2); **P2** = phase 2 (full product); **L** = later / niche;
**SKIPPED** = explicitly out of scope (decision ID); **DEFERRED** = held for a later phase, minimal
skeleton only.

---

### M01 — Sales invoicing *(feature_sales_invoices.md)* — priority CORE

**Purpose:** The primary POS: add lines by barcode/name, apply price/discount/VAT, settle cash,
card, or credit (أجل), persist invoice + stock + customer-ledger side effects atomically.

Canonical features:

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F01.1 | Sales screen (cash/credit/card settlement) | CORE | `FFFOUTPut`/`FFFOutPut` MDI (278 procs), `FFFStartUp` (252), `FormSellTime` (9), `FormPrintSales` (17) | F9 saves invoice; invoice = header + lines; settlement splits into `payed` (cash/card) + `agel` (credit) with `totalvalue = payed + agel` CHECK; open cash drawer on save/print (configurable). |
| F01.2 | Invoice states & lifecycle | CORE | invoice_status enum (feature doc §2) | States: Saved / Unsaved / **Un save** / Copy / transfer-to-sales-return / transfer-to-purchases / closed / archived / void. A "saved" invoice is immutable except via the editing subsystem (M17). |
| F01.3 | Chain replication of sales | P2 (chain = Phase-2, G09) | `titanksasales` 9-col insert loop, GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (3,564× uses) | Chain sales rows are the syncable summary (`invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue`); replicated through the outbox last-write-wins with `silsilaid` preserved (schema_design §1.4). |
| F01.4 | Line-level detail storage | CORE | `invoicedata` (header+lines fused), `wzgard` (stock batches) | New schema **splits** into `invoices` (header) + `invoice_lines` (lines, with batch/expiry/barcode); legacy fused `invoicedata` is not reproduced 1:1 (see ADJ-08). |
| F01.5 | Invoice printing & receipt | CORE | `FormPrintSales`, `ModPrint` (70 procs), print templates (reports_complete §3) | Print invoice/receipt, open drawer, barcode label; printer set per role (report/receipt/barcode/A4) (reports_complete §4). |

**Dependencies:** M14 (drug master lookup), M15 (customer), M16 (user & permission), M12
(discounts), M18 (VAT), M05 (stock decrement via `wzgard`/batch), M11 (credit creates MRD
receivable), M08/M09 (accounting side effects).

---

### M02 — Sales returns *(feature_sales_returns.md)* — priority CORE

**Purpose:** Reverse a sale: restore stock to batches, credit the customer's receivable, mirror a
chain row, and emit the correct tax-return document type.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F02.1 | Standard sales return | CORE | reverse path in `ModOot` §6.3 | Returned qty ≤ original qty per line; stock restored to the same batch (`wzgard`); receivable reduced; chain mirror row in `titanksasales`. |
| F02.2 | Return variants | CORE | conversion codes 600 vs 800; tax return invoice (فاتورة ضريبية - مرتجع); expiry return (مرتجع اكسبير); paid return (مرتجع مدفوع) | Return type determines tax document + accounting posting; `creditdebit` discriminator (see ADJ-19: modeled as `invoice_kind` + `return_of_invoice_id` in new schema). |

**Dependencies:** M01, M05, M11, M18, M08.

---

### M03 — Purchases *(feature_purchases.md)* — priority CORE

**Purpose:** Supplier inbound: receive stock into batches with cost + VAT + expiry, pay cash/card/
credit, update supplier payable.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F03.1 | Purchase invoice entry | CORE | `ModInn.bas` (71 procs), MDI `FFFINPut` (173), `FFFWaredMonsaref` (36) (المونسرف) | Adds `wzgard` batches at cost; updates `companies` payable; payment split cash/visa/credit/agel. |
| F03.2 | Purchase price recalculation | CORE | `Raz.bas` `ReloadCurent500Inn`, `Titan ReCalculate_By_Value_inn` | Recalculate purchase totals by value; unit cost stored at 4 dp. |
| F03.3 | Last-purchase price & discount | CORE | `storediscount` (16-col), `ModDisc` | "Apply the discount of the last purchase" rule; per-item buy discount from supplier. |

**Dependencies:** M14, M15 (supplier), M16, M05 (stock in), M18, M09 (journal).

---

### M04 — Purchase returns *(feature_purchase_returns.md)* — priority CORE

**Purpose:** Reverse inbound: return goods to supplier (incl. expired-items variant), reduce stock
and payable.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F04.1 | Standard purchase return | CORE | `ModInn` @0x00949e78, `FFFINPut`, `FormReadArcInn` | Reverse stock from the original batch; reduce supplier payable; VAT/credit-note handling. |
| F04.2 | Expired-items return variant | CORE | return-of-expired path | Returns expiry-lapsed stock; posts against a write-off/expiry account. |

**Dependencies:** M03, M05, M15, M18.

---

### M05 — Stock counting & corrections *(feature_stock_counting.md)* — priority CORE

**Purpose:** Physical count, balance correction (تصحيح الرصيد), shelf/chain stock, min-level
control, and auto-order needs input.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F05.1 | Stock count & correction | CORE | `ModStock` class (~165 procs), `ModStorage` (154), `FFFDrugrasidCorrect` (28), `FormDrugRasidCorrectCalc` (3), `FormStockNow` (6), `FormSilsila` (26), `FFFSilsilaStock` (7) | Corrections record cost+VAT and old/new stock into `wzgard` (typee=correction) + `audit_log`; stock correction tracking report (RPT-D10). |
| F05.2 | Minimum-level control | CORE | `FormMinimumControl` (23) | Per-drug `minimum`; drives shortage system (M06). |
| F05.3 | Auto-order / needs suggestions | CORE | `FormAutoOrder` (43), `FormNeedsAll` (50), `FormNeedsDetails` (9), `FormNedBirbish` (6), `FormNeedEntryShow` (4) | Suggest reorder quantities from min-level and sales-rate models (see M06). |
| F05.4 | Stock validation | P2 | `ModStockTest` (4 procs) | Physical-vs-system reconciliation report. |

**Dependencies:** M14, M01, M03, M06, M16.

---

### M06 — Shortages *(feature_shortages.md)* — priority CORE

**Purpose:** Three shortage systems consolidated (النواقص المجمعة).

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F06.1 | Manual shortage system | CORE | `ModNeed`, `FFFNed`, `FormNeedEntryShow`, manual registration report (RPT-ST02) | Operator registers a need manually. |
| F06.2 | Half-automatic (minimum-level) shortage | CORE | `FormMinimumControl` (23), RPT-ST03 | `stock < minimum` ⇒ shortage line. |
| F06.3 | Automatic (sales-rate) shortage | CORE | `FormAutoOrder` (43), `FFFNedAuto` (44), RPT-ST01 | Shortage from sales velocity; combined screen `FormNeedsAll` (50) unifies the 3 (strings idx 13017 "نظام النواقص في تيتان يشتمل علي 3 انظمة"). |
| F06.4 | Needs as inter-pharmacy request | P2 | `titanneed` (5-col: drugname, quant, datee, sender, target), `FormNeedList(PerUser)` | Needs can become transfer requests to another branch (M07). |

**Dependencies:** M14, M05, M07.

---

### M07 — Transfers & logistics *(feature_transfers_logistics.md)* — priority P2 (CORE if chain/multi-branch)

**Purpose:** Inter-branch movement of goods and invoices, drivers/delivery, chain-buy orders,
rawakid (dead stock) exchange.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F07.1 | Branch transfers | P2 | `FormTahwil`, `FormTahwilList`, `titaninn` (transfer role, ADJ-11), `FormMoared` (20) | lifecycle request→approve→ship→receive; source/target branches. |
| F07.2 | Delivery & drivers | P2 | `FormTawsil` (6), `FormDrivers`, `Formdeliver`/`Moddelivery` (3), `delivery.phy` | assign driver from sales screen; delivery reports between work periods; HungerStation integration dropped (M23, X07). |
| F07.3 | Chain-buy / multi-branch purchase | P2 | `FormChainBuy` (6), `FormChainBuyList`, `ChainBuyStore` (12-col), `ChainBuyUsers` (12-col), `RawakidTablew` (12-col) | Cross-pharmacy order items with Mohafaza/Markaz geography; central buy coordination. |
| F07.4 | Rawakid (dead stock) exchange | P2 | `FormRawakid` (10), `RawakidTablew` | Publish/satisfy dead-stock needs across pharmacies. |
| F07.5 | Far-away branch sync (Titanfary) | L | `ModFarWay` (4), `Titanfary.exe`, `\Files\FarWay\FarData\{FromMain,ToMain\Inn,ToMain\Oot}` | File-based master-slave sync; superseded by outbox sync in the new architecture. |

**Dependencies:** M05, M06, M14, M16, M23 (delivery platforms).

---

### M08 — Balances / trial balance *(feature_balances.md)* — priority CORE

**Purpose:** Chart of accounts, trial balance (ميزان المراجعة), balance sheet (الميزانية
العمومية), capital (راس المال), P&L.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F08.1 | Chart of accounts tree | CORE | `ModAccounting` (25 procs), `wzaccfreetree` (mobile/master/fary), `FFFHisabatTree` (18), `FormAccAddQueed`, `FormAcclocalmain` | Hierarchy: اصول (Assets) / خصوم (Liabilities) / حقوق ملكية (Equity) / ايرادات (Revenue) / مصروفات (Expenses), with fixed/current children; per-branch tree. |
| F08.2 | Trial balance (ميزان المراجعة) | CORE | `FormMizanCreate` (33), `FormMizan` (7), RPT-F04 | Debit/credit/balance by account code; detailed variant. |
| F08.3 | Balance sheet & P&L statements | CORE | `FormSafiarbah` (3, راس المال), capital reports, RPT-F02 | Opening capital + investments − withdrawals + net profit = closing capital. |
| F08.4 | Account statement (كشف حساب) | CORE | `FormMonyDetails`, `FormDariba` (5), RPT-F01 | Chronological balance + customer ledger. |

**Dependencies:** M09 (feeds), M10, M11, M15.

---

### M09 — Accounting ledger *(feature_accounting_ledger.md)* — priority CORE

**Purpose:** Double-entry journaling: journal entries (قيود), per-branch account ledgers, general
accounting reports.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F09.1 | Journal entry (قيد محاسبي) | CORE | `ModAccounting` (25), `FormAccAddQueed`, `ModDailyQuiod`, `ModDailyManual`, `FormDailyManual(2)` | Every money/stock event posts debit+credit lines atomically; manual entries allowed with permission. |
| F09.2 | Per-branch ledger | CORE | `farysales` (15-col: mobile/grand/father/son/datee/monthe/yearo/payed/creditdebit/...), `FormMonyDetails`, `FFFMony` | `balances` key `(branch_id, account_id, month, year)` reproduces `farysales.monthe/yearo`; per-branch ميزان reproducible (schema_design §1.1). |
| F09.3 | General accounting reports | CORE | `FormAccReports`, `FormAccUploader` (47) (رفع القيود المحاسبية), RPT-F03 | Debit/credit/balance per account; accounting-entries upload/export. |
| F09.4 | Account closing journal | P2 | `FormEnd`, `ModEnd`, `FormGardMohasaby` | Monthly P&L close → equity. |

**Dependencies:** M08, M10, M01, M03, M11.

---

### M10 — Account closing / day & month close *(feature_account_closing.md)* — priority CORE

**Purpose:** تقفيل اليوم / تقفيل الشهر, cash drawer (الدرج), reconciliation (عجز/زيادة),
end-of-day reports, forced archiving + backup.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F10.1 | Day close (تقفيل اليوم) | CORE | `ModEnd`, `FormEnd` (13), `FormDailyQuiod` (16), `ModDailyQuiod` | Cannot close today before 1 PM (UI string); closed-day is immutable without re-open flow; roll-forward system date. |
| F10.2 | Cash drawer & shift settlement | CORE | `FormDolap` (12, الخزانة/الدرج), `FormUsersMony` (24), `FormTaslimReport`, RPT-A04/H02 | Drawer = opening + cash sales + cash in − cash out; عجز/زيادة (variance) reconciliation; per-user drawer handover between shifts. |
| F10.3 | Month close (تقفيل الشهر) | CORE | `ModBackupMonthly` (13), `\Files\Archive\monthy\`, RPT-H03 | Archive old sales before/at close; month snapshot of balances; monthly backup (M22). |
| F10.4 | Work-period & shift management | CORE | `ModAmil2` (9), `workperiod.phy`, `FormHodour` (16), `FormShiftFawateer` (9) | Shifts bound a day-close period; shift sales inquiry. |

**Dependencies:** M09, M01, M03, M11, M16, M22.

---

### M11 — Receivables / MRD *(feature_receivables_mrd.md)* — priority CORE

**Purpose:** Credit-customer (أجل) receivable management: installment customers (عملاء الأجل),
payments, manual corrections, statements.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F11.1 | MRD master & statements | CORE | `FFFMRD` (11), `FormMRDAgel` (7), `FormMrdKashf` (10) | Installment-customer receivable ledger; credit-sale pipeline (ADJ-16 naming). |
| F11.2 | MRD payments & manual entry | CORE | `FormMrdAmlManual` (9), `FormMrdKashf`, `FormMoamla` (5), `FormDariba` (5) | Payment applied to oldest invoices first; manual adjustment logged to audit. |
| F11.3 | Credit limit enforcement | CORE | `wzcustomers.creditlimit` | Credit sale blocked when debt ≥ credit limit (permission may override). |

**Dependencies:** M01, M15, M09.

---

### M12 — Discounts & offers *(feature_discounts.md)* — priority CORE

**Purpose:** Multi-tier discount engine (per-item, invoice, buy-discount, cash-discount, tax-item
discount) + promotional offers (عروض).

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F12.1 | Discount engine | CORE | `ModDisc` (10 procs), `storediscount` (16-col), `<purchases-disco>`, `<sales-disco>`, `<sales-with-vat-no-disc>` | Multi-tier % stacking up to 100 lines; modes: by currency / by % of profit / by % of total; "Apply sale discount for tax items"; "Clean sale discount for all items". |
| F12.2 | Store discount configuration | CORE | `FormStoreDiscount` (23/26), `storediscount` | Per-branch store discount rules (drugname, disco, quant, datee, country). |
| F12.3 | Promotional offers (عروض) | P2 | `ModOrood` (3), `orooda.phy` | Buy X units → get Y discount; sell X → discount Y; applies to current invoice. |

**Dependencies:** M01, M03, M18.

---

### M13 — Doctors & prescriptions *(feature_doctors_prescriptions.md)* — priority P2

**Purpose:** Prescription capture, drug-disease/DDI safety checks, Wasfaty prescription reporting.
Insurance (تأمين) customers deferred to Phase 2+ (X08).

**Important adjudication (ADJ-13):** the standalone doctor master (`FormDoctor`, `FormDoctorFees`,
`ModDoctor`) is marked **"In project: NO"** in this build (modules_gap_2.md:510,523;1307,1357).
The live surfaces are: prescription link from the sales screen, `FormWasfaty` (27), insurance
through `ModTamin` (15) + `FormAmilTamin` (16)/`FormAmilTamin2` (10), and patient/Drug-Drug checks
through `ModMarid`/`FormMarid*` (5), `ModDisease` (class, 6), `ModDDI` (class, 4), `ModPeInter`
(class, 4), `FormDrugDrug` (22).

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F13.1 | Prescription capture from sales | P2 | sales-screen prescription link, `FormWasfaty` (27) | Attach prescription (patient, doctor name, drugs) to a sale; Wasfaty period report (RPT-S15). |
| F13.2 | Insurance company pricing & invoice | DEFERRED (P2+, X08) | `ModTamin` (15), `FormAmilTamin(2)`, insurance reports (RPT-S09, RPT-C03) | Copay vs coverage split; insurance-specific invoice format; insurance-company customer filter. **Deferred to Phase 2+; `pharmatag-insurance` plugin skeleton only (X08).** |
| F13.3 | Drug safety checks (DDI/disease/patient) | P2 | `ModDDI`, `ModDisease`, `ModPeInter`, `FormDrugDrug` (22), `DDI.Phy`, patient data | Alert on interacting drugs / contraindicated-for-condition / patient-allergy; warning, not block. |
| F13.4 | Doctor master | L | `FormDoctor` (NOT in build) | Optional phase-3; absent from this build, so not required for parity. |

**Dependencies:** M01, M15, M16, M14.

---

### M14 — Drug master & pricing *(feature_drug_master_pricing.md)* — priority CORE (foundation)

**Purpose:** The drug catalog: Arabic/English names, generic, category, up to 5+1 barcodes,
packaging/unit conversions, three price tiers (سعر الجمهور / سعر الجملة / سعر الشراء-التكلفة),
VAT flag, price history, GS1 parsing.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F14.1 | Drug master CRUD | CORE | `wzdrugs` (29-col) + `wzdrugs2` (unitcost/costvalue/expire), `FFFNewDrug` (19), `FFFNewDrugServer` (28), `FormDrugsDetails` (51), `FFFNed`/`FFFNedw` | drugname unique natural key; lastedit logged to `audit_log`; `titanid` for chain sync; `localimport` source flag. |
| F14.2 | Multi-barcode lookup | CORE | `barcode` + `Barcode1..5`, `ModGS1Reader` (24), `FormMoreBarcodes` (8), `ModMergeBarcodes` (15) | Find drug by ANY code; GS1/DataMatrix/QR parse (GTIN/01, batch/10, expiry/17, serial/21); duplicate-barcode merge + undo. |
| F14.3 | Pricing tiers & price history | CORE | `FormDrugPrice` (18), `FormFixDrugPrice`, `FormTareefha`, `oldprices.phy`, `prices-changes.txt` | public/wholesale/cost; official-price update incl./excl. VAT (FormVat2 strings); price-change log → `price_change_log` + audit. |
| F14.4 | Unit conversions & packaging | CORE | `wzdrugs.units`, `Unitsmall`, `ModDRGEXChange` (4), `unit_conversions` table | box→strip→tablet factors; `exchangeRate` in cloud JSON. |
| F14.5 | Drug name unification & similarity | P2 | `ModDrugsUnify` (10), `FormDrugNameUnify` (12), `FormSimilars` (5), `FormReapetedDrugMerge` (10) | Merge duplicate names/similar formulations; barcode merge; near-similar search. |
| F14.6 | GS1 barcode label printing | P2 | `FormBarcodeSettings` (13), `FormParCode` (14), `ModGS1Reader`, label templates | Zebra labels, split/non-split, A4 6×24 grid, shelf labels (reports_complete §3.4). |

**Dependencies:** M16, M18, M23 (drug database import), M05.

---

### M15 — Customers & suppliers *(feature_customers_suppliers.md)* — priority CORE (foundation)

**Purpose:** Party master handling both customers and suppliers with credit accounts.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F15.1 | Party master (customer/supplier/both) | CORE | `wzcustomers` (randomid/typee/creditlimit/namee/...), `companies` (mobile PK), `ModMarid` (4 procs, 107-field struct), `FormMaridData` (15), `FormMarid` (5), `FormCoData` (8), `FFFWaredMonsaref` | `typee` distinguishes customer vs supplier; a company that is both → `kind='both'` with separate receivable/payable accounts (schema_design §1.7). |
| F15.2 | Customer/supplier credit accounts | CORE | `wzcustomers.creditlimit`, `ModMoamla` | Credit sale raises receivable; purchase raises payable; debt/dues reports (RPT-C01, RPT-SUP01/02). |
| F15.3 | National-ID / address capture | P2 | `FormIDCard`, `FormAddress`, JSON buyer fields (buildingNumber/governate/regionCity/street/postalCode) | Needed for B2B e-invoice and Wasfaty; Egyptian national-ID format. |

**Dependencies:** M01, M03, M11, M16, M09.

---

### M16 — Users, permissions & menus *(feature_users_permissions_menus.md)* — priority CORE (foundation)

**Purpose:** Authentication, 8 user types, 1–9 permission level, per-user menu access, shifts,
attendance, user money/drawer, audit trail.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F16.1 | Authentication & user accounts | CORE | `FFFStartUp` (252), `FFFUserEdit` (18), `FFFUserChoose` (19) | Username is a 17-digit numeric ID; password change; hide-password-on-manager-login option. |
| F16.2 | Permissions & menus | CORE | `FFFUserMenu`, `FFFUserMenuList`, `FormMenusPerUser`, `FormEmployee`, 8 user types, صلاحية 1–9 | Per-user menu/permission sets; e.g. صلاحية ≥7 required for balance edits; "اختبر الصلاحيات" test button; discount permission toggle per employee. |
| F16.3 | Shifts & attendance | CORE | `ModAmil2` (9), `FormHodour` (16), `FormHodour19` (35), `amil2.phy`/`AmilInfo.phy`, RPT-A02/A03 | Shift in/out by barcode; attendance; total employee hours in period. |
| F16.4 | User money & drawer handover | CORE | `FormUsersMony` (24), `FormTaslimReport` (تسليم الدرج) | Employee sales settlement; تسليم مبيعات الموظفين; drawer handover between shifts (RPT-A04). |
| F16.5 | Audit trail | CORE | `TitanUserAction` (11-col), `FormHistory`, `FormJournal`, activity-log report (RPT-A06) | Every mutation logged atomically; screens/menus/reports can filter by user/action/date. |

**Dependencies:** none (foundation); consumed by all modules.

---

### M17 — Invoice editing & corrections *(feature_invoice_editing.md)* — priority CORE

**Purpose:** Track-and-edit invoices, day-end manual entries, price/discount/stock corrections —
all audited.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F17.1 | Invoice edit tracking | CORE | `FormInvoiceTrackEditing`, `FormLastEdited` (10), `LastEdited.phy`, RPT-SP03, RPT-D05/F09 | Reverse-then-reapply; full pre-edit snapshot into `invoice_versions` (schema_design §1.3). |
| F17.2 | Daily manual entries (قيود يدوية) | CORE | `ModDailyQuiod`, `ModDailyManual` (6), `FormDailyManual(2)`, RPT-F10 | Manual money/stock adjustments allowed with permission; audited. |
| F17.3 | Price/discount/stock corrections | CORE | `FFFOOTQuant`, `FFFINNquant`, `FFFDrugrasidCorrect` (28), `FormDiscCorrect` (4), `FFFDiscCorrect`, `FormOutPuttakarirSpeed` (9) | Corrections post cost+VAT into `wzgard`; every correction → audit + correction-tracking report. |
| F17.4 | Invoice date edit | P2 | `FormEditFatDate`, `FormEditFatDate2` | Batch re-date invoices (e.g. catch-up entries); restricted permission. |

**Dependencies:** M01, M03, M05, M16.

---

### M18 — Tax invoicing *(feature_tax_invoicing.md)* — priority CORE (Egypt-first); Saudi = future override

**Purpose:** VAT calculation (Egypt 14% standard / 5% medical devices / medicines exempt 0% per
G06; Gulf 15% as override), VAT reports, ETA (Egypt) e-invoicing per the official ETA SDK spec.
ZATCA (KSA) kept as a future Saudi override only (G01).

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F18.1 | VAT calculation & display | CORE | `FormVat` (20), `FormVat2` (38), `<masrofat-vat>` | VAT on items flagged taxable; prices stored incl. or excl. VAT per `branches.vat_inclusive_prices`; per-line `tax_type` split (exempt/14%/5%); Egypt default 14%, medicines VAT-exempt 0% (G06); Gulf 15% as override. |
| F18.2 | VAT reports | CORE | `ModVatReport` (3), `FormVat`/`FormVat2`, RPT-F07/F08 | Quarterly GCC VAT, Egypt VAT periods; total-before-tax / total-tax / 15% columns; files in `Files\Accounting\Vat-reports\`. |
| F18.3 | ZATCA e-invoicing (KSA) — future Saudi override | L | `ModZatca2Wraber` (23), `ModSaturn` (24), `Modzatcasign` (3), `ZATCA` log, `einvoice_log` | **Not primary scope (G01/G04).** If a Saudi deployment is needed later, rebuild against the official ZATCA standard — NOT the corpus's 3 "summer" shapes (see ADJ-18). CSID, XML+QR, invoice counter/hash chain in DB (`einvoice_counters`). |
| F18.4 | ETA e-invoicing (Egypt) — canonical | CORE | `ModEtaWrappper` (7), `ModDttsEgypt` (2), `ModOuterConnections` (18), `FormEtaInfo` (9) | **Rebuilt natively per ETA official SDK (G04/G05; supersedes ADJ-21):** Invoice v1.0 JSON/XML, eReceipt v1.2 JSON, CAdES-BES signing, eSeal X.509 cert, SHA-256 QR + per-(branch,kind) counter/hash, pre-clearance submission, GS1/EGS codes; async submit/poll/notify via REST + OAuth. Legacy dead URLs are reference-only. |

**Dependencies:** M01, M03, M02, M04, M14, M15, M23.

---

### M19 — Operational utilities *(feature_operational_utilities.md)* — priority L (P2 for several)

**Purpose:** Small daily-use screens that are cheap to rebuild and add parity polish.

| ID | Feature | Priority | Key legacy entities |
|----|---------|----------|---------------------|
| F19.1 | End-of-day cash flow view | P2 | `FormootThisDay` (11), `FormMagazine` (12) |
| F19.2 | Cash-receipt corrections | P2 | `FormMrdKashf` (10), `FormCorrecyMony` (4) |
| F19.3 | Offer/price extras & classifications | L | `FormOrood1` (7), `FFFPriceExtra` (3), `FFFDrugsClassification` (2), `FormTareefha` |
| F19.4 | Short-day-notes & daily instructions | L | `FormDaysShortNote` (14), `Modeveryday` (9), `dailynotes.html` |
| F19.5 | Quick calculators & micro-tools | L | `FormCalculator` (10), `FFFPiano` (12), `FFFSODUKU` (36), `FFFUM` (10), `FFFMHFZ` (10), `FormExam` (7), `Forminputtotal` (5), `FormExForceChanged` (3) |

**Dependencies:** M01, M10, M16.

---

### M20 — Reports & analytics *(feature_reports_analytics.md + reports_complete.md)* — priority CORE

**Purpose:** 18 report categories, ~70 catalogued reports, printing, export (PDF/Excel/CSV/HTML/
clipboard).

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F20.1 | Report hub & categories | CORE | `FormReportsGeneral` (61), `ModPrint` (70), `FormReport(s)` | 18 Arabic categories (sales, purchases, customers, volume, history, shortages, accountant, shift handover, delivery, chain, capital, misc, company dues, employee); permission + report-password gate. |
| F20.2 | Core report set | CORE | FFFOutputTakarir (16), FFFInputTakarir (16), `FormOutPuttakarirSpeed` (9), `FormAmilTakarir` (23) | Sales/purchase/returns/customer/employee/drug/volume/profit reports (RPT-S01..S15, P01..P07, C01..C04, SUP01/02, A01..A06, ST01..ST06, D01..D10, F01..F11, OP01..OP05) — SQL per report spec in reports_complete.md §2. |
| F20.3 | Printing system | CORE | `FormPrinterSettings` (31), `FormPrinterSettingFary` (28), `FffSelectPrinter` (2) | 5 printer roles (report/receipt/barcode/invoice/A4); paper/orientation/margins/copies; auto-print + open-drawer flags. |
| F20.4 | Export | CORE | Excel/CSV/PDF/HTML/clipboard; `مجلد ملفات الاكسيل` | CSV delimiter configurable; UTF-8; PDF save; HTML summary dashboard. |

**Dependencies:** all modules (read side); M16 (report access).

---

### M21 — Misc modules *(feature_misc_modules.md)* — priority L (P2 for a few)

**Purpose:** Translation, number-to-words, countries, mobile/cloud helpers, offers infra, misc
wrappers. Most are infrastructure, not user features.

| ID | Feature | Priority | Key legacy entities |
|----|---------|----------|---------------------|
| F21.1 | Arabic↔English UI translation & number-to-words | P2 | `ModTranslator` (5), `ModEnglishtoArabic` (7), `ModTafqit` (4) — Arabic/English amounts-on-invoice (جنيه/ريال) |
| F21.2 | Country config (currency/VAT/language/ZATCA flag) | P2 | `ModCountries` (24), `companies.country`, `app_config` |
| F21.3 | Offers infrastructure | P2 | `ModOrood` (3) — shared with F12.3 |
| F21.4 | Mobile & cloud companion hooks | L | `ModMobile` (9) — registration, cloud sync |
| F21.5 | Misc wrappers (SQL, files, FlexGrid, wheel, screen, colors, WMI) | L | `ModSQL` (13), `ModFiles`/`Files` (20/41), `FLXMod` (55), `ModFlexWheel` (6), `ModScreen` (3), `ModColors` (3), `ModWMI` (12), `VB7` (42) — **infrastructure, not rebuild targets as-is** |

**Dependencies:** infrastructure only.

---

### M22 — Backup, archive & import/export *(feature_backup_archive_import.md)* — priority CORE

**Purpose:** Data safety: daily/monthly backup, monthly archive, single-file export/import, DBI
migration, "one file" transfer.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F22.1 | Backup & restore | CORE | `ModBackUp`, `FormBackup`, `FormBackRestore` (4), `FormRestore` (6), `FFFDackupAuto` (7), `Restore.bak` | Backup before day close; auto-backup; `Labirdo\Titan3-Backup\{Daily,Monthly}` rotation. |
| F22.2 | Monthly archive | CORE | `ModBackupMonthly` (13), `ModArchive` (2), `\Files\Archive\{Input,Output}`, `monthy\` | Archive old sales; compression; archive restore; verify; `FORCEARCHIVE`. |
| F22.3 | Single-file export/import (one file) | P2 | `ModOneFile` (23) | All data serialized to one file; validation + integrity checks. |
| F22.4 | Invoice import/export & branch exchange | P2 | `FormImportFat` (14), `FormExportFat`, `FormGetFats` (2), `FormImportFromOtherDBI` (19), `FormExportdataBase` (8), `FormImportFromExcell` (6) | Invoices between branches; Excel/CSV import; other-DBI import. |
| F22.5 | Database cleanup (تصفية قاعدة البيانات) | P2 | `FormDatabase`, `FFFClean` (36), `FormReadVer2` (14) | Delete old invoices while keeping drug/customer/supplier balances. |

**Dependencies:** M01–M10 (data), M16.

---

### M23 — External integrations *(feature_external_integrations.md)* — priority P2 (CORE where local law requires)

**Purpose:** Regulatory, market-data and delivery integrations.

| ID | Feature | Priority | Key legacy entities | Core business rules |
|----|---------|----------|---------------------|---------------------|
| F23.1 | ZATCA (KSA) — future Saudi override | L | `ModZatca2Wraber`, `ModSaturn`, `Modzatcasign`, `einvoice_log`, `einvoice_counters` | See F18.3. Out of primary scope (G01); rebuild against official ZATCA standard if a Saudi deployment is needed. |
| F23.2 | ETA e-invoicing (Egypt) | CORE | `ModEtaWrappper`, `ModDttsEgypt`, `EGYPT_ETA_DECOMPILED` | Per official ETA SDK (G04/G05): Invoice v1.0 JSON/XML, eReceipt v1.2 JSON, CAdES-BES signing + eSeal cert, pre-clearance, GS1/EGS codes. **Native reimplement (FastAPI worker), not EXE wrapping** (OQ-08). |
| F23.3 | DrugEye / drug database feed | P2 | `drgserver`, `usersourceupdate`, `drugeye_complete`, `drug_database_legal` | **Do not ship DrugEye data** (ADJ-20): use CC0 `karem505/egyptian-drug-database` + SFDA open data instead. |
| F23.4 | Nielsen market data | L | `nilsen2`, `ModNilsen` (class, undocumented) | ;-delimited, 6-month windows, RAR upload; ingestion path undocumented (OQ-11, awaiting data). |
| F23.5 | HungerStation / delivery platforms | SKIPPED | `Moddelivery`, OAuth token file, `hungerstation.partner.deliveryhero.io/v2/chains/` | **Dropped from scope (X07; resolved from OQ-12).** Contract was undocumented; not built. Delivery = manual assignment only (F07.2). |
| F23.6 | Cloud/network sync infra | P2 | `ModNetwork` (65), `ModSqlLink` (19), `ModTitanCloud` (16), `ModFTP` (10), `remotecontrol` | Replaced by outbox sync in new architecture; `remotecontrol` "passed functions" = **security anti-pattern, not rebuilt** (ADJ-22). |
| F23.7 | Country info / QR / other web services | L | `ModOuterConnections` (18), QR endpoints | Replaced by server-side services in the new stack. |

**Dependencies:** M01–M04, M07, M14, M18.

---

## 2. Contradictions & unknowns — adjudication

Every conflict found in the corpus, with the adjudicated decision. All `strings` citations are
**N+3** (ADJ-01). Field-level DDL contradictions were already resolved in
`SCHEMA_EVALUATION.md`/`SCHEMA_RESOLVED.md` (11 adopted, `schema_complete.sql` shapes win) and are
recorded here for traceability.

### 2.1 Systematic citation bug
**ADJ-01 — string-index vs line-number (off-by-+3).** `string index = line − 3`. All
`strings_*.txt:N` citations read as `N+3`. Verified: 4945→4948 (TitanUserAction INSERT),
4943→4946 (ChainBuyUsers INSERT), 5867→5870 (ChainBuyUsers SELECT) `[VERIFIED]`. **Action:**
mechanical `+3` fix across all 23 feature docs before builder uses any citation.

### 2.2 Schema contradictions (all resolved → `schema_complete.sql` shapes win; documented in SCHEMA_RESOLVED)
**ADJ-02 — `titanksasales` 9 vs 15 cols.** 9-col summary shape is ground truth (chain-sync loop);
the 15-col line-item shape belongs to a line-item table, not `titanksasales`. New schema: chain
summary replicated via outbox; line detail in `invoice_lines`.
**ADJ-03 — `titanksastock` 8 vs 24.** 8-col ground truth; 24-col form is a business_logic doc error.
**ADJ-04 — `titanneed` 5 vs 7.** 5-col needs-request ground truth; the 7-col shape is a
stock-snapshot error.
**ADJ-05 — `TitanUserAction` 11 vs 10 vs 10.** 11-col with `id IDENTITY` ground truth
(`schema_complete.sql:266-278`; the feature doc's cited range `245-256` is wrong — see ADJ-01
cross-file symptom).
**ADJ-06 — `usersourceupdate` 6 vs 9 vs 4.** 6-col ground truth (`schema_complete.sql:283-290`).
The 9-col form in raw `schema.sql` is a legacy variant of the same pull; 4-col form is
permissions_complete's error.
**ADJ-07 — `ChainBuyUsers` 12 vs 4 vs 1.** 12-col ground truth (`schema_complete.sql:338-353`);
4-col is the raw-schema variant; 1-col is permissions_complete's error.
**ADJ-08 — `invoicedata` header+lines fused.** Undecidable in legacy; new schema **splits** into
`invoices` + `invoice_lines`. Legacy fused table not reproduced.
**ADJ-09 — `wzphar` `pharname` vs `pharmacyname`.** SQL evidence (`group by pharmacyname,adress`,
`select pharmacyname,adress,... from storediscount`) wins → **`pharmacyname`**.
**ADJ-10 — `taronlineeg` vs `farysales` column swap.** reports_complete.md:1040 attributed
`farysales`' 15-col list to `taronlineeg`. Ground truth: `farysales` is the per-branch
debit/credit ledger (15-col); `taronlineeg` is the online drug-data table. Follow `schema_complete.sql`.
**ADJ-11 — `titaninn` transfer vs purchases.** Transfer table (fatid/itemsasstring/source/target)
wins for the table; the "purchase/inbound" role belongs to invoice tables. New schema: transfers
are a first-class entity.
**ADJ-12 — raw `schema.sql` vs `schema_complete.sql`.** `schema_complete.sql` wins (all 11
adjudications in SCHEMA_RESOLVED adopt its shapes).

### 2.3 Corpus-count / naming contradictions
**ADJ-13 — Doctors module absent in build.** `FormDoctor`/`FormDoctorFees`/`ModDoctor` are
"In project: NO". Prescription features are rebuilt from the live surfaces (sales-screen link,
`FormWasfaty`, `ModMarid`); insurance (`ModTamin`, `FormAmilTamin(2)`) is rebuilt from the live
surfaces but **deferred to Phase 2+ (X08)**. Doctor master is optional (L). Parity is defined
against the live surfaces, not the absent forms.
**ADJ-14 — form count 212 vs 237.** 237 = total objects in project_structure (includes
non-form objects / stubs); 212 = form count in gap_2 methodology. Non-blocking; not a feature issue.
**ADJ-15 — 23 feature docs vs "~28" claimed.** Corpus contains exactly 23 `feature_*.md`. No 28th
doc exists. The 22-module grouping maps to these 23 docs (see §1 note).
**ADJ-16 — MRD naming.** `ui_strings.json` labels all four MRD forms "حسابات المدينة" variants;
`ui_complete.md:140-144` labels by function (installment customers / MRD payments / manual /
kashf). **Functional labels win** for the new UI.
**ADJ-17 — `FormDrugsList` vs `FormDrugsLists`.** `FormDrugsLists` (15 procs, ui_complete.md:86)
is the real drug-list form; `FormDrugsList` in gap_2 is a name variant. Use `FormDrugsLists`.

### 2.4 Integration-shape contradictions
**ADJ-18 — three competing ZATCA "summer" JSON shapes (superseded by G05).**
reports_complete.md §7.2, api_integration.md:216-328, zatca_complete.md:99-205 were three
competing ZATCA/Saudi shapes with dead URLs. **Superseded:** the canonical payload is the ETA
official SDK spec — Invoice v1.0 JSON/XML, eReceipt v1.2 JSON (G04/G05; OQ-07 resolved to ETA
spec). The corpus shapes are kept only as a future Saudi-override reference.
**ADJ-19 — `creditdebit` return discriminator missing from schema.** The column appears in report
SQL but in no ground-truth CREATE TABLE. Model as `invoice_kind` + `return_of_invoice_id` in the
new schema (GAPS §7.6; `wzgard.typee`/`invoicedata.agel` hold the legacy meaning).
**ADJ-20 — DrugEye licensing.** Do **not** ship DrugEye data (drug_database_legal.md:241-260).
Use CC0 `karem505/egyptian-drug-database` + SFDA open data. The Drugeye feed is ROT-4 text, not a
protected format `[VERIFIED]`; the decoded 23,452-record dump exists in `/tmp/opencode/`.
**ADJ-21 — dead ETA/DTTS endpoints (superseded by G04).** The corpus's legacy Saudi/Egypt URLs are
dead and reference-only. **G04 overrides:** ETA e-invoicing is rebuilt natively (FastAPI worker,
CAdES-BES + eSeal, Invoice v1.0 / eReceipt v1.2, pre-clearance); no saturn/toolkit EXE wrapping.
**ADJ-22 — `remotecontrol` "passed functions" & AnyDesk backdoor.** Security anti-pattern (remote
code push + AnyDesk remote control). **Not rebuilt.** Telemetry/update channels are replaced by a
documented, consent-based updater or omitted.

### 2.5 Unconfirmed purposes (behavior asserted, not proven — treat as low-confidence, verify in pcode)
**ADJ-23 — `Titan CorrectStockForAll` / `ReloadRasidCorrect500` / `Reload_Drugs_in_last_Invoices`
/ `Titan ZuFillEmptyNameIftheresStock`.** Named "stock correction" but the correction rule is
never stated. **Action:** implement stock correction from the documented `wzgard`
typee=correction semantics; treat the four named routines as internal triggers, not spec.
**ADJ-24 — `agel` column meaning.** "age/type" per schema; in cash-flow logic it encodes
credit/agel amounts. New schema: `payment_splits` + explicit `agel` semantics (unpaid portion).
**ADJ-25 — empty/stub modules.** `ModOOTTrans` (4 bytes), `Modhelp`, `ModCompany`, `Types`,
`ModChanges`, `ZzBookMark` — **dead placeholders**, not rebuilt.

### 2.6 Undocumented persistence (blocking for data migration, not for feature design)
- **`.phy` money files** (`Daily*.phy`, `workperiod.phy`, `delivery.phy`, `PIFary.phy`,
  `fary.date.phy`, `drugeye-for-titan.phy`, `oot3.phy`, `rasd-config.*`) have **no complete record
  layouts** except partial `ModDrgW` mapping (GAPS §3.3, §5). Full per-file field maps were never
  produced. **Action:** `PHY_MIGRATION.md` (already in corpus) + `RECORD_LAYOUTS_daily_phy.md`
  cover the daily-family; complete the rest before migration ETL. This is a **migration** blocker,
  not a feature-design blocker.
- **`ZATCA` table is 100% inferred.** The real legacy log may live in saturn files; new schema
  defines `einvoice_log` regardless (schema_design §1.5).

---

## 3. Feature dependency graph

Build layers (bottom-up). Arrows mean "depends on". All CORE modules in layers 1–2 form the
**MVP**; layers 3–4 are phase 2.

```
LAYER 0 (foundations — build first, no deps)
  M16 Users/Permissions/Menus      M14 Drug Master & Pricing      M15 Customers & Suppliers
       │                               │                                │
LAYER 1 (transactions)
       ├─────────────┬─────────────────┴────────────┬───────────────────┤
  M01 Sales         M03 Purchases        M12 Discounts/Offers   M18 Tax/VAT
   │  │               │  │                   │                     │
LAYER 2 (consequences — build same milestone as layer 1)
   │  ├───────────────┤  │
  M05 Stock/Counting  M02 Sales Returns    M04 Purchase Returns   M11 Receivables (MRD)
   │       │                │                   │                     │
LAYER 3 (money & close — CORE, after transactions are correct)
   ├───────────────────────────┬─────────────────────────────────────────┤
  M06 Shortages               M09 Accounting Ledger ─── M08 Balances/Trial Balance
   │                              │
  M10 Account Closing (day/month, drawer, shifts) ─────────── M22 Backup/Archive
   │
  M20 Reports & Printing (reads everything above)

LAYER 4 (phase 2 — parallelizable once layers 1–3 are stable)
  M07 Transfers & Logistics      M13 Doctors & Prescriptions     M17 Invoice Editing & Corrections
  M19 Operational Utilities      M21 Misc Modules                M23 External Integrations
```

Phase order for the roadmap:
1. **MVP (layers 0–2):** M16 → M14 → M15 → M01/M03 (+ M12/M18) → M05 → M02/M04 → M11.
2. **Money close (layer 3):** M09/M08 → M10 → M22 → M20.
3. **Phase 2 (layer 4):** M07, M13, M17, M19, M21, M23.

Key cross-cutting dependencies to respect:
- **M05, M01, M03 share stock state.** Stock mutations (sale, purchase, return, correction) all
  write `stock_batches`/`branch_stock` and `audit_log` in one transaction; build a single stock
  service (service layer) rather than per-module writes.
- **M09 consumes every money event.** Journal posting must be a transaction-side effect, not a
  batch job.
- **M11 depends on the credit path of M01** (credit sale → receivable) and on M15
  (`creditlimit`).
- **M10 depends on M09** (close requires balanced ledger) and on M01/M03 totals.
- **M20 reads all; M22 protects all.** Neither blocks the other modules.

---

## 4. Definition of complete — per core feature

A feature is **done** when it passes all of: (a) the workflow it replaces, (b) the side-effect
invariants, (c) audit/sync, (d) reports/print, (e) data-migration path. Detailed checklists per
core feature:

**F14 Drug master** — CRUD for Arabic/English name, generic, category, company, 5+1 barcodes,
units/conversions, 3 price tiers, VAT flag, expiry-aware batches; lookup by ANY barcode/name;
price-history + audit on every change; migration ETL from `wzdrugs`/`wzdrugs2`/`titanstock`
accepts a dump file and round-trips.

**F16 Users/permissions** — login with 17-digit numeric ID; 8 roles; 1–9 permission level with
per-menu/action grants; "اختبر الصلاحيات" test; shift/attendance via barcode; per-user drawer
handover; audit-log shows every permission-denied attempt and every balance edit by صلاحية ≥7 rule.

**F01 Sales** — line add by barcode/name (GS1 incl.); price tiers; discount engine (all modes of
F12); VAT incl./excl.; settlement cash/card/credit with `totalvalue=payed+agel` invariant; F9 save;
stock decrement + audit + chain row + receivable credit all in one transaction; invoice + receipt
print; all invoice states including "Un save" and Copy.

**F03 Purchases** — supplier inbound with batch/cost/VAT/expiry; `ReloadCurent500Inn`-
equivalent recalc; payable update; last-purchase-discount application; purchase reports
(RPT-P01..P07) correct; stock in + audit + journal side effects transactional.

**F02/F04 Returns** — qty ≤ original enforcement; stock restored to original batch; receivable/
payable reversed; correct tax-return document type per variant (standard/expiry/paid, 600/800);
chain mirror row; return reports correct.

**M05 Stock counting** — physical count vs system with correction posting cost+VAT into batches;
old/new stock in audit; correction-tracking report; min-level and auto-order suggestions consume
the same stock truth.

**M06 Shortages** — the 3 systems individually correct AND the combined screen (النواقص المجمعة)
aggregates them; needs→transfer handoff works.

**M11 Receivables** — credit sale creates receivable; payment applies oldest-first; manual
adjustment audited; `creditlimit` enforced; statements (كشف حساب) and MRD reports correct.

**M09/M08 Balances & ledger** — every money event posts balanced debit/credit; trial balance
balances (debit=credit); balance sheet + P&L + capital statements reproduce the legacy
categories; per-branch `balances(branch_id, account_id, month, year)` correct.

**M10 Close** — day close blocked before 1 PM and when day already closed; drawer math
(opening+cash in−cash out) reconciles to عجز/زيادة; shift handover per user; month close archives
+ snapshots balances; closed days immutable.

**M22 Backup/archive** — backup runs before day close; auto-backup schedule; monthly archive
compress/restore/verify/FORCEARCHIVE; single-file export/import round-trips the whole DB.

**M20 Reports** — all CORE report IDs (RPT-S01..S15, P01..P07, C01..C04, SUP01/02, A01..A06,
ST01..ST06, D01..D10, F01..F11, OP01..OP05) return correct numbers from the new schema; print to
the 5 printer roles; export PDF/Excel/CSV/HTML; report-password + permission gating.

**M18 Tax** — VAT per line incl./excl. with per-line `tax_type` (exempt/14%/5%), matches totals;
quarterly/GCC/Egypt VAT reports match source SQL; ETA produces Invoice v1.0 JSON/XML + eReceipt
v1.2 with CAdES-BES/eSeal and atomic counter/hash (G04/G05); ZATCA = future Saudi override only.

**M13 Doctors (P2)** — prescription attached to sale; Wasfaty period report; DDI/disease/patient
checks warn (not block). Insurance copay/coverage split deferred to Phase 2+ plugin (X08).

**M07 Transfers (P2)** — request→approve→ship→receive lifecycle; chain-buy orders with
Mohafaza/Markaz; rawakid exchange; delivery/drivers with cash-collection reports.

---

## 5. Open questions (numbered)

1. **OQ-01 — corpus count.** The source list said "~28 feature docs"; exactly **23** exist. Are
   there 5 more docs elsewhere (e.g. in `titan_decompile/` or a sibling directory), or is 23 the
   real count? **→ RESOLVED 2026-08-16:** 23 is the real count (X13; no missing docs).
2. **OQ-02 — `invoicedata` runtime usage.** Is `invoicedata` actually read at runtime, or is the
   real line storage `wzgard` (1:1 by `randomid`)? This decides the new invoice_lines source of
   truth. (GAPS §7.7; verify in pcode.) **→ AWAITING DATA** (production dump).
3. **OQ-03 — return discriminator.** Confirm `creditdebit` semantics against raw pcode strings —
   does it live in `wzgard.typee`, `invoicedata.agel`, or is it purely report-SQL? (ADJ-19.)
   **→ AWAITING DATA** (X11).
4. **OQ-04 — `taronlineeg` vs `farysales`.** Confirm via pcode which INSERT targets which table
   before building the ETA/online-gov module. (ADJ-10.) **→ AWAITING DATA** (X12).
5. **OQ-05 — stock-correction rule.** What exactly do `Titan CorrectStockForAll` /
   `ReloadRasidCorrect500` rewrite (thresholds, dedup key, fields)? (ADJ-23.)
   **→ AWAITING DATA** (X10).
6. **OQ-06 — `.phy` money-file layouts.** Complete record layouts for
   `Daily.phy`/`Dailyline.phy`/`Dailymax.phy` (beyond RECORD_LAYOUTS_daily_phy.md),
   `workperiod.phy`, `delivery.phy`, `PIFary.phy`, `fary.date.phy`, `oot3.phy`,
   `rasd-config.*` — needed for migration ETL. **→ AWAITING DATA** (X01).
7. **OQ-07 — ZATCA canonical JSON.** Which of the 3 "summer" JSON shapes does
   `saturn.exe`/`toolkit.exe` actually consume? (ADJ-18; check `--generate-uuid` arg match.)
   **→ RESOLVED 2026-08-16:** canonical = ETA official SDK spec (G05); corpus shapes were
   ZATCA/Saudi + dead URLs.
8. **OQ-08 — external ZATCA toolchain.** Re-wrap `saturn.exe`/`toolkit.exe` (BouncyCastle signing)
   or reimplement signing in the new stack? Decision gates F18.3/F23.1.
   **→ RESOLVED 2026-08-16:** native reimplement (G04); no EXE wrapping. CAdES-BES via a crypto
   lib; eSeal key storage in `einvoice_log`/`einvoice_counters`.
9. **OQ-09 — `creditdebit`/`payed` in ground truth.** The 9-col `titanksasales` has no
   `creditdebit`/`payed`-vs-`agel` split beyond `payed`/`agel`/`disc`/`totalvalue`. Confirm the
   chain row's debt semantics. **→ AWAITING DATA** (X11).
10. **OQ-10 — drug master migration source.** Adopt CC0 `karem505/egyptian-drug-database` + SFDA
    open data as the seed catalog? (ADJ-20.) Legal sign-off required.
    **→ RESOLVED 2026-08-16:** yes — CC0 `karem505/egyptian-drug-database` (G03, research-verified).
11. **OQ-11 — Nielsen ingest.** How is `nilsen2` populated (which module/format)? If it cannot be
    recovered, is Nielsen parity required (L) or dropped? **→ AWAITING DATA** (X09).
12. **OQ-12 — HungerStation contract.** OAuth + `v2/chains/` request/response contract is
    undocumented. Obtain the spec or drop to "delivery assignment only".
    **→ RESOLVED 2026-08-16:** SKIPPED (X07) — dropped from feature inventory / plugin scope;
    manual delivery only (F07.2).
13. **OQ-13 — report SQL reconstruction.** `FormReportsGeneral` (61 procs) maps ~45 report types
    to forms, not SQL. Reproduce each report's SQL from the column specs in reports_complete.md
    §2/§7 and confirm against the new schema — or accept spec-level parity for non-core reports.
    **→ AWAITING DATA** (report-column specs against production schema).
14. **OQ-14 — multi-branch necessity.** Are chain/multi-branch features (M07, chain-sync of
    M01/M05, FaryNet) in scope for v1? If single-branch only, `branch_id` still columns everywhere
    (schema_design §1.1) but chain UIs ship in P2.
    **→ RESOLVED 2026-08-16:** single-pharmacy first; `branch_id` everywhere, chain UIs Phase 2 (G09).
15. **OQ-15 — insurance module scope (M13).** Which insurance companies / contract model does the
    target deployment need? Determines whether copay/coverage engine is P2 or later.
    **→ RESOLVED 2026-08-16:** DEFERRED to Phase 2+ (X08); `pharmatag-insurance` plugin skeleton only.
16. **OQ-16 — web vs desktop feature parity.** Which features are web-only vs desktop-only vs both?
    E.g. is the POS sales screen desktop-only (offline), with web read-only dashboards?
    **→ RESOLVED 2026-08-16:** keyboard-first desktop web + offline desktop (P08); POS
    desktop-first, web dashboards read-only first.
17. **OQ-17 — printer/drawer SDKs.** Receipt/barcode printing + cash-drawer opening on Linux
    (Tauri) has no legacy equivalent; confirm target OS and printer SDKs (Zebra EPL/ZPL,
    XPrinter) for the offline desktop.
    **→ RESOLVED 2026-08-16:** desktop = ESC/POS thermal + drawer (Rust); web = PDF/80mm fallback
    (P09).

---

*End of feature plan. All citations in this plan assume the N+3 rule (ADJ-01). Field-level schema
decisions defer to `schema/schema_design.md` + `SCHEMA_RESOLVED.md`.*