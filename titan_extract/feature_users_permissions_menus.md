# المستخدمون والصلاحيات والقوائم — Users, Permissions & Menus

**Purpose:** Full extraction of the TITAN.W1 (Phye.exe) user-management feature: the user master (username = 17-digit numeric ID, password/باسورد, mobile, type), the 8 user types and the **1–9 numeric permission level** (صلاحية) that gates features, how permissions gate operations («لا تملك صلاحية البيع الاجل», permission ≥ 7 for balance edits, technical-support permissions, manager-only actions), the per-user **menu system** (which screens/menus each user sees), employee management (FormEmployee, FFFAML, ModAmil2 shifts/attendance, FormHodour), user activity/audit (`TitanUserAction`), per-user money aggregation (`FormUsersMony`, تسليم مبيعات الموظفين، تسليم الدرج), the login flow (login-h.phy, us.phy), and password rules.

Sources reused: `permissions_complete.md`, `modules_gap_2.md` (FFFUserEdit/FFFUserList/FFFUserMenu/FFFUserMenuList/FormMenusPerUser/FormUsersGuide/FormUserGuide/FormEmployee), `modules_gap_1.md` (§8 ModAmil2), `modules_remaining_1/2.md`, `ui_complete.md` (Employees & Shifts forms), `business_logic_complete.md` (§2.5/§2.9), `schema_complete.sql` (tables 17/18 + ChainBuyUsers), `schema_mapping.md`, `drugeye_complete.md` (§5.3), `config_complete.md`, `feature_balances.md`, `feature_account_closing.md`, `feature_stock_counting.md`. Ground truth: `titan_decompile/strings_readable.txt` (line refs), `strings_utf16.txt`, `pcode_disasm.txt`.

---

## 1. Objects

### 1.1 User-master / account forms

| Object | Type | Procs | Role |
|---|---|---|---|
| **FFFUserEdit** | Form | 18 | تعديل بيانات المستخدم — edit user: username, password change, role, shift, permission toggles (modules_gap_2 §1; pcode start=160234+) |
| **FFFUserChoose** | Form | 19 | user selection/picker, filter by group (permissions_complete §8; pcode start=162651+) |
| **FFFNUserEdit** | Form | — | New-user creation screen (modules_gap_2 form family) |
| **FFFUserList** | Form | — | قائمة المستخدمين — user directory, select for edit (modules_gap_2 §12) |
| **FFFUserMenu** | Form | — | قائمة المستخدم / صلاحيات القوائم — per-user menu access assignment (modules_gap_2 §13) |
| **FFFUserMenuList** | Form | — | قائمة قوائم المستخدمين — master list of menu-permission sets/templates (modules_gap_2 §14) |
| **FormMenusPerUser** | Form | — | قوائم المستخدمين — assign screen/menu access per user, «اختبر الصلاحيات» test button (modules_gap_2 §52) |
| **FormEmployee** | Form | — | بيانات الموظفين / العاملين — employee directory, roles, shifts, permissions (modules_gap_2 §34) |
| **FormUsersGuide** / **FormUserGuide** / **FormGuide** | Form | — | دليل المستخدمين / دليل المستخدم / الدليل — in-app help/guide browsers (modules_gap_2 §42/70/71) |
| **FormMain** | Form | — | الشاشة الرئيسية — main hub; menu + status bar + current user (modules_gap_2 §50) |
| **FormMenu** | Form | — | القائمة — navigation tree shown per permissions (modules_gap_2 §51) |

### 1.2 Employee / shift / attendance objects

| Object | Type | Procs | Role |
|---|---|---|---|
| **ModUsers** | Module | — | User-management core referenced by FFFUserEdit/List/Menu/FormEmployee (modules_gap_2 cross-ref) |
| **ModAmil2** | Module | 9 | Employee module 2 — shifts/attendance: shift-in/out, attendance logging, employee sales inquiry, attendance barcode printing; reads/writes `Files\DBI\amil2.phy` + `Files\DBI\AmilInfo.phy` (modules_gap_1 §8) |
| **ModAmil** | Module | many | Core employee module (pcode start=67432+) |
| **FFFAML** | Form | 14 | العاملين — employee management (ui_complete §Employees) |
| **FormAmilTakarir** | Form | 23 | تقارير العاملين — employee reports |
| **FormAmilShow** | Form | 9 | عرض الموظف — employee display |
| **FormAmilHistory** | Form | 3 | تاريخ الموظف — employee history |
| **FormAmilTamin** / **FormAmilTamin2** | Form | 16 / 10 | رواتب الموظفين — employee salaries (v1/v2) |
| **FormHodour** | Form | 16 | الحضور والانصراف — attendance (basic) |
| **FormHodour19** | Form | 35 | الحضور المتقدم — attendance (advanced) |
| **FormShiftFawateer** | Form | 9 | فواتير الوردية — shift invoices |
| **FormShiftInput** | Form | 9 | ادخال الوردية — shift input |
| **FormAmilHistory / FormUserEhsa** | Form | 3 / 12 | employee/user statistics |

### 1.3 Money-per-user / audit objects

