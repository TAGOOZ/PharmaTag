# External Integrations (التكاملات الخارجية) — TITAN.W1 Feature Doc

## Purpose

TITAN.W1 (Phye.exe, by Phycod Systems / Pharorg) is not a standalone desktop app — it is a **cloud-connected node in the Phycod ecosystem**. Beyond the local pharmacy (sales, stock, accounts), it continuously talks to external systems:

1. **DrugEye (عين الدواء)** — the vendor's free Egyptian drug database: source of the drug master + prices, updated via `.rar`/`.phy` downloads and bidirectionally synced through the `drgserver` and `usersourceupdate` tables.
2. **Nielsen (نيلسن)** — an opt-in market-research channel where pharmacy sales data is formatted (`;`-delimited), aggregated over 6-month windows, RAR-compressed and **uploaded to a "data-for-sale" cloud path** to be sold to Nielsen.
3. **PhycodSystems cloud** — the vendor backend: 3 hosted servers, ~15 auto-downloaded executables, hardware fingerprint licensing, and an **AnyDesk-based remote-control backdoor** (silent install).
4. **Network / cloud sync** — multi-branch & chain sync via `ModNetwork`, `ModSqlLink`, `ModTitanCloud`, `ModFTP`, `ModMobile`, with FTP/HTTP upload and a large set of cloud data paths.
5. **Remote control & function upload** — the `remotecontrol` table carries "passed functions" (VB6 function code) pushed from the server and executed locally; `usersourceupdate` carries drug price/stock updates.
6. **API endpoints** — SOAP/REST endpoints for ZATCA (Saudi e-invoicing), DTTS/RSD (Saudi drug track & trace), ETA (Egyptian tax authority), HungerStation, and small utilities (QR code, country info).

> Scope: this doc covers the *integration layer* only. Sales/stock/accounting internals live in the other `feature_*.md` docs. This doc is the read-only research deliverable for rebuilding these integrations in a modern web+desktop replacement — **including which parts are legally and technically inadvisable to replicate**.

---

## 1. Objects (Modules / Forms / Procs)

| Object | Type | Procs | Role in integration |
|---|---|---|---|
| `ModDrugEye` | Class | 8 | Core DrugEye business logic — API comms, data transform, import/export (drugeye_complete.md:306-317) |
| `FFFDrugEye` | MDIForm | 22 | Main DrugEye search/browse/display UI inside TITAN (drugeye_complete.md:309-314) |
| `FormDrugeeyeUpadteFrom` | Form | 16 | DrugEye update download/extract/apply form (drugeye_complete.md:312-318, 335-343) |
| `ModNilsen` | Class | 20 | Nielsen data collection → format → RAR → curl upload (nielsen_complete.md:64-91) |
| `ModNetwork` | Module | 65 | FTP/HTTP, connectivity, cloud sync core (network_complete.md:4, 642-654; api_integration.md:467) |
| `ModFTP` | Module | 29 | WinInet FTP upload/download/listing (modules_gap_1.md:78-103; network_complete.md:666-676) |
| `ModSqlLink` | Module | 19 | Remote SQL Server linking & replication (modules_gap_1.md:232-281; schema_mapping.md:83) |
| `ModTitanCloud` | Module | 16 | Cloud storage sync, user data, update distribution (network_complete.md:678-687; schema_mapping.md:72) |
| `ModMobile` | Module | 9 | Mobile app connectivity & cloud sync (modules_remaining_1.md:162-189) |
| `ModRemoteControl` | Module | 10 | Remote-control & function-upload (network_complete.md:9, 428-449) |
| `ModOuterConnections` | Module | 18 | External API connections (ETA/ZATCA/SFDA/DrugEye) (modules_gap_1.md:648-677) |
| `ModServerConnections` | Module | 1 | Server connection utility (network_complete.md:11) |
| `ModWMI` | Module | 12 | Hardware fingerprinting for license binding (modules_remaining_1.md:191-218) |
| `ModDrgW` | Module | 13 | Drug-reference DB, reads `drgserver` (modules_gap_1.md:529-564) |
| `ModDRGEXChange` | Module | 4 | Drug data exchange; reads `drgserver`/`usersourceupdate` (modules_remaining_1.md:412-425; schema_mapping.md:73) |
| `ModEcommerce` | Module | 4 / 6 (form) | Online sales (HungerStation) (api_integration.md:474-475) |
| `ModEtaWrappper` | Module | 7 | Egyptian Tax Authority wrapper (api_integration.md:388, 634) |
| `ModDttsEgypt` | Module | 2 | Egypt drug-tracking (api_integration.md:638) |
| `ModDTTS` | Module | 48 | Saudi SFDA drug track & trace (api_integration.md:148-153) |
| `ModZatca` / `ModZatca2Wraber` / `ModSaturn` / `Modzatcasign` | Module | 14/24/29/3 | ZATCA e-invoicing (api_integration.md:379-385) |
| `FormRemoteControl` | Form | 10 | Remote-control UI → `remotecontrol` table (schema_mapping.md:138) |
| `FormRempteTitan` | MDIForm | 13 | Remote-Titan management → `remotecontrol`, `drgserver` (schema_mapping.md:139; phycodsystems_complete.md:578-596) |
| `FormSendChanges` | Form | 3 | Send updates to network → `usersourceupdate` (schema_mapping.md:141) |
| `FormUpdator` | Form | 7 | Receive updates from network → `usersourceupdate` (schema_mapping.md:142) |
| `FormChatAnydesk` | Form | — | AnyDesk chat interface (phycodsystems_complete.md:546) |
| `FormNetwasel` / `FormFaryNet` / `Modfarynet` | Form/Mod | 2/8/2 | Network settings / Fary network (api_integration.md:470-473) |
| `FormDrugStore` | Form | — | المخزن/مستودع — warehouse stock + **margin %** (modules_gap_2.md:568-583; feature_drug_master_pricing.md:71,138) |
| `FormGuide` | Form | — | الدليل/المرشد — in-app help/guide (modules_gap_2.md:782-793) |

Full 6,192-proc inventory: `raz_complete.md`.

