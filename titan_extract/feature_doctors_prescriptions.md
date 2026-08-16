# Feature: الأطباء والروشتات — Doctors & Prescriptions

**Purpose:** Full extraction of the TITAN.W1 (Phye.exe) doctor & prescription domain: the **doctor master** (بيانات الطبيب), **doctor fees** (أتعاب الأطباء), **prescription capture and patient–prescription linkage** (ربط مريض بوصفة طبية), the **electronic-prescription (وصفتي / Wasfaty)** integration, and the **insurance-company (شركة تامين / ModTamin)** billing flow that drives prescription reimbursements. Covers tables, fields, workflow, UI strings (Arabic), and business rules. Reuses `modules_gap_2.md` (FormDoctor, FormDoctorFees), `modules_remaining_1.md` (ModTamin, ModDisease, ModDDI, PeInter), `feature_sales_invoices.md`, `feature_customers_suppliers.md`, `reports_complete.md`, `api_integration.md`, and `dtts_complete.md`.

> **Reading note:** `FormDoctor` / `FormDoctorFees` / `ModDoctor` are marked **In project: NO** (`modules_gap_2.md:516,526`) — i.e. the doctor-management screens exist in the module inventory/version-history but are not present as compiled forms in this build. The *live* doctor/prescription surfaces in this build are: the sales screen (prescription link + delivery-note template), `FormWasfaty` (وصفتى, 27 procs), `ModMarid`/`FormMarid*` (patient/المريض), and `ModTamin`/`FormAmilTamin`/`FormAmilTamin2` (insurance/تأمين).

---

## 1. Objects

| Object | Kind | Procs | Role |
|--------|------|-------|------|
| `FormDoctor` | Form | — | بيانات الطبيب / الأطباء — doctor master (name, specialty, phone). **Not in this build** (`modules_gap_2.md:510–519`) |
| `FormDoctorFees` | Form | — | أتعاب الأطباء — doctor fees paid per prescription/clinic. **Not in this build** (`modules_gap_2.md:523–532`) |
| `ModDoctor` | Module | — | Doctor logic module. **Not in this build** (`modules_gap_2.md:1307,1357`) |
| `FormWasfaty` | Form | 27 | الوصفة الطبية الإلكترونية — Egyptian e-prescription (وصفتي) integration; the live prescription-capture surface (`ui_complete.md:244`; `ui_strings_readable.txt:233`) |
| `ModMarid` | Module | 4 | المريض — patient master; 107-field customer/patient record (`ui_forms.json:257`; `modules_gap_1.md:38,44`) |
| `FormMarid` | Form | 5 | المريض — patient/customer disease records (`ui_complete.md:174`) |
| `FormMaridData` | Form | 15 | بيانات المريض — patient data management (`ui_complete.md:175`) |
| `FormMaridFat` | Form | 4 | فواتير المريض — patient invoices (all invoices of a patient) (`ui_complete.md:176`) |
| `ModTamin` | Module | 15 | تأمين — insurance-company integration; loads insurance config, computes copay vs. coverage, prints insurance invoices (`modules_remaining_1.md:135–156`) |
| `FormAmilTamin` | Form | 16 | أمين تأمين (insurance employee work screen) (`modules_remaining_1.md:158`) |
| `FormAmilTamin2` | Form | 10 | أمين تأمين v2 (`modules_remaining_1.md:158`) |
| `FormReportsGeneral` | Form | — | hosts RPT-SP01 Patient-Prescription Link report (`reports_complete.md:696–700`) |
| `FormPrintSales` | Form | 17 | sales/وصفة طبية (delivery-note) printing (`feature_sales_invoices.md:166`) |
| `ModDisease` | Module | ~4 | disease database + prescription contraindication warnings (`modules_remaining_1.md:456–474`) |
| `ModDDI` | Class | 4 | drug–drug interaction checker, DB `Files\DB\DDI.Phy` (`modules_remaining_1.md:480–493`; `config_complete.md:15`) |
| `PeInter` | Class | — | per-patient interaction checker (allergies/conditions vs. prescription) (`modules_remaining_1.md:503–513`) |