| Object | Type | Procs | Role |
|---|---|---|---|
| **FormUsersMony** | Form | 24 | اموال المستخدمين — per-user money/sales aggregation (ui_complete; pcode start=639358+) |
| **FormMonyDetails** | Form | 7 | تفاصيل المال — daily cash-flow detail |
| **FormShiftFawateer** | Form | 9 | فواتير الوردية — per-shift invoice list |
| **FormHistory / FormJournal** | Form | — | سجل الانشطة / اليومية — user-activity audit trail (modules_gap_2 §44/49) |
| **FormDrugHistory** | Form | — | drug change history — fed from `TitanUserAction` (schema_mapping.md:235) |
| **TitanUserAction** | Table | — | audit log: drug/old/new/barcode/price/units/user/date (schema_complete.sql table 17) |
| **usersourceupdate** | Table | — | cross-pharmacy drug update sync queue (schema_complete.sql table 18) |

---

## 2. Step-by-step workflow

### 2.1 Login flow (تسجيل الدخول)
1. **Identify the pharmacy.** The mobile number is the pharmacy master key: «ادخل رقم موبايل صحيح ليتخدم ككود لنسختك علي السيرفر» (strings_readable.txt:8567); «برجاء ادخال رقم موبايل مخصص لصيدليتك او مؤسستك» (:9900); «برجاء ادخال رقم الموبايل للصيدلية من قائمة العملاء» (:9899). A unique mobile «لا يمكن تكراره لصيدلية اخري» (:8566).
2. **Enter username** — «ادخل اسم المستخدم وهو رقم طويل مكون من 17 رقم» (:8457) — the username is a **17-digit numeric ID** (modules_gap_2 §1). Also «ادخل اسم الحساب» (:8447), «ادخل رقم المستخدم» (:826).
3. **Enter password** — «ادخل كلمة المرور» (:8598). Manager login additionally asks «ادخل كلمة المرور الخاصة بالمدير» (:8600); technical-support login uses «ادخل كلمة المرور وتحصل عليها من الدعم الفني» (:8601).
4. **Validate** — «ادخل معلومات صحيحة في اسم المستخدم وكلمة المرور» (:8618); on mismatch «اسم المستخدم الذي ادخلته خاطئا يبدو برجاء الرجوع للايميل الخاص بك» (:8807). English messages: `Invalid Username or Password.`, `Username cannot be null.`, `Username is empty.`, `Password is empty.`, `Invalid user.` (permissions_complete §4).
5. **Login mode** (permissions_complete §2; strings):
   - «الدخول بحساب الادارة» (:9322) — management account
   - «الدخول بحساب العمليات» (:9323/9324) — operations account
   - «الدخول كمدير دون تسجيل خروج المستخدم الحالي» (:9325) — manager overlay w/o logout; «الان يمكنك فتح كافة الشاشات دون الحاجة لخروج المستخدم الحالي» (:9167); capped at 5 minutes: «تحديد مدة دخول المدير مع مستخدم اخر في نفس الوقت ب 5 دقائق» (:10084)
   - «تسجيل الدخول كدعم فني» (:10133); «ادخل بحساب الدعم الفني» (:8515)
   - «اخفاء كلمة المرور عند محاولة التسجيل الدخول كمدير دون خروج المستخدم الحالي» (:8423) — hide password when logging in as manager
   - Manager logout by typing 0: «ادخل الرقم صفر لتسجيل الخروج من حساب المدير» (:8431)
6. **Redirect** — «بعد تسجيل الدخول يقوم تيتان بتوجيهك مباشرة الي الشاشة التي كنت ترغب بزيارتها قبل تسجيل الدخول» (:9947) — return to the pre-login screen.
7. **Logout** — «تسجيل الخروج» (:10132), «تم تسجيل الخروج» (:10415). End-of-day/day-close (تقفيل) advances the program date and closes shifts: «كل امر تقفيل يغير تاريخ البرنامج يوم للامام» (:883), «لا يمكن تقفيل اليوم الحالي الا بعد الواحدة ظهرا» (:887), «تعديل طريقة تفعيل اليوم بحيث يتم تقفيل الشفت ايضا اثناء عملية تقفيل اليوم» (:10251). Session history stored in `Files\DBI\login-h.phy` (strings_readable.txt:6799); user settings in `Files\DBI\us.phy` (config_complete §16).

### 2.2 Creating / editing a user (FFFUserEdit, FFFNUserEdit)
1. Add user with username/password/mobile/type/shift (modules_gap_2 §1: `txtUsername`, `txtPassword`/`txtNewPassword`, `cmbRole` مدير/دعم فني/صيدلي/موظف, `cmbShift`, `chkPermissions[]` خصم/تعديل سعر/حذف فاتورة).
2. **Enter permission level** — «ادخل صلاحية الموظف الحالي من واحد الي تسعة» (FFFStartUp, strings_readable.txt:8572 / idx 9220); «ادخل الصلاحية كما تنطقها او تسعمها» (:8492). Invalid value: «الصلاحية غير مقبوله» (:9443).
3. First-time user gets base permissions: «تم منح هذا المستخدم الصاحايت الاساسية ويمكنك الاضافة اليها والحذف منها كما تشاء» (modules_gap_2 §34).
4. **Employee limit:** «لم يعد ممكنا اضافة موظفين جدد : يمكنك اضافة الموظف الجديد في مكان موظف قديم فقط بتغيير الاسم» (:894) — the app enforces a fixed employee slot count; a new employee must replace an old one by renaming.
5. Only the manager edits others: «المدير فقط يستطيع تغيير مدخلات المستخدمين الاخرين» (:9647), «المدير فقط يمكنه تعديل مدخلات الايام السابقة» (:9648).
6. Password change by user: «تغيير كلمة المرور الخاصة بي» (:10280); requires «برجاء ادخال كلمة المرور الحالية الخاصة بك» (:9901).

