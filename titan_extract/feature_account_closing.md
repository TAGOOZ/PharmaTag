# تقفيل حسابات — Account Closing / Daily Close / End of Day ("تقفيل")

**Purpose:** Full extraction of the account-closing (end-of-day) feature of TITAN.W1 (Phye.exe). This is the daily close workflow (تقفيل اليوم) and month close (تقفيل الشهر) by which the business day/shift is locked, cash drawer is counted (عد الدرج), the day's cash/network sales, purchases, expenses, profit and money movement are aggregated and balanced against expected totals, a difference (عجز / زيادة) is reconciled, daily balances are rolled forward into the next day, and end-of-day / work-period reports (تقرير تقفيل اليوم, تقرير تسليم الدرج, فترة العمل) are printed. It also covers manual daily entries (القيود اليدوية اليومية), the cash-out reasons (خروج نقدية), the money-movement screen (حركة مالية), and the daily-quota screen (حصة يومية). Everything is keyed off the global system date which the close operation advances by one day.

Source: `titan_decompile/` (strings_utf16.txt, strings_readable.txt, pcode_disasm.txt), reused from `business_logic_complete.md` (§10 ModMony, §11 backup), `reports_complete.md` (RPT-H02/H03, RPT-F01/F10, RPT-A04), `reports.md`, `ui_complete.md`, `ui_strings.json`, `modules_gap_2.md` (FormEnd, FormSafiarbah), `modules_remaining_1.md` (ModDailyQuiod, ModDailyManual), `schema_complete.sql` (`farysales`, `invoicedata`, `wzaccfreetree`).

---

## 1. Objects

### 1.1 Core modules / forms (from `pcode_strings.py names`, `ui_forms.json`)

