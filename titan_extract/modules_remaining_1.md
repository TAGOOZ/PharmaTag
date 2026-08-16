# TITAN.W1 — Remaining Modules Extraction (22 modules)

> Reverse-engineered from pcode_disasm.txt, strings_utf16.txt, and project_structure.json
> Module type legend: **Module** (.bas), **Class** (.cls)

---

## 1. ModCountries (Module, 24 procs)

**Purpose:** Multi-country configuration layer. Maps country names to numeric IDs, sets country-specific behavior (currency, VAT, tax rules, ZATCA e-invoicing settings). Used to adapt the pharmacy app for different markets.

**Key Procedures:**
| Proc Address | Size | Likely Function |
|---|---|---|
| `0x009c4a04` | 448 | Country-ID lookup — compares country name string to 12+ known values (1..11 IDs), returns `LitI2_Byte` integer IDs. Maps country names → numeric constants |
| `0x0097fe08` | 272 | Country initialization — calls property accessors on a country object, checks `MemLdI2` (country ID range 0–200), loads config |
| `0x009a908c` | 364 | Country settings loader — 5 sequential conditional checks (5 country options), with Arabic string literal `"'D* "` |
| `0x009f00fc` | 592 | Country config setter — 13 sequential calls to set properties (likely: country name, currency, VAT%, date format, language, ZATCA flag, etc.) |
| `0x0093307c` | 156 | Country feature checker — 11 sequential conditional checks (feature flags per country) |
| `0x00949448` | 168 | Country name list builder — concatenates Arabic strings: `"'DG1)-"`, `"'DDJH(J)-"`, `"'G3CF/1J)-"`, `"(FJ "`, `"(H139J/-"`, `"'3JH7-"` (Arabic country names) |
| `0x0092c404/0x0092c344/0x0092b504` | 140 each | Country-specific sub-routines — 8 sequential calls each (likely 3 similar country-specific config loaders) |
| `0x0092c1ac` | 116 | Path builder — sets `_Property_ = (_MethodCall_ & "\\")` (builds file path with country prefix) |
| `0x008e3ab8..0x008e36bc` | 20 each (×10) | Stub/singleton getters — tiny 9-token procs, likely return cached country properties |

**Country Names Detected (from string at 0x00949448):**
- Arabic country names encoded in VB6 Unicode — likely: Saudi Arabia, Kuwait, Bahrain, UAE, Jordan, Iraq, Egypt, Yemen, Oman, Qatar, Lebanon, Syria

**Strings:**
- `"Saudia"`, `"KSA"`, `"Egypt"`, `"Iraq"`, `"Oman"`, `"Qatar"`
- `"correct your country"`, `"Invalid country ID format."`, `"Export to current country is forbidden"`
- `http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso` (SOAP country info service)

**Tables:** Likely a `companies` table with `country` column

---

## 2. ModOneFile (Module, 23 procs)