---

## 2. DrugEye (عين الدواء) — External Egyptian Drug Database

### 2.1 What DrugEye is

DrugEye is a **free Egyptian drug catalog/reference** app ("دليل الأدوية الأول في مصر") built and maintained by **شركة التجمع الصيدلي للادوية (Pharorg)** — the same company behind TITAN (branded Phycod/Labirdo). Distribution is "**Proprietary (freeware)**": the app is free to *use*, but there is **no public ToS/EULA/API** granting rights to reuse the data (drug_database_legal.md:7, 23-42). Available on Android (`com.phycod.drugeye`), Windows ("Drug Eye for windows") and web (`drugeye.pharorg.com`) (drugeye_complete.md:5-13).

### 2.2 Objects

- `ModDrugEye` (8 procs) — core logic: DB queries, API calls, TITAN↔DrugEye data transform, export/import (drugeye_complete.md:306-317).
- `FFFDrugEye` (22 procs) — main UI: search by name/barcode/company, price display, shape/form display, export/import workflows (drugeye_complete.md:321-333).
- `FormDrugeeyeUpadteFrom` (16 procs) — update downloader: check → download `.rar` → extract → replace `.phy` → copy `DRUGS.PHY` to root → progress (drugeye_complete.md:335-343). **⚠️ Verified (2026-08-15): the compiled procs do NOT download/extract/run SQL — they repric an in-memory drug array and fill a grid; this is legacy/dead behavior in the analyzed build.**

### 2.3 Step-by-step workflow (update / import)

1. On update trigger, TITAN downloads `drugeye.update.titan.rar` from
   `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar`
   (drugeye_complete.md:168; api_integration.md:437-458; strings_utf16.txt:7899).
2. Extract; place `.phy` files into `\Files\DB\` / `\Files\DBI\`; copy `DRUGS.PHY` to the program root.
   - Arabic confirm string: **"تم نسخ ملف التحديث التلقائي الي المجلد الرئيسي للبرنامج واسم الملف هو DRUGS.PHY"** ("the automatic update file has been copied to the main program folder, file name DRUGS.PHY") (drugeye_complete.md:170; strings_readable.txt:10459).
3. Master DB file `\Files\DB\drugeye-for-titan.phy` (+`.rar`) is the read-only reference catalog (drugeye_complete.md:159-163).
4. Imported working copy: `\Files\DBI\fromdrugeye.phy` (drugeye_complete.md:162).

> **⚠️ VERIFIED CORRECTION (2026-08-15):** Steps 1–2 describe the *documented* flow but are **dead code** in the analyzed build. Live download of the URL proved the file is **not a RAR** — it is a **ROT-4-obfuscated text feed** of 23,452 drug records (see drugeye_complete.md §7A). The URL, filenames, and all drugeye SQL strings have **0 p-code references**; `FormDrugeeyeUpadteFrom` performs no download/extract/SQL (it only reprices an in-memory array and fills a grid). The only live drugeye string is `http://www.drugeye.pharorg.com` (21 refs, HTTP web-service call). Drug data actually reaches TITAN via **native VB6 fixed-record `.phy` I/O** (`GetRecOwn4`/`PutRecOwn4` through `ModDrgW`, `FFFDrugEye`, `Files`, `FormImportFromOtherDBI`, `ModDRGEXChange`). Treat steps 1–2 as legacy documentation.