### ModTamin procedures (`modules_remaining_1.md:142–152`)

| Address | Tokens | Likely function |
|---------|--------|-----------------|
| `0x00a036b8` | 652 (213) | Main insurance data loader — insurance company config |
| `0x009ddd84` | 492 (125) | Insurance price calculator — patient copay vs. insurance coverage |
| `0x00a3444c` | 812 (236) | Insurance invoice printer — insurance-specific invoice format |
| `0x0094cae4` / `0x0094cccc` | 172 each | Load/save insurance settings pair |
| `0x0093e7ec` / `0x0093df54` | 152 each | Insurance company list operations pair |
| `0x00956ed8` / `0x00955e58` | 188 each | Insurance report generators pair |
| `0x00934128` | 140 | Insurance validation |
| `0x008f4a5c` | 52 | Insurance flag checker |
| `0x0092bbbc` | 132 | Insurance coverage lookup |
| `0x00904bcc` | 76 | Insurance discount calculator |
| `0x00951bd0` | 180 | Insurance report formatter |

---

## 2. Step-by-step workflow

### 2.1 Doctor master (بيانات الطبيب) — planned flow (`modules_gap_2.md:510–519`)
1. Open FormDoctor → grid `dgDoctors` lists all doctors.
2. Enter name (`txtName`), specialty (`txtSpecialty`), phone (`txtPhone`).
3. `btnAdd` / `btnEdit` / `btnDelete` maintain the directory.
4. From FormDoctor open **FormDoctorFees** (`modules_gap_2.md:519`).
5. FormDoctorFees: pick doctor from `cmbDoctor`, enter fee `txtAmount` + `txtDate` (per-visit أتعاب), `btnAdd` to record, `btnPrint` for fee report (`modules_gap_2.md:531`).
6. Doctor directory is also referenced from `FormMoamla` (customer transaction form) and customer/supplier forms (`modules_gap_2.md:390,833`) — a doctor is linkable to a customer/patient.

### 2.2 Prescription capture & patient linkage (وصفى طبية / ربط مريض بوصفة)
1. At sale time the pharmacist links the current invoice to a **وصفة طبية (prescription)** and to the patient (وصفتى flow; `FormWasfaty`, 27 procs).
2. On link: `تم ربط المريض الحالي بالوصفة الطبية الحالية حيث يمكنك مستقبلا معرفة كافة الوصفات الطبية لهذا المريض` ("current patient linked to current prescription — you can later see all prescriptions of this patient") (`strings_utf16.txt:11104`).
3. On unlink: `تم الغاء ربط المريض بالوصفة الطبية` (`strings_utf16.txt:11054`).
4. Guards: `هذه الوصفة مربوطة بهذا المريض بالفعل` (already linked, `strings_utf16.txt:13147`); `هذه الوصفة غير مربوطة اصلا` (not linked at all, `strings_utf16.txt:13146`).
5. Prescription is validated against the **disease** and **drug–drug** databases before saving:
   - `ربما يكون في هذه الوصفة ما يحظر استخدامه لمرضي الفشل الكلوي لكن لم يتمكن تيتان من كشفها` ("this prescription may contain something prohibited for kidney-failure patients — Titan could not detect it") (`strings_utf16.txt:11527,11528`).
   - `ليس لدي تيتان معلومة مؤكدة عن تاعلات دوائية دوائية فذف هذه الوصفة` ("Titan has no confirmed info on drug–drug interactions in this prescription") (`strings_utf16.txt:12642`).
   - These originate from **ModDisease** contraindication logic and **ModDDI** (DB `Files\DB\DDI.Phy`) (`modules_remaining_1.md:456–493`).
6. Per-patient interaction checking uses **PeInter** class (per-patient allergies/conditions/medications vs. prescription) (`modules_remaining_1.md:503–513`).