**Purpose:** "One File" export/import feature — bundles all pharmacy data (drugs, sales, purchases, customers, settings) into a **single `.phy` file** for data transfer, backup, or migration between installations. Opposite of multi-file backup.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00b1e378` | 4124 (1129) | **Main export routine** — largest proc in module, serializes all data tables into one file |
| `0x00b0ed64` | 3440 (984) | **Main import routine** — parses single file back into database |
| `0x00ac2500` | 1800 (510) | Data chunk writer — serializes table data with column headers |
| `0x00accebc` | 1932 (567) | Data chunk reader — deserializes table data from chunks |
| `0x00aa4618` | 1524 (459) | File header builder — writes metadata (pharmacy name, date, version, country) |
| `0x00a25914` | 768 (240) | Table schema writer |
| `0x00a1f2cc` | 760 (227) | Table schema reader |
| `0x00a01530` | 644 (193) | Data validation |
| `0x009fe0e4` | 576 (172) | Compression/packing |
| `0x009ed868` | 576 (183) | Decompression/unpacking |
| `0x009d2a74` | 488 (129) | File integrity check |
| `0x009be6a0` | 428 (113) | Chunk boundary handler |
| `0x009b6ed4` / `0x009b7a14` | 412 each | Duplicate table processors |
| `0x009a1428` | 352 (106) | File format detector |
| `0x00979c7c` | 236 (64) | Init/config loader |
| `0x00960a30` | 188 (52) | Init/config loader |
| `0x00948fa4` | 160 (47) | Init/config loader |
| `0x009331f8` | 128 (38) | Progress reporter |
| `0x0093f7b0` | 160 (42) | Cleanup handler |
| `0x0090088c` | 60 (17) | Simple wrapper |
| `0x008dd9c0` | 12 (4) | Empty/stub |

**Strings:**
- `"Export to one file"`, `"Only one file can be sent."`

**File format:** Single `.phy` file containing all pharmacy data serialized as text chunks

---

## 3. ModFiles (Module, 20 procs)

**Purpose:** Core file I/O abstraction layer for the `.phy` file format. Provides open, close, read, write, and path resolution for all Titan data files. All other modules use ModFiles for file access.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x0090d5f8` | 80 (27) | Open file for reading |
| `0x0090e0a8` | 80 (27) | Open file for writing |
| `0x00911818` | 84 (20) | File path resolver — resolves relative paths like `\\Files\\DBI\\*.phy` |
| `0x008e2e38` | 16 (5) | File exists check |
| `0x008e7f6c` | 24 (7) | File size getter |
| `0x00912de0` | 100 (32) | Read/write line operations |
| `0x008f67cc` | 44 (15) | Close file |
| `0x008f6834` | 44 (15) | Flush file |

**Also `Files` module (41 procs):** Higher-level file operations on top of ModFiles.

**Strings:** Extensive use of `.phy` file extensions:
- `\\Files\\DBI\\*.phy` — database index files
- `\\Files\\DB\\*.Phy` — database files
- `\\Files\\DBI\\orooda.phy`, `daily-manual.phy`, `tar.phy`, etc.

**File types:**
- `.phy` — Titan native data files
- `.DB` / `.DBI` — Database and index directories

---

## 4. ModUpto352 (Module, 18 procs)

**Purpose:** Version migration module — handles schema upgrades from older versions up to version 3.52. Contains ALTER TABLE statements, column additions, data transformations, and schema validation for each migration step.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00aada08` | 1456 (513) | Migration step A — adds columns, transforms data |
| `0x00aa9888` | 1432 (504) | Migration step B — similar column migration |
| `0x00a9f5d8` | 1328 (468) | Migration step C |
| `0x00ab38d0` | 1524 (543) | Migration step D — largest, most complex migration |
| `0x00aab930` | 1464 (520) | Migration step E |
| `0x009cd904` | 484 (154) | Migration orchestrator — sequences all steps |
| `0x00a9a864` | 1320 (467) | Migration step F |
| `0x00974db0` | 244 (71) | Pre-migration validation |
| `0x008fd474` | 68 (15) | Migration flag check |
| `0x00a009cc` | 564 (166) | Column existence checker — `IF NOT EXISTS (SELECT ... FROM INFORMATION_SCHEMA)` |
| `0x00a323c8` | 696 (241) | Data backfill — populates new columns from old data |
| `0x00a22018` | 636 (220) | Data backfill variant |
| `0x00a6a7e0` | 1004 (365) | Schema diff engine — compares current DB to target schema |
| `0x00a2be7c` | 668 (229) | Post-migration validation |
| `0x009aac40` | 376 (109) | Version number updater |
| `0x00912d44` | 96 (34) | Migration log writer |

**Strings:**
- `" 352"` (version number), `"تحديث 352"` (Arabic: "Update 352")
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/upgrade.html`
- `"upgrade"`

**Pattern:** Multiple large procs (1300–1500 bytes each) = sequential migration steps with SQL ALTER/UPDATE statements

---

## 5. ModTamin (Module, 15 procs)

