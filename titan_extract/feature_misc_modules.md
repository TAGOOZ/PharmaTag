# TITAN.W1 — Miscellaneous Auxiliary Modules (وحدات متنوعة)

**Project:** TITAN.W1 (Phye.exe) — VB6 P-Code Pharmacy Application
**Scope:** The "catch-all" feature doc for auxiliary support modules that power core sales, purchasing, billing, printing, migration and multi-market behavior. These modules are cross-cutting: most are invoked from the main sales/purchases screens (FFFStartUp/FFFOutPut/FFFInPut) rather than owning their own forms.

| # | Module | Type | Procs | Section |
|---|--------|------|-------|---------|
| 1 | ModOrood | Module | 3 | Offers & promotions |
| 2 | ModDisease | Class | 6 | Disease contraindications |
| 3 | ModDDI | Class | 4 | Drug-drug interactions |
| 4 | ModPeInter | Class | 4 | Patient–drug interaction |
| 5 | ModTafqit | Module | 4 | Amount-to-words |
| 6 | ModTranslator | Module | 5 | UI translation |
| 7 | ModEnglishtoArabic | Module | 7 | English→Arabic conversion |
| 8 | ModMobile | Module | 9 | Mobile companion sync |
| 9 | ModCountries | Module | 24 | Country/market config |
| 10 | ModAppType | Module | 9 | App type config |
| 11 | ModColors | Module | 3 | Color theme |
| 12 | ModScreen | Module | 3 | Screen/DPI handling |
| 13 | ModFlexWheel | Module | 4 | FlexGrid mouse wheel |
| 14 | ModOneFile | Module | 23 | Single-file export/import |
| 15 | ModFiles / Files | Module | 20 / 41 | `.phy` file I/O |
| 16 | ModReBuild | Module | 14 | DB schema rebuild |
| 17 | ModSQL | Module | 13 | SQL abstraction |
| 18 | VB7 | Module | 42 | VB6 compat layer |
| 19 | ModMergeBarcodes | Module | 15 | Barcode merge/unify |
| 20 | ModStockTest | Module | 4 | Stock reconciliation |
| 21 | Mod5Years | Module | 6 | 5-year archival |
| 22 | ModDRGEXChange | Module | 4 | Drug unit exchange |
| 23 | ModAccFreeOne | Module | 19 | Free accounting/activation |

Sources: `modules_gap_1.md`, `modules_remaining_1.md`, `config_complete.md`, `ui_complete.md`, `schema_complete.sql`, `pcode_strings.py`, `strings_utf16.txt`, `strings_readable.txt`.

---

## 1. Offers & Promotions — ModOrood (عروض)

**Purpose:** Buy-X-get-Y promotional engine. Lets the pharmacist attach quantity-based promotional discounts to individual items; when an invoice sells enough units of an offer item, a fixed/per-unit discount is applied automatically. Driven from the drug edit screen (`شاشة تعديل بيانات الادوية`).

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main offer calculator | `0x009f730c` | 588 | Applies promotional rules to invoice lines; filters `and master = N` (`strings_utf16.txt:1279`) |
| Offer rule loader | `0x0093d344` | 144 | Loads offer definitions from `\Files\DBI\orooda.phy` |
| Offer validation | `0x0093c588` | 140 | Checks whether an item qualifies for an active offer |

**Workflow**
1. On drug-card edit, the pharmacist defines an offer: threshold quantity + offer discount (see strings below).
2. On invoice save/refresh, ModOrood scans invoice lines for items flagged as offer items (`اصناف عليها عروض`).
3. If the sold quantity meets the offer quantity, the offer discount is applied on top of (or instead of) normal sale discounts.
4. Confirmation message shown: "سيتم الان تطبيق الخصومات والعروض علي الفاتورة الحالية اذا كانت تحتوي علي اصناف عليها عروض" (discounts/offers will now be applied to the current invoice if it contains offer items) — `strings_utf16.txt:11711`.

**Fields / data captured** (offer rule, stored in `orooda.phy`):
- `Item with offers` flag on drug card
- Offer discount (خصم العرض)
- Offer quantity (كمية العرض)
- Number of units that benefit from the offer discount (عدد الوحدات الذي سيستفيد من خصم العرض)

**Side-effects:** Applies discount amount to invoice lines → reduces sales totals, affects VAT base on discounted items (offer discount participates in discount flow alongside ModDisc). No stock side-effect.

**Pricing + VAT:** Discount is a value deducted per qualifying unit; VAT recomputed on the discounted net when VAT-enabled items are discounted (`Apply a sale discount for tax items`).

