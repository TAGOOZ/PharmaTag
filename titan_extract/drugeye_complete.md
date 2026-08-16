# DrugEye (عين الدواء) — Complete Analysis

## Executive Summary

DrugEye (عين الدواء / "Drug Eye") is a **free Egyptian drug database and reference application** built and maintained by the same company that makes TITAN.W1 — **شركة التجمع الصيدلي للادوية (Pharorg Egyptian Pharmaceutical Union Company)**, operating under the brand **Phycod / Labirdo**. It is available as:

1. An **Android app** (com.phycod.drugeye on Google Play)
2. A **Windows desktop app** ("Drug Eye for windows")
3. An **online web application** at drugeye.pharorg.com

DrugEye is NOT a price comparison tool or community platform. It is a **comprehensive drug catalog database** for the Egyptian market — a reference tool for pharmacists, doctors, and consumers to look up registered drugs in Egypt by name, barcode, company, etc.

TITAN.W1 has **deep bidirectional integration** with DrugEye: TITAN exports its drug data TO DrugEye, and DrugEye's master drug database can be imported INTO TITAN.

---

## 1. URLs and Endpoints

### Primary URLs
| URL | Purpose |
|-----|---------|
| `http://www.drugeye.pharorg.com` | Main DrugEye web application (returns 403 on direct fetch — likely requires auth or specific routing) |
| `http://www.drugeye.pharorg.com/rsd-api/start.aspx` | RSD (Saudi Drug Track and Trace) API integration endpoint |
| `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/drugeye.html` | Download page for DrugEye clients |
| `http://www.pharorg.com/drugeye/` | Marketing page for DrugEye on the main company site |
| `https://drugeye.pharorg.com/drugeyeapp/android-search/drugeye-android-live-go.aspx` | Online drug search (web alternative to Android app) |

### Download URLs
| URL | Purpose |
|-----|---------|
| `http://www.pharorg.com/Titan3/Us/drugeyewindows.rar` | DrugEye for Windows download |
| `http://www.pharorg.com/Titan3/Us/drugeyeandroid.apk` | DrugEye for Android APK |
| `https://play.google.com/store/apps/details?id=com.phycod.drugeye` | Google Play store listing |

### Data Sync URLs
| URL | Purpose |
|-----|---------|
| `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar` | DrugEye database update file for TITAN |

---

## 2. What DrugEye IS

From the official pharorg.com/drugeye/ page (translated from Arabic):

> **"Drug Eye: A Comprehensive Guide to Drugs in Egypt"**
>
> Discover the world of Egyptian drugs easily and effectively with the "Drug Eye" application, the latest release from the Egyptian Pharmaceutical Union. Whether you are a pharmacist, doctor, or consumer, this free application provides you with a comprehensive and up-to-date database of drugs registered in Egypt, with advanced search capabilities that make finding the required information quick and simplified.

### Key Features (from website)
- **Massive database**: Includes ALL drugs registered in Egypt
- **15 different search methods**: Search by trade name, scientific name, manufacturer company
- **Easy-to-use interface**: Simple, clear design
- **Free and small-size**: No payment required
- **Continuous updates**: Database is regularly updated
- **Drug price guide**: Know the latest drug prices
- **Comprehensive drug information**: Detailed information about each drug
- **Search with wildcards**: Use `*` for unknown letters (e.g., `*gm*600` for Augmentin 600mg)

### Positioning (from website)
DrugEye positions itself as:
- "The #1 drug guide in Egypt" (دليل الأدوية الأول في مصر)
- "Master of Egyptian drugs" (ماستر الأدوية المصرية)
- "Atlas of Egyptian drugs" (أطلس الأدوية المصرية)
- "Egyptian drugs database" (قاعدة بيانات الأدوية المصرية)
- "Egyptian drugs search engine" (باحث الأدوية المصرية)

---

## 3. Who Runs It

### Company: شركة التجمع الصيدلي للادوية (Pharorg Egyptian Pharmaceutical Union Company)
- **Website**: www.pharorg.com
- **Type**: Egyptian joint stock company (شركة مساهمة مصرية)
- **Founded by**: التجمع الصيدلي المصري (Egyptian Pharmaceutical Union)
- **Description**: First pharmaceutical company fully owned by Egyptian pharmacists, with 20% of shares allocated to other medical professions
- **Phone**: 01062700020
- **Software development**: Labirdo / Phycod Programming (شركة لابيردو للبرمجيات)
- **Facebook groups**: www.facebook.com/groups/pharorg, www.facebook.com/groups/pharorg.phye.users