**Purpose:** **Insurance company integration** (تأمين = Tamin/insurance in Arabic). Manages insurance company data, patient insurance coverage, drug pricing for insured patients, and printing insurance-specific invoices.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00a036b8` | 652 (213) | Main insurance data loader — loads insurance company config |
| `0x009ddd84` | 492 (125) | Insurance price calculator — calculates patient copay vs. insurance coverage |
| `0x00a3444c` | 812 (236) | Insurance invoice printer — generates insurance-specific invoice format |
| `0x0094cae4/0x0094cccc` | 172 each | Symmetric pair — likely load/save insurance settings |
| `0x0093e7ec/0x0093df54` | 152 each | Symmetric pair — likely insurance company list operations |
| `0x00956ed8/0x00955e58` | 188 each | Symmetric pair — likely insurance report generators |
| `0x00934128` | 140 | Insurance validation |
| `0x008f4a5c` | 52 | Insurance flag checker |
| `0x0092bbbc` | 132 | Insurance coverage lookup |
| `0x00904bcc` | 76 | Insurance discount calculator |
| `0x00951bd0` | 180 | Insurance report formatter |

**Strings:**
- `"Printing for insurance companies"`, `"insurance"`
- `"اضافة امر فلترة في تقرير عملاء شركة التأمين"` (Arabic: "Add filter command in insurance company customers report")

**Related Forms:** `FormAmilTamin` (16 procs), `FormAmilTamin2` (10 procs) — Insurance employee work screens

---

## 6. ModMobile (Module, 9 procs)

**Purpose:** Mobile connectivity module — handles communication with a mobile companion app (likely Android). Manages mobile number registration, cloud sync, data upload/download to/from mobile devices, and SMS-like features.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00af3764` | 2612 (691) | **Main mobile sync** — largest proc, handles full data exchange with mobile |
| `0x00a2bb84` | 788 (278) | Mobile registration — registers mobile number with cloud |
| `0x009f609c` | 588 (161) | Mobile data uploader |
| `0x009c5c40` | 440 (126) | Mobile data downloader |
| `0x009bdce4` | 408 (112) | Mobile status checker |
| `0x009a1268` | 324 (97) | Mobile config loader |
| `0x0096d0ac` | 216 (69) | Mobile number validator |
| `0x0091bac0` | 104 (32) | Mobile connection checker |
| `0x009142b0` | 96 (35) | Mobile cleanup |

**Strings:**
- `"Mobile"`, `"Mobile number for cloud connectivity"`, `"Mobile number for current cloud connectivity"`
- `"Upload Mobile"`, `"Upload to mobile"`
- `"Input mobile number"`, `"Input patient mobile number"`, `"Custmer mobile"`
- `"Wrong mobile Id"`, `"data in this mobile numer not present"`
- `'/titan-users/allinone/mobiles/'`, `'/titan-users/titan-mobile/files/'`
- `"xo-mobile.txt"`, `"mobiles.numbers.rar"`

**Cloud URLs:** `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/mobiles/`

---

## 7. ModWMI (Module, 12 procs)

**Purpose:** **Windows Management Instrumentation** hardware fingerprinting — collects BIOS serial number, CPU info, OS version, and network adapter MAC address for machine identification, license binding, and anti-piracy.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x009772e0` | 264 (81) | BIOS serial number reader — queries `Win32_BIOS` |
| `0x0094e9a0` | 156 (48) | CPU info reader — queries `Win32_Processor` |
| `0x00971060` | 228 (72) | OS version reader — queries `Win32_OperatingSystem` |
| `0x00948570` | 144 (42) | Network adapter reader — queries `Win32_NetworkAdapter` |
| `0x0096847c` | 228 (70) | Process checker — queries `Win32_Process` for running processes |
| `0x0097fcb0` | 276 (91) | **Hardware fingerprint builder** — combines all hardware IDs into unique machine key |
| `0x00932c70` | 140 (45) | WMI query executor — generic WMI query runner |
| `0x008fbfac` | 44 (12) | WMI connection initializer |

**Strings:**
- `"Select * from Win32_BIOS where PrimaryBIOS = true"`
- `"Select * from Win32_Processor"`
- `"Select Name from Win32_Process Where Name = '"`
- `"SELECT * FROM Win32_NetworkAdapter WHERE NetEnabled = True"`
- `"select * from Win32_OperatingSystem where Primary=true"`
- `"SerialNumber"`, `"deviceSerialNumber"`
- `"CPU : "`

**Usage:** License enforcement — hardware fingerprint tied to activation key

---

## 8. ModTranslator (Module, 5 procs)

**Purpose:** Language translation system — translates UI strings between Arabic and English. Works alongside ModEnglishtoArabic for bidirectional translation.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00b09cac` | 3244 (833) | **Main translation dictionary** — maps 800+ English terms to Arabic |
| `0x00b082c4` | 3200 (822) | **Reverse translation dictionary** — maps Arabic back to English |
| `0x0097d058` | 280 (74) | Translation lookup — finds translation by key |
| `0x0097ec90` | 280 (74) | Translation lookup (duplicate/variant) |
| `0x00ab8cd0` | 1740 (447) | Bulk translator — translates arrays of strings |