**Business rules**
- Offer only fires when invoice quantity ≥ offer quantity.
- Rule definition: "امكانية عمل عروض علي بعض الاصناف مثلا اذا تم بيع عدد معين من الوحدات يتم خصم رقم معين" (create offers on some items, e.g. sell X units → discount Y) — `strings_utf16.txt:10453`.
- Prompts: `ادخل خصم العرض` (enter offer discount, `:9176`), `ادخل كمية العرض` (enter offer quantity, `:9259`), `ادخل عدد الوحدات الذي سيستفيد من خصم العرض` (`:9233`).
- Offer applicability respects `master` flag filter (`and master = N`), i.e. offers may be scoped to master/pharmacy records.

**Tables:** `\Files\DBI\orooda.phy` (offer definitions file). Load message: `OroodA loading ..` (`:5839`).

**UI strings:** `عروض` (`:11966`), `قوائم العروض` (offer lists, `:12220`), `اصناف عليها عروض` (items with offers, `:9517`), `عروض الاسعار` (price offers, `:11967`).

**Related forms:** `FormOrood1` (7 procs, "اورود", stock items with offers).

---

## 2. Disease & Drug Interactions — ModDisease, ModDDI, ModPeInter

### 2.1 ModDisease (Class) — disease database & contraindications

**Purpose:** Maintains a medical disease catalog and drug–disease contraindication knowledge. At sale time the system warns if a prescribed drug is contraindicated for a patient's recorded conditions (e.g. kidney failure).

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main disease database | `0x00b23780` | 4340 | 132 strings — disease definitions + contraindication rules |
| Disease–drug contraindication checker | `0x00a47344` | 920 | 23 strings — checks drug vs patient conditions |
| Disease list loader | `0x00997d7c` | 320 | loads disease list (8 strings) |
| Disease search | `0x0093686c` | 124 | name search |
| Disease info formatter | `0x0092bc68` | 112 | display formatting |
| Stub | `0x008dcc84` | 4 | placeholder |

**Knowledge categories detected** (`strings_utf16.txt`):
- `All Disease`, `Heart Disease(s)`, `Kidny Disease` (`:3834`, `:5195-5196`, `:5450`)
- `Parkinson's disease.Anti-Muscarinic / .Dopamine agonist / .MAO-B inhibitor` (`:5910-5913`)
- `Antirheumatic Agent.Wilson's disease.Antidote Chelating Agent` (`:4009`)
- `Analgesic&Anti-inflamatory Agents->Modify,Supress Rhaumatic Disease` (`:3864`)
- `Warfarin+piroxicam Potential for serious bleed` (interaction hint in main proc `0x00b23780`)

**Business rules**
- Warning when prescription may be forbidden for kidney-failure patients: "ربما يكون في هذه الوصفة ما يحظر استخدامه لمرضي الفشل الكلوي لكن لم يتمكن تيتان من كشفها" (`:11527-11528`).
- Pharmacological field defaults to "كل الامراض" (all diseases); failure to find a match resets the pharmacology field back to "all diseases" (`:9334`).
- Patient identified by national ID (الرقم القومي) because it is unique for life — `:13363`.

**Related forms:** `FormMarid` (5), `FormMaridData` (15, بيانات المرضي), `FormMaridFat` (4, فواتير المريض).

### 2.2 ModDDI (Class) — drug–drug interaction checker

**Purpose:** Loads a drug-interaction knowledge base and flags dangerous combinations on a prescription; shows an interactive warning screen between patient and pharmacist.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main DDI engine | `0x00b13644` | 3636 | 59 strings — loads/queries interaction DB |
| Interaction checker | `0x00a679d8` | 1044 | checks a drug pair |
| DDI report formatter | `0x0094c9f8` | 180 | formats warning report |
| DDI database initializer | `0x00927b3c` | 116 | opens DB |

**Tables / files:** `\Files\DB\DDI.Phy` (`:7225`).

**Business rules**
- Runs at prescription/sale time; if two interacting drugs co-occur, warn: "ليس لدي تيتان معلومة مؤكدة عن تفاعلات دوائية في هذه الوصفة" (Titan has no confirmed interaction info for this prescription) — `:12642`.
- Screen is explicitly interactive between patient and pharmacist: "لان هذه الشاشة هي شاشة تفاعلية بين المريض والصيدلي" (`modules_remaining_1.md`).
- Header label: `التفاعلات الدوائية الدوائية` (`:9910`).

**Related form:** `FormDrugDrug` (22 procs, "تفاعل الدواء بالدواء").

### 2.3 ModPeInter (Class) — patient–drug interaction

**Purpose:** Per-patient interaction checking combining allergies, recorded conditions (via ModDisease) and current medications — broader than ModDDI's drug-pair check. A Class (instantiated per patient profile).

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main patient interaction engine | `0x009afb98` | 360 | checks drug vs patient profile |
| Patient allergy checker | `0x0098747c` | 272 | allergy matching |
| Patient condition checker | `0x009702cc` | 228 | condition matching |
| Stub | `0x008ea35c` | 28 | placeholder |

