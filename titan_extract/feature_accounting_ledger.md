# قيود الحسابات وشجرة الحسابات — Accounting Ledger & Chart of Accounts ("Hisabat Tree")

**Purpose:** Full extraction of the accounting-ledger / chart-of-accounts feature cluster of TITAN.W1 (Phye.exe). This covers the chart-of-accounts tree (شجرة الحسابات, FFFHisabatTree) and its editing screen (المحاسبة المحلية الرئيسية, FormAcclocalmain), the manual double-entry journal entry (قيد محاسبي, FormAccAddQueed), the money-detail and money-operations screens (تفاصيل المال FormMonyDetails / العمليات المالية FFFMony), the per-employee / per-agent ledger archive (أرشيف تقارير الموظفين, FormAmilReportsArchiv), the accounting report builder (تقارير المحاسبة, FormAccReports), and the accounting inventory / stock-accounting reconciliation (الجرد المحاسبي, FormGardMohasaby). Entries are stored per-branch in `wzaccfreetree` (account tree) and `farysales` (ledger lines with debit/credit), and the cluster plugs into the balance / trial-balance system already documented in `feature_balances.md` and the day-close in `feature_account_closing.md`.

Source: `titan_decompile/` (strings_utf16.txt, strings_readable.txt, pcode_disasm.txt), reused from `schema_complete.md` (§25 wzaccfreetree, §27 farysales), `feature_balances.md` (trial balance / RPT-F03/F04), `feature_account_closing.md` (FormMonyDetails, FFFMony, RPT-F01), `reports_complete.md` (RPT-F01/F03), `modules_gap_1.md` (§14 ModAccounting, §17 ModAccFreeOne), `business_logic_complete.md` (§10 ModMony), `ui_strings.json`.

---

## 1. Objects

### 1.1 Core modules / forms (from `pcode_strings.py names`, `ui_strings.json` `forms`)