### 2.3 Permission gating (الصلاحية 1–9)
- Level is a single **integer 1–9** per employee (permits the 8 documented user types, see §3).
- **Level 9 = full manager:** «الصلاحية 9 يعني انك تمنح هذا الموظف كافة صلاحيات المدير في اي شاشة له حق الولوج اليها» (:9442).
- **Level 1 = minimal:** «بينما الصلاحية 1 فهي صلاحية منخفضة للغاية ينتج عن ذلك منعه من استخدام ادوات كثيرة داخل الشاشات التي تم منحها اليه» (:10004).
- Feature gates fire at runtime, e.g. credit sales: «لا تملك صلاحية البيع الاجل يمكن الحصول علي هذه الصلاحية من الشاشة الرئيسية للبرنامج قائمة الصيدلية العاملين تعديل اعدادات العاملين» (:885).
- Balance edits need **level ≥ 7**: «لا تملك الصلاحيات اخبر المدير بان يمنحك صلاحية 7 اواعلي» (:11656); «منع المسخدمين من تعديل الارصدة الا بحصولهم علي صلاحية 7 او اعلي» (feature_stock_counting.md:84).
- Manager must grant each permission explicitly: «غير مسموح لك-للمدير منحك هذه الصلاحية من شاشة تعديل اعدادات العاملين» (FFFInPut, strings_readable.txt:12034).
- Technical-support permissions: «تحتاج لصلاحيات الدعم الفني برجاء التوجه الي الشاشة الرئيسية ثم قائمة الصيدلية ثم العاملين ثم الدخول كدعم فني» (:10065); success «الان انت تملك صلاحيات الدعم الفني» (:9157).
- Permission list editable: «اضافة امكانية البحث في قائمة صلاحيات الموظف في شاشة تعديل اعدات العاملين» (:8934); «اضافة بند تعديل الرصيد ضمن قائمة صلاحياة الموظف» (:8951); «اضافة حصلاحية عمل الخصم من عدمه للموظفين في قائمة صلاحيات الموظف» (:8958); discount threshold permissions «أدخل نسبة التحفيذ لخصم اكبر من 25%...75%» (:8244–8249).
- Unauthorized messages: `Stakeholder is unauthorized for this operation`, `User is not authorized for this service. Apply to your firm.`, `You are not authorized to use this service.` (permissions_complete §9).
- Blocked/deactivated account: «Your account is deactivated. Apply to your system manager.», «Your user has been temporarily blocked. Please try again later», «Sender user is passive» (permissions_complete §9).

### 2.4 Menus per user (قوائم المستخدم)
1. Each user is granted **screen access** through FormMenusPerUser / FFFUserMenu (chkAccess[] per menu/screen) and permission sets in FFFUserMenuList; user picks from FFFUserList/FFFUserChoose (modules_gap_2 §13/14/52).
2. The main menu (FormMenu/FormMain) renders only the screens the current user may open; buttons disabled/hidden by permission (permissions_complete §12 «Menu items shown/hidden based on user permissions»).
3. «اختبر الصلاحيات» — test the permissions (modules_gap_2 §52).
4. In-sale screens can be opened for any granted screen without logout («الان يمكنك فتح كافة الشاشات دون الحاجة لخروج المستخدم الحالي» :9167).
5. In-app help: FormUsersGuide/FormUserGuide/FormGuide (دليل المستخدمين/دليل المستخدم/الدليل) — help browser reachable from the menu; «شرح بالفيديو علي يوتيوب» (:11776).