**Business rules**
- Prescription–patient binding is explicit: "تم ربط المريض الحالي بالوصفة الطبية الحالية حيث يمكنك مستقبلا معرفة كافة الوصفات الطبية لهذا المريض" (patient linked to current prescription; future prescriptions queryable per patient) — `:11104`; unbind string `:11054`; already-linked `:13147`; not-linked `:13146`.
- Patient lookup requires national ID first: "اختر مريض اولا وذلك بادخال الرقم القومي له" (`:9045`).

**Related forms:** `FormMarid*` (patient screens).

---

## 3. Amount-to-Words — ModTafqit (تقطيع / كتابة المبلغ بالحروف)

**Purpose:** Converts numeric money amounts to Arabic/English words for formal financial documents and invoice printing (e.g. "فقط لا غير").

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main Arabic number-to-words | `0x00ae2780` | 2312 | 99 strings — Arabic grammar for units/tens/hundreds/thousands/millions/billions; contains `ايجارات` (rent) label |
| English number-to-words | `0x00ad1804` | 2060 | 79 strings — English equivalent |
| Currency formatter | `0x00a5736c` | 1000 | appends currency name (ريال, جنيه) |
| Fraction/helper | `0x00966410` | 240 | decimal part / half-units handling |

**Workflow**
1. Sales/purchase print path calls ModTafqit with the invoice total.
2. Integer part converted to words in the selected language (Arabic default; English when `الاسم باللغه الانجليزية` active).
3. Currency formatter appends the country currency (ريال for KSA/Oman, جنيه for Egypt — see section 6 ModCountries currency config).
4. Fraction part appended (e.g. "و... جنيه فقط لا غير").

**UI strings / currency vocabulary** (`strings_utf16.txt`):
- `ريال` (`:11582`), `جنيه` (`:11297`), `جنيها` (`:11299`), `جنيه فقط لا غير` (`:11298`)
- Currency pricing strings: `الجملة بالدولار` (`:9926`), `ادخل عدد العملات المحلية التي تساوي واحد دولار` (enter local currency per 1 USD, `:9229`).

**Business rules**
- Correct Arabic number grammar (dual/plural agreement) across orders up to billions; the main proc's 99 strings cover number-word tables.
- Amounts always printed fully in words on A4/thermal invoices to satisfy Arabic commercial document norms.
- Also used by free accounting module for cheque/statement amounts.

**Side-effects:** None (pure formatting/printing).

---

## 4. Translation — ModTranslator, ModEnglishtoArabic

### 4.1 ModTranslator (Module, 5 procs)

**Purpose:** UI language translation (Arabic ⇄ English) driven by Windows locale; detects non-Arabic Windows setup and offers guidance.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main translation dictionary (en→ar) | `0x00b6058c` | — | 1128 strings (largest) |
| Reverse dictionary (ar→en) | `0x00b53198` | — | 442 strings |
| Dictionary A (shared) | `0x00b1f3f8` | — | 204 strings |
| Dictionary B | `0x00ac5260` | — | 90 strings |
| Bulk translator (arrays) | `0x008d930c` | 0 | stub |

**Strings:** `Translation` (`:6714`), `language Settings`, `this means that setup of language in windows is not set to arabic`, `<html lang='ar'>`, `accept-language`.

**Business rules**
- If the Windows system locale is not Arabic, shows guidance to set Arabic locale (`Change system locale` → `Arabic Egypt`), optionally running `powershell` / `intl.cpl` — `config_complete.md §12`.
- HTML output switches to `lang='ar'` and RTL when Arabic selected.

### 4.2 ModEnglishtoArabic (Module, 7 procs)

**Purpose:** Converts English pharmaceutical terms, drug names, and UI labels to Arabic; manages RTL text layout.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| English→Arabic dictionary | `0x00b09cac` | 3244 | 59 strings |
| Arabic→English dictionary | `0x00b082c4` | 3200 | 59 strings |
| Drug name translator | `0x00ae3a10` | 2304 | 830 tokens — maps English drug names to Arabic |
| UI string translator | `0x00ab8cd0` | 1740 | bulk translate |
| Text direction handler (RTL/LTR) | `0x009b0bd4` | 380 | layout flip |
| Lookup helpers | `0x0097d058` / `0x0097ec90` | 280 each | key lookup |

**Strings:** `Arabic Transparent` (Arabic font), `Arabic name`, `Name Arabic`, `NameArabic`, `NameEnglish`, `English Horn` (font), "for windows xp click 'advanced' then select 'Arabic'".

**Business rules**
- Drug cards carry dual names: `الاسم باللغه الانجليزية` (`:9771`) and `الاسم باللغه العربية` (`:9772`); recommendation: drug names in English letters, cosmetics in Arabic — `:13369`.
- Translation affects printed reports and drug lookup indexing (both names searchable).

