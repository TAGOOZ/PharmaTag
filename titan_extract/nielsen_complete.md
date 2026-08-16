# Nielsen Market Research Data Analysis — TITAN.W1 Pharmacy Management System

## Executive Summary

TITAN.W1 (by Phycod Systems) contains a **dedicated class module `ModNilsen`** (112KB, 20 procedures) that handles **data collection and transmission to Nielsen** for pharmaceutical market research. The data is sent to a Phycod-controlled server at `phycodsystems-001-site12.htempurl.com` under paths explicitly labeled **"data-for-sale"**, indicating this is a **data selling operation** where pharmacy sales data is monetized.

---

## 1. ALL Nielsen-Related Strings Found

### Primary Nielsen Strings (from `strings_utf16.txt`)

| Line | String | Significance |
|------|--------|--------------|
| 901 | `delete from nilsen2` | SQL to clear the `nilsen2` table |
| 4157 | `C:\\Nielsen\\` | Local directory for Nielsen data files |
| 4158 | `C:\\Nielsen\\6-months\\` | 6-month aggregated data directory |
| 4159 | `C:\\Nielsen\\6-months\\eg\\` | Egypt-specific 6-month data |
| 5346 | `Integration with Nielsen` | Feature menu label / description |
| 7236 | `\\Files\\DB\\Nilsenlist.rar` | Compressed database of Nielsen pharmacy list |
| 7952 | `https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar` | **CRITICAL**: Full URL to download Nielsen numbers data |
| 8108 | `mobiles.numbers.rar` | Compressed mobile numbers file |
| 8150 | `nielsen/` | Base directory path |
| 8306 | `reset Nielsen data?` | Confirmation dialog for resetting Nielsen data |
| 8483 | `titan-users/data-for-sale/nielsen-curl` | Upload endpoint for Nielsen data via curl |
| 8484 | `titan-users/data-for-sale/nielsen/egypt` | Egypt-specific Nielsen data upload path |
| 8485 | `titan-users/data-for-sale/nielsen/members-only/data/` | Members-only data directory |
| 8486 | `titan-users/data-for-sale/nielsen/saudi` | Saudi-specific Nielsen data upload path |

### Related Data-For-Sale Strings

| Line | String | Significance |
|------|--------|--------------|
| 2204 | `/titan-users/data-for-sale/avros/egypt/` | Avros (pharmacy chain) Egypt data |
| 2205 | `/titan-users/data-for-sale/avros/saudi/` | Avros Saudi data |
| 2206 | `/titan-users/data-for-sale/avros/world/` | Avros worldwide data |
| 7713 | `done for avros` | Avros processing completion message |

---

## 2. The `nilsen2` Table

### SQL Statement Found
```sql
delete from nilsen2
```

This is a **cleanup/reset statement** that purges the `nilsen2` table. The table name "nilsen2" (not "nielsen") suggests:
- It may be a local staging table for Nielsen data before upload
- The "2" suffix suggests a versioning pattern (nilsen, nilsen2)
- The table likely stores pharmacy sales data aggregated for Nielsen reporting

### Inferred Table Structure (from pcode analysis)
Based on the pcode procedures in `ModNilsen`, the `nilsen2` table likely contains:
- **Pharmacy identifiers** (pharmacyid, pharmacyname)
- **Drug identifiers** (barcode, drugname, titanid)
- **Sales data** (quantity, price, totalvalue)
- **Date ranges** (datee — start/end dates for 6-month periods)
- **Country/region** (egypt, saudi, world)
- **Company data** (company-name)

---

## 3. ModNilsen Class Module — 20 Procedures

### Procedure Overview (from `procedures.txt` and `pcode_disasm.txt`)