**Export to DrugEye (reverse direction):**
- Staging dir `\Files\Export\DrugEye\`; instruction string: **"Program Folder\\Files\\Export\\DrugEye if you want to sent it to Drug Eye user"** (strings_utf16.txt:6038; drugeye_complete.md:174-184).
- Menu string "Export to drugeye" / "Export_Drug_Upgrading_Data_Base" — exports the drug DB upgrade file (strings_utf16.txt:4886; drugeye_complete.md:181).
- Arabic: **"تصدير الي برنامج عين الدواء"** (strings_readable.txt:10190).

### 2.4 Fields / data captured (drug master)

| Field | Type | Notes |
|---|---|---|
| `drugname` | nvarchar(90-100) | trade name (drugeye_complete.md:97,467) |
| `Barcode`/`Barcode1-5` | varchar(16) | up to 5 barcodes per drug (drugeye_complete.md:99,468) |
| `price` / `PriceNow` | real | selling price (source of price master) |
| `disco` | real | discount % (drugeye_complete.md:104) |
| `units` / `Unitsmall` | int | pack size / small units (drugeye_complete.md:106-107) |
| `shape` | int | drug form code (50+ enumerated forms, drugeye_complete.md:116-143) |
| `stock` | real | inventory (drugeye_complete.md:108) |
| `company` / `CompanyName` | — | manufacturer (drugeye_complete.md:109) |
| `Expire` / `ExpireId` | — | expiry (drugeye_complete.md:110) |
| `vat` | real | VAT % (drugeye_complete.md:111) |
| `localimport` | int | local-import flag (drugeye_complete.md:112) |
| `classy` | — | classification (drugeye_complete.md:113) |
| `pharmacyid` | nvarchar(15) | pharmacy identifier (drugeye_complete.md:114) |
| `lastedit` / `titanid` | — | edit stamp / TITAN internal ID (drugeye_complete.md:115) |

Search capabilities: wildcard `*` names, generic name, up-to-5 barcodes, company, shape filter (drugeye_complete.md:145-152).

### 2.5 The `drgserver` table (shared drug server list)

Per-pharmacy drug records pushed to / pulled from the DrugEye-backed server for chain sharing (drugeye_complete.md:203-212; schema_complete.sql:236-250):

```sql
insert into drgserver (datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport)
select * from drgserver where silsila = N'<chain_id>'
Delete from drgserver where id = N'<id>'
```

Columns: `id, datee, silsila (chain/series ID), mobile (pharmacy phone), drugname (FK→wzdrugs), price, barcode, units, vat, shape, localimport` (schema_complete.md:372-395). Live SQL refs in pcode: strings_utf16.txt:8005 (insert), :8336 (select by silsila), :783 (delete by id).

### 2.6 The `usersourceupdate` table (sync queue)

Staging table for drug **price/stock/unit updates** exchanged between pharmacies and the DrugEye/cloud source (drugeye_complete.md:186-201; schema_complete.sql:283-290):

```sql
insert into usersourceupdate (drugname,price,units,localimport, ...)   -- strings_utf16.txt:8010
SELECT top 3000 * FROM usersourceupdate WHERE Datee > '<timestamp>'    -- strings_utf16.txt:6213
DELETE FROM usersourceupdate WHERE id='<id>'                           -- strings_utf16.txt:4520
select drugname from usersourceupdate                                  -- strings_utf16.txt:1005
```

**Business rule:** the pull query is capped at **3000 rows** per sync (business_logic_complete.md:1247). Rows are deleted by `id` after processing (per-row ack). Read/write modules: `ModTitanCloud`, `ModDRGEXChange`; forms `FormUpdator` (receive) and `FormSendChanges` (send) (schema_mapping.md:72-73,141-142,236).

### 2.7 Related cloud tables

- `drugeyedash2` — server-side dashboard/analytics table TITAN queries: `SELECT * FROM drugeyedash2` (strings_utf16.txt:6208; drugeye_complete.md:214-221).
- MySQL backend DB names (not used for SQL here, they identify the DrugEye API DB): `db_9ffe55_apifordrugeye`, `db_9ffe55_apifordrugeye_admin` (strings_utf16.txt:7674-7675).
- `titanstock`/`titanksastock` — local drug/stock tables (CREATE in drugeye_complete.md:392-403); `wzdrugs` — drug master table that `drgserver.drugname` and `usersourceupdate.drugname` FK to (schema_complete.sql:456-458).

### 2.8 UI strings (Arabic + English)

- `Integration with Nielsen` (strings_utf16.txt:5346) — unrelated but adjacent menu.
- `Export to drugeye` (strings_utf16.txt:4886).
- `Drug Eye for android` / `Drug Eye for windows` (drugeye_complete.md:437-439).
- **"برنامج عين الدواء للاندرويد"** / **"برنامج عين الدواء للويندوز"** (strings_readable.txt:9933-9934).
- **"تصدير الي برنامج عين الدواء"** (strings_readable.txt:10190).
- **"تم نسخ ملف التحديث التلقائي الي المجلد الرئيسي للبرنامج واسم الملف هو DRUGS.PHY"** (strings_readable.txt:10459).
- URL set: drugeye.pharorg.com; rsd-api/start.aspx; drugeye.html; drugeye.update.titan.rar (strings_utf16.txt:7893,7899,7937,7938; drugeye_complete.md:17-39).

### 2.9 Side-effects

- **Drug master/price**: imported `.phy` becomes the local catalog; edits appear in `TitanUserAction` audit table (schema_complete.sql:266-278).
- **Chain share**: local edits write to `drgserver` (outbound) and `usersourceupdate` (inbound queue) → replicated to other chain pharmacies via `ModSqlLink`/`ModTitanCloud`.
- No stock/money side-effects from DrugEye itself — it only supplies the reference catalog and prices.

### 2.10 Legal caveat (SECURITY/LEGAL)

- DrugEye is **Proprietary (freeware)** — no ToS/EULA/privacy policy/API grant found (drug_database_legal.md:23-42). "Free to use app" ≠ "free to reuse data".
- `.phy` is a **proprietary binary format** (`created by titan www.pharorg.com/phye`) undocumented and subject to Pharorg IP (drug_database_legal.md:83-101).
- Recommended alternatives for a replacement: EDA EDDB (gov), CC0 GitHub dataset `karem505/egyptian-drug-database`, SFDA open data/API, SafeRx (drug_database_legal.md:163-205).
- **Do NOT scrape/import DrugEye data into a third-party app without written permission** from Pharorg (01062700020 / dr.saleh.mansour@gmail.com) (drug_database_legal.md:251-259).

---

## 3. Nielsen (نيلسن) — Data Selling

### 3.1 Object inventory — `ModNilsen` (20 procs)

| Address | Tokens | Role (inferred) |
|---|---|---|
| `0x0092c574` | 42 | Init/setup; reads array config vs threshold (1,500,000); calls upload |
| `0x008dfbb8` | 5 | getter/flag |
| `0x00977420` | 63 | data processing + file I/O |
| `0x00900ea8` | 18 | 3-param SQL query (config read) |
| `0x009a491c` | 96 | aggregation — builds `;`-delimited upload strings |
| `0x00abbe20` | 493 | **main collection** — loops, `;` records, `Y`/`H` flags, 50k+ items |
| `0x00aba8a0` | 487 | collection variant (region: Saudi vs Egypt) |
| `0x00b392b0` | 2634 | **largest — field mapper** (50+ LikeTextStr cases, DB→Nielsen format) |
| `0x009a2d04` / `0x009a2b5c` | 112 each | 6-month period date calculators |
| `0x008f2ee0` | 12 | region selector ("egypt" vs "saudi") |
| `0x00979374` | 72 | 7 sequential string replaces (formatting) |
| `0x009c8b1c` | 122 | validation; "NOT AVAILABLE" sentinel |
| `0x00aaf4e0` | 459 | **upload** — dates, 50k loop, upload, response check |
| `0x008ef0a4` | 14 | country path (egypt/saudi/world) |
| `0x00a7fd34` / `0x00a9794c` | 330/402 | sales-data build (barcode, qty, price, discount, units, market share) |
| `0x008f5cd0` | 13 | path builder |
| `0x009150b0` | 30 | **file download** (XMLHTTP → numbers.rar) |
| `0x009e3b6c` | 144 | full upload cycle + curl + response validation |

(nielsen_complete.md:64-91)

### 3.2 Step-by-step workflow

1. **Collect**: pharmacy sales data (per-drug name, barcode, titanid, qty sold, unit price, total, discount, units, stock) + per-pharmacy (name, id, address, country, store) + per-sale (invoiceid, datee, silsilaid, payed, total) (nielsen_complete.md:99-128).
2. **Stage**: write into the `nilsen2` table (cleared via `delete from nilsen2`, strings_utf16.txt:901 / nielsen_complete.md:15).
3. **Aggregate**: 6-month windows (`C:\Nielsen\6-months\eg\`, etc.) — matches Nielsen reporting cycles (nielsen_complete.md:126-128, 279).
4. **Format**: semicolon-delimited records; `'` quoting; `NOT AVAILABLE` for NULLs; VB6 Date double serialization (nielsen_complete.md:247-257).
5. **Compress**: RAR via WinRAR (`C:\Program Files\WinRAR\Rar.exe`); `\Files\DB\Nilsenlist.rar` (nielsen_complete.md:254-257).
6. **Upload**: `curl.exe` (`C:\Windows\System32\curl.exe`) → Phycod server under paths labeled **`titan-users/data-for-sale/...`**; response must be > 3 chars else failure (nielsen_complete.md:151-156, 260-267).
7. **Download report**: fetch `numbers.rar` (members-only) via XMLHTTP (proc `0x009150b0`) → extract to `C:\Nielsen\` (nielsen_complete.md:169-187).
8. **Reset**: local data reset — confirm **"reset Nielsen data?"** (strings_utf16.txt:8306).

### 3.3 The `nilsen2` table

Only SQL evidence is `delete from nilsen2`; columns inferred: `id, drugname`, plus `data` serialized staging column (schema_complete.sql:293-300; schema_complete.md:469-482). It is a **temporary staging/clearing table** ("cleared frequently", schema_complete.md:471). pcode table refs via ModSQL: `delete from nilsen2` (modules_gap_1.md:194). Producer module: `ModNilsen`; consumer form: `FormReportsGeneral` (schema_mapping.md:243).

### 3.4 Upload/download endpoints

| Type | Path | Purpose |
|---|---|---|
| upload | `titan-users/data-for-sale/nielsen-curl` | main curl upload (strings_utf16.txt:8483) |
| upload | `titan-users/data-for-sale/nielsen/egypt` | Egypt data (strings_utf16.txt:8484) |
| upload | `titan-users/data-for-sale/nielsen/saudi` | Saudi data (strings_utf16.txt:8486) |
| upload | `titan-users/data-for-sale/nielsen/members-only/data/` | members-only aggregated (strings_utf16.txt:8485) |
| download | `https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar` | compiled numbers report (strings_utf16.txt:7952; nielsen_complete.md:145-148) |
| local | `C:\Nielsen\`, `C:\Nielsen\6-months\`, `C:\Nielsen\6-months\eg\` | local staging (strings_utf16.txt:4157-4159) |
| local | `\Files\DB\Nilsenlist.rar` | pharmacy list archive (strings_utf16.txt:7236) |
| local | `mobiles.numbers.rar` | mobile numbers archive (strings_utf16.txt:8108) |
| base | `nielsen/` | base dir (strings_utf16.txt:8150) |

(Also Avros chain data-for-sale paths: strings_utf16.txt:2204-2206, `done for avros` :7713.)

### 3.5 UI strings

- `Integration with Nielsen` (strings_utf16.txt:5346) — feature menu label.
- **"التكامل مع نيلسن"** (strings_readable.txt:9264), variant **"التكامل مع نلسن"** (:9263).
- `reset Nielsen data?` (strings_utf16.txt:8306).

### 3.6 Business rules / edge cases

- **6-month aggregation** — hard-coded period windows (procs `0x009a2d04`/`0x009a2b5c`); data split by region `egypt`/`saudi`/`world`.
- 50,000-item processing loops with `Y`/`H` flags and market-share % per drug (nielsen_complete.md:75-76).
- Response validation > 3 chars; On Error handlers on all majors (nielsen_complete.md:267).
- Opt-in-style feature ("Integration with Nielsen"), not mandatory (nielsen_complete.md:216-223).
- Data is *explicitly labeled* **data-for-sale** — this is a monetized data-selling revenue stream for Phycod (nielsen_complete.md:193-199, 282).

### 3.7 SECURITY/LEGAL notes

- Selling/pharmacy sales data → third party (Nielsen via Phycod) **without apparent explicit per-transaction consent**; no opt-out or deletion mechanism visible (phycodsystems_complete.md:740-744).
- Uploads run over HTTP to `htempurl.com` (temp URL hosting), not HTTPS; transmitted effectively in plaintext (phycodsystems_complete.md:746-750).
- For a replacement, this feature is **not recommended to replicate**; if analytics are wanted, make it explicit opt-in, anonymize, and use HTTPS with documented data-processing agreements.

---

## 4. PhycodSystems — the vendor cloud platform

### 4.1 Three servers

| Server | Host | Purpose |
|---|---|---|
| Site 12 | `phycodsystems-001-site12.htempurl.com` | main distribution, cloud sync, tools, themes, Nielsen data (phycodsystems_complete.md:29-98) |
| Site 16 | `phycodsystems-001-site16.htempurl.com` | Saturn/ZATCA (KSA) distribution (phycodsystems_complete.md:29-31, 100-110) |
| Site 17 | `phycodsystems-001-site17.atempurl.com` | Saturn developer tools / alternate distribution (phycodsystems_complete.md:29-31, 112-120) |

### 4.2 Fifteen distributed executables

`Phye.exe` (main), `saturn.exe`, `saturn2.exe`, `saturnonboard.exe`, `toolkit.exe` (ETA), `curl.exe`, `anydesk.exe`, `flex.exe`, `tracer.exe`, `Labirdo.rasd.exe`, `showme.exe`, `easeus.exe`, `emerg.w.exe`, `server.connector.exe`, `Titanfary.exe` (branch instance) — with purpose table in phycodsystems_complete.md:616-634. DLLs incl. `libcurl-x64.dll`, `xi.dll`, `quricol32.dll`, `BouncyCastle.Crypto.dll`, `MessagingToolkit.QRCode.dll`, `SDKNETFrameWorkLib.dll`, `e_sqlite3.dll` (phycodsystems_complete.md:636-649).

**Auto-download policy**: when a feature needs a tool, TITAN checks locally, downloads from `900/` or `Titan3/Us/` if missing, executes **without user confirmation** (phycodsystems_complete.md:676-687; network_complete.md:386-390). URLs incl. `/900/titan.cloud/anydesk.exe`, `/900/titan.cloud/xi.dll`, `/900/curl/curl.exe`, `/900/etatoolkit/toolkit.exe` (api_integration.md:437-451).

### 4.3 Hardware fingerprinting (licensing)

`ModWMI` (12 procs) collects BIOS serial (`Win32_BIOS`), CPU (`Win32_Processor`), OS (`Win32_OperatingSystem`), network adapters (`Win32_NetworkAdapter WHERE NetEnabled = True`), process check (`Win32_Process`), builds a unique machine key (modules_remaining_1.md:191-218). Key is combined with MAC/disk/BIOS/Windows product ID to generate the serial number; license validated online on startup; one serial per hardware combo; transfer requires vendor intervention (phycodsystems_complete.md:488-509).

### 4.4 AnyDesk silent remote access

- `anydesk.exe` hosted at `/900/titan.cloud/anydesk.exe` (phycodsystems_complete.md:546-547; strings_readable.txt:7489).
- Silent/unattended install supported; vendor can initiate connection; "no user confirmation required in some modes"; persistent access possible (phycodsystems_complete.md:565-571).
- Related strings: `Run anydesk`, `Latest version of Anydesk`, `\anydesk.light.exe`, `\Files\DBI\remote-run-date.sdd` (strings_readable.txt:3741,5212,5854,6969,6833).
- UI: `FormChatAnydesk` (chat), `FormRemoteControl`, `ModRemoteControl` (phycodsystems_complete.md:545-550).

### 4.5 SECURITY issues (vendor platform)

1. **HTTP not HTTPS** for virtually all distribution (MITM injectable) (phycodsystems_complete.md:694-698).
2. **No code-signing/hash verification** of downloaded executables (phycodsystems_complete.md:700-704).
3. **Automatic tool execution** with no consent/scanning → supply-chain risk (phycodsystems_complete.md:706-711).
4. **Persistent remote access** (AnyDesk silent, no audit trail) (phycodsystems_complete.md:712-716).
5. **Data exfiltration**: hardware info, usage analytics, business data uploaded; Nielsen data sold (phycodsystems_complete.md:718-722).
6. **Vendor lock-in**: app will not function without Phycod servers (license validation online; tool distribution vendor-controlled) (phycodsystems_complete.md:791-798).

---

## 5. Network / Cloud — multi-branch sync

### 5.1 Cloud API base URLs

```
http://phycodsystems-001-site12.htempurl.com/
http://phycodsystems-001-site16.htempurl.com/
http://phycodsystems-001-site17.atempurl.com/
```
(api_integration.md:406-413)

### 5.2 Cloud data paths (upload/download)

```
/titan-users/allinone/data/          full DB sync (stock, prices, sales, customers)
/titan-users/allinone/mobiles/       mobile app data
/titan-users/drugs-unify/            centralized drug catalog
/titan-users/send-to/                inter-pharmacy transfers
/titan-users/t-link/                 real-time branch link
/titan-users/by-dos/                 DOS-based access
/titan-users/floor2/                 floor 2 data
/titan-users/titan-mobile/files/     mobile file sync
/titan-users/fary-net/               FarWay branch sync
/titan-users/dbi-zipped/Bux-w-{backup,egypt,saudia,world}/   zipped DBI backups
/allinone/  /mypharmacy/  /share/  /fromto/                 misc data endpoints
```
(api_integration.md:415-433; network_complete.md:337-359)

### 5.3 `ModNetwork` (65 procs) — FTP/HTTP core

- FTP APIs: `InternetOpenA`, `InternetConnectA`, `FtpPutFileA`, `FtpGetFileA`, `FtpDeleteFileA`, `FtpOpenFileA`, `FtpFindFirstFileA`, `FtpGetFileSize`, dir ops (network_complete.md:116-131).
- HTTP: `MSXML2.XMLHTTP`, `Msxml2.ServerXMLHTTP.6.0`, `InternetOpenUrlA`, `InternetReadFile`, `InternetWriteFile`, `InternetCheckConnectionA` (network_complete.md:188-215).
- Data flow: local → CSV/XML export → FTP/HTTP upload → cloud → other TITAN instance downloads → import (network_complete.md:653-663).
- FTP config: `\Files\DBI\myftp.phy`; prompts "input your ftp hostname / username / pass / remote path"; PowerShell WebClient STOR script; `ftpcmd.dat` batch script; curl `--ftp-pasv --retry 3 --retry-delay 2` (network_complete.md:133-179; api_integration.md:526-560).

### 5.4 `ModSqlLink` (19 procs) — remote SQL Server linking

- `Driver={SQL Server};SERVER=` connection string; remote query execution; push local→remote; pull remote→local; bulk sync procs up to 1772 tokens (modules_gap_1.md:232-281).
- Tables touched: `drgserver`, `remotecontrol`, `titanpharmalist`, `titanksasales`, `titanksastock`, `titaninn` (modules_gap_1.md:257-263).
- Network share: `net share Titan.master=` / `net share Titan.master /delete`; instructions "now, goto other computers and find 'Titan.master' in your network" (network_complete.md:411-416; modules_gap_1.md:272).
- Server connector: `server.connector.exe`, `\Files\DB\server.connection.report.txt`, `labirdo-server-connector` (network_complete.md:417-424).

### 5.5 `ModTitanCloud` (16 procs) — cloud sync

- Ops strings: `Cloud copy`, `Cloud storage of stock`, `Upload allinone`, `Upload Mobile`, `Upload the drug database to the cloud storage`, `Upload to mobile`, `Upload to RSD`, `Upload zipped DBI`, `Upload Merge File` (network_complete.md:324-335; strings_readable.txt:6452-6453).
- Table usage: `drgserver`, `remotecontrol`, `usersourceupdate` (schema_mapping.md:72).
- Sync triggers: startup (down: news/themes/blacklist), daily (up: sales/stock), on catalog change (up: drug unification), backup/restore, ZATCA/ETA submission, remote support (AnyDesk) (phycodsystems_complete.md:311-324).
- Conflict resolution: **last-write-wins, no versioning, no merge**, vendor can override (phycodsystems_complete.md:346-352).

### 5.6 `ModMobile` (9 procs) + `ModFarWay`

- Mobile: register mobile number with cloud, upload/download mobile data, `Upload to mobile`, `mobiles.numbers.rar`, `xo-mobile.txt`, paths `/titan-users/allinone/mobiles/`, `/titan-users/titan-mobile/files/` (modules_remaining_1.md:162-189).
- FarWay (branch): file-based master-slave sync via `\Files\FarWay\FarData\FromMain\` / `ToMain\Inn\` / `ToMain\Oot\`, heartbeat `i-am-runing.txt`, remote branch exe `Titanfary.exe` (modules_remaining_1.md:388-409).

### 5.7 Side-effects

- Multi-branch chain tables synced: `titanstock`, `titanksastock`, `titanksasales`, `titaninn`, `titanneed`, `titanpharmalist`, `usersourceupdate`, `remotecontrol`, `orders` (network_complete.md:602-615; feature_transfers_logistics.md:528).
- Cloud uploads contain full business data (sales, stock, customers, revenue) (phycodsystems_complete.md:527-532).

---

## 6. Remote control & function upload

### 6.1 The `remotecontrol` table

```sql
CREATE TABLE remotecontrol (
    id              INT IDENTITY(1,1),      -- PK
    datee           REAL DEFAULT 0,         -- date
    mobile          NVARCHAR(15) DEFAULT '',-- pharmacy phone
    copyid          NVARCHAR(50) DEFAULT '',-- copy identifier
    passedfunctions NVARCHAR(MAX) DEFAULT ''-- uploaded functions data
);
```
(schema_complete.sql:255-261; schema_complete.md:399-416)

SQL evidence (strings_utf16.txt:8008, 902, 903, 8347, 8348):
```
insert into remotecontrol (datee,mobile,copyid,passedfunctions)
select id,datee,passedfunctions from remotecontrol where mobile = N'<mobile>'
select passedfunctions from remotecontrol where datee > N'<ts>'     -- pull pending commands
delete from remotecontrol where id = N'<id>'                        -- ack/remove processed
delete from remotecontrol where passedfunctions =N'<fn>'            -- remove by function
```

### 6.2 Workflow (remote control / function upload)

1. **Server-side**: a command record is inserted with the target pharmacy phone in `mobile`, a `copyid` identifying the software copy, and **`passedfunctions`** = serialized VB6 function code/payload.
2. **Client-side**: TITAN polls `select passedfunctions from remotecontrol where datee > <lastcheck>` — i.e. fetches all functions newer than the last poll.
3. **Execution**: the passed functions are applied locally (the technical-support/function-upload mechanism); processed rows deleted by `id` or by `passedfunctions`.
4. **Register**: the pharmacy registers its copy — Arabic strings **"ادخل رقم موبايل صحيح ليتخدم ككود لنسختك علي السيرفر"** ("enter a correct mobile number to serve as the code for your copy on the server") (strings_readable.txt:8567) and **"تسجيل برنامجك لدي الدعم الفني"** ("register your program with technical support") (strings_utf16.txt:6133-6134; strings_readable.txt:10131/10135).
5. **Tech-support login**: **"Log in as Technical Support"** (strings_utf16.txt:5571) / **"Log in as a manager without logging off current user"** (:5572) / **"ادخل بحساب الدعم الفني"** (strings_readable.txt:8515) — grants elevated permissions; **"الان انت تملك صلاحيات الدعم الفني"** ("you now hold technical-support permissions") (strings_readable.txt:9160). Needs perms string: **"تحتاج لصلاحيات الدعم الفني ... الدخول كدعم فني"** (strings_readable.txt:10065).
6. **Remote titan** (`FormRempteTitan`, 13 procs): remote DB access, view/edit data, remote config, license update, transfers — touches `remotecontrol` and `drgserver` (phycodsystems_complete.md:578-596; schema_mapping.md:139).
7. **Remote GUI**: `ModRemoteControl` (10 procs) + `FormRemoteControl` + AnyDesk for full screen control (network_complete.md:428-449; phycodsystems_complete.md:541-576).

### 6.3 `usersourceupdate` (function/data upload queue)

Separate queue for **drug updates** (not functions): `id, drugname, price, units, localimport, datee` (schema_complete.sql:283-290). Pull capped at 3000 rows (business_logic_complete.md:1247); delete-by-id ack; forms `FormSendChanges` / `FormUpdator` (schema_mapping.md:141-142). Related Arabic hint: **"ادخل 555 لرفع اسماء الموردين الي كل الفروع"** ("enter 555 to upload supplier names to all branches") (strings_readable.txt:8433); **"اخل عدد العمليات المطلوب رفعها"** ("enter the number of operations to upload") (:8427); **"ادخال كود السلسة لكل صيدلية"** ("enter the chain code for each pharmacy") (:8430).

### 6.4 UI strings (Arabic)

- **"ادارة الدعم الفني"** (technical-support management) (strings_readable.txt:8428).
- **"التواصل مع فريق الدعم الفني"** (contact tech-support team) (:9270).
- **"الفاتورة التي تحاول الارجاع منها غير موجودة علي السيرفر"** (return invoice not found on server) (:9498).
- **"بحث عن فاتورة الكترونية علي السيرفر"** (search for e-invoice on server) (:9874).
- **"بيانات الدعم الفني لا يمكن عرضها"** (tech-support data cannot be displayed) (:9993).
- **"المعلومات غير متوفرة اتصل بالدعم الفني"** (info unavailable — contact tech support) (:9683).
- Dangerous-command gate: **"هذا الامر خطير للغاية . استشر الدعم الفني. اذا كنت تدرك هذا اكتب الرقم 600"** ("this command is extremely dangerous; consult tech support; if you understand, type 600") (strings_readable.txt:903).
- `\Files\DBI\remote-run-date.sdd` — last remote-run timestamp file (strings_readable.txt:6833).

### 6.5 SECURITY notes

- `passedfunctions` is effectively **remote code execution**: the vendor can push arbitrary function code to any registered copy and it runs at next poll, with rows auto-deleted after execution — no audit trail beyond the table itself.
- AnyDesk adds full GUI-level remote access; combined, the vendor has unauthenticated-by-user control (phycodsystems_complete.md:566-576, 712-716).
- `remotecontrol` rows are keyed by mobile phone — phone number is the *identity/copy code* on the server (strings_readable.txt:8567).

---

## 7. API / HTTP endpoints (api_integration.md)

| Endpoint | Purpose |
|---|---|
| `https://rsd.sfda.gov.sa:443/ws/PharmacySaleService/PharmacySaleService` (+ Cancel/Dispatch/Accept/Return/Transfer) | Saudi DTTS SOAP drug track & trace (api_integration.md:13-18) |
| `https://rsd.sfda.gov.sa/smp/Account/Index` | RSD login (drugeye_complete.md:293) |
| ZATCA OAuth `/connect/token` + submit | KSA e-invoicing via `toolkit.exe`/`saturn.exe` (api_integration.md:188-211) |
| `https://api.invoicing.eta.gov.eg`, `id.eta.gov.eg` (+ preprod) | Egyptian Tax Authority (network_complete.md:248-265) |
| `/api/v1/receipts/recent`, `/api/v1/receiptsubmissions`, `/api-sign.aspx` | ETA receipts/signing (network_complete.md:293-304) |
| `https://hungerstation.partner.deliveryhero.io/v2/oauth/token` + `/v2/chains/` | HungerStation e-commerce; token at `\Files\DBI\hungerstation.token.txt` (network_complete.md:221-241) |
| `http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso` | country/currency info (SOAP) (api_integration.md:481-491) |
| `http://api.qrserver.com/v1/create-qr-code/?` | QR generation (api_integration.md:393-402, 493-498) |
| `http://chart.googleapis.com/chart?` | Google Charts (network_complete.md:694) |
| `http://www.drugeye.pharorg.com/rsd-api/start.aspx` | DrugEye RSD proxy (drugeye_complete.md:23) |
| `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/TitanNews.txt` | news/update check (api_integration.md:501) |