---

## 5. Mobile Integration — ModMobile

**Purpose:** Connectivity with a companion mobile app (Android). Registers the pharmacy's mobile number with the Titan cloud, exchanges stock/price/data files, and validates mobile numbers for patients/customers.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main mobile sync | `0x00af3764` | 2612 | 81 strings — full data exchange with mobile |
| Mobile registration | `0x00a2bb84` | 788 | registers mobile number with cloud |
| Mobile data uploader | `0x009f609c` | 588 | push data to mobile |
| Mobile data downloader | `0x009c5c40` | 440 | pull data from mobile |
| Mobile status checker | `0x009bdce4` | 408 | checks companion status |
| Mobile config loader | `0x009a1268` | 324 | loads cloud config |
| Mobile number validator | `0x0096d0ac` | 216 | phone-number format check |
| Mobile connection checker | `0x0091bac0` | 104 | online check |
| Mobile cleanup | `0x009142b0` | 96 | cleanup |

**Strings** (`strings_utf16.txt`):
- `Mobile number for cloud connectivity` (`:5660`), `Input mobile number` (`:4823`), `Enter mobile number`
- `Custmer mobile` (`:4458`), `Input patient mobile number` (`:5336`)
- `Wrong mobile Id` (`:6945`), `data in this mobile numer not present` (`:7659`)
- `Upload to mobile` (`:6803`)
- Paths: `/titan-users/allinone/mobiles/` (`:2202`), `/titan-users/titan-mobile/files/` (`:2208`)
- Cloud base: `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/mobiles/`; files `xo-mobile.txt`, `mobiles.numbers.rar`
- `إضافة الربط مع تريسر لعمليات السنوات السابقه` (tracer link for past years) — mobile/tracer
- Egyptian governorate helper: `الدقهلية:المنصورة` (`:9984`), `اسيوط:الغنايم` (`:9472`) — location pairing used by the mobile data feeds.

**Tables:** `titanpharmalist (mobile)` — `begin insert into titanpharmalist (mobile) values (N'...` (`strings_readable.txt:886`); lookups `WHERE mobile='...'` on `taronlineeg` (`:819`), `farysales` (`:999`).

**Side-effects:** Registers pharmacy identity (mobile) in the cloud pharmacy registry; uploads price/stock snapshots for the mobile app; may write remote pharmacy data into `taronlineeg`/`farysales` mobile-keyed rows.

**Business rules**
- Wrong/unknown mobile returns `Wrong mobile Id`; absent data returns `data in this mobile numer not present`.
- Mobile number doubles as cloud key for pharmacy identification (same field used across DTTS/multi-instance sync).
- `القيمة المطلوبة` (required value) prompt used in mobile config UI (`:10240`).

---

## 6. Country / Settings Modules — ModCountries, ModAppType, ModColors, ModScreen, ModFlexWheel

### 6.1 ModCountries (Module, 24 procs)

**Purpose:** Multi-market configuration: maps country names to IDs, sets per-country currency, VAT, tax rules, ZATCA e-invoicing, date/language behavior. Adapts the same binary for KSA, Egypt, Iraq, Oman, Qatar, etc.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Country-ID lookup | `0x009c4a04` | 448 | maps country name → numeric ID (1..11) |
| Country init | `0x0097fe08` | 272 | reads country object properties (ID range 0–200) |
| Country settings loader | `0x009a908c` | 364 | 5 sequential country-option checks |
| Country config setter | `0x009f00fc` | 592 | sets 13 properties (name, currency, VAT%, date format, language, ZATCA flag, ...) |
| Country feature checker | `0x0093307c` | 156 | 11 feature flags |
| Country name list builder | `0x00949448` | 168 | concatenates Arabic country names |
| Country sub-loaders ×3 | `0x0092c404/0x0092c344/0x0092b504` | 140 each | per-country config |
| Path builder | `0x0092c1ac` | 116 | builds `path = base & "\"` with country prefix |
| Singleton getters ×10 | `0x008e3ab8..0x008e36bc` | 20 each | cached property getters |

**Strings:** `Saudia`, `KSA`, `Egypt`, `Iraq`, `Oman`, `Qatar`; `correct your country`, `Invalid country ID format.`, `Export to current country is forbidden`; SOAP country service `http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso` (`:7936` variant in ModDisease).

**Business rules**
- Country ID drives VAT rate and tax regime (see §5 pricing above; currency ريال/جنيه/دولار).
- Some export operations are blocked per country (`Export to current country is forbidden`).
- Country prefix used in file paths (per-country data directories).

### 6.2 ModAppType (Module, 9 procs)

**Purpose:** App deployment type — pharmacy / clinic / wholesaler / warehouse. Filters which tables, forms and features are available.

