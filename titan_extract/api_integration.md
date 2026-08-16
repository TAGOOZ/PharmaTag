# TITAN.W1 (Phye.exe) — External API Integrations, ZATCA & DTTS Compliance

> Extracted from VB6 decompiled strings (26,970 UTF-16LE constants, 124 API imports, 336 objects)

---

## 1. DTTS (SFDA Drug Tracking & Tracing) — SOAP/WSDL Services

### 1.1 Service Endpoints (Production)

| Service | Endpoint URL | WSDL |
|---|---|---|
| **Pharmacy Sale** | `https://rsd.sfda.gov.sa:443/ws/PharmacySaleService/PharmacySaleService` | `http://dtts.sfda.gov.sa/PharmacySaleService` |
| **Pharmacy Sale Cancel** | `https://rsd.sfda.gov.sa:443/ws/PharmacySaleCancelService/PharmacySaleCancelService` | `http://dtts.sfda.gov.sa/PharmacySaleCancelService` |
| **Drug Dispatch** | `https://rsd.sfda.gov.sa:443/ws/DispatchService/DispatchService` | `http://dtts.sfda.gov.sa/DispatchService` |
| **Accept Dispatch** | `https://rsd.sfda.gov.sa:443/ws/AcceptDispatchService/AcceptDispatchService` | `http://dtts.sfda.gov.sa/AcceptDispatchService` |
| **Drug Return** | `https://rsd.sfda.gov.sa:443/ws/ReturnService/ReturnService` | `http://dtts.sfda.gov.sa/ReturnService` |
| **Drug Transfer** | `https://rsd.sfda.gov.sa:443/ws/TransferService/TransferService` | `http://dtts.sfda.gov.sa/TransferService` |

### 1.2 SOAP Envelope Structure

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <!-- Service-specific request body -->
  </soap:Body>
</soap:Envelope>
```

### 1.3 DTTS XML Request Templates

#### Pharmacy Sale Request
```xml
<m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">
  <PRODUCTLIST xmlns="">
    <PRODUCT>
      <GTIN>{gtin_code}</GTIN>
      <TradeName>{trade_name}</TradeName>
      <TOGLN xmlns="">{pharmacy_gln}</TOGLN>
      <XD>{expiry_date}</XD>
      <SN>{serial_number}</SN>
      <BN>{batch_number}</BN>
    </PRODUCT>
  </PRODUCTLIST>
  <PRESCRIPTIONID xmlns="">{prescription_id}</PRESCRIPTIONID>
  <PRESCRIPTIONDATE xmlns="">{prescription_date}</PRESCRIPTIONDATE>
  <DOCTORID xmlns="">{doctor_id}</DOCTORID>
  <PATIENTNATIONALID xmlns="">{national_id}</PATIENTNATIONALID>
</m:PharmacySaleServiceRequest>
```

#### Pharmacy Sale Cancel Request
```xml
<m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">
  <!-- Cancellation reference to original sale -->
</m:PharmacySaleCancelServiceRequest>
```

#### Drug Dispatch Request
```xml
<m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">
  <PRODUCTLIST xmlns="">
    <PRODUCT>
      <GTIN>{gtin_code}</GTIN>
      <TradeName>{trade_name}</TradeName>
      <TOGLN xmlns="">{source_pharmacy_gln}</TOGLN>
      <XD>{expiry_date}</XD>
      <SN>{serial_number}</SN>
      <BN>{batch_number}</BN>
    </PRODUCT>
  </PRODUCTLIST>
  <DISPATCHNOTIFICATIONID xmlns="">{dispatch_notification_id}</DISPATCHNOTIFICATIONID>
</m:DispatchServiceRequest>
```

#### Accept Dispatch Request
```xml
<m:AcceptDispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/AcceptDispatchService">
  <DISPATCHNOTIFICATIONID xmlns="">{dispatch_notification_id}</DISPATCHNOTIFICATIONID>
</m:AcceptDispatchServiceRequest>
```

#### Drug Return Request
```xml
<m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">
  <PRODUCTLIST xmlns="">
    <PRODUCT>
      <GTIN>{gtin_code}</GTIN>
      <TradeName>{trade_name}</TradeName>
      <TOGLN xmlns="">{pharmacy_gln}</TOGLN>
      <XD>{expiry_date}</XD>
      <SN>{serial_number}</SN>
      <BN>{batch_number}</BN>
    </PRODUCT>
  </PRODUCTLIST>