**Strings:**
- `"Translation"`, `"language Settings"`
- `"this means that setup of language in windows is not set to arabic"`
- `"<html lang='ar'>"`, `"accept-language"`

---

## 9. ModEnglishtoArabic (Module, 7 procs)

**Purpose:** English-to-Arabic text conversion — larger than ModTranslator, contains massive lookup tables for converting English pharmaceutical terms, drug names, and UI labels to Arabic. Also handles RTL text layout.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00b09cac` | 3244 (833) | **English→Arabic dictionary** (shared with ModTranslator?) |
| `0x00b082c4` | 3200 (822) | **Arabic→English dictionary** |
| `0x00ae3a10` | 2304 (830) | **Drug name translator** — maps English drug names to Arabic |
| `0x00ab8cd0` | 1740 (447) | UI string translator |
| `0x009b0bd4` | 380 (112) | Text direction handler (RTL/LTR) |
| `0x0097d058` | 280 (74) | Lookup helper |
| `0x0097ec90` | 280 (74) | Lookup helper |

**Strings:**
- `"Arabic Transparent"`, `"Arabic name"`, `"Name Arabic"`, `"NameArabic"`, `"NameEnglish"`
- `"English Horn"`, `"for windows xp click 'advanced' then select 'Arabic'"`
- `"this means that setup of language in windows is not set to arabic"`

---

## 10. ModFlexWheel (Module, 6 procs)

**Purpose:** **FlexGrid mouse wheel scrolling** — enables mouse wheel scroll support for the VB6 MSFlexGrid control (which doesn't natively support it). Works with the FLXMod module (55 procs) which provides comprehensive FlexGrid customization.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x0091fd50` | 124 (45) | Wheel event handler — intercepts `WM_MOUSEWHEEL` messages |
| `0x00909df0` | 88 (28) | Scroll position calculator |
| `0x00984254` | 292 (105) | **Main scroll implementation** — handles vertical scroll of FlexGrid |
| `0x008f6df0` | 56 (19) | Grid row counter |

**Related: FLXMod** (55 procs) — Comprehensive FlexGrid helper: column sizing, row coloring, cell formatting, search, filter, sort, print, and export.

---

## 11. ModTafqit (Module, 4 procs)

**Purpose:** **Number-to-words conversion** (تقطيع = Tafqit in Arabic) — converts numeric amounts to Arabic/English words for invoice printing. Essential for formal Arabic financial documents.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00ae2780` | 2312 (703) | **Main Arabic number-to-words** — largest proc, handles Arabic grammar for millions/billions |
| `0x00ad1804` | 2060 (555) | **English number-to-words** — English equivalent |
| `0x00a5736c` | 1000 (289) | Currency formatter — adds currency name (ريال, جنيه) after number |
| `0x00966410` | 240 (65) | Helper — handles decimal/fraction part (and half cents) |

---

## 12. ModOrood (Module, 3 procs)

**Purpose:** **Promotions/offers system** (عروض = Orood in Arabic) — manages buy-X-get-Y discount offers, quantity-based pricing, and promotional pricing rules.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x009f730c` | 588 (216) | **Main offer calculator** — applies promotional rules to invoice lines |
| `0x0093d344` | 144 (45) | Offer rule loader — reads offer definitions from `orooda.phy` |
| `0x0093c588` | 140 (44) | Offer validation — checks if item qualifies for offer |