**Objects:** feature-flag checks (×4), form-visibility control (×2), table selection by `apptype` (×1), string mapping (×1), persistence (×1). Key proc `0x00969620` (9 strings) initializes flags.

**Strings** (`strings_readable.txt`/utf16): `and apptype ='`, `pharmacyid =`, `pharmacyname`, `adress`, `4=All drugs With No International Barcode And they are pharmacy drugs`.

**Business rules**
- `titanksastock` filtered by `pharmacyid` and `apptype`; `titanstock`/`titanneed` filtered by `pharmacyid` — `modules_gap_1.md §10`.
- App type also selects which drug set is "pharmacy drugs" for barcode/classification rules.

### 6.3 ModColors (Module, 3 procs)

**Purpose:** Color/theme for grids and forms (background/foreground/cell colors, color-blindness mode).

**Objects:** init (`0x0091ed20`), apply (`0x00926140`), persist (`0x00938458`). File `\Files\DBI\colors.phy`; strings `BackColor`, `ForeColor`, `CellBackColor`, `CellForeColor`, `BColor`, `Color blindness`. CSS themes for HTML reports: `.drugs-tabe td {border:1px solid black;color:blue}`, `.final-tabe td {…color:red}`, `background-color:#abeb34` — `modules_gap_1.md §11`.

**Related form:** `FFFColors` (4 procs, "الالوان").

### 6.4 ModScreen (Module, 3 procs)

**Purpose:** Screen-resolution detection and DPI handling via `GetSystemMetrics`/`SystemParametersInfo`; warns (and can terminate) if resolution too low.

**Objects:** resolution detect + form positioning (`0x009bde70`, 312), physical screen size with warning at 768×1024 threshold (`0x00939b78`, 148), fatal "screen too small" handler (`0x00919c70`, 96). Strings: `Screen Resolution...`, `Zoom in program screens`, `Print Screen`.

### 6.5 ModFlexWheel (Module, 4 procs)

**Purpose:** Enables mouse-wheel scrolling on MSFlexGrid (which lacks native wheel support), intercepting `WM_MOUSEWHEEL`.

**Objects:** wheel event handler (`0x0091fd50`, 124), scroll-position calc (`0x00909df0`, 88), main scroll impl (`0x00984254`, 292), row counter (`0x008f6df0`, 56). Companion `FLXMod` (55 procs) provides grid column sizing/coloring/filter/sort/print/export — `ui_complete.md` (FLXMod top-10 module).

---

## 7. Data Files Handling, DB Rebuild, VB7 Compat — ModOneFile, ModFiles, ModReBuild, ModSQL, VB7

### 7.1 ModFiles / Files — `.phy` file I/O

**Purpose:** Core file abstraction for Titan's proprietary `.phy` format (open/close/read/write/path resolution). All other modules use it.

**ModFiles (20 procs):** open-read (`0x0090d5f8`), open-write (`0x0090e0a8`), path resolver (`0x00911818`, 2 strings), exists (`0x008e2e38`), size (`0x008e7f6c`), line read/write (`0x00912de0`), close (`0x008f67cc`), flush (`0x008f6834`), plus a higher-level **`Files` module (41 procs)**.

**Data directories** (`config_complete.md §16`, `strings_readable.txt`):
- `\Files\DBI\*.phy` — index/state files (colors, print, us, myftp, integrations, orooda, daily-manual, titanver, app.version, login-h, mandoup, inndesign, pixml, xmlauth3)
- `\Files\DB\*.Phy` — database files (DDI.Phy, Restore.bak, Install.rf, server.connection.report.txt)
- Migration artifacts: `pruchfull.phy to pruchworld.phy to remove serial column and add tawreed number in chars` (`:8253`)

### 7.2 ModOneFile (Module, 23 procs)

**Purpose:** "Export to one file" — serializes the entire pharmacy database (drugs, sales, purchases, customers, settings) into a single `.phy` file for transfer/backup/migration; imports it back.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main export routine | `0x00b1e378` | 4124 | serializes all tables into one file |
| Main import routine | `0x00b0ed64` | 3440 | parses file back into DB |
| Data chunk writer | `0x00ac2500` | 1800 | writes table data with column headers |
| Data chunk reader | `0x00accebc` | 1932 | reads chunks |
| File header builder | `0x00aa4618` | 1524 | metadata (pharmacy name, date, version, country) |
| Schema writer/reader | `0x00a25914` / `0x00a1f2cc` | 768 / 760 | table schema serialize/deserialize |
| Data validation | `0x00a01530` | 644 | integrity checks |
| Compress / decompress | `0x009fe0e4` / `0x009ed868` | 576 each | packing |
| Integrity check | `0x009d2a74` | 488 | checksum/file verify |
| Chunk boundary handler | `0x009be6a0` | 428 | chunk framing |
| Duplicate table processors | `0x009b6ed4` / `0x009b7a14` | 412 each | dedupe on import |
| Format detector | `0x009a1428` | 352 | recognizes file type |
| Progress/cleanup | `0x009331f8` / `0x0093f7b0` | 128 / 160 | UI + cleanup |

