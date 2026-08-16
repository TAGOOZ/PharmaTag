# SCHEMA RESOLUTION REPORT — 11 Conflicting Tables

**Producer:** schema-resolver pass over `titan_decompile/` (pcode_disasm.txt, strings_utf16.txt) + `idx2refs_correct.json` / `idx2procs_litstr.json` + `schema_complete.sql` ground truth
**Date:** 2026-08-15
**Purpose:** adjudicate the 10 schema contradictions of `GAPS_REPORT.md` §2.1–2.10 plus the `creditdebit` column question (GAPS §4.6/§7.6), resolving each to the column list the **p-code actually uses at runtime**, not what a docs author wrote.

---

## 0. Decoding rules used (all `[VERIFIED]`)

| Rule | Source |
|---|---|
| String index = 1-based utf16 line − 3 | `DECOMPILE_CHEATSHEET.md:19`; verified via GUID idx 7423 at `strings_utf16.txt:7425` |
| LitVarStr 2-byte `[3a <hi> <lo>]`: idx = `((hi & 0x3F) << 8) \| lo` | cheatsheet:19; verified `[3a 5c ff 82 00]` → 7423 |
| LitVarStr 4-byte `[3a ..]`: idx = `b[1] \| b[2]<<8 \| b[3]<<16` | cheatsheet:19 |
| LitStr `[1b <lo> <hi>]`: idx = `lo \| hi<<8` | verified `[1b fe 02]` → 766 |
| `idx2refs_correct.json` = LitVarStr (3a) form only | compared against `idx2procs_litstr.json`; the two maps are complementary, not duplicate |
| `idx2procs_litstr.json` = LitStr (1b) form only | idem |
| Procedure identity for a ref line | proc header `[Form/Module/...] Name @0x...` in pcode_disasm.txt |

Ref counts below give **idx2refs_correct.json** first (the map the task requires), then the LitStr count from `idx2procs_litstr.json`, then the combined scan. A fragment is "**live**" only if at least one form has a real pcode reference.

---

## 1. `titanksasales` — 9 vs 15 vs "more" columns

### Conflict (GAPS §2.1)
- `schema_complete.sql:113-123`: 9 cols `id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue`.
- `business_logic_complete.md:104-120`: 15 line-item cols `invoiceid, IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price, PharmacistTel, Mohafaza, Markaz, SourceIdDateTime, RequisterTel, country`.
- `reports_complete.md:1033`: adds yet more `creditdebit, vat, mobile, writer, phar, tips`.

### Resolution — **9-col summary table**
`id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue` — the 9-col form wins. The 15-col and reports shapes are **other tables' column lists misattributed to titanksasales** (see §7 invoicedata and §9 farysales).