| Object | Type | Procs | Role |
|---|---|---|---|
| **FFFHisabatTree** | Form | 18 | شجرة الحسابات — the chart-of-accounts tree (parent/child account hierarchy). pcode ~lines 596066–597620. |
| **FormAcclocalmain** | Form | 10 | المحاسبة المحلية الرئيسية — local accounting main / account-editing screen. pcode ~lines 592339–592997. |
| **FormAccAddQueed** | Form | 5 | إضافة قيد محاسبي — add a manual journal entry (debit/credit). pcode ~lines 591350–592339. |
| **FormAccReports** | Form | 4 | تقارير المحاسبة — accounting reports builder (RPT-F03 Account/Debit/Credit/Balance). pcode ~lines 592997–593457. |
| **FormMonyDetails** | Form | 7 | تفاصيل المال — daily cash-flow detail feeding balances (reports RPT-F01). pcode ~lines 407615–408240. |
| **FFFMony** | Form | 13 | العمليات المالية — financial operations / money-movement screen. pcode ~lines 89534–90507. |
| **FormAmilReportsArchiv** | Form | 6 | أرشيف تقارير الموظفين — agent/employee report archive + ledger export. pcode ~lines 683453–683900. |
| **FormGardMohasaby** | Form | 4 | الجرد المحاسبي — accounting inventory / ledger reconciliation vs drawer. pcode ~lines 203725–204072. |
| **FFFDrugrasidCorrect** | Form | 28 | تصحيح أرصدة الأدوية — drug-balance correction (covered in feature_invoice_editing.md / feature_stock_counting.md; noted here only). |
| **ModAccounting** | Module | 25 | Full double-entry accounting engine (chart of accounts, journal, trial balance) — modules_gap_1 §14, pcode ~lines 555471–556496. |
| **ModAccFreeOne** | Module | 19 | Account-free / branch-ledger engine writing `wzaccfreetree` + `\Files\Accounting\` — modules_gap_1 §17, pcode ~lines 593469–594258+. |
| **ModMony** | Module | 41 | Financial module — invoice tracking, cash movement, capital (business_logic_complete §10). |

Form titles verified in `ui_strings.json` `forms`: FFFHisabatTree=شجرة الحسابات (18 procs), FormAcclocalmain=المحاسبة المحلية الرئيسية (10), FormAccAddQueed=إضافة قيد محاسبي (5), FormAccReports=تقارير المحاسبة (4), FormGardMohasaby=الجرد المحاسبي (4), FormMonyDetails=نموذج FormMonyDetails (7), FFFMony=العمليات المالية (13), FormAmilReportsArchiv=أرشيف تقارير الموظفين (6), FFFDrugrasidCorrect=تصحيح أرصدة الأدوية (28). `menu_items` (9 root items) contains no accounting entries — the menu path is not derivable from ui_strings.json.

### 1.2 Key accounting data files (from strings_readable.txt / schema)

```
wzaccfreetree                      — chart of accounts (master/fary parent-child)   (schema_complete §25)
farysales                          — per-branch ledger lines (grand, father, son, creditdebit, typee) (§27)
\Files\Accounting\                 — accounting data directory
\Files\Accounting\moves\           — journal entries (moves)
\Files\Accounting\sales\           — sales accounting
\Files\DBI\acctree.phy             — account tree (chart of accounts)
\Files\DBI\acctree2.phy            — account tree (alt)
\Files\DBI\MonyInfo.phy            — money/balance info
```

---

## 2. Step-by-step workflow

From pcode + string evidence:

1. **Chart-of-accounts tree (FFFHisabatTree)** — the 18 procs build and render the account tree. Proc @0x009e9c8c (L596066) carries the binary grid key `\x01M…` (idx 48); proc @0x009caa78 (L596247) renders the day-summary div "قيمة كل ادوية الصيدلية بسعر الجمهور" (idx 3327, L596256/L596280); proc @0x009871c8 (L596414) is the "Start" entry (idx 6399) that loads the tree; proc @0x00a03f00 (L596516) prints the "رابعا" (fourth) accounting section header (idx 11519, L596534) and walks the tree per-account looping 500 nodes, pulling "اجمالي الشراء قبل الضريبة" (idx 8958, L596676); proc @0x009ae484 (L596713) reorders tree rows (selection 1/3 vs 4 branches); proc @0x009b1888 (L596826) iterates the tree array rows and emits the drawer-cash note "اي نقدية تخرج عن طريق الدرج خلال اليوم…" (idx 10494, L596942); proc @0x00a04ffc (L597229) loops 500 nodes, emits "ايجارات" (rent — idx 10495, L597308) and "اجمالي الشراء قبل الضريبة" (idx 8958, L597399) totals; proc @0x00948dcc (L597431) walks tree rows and advances a counter; proc @0x0095955c (L597168) loops 500 nodes comparing strings. The tree pairs with `wzaccfreetree(mobile, master, fary)` — accounts are parent (`master`) / child (`fary`) nodes (`insert into wzaccfreetree (mobile,master,fary) values (`, `if not exists( select * from wzaccfreetree where` — schema_complete §25).

2. **Day-summary report writer (FFFHisabatTree @0x009c39f8, L596956)** — writes one output row per day-summary bucket: iterates item-type buckets 0x0b–0x0f (today's drugs sold / stock buckets) then a series of fixed numeric column ids (0x044d, 0x044e, 0x0515, 0x0516, 0x01ae15–0x01ae18, 0xa80035/0xa80036, 0x01fc35, 0xc684b5, 0x02fd36, 0x05dd/0x05de/0x05df, 0x024a55, 0x04b1–0x04b3, 0x0579/0x057a) and emits them with the binary grid keys (idx 41–68, `\x01F…`–`\x01a…`). The div/XML placeholders used across the accounting cluster are idx 3319–3344 (`divsigil`, `divthisday`, `showData`, `<drg>`, `<drug-number>`, `<drug-stock>`, `<drug>`, `drugs-gomhour`, `drugs-stock-cost-novat`, `drugs-stock-cost-withvat`, `drugs-tbale`, `eftitahy-cash/customers/khosom-thabita/makhzon/mrd/net/osol-thabita`, `<encoding>must be utf-8…`, `<expire>`); per idx2refs2 these divs are used by FFFMony@0x009e1f28 (idx 3326, L89819), FormAccUploader (idx 3327, L590710/L590743) and FormUsersMony (idx 3327, L641509) — while FFFHisabatTree uses idx 3327 only at L596256/L596280. The ZATCA XML fragments `"street":`/`"taxableItems":`/`"total":`/`"totalSale":`/`"unitPrice":`/`"unitType":`/`"valueDifference":`/`]` (idx 255–262) are referenced by ModAccFreeOne (L593644/L593669/L593911/L593936/L594258), not by FFFHisabatTree.

3. **Local accounting screen (FormAcclocalmain)** — 10 procs. Load (L592339, L592353), date handling, the "Start" entry (idx 6399, L592533/L592544), grid rendering (L592365, L592509, L592568, L592585), and the master-account SQL filter `'  and master =N'` (idx 1279, L592432/L592482) used to query child accounts under a master. Proc @0x009eb550 (L592592) reads the commercial-registration token "CoReg" (idx 4351, L592646). Proc @0x00a0baa8 (L592768) reads a numeric field, converts it to string, formats it into a grid column, and if < 1 sets a default (loop over 0x1388=5000 rows).

4. **Add journal entry (FormAccAddQueed)** — 5 procs. Proc @0x008e5958 (L591350) is the entry-creation loop; proc @0x00a595e4 (L591362, size=1012) creates the entry record, using the sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (idx 7423, L591699/L591732) as an identifier; proc @0x009aadc8 (L591693) builds an entry record — reads fields via procs 0x10/0x08, formats a date (FnCDateVar), writes it back to a date field, then builds a report frame (13 `LitVar_Missing` + 4 string args) dispatched through proc 0x16; proc @0x00a64320 (L591784, size=1072) references the governorate/branch list (idx 9471 "اسيوط:البداري", L591803/L591841/L591854/L591889/L591902) and, when a branch-count check (< 5) succeeds, builds a default entry with the binary grid keys idx 8/40/56 (`\x01%\xecP`, `\x01E\xecP`, `\x01U\xecP`); proc @0x00a24f08 (L592111) finishes the entry. Manual entries require a description first — "ادخل وصف القيد اولا" (idx 8637, per feature_balances §2.3).

5. **Money details / operations (FormMonyDetails, FFFMony)** — FormMonyDetails (7 procs, no pool strings — pure numeric) reads a money record, converts amounts to strings into grid cells (@0x00914794 L407615; @0x008fedcc L407651; @0x00aa78d4 L407673 builds cash-flow rows; @0x008ec980/@0x008ec9d4 are no-op/guard stubs; @0x00936fd8 L408201 prints via the 4 report calls 0x50/0x64/0x68/0x60). FFFMony (13 procs) is the financial-operations screen: grid setup @0x009e1f28 (L89692) sets column widths 100/1700/1000/2500/5000; proc @0x009dfbc4 (L89843) checks seller validity and, on "Invalid seller information." (idx 5375, L89873/L89898), builds an error via proc 0x10; proc @0x009b7bf8 (L90016) shifts array rows (MemLdFPR8/MemStFPR8 0x14, MemLdStr/MemStStrCopy 0x10); date range @0x008e9e04 (L89676) uses "2021-01-31" (idx 2558, L89783) and "58" (idx 2814, L89795); proc @0x009a8d24 (L90507) appends the day's money rows to the grid (idx 3326 div, idx 3070 `</local-file-path>`). This is the daily money-movement screen feeding RPT-F01 (feature_account_closing §1.1).

6. **Agent/employee ledger archive (FormAmilReportsArchiv)** — 6 procs. Proc @0x008da82c/@0x008e7020 are guards; proc @0x0098e804 (L683472) is the archive load loop (135 items, MemLdI2) with the day-summary div (idx 3327, L683513/L683518/L683533/L683554); proc @0x0094bc90 (L683563) loops an array and concatenates strings; proc @0x009808b8 (L683614) is the report-builder proc — it loads the archive with ~11 `LitVar_Missing` args and 6 string args, then calls proc 0x16 with the report frame, using the sales GUID (idx 7423, L683624/L683661), "Cloud storage of stock" (idx 4350, L683646), "DeviceName" (idx 4606, L683649); proc @0x00a8d378 (L683675) prints the archive including "ايجارات" (idx 10495, L683765/L683922).

7. **Accounting reports (FormAccReports)** — 4 procs. Proc @0x009927bc (L592997) is the report-run proc (calls 0x01–0x02 to load, builds a report frame with 11 `LitVar_Missing` + 5 string args, calls proc 0x0b); it uses the *Samsung* printer token (idx 1790, L593044/L593106) and the "1-5-2020" date seed (idx 2303, L593053); proc @0x00a85bc0 (L593070, size=1184) is the report-grid renderer — builds the account/debit/credit/balance table, prints "رابعا" (idx 11519, L593072/L593083/L593118/L593191/L593411), loops 5000 rows (LitVarI4 0x1388), and passes the sales GUID (idx 7423) into the report; proc @0x00926b44 (L593419) validates args and calls the report with string concatenation; proc @0x008e6b58 (L593457) is a 20-byte no-op stub. This is RPT-F03 (Account/Debit/Credit/Balance) per reports_complete §RPT-F03 and feature_balances §1.1.

8. **Accounting inventory (FormGardMohasaby)** — 4 procs, all pure-numeric (only the binary grid key idx 48). Proc @0x008fdac8 (L203725) writes 0 to a value slot; if the count equals 27 (0x1b) it flags a row. Proc @0x00a46f28 (L203754) is the main reconciliation: calls procs 0x44 and 0x40, exits if either returns 0, otherwise compares FPR8 (LtR8) sums, walks the ledger array comparing MemLdFPR4 field 0x78==0 and MemLdStr field 0x3c==0 to find unaccounted rows, accumulates rows in range into sums (loop up to 0x0fd0=4048), computes a net figure `c - (a+b) - d` and a percentage `c / 30 * 100` (DivR8 0x1e * MulR8), and writes results through report calls 0x30/0x28/0x20/0x18/0x10/0xfc/0x04. This is the ledger-vs-drawer reconciliation screen (الجرد المحاسبي).

---

## 3. Fields / data captured

### 3.1 wzaccfreetree — chart of accounts (schema_complete §25, lines 615–631)
```
id      INT PK
mobile  NVARCHAR(15)      — branch id
master  NVARCHAR(100)     — parent account (مصنف رئيسي)
fary    NVARCHAR(100)     — child account (صنف فرعي)
SQL: insert into wzaccfreetree (mobile,master,fary) values ( ...
SQL: if not exists( select * from wzaccfreetree where ...
```

### 3.2 farysales — per-branch ledger lines (schema_complete §27, lines 655–690)
```
id, mobile, grand REAL, father NVARCHAR(100), son NVARCHAR(100),
datee REAL, datetimee, dateemanual REAL, monthe, yearo, payed REAL,
creditdebit NVARCHAR(20), typee NVARCHAR(50), phar, randomid, tips, writer, classy
SQL: (mobile,grand,father,son,datee,datetimee,dateemanual,monthe,yearo,payed,creditdebit,typee,phar,randomid,tips,writer,classy)values(
SQL: select datee, Pa=sum(payed) from ...
```
The `father`/`son` columns mirror `wzaccfreetree.master/fary`; `creditdebit` is the مدين/دائن side and `grand` the amount.

### 3.3 Accounting report columns (FormAccReports, RPT-F03)
```
Account, Debit, Credit, Balance, Period        (RPT-F03)
Entry Date, Account, Debit, Credit, Description, Status   (RPT-F11 upload)
رابعا (idx 11519) section header, 1-5-2020 date seed (idx 2303), *Samsung* printer token (idx 1790)
```

### 3.4 Day-summary HTML placeholders (idx 3319–3344, shared with day-close)
```
divsigil/divthisday/showData divs, <drg>/<drug-number>/<drug-stock>/<drug>,
drugs-gomhour, drugs-stock-cost-novat, drugs-stock-cost-withvat, drugs-tbale,
eftitahy-cash / -customers / -khosom-thabita / -makhzon / -mrd / -net / -osol-thabita
<encoding>must be utf-8 not optional<encoding>, <expire>
```

### 3.5 Chart labels (strings_utf16.txt, near the account tree)
```
اجمالي الربح في المبيعات (8955), اجمالي الشراء (8957), اجمالي الشراء قبل الضريبة (8958),
اجمالي الصافي (8959), اجمالي الضريبة (8961), اجمالي الفاتورة (8962),
اجمالي المبيعات (8964), اجمالي المصروفات (8967), اجمالي النقدية (8972)
ايجارات (10495), ايرادات (10496), ايرادات.ايرادات اخري (10497), ايرادات.مبيعات (10498),
ب.الضريبه (10502) — chart-of-accounts sub-accounts
اي نقدية تخرج عن طريق الدرج خلال اليوم فيفضل تسجيلها خارجيا او ترحيل قيمتها فورا من الخزينة الي الدرج (10494)
رابعا (11519), رأس المال (11520)
```

### 3.6 Governorate / branch list (idx 9470–9476, used by FormAccAddQueed)
```
اسيوط-سوهاج-البحر-قنا-الاقصر-اسوان-الوادي-... (9470)
اسيوط:البداري (9471), اسيوط:ابوتيج (9472), اسيوط:اسيوط (9473) ... (اسوان، الوادي)
```
Entries are per-branch; the journal-entry screen validates the selected governorate before posting.

---

## 4. Side-effects

- **Chart of accounts:** `wzaccfreetree` grows/updates via ModAccounting (procs 5–10 create/update/delete) and FormAcclocalmain's `master =N'` queries; mirrored to `acctree.phy`/`acctree2.phy` (feature_balances §1.2).
- **Ledger lines:** journal entries write `farysales` (per branch) and `\Files\Accounting\moves\`; the sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (idx 7423) appears in the entry, archive, and report procs of this cluster as the shared business identifier.
- **Balances:** the ledger feeds the trial balance / balance sheet (feature_balances §2.4–2.6); balances are fed automatically from sales & purchases ("تتغير ارصدة الشركات والعملاء تلقائيا…" idx 10054).
- **Day close:** FormMonyDetails/FFFMony are the daily cash-flow screens consumed by the day-close (feature_account_closing §1.1) and by RPT-F01 (reports_complete §RPT-F01).
- **Staff ledger:** FormAmilReportsArchiv exports the agent ledger to archive reports (idx 3327 div, idx 4350 cloud storage, idx 4606 device name).
- **VAT:** ب.الضريبه (idx 10502) and the VAT eftitahy placeholders (idx 3336–3342) tie the ledger to VAT accounts (feature_balances §5).

---

## 5. Pricing + VAT

- Accounting quantities (modicsums) are computed from the ledger sums, not from prices. Totals like "اجمالي الشراء قبل الضريبة" (idx 8958) are pre-VAT purchase totals; "اجمالي الضريبة" (idx 8961) is the VAT amount; ب.الضريبه (idx 10502) is the VAT sub-account in the chart.
- The ZATCA e-invoice XML fragments (`"street":`, `"taxableItems":`, `"total":`, `"totalSale":`, `"unitPrice":`, `"unitType":`, `"valueDifference":`, `]` — idx 255–262) are built by ModAccFreeOne (L593644/L593669/L593911/L593936/L594258) for the ledger/summary export, not by FFFHisabatTree.

---

## 6. Gaps & open questions

- **String-pool line ambiguity:** pcode string-index values are exact (verified via `pcode_strings.py`); raw strings_utf16.txt line = idx + 3 (e.g. idx 3327 = line 3330). Cite decoded text by idx.
- **Small LitVarStr indices** seen in pcode (0x0e, 0x0f, 0x11, 0x12–0x17, 0x1a, 0x28, 0x29…) are local `\x01`-prefixed binary literals (grid keys/formats) not in the decoded pool; they are filtered from search output.
- **ModAccFreeOne relationship:** the task pointer to business_logic_complete.md for ModAccounting/ModAccFreeOne is wrong; both are in `modules_gap_1.md` §14 (:399) and §17 (:495). ModAccFreeOne pcode 593469–594258+ uses idx 9471 (branch), idx 255 (`"street":` ZATCA), idx 4351 (CoReg) — overlaps this cluster.
- **FormAccReports proc 4** (@0x008e6b58, 20 bytes) and **FormMonyDetails stubs** (@0x008d860c) are empty/no-op — likely unused dispatchers.
- **Unread tails (optional):** FormGardMohasaby @0x00906e40/@0x00906ec4; FormAmilReportsArchiv @0x009808b8/@0x00a8d378 tails; FFFMony procs 90163–90507; full FFFDrugrasidCorrect 28-proc set (covered in feature_invoice_editing.md:5,18,111,141 and feature_stock_counting.md:19,42).
- **Menu path:** `ui_strings.json` `menu_items` has only 9 roots with no accounting entries; the forms' menu placement is not derivable from ui_strings.json.
- **Governorate list** (idx 9470–9476) is truncated at the 6 decoded entries; the full list (اسوان، الوادي، …) is not enumerated here.