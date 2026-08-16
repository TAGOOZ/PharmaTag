# ZATCA E-Invoicing - Complete Integration Specification

## Source Modules
- **ModZatca** (14 procedures) - Core ZATCA integration
- **ModZatca2Wraber** (24 procedures) - Extended ZATCA functions
- **Modzatcasign** (3 procedures) - ZATCA XML/JSON signing
- **FormVat** (20 procedures) - VAT reporting form
- **FormVat2** (38 procedures) - Extended VAT form
- **FormVatfakeInvo** (15 procedures) - Fake invoice handling
- **FormRsdDispatch** (16 procedures) - RSD dispatch integration
- **FormGovData** (5 procedures) - Government data form
- **ModEtaWrappper** (7 procedures) - ETA wrapper (shared)
- **ModTafqit** (4 procedures) - Arabic number formatting

---

## 1. ZATCA API Endpoints

### Base URLs
```
Production:  https://api.zatca.gov.sa
Preprod:     https://api.preprod.zatca.gov.sa (implied from pattern)
```

### Saturn Companion Service (Local Signing Engine)
```
Saturn executable:     C:\saturn\saturn.exe
Saturn2 executable:    C:\saturn\saturn2.exe
Onboarding tool:       C:\Files\Zatca\saturnonboard.exe
UUID Generator:        C:\eToolKit\toolkit.exe
API Signing:           C:\api-sign.aspx
```

### Saturn File Paths
```
C:\saturn\
C:\saturn\zatca\
C:\saturn\zatca\computer-1\
C:\saturn\zatca\computer-1\lastdata\
C:\saturn\zatca\computer-1\lastdata\counter.txt
C:\saturn\zatca\computer-1\lastdata\hash.txt
C:\saturn\Zatca\computer-1\invoices\
C:\saturn\help\summer.txt
C:\saturn\help\xmlauth3.txt
C:\saturn\help\zatca.onboarding.form.xlsx
```

### ETA Wrapper (for Egypt - shares pattern)
```
C:\eToolKit\appsettings.json
C:\eToolKit\summer_without_uuid.json
C:\eToolKit\summer_with_uuid.json
C:\eta-qr\
```

---

## 2. Invoice Types

### Invoice Type Codes (ZATCA Standard)
```
b2b-normal     - B2B Standard Invoice
b2b-credit     - B2B Credit Note
b2b-debit      - B2B Debit Note
b2c-normal     - B2C Simplified Invoice
b2c-credit     - B2C Credit Note
b2c-debit      - B2C Debit Note
```

### Document Type Codes
```
b2b-standard-001  - B2B Standard invoice type code
```

### Invoice Type Strings
```
"b2b-normal; b2b-credit; b2b-debit; b2c-normal; b2c-credit; b2c-debit"
```

### Internal Invoice Classification
```
As a Sales invoice
As a new purchase invoice
As a new purchase return invoice
Sales return invoice
Purchases invoice
Fake-invoice
Fake-invoice-csv
Transferred invoice
E-Invoice / Electronic-Invoice / E.INVOICE
```

---

## 3. Complete JSON Invoice Structure

### Top-Level Fields
```json
{
    "uuid": "",
    "previousUUID": "",
    "referenceUUID": "",
    "referenceOldUUID": "",
    "deviceSerialNumber": "",
    "invoiceCounter": "",
    "invoiceNumber": "",
    "invoiceType": {
        "invoiceType": "",
        "invoiceTypeAll": ""
    },
    "seller": {},
    "buyer": {},
    "invoiceItems": [],
    "taxTotals": [],
    "netAmount": "",
    "qr": ""
}
```

### Seller Fields
```json
{
    "seller": {
        "seller-name": "",
        "seller-name-arabic": "",
        "seller-vat-number": "",
        "seller-street": "",
        "seller-building-number": "",
        "seller-plot-id": "",
        "seller-city": "",
        "seller-district": "",
        "seller-postal-zone": "",
        "seller-region": "",
        "seller-crn": ""
    }
}
```

### Buyer Fields (B2B Only)
```json
{
    "buyer": {
        "buyer-name": "",
        "buyer-vat-number": "",
        "buyer-street": "",
        "buyer-building-number": "",
        "buyer-plot-id": "",
        "buyer-city": "",
        "buyer-district": "",
        "buyer-postal-zone": "",
        "buyer-region": "",
        "buyer-crn": ""
    },
    "buyer-data-in-case-of-b2b-invoice-only": ""
}
```

### Invoice Items Array
```json
{
    "invoiceItems": [
        {
            "item-name": "",
            "quantity": "",
            "tax-percent": "",
            "total-value": "",
            "taxableItems": [
                {
                    "taxType": "",
                    "taxRate": "",
                    "taxAmount": "",
                    "taxableAmount": ""
                }
            ]
        }
    ]
}
```