**Strings:** `Export to one file` (`:4888`), `Only one file can be sent.` (`:5823`), `الي ملف واحد علي شكل قاعدة بيانات اكسس` (to one file in the form of an Access database, `:10424`).

**Business rules**
- Output is a single self-contained file (optionally Access-compatible) with header → schema → data chunks.
- Validation and integrity checks before import; duplicate table rows handled on import.
- Compress/decompress for smaller transfers; progress reported during export/import.

### 7.3 ModReBuild (Module, 14 procs)

**Purpose:** Database schema migration/rebuild engine — CREATE/ALTER/DROP tables, add columns, rebuild indexes, conditional column-existence checks via `INFORMATION_SCHEMA`.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Bulk schema modification | `0x00adcc5c` | — | ~30+ ALTER TABLE column additions |
| Table creation | `0x00a35d80` | 824 | CREATE TABLE with many columns (14 strings) |
| Index rebuild | `0x009be498` | 404 | create/drop indexes |
| Column existence check + ALTER | `0x009f0b40` | — | `IF NOT EXISTS (SELECT ... FROM INFORMATION_SCHEMA.COLUMNS ...)` (8 strings) |
| Data migration procs | `0x00949708`/`0x00941674`/`0x00a8f4f8` | — | move old→new schema |
| Validation/repair | `0x00999194`/`0x009515cc`/`0x00ad4210` | — | schema verify (18 strings) |
| Version check | `0x008d9000` | 4 | placeholder |

**Strings** (`modules_gap_1.md §5`): `CREATE TABLE titanksasales (`, `CREATE TABLE titanksastock (`, `CREATE TABLE titanneed (`, `create table titaninn (`, `drop table titaninn;`, `select Column_name From Information_schema.Columns where Table_name like`, `Column separation letter in Excel table`, `ColumnWidth`.

**Tables:** `titanksasales`, `titanksastock`, `titanneed`, `titaninn`, `TitanUserAction`.

**Related:** `ModUpto352` (migration to v3.52, "تحديث 352") — version-gated ALTER steps (`modules_remaining_1.md §4`).

### 7.4 ModSQL (Module, 13 procs)

**Purpose:** Central SQL/ADODB data-access layer — connection lifecycle, query builder, recordset iteration, field extraction, INSERT/UPDATE/DELETE/SELECT dispatch, transactions.

**Objects** (key): main SQL exec (`0x00a03110`, 24 strings — connection build `ADODB.connection`, multi-branch statement), query builder (`0x00916f90`), connection check (`0x008f0380`), recordset iteration (`0x0093ec44`), field extract (`0x0090b740`), transaction mgmt (`0x0094f278`).

**Strings** (`modules_gap_1.md §7`): `select * from titaninn`, `select * from titanksasales`, `select * from titanksastock`, `delete from drgserver`, `delete from nilsen2`, `delete from remotecontrol`, `insert into titaninn`, `insert into titanksasales`, `insert into wzdrugs`, `if not exists (select * from storediscount ...`, `select invoiceid from titanksasales where`, `select drugname from titanksastock where`, `items need to update :`.

**Tables touched:** `titaninn`, `titanksasales`, `titanksastock`, `titanstock`, `titanpharmalist`, `drgserver`, `storediscount`, `nilsen2`, `remotecontrol`, `RawakidTablew`, `taronlineeg`, `usersourceupdate`, `farysales`, `wzdrugs`, `wzphar`.

### 7.5 VB7 (Module, 42 procs)

**Purpose:** VB6-runtime compatibility/utility layer: date handling, array manipulation, string ops, file wrappers, memory helpers, plus validation messages used by GS1/barcode features.

**Key strings** (`modules_gap_1.md §6`): `Sent XML data structure is not compatible with the scheme in WSDL document`, `The format of the batch number of the product is incompatible.`, `The format of the expiry date of the product (XD) is incompatible.`, `The format of the product information of the product (GTIN) is incompatible.`, `Types of barcode paper compatible with Titan`. Proc count confirms 42 procs; largest (`0x00ac59f8`, 35 strings) is a file parser/data transformer.

---

## 8. Barcode Merge, Stock Test, 5-Year Archive, Drug Exchange, Free Accounting

### 8.1 ModMergeBarcodes (Module, 15 procs)