### 2.3 Wasfaty (وصفتى) e-prescription period sales
- Requires a dedicated **عميل وصفتي** and **مورد وصفتي** configured: `تاكد ان لديك عميل ومورد لوصفتي` (`strings_utf16.txt:10701`).
- Exactly one each: `لديك اكثر من عميل وصفتي ولا يمكن الاستمرار` / `لديك اكثر من مورد وصفتي ولا يمكن الاستمرار` ("you have more than one Wasfaty customer/supplier — cannot continue") (`strings_utf16.txt:12516,12517`).
- Customer flagged: `هذا العميل من عملاء وصفتي` (`strings_utf16.txt:13090`); the customer appears in lists as `عميل وصفتي` (`strings_utf16.txt:12000`).
- Sales without a Wasfaty link are reportable: `فواتير المبيعات بدون وصفتي عن فترة` ("sales invoices without Wasfaty for a period") (`strings_utf16.txt:12100`).

### 2.4 Insurance company (شركة تامين) flow
1. Insurance companies are customer/supplier accounts of type **شركة تامين** (readable `typee` value; `ui_strings_readable.txt:2270`; `feature_customers_suppliers.md:55`).
2. Insurer = supplier side (purchases/claims) and patient = sub-customer (عميل فرعي): `اضافة العملاء الفرعيين الملحقين بالعميل الاصلي مثل عملاء شركات التامين او افراد اسرة ملحقين باسم عميل رئيسي` (`strings_utf16.txt:9571`). Insurance-company customers are `عملاء شركات التامين` (`strings_utf16.txt:11984`).
3. `ModTamin` loads insurance company config, computes the **patient copay vs. insurance coverage**, and prints insurance-specific invoices (`modules_remaining_1.md:137–144`). Insurance discount logic: `تعديلات علي الية خصم شركات التامين مما يسمح بتعديل نسبة خصم المستورد` ("changes to insurance-company discount mechanism allowing importer-discount % adjustment") (`strings_utf16.txt:10917`).
4. `FormAmilTamin` / `FormAmilTamin2` are the insurance-employee work screens for processing these transactions (`modules_remaining_1.md:158`).
5. Print for insurers: `طباعة لشركات التامين` (`strings_utf16.txt:11898`; RPT-S09).
6. Anti-fraud tooling for purchase invoices involving insurers: `اضافة مزيد من ادوات التامين ضد محاولة العبث او السرقة او تسوية الرصيد من قبل الموظفين في فواتير المشتريات` (`strings_utf16.txt:9638`).

### 2.5 DTTS/reimbursement link (external)
- Sales XML to the DTTS (Saudi FDA track&trace) service carries prescription context: `<PRESCRIPTIONID>`, `<PRESCRIPTIONDATE>`, `<DOCTORID>`, `<PATIENTNATIONALID>` (`api_integration.md:45–48`).
- Prescription-number validation strings (DTTS reimbursement): "Prescription number must not be empty for prescription drugs", "The prescription number has already been registered", "This prescription has already been queried by the reimbursment institution. It cannot be canceled." etc. (`dtts_complete.md:501–507,951–957`).

---

## 3. Fields / data captured

### Doctor master (FormDoctor; planned) (`modules_gap_2.md:518`)
| Control | Arabic | Meaning |
|---------|--------|---------|
| `dgDoctors` | شبكة الأطباء | doctor grid |
| `txtName` | اسم الطبيب | doctor name |
| `txtSpecialty` | التخصص | specialty |
| `txtPhone` | التليفون | phone |
| `btnAdd`/`btnEdit`/`btnDelete` | اضافة/تعديل/حذف | CRUD buttons |

### Doctor fees (FormDoctorFees; planned) (`modules_gap_2.md:531`)
| Control | Arabic | Meaning |
|---------|--------|---------|
| `dgFees` | شبكة الأتعاب | fees grid |
| `cmbDoctor` | الطبيب | doctor picker |
| `txtAmount` | قيمة الأتعاب | fee amount (رسوم العيادة / أتعاب الطبيب) |
| `txtDate` | التاريخ | fee date |
| `btnAdd` / `btnPrint` | اضافة / طباعة | add fee / print fee report |