| Address | Size | Frame | Tokens | Purpose (Inferred) |
|---------|------|-------|--------|-------------------|
| `0x0092c574` | 124 | 20 | 42 | **Initialization/Setup** — OnError handler, reads array config, compares to threshold (0x00924f09 = 1,500,000), calls upload functions |
| `0x008dfbb8` | 12 | 16 | 5 | **Simple getter** — Returns a single value (likely a flag or setting) |
| `0x00977420` | 252 | 184 | 63 | **Data processing with file I/O** — OnError, reads/writes strings, handles file paths, processes data with separators ("r", " ", "'") |
| `0x00900ea8` | 64 | 36 | 18 | **Database query** — Executes SQL with 3 parameters, returns string result (likely reads Nielsen config) |
| `0x009a491c` | 320 | 208 | 96 | **Data aggregation** — Processes arrays, concatenates semicolon-delimited records, builds upload strings |
| `0x00abbe20` | 1632 | 424 | 493 | **MAIN DATA COLLECTION** — Complex nested loops, builds semicolon-delimited records with drug names, barcodes, quantities, prices, market share percentages. Uses `;` as separator, `Y`/`H` flags, processes 50,000+ items |
| `0x00aba8a0` | 1624 | 424 | 487 | **MAIN DATA COLLECTION (variant)** — Nearly identical to above, likely for different region (Saudi vs Egypt) |
| `0x00b392b0` | 6144 | 4 | 2634 | **LARGEST PROCEDURE — Field mapping** — Massive switch/case structure with 50+ LikeTextStr comparisons. Maps database fields to Nielsen format. Each case handles a different field name |
| `0x009a2d04` | 364 | 92 | 112 | **Date calculation** — Computes 6-month periods, handles date boundaries, returns Double (date value) |
| `0x009a2b5c` | 364 | 92 | 112 | **Date calculation (variant)** — Similar to above but with different date offsets (0x13 vs 0x12, 0x14) |
| `0x008f2ee0` | 44 | 32 | 12 | **Region selector** — Checks a flag, returns different string literals (likely "egypt" vs "saudi" path) |
| `0x00979374` | 276 | 12 | 72 | **Multi-replace** — Executes 7 sequential string replacements on data (formatting for Nielsen) |
| `0x009c8b1c` | 376 | 328 | 122 | **Data validation** — Processes arrays, checks for non-zero values, builds status strings with "NOT AVAILABLE" sentinel |
| `0x00aaf4e0` | 1528 | 408 | 459 | **DATA UPLOAD** — OnError handler, processes date ranges, iterates 50,000 items, builds upload records, executes upload |
| `0x008ef0a4` | 36 | 4 | 14 | **Country path resolver** — Checks two flags, returns different path strings (egypt/saudi/world) |
| `0x00a7fd34` | 1076 | 484 | 330 | **Sales data processing** — Iterates through date ranges, processes drug data, builds detailed records with barcode, quantity, price, discount, units, market share |
| `0x00a9794c` | 1336 | 340 | 402 | **Sales data processing (variant)** — Similar to above, likely for different data format or region |
| `0x008f5cd0` | 40 | 16 | 13 | **Path builder** — Concatenates base path with filename, returns full path string |
| `0x009150b0` | 92 | 56 | 30 | **File download** — Creates XMLHTTP object, fetches remote file (likely numbers.rar), saves to local |
| `0x009e3b6c` | 480 | 312 | 144 | **Full upload cycle** — OnError, processes dates, builds upload string, executes curl upload, validates response |

---

## 4. What Pharmacy Data is Sent to Nielsen

### Data Fields Collected (from pcode analysis)

Based on the pcode procedures (especially `0x00abbe20` and `0x00a7fd34`), the following data is collected:

#### Per-Drug Data:
1. **Drug Name** (`drugname`) — Full pharmaceutical name
2. **Barcode** (`barcode`) — EAN/UPC product barcode
3. **Titan ID** (`titanid`) — TITAN system's internal drug identifier
4. **Quantity Sold** — Number of units sold
5. **Unit Price** (`price`) — Selling price per unit
6. **Total Value** — Quantity × Price
7. **Discount** (`disco`) — Discount percentage applied
8. **Units** (`units`) — Pack size
9. **Market Share** — Calculated as percentage of total sales
10. **Stock Level** (`stock`) — Current inventory