### Related Products
- **TITAN (تيتان)**: Pharmacy management system (the app we're reverse-engineering)
- **Saturn**: ZATCA e-invoicing integration (for Saudi Arabia)
- **Phye.exe**: The TITAN runtime engine (PHYCOD Programming Language)

---

## 4. What Data DrugEye Provides

Based on the database structure strings found in TITAN:

### Drug Data Fields
From SQL DDL and insert statements found in the codebase:

| Field | Type | Description |
|-------|------|-------------|
| `drugname` | nvarchar(90-100) | Drug trade name |
| `Barcode` / `Barcode1-5` | varchar(16) | International barcode (EAN/UPC) |
| `price` | real | Current selling price |
| `PriceNow` | real | Current price (alternate field) |
| `disco` | — | Discount percentage |
| `units` | int | Package units |
| `Unitsmall` | int | Small units |
| `shape` | int | Drug form (encoded as integer) |
| `stock` | real | Stock quantity |
| `company` / `CompanyName` | — | Manufacturing company |
| `Expire` / `ExpireId` | — | Expiry date |
| `pack` / `packs` | — | Package information |
| `vat` | — | VAT percentage |
| `localimport` | — | Local import flag |
| `classy` | — | Drug classification |
| `pharmacyid` | nvarchar(15) | Pharmacy identifier |
| `lastedit` | — | Last edit timestamp |
| `titanid` | — | TITAN internal ID |

### Drug Forms (Shape Values)
The `shape` field encodes drug forms as integers. The following forms are enumerated in the codebase:

**Oral forms:**
- CAPSULE, TABLET, FILM COATED TABLET, COATED TABLET, ENTERIC COATED TABLET
- CHEWABLE TABLET, EFFERVESCENT TABLET, DISINTEGRATING TABLET, DISPERSIBLE TABLET
- BIOADHESIVE TABLET, DUAL RELEASE CAPSULE, ENTERIC COATED CAPSULE
- ENTERIC COATED SOFT GELATIN CAPSULE, INHALATION CAPSULE
- SOFT GELATIN CAPSULE (implied)
- SYRUP, DRY SYRUP, ORAL DROPS, ORAL GEL, ORAL OINTMENT
- GRANULES, EFFERVESCENT GRANULES, GRANULES FOR ORAL SUSPENSION
- POWDER, POWDER FOR ORAL SUSPENSION
- SOLUTION, SUSPENSION

**Topical forms:**
- CREAM, FACE CREAM, HAIR CREAM, LIPOCREAM, EMULGEL, GEL, HAIR GEL
- OINTMENT, EYE OINTMENT, EYE/EAR OINTMENT
- NASAL GEL

**Ophthalmic forms:**
- EYE DROPS, EYE/EAR DROPS, EYE/NOSE DROPS, OPHTHALMIC SOLUTION, OPHTHALMIC SUSPENSION

**Other forms:**
- DROPS (general), EAR DROPS, NASAL DROPS, E.NASAL DROPS
- INHALER, INHALATION POWDER, INHALATION SOLUTION
- INJECTION, PATCH, SUPPOSITORY (implied)
- VAGINAL CREAM
- HEMODIALYSIS SOLUTION, ANTISEPTIC SOLUTION

### Drug Search Capabilities
From the codebase, TITAN supports multiple barcode fields (Barcode1 through Barcode5) for cross-referencing drugs. The search supports:
- Trade name search (with wildcard support using `*`)
- Generic/scientific name search
- Barcode search (up to 5 barcode fields per drug)
- Company/manufacturer search
- Shape/form filtering

---

## 5. Data Flow Between TITAN and DrugEye

### 5.1 Files Downloaded FROM DrugEye

| File | Path in TITAN | Purpose |
|------|---------------|---------|
| `drugeye-for-titan.phy` | `\Files\DB\drugeye-for-titan.phy` | DrugEye master drug database for TITAN (PHY format) |
| `drugeye-for-titan.rar` | `\Files\DB\drugeye-for-titan.rar` | Compressed version of above |
| `drugeye.update.titan.rar` | `\Files\db\drugeye.update.titan.rar` | Incremental update file from DrugEye server |
| `fromdrugeye.phy` | `\Files\DBI\fromdrugeye.phy` | DrugEye data imported into TITAN's working DB |
| `DRUGS.PHY` | (root program folder) | Auto-updated drug database file (copied from update) |

**Update mechanism:**
1. TITAN downloads `drugeye.update.titan.rar` from `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar`
2. The update is extracted and the `DRUGS.PHY` file is copied to the program's main folder
3. The Arabic string `تم نسخ ملف التحديث التلقائي الي المجلد الرئيسي للبرنامج واسم الملف هو DRUGS.PHY` confirms: "The automatic update file has been copied to the main program folder, and the file name is DRUGS.PHY"

> **⚠️ EMPIRICAL CORRECTION (verified 15-Aug-2026 by downloading the live feed):** The above is the *documented* flow. It is **NOT what the running code does**. The file at that URL is **not a RAR archive** and the app's p-code has **0 references** to this URL string (see §7A "Empirical feed analysis" and §9 "verified dead code"). Treat §5.1's steps 1–3 as a **legacy/stale description**, not current behavior.

### 5.2 Files Uploaded/exported TO DrugEye

| File/Directory | Path in TITAN | Purpose |
|----------------|---------------|---------|
| Export directory | `\Files\Export\DrugEye\` | Staging area for DrugEye exports |
| Export instruction | "Program Folder\\Files\\Export\\DrugEye if you want to sent it to Drug Eye user" | Manual export |

**What gets exported:**
- The string "Export to drugeye" indicates a function to export drug data
- "Export_Drug_Upgrading_Data_Base" suggests it exports a drug database upgrade file
- "Export current drug to a file" allows exporting individual drug records
- The export goes to `\Files\Export\DrugEye\` directory
- Users manually place files there to share with DrugEye users

### 5.3 The `usersourceupdate` Table

This appears to be the **synchronization table** for drug price/stock updates between pharmacies and the DrugEye cloud:

```sql
-- Structure (inferred from inserts):
insert into usersourceupdate (drugname, price, units, localimport, ...)

-- Reading updates:
SELECT top 3000 * FROM usersourceupdate WHERE Datee > '<timestamp>'

-- Cleanup:
DELETE FROM usersourceupdate WHERE id='<id>'
```

This table stores drug updates that can be pushed to or pulled from the cloud (DrugEye server).

### 5.4 The `drgserver` Table

Drug server data for sharing between pharmacies via DrugEye:

```sql
insert into drgserver (datee, silsila, mobile, drugname, price, barcode, units, vat, shape, localimport)
select * from drgserver where silsila = N'<chain_id>'
```

Fields: date, chain/serial, mobile, drug name, price, barcode, units, VAT, shape, local import flag.

### 5.5 The `drugeyedash2` Table

```sql
SELECT * FROM drugeyedash2
```

This appears to be a **dashboard/analytics table** on the DrugEye server that TITAN queries. The "dash" suffix suggests it's a dashboard data source — possibly aggregated statistics about drug usage, prices, or pharmacy activity.

---

## 6. The `.phy` File Format

The `.phy` extension is TITAN's proprietary binary database format (PHYCOD format). From the codebase:

### Evidence of Binary Format
- The strings file contains `created by titan www.pharorg.com/phye` — suggesting .phy files are created by the TITAN/Phye system
- `PHYCOD PROGRAMMING LANGUAGE` appears in the strings, confirming PHY is the programming language
- `.phy` files are used for virtually all TITAN data stores (customers, sales, purchases, drugs, etc.)

### `.phy` Files Related to DrugEye
| File | Description |
|------|-------------|
| `fromdrugeye.phy` | Drug data imported FROM DrugEye |
| `drugeye-for-titan.phy` | DrugEye's master drug database formatted for TITAN |
| `DRUGS.PHY` | Auto-updated drug database (copied from DrugEye update) |
| `drugsiraq.phy` | Iraq-specific drug database |
| `drugsksa.phy` | Saudi Arabia-specific drug database |
| `drugsyamen.phy` | Yemen-specific drug database |
| `egypt.phar.phy` | Egypt pharmaceutical database |
| `bahrein.phar.phy` | Bahrain pharmaceutical database |
| `iraq.phar.phy` | Iraq pharmaceutical database |
| `oman.phar.phy` | Oman pharmaceutical database |
| `saudia.phar.phy` | Saudi pharmaceutical database |
| `sudan.phar.phy` | Sudan pharmaceutical database |
| `yamen.phar.phy` | Yemen pharmaceutical database |
| `Libya.phar.phy` | Libya pharmaceutical database |

### Country-Specific Databases
TITAN maintains separate `.phy` drug databases for each Arab country:
- Egypt, Iraq, Saudi Arabia, Yemen, Bahrain, Oman, Sudan, Libya
- Each has a `*.phar.phy` file (pharmaceutical data) and some have `drugs*.phy` files

---

## 7. The `.rar` Update Files

TITAN uses `.rar` archives for distributing updates:
- `drugeye-for-titan.rar` — compressed drug database
- `drugeye.update.titan.rar` — incremental update from server
- Various other `.rar` files for software components

The update flow:
1. Download `.rar` from phycodsystems server
2. Extract contents
3. Place `.phy` files in appropriate `\Files\DB\` or `\Files\DBI\` directories
4. Copy `DRUGS.PHY` to program root

> **⚠️ EMPIRICAL CORRECTION:** Despite the `.rar` name, `drugeye.update.titan.rar` is **NOT an archive**. Live download (2026-08-15) returned HTTP 200, 1,055,820 bytes of **plain ASCII text** (no `Rar!` magic header). It is a **ROT-4-obfuscated drug feed**. See §7A.

---

## 7A. Empirical feed analysis — what `drugeye.update.titan.rar` actually is (verified 2026-08-15)

### 7A.1 The file is not a RAR — it's a ROT-4 obfuscated text drug feed

A live download from `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar` returned:

- **HTTP 200**, `content-type: application/octet-stream`
- **`last-modified: Wed, 12 Aug 2026 12:41:51 GMT`** (server re-publishes; the feed is a static file the vendor overwrites)
- **`cache-control: max-age=31536000`** (clients may cache for 1 year)
- **1,055,820 bytes**, CRLF lines, **23,452 records** — no `Rar!` magic header, so not a RAR/ZIP archive
- Re-download seconds later gave an **identical MD5** (`a806dff7...`) → stable static snapshot, not generated per-request

### 7A.2 The obfuscation scheme (ROT-4 / Caesar +4)

Every letter and digit is shifted **+4** (decode = shift **−4**), with wraparound; selected punctuation is literal:

| Range | Rule | Example |
|---|---|---|
| `A`–`Z` + `[ \ ] ^` (0x41–0x5E) | shift −4 (wrap) | `ZMPPE` → `VILLA`, `\` → `X` |
| `a`–`z` (0x61–0x7A) | shift −4 (wrap) | `b` → `x` (used as field sep after decode) |
| digits `4`–`9` → `0`–`5`; `: ; < = >` → `6`–`9` | shift −4 | `4` → `0`, `:` → `6`, `=` → `9` |
| `$ . , ( ) & - /` and space | **literal** (unshifted) | stays as-is |

So encoded `4bZMPPE$...` decodes to `0xVILLA$...`, and encoded digit `1` decodes to `-` (`ANTI1DANDRUFF` → `ANTI-DANDRUFF`).

### 7A.3 Record format (after decode)

```
<barcode>x<BRAND>$<product>$<form>$<strength>...x<PRICE>x<QTY>x
```

| Field | Example | Stats (23,452 records) |
|---|---|---|
| Barcode | `6224007745014` (Egyptian EAN-13) | 11,198 barcode-like codes (≥8 digits) |
| BRAND | `ZINCOFACT` | 12,828 distinct brands |
| product/form/size | `CREAM$50$GM`, `LOTION$60$ML` | variable arity (`$`-joined, 3–10 fields) |
| PRICE | `75`, `16.75`, `241.25` | 23,438 rows have prices (min 2.05, max 375,504) |
| QTY | `1` (mostly) | also 2/3/4/5 |

Sample decoded rows:
```
6224007745014 | ZINCOFACT  | CREAM$50$GM            | 75
6224000201593 | ZINCODERM  | TOPICAL$LOTION$120ML   | 65
3401344908347 | WHITE      | OBJECTIVE$LIGHTENING$CREAM$DAY$CARE$30ML | 420
6223003572877 | ZETRAFENAC | 0.21)EYE$DROPS$5$ML   | 1826
```

Decoded copy saved at `/tmp/opencode/drugeye.update.titan.decoded.txt` (23,452 lines).

### 7A.4 How this feed is "updated"

- **Vendor side:** Pharorg rebuilds its master catalog → applies ROT-4 → overwrites the static file on the htempurl server. `last-modified` reflects each publish (last seen 2026-08-12).
- **Client side:** whoever fetches the URL gets the newest snapshot; the decoded copy updates only on re-fetch + re-decode.
- **In TITAN itself:** the app's p-code has **0 references** to this URL or to the related filenames/SQL (verified with the corrected 2-byte/4-byte index decoder). Nothing in the analyzed build auto-downloads it. Any update is manual/external/vestigial (see §9).

---

## 8. Database Backend

### MySQL Database: `db_9ffe55_apifordrugeye`

This is the **backend MySQL database** that powers the DrugEye API:

| Identifier | Purpose |
|------------|---------|
| `db_9ffe55_apifordrugeye` | Main DrugEye API database |
| `db_9ffe55_apifordrugeye_admin` | Admin access to the same database |

The naming convention `db_9ffe55_apifordrugeye` follows a pattern: `db_<hash>_apifordrugeye`, suggesting this is a hosted MySQL database (likely on a shared hosting service) with a randomly-generated prefix for isolation.

### API Endpoint: rsd-api

`http://www.drugeye.pharorg.com/rsd-api/start.aspx`