### Tax Summary
```json
{
    "taxTotals": [
        {
            "taxType": "",
            "taxAmount": ""
        }
    ]
}
```

### QR Code Data
```json
{
    "qr": ""
}
```

### Commercial Discount Data
```json
{
    "commercialDiscountData": [],
    "itemDiscountData": [],
    "extraReceiptDiscountData": []
}
```

---

## 4. Complete XML Templates

### Invoice XML Structure
```xml
<?xml version="1.0" encoding="UTF-8"?>
<invoice>
    <invoice-number></invoice-number>
    <invoice-type></invoice-type>
    <invoice-type-all></invoice-type-all>
    <invoice-data/>
    <invoice-data>
        <invoice-items>
            <item-name></item-name>
            <quantity></quantity>
            <tax-percent></tax-percent>
            <tax-percent><total-value></total-value>
            <total-value></total-value>
            <taxableItems>
                <taxType></taxType>
            </taxableItems>
        </invoice-items>
    </invoice-data>
    
    <!-- Seller Data -->
    <seller-data/>
    <seller-name></seller-name>
    <seller-name-arabic></seller-name-arabic>
    <seller-vat-number></seller-vat-number>
    <seller-street></seller-street>
    <seller-building-number></seller-building-number>
    <seller-plot-id></seller-plot-id>
    <seller-city></seller-city>
    <seller-district></seller-district>
    <seller-postal-zone></seller-postal-zone>
    <seller-region></seller-region>
    <seller-crn></seller-crn>
    
    <!-- Buyer Data (B2B) -->
    <buyer-data-in-case-of-b2b-invoice-only/>
    <buyer-name></buyer-name>
    <buyer-vat-number></buyer-vat-number>
    <buyer-street></buyer-street>
    <buyer-building-number></buyer-building-number>
    <buyer-plot-id></buyer-plot-id>
    <buyer-city></buyer-city>
    <buyer-district></buyer-district>
    <buyer-postal-zone></buyer-postal-zone>
    <buyer-region></buyer-region>
    <buyer-crn></buyer-crn>
    
    <!-- Reference Invoice -->
    <refrenceInvoiceNumber></refrenceInvoiceNumber>
    <refrenceInvoiceDate></refrenceInvoiceDate>
    
    <!-- Tax -->
    <tax-percent></tax-percent>
    
    <!-- QR -->
    <qr></qr>
    
    <!-- Credit/Debit Note -->
    <add-the-next-2-items-with-return-debit-notes-only/>
    <creditor-details></creditor-details>
    <creditor></creditor>
    <debit></debit>
</invoice>
```

### Signed XML Wrapper
```xml
signed.xml  (output file)
```

### XML Authentication File
```
C:\saturn\help\xmlauth3.txt
C:\Files\Zatca\xmlauth3.txt
\Files\DBI\xmlauth3.txt
```

---

## 5. UUID Generation

### UUID Generation Command
```
toolkit.exe --generate-uuid --input-json-path summer_without_uuid.json --output-json-path summer_with_uuid.json
```

### UUID Files
```
C:\eToolKit\summer_without_uuid.json   (JSON before UUID)
C:\eToolKit\summer_with_uuid.json      (JSON with UUID)
\generateUUID.bat                       (batch script)
```

### UUID Fields in JSON
```json
{
    "uuid": "",
    "previousUUID": "",
    "referenceUUID": "",
    "referenceOldUUID": ""
}
```

### UUID Data Flow
```
Json before UUID -> toolkit.exe -> Json With UUID
Last UUID is tracked separately
```

---

## 6. QR Code Generation

### QR Code Sources
```
http://api.qrserver.com/v1/create-qr-code/?
http://chart.googleapis.com/chart?
C:\saturn\MessagingToolkit.QRCode.dll
C:\saturn\BouncyCastle.Crypto.dll
```

### QR Code Parameters
```
cht=qr&
charset-target=UTF-8&
choe=UTF-8&
bin.base64=
```

### QR Code Storage Paths
```
\Files\qr\
\qr.jpg
labirdo\titan3-backup\qr\
C:\eta-qr\
```

### QR Code Display
```
Old QR code printing
Best QR reader
The best QR reader
```

---

## 7. Authentication & CSID

### CSID / Certificate Pattern
```
C:\saturn\help\xmlauth3.txt     (XML authentication data)
C:\Files\Zatca\xmlauth3.txt     (copy)
\Files\DBI\xmlauth3.txt          (DBI folder copy)
xmlauth3.txt                     (saturnfiles download)
```