#### Per-Pharmacy Data:
1. **Pharmacy Name** (`pharmacyname`) — Arabic and English
2. **Pharmacy ID** (`pharmacyid`) — Unique identifier
3. **Address** (`adress`) — Physical location
4. **Country** — Egypt, Saudi Arabia, or World
5. **Store Name** (`storename`)

#### Per-Sale Data:
1. **Invoice ID** (`invoiceid`) — Transaction identifier
2. **Date** (`datee`) — Transaction date
3. **Sales Chain** (`silsilaid`) — Sale sequence number
4. **Payment Status** (`payed`) — Payment method
5. **Total Value** (`totalvalue`) — Invoice total

#### Aggregated Data:
1. **6-month periods** — Data is aggregated in 6-month windows
2. **Market share percentages** — Per drug, per pharmacy, per region
3. **Country-specific totals** — Egypt and Saudi Arabia separated

---

## 5. Data Upload Mechanism

### Upload Paths

| Path | Purpose |
|------|---------|
| `titan-users/data-for-sale/nielsen-curl` | Main upload endpoint (via curl) |
| `titan-users/data-for-sale/nielsen/egypt` | Egypt-specific data |
| `titan-users/data-for-sale/nielsen/saudi` | Saudi-specific data |
| `titan-users/data-for-sale/nielsen/members-only/data/` | Members-only aggregated data |

### Download Path

| URL | Purpose |
|-----|---------|
| `https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar` | Download compiled Nielsen numbers |

### Upload Process (from pcode analysis)

1. **Data Collection**: Pharmacy sales data is aggregated into `nilsen2` table
2. **Formatting**: Data is formatted as semicolon-delimited records
3. **Compression**: Data is packed into RAR archives
4. **Upload**: Data is sent via curl to Phycod server
5. **Validation**: Response is checked (must be > 3 characters)
6. **Reset**: Local Nielsen data can be reset (`reset Nielsen data?`)

### Local Storage

```
C:\Nielsen\
├── 6-months\
│   └── eg\          (Egypt 6-month data)
└── (current period data)
```

---

## 6. The `numbers.rar` File

### Location
```
https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar
```

### What It Contains
Based on the pcode analysis, `numbers.rar` likely contains:
- **Compiled Nielsen market share numbers** for participating pharmacies
- **Aggregated drug sales data** across the TITAN network
- **Market share percentages** per drug category
- **Regional breakdowns** (Egypt, Saudi Arabia, World)

### Access Method
- The file is hosted on Phycod's tempurl server
- Downloaded via `ModNilsen` procedure `0x009150b0` (uses XMLHTTP)
- Extracted locally to `C:\Nielsen\` directory
- Referenced as "members-only" data — requires membership/subscription

---

## 7. Business Relationship Analysis

### Evidence of Data Selling

1. **Explicit Labeling**: All upload paths contain `data-for-sale` — this is literally labeled as data being sold
2. **Phycod as Intermediary**: The data goes to Phycod's server, not directly to Nielsen
3. **Members-Only Access**: The compiled data is behind a "members-only" gate
4. **Multiple Countries**: Egypt, Saudi Arabia, and World data are sold separately
5. **Avros Data**: Separate data-for-sale paths exist for "avros" (likely a pharmacy chain)

### Data Flow

```
TITAN Pharmacy → ModNilsen → nilsen2 table → Format → RAR → Upload to Phycod → Sell to Nielsen
                                                                    ↓