Modules: `ModDTTS`(48), `ModZatca`(14), `ModZatca2Wraber`(24), `ModSaturn`(29), `ModEtaWrappper`(7), `ModOuterConnections`(18), `ModEcommerce`(4). Full mapping in api_integration.md:684-712.

---

## 8. Tables (CREATE TABLE, annotated)

```sql
-- 15. drgserver — shared drug server list (chain price/drug share via DrugEye cloud)
CREATE TABLE drgserver (
    id              INT IDENTITY(1,1),     -- PK auto-increment
    datee           REAL DEFAULT 0,        -- date (VB6 serial)
    silsila         NVARCHAR(50) DEFAULT '',-- chain/series ID
    mobile          NVARCHAR(15) DEFAULT '',-- pharmacy phone
    drugname        NVARCHAR(100) DEFAULT '',-- FK -> wzdrugs.drugname
    price           REAL DEFAULT 0,        -- price (source for chain price share)
    barcode         VARCHAR(16) DEFAULT '',-- barcode
    units           INT DEFAULT 0,         -- units
    vat             REAL DEFAULT 0,        -- VAT %
    shape           INT DEFAULT 0,         -- drug form code
    localimport     INT DEFAULT 0          -- import source flag
);
-- SQL: insert into drgserver (datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport)
--      select * from drgserver where silsila = N'<chain>'
--      Delete from drgserver where id = N'<id>'

-- 16. remotecontrol — remote control / function upload log
CREATE TABLE remotecontrol (
    id              INT IDENTITY(1,1),     -- PK
    datee           REAL DEFAULT 0,        -- date
    mobile          NVARCHAR(15) DEFAULT '',-- pharmacy phone (copy code)
    copyid          NVARCHAR(50) DEFAULT '',-- copy identifier
    passedfunctions NVARCHAR(MAX) DEFAULT ''-- pushed function payload (RCE channel)
);
-- SQL: insert into remotecontrol (datee,mobile,copyid,passedfunctions)
--      select id,datee,passedfunctions from remotecontrol where mobile = N'<mobile>'
--      select passedfunctions from remotecontrol where datee > N'<ts>'
--      delete from remotecontrol where id = N'<id>'
--      delete from remotecontrol where passedfunctions =N'<fn>'

-- 18. usersourceupdate — drug price/stock update sync queue (cloud/DrugEye)
CREATE TABLE usersourceupdate (
    id              INT IDENTITY(1,1),     -- PK
    drugname        NVARCHAR(100) DEFAULT '',-- FK -> wzdrugs.drugname
    price           REAL DEFAULT 0,        -- price
    units           INT DEFAULT 0,         -- units
    localimport     INT DEFAULT 0,         -- import source
    datee           REAL DEFAULT 0         -- date
);
-- SQL: insert into usersourceupdate (drugname,price,units,localimport,...)
--      SELECT top 3000 * FROM usersourceupdate WHERE Datee > '<ts>'  -- capped pull
--      DELETE FROM usersourceupdate WHERE id='<id>'

-- 19. nilsen2 — Nielsen staging table (cleared frequently)
CREATE TABLE nilsen2 (
    id              INT IDENTITY(1,1),     -- PK [INFERRED]
    drugname        NVARCHAR(100) DEFAULT '',-- drug name
    data            NVARCHAR(MAX) DEFAULT ''-- serialized/aggregated data [INFERRED]
);
-- SQL: delete from nilsen2

-- 17. TitanUserAction — audit of all drug modifications (compliance trail)
CREATE TABLE TitanUserAction (
    id INT IDENTITY(1,1), drugname NVARCHAR(100) DEFAULT '0',
    typevalue NVARCHAR(100) DEFAULT '0', oldvalue NVARCHAR(100) DEFAULT '0',
    newvalue NVARCHAR(100) DEFAULT '0', mobile NVARCHAR(15) DEFAULT '0',
    namee NVARCHAR(100) DEFAULT '', curbarcode VARCHAR(15) DEFAULT '0',
    curprice REAL DEFAULT '0', units INT DEFAULT 0, datee REAL DEFAULT '0'
);
```
(schema_complete.sql:236-300; schema_complete.md:372-482)