### 2.5 Employee management & shifts (FormEmployee, FFFAML, ModAmil2, FormHodour)
1. **Add employee:** «ادخل اسم الموظف» (:8460), «ادخل باسورد الموظف» (:8514); re-enter pass: «برجاء اعادة ادخال رقم المرور الخاص بالموظف» (:267) / «...بمدير الصيدلية» (:268).
2. **Change permissions:** «تغيير صلاحيات موظف» (:269); «اضافة موظف جديد» (:258); «اجمالي ساعات الموظفين في الفترة» (:255) — total employee hours in period.
3. **Attendance (حضور وانصراف):** ModAmil2 proc 2 reads the employee **barcode**, validates the employee, logs time (modules_gap_1 §8). «ادخل رقم مرور المدير او الموظف الذي تود تسجيل حركة حضوره وانصرافه» (:8561). Buttons «تسجيل حضور» (:10136) / «تسجيل انصراف» (:10134); «انصراف» (:9827). «قم باعداد الشاشة لاستقبال امر الباركود من خلال الضغط علي امر حضور» / «...امر انصراف» (:11549–11550). Print attendance barcode: `Print the attendance and departure barcode` (config_complete §2).
4. **Shift (وردية/شفت) system:** shifts take sequential numbers starting at 1: «اصبح الشيفتات او الفترات تاخذ ارقام مرتبة تبدا من 1 بدلا من ارقام عشوائية» (:8835). «امكانية تسجيل دخول اكثر من موظف في نفس الوقت عند تشغيل اكثر من جهاز في الصيدلية» (:9794). «امكانية خروج الموظف مع الابقاء علي الشيفت» (modules_gap_2 §7). Per-shift sales query: «استعلام مبيعات الشفتات وفيها تفصيل مبيعات الشفت والمستخدمين اللذين قاموا بالعمل فيه» (:8965, FormShiftFawateer).
5. **Shift-handover / drawer (تسليم الدرج):** «تظهر لك شاشة تطالبك بعد الدرج فقم بذلك وابلغ البرنامج القيمة الموجودة» (:10226), «تعد الدرج وتكتب القيمة في الحقل المخصص لذلك» (:10230). «المدير ومساعده فقط يحق لهم الخروج دون عد الدرج» (:9649). Reports: «تقاريرتسليم الدرج بين الفترات» (:10320), «تم تطوير نظام الشفتات الي نظام احدث وتجد التقرير الخاص به في شاشة تسليم الدرج بين الموظفين» (:10421). Drawer math: «اجمالي الدرج حاليا مطروح منه الدرج عن بداية الفترة ومضافا اليه اي نقدية خرجت من الدرج اثناء الفترة لاي سبب» (:8305).
6. **Attendance reports:** «دخول وخروج العاملين» (:10836); «الموظف التاريخ توقيت الدخول» (:9719); «تقرير وقت تسجيل الدخول للموظفين» (:10331); «تم اضافة تقرير التعرف علي وقت تسجيل الدخل لكل موظف» (:10366). Barcode-driven attendance with date-range filter (ModAmil2 proc 9).
7. **Trust ranking:** «رتب موظفينك من حيث الموثوقية في المكان» (:10863); «Sort your employees according to the degree of trust» (modules_gap_1 §8).

### 2.6 User activity audit (سجل الانشطة / TitanUserAction)
1. Every drug/price/barcode/balance edit writes a row to `TitanUserAction` via `INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)` (strings_readable.txt:4945; business_logic_complete.md:449).
2. Surfaced through «تم انشاء الية تتبع تحركات المستخدمين داخل البرنامج من امر سجل الانشطة في قائمة تقارير» (:10399) — «سجل الانشطة» (:10972) report = FormHistory/FormJournal; drug-level view = FormDrugHistory (schema_mapping.md:235).
3. Invoice-edit tracking shows editor mobile+name, item, type, prices, value, branch, date (feature_invoice_editing.md:268).

### 2.7 Per-user money aggregation (FormUsersMony)
1. FormUsersMony (24 procs, اموال المستخدمين) aggregates each user's sales/money; connected to `invoicedata` + `titanpharmalist` (schema_mapping.md:150).
2. Delivery/handover reports: «تسليم مبيعات الموظفين» (:10165), «تسليم مبيعات الفترات» (:10164), «ادخل مبيعات الموظف خلال الشفت الحالي» (:8615). Per-shift/per-user invoice columns: «الفاتورة الشفت المستخدم القيمة المخصوم شراء الاجل المدفوع» (:9497).
3. Employee sales inquiry: «Inquiry about employee sales», «Inquiry about shifts sales» (ModAmil2 §8). Employee performance/points: «احصائيات النقاط للموظف» (:8351), «احصائيات النقاط لموظف» (:8352).
4. Salaries: «المرتب» (:9653), «اضافة المرتب الاساسي» (:8922); salary payment moves money drawer→treasury: «ستقوم لحظة اخراج المرتب بتحويل قيمته من الدرج الي الخزينة ثم تقوم بصرفه من شاشة مصروفات» (:10966); hourly-rate formula: «اذا حضر الموظف 370 ساعة وكان سعر ساعته الشهرية 100 جنيه فتكون المعادلة كالتالي» (:8682).
5. Money-per-user feeds the daily closing (تقفيل اليوم) — «يجب ان تكوت القيمة القصوي اكبر من القيمة الصغري» guards ranges (feature_account_closing.md:28).

---

## 3. User types / permission levels

### 3.1 The 8 documented user types (permissions_complete §1, with gate strings)

| # | Type (En) | Type (Ar) | Effective level | Notes |
|---|---|---|---|---|
| 1 | **Super Admin** | المشرف العام | 9 | Full system access, «Login as super admin» |
| 2 | **Admin** | مدير الصيدلية | 9 | «الحساب الرئيسي الان هو حساب مدير الصيدلية» (:9310); can manage users, «المدير فقط يستطيع تغيير مدخلات المستخدمين الاخرين» (:9647) |
| 3 | **Pharmacy Manager** | مدير الصيدلية (إدارة) | 8–9 | Management; «الدخول بحساب الادارة» (:9322) |
| 4 | **Technical Support** | الدعم الفني | — | «تسجيل الدخول كدعم فني» (:10133), «ادارة الدعم الفني» (:8425), «Contact tech support Code =» (:511) |
| 5 | **Operations Account** | حساب العمليات | mid | «الدخول بحساب العمليات» (:9323/9324) |
| 6 | **Management Account** | حساب الادارة | high | management reports & settings |
| 7 | **Normal User** | مستخدم عادي | 1–5 | «الصلاحية 1 فهي صلاحية منخفضة للغاية» (:10004) |
| 8 | **Cashier** | الكاشير | 1–4 | sales-focused; credit-sale gate «لا تملك صلاحية البيع الاجل» (:885) unless granted |