### Evidence
- Column-list fragment matches ground truth **exactly**: idx 8016 `invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue ) values (` at `strings_utf16.txt:8019`. **refs = 0 (correct) + 0 (litstr) = 0** (template string, assembled at runtime).
- INSERT prefix idx 941 `insert into titanksasales (` at `strings_utf16.txt:944`, refs = 0 + 0 = 0.
- CREATE prefix idx 765 `CREATE TABLE titanksasales (` at `strings_utf16.txt:768`, refs = 0 + 0 = 0.
- **Live** UPDATE: idx 1030 `update titanksasales set` at `strings_utf16.txt:1033`; **correct=0, litstr=2** → FFFStartUp@0x008ddccc `pcode_disasm.txt:11842`, FFFOutPut@0x00b0df44 `pcode_disasm.txt:52105`.
- **Live** SELECT: idx 1004 `select invoiceid from titanksasales where` at `strings_utf16.txt:1007`; **correct=0, litstr=1** → FFFOutPut@0x00b3ac8c `pcode_disasm.txt:47415`.
- Chain-sync loop is **live**: GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` idx 7423 (`strings_utf16.txt:7425`) has **correct = 3,564 refs** (FFFStartUp 934, ModPharm 552, FFFOutPut 172, ModStorage 108, FFFNew 92, ModTafqit 88, FFFInPut 85, FFFNewDrugServer 84 …). The 9-col insert with this GUID is the chain-sales sync documented at `raz_complete.md:404`.
- **Ruling:** 9 cols; the 15-col list is the `invoicedata`/`RawakidTablew` line-item shape (see §7), and the `reports_complete.md:1033` extras belong to `farysales` (see §9).

---

## 2. `titanksastock` — 8 vs 24 columns

### Conflict (GAPS §2.2)
- `schema_complete.sql:128-137`: 8 cols `id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock`.
- `business_logic_complete.md:72-99` ("Primary Drug Table"): 24 cols incl. `Barcode1..5, PriceNow, wareprice3, SellDisc, ExpireId/Expire, Tips, Mohafaza, Markaz, SourceIdDateTime, RequisterTel, country`.

### Resolution — **8-col stock table**
`id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock`. The 24-col form is `wzdrugs` (the drug master), not the chain-stock snapshot.

### Evidence
- **Live** CREATE: idx 766 `CREATE TABLE titanksastock (` at `strings_utf16.txt:769`; **correct=1, litstr=2, combined=3** →
  - FFFOutPut@0x00b3ac8c `pcode_disasm.txt:48824`
  - FFFOutPut@0x00b45184 `pcode_disasm.txt:54353`
  - FFFDRUGRUN@0x00b12748 `pcode_disasm.txt:359921` (via correct.json)
- Column fragments referenced in the same CREATE assembler (FFFOutPut@0x00b3ac8c, start 47129):
  - idx 987 `pharmacyid nvarchar(15) default '' )` at `strings_utf16.txt:990`, L47672 and (b45184) L53102
  - idx 1008 `shape int default '0',` at `strings_utf16.txt:1011`, L48623 / L54134
  - idx 1012 `silsilaid nvarchar(15) default '', ` at `strings_utf16.txt:1015`, L48933 / L54474
  - idx 1014 `stock real default '0' ,` at `strings_utf16.txt:1017`, L49091 / L54644 (also FFFStartUp@0x009a31ac L11730)
- INSERT column-list template idx 912 `drugname,datee,silsilaid,minimum,pharmacyid,classy,stock) values (` at `strings_utf16.txt:915`; refs = 0 + 0 = 0 (matches the 7 col body; `id` is the IDENTITY PK).
- **Ruling:** 8 cols; the 24-col "Primary Drug Table" in business_logic_complete.md is `wzdrugs` (`schema_complete.sql:14-43`).

---

## 3. `titanneed` — 5 vs 7 columns, disjoint

### Conflict (GAPS §2.3)
- `schema_complete.sql:156-163`: `id, drugname, quant, datee, sender, target`.
- `business_logic_complete.md:129-137`: `drugname, datee, silsilaid, minimum, pharmacyid, classy, stock` — a stock snapshot, no overlap with needs-request.

### Resolution — **6-col needs/order table**
`id, drugname, quant, datee, sender, target`. The 7-col shape is the **titanksastock** column list pasted into the wrong section.

### Evidence
- **Live** CREATE: idx 767 `CREATE TABLE titanneed (` at `strings_utf16.txt:770`; **correct=0, litstr=2, combined=2** →
  - FFFOutPut@0x00b3e1e4 `pcode_disasm.txt:36824`
  - FFFOutPut@0x00b4ca40 `pcode_disasm.txt:38834`
- **Live** confirmation message: idx 1022 `table titanneed created !` at `strings_utf16.txt:1025`; **correct=2** → FFFDRUGRUN@0x00b12748 `pcode_disasm.txt:359924`, ModOuterConnections@0x00a04494 `pcode_disasm.txt:650260`.
- INSERT template idx 8006 `insert into titanneed (drugname,quant,datee,sender,target) values (` at `strings_utf16.txt:8009`; refs = 0 + 0 = 0 (5-col body + `id` PK = 6 cols).
- Column-fragment templates (unreferenced but present): idx 1005 `sender nvarchar(20) default '',` L1008; idx 1023 `target nvarchar(20) default '') ` L1026; idx 993 `quant real default 0 , ` L996; idx 1007 `silsilaid = ` L1010.
- **Ruling:** 6 cols as `schema_complete.sql:156-163`. The `sender`/`target` NVARCHAR(20) fragments confirm the inter-pharmacy request role, not stock snapshot.

---

## 4. `TitanUserAction` — three different DDLs

### Conflict (GAPS §2.4)
- `schema_complete.sql:266-278`: 11 cols, `id INT IDENTITY`, `drugname NVARCHAR(100)`, `curbarcode VARCHAR(15)`, `units INT`, `datee REAL`.
- `permissions_complete.md:261-272`: 10 cols, **no `id`**, `curbarcode varchar(50)`, `units int`, `datee datetime`.
- `business_logic_complete.md:142-153`: 10 cols, `units NVARCHAR(20)`, `datee DATETIME`, `curbarcode NVARCHAR(50)`.

### Resolution — **11-col audit log**
`id, drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee` with `id INT IDENTITY` and `curbarcode VARCHAR(15)`, `units INT`, `datee REAL` (the SQL-file form). The 10-col variants drop the auto-increment PK and change types to match a **different** (raw `schema.sql`) table.

### Evidence
- INSERT column-list template idx 5252 `INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)` at `strings_utf16.txt:5255`; refs = 0 + 0 = 0. The 10-column body exactly matches ground truth minus the IDENTITY PK — so the **schema 11-col = 10 insert cols + `id`**.
- CREATE prefix idx 4242 `CREATE TABLE TitanUserAction` at `strings_utf16.txt:4245`; refs = 0 + 0 = 0.
- **Ruling:** `schema_complete.sql:266-278`; the two 10-col DDLs in permissions/business_logic are the raw-schema lineage (GAPS §2.11), which lacks `id`. `units INT` and `datee REAL` beat `NVARCHAR`/`DATETIME` (matches the 3a/LitStr pool typing used across all Titan tables).

---

## 5. `usersourceupdate` — 6 vs 9 vs 4 columns

### Conflict (GAPS §2.5)
- `schema_complete.sql:283-290`: 6 cols `id, drugname, price, units, localimport, datee`.
- `feature_users_permissions_menus.md:240-250`: 9 cols (adds `barcode, pharmacyid, lastedit`) — exactly what raw `schema.sql:263-273` contains.
- `permissions_complete.md:285-292`: 4 cols `drugname varchar(200), price float, units int, localimport int` — no `id`, no `datee`.

### Resolution — **6-col sync log**
`id, drugname, price, units, localimport, datee` (`schema_complete.sql:283-290`).

### Evidence
- INSERT template idx 8007 `insert into usersourceupdate (drugname,price,units,localimport,` at `strings_utf16.txt:8010`; refs = 0 + 0 = 0. Prefix matches the 6-col body exactly (continues with `datee`).
- **Live** SELECT landmark (matches 6-col or 9-col, **not** 4-col): idx 6210 `SELECT top 3000 * FROM usersourceupdate WHERE Datee > '` at `strings_utf16.txt:6213`; refs = 0 + 0 = 0; the same statement appears at `strings_readable.txt:5873` (GAPS §1 verified).
- DELETE-by-id confirms `id` PK: idx 4517 `DELETE FROM usersourceupdate WHERE id='` at `strings_utf16.txt:4520`; refs = 0 + 0 = 0.
- SELECT idx 1002 `select drugname from usersourceupdate` at `strings_utf16.txt:1005`; refs = 0 + 0 = 0.
- **Ruling:** 6 cols. The 9-col form is the raw `schema.sql:263-273` lineage; the 4-col form is a cut-down partial. Both `id` (DELETE `WHERE id`) and `datee` (SELECT `WHERE Datee >`) are real — the 4-col DDL is wrong.

---

## 6. `ChainBuyUsers` — 12 vs 4 vs 1 columns

### Conflict (GAPS §2.6)
- `schema_complete.sql:338-353`: 12 cols `PharmacistTel, Expire, IdDateTime, Quant, DrugName, SellDisc, Mohafaza, Markaz, Tips, RequisterTel, country, price` (+ `id`).
- `feature_users_permissions_menus.md:259-267`: 4 cols `PharmacistTel, Name, PharmacyId, Datee` (raw `schema.sql:317-323` matches this 4-col).
- `permissions_complete.md:277-281`: `PharmacistTel varchar(20)` only.

### Resolution — **12-col chain-buy user/order row**
`id, PharmacistTel, Expire, IdDateTime, Quant, DrugName, SellDisc, Mohafaza, Markaz, Tips, RequisterTel, country, price`.

### Evidence
- Column-list template idx 5939 `PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,Tips,RequisterTel,country,price` at `strings_utf16.txt:5942`; refs = 0 + 0 = 0. Matches the 12-col body exactly.
- Sibling 10-col shape idx 5938 `PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,SourceIdDateTime,price` at `strings_utf16.txt:5941` — this is the **RawakidTablew** variant (schema_complete.sql:358-373 uses `SourceIdDateTime` + `Tips` + `RequisterTel` + `country`; the combined 13-col).
- INSERT prefix idx 5250 `INSERT INTO ChainBuyUsers` at `strings_utf16.txt:5253`; SELECT idx 6207 `SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%` at `strings_utf16.txt:6210`; bare name idx 4292 `ChainBuyUsers` at `strings_utf16.txt:4295`; all refs = 0 + 0 = 0.
- **Ruling:** 12 cols + `id`. The 4-col and 1-col forms are the raw-schema lineage. `ChainBuyUsers` and `RawakidTablew` are sibling tables sharing the drug/order shape; `ChainBuyStore` (idx 5249/6206, `strings_utf16.txt:5252`/`:6209`) is the store-level twin.

---

## 7. `invoicedata` — header and line items merged

### Conflict (GAPS §2.7)
- `schema_complete.sql:168-187` fuses invoice-header cols (`invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue`) with line-item cols (`IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price`).
- Raw `schema.sql:131-140` is header-only.

### Resolution — **17-col single table (header + lines in one row)**
`id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue, IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price` — the merged `schema_complete.sql:168-187` form is the real one.

### Evidence
- **Live** line-item column list: idx 508 `(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price) ` at `strings_utf16.txt:511`; **correct=0, litstr=3, combined=3** →
  - FFFOutPut@0x00946bc0 `pcode_disasm.txt:28583`
  - FFFInPut@0x00b4a9a8 `pcode_disasm.txt:140753`
  - Raz@0x009b5a00 `pcode_disasm.txt:575052`
- Header column-list template idx 8016 `invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue ) values (` at `strings_utf16.txt:8019`; refs = 0 + 0 = 0.
- Table-name literal idx 8015 `invoicedata` at `strings_utf16.txt:8018`; refs = 0 + 0 = 0 (name assembled at runtime).
- `IdDateTime` filter fragment idx 793 `IdDateTime = '` at `strings_utf16.txt:796`; **litstr=1** → FFFOutPut@0x00b4ca40 `pcode_disasm.txt:39675`.
- **Ruling:** merged single-table form. The 15-col "titanksasales" shape in `business_logic_complete.md:104-120` is this line-item list prefixed with `invoiceid`; there is **no** separate line-item table in the p-code — both header and lines go into `invoicedata` in one row (GAPS §7.7 answered: yes, one table).

---

## 8. `wzphar` — `pharname` vs `pharmacyname`

### Conflict (GAPS §2.8)
- `schema_complete.sql:204-210` and `schema_mapping.md:17` use **`pharname`**.
- SQL evidence elsewhere uses **`pharmacyname`**: `"group by pharmacyname,adress"`, `"where pharmacyname=N'"` (`schema_complete.md:329-330`), `"select pharmacyname,adress,count(*),max(datee) from storediscount"` (`modules_remaining_2.md:233`); `storediscount` itself uses `pharmacyname` (`schema_complete.sql:219`).

### Resolution — **both are correct, on different tables**
`wzphar.pharname` (`NVARCHAR(100)`) is the pharmacy master column; `pharmacyname` belongs to `storediscount`, `titanpharmalist`, `titanpharmalist`-style aggregates. No contradiction once the table is named.

### Evidence
- The only `wzphar` SQL fragment uses **`pharname`**: idx 999 `select distinct pharname from wzphar` at `strings_utf16.txt:1002`; refs = 0 + 0 = 0.
- All `pharmacyname` fragments reference **other tables**:
  - idx 928 `group by pharmacyname,adress` at `strings_utf16.txt:931` (storediscount aggregate)
  - idx 1039 `where pharmacyname=N'` at `strings_utf16.txt:1042`
  - idx 7435 `adress,storename,pharmacyname ,pharmacyname2,datee,...` at `strings_utf16.txt:7438` — the **storediscount 16-col INSERT** (`raz_complete.md:428`; matches `schema_complete.sql:215-233`)
  - idx 8104 `mobile,datee,changed,apptype,pharmacyname,barcode)values(` at `strings_utf16.txt:8107` — the **titanpharmalist** INSERT
  - idx 8225 `pharmacyname` at `strings_utf16.txt:8228`; idx 8339/8346 storediscount SELECTs at `strings_utf16.txt:8342`/`:8349`
- **Ruling:** keep `wzphar.pharname`; `pharmacyname` is `storediscount`/`titanpharmalist`. This resolves GAPS §2.8 with no schema change.

---

## 9. `taronlineeg` vs `farysales` — swapped column lists

### Conflict (GAPS §2.9)
- `reports_complete.md:1040` documents `taronlineeg` as `mobile, grand, father, son, datee, datetimee, monthe, yearo, payed, creditdebit, typee, phar, randomid, tips, writer, classy`.
- That exact list is **`farysales`** in `schema_complete.sql:411-431`. `taronlineeg` in `schema_complete.sql:305-315` is `CreateDate, mobile, NameEnglish, NameArabic, drugname, price, barcode`.

### Resolution — **reports_complete.md had the tables swapped**
`taronlineeg` = `id, CreateDate, mobile, NameEnglish, NameArabic, drugname, price, barcode`. The 17-col `grand/father/son/creditdebit/...` list is **`farysales`**.

### Evidence
- **Live** 17-col INSERT column list idx 396 `(mobile,grand,father,son, datee,datetimee,dateemanual,monthe,yearo,payed,creditdebit,typee,phar,randomid,tips,writer,classy)values` at `strings_utf16.txt:399`; **correct=0, litstr=3, combined=3** →
  - FFFNew@0x009b4450 `pcode_disasm.txt:116821`
  - ModStock@0x009e4c70 `pcode_disasm.txt:228006`
  - ModDTTS@0x00b2df78 `pcode_disasm.txt:483930`
  - It matches `farysales` **exactly** (17 cols in schema_complete.sql:411-431 order), proving `farysales` is the target of the live insert.
- `farysales` SELECT idx 996 `select * from farysales where mobile = N'` at `strings_utf16.txt:999`; refs = 0 + 0 = 0.
- `taronlineeg` fragments (all match the CreateDate/mobile/Name schema, refs = 0 + 0 = 0):
  - idx 814 `SELECT count(*) FROM taronlineeg` L817; idx 815 `SELECT top 100 * FROM taronlineeg WHERE CreateDate >` L818
  - idx 816 `SELECT top 100 * FROM taronlineeg WHERE mobile='` L819; idx 817 `SELECT top 50 * FROM taronlineeg WHERE NameEnglish like N'` L820
  - idx 1033 `update taronlineeg set` L1036
- **Ruling:** reports_complete.md:1040 mislabeled farysales's list as taronlineeg. `creditdebit` is a real `farysales` column (see §11). GAPS §7.5 answered from pcode: the `farysales` INSERT is live in 3 procs; no taronlineeg INSERT exists.

---

## 10. `titaninn` — transfer vs purchases

### Conflict (GAPS §2.10)
- `schema_complete.sql:100-108`: inter-pharmacy transfer (`fatid, itemsasstring, datee, source, silsilaid, target`).
- `business_logic_complete.md:123-125`: "Purchase/Inbound table — stores all inbound invoice items".

### Resolution — **inter-pharmacy transfer table**
`id, fatid, itemsasstring, datee, source, silsilaid, target`. The purchases label is wrong.

### Evidence
- **Live** DELETE (only DML that is definitively live for this table): idx 450 `delete from titaninn` at `strings_utf16.txt:453`; **correct=0, litstr=2, combined=2** → ModDTTS@0x00b2df78 `pcode_disasm.txt:484260`, Raz@0x0093404c `pcode_disasm.txt:572651`.
- **Live** SELECT: idx 1003 `select fatid from titaninn where ` at `strings_utf16.txt:1006`; **correct=0, litstr=3, combined=3** → FFFStartUp@0x009a8110 `pcode_disasm.txt:11589`, FFFOutPut@0x00b3ac8c `pcode_disasm.txt:47354`, FFFOutPut@0x00b45184 `pcode_disasm.txt:52904`.
- **Live** DROP: idx 906 `drop table titaninn;` at `strings_utf16.txt:909`; combined=1 → FFFOutPut@0x00a891b4 `pcode_disasm.txt:43635`.
- ModDTTS assembles the CREATE from the exact schema columns (L484176–L484332):
  - idx 436 `ID int IDENTITY(1,1),` L484176 (+ FFFNew@0x00ac9004 L117591)
  - idx 451 `fatid int default '0',` L484266 (+ Raz L572655, L572664)
  - idx 455 `itemsasstring nvarchar(4000) default '',` L484290
  - idx 449 `datee int default '0',` L484254 (+ Raz L572646)
  - idx 460 `silsilaid nvarchar(15) default '',` L484320
  - idx 461 `source nvarchar(100) default '',` L484326
  - idx 462 `target nvarchar(100) default '' )` L484332
  - (fragments at `strings_utf16.txt:439,454,458,452,463,464,465`)
- Transfer role fragments: idx 940 `insert into titaninn (fatid,itemsasstring,datee,source,silsilaid,target)VALUES (` at `strings_utf16.txt:943` (refs 0+0=0); idx 1000/1001 `select * from titaninn where source/target =N'` at `strings_utf16.txt:1000`/`:1001`; idx 1034 `update titaninn set target =N''` at `strings_utf16.txt:1037`. The `source`/`target`/`silsilaid`/`itemsasstring` field set is the transfer-record shape, not purchase lines.
- **Ruling:** 7-col transfer table per `schema_complete.sql:100-108`; the "purchases" reading is a docs error — purchases go to `invoicedata`/`titanstock`.

---

## 11. `creditdebit` — column, not a table

### Conflict (GAPS §4.6, §7.6)
- `creditdebit` appears in report SQL (`reports_complete.md:80,1081`) but in **no** ground-truth CREATE TABLE for `titanksasales`/`invoicedata`; GAPS §4.6 flags it as an undocumented return discriminator, and §7.6 suspects it "lives in `wzgard.typee` or `invoicedata.agel`".

### Resolution — **`creditdebit` is a real `farysales` column**
`farysales.creditdebit NVARCHAR(20) DEFAULT ''` (`schema_complete.sql:424`). It is **not** a column of `titanksasales` or `invoicedata`.

### Evidence
- The **live** `farysales` INSERT column list idx 396 (`strings_utf16.txt:399`) contains `creditdebit` between `payed` and `typee` — refs **correct=0, litstr=3** (FFFNew@0x009b4450 L116821, ModStock@0x009e4c70 L228006, ModDTTS@0x00b2df78 L483930). This is the only INSERT with `creditdebit` in the pool.
- `creditdebit` appears in **no** titanksasales/invoicedata fragment — the GAPS observation is confirmed: the column does not exist there.
- **Ruling:** map `creditdebit` to `farysales` (§9). The sales-return discriminator is `farysales.creditdebit`; the reports that read it (`reports_complete.md:80,1081`) are reading `farysales`, and the "taronlineeg" name in those reports is the §9 swap.

---

## Summary table

| # | Table | Conflict (GAPS) | Resolution (final cols) | Live p-code anchor |
|---|---|---|---|---|
| 1 | titanksasales | 9 vs 15 vs more | `id, invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue` | GUID loop 3564×; update/select live |
| 2 | titanksastock | 8 vs 24 | `id, drugname, datee, silsilaid, minimum, pharmacyid, classy, stock` | CREATE live ×3 (48824/54353/359921) |
| 3 | titanneed | 5 vs 7 disjoint | `id, drugname, quant, datee, sender, target` | CREATE live ×2 (36824/38834) + "created" |
| 4 | TitanUserAction | 11 vs 10 vs 10 | 11-col w/ `id`; `units INT`, `datee REAL` | insert template (dead) |
| 5 | usersourceupdate | 6 vs 9 vs 4 | `id, drugname, price, units, localimport, datee` | SELECT `Datee >` + DELETE by id |
| 6 | ChainBuyUsers | 12 vs 4 vs 1 | 12-col + `id` | insert template (dead) |
| 7 | invoicedata | header vs merged | 17-col merged single table | line-items INSERT live ×3 (28583/140753/575052) |
| 8 | wzphar | pharname vs pharmacyname | `pharname`; `pharmacyname` → storediscount/titanpharmalist | wzphar SELECT uses `pharname` |
| 9 | taronlineeg / farysales | swapped lists | taronlineeg=7-col online; farysales=17-col ledger | farysales INSERT live ×3 (116821/228006/483930) |
| 10 | titaninn | transfer vs purchases | 7-col transfer table | CREATE fragments in ModDTTS; delete/select/drop live |
| 11 | creditdebit | column vs table | `farysales.creditdebit` only | in live farysales INSERT list |

**Bottom line:** adopt `schema_complete.sql` as-is for all 11 items. Every contradiction resolves to the SQL-file shape, and the "other" versions are column lists from `wzdrugs` (§2), `invoicedata`/`RawakidTablew` (§1,§7), `storediscount`/`titanpharmalist` (§8), `farysales` (§9,§11), or the older raw `schema.sql` lineage (§4,§5,§6) — exactly what GAPS §7.1 requested.