</m:ReturnServiceRequest>
```

#### Drug Transfer Request
```xml
<m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">
  <PRODUCTLIST xmlns="">
    <PRODUCT>
      <GTIN>{gtin_code}</GTIN>
      <TradeName>{trade_name}</TradeName>
      <TOGLN xmlns="">{target_pharmacy_gln}</TOGLN>
      <XD>{expiry_date}</XD>
      <SN>{serial_number}</SN>
      <BN>{batch_number}</BN>
    </PRODUCT>
  </PRODUCTLIST>
</m:TransferServiceRequest>
```

### 1.4 DTTS Product Fields

| Field | Description | Format |
|---|---|---|
| `GTIN` | Global Trade Item Number (barcode) | Numeric, 14 digits |
| `TradeName` | Drug trade name | String |
| `TOGLN` | Target Organization GLN | Numeric, 13 digits (e.g. `0000000000000`) |
| `XD` | Expiry date | Date string |
| `SN` | Serial/lot number | String |
| `BN` | Batch number | String |
| `DISPATCHNOTIFICATIONID` | Dispatch tracking ID | String |

### 1.5 DTTS Error Codes

| Code | Meaning |
|---|---|
| `<EID>` | Information is missing or invalid |
| `<MI>` | Manufacturer GLN information is missing or invalid |
| `<PID>` | Product ID information is missing or invalid |
| `<PT>` | Product type area is missing or invalid. Only drug (PP) is accepted |
| `<XD>` | Expiry date information is missing or incorrect |

### 1.6 DTTS Validation Messages

- "The format of the product information of the product (GTIN) is incompatible."
- "This GTIN + BN has been recalled"
- "This GTIN/BN has been blocked. First perform recall operation in Block Screen."
- "Undefined Drug (GTIN does not exist)."
- "This batch number was used before with a different expire date or production date."

### 1.7 Module Mapping

| Module | Purpose | Procedures |
|---|---|---|
| `ModDTTS` | Main DTTS integration (48 procs) | Sale, cancel, dispatch, accept, return, transfer |
| `Formdtts` | DTTS UI form (26 procs) | User interface for DTTS operations |
| `ModDttsEgypt` | Egypt DTTS variant (2 procs) | Egyptian drug tracking |

---

## 2. ZATCA E-Invoicing (Fatoorah) — REST/JSON API

### 2.1 Architecture Overview

The system uses a **two-stage process**:

1. **Titan VB6** builds the invoice JSON ("summer" format)
2. **External toolkit** (`toolkit.exe` or `saturn.exe`) handles:
   - UUID generation
   - CSID (Cryptographic Stamp ID) signing
   - ZATCA API submission
   - QR code generation

### 2.2 External Tools

| Tool | Location | Purpose |
|---|---|---|
| `toolkit.exe` | `C:\eToolKit\toolkit.exe` | UUID generation, ZATCA signing |
| `saturn.exe` | `C:\saturn\saturn.exe` | ZATCA integration (alternative) |
| `saturn2.exe` | `C:\saturn\saturn2.exe` | ZATCA integration (version 2) |
| `saturnonboard.exe` | Remote download | ZATCA onboarding tool |
| `api-sign.aspx` | `C:\api-sign.aspx` | Digital signing endpoint |

### 2.3 UUID Generation Flow

```bash
toolkit.exe --generate-uuid \
  --input-json-path summer_without_uuid.json \
  --output-json-path summer_with_uuid.json
