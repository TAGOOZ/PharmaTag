# النسخ الاحتياطي والأرشفة والاستيراد — Backup, Archive & Import/Export ("الباك اب / الأرشفة / الفواتير المحولة")

**Purpose:** Full extraction of the backup (النسخ الاحتياطي), archiving (الأرشفة) and invoice import/export (استيراد/تصدير الفواتير) features of TITAN.W1 (Phye.exe). Covers the full database backup workflow (manual, automatic-at-close, daily and monthly), the monthly archive `\Files\Archive\monthy\`, backup-before-day-close integration, the restore workflow, archiving old sales/purchase invoices (تخزين/أرشفة فواتير المبيعات والمشتريات القديمة), inter-pharmacy invoice transfer via import/export of "fat" (فاتورة) using `titaninn`, database maintenance / clean-up (FormDatabase تصفية قاعدة البيانات), the `.phy` file system, and the `usersourceupdate` / `remotecontrol` sync logs used to move drug/price/function data between pharmacy instances.

Source: `titan_decompile/` (strings_utf16.txt, strings_readable.txt, pcode_disasm.txt), reused from `business_logic_complete.md` (§11 ModBackup, §23 Backup & Cloud Architecture, §2.9/2.10), `modules_gap_1.md` (§19 ModBackupMonthly), `modules_gap_2.md` (§7 FormEnd, §18 FormArchiveBuy, §19 FormArchiveSales, §20 FormBackup, §23 FormDatabase, §9 FormImportFat, §35 FormExportFat, §36 FormExportFatList, §46 FormImportFatList, §75–80 FormX*), `modules_remaining_1.md` (ModOneFile, ModArchive procs), `modules_remaining_2.md` (§11 ModArchive), `network_complete.md` (§10 Backup System, §11 Export/Import System, §9 Remote Control), `config_complete.md` (§5 Backup Paths, §16 File Paths), `schema_complete.md`/`schema_complete.sql` (tables 6 titaninn, 16 remotecontrol, 18 usersourceupdate, 2.9/2.10 in business_logic), `feature_account_closing.md` (backup/archive at close, Daily.phy).

---

## 1. Objects

### 1.1 Backup / restore objects

| Object | Type | Procs | Role |
|---|---|---|---|
| **ModBackUp** | Module | 43 | Backup & restore engine — full DB backup, restore point, F9/F12 save shortcuts, USB/cloud/internet backup (business_logic_complete §11.1–11.3; pcode `Module ModBackUp` entries in pcode_disasm, e.g. @0x00ade704 with 25 strings). |
| **ModBackupMonthly** | Module | 13 | Monthly backup & archive — monthly closing/compression, backup rotation, internet (FTP) upload, restore from archives (modules_gap_1 §19). Procs include monthly archive init, archive status check, monthly archival with ZIP compression (size 1300), archive extraction/restore (1260), internet backup upload (1292), full monthly closing workflow (3208), backup rotation/cleanup (1504), archive verification (900). |
| **FormBackup** | Form | — | النسخ الاحتياطي — manual backup creation, restore point, backup scheduling (modules_gap_2 §20). Controls: btnBackup, btnRestore, txtPath, btnBrowse, chkAutoBackup, cmbFrequency. |
| **FormBackRestore** | Form | 4 | Backup/restore interface (schema_mapping.md:208; pcode @0x008db6e0…). |
| **FormRestore** | Form | 6 | استرجاع النسخ الاحتياطية — data restore (schema_mapping.md:209; strings_readable:8759). |
| **FFFbackupAuto** | Form | 5 | Automatic backup form — runs the timed/auto backup (pcode names @0x008fdba4…, @0x00a2e878 with 4 strings). |
| **FormXBackup / FormXRestore** | Form | — | Backup/restore utilities launched from FormEnd (modules_gap_2 §75–80; feature_account_closing §1.1). |
| **cZipArchive** | PropertyPage | ~18 | ZIP compression/decompression component used by backup & archive (pcode names; modules_remaining_2 §11). |
| **ModFTP / ModNetwork / ModTitanCloud** | Module | 29/65/16 | FTP upload of backups (`C:\ftpdbi.zip`, `ftpcmd.dat`, curl `--ftp-pasv --retry 3`), cloud backup to `titan-users/dbi-zipped/Bux-w-backup/` etc. (network_complete §2, §6, §10). |

### 1.2 Archive objects

| Object | Type | Procs | Role |
|---|---|---|---|
| **ModArchive** | Module | 2 | Data archiving — `Archive old sales invoices`, `Read archived invoices`, `CompressArchive`/`OpenArchive`/`ForceArchive`, `cZipArchive`, archive dirs `\Files\Archive\Input\`, `\Files\Archive\Output\`, `\Files\Archive\monthy\` (modules_remaining_2 §11; pcode @0x007b… start=507444). |
| **FormArchiveSales** | Form | — | أرشفة المبيعات القديمة — archive old sales invoices (modules_gap_2 §19; strings_readable:8253). Controls: txtFromDate, txtToDate, btnArchive, dgPreview, lblCount. |
| **FormArchiveBuy** | Form | — | أرشفة المشتريات القديمة — archive old purchase invoices (modules_gap_2 §18; strings_readable:8254). Controls: txtFromDate, txtToDate, btnArchive, dgPreview, lblCount, chkDeleteAfter. |
| Archive procs (modules_remaining_1 §0x…): | | | Archive processor (identifies/moves data older than 5 years, 372), archive compressor (332), archive restorer (416), archive query (316), archive report (396), archive flag checker (92) (modules_remaining_1.md:375–380). |
| **FormEnd** | Form | 13 | نهاية اليوم — hosts btnArchive / btnBackup for archive-old-invoices and backup-at-close (modules_gap_2 §7; feature_account_closing §1.1). |

### 1.3 Invoice import/export objects (فاتورة بين الصيدليات)

| Object | Type | Procs | Role |
|---|---|---|---|
| **FormImportFat** | Form | 14 | استيراد الفاتورة — import a transferred invoice (pcode @0x00a2311c start=440867 …; modules_gap_2 §9). Controls: txtFilePath, btnBrowse, cmbImportType (مشتريات/مرتجعات), dgPreview, btnMap, btnImport, btnValidate, lblProgress, chkOverwrite. |
| **FormImportFatList** | Form | — | قائمة الفواتير المستوردة — list of imported invoices (modules_gap_2 §46). |
| **FormExportFat** | Form | — | تصدير الفاتورة — export invoice data to file / another pharmacy (modules_gap_2 §35). |
| **FormExportFatList** | Form | — | قائمة الفواتير المُصدّرة — list of exported invoices (modules_gap_2 §36). |
| **FormGetFats** | Form | 2 | جلب الفواتير — fetch invoices from branches/DB (modules_gap_2 §8): "برجاء تحديد الفواتير التي تريد جمعها من الجدول ادناه" (strings_readable:9919). |
| **FormGetFatsFromStore** | Form | — | جلب الفواتير من المخزن — fetch invoices from warehouse (modules_gap_2 §41). |
| **ModImportExport** | Module | — | Import/export engine shared by FormImportFat/FormExportFat/FormGetFats/FormTahwil (modules_gap_2 cross-ref table). |
| **FormTahwil / FormTahwilList** | Form | — | تحويل الفواتير بين الفروع — branch transfer (modules_gap_2 §67–68). |
| **FormCopyMe** | Form | 3 | نسخ فاتورة — copy/duplicate invoice items (modules_gap_2 §4). |

### 1.4 Database maintenance & sync-log objects

| Object | Type | Procs | Role |
|---|---|---|---|
| **FormDatabase** | Form | — | قاعدة البيانات / تصفية قاعدة البيانات — compact/repair/clean DB, delete all invoices while keeping drug/customer/supplier balances (modules_gap_2 §23). Controls: btnCompact, btnRepair, btnClean, dgStats, lblSize, btnBackup. |
| **ModSqlLink** | Module | 19 | Remote SQL linking — network pharmacy discovery/linking, data replication, remote invoice lookup/transfer, sync via `remotecontrol`/`drgserver`/`titaninn` (modules_gap_1 §9). |
| **ModOneFile** | Module | — | "One File" export/import — bundles all pharmacy data into a single `.phy` file for backup/migration (modules_remaining_1 §start). |

---

## 2. Step-by-step workflow

### 2.1 Full database backup (نسخ احتياطي كامل)

1. **Trigger manual backup** — "حفظ نسخة احتياطية" (strings_readable:10721); Save by `F9`, Unsave by `F12` (business_logic_complete §11.3 "Save by F9 ; Unsave by F12"). From the sales screen the system may auto-request a backup: "يحتاج تيتان لحفظ نسخة احتياطية هل تسمح له الان" (strings_readable:12659).
2. **Choose destination** — the backup is written under `Labirdo\Titan3-Backup\` with subfolders `Daily\`, `Monthly\`, `Export\`, `xj\` (compressed), `images\`, `tars-copy\`, `qr\`, `Rur\` (network_complete §10; business_logic_complete §11.1). Backup path stored in a file inside the backup folder: "سيتم حفظ مسار النسخة في مجلد النسخ الاحتياطية في ملف اسمه …" (strings_readable:11070). Config key: "Backup folder" (config_complete §5).
3. **Optional USB copy** — "Save a bakeup on the usb flash" / "يمكن عمل نسخة احتياطية اضافية بشكل تلقائي علي الفلاشة" (strings_readable:12689; business_logic_complete §11.2 rule 5).
4. **Internet backup** — "حفظ نسخة احتياطية عبر الانترنت" (strings_readable:10723) / "Create Internet backup"; success confirmed "تم حفظ نسخة احتياطية علي الانترنت بنجاح" (strings_readable:10440). Internet backup is enabled/configured via `DBI\internet-backup.txt` (config_complete §16; network_complete §10) and uploaded with FTP/curl (`C:\ftpdbi.zip` staged ZIP, ModFTP).
5. **Automatic backup timing** — "تعديل نظام النسخ الاحتياطي من ساعة الي 3 ساعات في شاشة المبيعات" (strings_readable:10258) — auto-backup frequency configurable (every hour → every 3 hours) from the sales screen; FFFbackupAuto runs it.
6. **Backup retention** — "تم تخفيض مدة النسخ الاحتياطية من 30 يوم الي عشرة ايام مع احتفاظ بنسخة دائمة لكل شهر من الشهور" (strings_readable:10414) — daily backups retained ~10 days, one permanent copy kept per month. "Clean backups" / "تنظيف النسخ الاحتياطية القديمة" (strings_readable:10485–10486) removes old backups; history logged in `Labirdo\Titan3-Backup\History.txt` (config_complete §5; business_logic_complete §11.1).
7. **Backup label** — each backup is stamped "This is Titan backup maked by [user]" (business_logic_complete §11.2 rule 7).

### 2.2 Backup at day close (تقفيل اليوم)

- **FormEnd / btnBackup** — the close screen offers backup. Behavior configurable in advanced settings: "سيتم الان تقفيل اليوم بدون اخذ نسخة احتياطية بناءا علي اعداداتك في شاشة اعدادات متقدمة" (strings_readable:11043); "حفظ نسخة احتياطية رئيسية اثناء الاغلاق" (strings_readable:10722).
- **Daily backup** — "انشاء مجلد داخل مجلد النسخ الاحتياطية ليحتفظ بسجل يومي للارصدة مما يسمح …" (strings_readable:9825) — the daily backup folder keeps a daily balance-history so balances can be rolled back; folder `Labirdo\Titan3-Backup\Daily\` (idx 6656 `Titan3-Backup\\Daily\\`).
- **Self-healing**: if a backup file is corrupt the program reports and may create a fresh one: "لم نعثر علي نسخة احتياطية حديثة من بياناتك .. سيجري الان حفظ نسخة" (strings_readable:11931); "عند تلف احد ملفات البرنامج فان النسخ الاحتياطي العادي يتوقف وقد حلت المشكلة باضافة طريقة نسخ احتياطي جديدة تتجاهل الملفات التالفة …" (strings_readable:11333).

### 2.3 Monthly backup & archive (نسخ احتياطي شهري / أرشفة شهرية)

1. **ModBackupMonthly** builds the monthly archive: sales/purchase data is compressed (ZIP via `cZipArchive`) into `\Files\Archive\monthy\` (modules_gap_1 §19; modules_remaining_2 §11: `\\Files\\Archive\\monthy\\`).
2. Stage dirs `\Files\Archive\Input\` (purchases) and `\Files\Archive\Output\` (sales) are used; `CompressArchive` / `OpenArchive` / `ForceArchive` / `FORCEARCHIVE` control the lifecycle; errors surfaced as "Cannot init deflate compressor", "Error compressing", "Error reading archive" (modules_gap_1 §19).
3. Monthly closing may push the archive to FTP (`/Monthly/St/`, `<monthly-data>`, "Create Internet backup") and writes a metadata/verification file `Files\DBI\last-archive-process.xml` / `months.data.xml` (modules_gap_1 §23 strings).
4. Month-end accounting archives journal moves and opening balances: `\Files\Archive\monthy\moves\` and `\Files\Archive\monthy\start-data\` (feature_account_closing §1.2; feature_balances.md:43–44).
5. "التحقق من وجود نسخة لكل شهر" (feature_account_closing idx 9237) — the system verifies a backup exists for every month.

### 2.4 Restore workflow (استرجاع)

1. "Restore backup" / "Restore.exe" / "Run restore.exe to restore your data" (business_logic_complete §11.2 rule 6; modules_remaining_2). Restore point file `\Files\DB\Restore.bak` (config_complete §1/§16).
2. "استرجاع النسخ الاحتياطية" (strings_readable:8759) — pick a backup from the backup folder and restore.
3. If data is lost the app may ask support: "برجاء الاتصال بخدمة العملاء لمساعدتك علي استرجاع نسخة احتياطية" (strings_readable:12621); expiry-corruption: "كان تيتان يحاول تمديد تواريخ الصلاحية لكن العملية فشلت برجاء استرجع نسخة احتياطية بمساعدة الدعم الفني" (strings_readable:11574).
4. A `.phy` file can also be restored from the compressed copy: `Labirdo\Titan3-Backup\xj\Phye.zip` and `xj\Phye.safer\` (config_complete §5).
5. Guard: "لا يمكن تشغيل البرنامج من مجلد النسخ الاحتياطية قم بنسخة الي مكان اخر" (strings_readable:11707) — never run the program from inside the backup folder.

### 2.5 Archiving old invoices (تخزين/أرشفة فواتير المبيعات والمشتريات القديمة)

1. **Entry** — from the main screen: قائمة مشتريات → تخزين فواتير المشتريات القديمة / قائمة مبيعات → تخزين فواتير المبيعات القديمة (strings_readable:10121–10122, 11879). Dedicated screens أرشفة المبيعات/المشتريات القديمة (FormArchiveSales/FormArchiveBuy) accept a date range (txtFromDate/txtToDate), preview (dgPreview) and archive.
2. **Automatic trigger** — when the invoice table approaches its limit: "لقد وصلت الي الحد الاقصي المسموح به من الفواتير ولا يمكنك الاستمرار فمن فضلك توجه … قاءمة مشتريات تخزين فواتير المشتريات القديمة" (strings_readable:11879); "تواصل مع ادارة البرنامج للاهمية حيث ان عدد فواتيرك اصبح كبيرا جدا ويحتاج الي ارشفة" (strings_readable:10498). Capacity was raised from 10,000 to 20,000 invoices per archive pass: "ارشفة فواتير المبيعات تشمل ارشفه 20000 فاتورة بدلا من 10000" (strings_readable:8742); Titan 358 "زيادة عدد الفواتير الي الضعف في المشتريات والمبيعات لتقليل الارشفة" (strings_readable:11156).
3. **What happens** — the oldest invoices are moved to the archive while keeping all their data, retrievable at any time: "وسيتم نقل الاقدم الي الارشفة مع الاحتفاظ بكافة بياناتها واستدعائها في اي وقت" (strings_readable:12557). Sales archive → `\Files\Archive\Output\`, purchases archive → `\Files\Archive\Input\` (business_logic_complete §2.11/§23.1). "الان يمكنك الارشفة الكاملة" (strings_readable:9163).
4. **Failure handling** — "لم تنجح عملية تخزين فواتير المبيعات / المشتريات" (strings_readable:11921–11923); "فشلت عملية الارشفة لا يمكنني الاستمرار. برجاء الاتصال بخدمة العملاء" (strings_readable:11406). Mandatory before update: "برجاء الاتصال بخدمة العملاء لتنفيذ عملية ارشفة المبيعات/المشتريات قبل التحديث" (strings_readable:9929–9930).
5. **Read archived invoices** — "Read archived invoices" (modules_remaining_2 §11) allows browsing archived data without full restore; archive query proc + `Files\Archive\last-3-days-sales.csv` (recent sales) and `Files\Archive\undo.sales.txt` (undo sales archive) support it.
6. **Month-close integration** — FormEnd's btnArchive archives old invoices at close; the archived invoice number may be re-numbered: "رقم الفاتورة بعد الارشفة" (strings_readable:10899).
7. **5-year rule** — archive processor identifies/moves data older than 5 years (modules_remaining_1 archive procs: "moves data older than 5 years").
8. **Balances preserved** — stock snapshot taken at archive time: "Drugs stock before archive was : …" (modules_gap_1 §19); customer/supplier balances survive archiving because invoices only are moved out.

### 2.6 Import/export of fat (فاتورة) between pharmacies

1. **Export** — "تصدير الفاتورة الي صيدلية اخري" (strings_readable:10186) / "Export invoice to another pharmacy" (strings_readable:4585); "Transfer invoice to another pharmacy" (strings_readable:6361); "تحويل الفاتورة الي صيدلية اخري" (strings_readable:10112). "تحسين خدمة تصدير الفواتير ما بين افرع الصيدليات" (strings_readable:10094). The invoice is serialized into the `titaninn` table as `itemsasstring` (see §8).
2. **Import** — "استيراد فاتورة محولة من مستودع او صيدلية اخري" (strings_readable:8783) / "Importing a transferred invoice from another warehouse or pharmacy" (strings_readable:4981). FormGetFats collects invoices from a table: "برجاء تحديد الفواتير التي تريد جمعها من الجدول ادناه" (strings_readable:9919); import type selection: "اختر القيمة التي تود استيرادها" (strings_readable:8375).
3. **Target routing** — an imported fat can be routed to sales or to a sales return: "ادخل 800 لتحويل الفاتورة الي مبيعات … او 600 لتحويلها الي مرتجع مبيعات" (strings_readable:8441); "تحويل الفاتورة الي مرتجع مبيعات" from قائمة تحرير (strings_readable:12240). "فاتورة محولة" (strings_readable:11370).
4. **Transfer to a customer** — transferring invoices to another customer: "اختر العميل الذي سيتم نقل الفواتير اليه" (strings_readable:8372).
5. **File/batch import-export** — generic Import/Export: "Export to a batch file"/"Import from a batch file" (strings_readable:4592/4969), "Export to file"/"Import from file" (4596/4971), "Export database to Excel" (4582), "Import from another software". Formats: `exported.data.all.csv`, `exported.data.stock.csv`, `exported.worked.data.csv`, `Cusom-export.csv`, `drugs-stock2.csv` (network_complete §11).
6. **Re-export of problem invoices** — "تصدير الفواتير التي تحتوي علي مشكلة في حساب الاجل" (strings_readable:10083; modules_gap_2 §35); "Export invoices that contain a problem in calculating debts".
7. **titaninn lifecycle** — after the target pharmacy receives the transfer its `target` is cleared: `update titaninn set target = N''`; sender/target queries `select * from titaninn where source/target =N'…'`; `titaninn` can be dropped/rebuilt (schema_complete table 6).

### 2.7 Database maintenance (FormDatabase تصفية قاعدة البيانات)

1. Compact / repair / clean orphaned records (modules_gap_2 §23).
2. **Delete-all-invoices option** — "اضافة امكانية حذف الفواتير كلها مع الاحتفاظ بارصدة الادوية والعملاء والموردين وهذا من شاشة تصفية قواعد البيانات" (modules_gap_2 §23 Arabic string); FormX/FormXEnd variant: "الان يمكنك الغاء حفظ الفواتير القديمه" (modules_gap_2 §75–80). Deleting invoices keeps drug stock (wzdrugs/titanstock), customer balances (wzcustomers) and supplier balances intact.
3. Also offers backup (btnBackup) and connects to FormBackup/FormXBackup.

### 2.8 Sync logs — usersourceupdate & remotecontrol

- **usersourceupdate** logs every drug price/units update pushed from a source pharmacy so other instances can apply it: `insert into usersourceupdate (drugname,price,units,localimport,…)`; consumers pull `SELECT top 3000 * FROM usersourceupdate WHERE Datee > '…'`; admin deletes processed rows `DELETE FROM usersourceupdate WHERE id='…'` (schema_complete table 18; strings_readable:779, 4235, 5870, 7608). Used by "Import item updates from a friend", "Import the prices from old data", "Share between my group" flows (config_complete §18; network_complete §11).
- **remotecontrol** stores function/command payloads per pharmacy: `insert into remotecontrol (datee,mobile,copyid,passedfunctions)`; queried by mobile `select id,datee,passedfunctions from remotecontrol where mobile = N'…'` and by date `select passedfunctions from remotecontrol where datee > N'…'`; cleanup `delete from remotecontrol where id = N'…'` / `where passedfunctions = N'…'` (schema_complete table 16; network_complete §9; strings_readable:678–679, 7606, 7919–7920). Drives "Remote-control", "Log in as Technical Support", server-connector and cloud `titan-users/send-to/` flows.
- **TitanUserAction** additionally logs every drug modification (drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee) for audit across sync (schema_complete table 17).

---

## 3. Fields / data captured

### 3.1 Backup metadata files
```
Labirdo\Titan3-Backup\History.txt        — backup history log (date/user)
Labirdo\Titan3-Backup\titan-info.txt     — pharmacy/app info
Labirdo\Titan3-Backup\xj\internet-backup.txt — internet backup config
DBI\internet-backup.txt                  — internet backup switch/config
\Files\DB\Restore.bak                    — restore point
\Files\DBI\*.bak                         — DB backups
```
Backup label: "This is Titan backup maked by [user]".

### 3.2 Archive files
```
\Files\Archive\Input\                    — purchase archives (أرشفة المشتريات)
\Files\Archive\Output\                   — sales archives (أرشفة المبيعات)
\Files\Archive\monthy\                   — monthly archives
\Files\Archive\monthy\moves\             — monthly closing journal moves
\Files\Archive\monthy\start-data\        — monthly opening balances
\Files\Archive\last-3-days-sales.csv     — recent-3-days sales export
\Files\Archive\undo.sales.txt            — undo-sales archive
Files\DBI\last-archive-process.xml       — last archive process XML
Files\DBI\months.data.xml                — monthly data XML
```
Archive controls: txtFromDate, txtToDate, btnArchive, dgPreview, lblCount, chkDeleteAfter (FormArchiveSales/FormArchiveBuy).

### 3.3 Import/export (fat) fields
- FormImportFat: txtFilePath, btnBrowse, cmbImportType (مشتريات/مرتجعات), dgPreview, btnMap, btnValidate, btnImport, lblProgress, chkOverwrite.
- Routing keys: `800` → sales invoice, `600` → sales return invoice (strings_readable:8441).
- File formats: `exported.data.all.csv`, `exported.data.stock.csv`, `exported.worked.data.csv`, `Cusom-export.csv`, `drugs-stock2.csv`.

### 3.4 Database maintenance (FormDatabase)
- Stats grid dgStats (table sizes/counts), lblSize (DB size), buttons btnCompact/btnRepair/btnClean/btnBackup.
- Delete-all-invoices keeps drug stock, customer balances, supplier balances.

---

## 4. Side-effects

- **Stock (wzgard/titanstock/titanksastock):** archiving does not change current stock — a snapshot is taken first ("Drugs stock before archive was : …"); deleting all invoices (FormDatabase) preserves drug balances.
- **Customer/supplier balances (wzcustomers/companies):** preserved when invoices are archived or deleted; transfer of fat may move the debt to the target customer ("اختر العميل الذي سيتم نقل الفواتير اليه").
- **Money / daily files:** daily backup keeps a per-day balance history inside the backup folder so cash/daily balances can be rolled back (strings_readable:9825); `Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy` are part of the backed-up `.phy` set (feature_sales_invoices.md:282; feature_account_closing §3).
- **Sync tables:** each price/units edit writes `usersourceupdate`; remote commands/functions write `remotecontrol`; both replicate to linked pharmacies via ModSqlLink/cloud (`titan-users/send-to/`, `titan-users/allinone/data/`).
- **Inter-pharmacy invoice queue:** exporting a fat inserts a `titaninn` row (source=this pharmacy); importing consumes/clears `target`; unlinked rows remain pending in the "Pending invoice folder from linked devices" (modules_gap_1 §9).
- **Audit:** TitanUserAction records the user/mobile/barcode/price/units for every change that a backup or sync transports.

---

## 5. Pricing + VAT

- Backup/archive/import-export do not compute prices; they serialize stored values (price, units, vat, disc) exactly as held in the source rows.
- Importing a transferred fat applies the stored per-line price, SellDisc and vat; routing 800/600 keeps the invoice's tax treatment (sales vs sales-return).
- `usersourceupdate` carries price+units+localimport to propagate a price change across the group; the receiving pharmacy merges with its existing VAT and discount rules (feature_discounts/feature_drug_master_pricing apply).

---

## 6. Payment methods

- No payment capture in backup/archive itself. Transferred sales fats preserve their original payment method (كاش/شبكة/أجل) through `itemsasstring`; the importing pharmacy reconciles the money side via the daily drawer/`farysales` ledger (feature_account_closing §6).

---

## 7. Printing

- Backup/archive produce log/verification files rather than printed reports:
  - `History.txt` (backup history), `titan-info.txt`, `internet-backup.txt`.
  - Archive verification: "Titan ZuLastArchiveCheck" (modules_gap_1 §19); archive status report proc (modules_remaining_1).
- Day-close reports may print the archive status (feature_account_closing §7, RPT-H02/H03). Print-template selection for close-adjacent reports: "ادخل رقم نموذج الطباعه من القيم الاتيه 500 600 700 800" (strings_readable:9216).

---

## 8. Tables

### 8.1 titaninn — inter-pharmacy invoice transfer queue
From `schema_complete.sql` table 6:
```sql
CREATE TABLE titaninn (
    id            INT IDENTITY(1,1),            -- PK auto-increment
    fatid         INT DEFAULT '0',              -- group/batch ID of the transferred fat
    itemsasstring NVARCHAR(4000) DEFAULT '',    -- serialized invoice items (خطوط الفاتورة)
    datee         INT DEFAULT 0,                -- date
    source        NVARCHAR(100) DEFAULT '',     -- exporting pharmacy
    silsilaid     NVARCHAR(15) DEFAULT '',      -- chain/series id
    target        NVARCHAR(100) DEFAULT ''      -- importing pharmacy ('' once consumed)
);
-- insert into titaninn (fatid,itemsasstring,datee,source,silsilaid,target) VALUES (...)
-- select * from titaninn where source/target = N'...'
-- update titaninn set target = N''   |  delete from titaninn  |  drop table titaninn
```
This is the backbone of FormImportFat/FormExportFat/FormGetFats/FormTahwil.

### 8.2 usersourceupdate — drug update sync log
From `schema_complete.sql` table 18:
```sql
CREATE TABLE usersourceupdate (
    id          INT IDENTITY(1,1),   -- PK
    drugname    NVARCHAR(100) DEFAULT '',  -- FK→wzdrugs
    price       REAL DEFAULT 0,      -- new price
    units       INT DEFAULT 0,       -- units per pack
    localimport INT DEFAULT 0,       -- import source (0-5)
    datee       REAL DEFAULT 0       -- date (VB6 serial)
);
-- insert into usersourceupdate (drugname,price,units,localimport,...)
-- select drugname from usersourceupdate | SELECT top 3000 * ... WHERE Datee > '...'
-- DELETE FROM usersourceupdate WHERE id='...'
```

### 8.3 remotecontrol — remote function/command log
From `schema_complete.sql` table 16:
```sql
CREATE TABLE remotecontrol (
    id               INT IDENTITY(1,1),   -- PK
    datee            REAL DEFAULT 0,      -- date (VB6 serial)
    mobile           NVARCHAR(15) DEFAULT '',  -- target/owner pharmacy phone
    copyid           NVARCHAR(50) DEFAULT '',  -- copy identifier
    passedfunctions  NVARCHAR(MAX) DEFAULT ''  -- serialized function/command payload
);
-- insert into remotecontrol (datee,mobile,copyid,passedfunctions)
-- select id,datee,passedfunctions from remotecontrol where mobile = N'...'
-- select passedfunctions from remotecontrol where datee > N'...'
-- delete from remotecontrol where id/passedfunctions = N'...'
```

### 8.4 TitanUserAction — audit log carried through backup/sync
`schema_complete.sql` table 17 — drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee.

### 8.5 Support tables
- `titanksasales` / `invoicedata` — the invoices being archived (sales) — archived out of the main table into `\Files\Archive\Output\` (business_logic_complete §2.11).
- `farysales` — branch-level archived sales/money ledger (schema_complete table 27).
- `drgserver` — server drug list synced alongside backups (schema_complete table 15).
- `storediscount` — discount records replicated with `usersourceupdate` flows (schema_complete table 14).

---

## 9. UI strings (Arabic)

### 9.1 Backup
- `حفظ نسخة احتياطية` (10721) — Save a backup
- `حفظ نسخة احتياطية رئيسية اثناء الاغلاق` (10722) — Save a main backup at closing
- `حفظ نسخة احتياطية عبر الانترنت` (10723) — Save an internet backup
- `استرجاع النسخ الاحتياطية` (8759) — Restore backups
- `مجلد النسخ الاحتياطية` (12008) — Backup folder
- `تنظيف النسخ الاحتياطية` / `تنظيف النسخ الاحتياطية القديمة` (10485/10486) — Clean (old) backups
- `تم حفظ نسخة احتياطية علي الانترنت بنجاح` (10440) — Internet backup saved successfully
- `تعديل نظام النسخ الاحتياطي من ساعة الي 3 ساعات في شاشة المبيعات` (10258) — backup frequency 1h→3h
- `تم اعادة ترتيب ونظيم ملفات النسخ الاحتياطية لتسهيل التوصل اليها واسترجاعها` (10376)
- `تم تخفيض مدة النسخ الاحتياطية من 30 يوم الي عشرة ايام مع احتفاظ بنسخة دائمة لكل شهر من الشهور` (10414)
- `سيتم الان تقفيل اليوم بدون اخذ نسخة احتياطية بناءا علي اعداداتك في شاشة اعدادات متقدمة` (11043)
- `سيتم الان حفظ نسخة احتياطية عبر الانترنت` (11046)
- `سيتم حفظ مسار النسخة في مجلد النسخ الاحتياطية في ملف اسمه` (11070)
- `لم نعثر علي نسخة احتياطية حديثة من بياناتك .. سيجري الان حفظ نسخة` (11931)
- `لا يمكن تشغيل البرنامج من مجلد النسخ الاحتياطية قم بنسخة الي مكان اخر` (11707)
- `يحتاج تيتان لحفظ نسخة احتياطية هل تسمح له الان` (12659)
- `يمكن عمل نسخة احتياطية اضافية بشكل تلقائي علي الفلاشة` (12689)
- `يجب الاتصال بخدمة العملاء لمساعدتك علي استرجاع نسخة احتياطية` (12621)
- `عند تلف احد ملفات البرنامج فان النسخ الاحتياطي العادي يتوقف ...` (11333)

### 9.2 Archive
- `أرشفة المبيعات القديمة` (8253) — Archive old sales
- `أرشفة المشتريات القديمة` (8254) — Archive old purchases
- `تخزين فواتير المبيعات القديمة` / `تخزين فواتير المشتريات القديمة` (10121/10122) — Store old sales/purchase invoices
- `ارشفة فواتير المبيعات تشمل ارشفه 20000 فاتورة بدلا من 10000` (8742)
- `الان يمكنك الارشفة الكاملة` (9163) — Full archive now possible
- `تحسن شاشة الارشفة` (10089) — Archive screen improved
- `لقد وصلت الي الحد الاقصي المسموح به من الفواتير ولا يمكنك الاستمرار ...` (11879)
- `تواصل مع ادارة البرنامج للاهمية حيث ان عدد فواتيرك اصبح كبيرا جدا ويحتاج الي ارشفة` (10498)
- `لم تنجح عملية تخزين فواتير المبيعات/المشتريات` (11921–11923)
- `فشلت عملية الارشفة لا يمكنني الاستمرار ...` (11406)
- `وسيتم نقل الاقدم الي الارشفة مع الاحتفاظ بكافة بياناتها واستدعائها في اي وقت` (12557)
- `رقم الفاتورة بعد الارشفة` (10899)
- `برجاء الاتصال بخدمة العملاء لتنفيذ عملية ارشفة المبيعات/المشتريات قبل التحديث` (9929/9930)

### 9.3 Import / export of fat
- `تصدير الفاتورة الي صيدلية اخري` (10186) — Export the invoice to another pharmacy
- `تحويل الفاتورة الي صيدلية اخري` (10112) — Transfer the invoice to another pharmacy
- `استيراد فاتورة محولة من مستودع او صيدلية اخري` (8783) — Import a transferred invoice from a warehouse or another pharmacy
- `فاتورة محولة` (11370) — Transferred invoice
- `تحسين خدمة تصدير الفواتير ما بين افرع الصيدليات` (10094)
- `برجاء تحديد الفواتير التي تريد جمعها من الجدول ادناه` (9919)
- `اختر القيمة التي تود استيرادها` (8375)
- `اختر العميل الذي سيتم نقل الفواتير اليه` (8372)
- `ادخل 800 لتحويل الفاتورة الي مبيعات ... او 600 لتحويلها الي مرتجع مبيعات` (8441)
- `من شريط قوائم الشاشة اختر قائمة تحرير ثم امر تحويل الفاتورة الي مرتجع مبيعات` (12240)
- `تم تحويل الفاتورة` (10413)
- `تصدير الفواتير التي تحتوي علي مشكلة في حساب الاجل` (10083)

### 9.4 Database maintenance
- `اضافة امكانية حذف الفواتير كلها مع الاحتفاظ بارصدة الادوية والعملاء والموردين وهذا من شاشة تصفية قواعد البيانات` (modules_gap_2 §23)
- `الان يمكنك الغاء حفظ الفواتير القديمه` (modules_gap_2 §75–80)

### 9.5 Sync / network
- `Export invoice to another pharmacy` (4585) / `Importing a transferred invoice from another warehouse or pharmacy` (4981) / `Transfer invoice to another pharmacy` (6361)
- `Export database to Excel` (4582), `Export to a batch file` (4592), `Export to file` (4596), `Import from a batch file` (4969), `Import from file` (4971)
- `Pending invoice folder from linked devices` (modules_gap_1 §9)
- `Remote Control`, `Log in as Technical Support` (network_complete §9)

---

## 10. Business rules / edge cases

1. **no-backup folder skips backup** — "Back up is ignored by 'no-backup' folder" — if the destination is inside a folder named `no-backup`, backup is skipped (business_logic_complete §11.2 rule 1; config_complete §5).
2. **Retention policy** — ~10 days of daily backups + one permanent copy per month; "Clean backups" prunes old ones (strings_readable:10414).
3. **Never run from backup folder** — the program refuses to start from inside the backup directory (11707).
4. **Archive capacity** — archive pass handles up to 20,000 invoices; hitting the invoice ceiling forces archiving before more invoices can be saved (8742, 11879, 10498).
5. **Archive before upgrade** — archiving sales/purchases is required before software update (9929–9930).
6. **5-year archive window** — archive processor moves data older than 5 years (modules_remaining_1 archive procs).
7. **Archived data is fully retrievable** — "الاحتفاظ بكافة بياناتها واستدعائها في اي وقت"; read-archived-invoices path exists (12557; modules_remaining_2 §11).
8. **Balances survive archiving/deleting invoices** — drug stock, customer balances and supplier balances are kept when invoices are archived or deleted via تصفية قاعدة البيانات (modules_gap_2 §23; §75–80).
9. **Backup before close is optional** — governed by advanced settings (11043); a "main" backup at close can be forced (10722).
10. **Auto-backup cadence** — every hour to every 3 hours, configurable from the sales screen (10258); FFFbackupAuto performs it.
11. **Internet backup is an explicit separate action** — Create Internet backup uploads the staged `ftpdbi.zip` via FTP/curl; success is confirmed (10723, 10440).
12. **Corrupt-file resilience** — a second backup method that skips corrupt files keeps the chain alive (11333); missing recent backup triggers an immediate fresh save (11931).
13. **Fat transfer routing** — imported fat is routed 800→sales or 600→sales return (8441); a transferred fat can be re-targeted to another customer (8372).
14. **Transfer queue integrity** — `titaninn.target` marks delivery; when empty the fat is available for pick-up; the table can be rebuilt (schema_complete table 6).
15. **Sync-log hygiene** — `usersourceupdate` rows are pulled in batches of 3000 and deleted once applied; `remotecontrol` rows keyed by mobile and purged by id or empty function payload (schema_complete tables 16/18).
16. **Remote control** — technical support may push functions via `remotecontrol` and "Log in as Technical Support"; server-connector logs to `\Files\DB\server.connection.report.txt` (network_complete §8–9).
17. **Group price sharing** — price/units changes flow through `usersourceupdate` to the group ("Share between my group", "Import the prices from old data") (config_complete §18).
18. **Verify monthly presence** — "التحقق من وجود نسخة لكل شهر" — the system checks every month has an archive (feature_account_closing idx 9237).

---

## 11. Reused references

- business_logic_complete.md §11 ModBackup (43 procs), §23 Backup & Cloud Architecture, §2.9 usersourceupdate, §2.10 remotecontrol, §2.11 farysales archive.
- modules_gap_1.md §19 ModBackupMonthly, §9 ModSqlLink, §4 ModFTP.
- modules_gap_2.md §7 FormEnd, §18 FormArchiveBuy, §19 FormArchiveSales, §20 FormBackup, §23 FormDatabase, §8 FormGetFats, §9 FormImportFat, §35 FormExportFat, §36 FormExportFatList, §46 FormImportFatList, §67–68 FormTahwil, §75–80 FormX*.
- modules_remaining_1.md (ModOneFile, archive procs) and modules_remaining_2.md §11 ModArchive.
- network_complete.md §10 Backup System, §11 Export/Import System, §9 Remote Control, §2 FTP, §6 Cloud Sync.
- config_complete.md §5 Backup Paths, §16 File Paths, §18 Branch/Multi-store.
- schema_complete.md / schema_complete.sql tables 6 (titaninn), 16 (remotecontrol), 18 (usersourceupdate), 17 (TitanUserAction), 15 (drgserver).
- feature_account_closing.md (archive/backup at close, Daily.phy, month-close archive paths).
- feature_balances.md (archive of monthly opening/closing balances).