**Purpose:** Merges/unifies duplicate barcodes, links multiple barcodes to one drug, finds near-identical barcodes (1–2 digit differences), tracks merge history, and maintains a "similar barcode" relationship database. Critical because different suppliers ship the same drug under different barcodes.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main merge engine | `0x00a2a350` | 752 | merges duplicate barcode records |
| Merge undo | `0x00a3044c` | 772 | reverses a merge |
| Barcode similarity finder | `0x00a486d0` | 908 | barcodes differing by 1–2 digits |
| Barcode relationship manager | `0x009f3bf4` | 568 | links barcodes → drug IDs |
| Barcode validator | `0x0097c2fc` | 280 | structure validation |
| Barcode history tracker | `0x009fb32c` | 596 | merge history |
| Barcode report | `0x00988cb4` | 284 | report generator |
| Lookup / add / remove | `0x0092633c`/`0x0092a5f4`/`0x00958d0c` | 76/124/200 | quick ops |
| List ops pair | `0x0093fbf8`/`0x0093f178` | 136 each | list management |
| Utilities | `0x008f8478`/`0x008f85c4`/`0x008fc720` | 44/52/48 | helpers |

**Strings** (utf16/readable): `بورود`/barcode merge, `تعريف حظر الباركودات` (define barcode block, `:10920`), `Block barcode from usage` (`:4096`), `Remove duplicate barcodes for items`, `Clean duplicate barcode`, `Download duplicated barcode blocking tool`, `Change international barcode`, `Barcode1..Barcode5` (`OR Barcode1=N'...`).

**Business rules**
- Lookups scan `Barcode1..Barcode5` + short code; merge makes several equivalent barcodes resolve to one drug record.
- Blocked/duplicate barcodes can be blocked from usage and later unblocked (`Block barcode from usage`, `Cancel barcode blocking`).
- Merge history retained for undo.
- GS1 structure validated; `An international barcode common to more than one drug` / `An international barcode with an incorrect structure` errors.

**Related form:** `FormMoreBarcodes` (8 procs, "باركودات اضافية") and `FormParCode` (14 procs, "باركود").

### 8.2 ModStockTest (Module, 4 procs)

**Purpose:** Stock reconciliation / "جرد حسابي" (accounting inventory): verifies system stock against movement history, computes differences, and produces stock-test reports.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Main stock test | `0x00a1c234` | 652 | runs comprehensive validation |
| Stock difference calculator | `0x0095070c` | 172 | diffs expected vs recorded |
| Stock test report | `0x00998204` | 280 | report generator |
| Stock audit-trail checker | `0x009dfe20` | 524 | 27 strings — physical vs system comparison |

**Business rules**
- Reconstructs expected stock from sale/purchase/need/move history and compares to `titanksastock`/`titanstock` current balances.
- Differences are itemized so the pharmacist can correct balances (`FormDrugrasidCorrect`, تصحيح رصيد الدواء).
- Related concept: `راس المال` (capital) reporting uses reconciled balances.

### 8.3 Mod5Years (Module, 6 procs) + archival

**Purpose:** Long-term archival of data older than 5 years into compressed/serialized form, with restore, query-without-restore, and status reporting.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Archive processor | `0x009b8e98` | 372 | moves data older than 5 years |
| Archive compressor | `0x009af9b4` | 332 | compresses archived records |
| Archive restorer | `0x009c05ec` | 416 | restores on demand |
| Archive query | `0x0099773c` | 316 | query archived data without full restore |
| Archive report | `0x009d0350` | 396 | status report |
| Archive flag checker | `0x0091608c` | 92 | archived-state check |

**Strings:** `Sorry i have served you for more than 45 years ,thats enough :(` (age cap), `Import the prices from old data`, `ادخل عدد السنوات` (enter number of years, `:9227`), `ادخل عدد السنوات بالموجب او السالب حسب الحاجة` (`:9228`).

**Business rules**
- Archive threshold adjustable in years (±).
- Archived invoices retain full data and can be recalled any time: "وسيتم نقل الاقدم الي الارشفة مع الاحتفاظ بكافة بياناتها واستدعائها في اي وقت" (`:13249`).
- Archival messaging around 10k→20k invoice capacity: "ارشفة فواتير المبيعات تشمل ارشفه 20000 فاتورة بدلا من 10000" (`:9393`); over-large invoice counts warn "عدد فواتيرك اصبح كبيرا جدا ويحتاج الي ارشفة" (`:11157`).
- Sales/purchases archived separately (`أرشفة المبيعات القديمة` `:8899`, `أرشفة المشتريات القديمة` `:8900`); failure aborts: `فشلت عملية الارشفة لا يمكنني الاستمرار. برجاء الاتصال بخدمة العملاء` (`:12085`).
- Related 3-year fraud detection: `مقارنة المبيعات لاخر 3 سنوات لكشف اذا كان هناك تلاعب في الفواتير القديمة` (`:12870`).

**Related:** `ModBackupMonthly` (monthly archive/close, `modules_gap_1.md §19`).