This is NOT an API for the drug database itself. "RSD" stands for **"Drug Track and Trace System" (RSD = نظام تتبع الأدوية)** — this is the Saudi SFDA (Saudi Food and Drug Authority) drug tracking system. The endpoint integrates TITAN with the Saudi RSD system through DrugEye's infrastructure.

Related RSD strings in TITAN:
- `https://rsd.sfda.gov.sa/smp/Account/Index`
- `https://rsd.sfda.gov.sa:443/ws/DispatchService/DispatchService`
- `https://rsd.sfda.gov.sa:443/ws/PharmacySaleService/PharmacySaleService`
- `https://rsd.sfda.gov.sa:443/ws/PharmacySaleCancelService/PharmacySaleCancelService`
- `https://rsd.sfda.gov.sa:443/ws/ReturnService/ReturnService`
- `https://rsd.sfda.gov.sa:443/ws/TransferService/TransferService`
- `Drug Track and Trace System Website (RSD)`
- `Integration tools with RSD`
- `Upload to RSD`

---

## 9. TITAN's DrugEye Module Architecture

### VB6/P-code Components

| Component | Type | Procedures | Description |
|-----------|------|------------|-------------|
| **ModDrugEye** | Class (Module) | 8 | Core DrugEye business logic — data processing, API communication, database sync |
| **FFFDrugEye** | MDIForm | 22 | Main DrugEye UI form — the user-facing interface within TITAN |
| **FormDrugeeyeUpadteFrom** | Form | 16 | DrugEye update download/apply form — handles fetching and installing updates |
| **FFFDS** | MDIForm | — | Multiple instances (70+) — likely the main DrugEye search/browse form (Drug Search) |