### Onboarding
```
C:\saturn\help\zatca.onboarding.form.xlsx
Registration in the second stage of the electronic invoice
```

### Token/Authentication Flow
```
Access Token
access_token
Authorization
Bearer 
authid
autho
```

### ZATCA Response Handling
```
zatca-response
Zatca-response.txt
Zatca\\
Zatca\\B2c\\
```

### Saturn Libraries
```
C:\saturn\BouncyCastle.Crypto.dll      (Crypto operations)
C:\saturn\MessagingToolkit.QRCode.dll  (QR generation)
C:\saturn\SDKNETFrameWorkLib.dll       (SDK)
C:\saturn\SDKNETFrameWorkLib.dll.config
C:\saturn\System.Net.Http.dll          (HTTP)
```

### Signing
```
signed.xml
Modzatcasign (3 procedures) - Signing module
Entry %1 has invalid signature
Failed to sign document
```

---

## 8. Tax Categories & Rates

### Tax Types
```json
{
    "taxType": ""
}
```

### Tax Values in Invoice
```
"taxableItems": []
"taxTotals": []
"taxType": ""
"tax-percent"
"taxPercent"
```

### VAT Categories (from invoice items)
```
Vat
VAT
vat
Vat%
Vat.No
Vat:
Vat registeration number
Tax
Tax number
Tax registration number
```

### VAT Status Management
```
Change Vat status
Change tax value
Change value of VAT for tax items
Cancellation of the vat with an increase in the price of items
Adding VAT to price (+) or removing it (-)
input + to add vat to price or - to remove it
```

---

## 9. Invoice Counter & Hash

### Counter Files
```
C:\saturn\zatca\computer-1\lastdata\counter.txt
C:\saturn\zatca\computer-1\lastdata\hash.txt
```

### Counter Management
```
Restart upcounter
Re-start upload counter
invoice-counter
```

### Hash Management
```
hash
Hash Check Failed
HashDigestLength
```

---

## 10. VAT Reporting

### VAT Report Types
```
Quarterly VAT report
Monthly VAT report
Annual VAT report
```

### VAT Report Fields
```
<sales-vat>
<sales-with-vat>
<sales-with-vat-no-disc>
<sales-non-taxable>
<sales-taxable>
<sales-cost-no-vat>
<sales-cost-with-vat>
<sales-invoices-number>
<sales-non-vated-items>
<sales-vated-items-without-vat>
<sales-total-vat>
<sales-total-valueb>
<sales-total-valuez>

<purchases-vat>
<purchases-with-vat>
<purchases-non-taxable>
<purchases-taxable>
<purchases-cost-no-vat>
<purchases-cost-with-vat>
<purchases-invoices-number>
<purchases-non-vated-items>
<purchases-vated-items-without-vat>
<purchases-total-vat>
<purchases-total-with-vat-actual>
<purchases-total-with-vat-cpu>
<purchases-total-gomhour>

<masrofat-vat>
<moves-masrofat-vat>
<moves-vat-purchases>
<moves-vat-sales>

<total-Cost-no-vat>
<total-Cost-with-vat>

<pharmacy-vatnumber>
```

### VAT Report File Paths
```
\Files\Accounting\Vat-reports\
VatFile-
VatFile-Result.txt
```

### VAT Report Operations
```
Re-apply vat on invoices
Manually resetting the Vat value in old invoices
Recalculation of sales invoices
Reset-old-vat
```

---

## 11. Validation Rules

### Seller Validation
```
Invalid seller information.
Invalid Seller Stakeholder number(GLN)
Indicated seller is deactivated
Seller GLN format is not appropriate! GLN must consist of 13 digits and they must be numbers!
Seller GLN information is missing or invalid.
```

### Buyer Validation
```
Invalid Buyer Stakeholder number.
Receiver GLN format is incorrect. GLN must consist of a 13 digit numeric value.
Invalid Buyer Stakeholder number.
Stakeholder type of buyer is not suitable for this operation
```

### Invoice Validation
```
Abnormal entries in the invoice
Delete invalid invoices
Invalid status.
Invalid isExportable value.
Invalid isExported value.
Invalid Prescription Date.
```

### Tax Validation
```
AUTHORIZATION_STATUS is empty or invalid
LEGAL_STATUS is empty or invalid
MARKETING_STATUS is empty or invalid
PRODUCT_CONTROL is empty or invalid
Product control status is empty or invalid
STATUS is empty or invalid
Status matrix definition is missing
```

### Product Validation
```
Product barcode information is missing or invalid
The format of the product information of the product (GTIN) is incompatible.
Product has expired.
```

---

## 12. File Download URLs (Saturn/ZATCA)