### 3.2 Numeric level semantics (the same single `صلاحية` field, 1–9)
- **9** = all manager permissions on any accessible screen (:9442).
- **7** = required for balance edits «لا تملك الصلاحيات اخبر المدير بان يمنحك صلاحية 7 اواعلي» (:11656).
- **1** = minimal; many tools blocked within granted screens (:10004).
- **Invalid** = «الصلاحية غير مقبوله» (:9443).
- Entry prompt: «ادخل صلاحية الموظف الحالي من واحد الي تسعة» (:8572), «ادخل الصلاحية كما تنطقها او تسعمها» (:8492).

### 3.3 Permission categories (permissions_complete §2)
Sales (sell/return/discount/void/price-edit/price-override), Purchases (buy/import/return/edit purchase price), Inventory (edit stock/transfer/receive/export/import), Reports (view/print/export + financial/sales/purchase), Settings (pharmacy/printer/barcode/company/VAT), User management (add/edit/delete users, change/reset passwords, view activity).

---

## 4. Fields / data captured

### 4.1 User master (FFFUserEdit controls — modules_gap_2 §1)
```
Username  (اسم المستخدم = 17-digit numeric ID)   — txtUsername
Password  (كلمة المرور)                          — txtPassword / txtNewPassword
Mobile    (رقم الموبايل)                         — pharmacy/user key, used in audit rows
Type/Role (cmbRole: مدير/دعم فني/صيدلي/موظف)
Permission level (الصلاحية 1–9)                  — integer gate
Shift     (cmbShift)                             — shift assignment
Permissions[] (chkPermissions[]: خصم، تعديل سعر، حذف فاتورة، تعديل رصيد…)
```

### 4.2 TitanUserAction (audit) — schema_complete.sql table 17
`drugname, typevalue, oldvalue, newvalue, mobile, namee, curbarcode, curprice, units, datee` (+ `id` IDENTITY). `mobile` = the acting user's phone, `namee` = acting user's name.

### 4.3 usersourceupdate (sync queue) — schema_complete.sql table 18
`id` IDENTITY, `drugname`, `price`, `units`, `localimport`, `datee`, `barcode`, `pharmacyid`, `lastedit`. Insert `insert into usersourceupdate (drugname,price,units,localimport,...)` (strings_readable.txt:7608); read `SELECT top 3000 * FROM usersourceupdate WHERE Datee > '<ts>'` (:5870); delete `DELETE FROM usersourceupdate WHERE id='...'` (:4235); existence check `select drugname from usersourceupdate` (:779).

### 4.4 Employee records (ModAmil2 files)
`Files\DBI\amil2.phy`, `Files\DBI\AmilInfo.phy` — employee name, password (باسورد الموظف), permission level, shift/hours, attendance log (modules_gap_1 §8). `taronlineeg` used for online transactions per employee.

### 4.5 Session / config files
`Files\DBI\login-h.phy` (login history), `Files\DBI\us.phy` (user settings), `Files\DBI\myhistory.txt` (user history), `Files\DBI\myftp.phy` (FTP credentials) (config_complete §16).

---

## 5. Side-effects

- **User audit:** every drug/price/barcode/balance edit → `TitanUserAction` row (old/new value, acting mobile+name, barcode, price, units, date).
- **Cross-pharmacy sync:** drug price/stock updates → `usersourceupdate` → cloud (DrugEye `/titan-users/...`, drugeye_complete §5.3) → remote branches (network_complete.md:611; schema_mapping.md:267).
- **Shift/attendance:** attendance log appended (ModAmil2 proc 2); per-shift invoice data written for FormShiftFawateer.
- **Drawer/treasury:** per-user sales & handover feed drawer count (الدرج), treasury, and تسليم الدرج reports; salary payout transfers drawer→treasury.
- **Customer/supplier balances:** user actions can change balances (اجل العملاء/مستحقات الموردين) automatically from sales & purchases (feature_balances.md:60); credit-sale permission controls whether اجل invoices can be created at all.

---

## 6. Pricing + VAT

Not pricing itself, but permission gates cover pricing/VAT operations:
- `Can edit prices`, `Can override prices` (permissions_complete §2); «لتغيير سعر الدواء» (:279); price edits audited in `TitanUserAction` (feature_drug_master_pricing.md:160).
- Cost-price view gated: «لا تملك صلاحية لعرض سعر الشراء» (feature_drug_master_pricing.md:282).
- VAT settings edits require Settings permissions (permissions_complete §2; config_complete §4 «Add or Remove Vat», «Change Vat status»).
- Discount permission per employee: «اضافة حصلاحية عمل الخصم من عدمه للموظفين في قائمة صلاحيات الموظف» (:8958).

---

## 7. Payment methods