**Strings:**
- `"OroodA loading .."`, `\\Files\\DBI\\orooda.phy`
- `"Item with offers"`, `"offers"`, `"عروض"`, `"قوائم العروض"` (Offer lists)
- `"ادخل خصم العرض"` (Enter offer discount), `"ادخل كمية العرض"` (Enter offer quantity)
- `"ادخل عدد الوحدات الذي سيستفيد من خصم العرض"` (Enter units that benefit from offer discount)
- `"امكانية عمل عروض علي بعض الاصناف مثلا اذا تم بيع عدد معين من الوحدات يتم خصم رقم معين"` (Create offers on items: sell X units → get Y discount)
- `"سيتم الان تطبيق الخصومات والعروض علي الفاتورة الحالية"` (Applying discounts and offers to current invoice)

**File:** `\\Files\\DBI\\orooda.phy` — offers database

---

## 13. ModStockTest (Module, 4 procs)

**Purpose:** Stock/inventory testing and validation — performs stock reconciliation checks, verifies stock quantities against transactions, and generates stock test reports.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00a1c234` | 652 (207) | **Main stock test** — runs comprehensive stock validation |
| `0x0095070c` | 172 (56) | Stock difference calculator |
| `0x00998204` | 280 (79) | Stock test report generator |
| `0x009dfe20` | 524 (143) | Stock audit trail checker — compares physical vs. system stock |

---

## 14. ModDailyManual (Module, 6 procs)

**Purpose:** Manual daily operations — handles manual journal entries, manual stock adjustments, and manual financial corrections that bypass the normal automated workflow.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x009203f8` | 108 (34) | Manual entry processor A |
| `0x0091f3d8` | 108 (34) | Manual entry processor B |
| `0x00936a14` | 132 (39) | Manual stock adjuster |
| `0x00936394` | 132 (39) | Manual financial adjuster |
| `0x0090cc18` | 92 (35) | Manual entry validator |
| `0x00913cbc` | 104 (37) | Manual entry printer |

**Strings:**
- `"DailyManual2 loading .."`, `"Done for ReloadDailyManual"`
- `"Add an item by Manual search"`, `"Manual adjustment report"`
- `"Manually resetting the Vat value in old invoices"`
- `"Needs - Manual system"`
- `\\Files\\DBI\\daily-manual.phy`, `\\Files\\DBI\\daily-manual-2.phy`

**Related Forms:** `FormDailyManual` (6 procs), `FormDailyManual2` (5 procs)

---

## 15. ModDailyQuiod (Module, 2 procs)

**Purpose:** **Daily closing/quietus** (quit/close = Quiod) — end-of-day reconciliation that totals all sales, calculates cash drawer, generates daily summary, and closes the business day.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x0093f5e4` | 148 (42) | Daily close processor — totals sales/purchases for the day |
| `0x00934920` | 140 (45) | Daily summary generator — generates end-of-day report |

**Related Form:** `FormDailyQuiod` (16 procs) — Full daily closing interface

---

## 16. Mod5Years (Module, 6 procs)

**Purpose:** **5-year data archival** — archives old pharmacy data (older than 5 years) into compressed/serialized format, with ability to restore and query archived data. Handles long-term data retention.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x009b8e98` | 372 (107) | Archive processor — identifies and moves data older than 5 years |
| `0x009af9b4` | 332 (90) | Archive compressor — compresses archived records |
| `0x009c05ec` | 416 (143) | Archive restorer — restores archived data on demand |
| `0x0099773c` | 316 (106) | Archive query — queries archived data without full restore |
| `0x009d0350` | 396 (120) | Archive report — generates archive status report |
| `0x0091608c` | 92 (29) | Archive flag checker — checks if data is archived |

**Strings:**
- `"Sorry i have served you for more than 45 years ,thats enough :("` (humorous age limit message)
- `"Import the prices from old data"`

---

## 17. ModFarWay (Module, 4 procs)