### 8.4 ModDRGEXChange (Module, 4 procs)

**Purpose:** Drug unit exchange — converts between packaging units (box→strip→tablet) and handles multi-currency exchange rates for drug pricing.

**Objects**
| Proc | Address | Size | Role |
|---|---|---|---|
| Exchange rate loader | `0x009894fc` | 220 | loads rates |
| Main exchange calculator | `0x00a3f0c0` | 824 | converts between units/currencies |
| Exchange rate updater | `0x00a085fc` | 580 | 1 string |
| Exchange rate validator | `0x009c0218` | 444 | validates rates |

**Strings:** `"exchangeRate": ` (JSON cloud field, `strings_readable.txt:279`); currency config `"currency": "`, `valueDifference`; `ادخل عدد العملات المحلية التي تساوي واحد دولار` (`:9229`); `Discount by currency` / `خصم بالعملة` (`:11424`).

**Business rules**
- `exchangeRate` used in cloud price feeds (per-country currency — see ModCountries).
- Unit conversion applied at sale/print when the user switches packaging; pricing recomputed across rate.
- Exchange feed supports multi-market price sync (`titan-users/data-for-sale/.../`).

### 8.5 ModAccFreeOne (Module, 19 procs)

**Purpose:** Free/limited accounting tier: trial-period tracking, activation/license validation, feature restrictions, network activation, and the free account tree (`wzaccfreetree`).

**Objects (key):**
| Proc | Address | Size | Role |
|---|---|---|---|
| Trial period check | `0x00923c44` | — | activation status |
| Activation code validation | `0x00965d0c`/`0x00a25fc4`/`0x00a27090` | — | 1/3/3 strings |
| License status | `0x00a96228` | — | license check |
| Trial counter increment | `0x00a7e418` | — | trial days++ |
| Activation persistence/deactivation/network | remaining procs | — | save/remove/network activation |

**Strings** (`modules_gap_1.md §17`): `License`, `License number is empty`, `License number used by someone else`, `TRial No:`, `Temporary activation for 3 days` (`تفعيل مؤقت لمدة ثلاثة ايام`, `:10951`), `Activate your app`, `Active up to`, `Input activation code for mandoup`, `Successfull activation`, `Invalid deactivation reason`, `you choosed to remove your activation`, `Network-activation`, `Free Disk Space ON C:\ is MB and it is not enough for windows system`, `Use deactivation notification for expired units.`; Arabic activation strings: `تفعيل النسخة عبر التليفون` (`:10950`), `تم تفعيل نسختك الفرعية لمدة سنة` (sub-license for 1 year, `:11090`), `تهانينا تم تفعيل نسختك` (`:11153`).

**Tables / files:** `wzaccfreetree (mobile,master,fary)` — `insert into wzaccfreetree (mobile,master,fary) values (...)`; `if not exists( select * from wzaccfreetree where ...)`; `Files\accounting\id.txt`; `Files\DBI\mandoup.phy`.

**Business rules**
- Free tier restricted to a simplified account tree; full accounting requires activation of `قسم المحاسبة المتكامل` (`تفعيل قسم المحاسبة المتكامل`, `:10949`).
- Trial limited (3 days temporary activation); permanent activation binds to hardware fingerprint (ModWMI) — `لا يمكن تفعيل نسختك بطريقة المعرف الثابت` (`:1118`).
- Each license key usable by one machine; duplicate use → `License number used by someone else`.
- Network activation distributes activation among linked PCs; sub-licenses valid for 1 year.
- Also verifies minimum free disk space before operations.

**Related forms:** `FormAccUploader` (47 procs, finance), accounting module `ModAccounting` (`modules_gap_1.md §14`).

---

## Cross-cutting summary

- **Sale-time safety net:** ModOrood (offers) + ModDisease/ModDDI/ModPeInter (interactions) all hook into the sales/prescription workflow; the diagnosis/recommendation screen is shared with `FormMarid*` and `FormDrugDrug`.
- **Print/billing:** ModTafqit renders the amount-in-words line on invoices; ModTranslator/ModEnglishtoArabic switch print language; ModDRGEXChange converts unit/currency before pricing.
- **Persistence & migration:** ModFiles/ModOneFile handle `.phy` I/O and whole-DB transfer; ModSQL is the ADODB layer; ModReBuild + ModUpto352 perform versioned schema upgrades; VB7 supplies runtime helpers.
- **Multi-market identity:** ModCountries (country ID → currency/VAT/ZATCA), ModAppType (pharmacy type → table filtering), ModMobile (cloud mobile key), ModAccFreeOne (license bound to hardware via ModWMI).
- **Data hygiene:** ModMergeBarcodes (duplicate/blocked barcodes), ModStockTest (balance reconciliation), Mod5Years/ModBackupMonthly (archival retention).