### Patient master (ModMarid) (`modules_gap_1.md:38,44`)
107-field record: name, national ID, phone, address, insurance-company linkage (شركة تامين), sub-customer linkage (عميل فرعي), credit limit, opening balance, discount percents (خصم المحلي / خصم المستورد), loyalty points, etc. (`feature_customers_suppliers.md:103`).

### Prescription link (live)
- Prescription id + date + patient (national ID) + doctor, captured at sales and carried in the delivery-note/وصفة طبية print (`reports_complete.md:874–886`) and DTTS XML (`api_integration.md:45–48`).
- The sales line `Tips` (ملاحظات) field can carry notes (`business_logic_complete.md:336`); invoice number is the linkage key.

### Insurance (ModTamin)
- Insurance company master: name, discount model (نسبة خصم), coverage %; patient-side copay vs. coverage split (`modules_remaining_1.md:137–144`).
- Insurance company customer report filter added in **v348+**: `اضافة امر فلترة في تقرير عملاء شركة التأمين` (`strings_utf16.txt:9583`; `reports_complete.md:1282`).

---

## 4. Side-effects

| Trigger | Effect | Where |
|---------|--------|-------|
| Insurance customer sale (credit) | Posts **deferred (أجل)** balance to `wzcustomers` of the insurer/patient account | `feature_sales_invoices.md:153–158`; `schema_complete.md:111–127` |
| Insurer as supplier (claims) | Purchase payable on `companies` supplier master; links to insurance-company customer/claims | `feature_purchases.md:393` |
| Sale with prescription link | Invoice archived in sales tables (`titanksasales`, `invoicedata`) tagged with Wasfaty customer/supplier; auditable via RPT-SP01 | `feature_sales_invoices.md:184–209` |
| Drug sale | Stock decrement in `wzgard`/`titanstock`; money into `wzmony`/`wzdaily`/`wzbank` | `business_logic_complete.md` §16; `schema_complete.md:80–110` |
| Prescription contraindication detected | Warning message only; sale still possible (Titan "لم يتمكن تيتان من كشفها" wording implies soft warning) | `strings_utf16.txt:11527` |

---

## 5. Pricing + VAT

- Doctor fees and insurance copays are **money movements, not drug pricing**; drug line pricing/VAT follows the standard sales formula (`feature_sales_invoices.md:130–137`):
  ```
  Subtotal      = Σ (Quantity × Unit Price)
  Discount      = Subtotal × (SellDisc / 100)
  VAT           = (Subtotal − Discount) × (VAT% / 100)   # default 15%
  Total         = Subtotal − Discount + VAT
  ```
- Insurance price calculator (`ModTamin @0x009ddd84`) computes **patient copay vs. insurance coverage** — i.e. the insurer's share is billed to the شركة تامين account, the patient's share is collected from the patient (`modules_remaining_1.md:143`). Insurance discount % is configurable per company (`strings_utf16.txt:10917`).
- `عمولة الشبكة` (network/visa commission, `strings_utf16.txt:11994`) and the credit-sale rule apply to insurer payments like any other card/credit sale (`feature_sales_invoices.md:151–158`).

---

## 6. Payment methods

Standard sales payment split applies to prescription/insurance sales: **كاش (cash)** · **فيزا/شبكة (card)** · **أجل (deferred)**; `payed + agel = totalvalue`; credit sale requires `السماح بالبيع الاجل` permission and cannot exceed the customer credit limit (`feature_sales_invoices.md:151–158`). Insurance claims typically post as أجل to the insurer then settle via receipts (سند قبض / سند صرف, `feature_sales_invoices.md:170`).

---

## 7. Printing