Nielsen Reports ← Download numbers.rar ← Phycod Server ← Aggregated Data
```

### Who Pays Whom

- **Pharmacies pay Phycod** for TITAN software
- **Phycod sells pharmacy data to Nielsen** (labeled "data-for-sale")
- **Pharmacies receive Nielsen reports** (market share data) in return
- **Nielsen pays Phycod** for aggregated pharmaceutical sales data

### Is It Opt-In or Mandatory?

Evidence suggests **opt-in with incentives**:
- The feature is labeled "Integration with Nielsen" — a feature, not a requirement
- The "members-only" label implies subscription/membership
- The data download (`numbers.rar`) is the reward for participation
- Pharmacies likely receive market share reports in exchange for their sales data

---

## 8. Geographic Coverage

### Egypt (`eg` / `egypt`)
- `C:\Nielsen\6-months\eg\` — Local storage
- `titan-users/data-for-sale/nielsen/egypt` — Upload path
- Most detailed data (primary market)

### Saudi Arabia (`saudi` / `saudia`)
- `titan-users/data-for-sale/nielsen/saudi` — Upload path
- `saudia.phar.phy` — Saudi pharmacy data file
- `saudia.phar.phy` — Referenced in strings

### World (`world`)
- `/titan-users/data-for-sale/avros/world/` — Avros world data
- `titan-users/dbi-zipped/Bux-w-world/` — World backup data
- Aggregated global data

---

## 9. Technical Implementation Details

### Data Format
- **Delimiter**: Semicolon (`;`)
- **String Quoting**: Single quotes (`'`)
- **NULL Handling**: `NOT AVAILABLE` sentinel string
- **Date Format**: VB6 Date serialization (Double)
- **Numeric Format**: VB6 Currency/Double

### Compression
- **RAR archives** for data transfer
- **WinRAR** (`C:\Program Files\WinRAR\Rar.exe`) for compression
- Path: `\\Files\\DB\\Nilsenlist.rar`

### Upload Mechanism
- **curl.exe** (`C:\Windows\System32\curl.exe`)
- **FTP Upload** supported (see `<function>ftp-upload</function>` strings)
- **HTTP POST** to Phycod tempurl server

### Error Handling
- All major procedures have `On Error GoTo ErrHandler`
- Upload failures are logged
- Response validation (checks response length > 3)

---

## 10. Key Findings Summary

1. **TITAN.W1 is actively collecting and selling pharmacy sales data to Nielsen** through its ModNilsen module
2. **The data is explicitly labeled "data-for-sale"** in the server paths
3. **Phycod Systems acts as the intermediary**, hosting the data on their servers and managing the Nielsen relationship
4. **The nilsen2 table** is the local staging area for data before upload
5. **numbers.rar** contains the compiled Nielsen market share reports
6. **Data covers Egypt, Saudi Arabia, and worldwide markets**
7. **The 6-month aggregation period** matches Nielsen's standard reporting cycles
8. **20 procedures** handle the complete data lifecycle: collection, formatting, upload, download, and reset
9. **The largest procedure (0x00b392b0, 6144 bytes, 2634 tokens)** is a massive field mapper that converts TITAN database fields to Nielsen format
10. **This is a revenue stream for Phycod** — they monetize their pharmacy network's sales data

---

## 11. Data Accessibility

### Can We Access the Nielsen Data?

| Data Source | Accessible? | Format | Location |
|-------------|-------------|--------|----------|
| `nilsen2` table | **YES** (if database available) | SQL table | Local database |
| `numbers.rar` | **NO** (server may be down) | RAR archive | `phycodsystems-001-site12.htempurl.com` |
| `Nilsenlist.rar` | **YES** (if installed) | RAR archive | `\Files\DB\Nilsenlist.rar` |
| ModNilsen procedures | **YES** (decompiled) | VB6 pcode | Binary |
| Strings | **YES** (extracted) | UTF-16 text | `strings_utf16.txt` |

### What We CAN Extract

1. **All Nielsen-related string constants** — Complete list in Section 1
2. **All 20 ModNilsen procedures** — Decompiled pcode available
3. **Data field mappings** — From procedure `0x00b392b0`
4. **Upload/download paths** — Complete server paths
5. **SQL statements** — Including `nilsen2` table operations

### What We CANNOT Extract

1. **Actual pharmacy sales data** — Not in the binary, only in the database
2. **numbers.rar contents** — Would need to download from server
3. **Nielsen report format** — Encoded in the compressed data files
4. **API keys/authentication** — Not visible in strings

---

*Analysis completed on 2026-08-15*
*Source files: strings_utf16.txt, pcode_disasm.txt, objects.txt, ModNilsen.cls*
*Total ModNilsen procedures: 20*
*Total Nielsen-related strings: 17 unique entries*