Related: `titanpharmalist` (pharmacy list), `taronlineeg` (online catalog), `storediscount`, `titanstock`/`titanksastock` (chain-stock), `orders`, `titaninn`/`titanneed` (inter-pharmacy) (network_complete.md:602-615). FK graph: `wzdrugs.drugname ──< drgserver` and `──< usersourceupdate`; `wzphar.pharmacyid ──< remotecontrol.mobile` and `──< drgserver.mobile` (schema_complete.sql:456-471).

---

## 9. UI strings summary (Arabic + English)

| Arabic / English | Where | Source |
|---|---|---|
| التكامل مع نيلسن / نلسن (Integration with Nielsen) | settings/menu | strings_readable.txt:9263-9264; utf16:5346 |
| برنامج عين الدواء للاندرويد / للويندوز | DrugEye menu | strings_readable.txt:9933-9934 |
| تصدير الي برنامج عين الدواء (Export to DrugEye) | DrugEye menu | strings_readable.txt:10190 |
| تم نسخ ملف التحديث التلقائي ... DRUGS.PHY | update done | strings_readable.txt:10459 |
| ادخال كود السلسة لكل صيدلية | chain setup | strings_readable.txt:8430 |
| ادخل 555 لرفع اسماء الموردين الي كل الفروع | function upload | strings_readable.txt:8433 |
| اخل عدد العمليات المطلوب رفعها | function upload count | strings_readable.txt:8427 |
| ادخل رقم موبايل صحيح ليتخدم ككود لنسختك علي السيرفر | register copy | strings_readable.txt:8567 |
| تسجيل برنامجك لدي الدعم الفني (Register your program...) | register | strings_utf16.txt:6133-6134; readable:10131/10135 |
| ادخل بحساب الدعم الفني (Log in as Technical Support) | tech login | strings_utf16.txt:5571; readable:8515 |
| الان انت تملك صلاحيات الدعم الفني | perms granted | strings_readable.txt:9160 |
| ادخل هامش ربح المخزن وغالبيا يكون من واحد الي ستة | warehouse margin | strings_readable.txt:8635 (FormDrugStore) |
| هذا الامر خطير للغاية ... اكتب الرقم 600 | danger gate | strings_readable.txt:903 |
| reset Nielsen data? | Nielsen reset | strings_utf16.txt:8306 |
| Log in as a manager without logging off current user | manager | strings_utf16.txt:5572 |