Gated by permissions: cash (كاش), network/card (شبكة/فيزا), credit (اجل — needs «صلاحية البيع الاجل», :885). Per-user money aggregation reports columns: المدفوع (paid), الاجل (credit), شراء (purchase) per invoice per user (:9497). Payment on credit invoices checks customer credit limit: «اجمالي المتبقي من هذه الفاتورة ومديونية هذا العميل اكبر من الحد الائتماني له ولهذا فلا يمكن حفظ الفاتورة» (:8317).

---

## 8. Printing

- Attendance/exit barcode: `Print the attendance and departure barcode` (config_complete §2) — prints employee barcode for attendance scanning.
- Employee reports: تقارير العاملين (FormAmilTakarir), دخول وخروج العاملين (:10836), «تقرير وقت تسجيل الدخول للموظفين» (:10331).
- Shift sales: استعلام مبيعات الشفتات (:8763), تسليم الدرج بين الفترات (:10320), تسليم مبيعات الموظفين/الفترات (:10164–10165).
- Activity log: سجل الانشطة (:10972) / FormHistory.
- Salary reports: رواتب الموظفين (FormAmilTamin), «اجمالي ساعات الموظفين في الفترة» (:255).
- Print templates selector 500/600/700/800 applies to balance/close reports (feature_balances.md:170).

---

## 9. Tables

### 9.1 TitanUserAction — audit / user action log (schema_complete.sql table 17)
```sql
CREATE TABLE TitanUserAction (
    id          INT IDENTITY(1,1) NOT NULL,   -- PK
    drugname    NVARCHAR(100) DEFAULT '',     -- affected drug
    typevalue   NVARCHAR(100) DEFAULT '0',    -- action type
    oldvalue    NVARCHAR(200) DEFAULT '',     -- previous value
    newvalue    NVARCHAR(200) DEFAULT '',     -- new value
    mobile      NVARCHAR(15)  DEFAULT '',     -- acting user phone (user key)
    namee       NVARCHAR(100) DEFAULT '',     -- acting user name
    curbarcode  VARCHAR(16)   DEFAULT '',     -- current barcode
    curprice    REAL          DEFAULT 0,      -- current price
    units       INT           DEFAULT 0,      -- units
    datee       REAL          DEFAULT 0       -- date
);
-- INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)
```
(schema_complete.sql:245–256; INSERT at strings_readable.txt:4945)

### 9.2 usersourceupdate — cross-pharmacy drug update queue (schema_complete.sql table 18)
```sql
CREATE TABLE usersourceupdate (
    id          INT IDENTITY(1,1) NOT NULL,   -- PK
    drugname    NVARCHAR(100) DEFAULT '',     -- FK→wzdrugs (drug)
    price       REAL          DEFAULT 0,      -- new price
    units       INT           DEFAULT 0,      -- units/stock
    localimport INT           DEFAULT 0,      -- import source flag
    datee       REAL          DEFAULT 0,      -- date
    barcode     VARCHAR(16)   DEFAULT '',     -- drug barcode
    pharmacyid  NVARCHAR(15)  DEFAULT '',     -- source pharmacy
    lastedit    VARCHAR(50)   DEFAULT ''      -- last editor
);
-- insert into usersourceupdate (drugname,price,units,localimport,...)
-- SELECT top 3000 * FROM usersourceupdate WHERE Datee > '<timestamp>'
-- DELETE FROM usersourceupdate WHERE id='<id>'
```
(schema_complete.sql:263–273; drugeye_complete.md:188–199)

### 9.3 ChainBuyUsers — chain-pharmacy users (schema.sql / schema_complete.md)
```sql
CREATE TABLE ChainBuyUsers (
    PharmacistTel NVARCHAR(15) DEFAULT '',    -- pharmacist telephone (user key)
    Name          NVARCHAR(100) DEFAULT '',
    PharmacyId    NVARCHAR(15)  DEFAULT '',
    Datee         REAL          DEFAULT 0
);
-- INSERT INTO ChainBuyUsers ... ; SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%...%'
```
(schema.sql:317–323; strings_readable.txt:4943/5867)

### 9.4 Supporting tables
- `wzcustomers` (creditlimit per customer — credit-sale gate target), `companies` (mobile+pass supplier auth), `farysales` (per-branch/per-user ledger: writer column records the acting user; creditdebit/payed), `invoicedata` (per-invoice totals feeding FormUsersMony), `titanpharmalist` (pharmacy list for cross-branch), `taronlineeg` (online transactions per employee) — schema_mapping.md:150,232.
- `remotecontrol` / `drgserver` — cloud sync channels that carry usersourceupdate payloads (network_complete.md:611).

---

## 10. UI strings (Arabic)