### ModDrugEye Procedures (8 procs)
The module handles:
1. Database queries against DrugEye data
2. API calls to drugeye.pharorg.com
3. Data transformation between TITAN's internal format and DrugEye's format
4. Export operations (creating files for DrugEye consumption)
5. Import operations (parsing files from DrugEye)

### FFFDrugEye Procedures (22 procs)
The main form handles:
1. Drug search/display UI
2. Barcode scanning integration
3. Price display
4. Company information display
5. Drug form/shape display
6. Navigation between drug records
7. Export-to-DrugEye workflow
8. Import-from-DrugEye workflow

### FormDrugeeyeUpadteFrom Procedures (16 procs)
The update form handles:
1. Checking for updates from the server
2. Downloading update files
3. Extracting `.rar` archives
4. Replacing `.phy` files
5. Copying `DRUGS.PHY` to program root
6. Progress reporting

> **⚠️ VERIFIED CORRECTION (2026-08-15, p-code disassembly):** Points 1–6 above are the *documented* intent, **not** what the compiled code executes. Deep disassembly of the largest procs (`@0x00a0bd9c` size=664, `@0x00a06988` size=636, `@0x009c1bd0`, `@0x009ec68c`, `@0x009d5868`, `@0x009e2858`) shows **no file open, no download, no SQL**. The form iterates an in-memory drug array (offsets 0x64/0x2C0 = prices), recomputes prices, and pushes rows to a grid (`LateIdCallSt AddItem`). Only generic UI strings are referenced (e.g. `ايجارات`, `رابعا`, `Invalid seller information.`).