---

## 10. Business rules / edge cases

- **DrugEye master**: imported `.phy` is reference; edits logged to `TitanUserAction`; chain edits propagate via `drgserver`/`usersourceupdate`.
- **Nielsen**: 6-month aggregation windows; region split (eg/saudi/world); `;`-delimited payload; RAR + curl; response must exceed 3 chars; local reset available.
- **usersourceupdate**: pull capped at **3000 rows**; delete-by-id ack; price/units/localimport changes flow pharmacy↔cloud.
- **remotecontrol**: pull = `datee > last_poll`; execute then delete-by-id; `mobile` is the copy identity; `copyid` identifies installation.
- **Cloud sync**: last-write-wins; no versioning/merge; vendor override possible; network share `Titan.master` for LAN mode.
- **Licensing**: hardware fingerprint (WMI) → serial → online validation; trial limited (no cloud/ZATCA/ETA, watermarked reports) (phycodsystems_complete.md:497-509).
- **Country gating**: "Export to current country is forbidden" (modules_remaining_1.md:30); per-country drug `.phy` files (drugeye_complete.md:240-249).

---

## 11. SECURITY / LEGAL summary for the replacement

| Item | Risk | Recommendation |
|---|---|---|
| DrugEye data reuse | Copyright/proprietary `.phy`; no license (drug_database_legal.md:7,83-101) | Use EDA/CC0/SFDA datasets; get written permission for DrugEye |
| Nielsen data selling | Sells pharmacy data without explicit consent; HTTP-only (phycodsystems_complete.md:740-750) | Do not replicate; if analytics: opt-in, anonymized, HTTPS, documented DPAs |
| AnyDesk silent install / remotecontrol `passedfunctions` | Remote code execution + persistent access, no audit (phycodsystems_complete.md:712-716) | Replace with authenticated, consent-gated, audited support tunnel (e.g. signed pairing) |
| HTTP distribution + unsigned binaries | MITM / supply-chain (phycodsystems_complete.md:694-711) | HTTPS + code-signing + hash pinning for all tool downloads |
| Vendor lock-in / online-only license | App dead without vendor servers (phycodsystems_complete.md:791-798) | Design offline-capable licensing; self-hostable sync |
| Hardware fingerprint privacy | Collects BIOS/CPU/MAC/OS data silently (phycodsystems_complete.md:511-519) | Collect minimal device ID with disclosure |

---

## 12. Sources

- `drugeye_complete.md`, `drug_database_legal.md`, `nielsen_complete.md`, `phycodsystems_complete.md`, `network_complete.md`, `api_integration.md`
- `modules_gap_1.md` (ModFTP, ModOuterConnections, ModSqlLink, ModDrgW), `modules_remaining_1.md` (ModMobile, ModWMI, ModDRGEXChange), `modules_gap_2.md` (FormDrugStore §28-30, FormGuide §42)
- `schema_complete.sql`/`schema_complete.md` (tables 15-19, FK graph), `business_logic_complete.md` (§2.9-2.12, :1247), `schema_mapping.md` (module↔table matrix)
- Ground truth: `titan_decompile/strings_utf16.txt` (string index = 1-based line − 3), `titan_decompile/strings_readable.txt`, `titan_decompile/pcode_disasm.txt`