- **Sales invoice** (`FormPrintSales`): A4/A5 templates with patient/وصفة section — header `Prescription / وصفة طبية`, fields `Patient`, `Date`, `Doctor`, `National ID`, items `# | Drug | Dosage | Duration`, `Notes`, and a QR/barcode block (`reports_complete.md:870–887`). Accessed via `feature_sales_invoices.md:176`.
- **Insurance invoice** (`ModTamin @0x00a3444c`): `طباعة لشركات التامين` — insurance-specific layout with insurer/coverage breakdown (`modules_remaining_1.md:144`; `strings_utf16.txt:11898`).
- **Doctor fees report** (`FormDoctorFees btnPrint`): أتعاب الأطباء listing by doctor (`modules_gap_2.md:531`).
- **Wasfaty period report**: `تقرير وصفتي عن الفترة ادناه` (`strings_utf16.txt:10988`).
- **Patient-Prescription Link report** RPT-SP01 `تقرير ربط مريض بوثفة طبية`: columns Patient Name, National ID, Prescription Date, Doctor, Drug List, Status (`reports_complete.md:696–700`).
- Print triggers: auto-print on save config, drawer-open on print (`feature_sales_invoices.md:171–172`).

---

## 8. Tables

No dedicated doctor/prescription/insurance tables exist in the 28-table SQL schema (`schema_complete.md:9`); the domain rides on the customer/purchases/sales tables:

```sql
-- Customer/patient master — doctor & insurer linkage lives here via typee:
CREATE TABLE wzcustomers (
    randomid    NVARCHAR(50)  PRIMARY KEY,  -- unique patient/doctor/insurer id
    phar        NVARCHAR(15)  DEFAULT '',   -- FK -> wzphar (pharmacy)
    typee       NVARCHAR(50)  DEFAULT '',   -- customer type: عميل / مورد / شركة / شركة تامين / عميل وصفتي / عميل فرعي ...
    writer      NVARCHAR(50)  DEFAULT '',   -- entered by
    creditlimit REAL          DEFAULT 0,    -- credit limit
    datee       REAL          DEFAULT 0,    -- creation date (VB6 serial)
    namee       NVARCHAR(100) DEFAULT ''    -- name
);
-- (schema_complete.md:111-127)

-- Supplier master (insurers as suppliers / claims):
CREATE TABLE companies ( mobile NVARCHAR(15) PRIMARY KEY, pass NVARCHAR(50) DEFAULT '' );
-- (schema_complete.md:131-140)

-- Chain sales master + line data (prescription-linked invoices):
CREATE TABLE titanksasales ( id INT IDENTITY(1,1), invoiceid REAL DEFAULT 0,
    datee REAL DEFAULT 0, silsilaid NVARCHAR(15) DEFAULT '', pharmacyid NVARCHAR(15) DEFAULT '',
    payed REAL DEFAULT 0, disc REAL DEFAULT 0, agel REAL DEFAULT 0, totalvalue REAL DEFAULT 0 );
-- (feature_sales_invoices.md:184-209; schema_complete.sql)

-- Sales line data (Tips/ملاحظات field holds prescription notes):
--   (IdDateTime, Quant, DrugName, SellDisc, Tips, Expire, Minimum, price)
-- (business_logic_complete.md:325-337)

-- Drug interaction DB (external, not SQL):
--   Files\DB\DDI.Phy  (config_complete.md:15,368)
```

Additional 28-table inventory in `schema_complete.md:13–716` (wzdrugs, wzgard, titaninn, titanstock, titanneed, invoicedata, orders, storediscount, TitanUserAction audit, etc.). Doctor/prescription master data would be new tables in a replacement build (e.g. `doctors`, `doctor_fees`, `prescriptions`, `prescription_lines`, `insurance_companies`, `insurance_policies`).

---

## 9. UI strings (Arabic)

Doctor master / fees (planned forms): `بيانات الطبيب / الأطباء` (`modules_gap_2.md:514`), `أتعاب الأطباء` (`modules_gap_2.md:527`).

Prescription linkage (live):
- `تم ربط المريض الحالي بالوصفة الطبية الحالية حيث يمكنك مستقبلا معرفة كافة الوصفات الطبية لهذا المريض` — link OK (`strings_utf16.txt:11104`)
- `تم الغاء ربط المريض بالوصفة الطبية` — unlink OK (`:11054`)
- `هذه الوصفة مربوطة بهذا المريض بالفعل` — already linked (`:13147`)
- `هذه الوصفة غير مربوطة اصلا` — not linked (`:13146`)
- `ربما يكون في هذه الوصفة ما يحظر استخدامه لمرضي الفشل الكلوي لكن لم يتمكن تيتان من كشفها` — disease warning (`:11527,11528`)
- `ليس لدي تيتان معلومة مؤكدة عن تاعلات دوائية دوائية فذف هذه الوصفة` — DDI warning (`:12642`)