### 10.1 Login / account
```
ادخل اسم المستخدم وهو رقم طويل مكون من 17 رقم     (:8457)  — username = 17-digit ID
ادخل اسم الحساب                                 (:8447)  — account name
ادخل رقم المستخدم                               (:826)
ادخل كلمة المرور                                (:8598)  — enter password
ادخل كلمة المرور الجديدة                         (:8599)  — new password
ادخل كلمة المرور الخاصة بالمدير                   (:8600)  — manager password
ادخل كلمة المرور وتحصل عليها من الدعم الفني        (:8601)  — support password
ادخل معلومات صحيحة في اسم المستخدم وكلمة المرور    (:8618)  — invalid creds
اسم المستخدم الذي ادخلته خاطئا برجاء الرجوع للايميل (:8807)
اسم المستخدم / الحساب                            (:8789/8806)
الحساب الرئيسي الان هو حساب مدير الصيدلية           (:9310)
الدخول بحساب الادارة / بحساب العمليات              (:9322–9324)
الدخول كمدير دون تسجيل خروج المستخدم الحالي        (:9325)
اخفاء كلمة المرور عند محاولة التسجيل الدخول كمدير   (:8423)
ادخل الرقم صفر لتسجيل الخروج من حساب المدير        (:8431)
تسجيل الدخول كدعم فني / الدخول والخروج            (:10133/:9326)
بعد تسجيل الدخول يقوم تيتان بتوجيهك مباشرة الي الشاشة... (:9947)
تسجيل الخروج / تم تسجيل الخروج                    (:10132/:10415)
```

### 10.2 Permission gates (صلاحية)
```
لا تملك صلاحية البيع الاجل يمكن الحصول علي هذه الصلاحية من الشاشة الرئيسية
  قائمة الصيدلية العاملين تعديل اعدادات العاملين    (:885)   — credit-sale gate
لا تملك الصلاحيات اخبر المدير بان يمنحك صلاحية 7 اواعلي (:11656) — balance-edit gate
ادخل صلاحية الموظف الحالي من واحد الي تسعة          (:8572)   — level prompt 1–9
ادخل الصلاحية كما تنطقها او تسعمها                  (:8492)
الصلاحية 9 يعني انك تمنح هذا الموظف كافة صلاحيات المدير
  في اي شاشة له حق الولوج اليها                    (:9442)   — level 9 semantics
بينما الصلاحية 1 فهي صلاحية منخفضة للغاية ينتج عن ذلك
  منعه من استخدام ادوات كثيرة داخل الشاشات...      (:10004)  — level 1 semantics
الصلاحية غير مقبوله                                (:9443)
غير مسموح لك-للمدير منحك هذه الصلاحية من شاشة تعديل اعدادات العاملين (:12034)
لا تملك الصلاحيات لدخول هذه النافذة                    (:11657)  — window access gate
لا تملك الصلاحيات لدخول هذه النافذة من فضلك سجل دخولك
  من قائمة العاملين ثم اختر دخول                      (:11658)
لا تملك الصلاحيات لهذه الخاصية                         (:11659)
لا تملك الصلاحيات... من الشاشة الرئيسية اختر قائمة الصيدلية
  ثم العاملين ثم تسجيل الدخول كدعم فني                 (:11660)  — tech-support gate
لا يوجد مستخدم حالي. استخدم هذه الخاصية فقط اذا كان هناك
  مستخدم مسجل دخوله                                  (:11758)
تحتاج لصلاحيات الدعم الفني برجاء التوجه الي الشاشة الرئيسية
  ثم قائمة الصيدلية ثم العاملين ثم الدخول كدعم فني   (:10065)
الان انت تملك صلاحيات الدعم الفني                    (:9157)
انت لست المدير                                     (:9811)
المدير فقط يستطيع تغيير مدخلات المستخدمين الاخرين     (:9647)
المدير فقط يمكنه تعديل مدخلات الايام السابقة          (:9648)
المدير ومساعده فقط يحق لهم الخروج دون عد الدرج        (:9649)
المدير المالي                                       (:9646)
```

### 10.3 Password rules
```
باسورد قصير للغاية              (:9859)   — password too short
برجاء ادخال كلمة المرور الحالية الخاصة بك (:9901)  — current password for change
تغيير كلمة المرور الخاصة بي      (:10280)
برجاء اعادة ادخال رقم المرور الخاص بالموظف / بمدير الصيدلية (:267/:268)
ادخل باسورد المدير / ادخل باسورد الموظف (:8513/:8514)
ادخل رقم مرور المدير او الموظف الذي تود تسجيل حركة حضوره وانصرافه (:8561)
Call us telegram 01015441306 - Password Code =   (:548)   — recovery via Telegram
Call us 010309018711 HX=                          (:3965)
```

### 10.4 Employee / shift / attendance
```
اضافة موظف جديد / ادخل اسم الموظف / ادخل باسورد الموظف (:258/:8460/:8514)
تغيير صلاحيات موظف / اضافة بند تعديل الرصيد ضمن قائمة صلاحياة الموظف (:269/:8951)
لم يعد ممكنا اضافة موظفين جدد: يمكنك اضافة الموظف الجديد في مكان موظف قديم
  فقط بتغيير الاسم                                 (:894)
اجمالي ساعات الموظفين في الفترة                     (:255)
تسجيل حضور / تسجيل انصراف / انصراف                 (:10136/:10134/:9827)
لقد تم تسجيل حضورك                                 (:11862)
لم تقم بتسجيل حضورك لهذا اليوم                       (:11919)
الموظف التاريخ توقيت الدخول                          (:9719)
دخول وخروج العاملين                                 (:10836)
استعلام مبيعات العاملين / استعلامات مبيعات العاملين   (:8764/:8765)
استعلام مبيعات الشفتات وفيها تفصيل مبيعات الشفت والمستخدمين (:8965)
الشيفتات او الفترات تاخذ ارقام مرتبة تبدا من 1       (:8835)
امكانية تسجيل دخول اكثر من موظف في نفس الوقت عند تشغيل اكثر من جهاز (:9794)
تسليم مبيعات الموظفين / تسليم مبيعات الفترات         (:10165/:10164)
تقرير وقت تسجيل الدخول للموظفين                      (:10331)
رتب موظفينك من حيث الموثوقية في المكان               (:10863)
المرتب / اضافة المرتب الاساسي                        (:9653/:8922)
احصائيات النقاط للموظف / لموظف                       (:8351/:8352)
```