```

### 2.4 ZATCA Authentication (OAuth 2.0)

**Token Endpoint:**
```
POST {zatca_base_url}/connect/token
```

**Parameters:**
- `grant_type=client_credentials`
- `client_id={client_id}`
- `client_secret={client_secret}`

**Response:**
```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": ...
}
```

**Usage:**
```
Authorization: Bearer {access_token}
```

### 2.5 ZATCA Invoice JSON Structure (Full "Summer" Format)

#### Top-Level Structure
```json
{
  "header": {
    "uuid": "",
    "dateTimeIssued": "",
    "receiptNumber": "",
    "receiptType": "",
    "invoiceCounter": 0,
    "previousUUID": "",
    "referenceUUID": "",
    "referenceOldUUID": "",
    "deviceSerialNumber": "",
    "type": "",
    "typeVersion": "",
    "activityCode": "",
    "currency": "",
    "exchangeRate": 0,
    "taxCurrency": "",
    "documentUseReason": "",
    "companyTradeName": "",
    "brandName": "",
    "branchCode": "",
    "branchAddress": {
      "street": "",
      "buildingNumber": "",
      "regionCity": "",
      "governate": "",
      "postalCode": "",
      "country": ""
    },
    "rIN": ""
  },
  "seller": {
    "name": "",
    "nameArabic": "",
    "vatNumber": "",
    "street": "",
    "buildingNumber": "",
    "regionCity": "",
    "district": "",
    "governate": "",
    "postalCode": "",
    "country": "",
    "crn": "",
    "vendorId": ""
  },
  "buyer": {
    "name": "",
    "vatNumber": "",
    "street": "",
    "buildingNumber": "",
    "regionCity": "",
    "district": "",
    "governate": "",
    "postalCode": "",
    "country": "",
    "crn": ""
  },
  "documentType": {
    "receiptType": "",
    "receiptTypeVersion": ""
  },
  "taxTotals": [
    {
      "taxType": "",
      "rate": 0,
      "amount": 0
    }
  ],
  "totalSales": 0,
  "totalDiscount": 0,
  "totalCommercialDiscount": 0,
  "totalItemsDiscount": 0,
  "netAmount": 0,
  "totalAmount": 0,
  "paymentMethod": "",
  "itemData": [],
  "extraReceiptDiscountData": []
}
```

#### Item Data Structure
```json
{
  "itemCode": "",
  "internalCode": "",
  "description": "",
  "itemType": "",
  "unitType": "",
  "quantity": 0,
  "taxableItems": [
    {
      "taxType": "",
      "rate": 0,
      "amount": 0,
      "subType": ""
    }
  ],
  "commercialDiscountData": [],
  "itemDiscountData": [],
  "unitPrice": 0,
  "quantityUnitPrice": 0,
  "netSale": 0,
  "total": 0,
  "taxable": true,
  "taxableItemPrice": 0,
  "valueDifference": 0,
  "grossNetAmount": 0,
  "grouper": {
    "nameAr": "",
    "nameEn": ""
  }
}
```

### 2.6 ZATCA VAT Fields

| Field | Description |
|---|---|
| `taxType` | Tax type code (VAT) |
| `rate` | VAT rate (15%) |
| `amount` | Tax amount |
| `subType` | Tax sub-type |

### 2.7 ZATCA Invoice Types

| Code | Type |
|---|---|
| `S` | Standard invoice |
| `B2B` | Business-to-business |
| `B2C` | Business-to-consumer |
| `Simplified` | Simplified tax invoice |
| `Return` | Return invoice |
| `DebitNote` | Debit note |
| `CreditNote` | Credit note |

### 2.8 ZATCA Configuration Files

| File | Location | Purpose |
|---|---|---|
| `appsettings.json` | `C:\eToolKit\appsettings.json` | ZATCA API config (URLs, keys) |
| `summer.txt` | `\Files\DB\summer.txt` | Invoice template data |
| `summer.test.txt` | `\Files\DBI\summer.test.txt` | Test invoice data |
| `summer_without_uuid.json` | `C:\eToolKit\summer_without_uuid.json` | Pre-UUID invoice JSON |
| `summer_with_uuid.json` | `C:\eToolKit\summer_with_uuid.json` | Post-UUID invoice JSON |
| `xmlauth3.txt` | `C:\saturn\help\xmlauth3.txt` | ZATCA XML auth config |
| `zatca.onboarding.form.xlsx` | `C:\saturn\help\zatca.onboarding.form.xlsx` | Onboarding spreadsheet |
| `counter.txt` | `C:\saturn\zatca\computer-1\lastdata\counter.txt` | Invoice counter |
| `hash.txt` | `C:\saturn\zatca\computer-1\lastdata\hash.txt` | Previous invoice hash |

### 2.9 ZATCA Dependencies (saturn.exe)

| DLL | Purpose |
|---|---|
| `BouncyCastle.Crypto.dll` | Cryptographic operations (CSID signing) |
| `MessagingToolkit.QRCode.dll` | QR code generation |
| `SDKNETFrameWorkLib.dll` | ZATCA SDK wrapper |
| `System.Net.Http.dll` | HTTP client |
| `aspnetcorev2_inprocess.dll` | .NET hosting |
| `e_sqlite3.dll` | Local data storage |

### 2.10 Module Mapping

| Module | Purpose | Procedures |
|---|---|---|
| `ModZatca` | Core ZATCA logic (14 procs) | Invoice building, API calls |
| `ModZatca2Wraber` | ZATCA v2 Wraber integration (24 procs) | Updated ZATCA API |
| `Modzatcasign` | ZATCA signing (3 procs) | CSID/digital signature |
| `ModSaturn` | Saturn ZATCA tool (29 procs) | Alternative ZATCA client |
| `FormVat` | VAT form (20 procs) | VAT settings UI |
| `FormVat2` | VAT form v2 (38 procs) | Advanced VAT UI |
| `ModVatReport` | VAT reporting (3 procs) | VAT report generation |
| `FormRsdDispatch` | RSD Dispatch form (16 procs) | DTTS dispatch UI |
| `ModEtaWrappper` | ETA wrapper (7 procs) | Egyptian Tax Authority |

### 2.11 ZATCA QR Code Generation

```bash
http://api.qrserver.com/v1/create-qr-code/?data={base64_tlv_encoded_data}
```

The QR code contains TLV-encoded data with:
- Seller name, address
- VAT number
- Timestamp
- Invoice total
- VAT amount

---

## 3. Titan Cloud & Online Services

### 3.1 Cloud API Base URLs

```
http://phycodsystems-001-site12.htempurl.com/
http://phycodsystems-001-site16.htempurl.com/
http://phycodsystems-001-site17.atempurl.com/
```

### 3.2 Cloud API Endpoints

| Endpoint | Purpose |
|---|---|
| `/titan-users/allinone/data/` | Cloud data sync |
| `/titan-users/allinone/mobiles/` | Mobile data sync |
| `/titan-users/data-for-sale/avros/saudi/` | Saudi pharmacy data |
| `/titan-users/data-for-sale/avros/egypt/` | Egypt pharmacy data |
| `/titan-users/data-for-sale/avros/world/` | World pharmacy data |
| `/titan-users/floor2/` | Floor 2 data |
| `/titan-users/titan-mobile/files/` | Mobile file sync |
| `/titan-users/drugs-unify/` | Drug name unification |
| `/titan-users/send-to/` | Data transmission |
| `/titan-users/t-link/` | T-Link integration |
| `/titan-users/by-dos/` | DOS-based data access |
| `/allinone/` | All-in-one data package |
| `/mypharmacy/` | Pharmacy data |
| `/share/` | Shared data |
| `/fromto/` | Data transfer range |

### 3.3 Titan Cloud File Downloads

| File | URL |
|---|---|
| `Phye.exe` (main app) | `/Titan3/Us/world/Phye.exe` |
| `server.connector.exe` | `/Titan3/Us/world/server.connector.exe` |
| `emerg.w.exe` | `/Titan3/Us/world/emerg.w.exe` |
| `xi.dll` | `/900/titan.cloud/xi.dll` |
| `anydesk.exe` | `/900/titan.cloud/anydesk.exe` |
| `flex.exe` | `/900/flex.exe` |
| `toolkit.exe` | `/900/etatoolkit/toolkit.exe` |
| `tracer.exe` | `/900/tracer/tracer.exe` |
| `showme.exe` | `/Titan3/Us/showme.exe` |
| `easeus.exe` | `/Titan3/Us/easeus.exe` |
| `Labirdo.rasd.exe` | `/900/Labirdo.rasd.exe` |
| `curl.exe` | `/900/curl/curl.exe` |

### 3.4 Titan Cloud HTML Pages

| Page | URL |
|---|---|
| Titan home | `/Titan3/Us/titan.html` |
| DrugEye | `/Titan3/Us/drugeye.html` |
| Upgrade info | `/Titan3/Us/upgrade.html` |
| Programs | `/Titan3/Us/programs.html` |
| Daily notes | `/Titan3/Us/dailynotes.html` |
| Paper | `/Titan3/Us/paper.html` |

### 3.5 Module Mapping

| Module | Purpose | Procedures |
|---|---|---|
| `ModTitanCloud` | Cloud sync engine (16 procs) | Upload/download, sync |
| `ModNetwork` | Network operations (65 procs) | FTP, HTTP, connectivity |
| `ModFTP` | FTP operations (29 procs) | FTP file transfer |
| `ModMobile` | Mobile integration (9 procs) | Mobile app data |
| `FormNetwasel` | Network form (2 procs) | Network settings UI |
| `FormFaryNet` | Fary network (8 procs) | Network integration |
| `Modfarynet` | Fary network module (2 procs) | Network protocol |
| `ModEcommerce` | E-commerce (4 procs) | Online sales |
| `FormEcommerce` | E-commerce form (6 procs) | E-commerce UI |

---

## 4. External APIs & Web Services

### 4.1 Country Information Service (SOAP)

```
http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso
```

XML namespaces:
```xml
<m:ListOfCurrenciesByCode xmlns:m="http://webservices.oorsprong.org/websamples.countryinfo">
</m:ListOfCurrenciesByCode>
```

### 4.2 QR Code Generation API

```
http://api.qrserver.com/v1/create-qr-code/?data={url_encoded_data}
```

### 4.3 Titan News & Updates

```
http://phycodsystems-001-site12.htempurl.com/Titan3/Us/TitanNews.txt
http://www.drugeye.pharorg.com
http://www.drugeye.pharorg.com/rsd-api/start.aspx
http://www.akhbarak.net/
```

---

## 5. FTP Integration (ModFTP)

### 5.1 FTP Operations

| Function | API |
|---|---|
| Open connection | `InternetOpenA`, `InternetConnectA` |
| Upload file | `FtpPutFileA` |
| Download file | `FtpGetFileA` |
| Delete file | `FtpDeleteFileA` |
| Open remote file | `FtpOpenFileA` |
| List files | `FtpFindFirstFileA`, `InternetFindNextFileA` |
| Change directory | `FtpSetCurrentDirectoryA` |
| Get file size | `FtpGetFileSize` |
| Get current dir | `FtpGetCurrentDirectoryA` |

### 5.2 FTP Upload Pattern (PowerShell)

```powershell
$server = "ftp://..."
$username = "..."
$password = "..."
$cred = New-Object System.Net.NetworkCredential($username, $password)
$wc = New-Object System.Net.WebClient
$wc.Credentials = $cred
$wc.UploadFile($remoteFile, "STOR", $localFile)
```

### 5.3 FTP Upload Pattern (curl)

```bash
curl.exe --ftp-pasv --retry 3 --retry-delay 2 \
  -T "{local_file}" \
  --stderr "curl_upload.log" \
  --write-out "%{response_code}" \
  "{ftp_url}"