Wasfaty (وصفتى):
- `تاكد ان لديك عميل ومورد لوصفتي` — setup check (`:10701`)
- `لديك اكثر من عميل وصفتي ولا يمكن الاستمرار` (`:12516`) / `لديك اكثر من مورد وصفتي ولا يمكن الاستمرار` (`:12517`)
- `عميل وصفتي` (`:12000`) · `هذا العميل من عملاء وصفتي` (`:13090`)
- `فواتير المبيعات بدون وصفتي عن فترة` (`:12100`) · `تقرير وصفتي عن الفترة ادناه` (`:10988`)

Insurance (تأمين):
- `شركة تامين` (`:11783`) · `عملاء شركات التامين` (`:11984`) · `تامينات` (`:10703`)
- `طباعة لشركات التامين` (`:11898`) · `تعديلات علي الية خصم شركات التامين مما يسمح بتعديل نسبة خصم المستورد` (`:10917`)
- `اضافة العملاء الفرعيين الملحقين بالعميل الاصلي مثل عملاء شركات التامين او افراد اسرة ملحقين باسم عميل رئيسي` (`:9571`)
- `اضافة امر فلترة في تقرير عملاء شركة التأمين` (v348+) (`:9583`)
- `اضافة مزيد من ادوات التامين ضد محاولة العبث او السرقة او تسوية الرصيد من قبل الموظفين في فواتير المشتريات` (`:9638`)
- `عمولة الشبكة` — card/network commission (`:11994`)

Patient screens: `المريض` (FormMarid), `بيانات المريض` (FormMaridData), `فواتير المريض` (FormMaridFat) (`ui_complete.md:174–176`).

---

## 10. Business rules / edge cases

1. **Doctor master uniqueness**: one doctor record per name/specialty/phone; doctor may be attached to multiple patients (`modules_gap_2.md:510–519`).
2. **Doctor fees** are recorded per visit/date against the doctor (رسوم عيادات) and reported separately from drug sales (`modules_gap_2.md:523–532`).
3. **One-to-one patient↔prescription link**: a prescription can be linked to only one patient; a second link errors (`strings_utf16.txt:13147`). Unlinking only allowed when a link exists (`:13146`).
4. **Wasfaty single-customer/single-supplier invariant**: exactly one `عميل وصفتي` and one `مورد وصفتي` must exist to proceed (`:12516,12517`); both required (`:10701`).
5. **Contraindication checks are advisory** — Titan issues soft warnings for kidney-failure contraindications and unknown drug–drug interactions but does not block the sale (`:11527,11528,12642`; `modules_remaining_1.md:456–493`).
6. **Insurance pricing**: patient copay vs. insurance coverage split computed by ModTamin; insurer share billed to the شركة تامين account; importer-discount % adjustable per insurer (`modules_remaining_1.md:143`; `strings_utf16.txt:10917`).
7. **Insurance customers are sub-customers** (عميل فرعي) of a primary customer (insurance company), enabling family-member and insurer-linked claims (`strings_utf16.txt:9571`; `feature_customers_suppliers.md:69–70`).
8. **Credit rules apply to insurers**: insurance-company sales post أجل and are subject to credit-limit and `السماح بالبيع الاجل` permission checks (`feature_sales_invoices.md:155–158`).
9. **Anti-fraud**: extra تأمين tooling on purchase invoices blocks tampering / employee balance settlement (`strings_utf16.txt:9638`).
10. **DTTS/reimbursement integration**: prescription number mandatory for prescription drugs; already-registered prescription numbers are rejected; reimbursed prescriptions cannot be cancelled (`dtts_complete.md:501–507`).
11. **Report filterability**: insurance-company customer report gained a filter command in v348+ (`reports_complete.md:1282`).