### Saturn Distribution
```
http://phycodsystems-001-site16.htempurl.com/saturnfiles/saturn.exe
http://phycodsystems-001-site16.htempurl.com/saturnfiles/BouncyCastle.Crypto.dll
http://phycodsystems-001-site16.htempurl.com/saturnfiles/MessagingToolkit.QRCode.dll
http://phycodsystems-001-site16.htempurl.com/saturnfiles/SDKNETFrameWorkLib.dll
http://phycodsystems-001-site16.htempurl.com/saturnfiles/SDKNETFrameWorkLib.dll.config
http://phycodsystems-001-site16.htempurl.com/saturnfiles/System.Net.Http.dll
http://phycodsystems-001-site16.htempurl.com/saturnfiles/summer.b2b.rar
http://phycodsystems-001-site16.htempurl.com/saturnfiles/xmlauth3.txt
http://phycodsystems-001-site16.htempurl.com/saturnfiles/zatca.onboarding.form.xlsx
```

### Saturn2 (Alternative)
```
http://phycodsystems-001-site17.atempurl.com/saturnfiles/saturn2.exe
http://phycodsystems-001-site17.atempurl.com/saturnfiles/BouncyCastle.Crypto.dll
http://phycodsystems-001-site17.atempurl.com/saturnfiles/MessagingToolkit.QRCode.dll
http://phycodsystems-001-site17.atempurl.com/saturnfiles/SDKNETFrameWorkLib.dll
http://phycodsystems-001-site17.atempurl.com/saturnfiles/SDKNETFrameWorkLib.dll.config
http://phycodsystems-001-site17.atempurl.com/saturnfiles/System.Net.Http.dll
```

### Developer Resources
```
http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/
http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/api-sign.rar
http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/summer.test.txt
```

### QR Code Library
```
http://phycodsystems-001-site12.htempurl.com/titan3/us/tools/quricol32.dll
C:\saturn\MessagingToolkit.QRCode.dll
```

---

## 13. Invoice Operations

### Invoice Actions
```
Delete contents of invoice
Delete drug from invoice
Delete entire invoice
Delete invalid invoices
Delete the invoice
Forced cleaning of an invoice
Clean invoices starting from 
Restore a deleted invoice
Copy invoice
Copy the invoice to a sales return invoice
Copy the invoice to sales invoice
Invoice type conversion
Modifiy invoice date
Search by invoice number
Bring all invoices
Bring invoices
All invoices
Today's invoices
```

### Invoice Numbering
```
Invoice.b2b.Number.
Titan Internal invoice number
The number printed on the paper invoice
The short code for the current invoice items
Invoice counter
```

### Invoice Display
```
Search for electronic invoice on server
View the electronic invoice for this invoice
Fake-invoice
Fake-invoice-csv
```

---

## 14. Saturn Onboarding Flow

### Onboarding Steps
```
1. Registration in the second stage of the electronic invoice
2. ZATCA onboarding form: zatca.onboarding.form.xlsx
3. Saturn companion service setup
4. xmlauth3.txt authentication file
5. Certificate/CSID generation
```

### Saturn Configuration
```
SDKNETFrameWorkLib.dll.config  (config file)
summer.test.b2b.normal.txt     (test invoice)
summer.txt                     (summer template)
summer_without_uuid.json       (pre-UUID)
summer_with_uuid.json          (post-UUID)
```

---

## 15. Module Procedures

### ModZatca (14 procedures)
Core ZATCA integration functions - invoice building, sending, response handling.

### ModZatca2Wraber (24 procedures)
Extended ZATCA functions - additional field mapping, validation, report generation.

### Modzatcasign (3 procedures)
XML/JSON signing operations for ZATCA compliance using BouncyCastle.

### FormVat (20 procedures)
VAT reporting UI - quarterly reports, sales/purchase VAT calculations.

### FormVat2 (38 procedures)
Extended VAT reporting - detailed breakdown, export, monthly/annual views.

### FormRsdDispatch (16 procedures)
RSD Dispatch integration - connects ZATCA with drug tracking for dispatched items.

---

## 16. Data Flow Summary

```
Invoice Created in Titan
    ↓
JSON Built (seller, buyer, items, tax)
    ↓
UUID Generated (toolkit.exe)
    ↓
JSON With UUID -> Saturn (saturn.exe)
    ↓
Saturn Signs (BouncyCastle) -> signed.xml
    ↓
QR Code Generated (MessagingToolkit.QRCode.dll)
    ↓
Response: zatca-response
    ↓
Stored: C:\saturn\zatca\computer-1\invoices\
Counter Updated: counter.txt
Hash Updated: hash.txt
```