### Verified dead code in the analyzed build (2026-08-15)

With a corrected string-index decoder (`idx = b1 | b2<<8 | b3<<16` for 4-byte operands), **all** of the following have **0 LitVarStr references** in `pcode_disasm.txt`:

| String | utf16 line | Purpose |
|---|---|---|
| `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar` | 7899 | the feed download URL |
| `http://phycodsystems-001-site12.htempurl.com/` (base) | 7877 | server base URL |
| `\Files\db\drugeye.update.titan.rar` | 7315 | download destination |
| `\Files\DBI\fromdrugeye.phy` | 7151 | import working copy |
| `\Files\DB\drugeye-for-titan.phy` / `.rar` | 7246/7247 | master catalog |
| `DRUGS.PHY` | 781 | root drug DB |
| `insert into drgserver (...)` | 7603/8005 | feed→SQL insert |
| `insert into usersourceupdate (...)` | 7608/8010 | sync queue insert |
| `select * from drgserver where silsila` | 7908 | per-pharmacy lookup |
| `insert into wzdrugs ( ` / `update wzdrugs set` / `update wzdrugs2 set` | 720/807/808 | drug-master write |
| `delete from drgserver` / `SELECT top 3000 * FROM usersourceupdate` / `DELETE FROM usersourceupdate WHERE id` | 559/5870/4235 | queue ops |
| `drugeyedash2` | 6208 | dashboard table |