```

### 5.4 FTP Command Script Pattern

```bat
>> ftpcmd.dat
open {ftp_server}
{username}
{password}
put {local_file} {remote_file}
bye
> ftpcmd.dat
ftp -s:ftpcmd.dat
```

---

## 6. Authentication & Credentials Patterns

### 6.1 ZATCA OAuth2 Flow

```
1. POST /connect/token
   grant_type=client_credentials
   client_id={client_id}
   client_secret={client_secret}

2. Response: {"access_token": "...", "token_type": "Bearer"}

3. Use: Authorization: Bearer {access_token}
```

### 6.2 Credential Storage

| Location | Purpose |
|---|---|
| `<client_id>` / `<client_secret>` | ZATCA OAuth2 credentials (XML) |
| `<secret>` / `<pass>` | General passwords (XML) |
| `<authid>` | Authentication ID (XML) |
| `<userid>` / `<username>` | User credentials (XML) |
| `access_token` | OAuth2 bearer token (JSON) |

### 6.3 Database Connection Strings

```
;DATABASE={db_name}
;UID={username}
;PWD={password}
```

### 6.4 Windows API Crypto Functions

```vb
CryptStringToBinaryW Lib "Crypt32"
CryptBinaryToStringW Lib "Crypt32"
```

---

## 7. E-Commerce Integration (ModEcommerce)

### 7.1 E-Commerce JSON Template

```json
{
  "products": [
    {
      "sku": "",
      "barcode": "",
      "name": "",
      "active": true,
      "maximum_sales_quantity": 0,
      "quantity": 0
    }
  ]
}
```

### 7.2 HungerStation Token

```
\Files\DBI\hungerstation.token.txt
```

---

## 8. Egyptian Integration (ModDttsEgypt, ModEtaWrappper)

### 8.1 Egyptian Tax Authority

- `ModEtaWrappper` (7 procs) — Egyptian Tax Authority wrapper
- `ModEta` class (48 procs) — ETA data model
- `FormEtaInfo` (9 procs) — ETA information UI
- `FormAccUploader` (47 procs) — Accounting data upload

### 8.2 Egypt-Specific Endpoints

```
/titan-users/data-for-sale/avros/egypt/
```

---

## 9. System Architecture Summary

```
┌─────────────────────────────────────────────────────┐
│                 TITAN.W1 (Phye.exe)                 │
│                VB6 Desktop Application              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  ModDTTS      │  │  ModZatca    │  │ ModNetwork│ │
│  │  (48 procs)   │  │  (14 procs)  │  │ (65 procs)│ │
│  │  DTTS/SFDA    │  │  ZATCA v1    │  │ FTP/HTTP  │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                 │                │         │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌─────┴─────┐ │
│  │  ModZatca2   │  │  ModSaturn   │  │ ModFTP    │ │
│  │  (24 procs)  │  │  (29 procs)  │  │ (29 procs)│ │
│  │  ZATCA v2    │  │  Saturn/ZATCA│  │ WinInet   │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                 │                │         │
│         ▼                 ▼                ▼         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ SOAP/WSDL    │  │ REST/JSON    │  │ FTP/HTTP  │ │
│  │ RSF.SFDA     │  │ toolkit.exe  │  │ Cloud CDN │ │
│  │ .GOV.SA      │  │ saturn.exe   │  │ phycod    │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ModTitanCloud (16)  │  ModEcommerce (4)            │
│  Cloud Sync          │  Online Sales                │
└─────────────────────────────────────────────────────┘
```

---

## 10. Key Module Index

| Module | Procs | Purpose |
|---|---|---|
| `ModDTTS` | 48 | SFDA Drug Tracking |
| `ModZatca` | 14 | ZATCA e-Invoicing |
| `ModZatca2Wraber` | 24 | ZATCA v2 |
| `Modzatcasign` | 3 | ZATCA signing |
| `ModSaturn` | 29 | Saturn ZATCA tool |
| `ModNetwork` | 65 | Network operations |
| `ModFTP` | 29 | FTP transfers |
| `ModTitanCloud` | 16 | Cloud sync |
| `ModMobile` | 9 | Mobile integration |
| `ModEcommerce` | 4 | E-commerce |
| `ModEtaWrappper` | 7 | Egyptian Tax Authority |
| `ModDttsEgypt` | 2 | Egypt drug tracking |
| `ModIntegrations` | 18 | General integrations |
| `ModOuterConnections` | 18 | External connections |
| `ModServerConnections` | 1 | Server connections |
| `FormRsdDispatch` | 16 | DTTS dispatch form |
| `Formdtts` | 26 | DTTS UI |
| `FormVat` | 20 | VAT settings |
| `FormVat2` | 38 | Advanced VAT |
| `FormVatfakeInvo` | 15 | VAT fake invoice |
| `FormIntegrations` | 9 | Integrations UI |
| `FormEtaInfo` | 9 | ETA info |
| `FormElectroniaChecker` | 14 | Electronics checker |
| `FormFaryNet` | 8 | Network form |
| `FormEcommerce` | 6 | E-commerce UI |

---

## 11. Compliance Notes

### Saudi Market Requirements

1. **DTTS Compliance**: All drug sales, transfers, returns, and dispatches must be reported to SFDA via SOAP/WSDL services at `rsd.sfda.gov.sa`
2. **ZATCA Compliance**: All invoices must be submitted to ZATCA via the Saturn/eToolKit integration with:
   - UUID generation
   - CSID digital signing
   - QR code embedding
   - Invoice hash chaining (previous UUID reference)
3. **VAT**: 15% standard rate, with tax item tracking per invoice line
4. **Drug Tracking**: GTIN-based tracking with batch/lot numbers, expiry dates, and GLN-based pharmacy identification