### 10.5 Audit / activity
```
تم انشاء الية تتبع تحركات المستخدمين داخل البرنامج من امر سجل الانشطة
  في قائمة تقارير                                   (:10399)
سجل الانشطة                                       (:10972)
المستخدم الحالي                                   (:138)
تاريخ التعديل الصنف التعديل سعر البيع خصم الشراء قيمة التعديل الفرع (:139)
الفاتورة الشفت المستخدم القيمة المخصوم شراء الاجل المدفوع (:9497)
```

---

## 11. Business rules / edge cases

1. **Username = 17-digit numeric ID** (mobile-style national code), not a free-text name (:8457); stored as the audit `mobile`/`namee` pair (TitanUserAction).
2. **Single permission integer 1–9** drives all feature gates; 9 = full manager on any accessible screen (:9442); 1 = minimal (:10004); the 8 user types (super admin/admin/manager/tech-support/operations/management/normal/cashier) map onto this scale (permissions_complete §1).
3. **Credit sales (البيع الاجل) require an explicit permission** — otherwise «لا تملك صلاحية البيع الاجل» blocks the invoice (:885).
4. **Balance edits require permission ≥ 7** (:11656; feature_stock_counting.md:84); the permission itself is granted from «تعديل اعدادات العاملين» only (:12034).
5. **Only the manager edits other users' entries** and previous-day data (:9647/:9648); «انت لست المدير» blocks non-managers (:9811).
6. **Manager overlay login** («الدخول كمدير دون تسجيل خروج المستخدم الحالي») is capped at **5 minutes** (:10084) and can hide the password (:8423); exit via entering `0` (:8431).
7. **Employee slot limit** — no new employees once the cap is reached; replace an old employee by renaming (:894).
8. **Password policy:** minimum length («باسورد قصير للغاية», :9859), re-entry confirmation (:267/:268), current-password required to change own password (:9901). Recovery = Telegram support with a Password Code (:548, :3965); default/reset example `3030` (permissions_complete §3).
9. **Shifts are sequential numbered periods** (1,2,3…) (:8835), may have multiple employees logged in concurrently from multiple PCs (:9794), and survive employee logout («امكانية خروج الموظف مع الابقاء علي الشيفت»).
10. **Drawer settlement on shift/end-of-day:** cashiers must count the drawer («تظهر لك شاشة تطالبك بعد الدرج», :10226); only manager + assistant may leave without counting (:9649); drawer report = تسليم الدرج بين الفترات (:10320).
11. **Attendance by barcode** — employee barcode printed (`Print the attendance and departure barcode`), scanned via حضور/انصراف buttons (ModAmil2 proc 2; :11549–11550); confirmation «لقد تم تسجيل حضورك» (:11862) and a daily check «لم تقم بتسجيل حضورك لهذا اليوم» (:11919).
12. **Audit trail mandatory** — all drug/price/balance edits write `TitanUserAction`; reviewed via سجل الانشطة / FormHistory / FormDrugHistory (:10399).
13. **userSourceUpdate is a sync queue** — batched (top 3000 per pull, :5870), keyed by `id`, propagated to linked pharmacies/cloud, cleaned by id-delete (:4235).
14. **Account deactivation/blocking:** passive/blocked users rejected at login (`Your account is deactivated…`, `Your user has been temporarily blocked…`, permissions_complete §9).
15. **After login the user is returned to the screen they wanted** before login (:9947); main menu shows only the screens granted to the current user (permissions_complete §12).

---

## 12. Reused references

- permissions_complete.md (8 user types, login types, permission categories, password strings, TitanUserAction/usersourceupdate).
- modules_gap_2.md §1/§12–14/§34/§42/§50–52 (FFFUserEdit, FFFUserList, FFFUserMenu, FFFUserMenuList, FormMenusPerUser, FormEmployee, FormUsersGuide/FormUserGuide).
- modules_gap_1.md §8 ModAmil2 (shifts/attendance, amil2.phy/AmilInfo.phy).
- ui_complete.md (Employees & Shifts forms; FormUsersMony=اموال المستخدمين).
- business_logic_complete.md §2.5 (TitanUserAction DDL) / §2.9 (usersourceupdate).
- schema_complete.sql tables 17–18; schema.sql (TitanUserAction, usersourceupdate, ChainBuyUsers).
- schema_mapping.md (FormUsersMony→invoicedata/titanpharmalist; TitanUserAction/usersourceupdate wiring).
- drugeye_complete.md §5.3 (usersourceupdate sync semantics).
- feature_stock_counting.md:84 (permission ≥7 for balance edits); feature_balances.md; feature_account_closing.md (FormUsersMony).
- titan_decompile/strings_readable.txt (line refs cited throughout).