This mirrors the wider finding that even core-table SQL (`insert into titanksasales` line 944, `insert into wzcustomers` 8007, `insert into remotecontrol` 8008…) has 0 refs — **the running app does not load these strings as literals**; the string table documents *behavior*, not current execution.

### The ONLY live drugeye string

`http://www.drugeye.pharorg.com` (idx 7934) — **21 refs**, all URL-building in VB7 module procs + `FormRempteTitan` + `Modzatcasign`. It is an **HTTP web-service call** (concatenated with the sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e`), **not** a file download.

### The real data layer: VB6 record-file I/O (.phy), not SQL

The app reads/writes the drug master through native VB6 fixed-record I/O, not SQL:

- **Primitives:** `OpenFile` / `GetRecOwn4` / `PutRecOwn4` / `DestructRecord` / `Close` — **232 procs**, 98 of which perform record reads.
- **`ModDrgW`** — reads/writes drug-master records (loop 1..10000); field layout: I4 id@0x00, fixed-str15@0x04, fixed-str40@0x22, prices@0x64/0x2C0.
- **`FFFDrugEye`** (drug master window) — `GetRecOwn4`/`PutRecOwn4` on `.phy` records, loop 1..25000.
- **`Files` module** — generic `.phy` loader (`OpenFile` → `GetRecOwn4` → `Close`).
- **`FormImportFromOtherDBI`** — imports records from another DBI `.phy` file (5k/50k loop).
- **`ModDRGEXChange`** — exports drug records to a file via `PutRecOwn4`.

**Data-path diagram (verified):**
```
drugeye.pharorg.com (web service, 21 refs) ──┐
                                              ▼
DRUGS.PHY / fromdrugeye.phy ──► ModDrgW / FFFDrugEye ──► sale screen
(fixed-record GetRecOwn4/PutRecOwn4, loops to 10k/25k)
```

**Caveat:** inline `LitStr` content is truncated in the disassembly, so runtime-constructed SQL cannot be *fully* ruled out — but there is zero evidence for it in the analyzed build.

---

## 10. Business Model

### Free Application
DrugEye is explicitly **free** (مجاني):
- "مجاني وصغير الحجم" (Free and small-size)
- "استمتع بجميع هذه الميزات دون الحاجة إلى دفع أي رسوم" (Enjoy all these features without paying any fees)

### Revenue Strategy
The business model appears to be:
1. **DrugEye is free** — drives adoption of the TITAN ecosystem
2. **TITAN is the paid product** — pharmacy management system with premium features
3. **Pharorg company manufactures drugs** — the parent company produces pharmaceuticals (e.g., Neocleanz Douche)
4. **Investment opportunity** — shares in the company are available at 200 EGP each
5. **Pharmacy federation** — the "سلسلة صيدليات التجمع" (Union Pharmacy Chain) app on Google Play suggests a pharmacy network/loyalty program

### Cross-Promotion
- DrugEye promotes TITAN: "ليه تختار تيتان؟" (Why choose TITAN?)
- TITAN integrates DrugEye: automatic database updates
- Facebook groups create community
- The company produces its own drugs and distributes through its network

---

## 11. International Variants

TITAN supports drug databases for multiple Arab countries:

| Country | Drug Database File | Notes |
|---------|-------------------|-------|
| Egypt | `egypt.phar.phy` | Primary market |
| Saudi Arabia | `drugsksa.phy`, `saudia.phar.phy` | Includes RSD integration |
| Iraq | `drugsiraq.phy`, `iraq.phar.phy` | Separate databases |
| Yemen | `drugsyamen.phy`, `yamen.phar.phy` | Separate databases |
| Bahrain | `bahrein.phar.phy` | — |
| Oman | `oman.phar.phy` | — |
| Sudan | `sudan.phar.phy` | — |
| Libya | `Libya.phar.phy` | — |

Each country has its own drug registry, and TITAN maintains separate `.phy` files for each.

---

## 12. Related Tables and Data Structures

### `titanstock` / `titanksastock`
Local pharmacy stock tracking:
```sql
CREATE TABLE titanksastock (
  drugname nvarchar(100) default '',
  barcode varchar(16) default '',
  price real default '0',
  stock real default 0,
  units int default '0',
  Unitsmall int default '0',
  shape int default '0',
  pharmacyid nvarchar(15) default ''
)
```

### `ChainBuyStore` / `ChainBuyUsers`
Pharmacy chain purchasing system:
```sql
INSERT INTO ChainBuyStore
INSERT INTO ChainBuyUsers
SELECT * FROM ChainBuyStore ORDER BY DrugName DESC
SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%'
```

### `wzdrugs` / `wzgard` / `wzphar` / `wzcustomers`
Warehouse/drug distribution system:
- `wzdrugs` — warehouse drug inventory
- `wzgard` — warehouse transactions (phar, randomid, writer, datee, classy, quant, expire, price, oldstock, costvalue, vatvalue, totalwithvat, typee, drugname)
- `wzphar` — warehouse pharmacies
- `wzcustomers` — warehouse customers (randomid, phar, typee, writer, creditlimit, datee, namee)

### `storediscount`
Discount tracking across pharmacies:
- adress, pharmacyname, storename, drugname, disco, datee, tips

### `titaninn`
Inter-pharmacy transfer system:
- fatid, itemsasstring, datee, source, silsilaid, target

### `titanneed`
Drug demand/request system:
- drugname, quant, datee, sender, target

---

## 13. Key Strings Summary

### DrugEye-Specific Strings
```
'Drug Eye for android'
'Drug Eye for windows'
'Export to drugeye'
'In Drug eye'
'In drug eye'
'created by titan www.pharorg.com/phye'
'db_9ffe55_apifordrugeye'
'db_9ffe55_apifordrugeye_admin'
'drugeye'
'SELECT * FROM drugeyedash2'
'\Files\DB\drugeye-for-titan.phy'
'\Files\DB\drugeye-for-titan.rar'
'\Files\db\drugeye.update.titan.rar'
'\Files\DBI\fromdrugeye.phy'
'\Files\Export\DrugEye'
'\Files\Export\DrugEye\'
'Program Folder\\Files\\Export\\DrugEye if you want to sent it to Drug Eye user'
'http://www.drugeye.pharorg.com'
'http://www.drugeye.pharorg.com/rsd-api/start.aspx'
'http://phycodsystems-001-site12.htempurl.com/Titan3/Us/drugeye.html'
'http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar'
'www.facebook.com/groups/pharorg'
'www.facebook.com/groups/pharorg.phye.users'
'www.pharorg.com'
```

### Drug Data Structure Strings
```
'drugname nvarchar(90) default '''
'Barcode varchar(16) default '''
'PriceNow real default 0'
'shape int default 0'
'Units int default 0'
'Unitsmall int default 0'
'stock real default 0'
'pharmacyid nvarchar(15) default '''
'insert into drgserver (datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport)'
'insert into usersourceupdate (drugname,price,units,localimport,'
```

---

## 14. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DRUGEYE ECOSYSTEM                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ DrugEye       │    │ DrugEye       │    │ DrugEye Online       │  │
│  │ Android App   │    │ Windows App   │    │ (Web Browser)        │  │
│  │ (com.phycod.  │    │               │    │ drugeye.pharorg.com  │  │
│  │  drugeye)     │    │               │    │                      │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────┬───────────┘  │
│         │                    │                       │              │
│         └────────────────────┼───────────────────────┘              │
│                              │                                      │
│                    ┌─────────▼─────────┐                           │
│                    │ MySQL Database     │                           │
│                    │ db_9ffe55_         │                           │
│                    │ apifordrugeye      │                           │
│                    └─────────┬─────────┘                           │
│                              │                                      │
│                    ┌─────────▼─────────┐                           │
│                    │ RSD API Endpoint   │◄──── Saudi SFDA RSD      │
│                    │ rsd-api/start.aspx │      Drug Tracking        │
│                    └───────────────────┘                           │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                     ┌───────────────────┐                           │
│                     │ TITAN.W1 Pharmacy  │                           │
│                     │ Management System  │                           │
│                     └─────────┬─────────┘                           │
│                               │                                     │
│              ┌────────────────┼────────────────┐                   │
│              │                │                │                   │
│     ┌────────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐           │
│     │ FFFDrugEye    │ │ ModDrugEye  │ │ FormDrugeye │           │
│     │ (22 procs)    │ │ (8 procs)   │ │ eUpadteFrom │           │
│     │ Main UI Form  │ │ Business    │ │ (16 procs)  │           │
│     │               │ │ Logic       │ │ Update Form │           │
│     └───────┬───────┘ └──────┬──────┘ └──────┬──────┘           │
│             │                │                │                   │
│     ┌───────▼────────────────▼────────────────▼──────┐           │
│     │                  Local Files                    │           │
│     │  \Files\DB\drugeye-for-titan.phy               │           │
│     │  \Files\DBI\fromdrugeye.phy                    │           │
│     │  \Files\Export\DrugEye\                        │           │
│     │  DRUGS.PHY (auto-updated)                      │           │
│     │  \Files\db\drugeye.update.titan.rar            │           │
│     └────────────────────────────────────────────────┘           │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 15. Conclusions

1. **DrugEye is a free Egyptian drug reference database**, not a price comparison tool or social platform
2. **TITAN and DrugEye share the same developer** (Phycod/Labirdo/Pharorg)
3. **Bidirectional data flow**: TITAN exports drug data to DrugEye; DrugEye provides master drug database updates to TITAN
4. **The `.phy` format** is TITAN's proprietary binary database format (PHYCOD format)
5. **DrugEye has three clients**: Android, Windows, and Web
6. **The MySQL backend** (`db_9ffe55_apifordrugeye`) hosts the drug catalog
7. **DrugEye also serves as an RSD integration proxy** for Saudi Arabia's drug tracking system
8. **Country-specific drug databases** exist for 8+ Arab countries
9. **The business model** is free drug reference driving adoption of the paid TITAN pharmacy management system
10. **The `drugeyedash2` table** suggests analytics/dashboard capabilities on the server side

### 15.1 Verified corrections (2026-08-15, live feed download + p-code disassembly)

- **`drugeye.update.titan.rar` is NOT a RAR archive.** It is a **ROT-4-obfuscated plaintext drug feed** (23,452 records; 1,055,820 bytes; no Rar magic header). The vendor re-publishes it as a static file on the htempurl server (last-modified 2026-08-12).
- **The feed decode is trivial**: shift every letter/digit −4 (wrap into `[\]^`/`:;<=`), keep `$ . , ( ) & - /` and space literal; format `<barcode>x<BRAND>$<product>$<form>$<strength>...x<PRICE>x<QTY>x`. Fully decoded copy: `/tmp/opencode/drugeye.update.titan.decoded.txt`.
- **The documented download→extract→copy-DRUGS.PHY flow is dead code** in the analyzed build: URL, filenames, and all drugeye SQL strings have **0 p-code references** (verified with a corrected 2-byte/4-byte string-index decoder). The only live drugeye string is `http://www.drugeye.pharorg.com` (21 refs, HTTP web-service call).
- **Drug data actually enters through native VB6 fixed-record `.phy` I/O** (`OpenFile`/`GetRecOwn4`/`PutRecOwn4`; 232 procs, 98 record readers) via `ModDrgW`, `FFFDrugEye`, `Files`, `FormImportFromOtherDBI`, `ModDRGEXChange` — **not** SQL, and **not** the ROT-4 feed.
- **For a modern replacement:** treat the decoded feed as a useful *reference catalog* for seeding a Postgres drug table, and design the drug master as explicit SQL tables; do not replicate the vestigial `.rar`/ROT-4/curl download path.