**Purpose:** **Remote pharmacy branch synchronization** (Far Way = far-away branch) — syncs data between a main pharmacy and remote/branch locations using file-based exchange. The "FarWay" branch runs a separate instance (`Titanfary.exe`) and exchanges data files.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00945524` | 176 (61) | Connection checker — checks if remote branch is online |
| `0x00a033d0` | 624 (205) | **Data syncer** — sends/receives data files to/from remote branch |
| `0x00ab02b0` | 1620 (523) | **Main sync engine** — full bidirectional data exchange (largest proc) |
| `0x00975568` | 272 (90) | Sync status reporter |

**Strings:**
- `'Files\\FarWay\\Titanfary.exe'` — remote branch executable
- `\\Files\\FarWay\\FarData\\` — sync data directory
- `\\Files\\FarWay\\FarData\\FromMain\\` — data from main to branch
- `\\Files\\FarWay\\FarData\\ToMain\\Inn\\` — purchase data from branch to main
- `\\Files\\FarWay\\FarData\\ToMain\\Oot\\` — sales data from branch to main
- `\\Files\\FarWay\\i-am-runing.txt` — heartbeat/online indicator

**Architecture:** File-based master-slave sync (FromMain/ToMain directories)

---

## 18. ModDRGEXChange (Module, 4 procs)

**Purpose:** **Drug exchange rate** — manages exchange rates between different drug units/packaging (e.g., box→strip→tablet conversions) and possibly multi-currency drug pricing. The "EXChange" likely refers to unit exchange rates, not currency.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x009894fc` | 220 (69) | Exchange rate loader |
| `0x00a3f0c0` | 824 (254) | **Main exchange calculator** — converts between units |
| `0x00a085fc` | 580 (182) | Exchange rate updater |
| `0x009c0218` | 444 (163) | Exchange rate validator |

**Strings:** `"exchangeRate":` (JSON field name in cloud API)

---

## 19. ModMergeBarcodes (Module, 15 procs)

**Purpose:** **Barcode merging/unification** — detects and merges duplicate barcodes, links multiple barcodes to the same drug, and manages the "similar barcode" database. Critical for pharmacies that receive drugs with different barcodes from different suppliers.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00a2a350` | 752 (229) | **Main merge engine** — merges duplicate barcode records |
| `0x00a3044c` | 772 (240) | **Merge undo** — reverses a merge operation |
| `0x00a486d0` | 908 (280) | **Barcode similarity finder** — finds barcodes that differ by 1-2 digits |
| `0x009f3bf4` | 568 (171) | Barcode relationship manager — links barcodes to drug IDs |
| `0x0097c2fc` | 280 (95) | Barcode validator |
| `0x009fb32c` | 596 (188) | Barcode history tracker — tracks merge history |
| `0x00988cb4` | 284 (97) | Barcode report generator |
| `0x0092633c` | 76 (22) | Quick barcode lookup |
| `0x0092a5f4` | 124 (42) | Barcode adder |
| `0x00958d0c` | 200 (54) | Barcode remover |
| `0x0093fbf8/0x0093f178` | 136 each | Symmetric pair — barcode list operations |
| `0x008f8478` | 44 (13) | Simple check |
| `0x008f85c4` | 52 (17) | Simple utility |
| `0x008fc720` | 48 (14) | Simple utility |

**Related Form:** `FormMoreBarcodes` (8 procs) — Multi-barcode management UI

---

## 20. ModDisease (Class, 6 procs)

**Purpose:** **Disease/condition database** — manages a catalog of medical diseases and their drug contraindications. When a prescription is entered, the system checks if any drug is contraindicated for the patient's recorded conditions.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00b23780` | 4340 (1204) | **Main disease database** — largest proc, contains all disease definitions and drug-disease contraindications |
| `0x00a47344` | 920 (280) | Disease-drug contraindication checker |
| `0x00997d7c` | 320 (100) | Disease list loader |
| `0x0093686c` | 124 (40) | Disease search |
| `0x0092bc68` | 112 (36) | Disease info formatter |
| `0x008dcc84` | 4 (3) | Empty/stub |

**Strings:**
- `"All Disease"`, `"Heart Disease"`, `"Heart Diseases"`, `"Kidny Disease"`
- `"Parkinson's disease.Anti-Muscarinic"`, `"Parkinson's disease.Dopamine agonist"`, `"Parkinson's disease.MAO-B inhibitor"`
- `"Antirheumatic Agent.Wilson's disease.Antidote Chelating Agent"`
- `"Analgesic&Anti-inflamatory Agents->Modify,Supress Rhaumatic Disease"`
- `"المرضي"` (Patients), `"بيانات المرضي"` (Patient data)
- `"ربما يكون في هذه الوصفة ما يحظر استخدامه لمرضي الفشل الكلوي"` (This prescription may contain something contraindicated for kidney failure patients)