| Object | Type | Procs | Role |
|---|---|---|---|
| **ModEnd** | Module | — | End-of-day logic (close day, advance system date, roll forward balances). |
| **FormEnd** | Form | 13 | نهاية اليوم / إغلاق اليوم — end-of-day procedures: daily closing, shift settlement, report generation, archive old invoices, backup (modules_gap_2 §7). ~2200 bytes. Controls: btnCloseDay, btnArchive, btnBackup, btnReport, dgSummary, txtDate, chkForceClose, lblStatus. |
| **FFFDayEnd** | Form | 25 | نهاية اليوم — the day/month close report engine (reports_complete RPT-H02/H03). pcode ~lines 377311–379427. |
| **FFFDay** | Form | many | Daily data / day advance logic (pcode ~lines 278896–279324); references the day-close process. |
| **ModMony** | Module | 41 | Financial module — invoice tracking, financial reports, cash movement, capital accounts (business_logic_complete §10). |
| **ModDailyQuiod** | Module | 2 | Daily closing/quietus (حصة يومية) — end-of-day reconciliation that totals sales, calculates cash drawer, generates daily summary, closes the day (modules_remaining_1 §15). |
| **FormDailyQuiod** | Form | 16 | حصة يومية / العمليات اليومية السريعة — full daily closing interface (reports RPT-…, ui_form_titles "العمليات اليومية السريعة"). |
| **ModDailyManual** | Module | 8 | Manual daily entries engine — loads/saves manual entries (`daily-manual.phy` / `daily-manual-2.phy`). |
| **FormDailyManual** | Form | 6 | الإدخال اليومي اليدوي — manual daily entries (reports RPT-F10 القيود اليدوية). |
| **FormDailyManual2** | Form | 5 | الإدخال اليومي اليدوي 2 — second manual entry screen; queries `wzaccfreetree` via `' and master =N'` (master-account selection). |
| **FFFMony** | Form | 13 | العمليات المالية — financial operations (money movement). |
| **FormMonyDetails** | Form | 7 | تفاصيل المال — daily cash-flow detail (reports RPT-F01 حركة النقدية اليوم). |
| **FormCorrecyMony** | Form | 4 | تصحيح المال — money correction (reconcile drawer count). |
| **FormUsersMony** | Form | 24 | أموال المستخدمين — per-user sales/money aggregation for the period. |
| **FormSafiarbah** | Form | 3 | تحليل الأرباح — profit / capital analysis (modules_gap_2 §10, ModCapital). |
| **ModBackup / ModBackupMonthly** | Module | 43 | Backup invoked at close — `Titan3-Backup\Daily\` daily archives (business_logic_complete §11). |
| **FormXBackup / FormXRestore** | Form | — | Backup/restore launched from FormEnd. |

### 1.2 Data files involved in closing (from strings_readable.txt)

```
\Files\DBI\Daily.phy          — Daily transaction log (database of the day's money movement)
\Files\DBI\Dailyline.phy      — Daily line items
\Files\DBI\Dailymax.phy       — Daily maximums (Reload_Daily_Max)
\Files\DBI\daily-manual.phy   — Manual daily entries
\Files\DBI\daily-manual-2.phy — Manual daily entries (form 2)
\Files\DBI\MonyInfo.phy       — Money info / balances snapshot
\Files\DBI\fary.date.phy      — Fary (branch) date
\Files\DBI\fary.net.worked.txt
\Files\DB\closefary.phy       — Close-fary flag
\Files\DBI\acctree.phy / acctree2.phy — accounting tree (chart of accounts)
\Files\DBI\RasidCorrect.phy   — balance-correction log
\Labirdo\Titan3-Backup\Daily\  — daily backup archive folder
\Files\Archive\monthy\moves\   — monthly closing journal moves
\Files\Archive\monthy\start-data\ — monthly closing opening data
\Files\Archive\mizan-manual\   — manual trial-balance archive
```

---

## 2. Step-by-step workflow

From `strings_readable.txt` narrative + `business_logic_complete.md` §10 + `modules_gap_2.md` §7:

1. **Enter the close screen** — from the main screen choose قائمة ماليات (Finance menu) → تقفيل اليوم (Close the day). "تذهب الي شاشة تقفيل اليوم من خلال قائمة ماليات في شريط القوائم بالشاشة الرئيسية للبرنامج" (idx 10125) and "ثم توجه الي الشاشة الرئيسية للبرنامج واختر قائمة ماليات ومنها اختر امر تقفيل اليوم" (idx 10545). "الطريقة المثالية هي تقفيل اليوم من قائمة ماليات" (idx 9460). Alternative entry: "الي شاشة تقفيل اليوم" (idx 9770); screen title "شاشة اغلاق وتقفيل اليوم" (idx 11089) / "انهاء وتقفيل اليوم" (idx 9831).

2. **Time-of-day guard** — the current day can only be closed after 1:00 PM: "لا يمكن تقفيل اليوم الحالي الا بعد الواحدة ظهرا" (idx 887). If already closed: "لقد تم تقفيل اليوم فعليا" (idx 890).

3. **Optional backup** — before closing, the system may take a daily backup. "سيتم الان تقفيل اليوم بدون اخذ نسخة احتياطية بناءا علي اعداداتك في شاشة اعدادات متقدمة" (idx 11043) — backup behavior is controlled by advanced settings. "تخزين فواتير المبيعات القديمة" / "تخزين فواتير المشتريات القديمة" (archive old invoices at close).

4. **Count the cash drawer (عد الدرج)** — the system prompts to count the drawer and type the physical count: "تظهر لك شاشة تطالبك بعد الدرج فقم بذك وابلغ البرنامج القيمة الموجودة" (idx 10226), "تعد الدرج وتكتب القيمة في الحقل المخصص لذلك" (idx 10230). Note: "المدير ومساعده فقط يحق لهم الخروج دون عد الدرج" (idx 9649) — only manager/assistant may log out without counting the drawer. The expected amount = current drawer less the drawer at start of period plus any cash that left the drawer during the period for any reason: "اجمالي الدرج حاليا مطروح منه الدرج عن بداية الفترة ومضافا اليه اي نقدية خرجت من الدرج اثناء الفترة لاي سبب" (idx 8305).

5. **Aggregate the day** — total sales, purchases, expenses, money movement, VAT, checks, discounts for the day; compute expected cash and network totals. Columns: "التاريخ-كاش - كاش يدوي-شبكة- شبكة يدوي -عجز زيادة-محسوب المبيعات- صافي اليوم كاش- صافي اليوم شبكة - تكلفة مبيعات اليوم-ربح اليوم - شكك اليوم - خصومات اليوم - مشتريات اليوم - مصروفات اليوم - حركة مالية - الضريبة في المبيعات اليوم - الضريبة في المشتريات اليوم - الضريبة في المصروفات اليوم - الشركات حتي الان - اجل العملاء حتي الان - شراء غير شامل - جمهور حتي الان شامل - الكاش حتي الان - البنوك حتي الان - راس المال" (idx 9232, also idx 9228 and idx 9233).

6. **Reconcile difference (عجز / زيادة)** — the counted amount vs computed expected; difference is recorded. "عجز زيادة" column (idx 9232/9233); corrections "تصحيح الارصدة بالزيادة" / "تصحيح الارصدة بالعجز" (idx 10174/10175). Manual corrections may be edited from the pharmacy-date screen: "تم اضافة امكانيةتعديل قيمة نقدية تقفيل اليوم من شاشة تاريخ الصيدلية" (idx 10365).

7. **Manual money movement** — remaining cash-out / cash-in for the day recorded under ماليات → مصروفات وواردات → حركة مالية: "اذا كنت تقوم بهذا فعلا فقم باخراج باقي القيمة من الشاشة الرئيسية ثم ماليات ثم مصروفات وواردات ثم حركة مالية" (idx 8703). Manual money entries aggregated at close: "اضافة تقرير لتجميع المدفوع يدويا عند تقفيل اليوم" (idx 8954).

8. **Manual daily entries (القيود اليدوية)** — FormDailyManual / FormDailyManual2 let the user post manual journal entries for the day (reports RPT-F10), with an entry description required: "ادخل وصف القيد اولا" (idx 8637). These are stored in `daily-manual.phy` / `daily-manual-2.phy`.

9. **Confirm and save the close** — "تم اعادة حفظ بيانات تقفيل اليوم" (idx 10378); the day is marked closed and **the system date advances one day forward**: "كل امر تقفيل يغير تاريخ البرنامج يوم للامام فهذا يعني انك يجب ان تنفذ هذا الامر اكثر من مرة حتي يتم تصحيح تاريخ تيتان" (idx 883). "لقد تم تقفيل اليوم فعليا" (idx 890).

10. **Print the day-close report** — optionally print day data during closing: "اضافة امكانية طباعة بيانات اليوم اثناء التقفيل ويجب تفعيلها اولا من شاشة اعدادات متقدمة" (idx 8944). Report: تقرير تقفيل اليوم (RPT-H02) via FFFDayEnd.

11. **Shift close integration** — closing the day also closes the shift: "تعديل طريقة تفعيل اليوم بحيث يتم تقفيل الشفت ايضا اثناء عملية تقفيل اليوم" (idx 10251); "تغيير جزري علي نظام تقفيل الشيفت حيث اصبح مرنا وسهلا" (idx 10277). Drawer handover report: "تقارير تسليم الدرج بين الفترات" (idx 10320); shift sales inquiry "استعلام مبيعات الشفتات" (idx 8763). A shift can be kept open while the employee logs out: "امكانية خروج الموظف مع الابقاء علي الشيفت" (idx 9801).

12. **Month close (تقفيل الشهر)** — monthly closing aggregates the month: تقرير تقفيل الشهر (RPT-H03) via FFFDayEnd; "تقفيل الشهر" (idx 10332); monthly data under `\Files\Accounting\monthly\` and `\Files\Archive\monthy\moves\`, `\Files\Archive\monthy\start-data\` (monthly closing opening data). "التحقق من وجود نسخة لكل شهر" (idx 9237). "Monthly Accounting المحاسبة الشهرية Files\Accounting\monthly\" (reports.md B).

13. **Delete unnecessary daily closings** — "اذالة تقفيلات اليوم الغير ضرورية" (idx 8707) — admin may remove non-essential daily closing records.

---

## 3. Fields / data captured

### 3.1 Day-close aggregation fields (reports_complete RPT-H02 columns)

```
Date, Opening Balance, Total Sales, Total Returns, Total Purchases,
Expenses, Cash Received, Card Received, Closing Balance, Difference
```

### 3.2 Day-close detailed fields (idx 9232 / 9228 / 9233 — raw column lists)

```
التاريخ (Date)
كاش (Cash), كاش يدوي (Manual cash), شبكة (Network/card), شبكة يدوي (Manual network)
عجز / زيادة (Shortfall / Surplus)
محسوب المبيعات (Calculated sales)
صافي اليوم كاش (Today's net cash), صافي اليوم شبكة (Today's net network)
تكلفة مبيعات اليوم (Today's cost of sales)
ربح اليوم (Today's profit)
شيك اليوم (Today's checks)
خصومات اليوم (Today's discounts)
مشتريات اليوم (Today's purchases)
مصروفات اليوم (Today's expenses)
حركة مالية (Money movement)
الضريبة في المبيعات اليوم (VAT in today's sales)
الضريبة في المشتريات اليوم (VAT in today's purchases)
الضريبة في المصروفات اليوم (VAT in today's expenses)
الشركات حتي الان (Companies to date)
اجل العملاء حتي الان (Customer credit to date)
شراء غير شامل (Purchase excl. VAT)
جمهور حتي الان شامل (Public/retail to date incl. VAT)
الكاش حتي الان (Cash to date)
البنوك حتي الان (Banks to date)
راس المال (Capital)
```

### 3.3 Work-period / shift fields

- Period start/end: "اختر بداية الفترة" (idx 8378), "اختر نهاية الفترة" (idx 8397), "ادخل تاريخ بداية الفترة" (idx 8519), "ادخل تاريخ انتهاء الفترة" (idx 8518), "تاريخ بداية الفترة"/"تاريخ انتهاء الفترة" (idx 10034/10033), "رقم الفترة" (idx 10905).
- Period sales: "ادخل مبيعات الفترة هذا اليوم" (idx 8613), "ادخل مبيعات الفترة الحالية" (idx 8614), "ادخل مبيعات الموظف خلال الشفت الحالي" (idx 8615), "الاجمالي عن الفترة" (idx 9089).
- Note: "توضيح هام المطلوب هو اجمالي مبيعات الفترة وليس نقدية الدرج الان" (idx 10512) — the figure required is period sales, not current drawer cash.
- Drawer: "الدرج" (idx 9327), "الدرج المتصل بالطابعة" (idx 9328), "الدرج المتصل مباشرة بالكمبيوتر" (idx 9329), "فتح الدرج اثناء حفظ الفواتير" (idx 11380), "طوال هذا اليوم سيتم فتح الدرج المتصل بالطابعة مع كل عملية حفظ" (idx 11235).

### 3.4 Money-movement fields (حركة مالية)

```
رقم العملية (Operation#), تاريخ (Date), وارد (In), صادر (Out), الوصف (Description)  (idx 10892)
مصروفات نقدية، مصروفات شبكة، حركة نقدية ايداع، حركة شبكة ايداع، حركة نقدي سحب، حركة شبكة سحب  (idx 12137)
```

### 3.5 Manual journal-entry fields (FormDailyManual / reports RPT-F10)

```
Date, Entry Type, Amount, Description, Employee
```
Entry description mandatory: "ادخل وصف القيد اولا" (idx 8637).

### 3.6 Cash-out / cash-in reasons (خروج نقدية / دخول نقدية)

```
خروج مال من المشروع - توزيع ارباح          (idx 10757) — capital withdrawal / profit distribution
خروج نقدية نتيجة ارتجاع ادوية في المبيعات   (idx 10758) — cash out from sales returns
خروج نقدية نتيجة الدفع للشركات              (idx 10759) — cash out from supplier payments
دخول نقدية نتيجة ارتجاع الدفع من الشركات    (idx 10835) — cash in from supplier refunds
نقدية خرجت عن طريق شاشة المبيعات في شكل مرتجع ادوية او خروج نقدية لعميل باي شكل (idx 12342)
```

---

## 4. Side-effects

- **System date (global):** each close advances the program date one day forward (idx 883); the pharmacy-date screen can adjust the closing cash value (idx 10365).
- **Money / ledger:** daily transaction log `Daily.phy` + `MonyInfo.phy` balances snapshot; money movement (حركة مالية) recorded with in/out amounts; bank and cash positions (البنوك حتي الان / الكاش حتي الان) tracked.
- **Chain sales:** `titanksasales` (per-day sales summary) and `invoicedata` (line items) feed the day totals.
- **Customers / suppliers:** accrued balances (اجل العملاء, الشركات/مستحقات الموردين) rolled forward.
- **Fary (branch):** `farysales` table + `fary.date.phy`, `closefary.phy` record branch-level closing; monthly fary data in `\Files\Archive\monthy\`.
- **Stock:** purchases/prices unchanged by close itself; but balances (ارصدة) roll into next day. "انشاء مجلد داخل مجلد النسخ الاحتياطية ليحتفظ بسجل يومي للارصدة" (idx 9224) — a daily balance-history folder is created inside the backup folder.
- **Archive:** old invoices archived at close (تخزين فواتير المبيعات/المشتريات القديمة); monthly moves in `\Files\Archive\monthy\moves\`.
- **Backup:** daily archive under `Labirdo\Titan3-Backup\Daily\` (business_logic_complete §11; idx 6656 `Titan3-Backup\Daily\`).
- **Shift/drawer handover:** shift closed with the day; drawer handover report (تسليم الدرج بين الفترات) generated.

---

## 5. Pricing + VAT

Closing does not price drugs, but it sums VAT by bucket:
- "الضريبة في المبيعات اليوم" / "الضريبة في المشتريات اليوم" / "الضريبة في المصروفات اليوم" (idx 9232) — sales VAT, purchase VAT, expense VAT aggregated per day.
- Period VAT: "ادخل نسبة الضربية الموجودة في الفترة المختارة" (idx 8630); "ادخل اجمالي المبلغ شامل الضريبة لكل الفترة" (idx 8443).
- VAT-tag `<masrofat-vat>` (expense VAT) is live in the money/expense pipeline (per feature_notes §22).
- Period report VAT columns (RPT-F07/F08) come from `FormVat`/`FormVat2`, not the close itself.

---

## 6. Payment methods

Cash / Network (شبكة, cards) split tracked through the close:
- "كاش" (cash) and "شبكة" (network/card), each with a manual variant (كاش يدوي / شبكة يدوي) and a net-per-day figure (صافي اليوم كاش / صافي اليوم شبكة) (idx 9232/9233).
- Cash received vs card received in day-close report (RPT-H02: Cash Received, Card Received).
- "اجمالي المدفوع فيزا اليوم" (Total Visa paid today, idx 8318).
- Checks: "شكك اليوم" (Today's checks, idx 9232).
- Payment types from business_logic_complete §10.2: Cash, Cash PC, Cards paid, Paid, Payable amount, Relayed amount.

---

## 7. Printing

- **Day-close report** (تقرير تقفيل اليوم, RPT-H02) via **FFFDayEnd** (25 procs).
- **Month-close report** (تقرير تقفيل الشهر, RPT-H03) via **FFFDayEnd**.
- **Work-period report** (فترة العمل) via FFFDayEnd (reports.md A).
- **Drawer handover report** (تقارير تسليم الدرج بين الفترات, RPT-A04) — FormTaslimReport.
- **Manual-entry report** (RPT-F10 القيود اليدوية / Manual adjustment report) — FormDailyManual; "Manual adjustment report" (modules_remaining_1 §14).
- **Money details / cash flow** (حركة النقدية اليوم, RPT-F01) — FormMonyDetails.
- **Money-movement report** (تقرير الواردات والمصروفات, idx 10326) — revenue vs expenses.
- Print template selector for closing-adjacent reports: "ادخل رقم نموذج الطباعه من القيم الاتيه 500 600 700 800" (idx 9216) — enter the print-template number among 500/600/700/800.
- Optional printing of day data during closing must be enabled in advanced settings (idx 8944).

---

## 8. Tables

### 8.1 farysales — daily/branch ledger (journal of money movements & balances)
From `strings_readable.txt` line 181 (INSERT column list) + `schema_complete.sql` table 27 (reconstructed).

```sql
CREATE TABLE farysales (
    mobile       NVARCHAR(15) DEFAULT '' NOT NULL,   -- [EXPLICIT] pharmacy phone
    grand        REAL         DEFAULT 0,             -- [INFERRED] grand total
    father       NVARCHAR(100) DEFAULT '',           -- [INFERRED] parent/master account
    son          NVARCHAR(100) DEFAULT '',           -- [INFERRED] child account
    datee        REAL         DEFAULT 0,             -- [INFERRED] date (VB6 serial)
    datetimee    DATETIME,                           -- [INFERRED] datetime
    dateemanual  REAL         DEFAULT 0,             -- [INFERRED] manual entry date
    monthe       NVARCHAR(10) DEFAULT '',            -- [INFERRED] month
    yearo        NVARCHAR(10) DEFAULT '',            -- [INFERRED] year
    payed        REAL         DEFAULT 0,             -- [INFERRED] amount paid
    creditdebit  NVARCHAR(20) DEFAULT '',            -- [INFERRED] credit/debit flag
    typee        NVARCHAR(50) DEFAULT '',            -- [INFERRED] type
    phar         NVARCHAR(15) DEFAULT '',            -- [INFERRED] pharmacy ID
    randomid     NVARCHAR(50) DEFAULT '',            -- [INFERRED] unique ID
    tips         NVARCHAR(50) DEFAULT '',            -- [INFERRED] notes
    writer       NVARCHAR(50) DEFAULT '',            -- [INFERRED] entered by
    classy       NVARCHAR(35) DEFAULT ''             -- [INFERRED] category
);
-- Live usage: SELECT * FROM farysales WHERE mobile = N'...'   (strings_readable line 773)
-- This is the primary per-day/per-branch money ledger; the father/son columns map to
-- the chart-of-accounts tree (wzaccfreetree), creditdebit marks debit/credit sides.
```

### 8.2 wzaccfreetree — accounting chart-of-accounts tree
From `schema_complete.sql` table 25 + `strings_readable` line 7604.

```sql
CREATE TABLE wzaccfreetree (
    id       INT IDENTITY(1,1),           -- [INFERRED] auto-increment PK
    mobile   NVARCHAR(15) DEFAULT '',     -- [EXPLICIT] pharmacy phone
    master   NVARCHAR(100) DEFAULT '',    -- [EXPLICIT] master account (parent)
    fary     NVARCHAR(100) DEFAULT ''     -- [EXPLICIT] sub-account / leaf account
);
-- INSERT INTO wzaccfreetree (mobile,master,fary) VALUES (...)   (line 7604)
-- Lookups use "and master =N'" (FormDailyManual2, idx 1279)
```

### 8.3 invoicedata — daily invoice/line source
`schema_complete.sql` table 11 — supplies day totals (invoiceid, datee, pharmacyid, payed, disc, totalvalue, IdDateTime, Quant, DrugName, SellDisc, price …).

### 8.4 titanksasales — chain sales summary
`schema_complete.sql` table 7 — invoiceid, datee, silsilaid, pharmacyid, payed, disc, agel, totalvalue; feeds daily sales totals.

### 8.5 Day-close file backing (not SQL)
`Daily.phy`, `Dailyline.phy`, `Dailymax.phy`, `MonyInfo.phy`, `daily-manual.phy`, `daily-manual-2.phy`, `fary.date.phy`, `closefary.phy`, `acctree.phy` — VB6 sequential/random `.phy` files holding the day's money ledger, balances and manual entries.

---

## 9. UI strings (Arabic)

### 9.1 Screen titles & menu
- `تقفيل اليوم` (idx 10333) — Close the day
- `تقفيل الشهر` (idx 10332) — Close the month
- `اغلاق و تقفيل` / `اغلاق وتقفيل` (idx 9051/9052) — Close & settle
- `شاشة اغلاق وتقفيل اليوم` (idx 11089) — Day close & settle screen
- `انهاء وتقفيل اليوم` (idx 9831) — Finish & close the day
- `الي شاشة تقفيل اليوم` (idx 9770) — Go to the day-close screen
- `الطريقة المثالية هي تقفيل اليوم من قائمة ماليات` (idx 9460) — Best way: close the day from the Finance menu
- `الي نهاية يوم` (idx 9768) — to end of day
- `ماليات` — Finance menu (money/finance)
- `تسليم الدرج بين الفترات` — drawer handover between periods
- `فترة العمل` — work period

### 9.2 Messages (errors / info / confirm)
- `لا يمكن تقفيل اليوم الحالي الا بعد الواحدة ظهرا` (idx 887) — Cannot close today before 1 PM
- `لقد تم تقفيل اليوم فعليا` (idx 890) — The day is already actually closed
- `كل امر تقفيل يغير تاريخ البرنامج يوم للامام...` (idx 883) — Each close advances the program date one day forward
- `سيتم الان تقفيل اليوم بدون اخذ نسخة احتياطية بناءا علي اعداداتك...` (idx 11043) — Closing without backup per advanced settings
- `تم اعادة حفظ بيانات تقفيل اليوم` (idx 10378) — Day-close data re-saved
- `تم تحسين شاشة تقفيل اليوم` (idx 10411) — Day-close screen improved
- `تم حفظ كافة الفواتير ما عدا الفارغة` (idx 9206) — All invoices saved except empty ones
- `تظهر لك شاشة تطالبك بعد الدرج فقم بذك وابلغ البرنامج القيمة الموجودة` (idx 10226) — Count-drawer prompt
- `المدير ومساعده فقط يحق لهم الخروج دون عد الدرج` (idx 9649) — Only manager/assistant may exit without counting the drawer
- `اضافة امكانية طباعة بيانات اليوم اثناء التقفيل ويجب تفعيلها اولا من شاشة اعدادات متقدمة` (idx 8944)
- `تم استحداث شاشة تظهر كافة المؤثرات علي مالية الدرج اثناء اليوم للمراجعة وهي موجودة في قائمة ماليات` (idx 10351) — new screen showing all effects on drawer cash for review
- `تعديل طريقة تفعيل اليوم بحيث يتم تقفيل الشفت ايضا اثناء عملية تقفيل اليوم` (idx 10251)

### 9.3 Columns / labels
- `عجز زيادة` — shortfall / surplus
- `محسوب المبيعات` — calculated sales
- `صافي اليوم كاش` / `صافي اليوم شبكة` — today's net cash / network
- `تكلفة مبيعات اليوم` / `ربح اليوم` / `شكك اليوم` / `خصومات اليوم` / `مشتريات اليوم` / `مصروفات اليوم` / `حركة مالية` (idx 9232/9233)
- `الشركات حتي الان` / `اجل العملاء حتي الان` / `شراء غير شامل` / `جمهور حتي الان شامل` / `الكاش حتي الان` / `البنوك حتي الان` / `راس المال` (idx 9228/9232)
- `اجمالي الدرج حاليا مطروح منه الدرج عن بداية الفترة ومضافا اليه اي نقدية خرجت من الدرج اثناء الفترة لاي سبب` (idx 8305)
- `اجمالي النقدية` (idx 8324), `اجمالي المدفوع فيزا اليوم` (idx 8318), `اجمالي المصروفات` (idx 8319), `اجمالي المصروفات خلال الفتره` (idx 8320), `اجمالي مدفوعات المشتريات خلال الفتره` (idx 8338), `اجمالي مبيعات الفترة هو 2000 جنيه وليس 1400 جنيه لان المنصرفات لا تحتسب` (idx 8336)
- `رقم العملية تاريخ وارد صادر الوصف` (idx 10892)
- `مصروفات نقدية مصروفات شبكة حركة نقدية ايداع حركة شبكة ايداع حركة نقدي سحب حركة شبكة سحب` (idx 12137)
- `مصروفات و واردات` (idx 12138), `تقرير الواردات و المصروفات` (idx 10326)
- `قيد` / `ادخل وصف القيد اولا` (idx 8637)
- `خروج مال من المشروع- توزيع ارباح` (idx 10757)

---

## 10. Business rules / edge cases

1. **1 PM rule:** the current day cannot be closed before 1:00 PM (idx 887).
2. **Date advance:** each close moves the program date one day forward; if the date drifts, run the close more than once to correct Titan's date (idx 883). Date is protected: "غير مسموح بتغير التاريخ الا بهذه الطريقة حفاظا علي الحسابات الدقيقة للبرنامج" (idx 12032).
3. **Idempotency:** once closed, the day is marked closed ("لقد تم تقفيل اليوم فعليا"); repeated close blocked or detected.
4. **Drawer count:** physical drawer must be counted and entered unless the actor is the manager/assistant (idx 9649). The expected drawer = opening + sales − outflows (idx 8305).
5. **Sales vs drawer distinction:** the required figure is total period sales, NOT the current drawer cash (idx 10512). Expenses taken from the drawer do not reduce sales totals: "اجمالي مبيعات الفترة هو 2000 جنيه وليس 1400 جنيه لان المنصرفات لا تحتسب" (idx 8336); "بمعني انك لو قمت ببيع فاتورتين بقيمة 500 جنيه وقمت بشراء ادوية بقيمة 300 جنيه فان اجمالي المبيعات هو 500 بينما الدرج 200 فقط" (idx 9963).
6. **Cash-out handling:** any cash leaving the drawer during the day (returns, supplier payment, capital withdrawal, salaries, rent) should be moved from the drawer to the treasury (الخزينة) and settled properly, otherwise the close will lock on the wrong value: "بغض النظر عن المصروفات" / idx 9902, 10966, 9844.
7. **Salary example:** paying a 700-EGP salary straight from the drawer then closing locks only the net; better to transfer to the treasury first, then expense from مصروفات (idx 10966, 12001).
8. **Shift coupling:** closing the day also closes the open shift (idx 10251); an employee may log out while keeping the shift open (idx 9801).
9. **Manual cash override:** the closing cash value may be adjusted from the pharmacy-date screen (idx 10365).
10. **Backup configurable:** closing may skip backup per advanced settings (idx 11043).
11. **Non-essential closing removal:** admin can remove unnecessary day closings (idx 8707).
12. **Money movement reconciliation screen:** a dedicated screen under Finance lists all effects on drawer cash during the day for review (idx 10351); expected actual money movement entered via مصروفات وواردات → حركة مالية (idx 8703).
13. **Persistence files:** day ledger in `Daily.phy` + `MonyInfo.phy`; manual entries in `daily-manual.phy`/`daily-manual-2.phy`; branch close flag in `closefary.phy`.
14. **Finance menu (ماليات)** is the canonical entry for closing, manual entries and money movement.

---

## 11. Reused references

- business_logic_complete.md §10 ModMony (financial ops, payment types, calculations), §11 backup.
- reports_complete.md RPT-H02/H03 (day/month close), RPT-F01 (cash flow), RPT-F10 (manual entries), RPT-A04 (drawer handover).
- reports.md A (daily reports) & B (monthly reports).
- modules_gap_2.md §7 FormEnd, §10 FormSafiarbah.
- modules_remaining_1.md §14 ModDailyManual, §15 ModDailyQuiod.
- schema_complete.sql tables 7, 11, 25, 27.
- ui_complete.md form title table (FormDailyQuiod=حصة يومية, FormEnd=الإغلاق والنهاية, etc.).