**Related Forms:** `FormMarid` (5 procs), `FormMaridData` (15 procs), `FormMaridFat` (4 procs)

---

## 21. ModDDI (Class, 4 procs)

**Purpose:** **Drug-Drug Interaction** checker — loads a drug interaction database from `DDI.Phy` and checks prescriptions for potentially dangerous drug combinations. Alerts the pharmacist when interacting drugs are prescribed together.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x00b13644` | 3636 (1194) | **Main DDI engine** — largest proc, loads and queries the interaction database |
| `0x00a679d8` | 1044 (302) | Interaction checker — checks a pair of drugs for interactions |
| `0x0094c9f8` | 180 (48) | DDI report formatter |
| `0x00927b3c` | 116 (36) | DDI database initializer |

**Strings:**
- `'\\Files\\DB\\DDI.Phy'` — drug interaction database file
- `'التفاعلات الدوائية الدوائية'` (Drug-drug interactions)
- `"لان هذه الشاشة هي شاشة تفاعلية بين المريض والصيدلي"` (This screen is interactive between patient and pharmacist)

**Related Form:** `FormDrugDrug` (22 procs) — Drug interaction checking UI

---

## 22. ModPeInter (Class, 4 procs)

**Purpose:** **Patient interaction checker** (PeInter = Patient Interaction) — checks drug prescriptions against patient-specific data: allergies, conditions (via ModDisease), and existing medications. Broader than ModDDI (which only checks drug-drug); PeInter checks drug-patient compatibility.

**Key Procedures:**
| Proc Address | Size (tokens) | Likely Function |
|---|---|---|
| `0x009afb98` | 360 (117) | **Main patient interaction engine** — checks drug against patient profile |
| `0x0098747c` | 272 (89) | Patient allergy checker |
| `0x009702cc` | 228 (69) | Patient condition checker |
| `0x008ea35c` | 28 (9) | Empty/stub |

**Note:** PeInter is a **Class** (not Module), suggesting it's instantiated per-patient — each patient gets their own PeInter object that holds their allergy/condition profile and checks prescriptions against it.

---

## Summary Table

| # | Module | Type | Procs | Purpose |
|---|---|---|---|---|
| 1 | ModCountries | Module | 24 | Multi-country configuration (KSA, Egypt, Iraq, etc.) |
| 2 | ModOneFile | Module | 23 | Single-file export/import for data transfer |
| 3 | ModFiles | Module | 20 | Core file I/O for .phy format |
| 4 | ModUpto352 | Module | 18 | Version migration to v3.52 |
| 5 | ModTamin | Module | 15 | Insurance company integration |
| 6 | ModMobile | Module | 9 | Mobile app connectivity & cloud sync |
| 7 | ModWMI | Module | 12 | Hardware fingerprinting (WMI queries) |
| 8 | ModTranslator | Module | 5 | Arabic↔English UI translation |
| 9 | ModEnglishtoArabic | Module | 7 | English→Arabic text conversion |
| 10 | ModFlexWheel | Module | 6 | Mouse wheel support for FlexGrid |
| 11 | ModTafqit | Module | 4 | Number-to-words (Arabic/English) |
| 12 | ModOrood | Module | 3 | Promotional offers/discounts |
| 13 | ModStockTest | Module | 4 | Stock validation & reconciliation |
| 14 | ModDailyManual | Module | 6 | Manual daily adjustments |
| 15 | ModDailyQuiod | Module | 2 | End-of-day closing |
| 16 | Mod5Years | Module | 6 | 5-year data archival |
| 17 | ModFarWay | Module | 4 | Remote branch sync |
| 18 | ModDRGEXChange | Module | 4 | Drug unit exchange rates |
| 19 | ModMergeBarcodes | Module | 15 | Duplicate barcode merging |
| 20 | ModDisease | Class | 6 | Disease database & contraindications |
| 21 | ModDDI | Class | 4 | Drug-drug interaction checker |
| 22 | ModPeInter | Class | 4 | Patient-drug interaction checker |
