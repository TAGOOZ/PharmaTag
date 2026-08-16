# DTTS (SFDA Drug Track and Trace System) - Complete Integration Specification

## Source Modules
- **ModDTTS** (48 procedures) - Core DTTS integration
- **ModDttsEgypt** (2 procedures) - Egyptian DTTS variant
- **Formdtts** (26 procedures) - DTTS UI form
- **FormRsdDispatch** (16 procedures) - RSD dispatch form
- **FormEtaInfo** (9 procedures) - ETA info form (Egypt)
- **FormGovData** (5 procedures) - Government data form
- **ModGS1Reader** (24 procedures) - GS1 barcode reader
- **ModCountries** (24 procedures) - Country-specific integrations
- **ModTafqit** (4 procedures) - Arabic number formatting

---

## 1. SFDA RSD Web Service Endpoints (6 SOAP Services)

### Service 1: PharmacySaleService
```
URL: https://rsd.sfda.gov.sa:443/ws/PharmacySaleService/PharmacySaleService
WSDL: https://rsd.sfda.gov.sa:443/ws/PharmacySaleService/PharmacySaleService?wsdl
Namespace: http://dtts.sfda.gov.sa/PharmacySaleService
Request Element: <m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">
```

### Service 2: PharmacySaleCancelService
```
URL: https://rsd.sfda.gov.sa:443/ws/PharmacySaleCancelService/PharmacySaleCancelService
WSDL: https://rsd.sfda.gov.sa:443/ws/PharmacySaleCancelService/PharmacySaleCancelService?wsdl
Namespace: http://dtts.sfda.gov.sa/PharmacySaleCancelService
Request Element: <m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">
```

### Service 3: DispatchService
```
URL: https://rsd.sfda.gov.sa:443/ws/DispatchService/DispatchService
WSDL: https://rsd.sfda.gov.sa:443/ws/DispatchService/DispatchService?wsdl
Namespace: http://dtts.sfda.gov.sa/DispatchService
Request Element: <m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">
```

### Service 4: AcceptDispatchService
```
URL: https://rsd.sfda.gov.sa:443/ws/AcceptDispatchService/AcceptDispatchService
WSDL: https://rsd.sfda.gov.sa:443/ws/AcceptDispatchService/AcceptDispatchService?wsdl
Namespace: http://dtts.sfda.gov.sa/AcceptDispatchService
Request Element: <m:AcceptDispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/AcceptDispatchService">
```

### Service 5: ReturnService
```
URL: https://rsd.sfda.gov.sa:443/ws/ReturnService/ReturnService
WSDL: https://rsd.sfda.gov.sa:443/ws/ReturnService/ReturnService?wsdl
Namespace: http://dtts.sfda.gov.sa/ReturnService
Request Element: <m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">
```

### Service 6: TransferService
```
URL: https://rsd.sfda.gov.sa:443/ws/TransferService/TransferService
WSDL: https://rsd.sfda.gov.sa:443/ws/TransferService/TransferService?wsdl
Namespace: http://dtts.sfda.gov.sa/TransferService
Request Element: <m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">
```

### RSD Portal URLs
```
Account:    https://rsd.sfda.gov.sa/smp/Account/Index
Portal:     https://rsd.sfda.gov.sa/sop?fbclid=IwAR1pit_DvwLHRkNofpsw2pV5ZUW8mSzct1IA_X3FgBs2VXnyc5lJSlIAUlo
API:        http://www.drugeye.pharorg.com/rsd-api/start.aspx
Website:    Drug Track and Trace System Website (RSD)
```

---

## 2. SOAP Envelope Structure

### Standard SOAP Envelope
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <!-- Service-specific request element here -->
  </soap:Body>
</soap:Envelope>
```

### SOAP Content Type
```
text/xml; charset=utf-8
```

### SOAP Action
```
SOAPAction
SOAP
soap-envelope
*soap-envelope*
```

---

## 3. PharmacySaleService - Complete XML Template

### Request Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:PharmacySaleServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleService">
      
      <!-- Pharmacy Information -->
      <pharmacy-name-arabic></pharmacy-name-arabic>
      <pharmacy-name-engilsh></pharmacy-name-engilsh>
      <pharmacy-Adress></pharmacy-Adress>
      <pharmacy-CRN></pharmacy-CRN>
      <pharmacy-mobile></pharmacy-mobile>
      <pharmacy-Mobile></pharmacy-Mobile>
      <pharmacy-vatnumber></pharmacy-vatnumber>
      
      <!-- Seller (Pharmacy) Stakeholder -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Prescription Information -->
      <PRESCRIPTIONID xmlns=""></PRESCRIPTIONID>
      <PRESCRIPTIONDATE xmlns=""></PRESCRIPTIONDATE>
      <DOCTORID xmlns=""></DOCTORID>
      <PATIENTNATIONALID xmlns="">28303011503213</PATIENTNATIONALID>
      
      <!-- Receipt Information -->
      <receiptType></receiptType>
      <receiptNumber></receiptNumber>
      
      <!-- Product List -->
      <PRODUCTLIST xmlns="">
        <GTIN></GTIN>
        <TOGLN xmlns="">0000000000000</TOGLN>
        <BN></BN>
        <XD></XD>
        <SN></SN>
        <PT></PT>
        <PC></PC>
        <UP></UP>
        <QN></QN>
        <DISPENSED></DISPENSED>
      </PRODUCTLIST>
      
    </m:PharmacySaleServiceRequest>
  </soap:Body>
</soap:Envelope>
```

---

## 4. PharmacySaleCancelService - Complete XML Template

### Request Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:PharmacySaleCancelServiceRequest xmlns:m="http://dtts.sfda.gov.sa/PharmacySaleCancelService">
      
      <!-- Notification ID to Cancel -->
      <DISPATCHNOTIFICATIONID xmlns=""></DISPATCHNOTIFICATIONID>
      
      <!-- Pharmacy Information -->
      <pharmacy-name-arabic></pharmacy-name-arabic>
      <pharmacy-name-engilsh></pharmacy-name-engilsh>
      <pharmacy-Adress></pharmacy-Adress>
      <pharmacy-CRN></pharmacy-CRN>
      <pharmacy-mobile></pharmacy-mobile>
      <pharmacy-vatnumber></pharmacy-vatnumber>
      
      <!-- Seller Stakeholder -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Product List for Cancellation -->
      <PRODUCTLIST xmlns="">
        <GTIN></GTIN>
        <BN></BN>
        <XD></XD>
        <SN></SN>
        <QN></QN>
      </PRODUCTLIST>
      
    </m:PharmacySaleCancelServiceRequest>
  </soap:Body>
</soap:Envelope>
```

---

## 5. DispatchService - Complete XML Template

### Request Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:DispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/DispatchService">
      
      <!-- Notification ID -->
      <DISPATCHNOTIFICATIONID xmlns=""></DISPATCHNOTIFICATIONID>
      
      <!-- Sender (Warehouse/Source) Information -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Receiver (Pharmacy/Destination) GLN -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Product List -->
      <PRODUCTLIST xmlns="">
        <GTIN></GTIN>
        <BN></BN>
        <XD></XD>
        <SN></SN>
        <PT></PT>
        <QN></QN>
      </PRODUCTLIST>
      
    </m:DispatchServiceRequest>
  </soap:Body>
</soap:Envelope>
```

---

## 6. AcceptDispatchService - Complete XML Template

### Request Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:AcceptDispatchServiceRequest xmlns:m="http://dtts.sfda.gov.sa/AcceptDispatchService">
      
      <!-- Notification ID to Accept -->
      <DISPATCHNOTIFICATIONID xmlns=""></DISPATCHNOTIFICATIONID>
      
      <!-- Receiver (Pharmacy) GLN -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Product List to Accept -->
      <PRODUCTLIST xmlns="">
        <GTIN></GTIN>
        <BN></BN>
        <XD></XD>
        <SN></SN>
        <QN></QN>
      </PRODUCTLIST>
      
    </m:AcceptDispatchServiceRequest>
  </soap:Body>
</soap:Envelope>
```

---

## 7. ReturnService - Complete XML Template

### Request Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:ReturnServiceRequest xmlns:m="http://dtts.sfda.gov.sa/ReturnService">
      
      <!-- Sender (Pharmacy returning) GLN -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Receiver (Warehouse) GLN -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Product List for Return -->
      <PRODUCTLIST xmlns="">
        <GTIN></GTIN>
        <BN></BN>
        <XD></XD>
        <SN></SN>
        <PT></PT>
        <QN></QN>
      </PRODUCTLIST>
      
    </m:ReturnServiceRequest>
  </soap:Body>
</soap:Envelope>
```

---

## 8. TransferService - Complete XML Template

### Request Template
```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:TransferServiceRequest xmlns:m="http://dtts.sfda.gov.sa/TransferService">
      
      <!-- Sender (Source Pharmacy) GLN -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Receiver (Destination Pharmacy) GLN -->
      <TOGLN xmlns="">0000000000000</TOGLN>
      
      <!-- Product List for Transfer -->
      <PRODUCTLIST xmlns="">
        <GTIN></GTIN>
        <BN></BN>
        <XD></XD>
        <SN></SN>
        <PT></PT>
        <QN></QN>
      </PRODUCTLIST>
      
    </m:TransferServiceRequest>
  </soap:Body>
</soap:Envelope>
```

---

## 9. Drug/Product Fields

### GTIN (Global Trade Item Number)
```
GTIN
<GTIN></GTIN>
</GTIN>
The format of the product information of the product (GTIN) is incompatible.
Undefined Drug (GTIN does not exist).
This GTIN + BN has been recalled
This GTIN/BN has been blocked. First perform recall operation in Block Screen.
```

### Batch Number (BN)
```
BN
Batch Number
Batch
batch and serial
Either <BN> batch number field does not exist or is invalid.
The format of the batch number of the product is incompatible.
This batch number was used before with a different expire date or production date.
Indicated batch number has been recalled.
```

### Expiry Date (XD)
```
XD
Expiry Date
<expire></expire>
</expire>
ExpireId
XD format validation
The format of the expiry date of the product (XD) is incompatible.
<XD> Expiry date information is missing or incorrect.
Expiry Date cannot exceed Production Date more than 7 years.
Product has expired.
```

### Serial Number (SN)
```
SN
SerialNumber
Serial
Format of the serial number is invalid.
Serial number is empty or invalid.
In <PRODUCTS> products' serial numbers <SN> information is not entered.
This Serial Number is already registered.
this Serial has copied to clipboard
```

### Product Type (PT)
```
PT
<PT> Product type area is missing or invalid product type... Only drug (PP) is accepted.
Product type: PP (Pharmaceutical)
```

### Product Control (PC)
```
PC
PRODUCT_CONTROL is empty or invalid
Product control status is empty or invalid
```

### Unit Price (UP)
```
UP
```

### Quantity (QN)
```
QN
```

### Dispensed Flag
```
DISPENSED
```

### Product Status Flags
```
Product control status is empty or invalid
Stakeholder status is empty or invalid
Product has been consumed.
Product has been recalled.
Product has been recalled at another stakeholder level.
Product registered on you has been recalled.
Product registered on you has been recalled at another stakeholder level.
The product is in deactivated status
The product is not deactivated.
The product is not deactivated by you.
The product has already been deactivated.
The product is blocked.
The product is recalled
The Product has been recalled.
The product has already been sold by pharmacy.
The product is already registered in another pharmacy.
The product is already registered in another hospital.
The product is already registered in another hospital's stock.
The product is in another hospital's stock.
The product was sold to the reimbursment institution. The sale should be canceled based on prescription.
The product was exported by another stakeholder.
The product has already been exported.
Product has been exported.
```

---

## 10. Stakeholder/GLN Fields

### GLN (Global Location Number)
```
GLN
TOGLN
First 13 characters of user name must be the same with GLN
Invalid GLN format.
Invalid destination GLN.
Sender GLN format is not appropriate! GLN must consist of 13 digits and they must be numbers!
Sender GLN information is missing or invalid.
Receiver GLN format is incorrect. GLN must consist of a 13 digit numeric value.
Source GLN information is missing
Target GLN information is missing
The entered GLN is not a pharmacy GLN.
Enput Target GLN
Inpu GLN for this supplier
```

### Stakeholder Types
```
Stakeholder
Stakeholder type of buyer is not suitable for this operation
Stakeholder type of seller is not suitable for this operation
Stakeholder type cannot be ull.
Stakeholder type is empty or invalid
Invalid stakeholder type
Stakeholder status is empty or invalid
Stakeholder name is empty or invalid
Stakeholder not found.
Invalid Seller Stakeholder number(GLN)
Invalid Buyer Stakeholder number.
Invalid Stakeholder number (GLN)
Undefined Stakeholder number (GLN)
Undefined Seller Stakeholder
```

### Stakeholder Status
```
Indicated seller is deactivated
Sender stakeholder is passive
Receiver stakeholder is passive
The receiver is deactivated.
Your account is deactivated. Apply to your system manager.
Invalid deactivation reason
```

### Stakeholder Authorization
```
Stakeholder is unauthorized for this operation
This stakeholder is not authorized for human drugs.
This stakeholder is not authorized for veterinary drugs.
The stakeholder is not authorized to supply for this drug.
User is not authorized for this service. Apply to your firm.
You are not authorized to use this service.
```

---

## 11. Prescription/Patient Fields

### Prescription Fields
```
PRESCRIPTIONID
PRESCRIPTIONID xmlns=""
PRESCRIPTIONDATE
PRESCRIPTIONDATE xmlns=""
Prescription Number must be defined.
Prescription number must not be empty for prescription drugs.
The prescription number has already been registered.
The prescription number is not registered.
The prescription number is already registered
No sale operation has been performed for the indicated prescription number.
This prescription has already been queried by the reimbursment institution. It cannot be canceled.
This prescription has already been registered
```

### Doctor Fields
```
DOCTORID
DOCTORID xmlns=""
```

### Patient Fields
```
PATIENTNATIONALID
PATIENTNATIONALID xmlns=""
```

---

## 12. Pharmacy Fields

### Pharmacy Information
```
pharmacy-name-arabic
pharmacy-name-engilsh
pharmacy-Adress
pharmacy-CRN
pharmacy-mobile
pharmacy-Mobile
pharmacy-vatnumber
pharmacyname
Pharmacy name in arabic
Pharmacy name in english
Input pharmacy name in english
Pharmacy No. 0
Normal pharmacy
Pharmacy store
Pharmacy warehouse
Pharmacy manager
Pharmacy data
```

### Receipt Fields
```
receiptType
receiptNumber
Receipt Type accept 'S' or 'R' only
Receipt Number is missing
Receipt Total is invalid
```

---

## 13. Notification System

### Notification Types
```
NOTIFICATIONID
DISPATCHNOTIFICATIONID
Notification ID
Notification ID can not be received.
No dispatch notification found for the specified notification ID.
No block operation related with this notification ID.
Invalid notification type.
Clean_Rasd_NotificationId
```

### Notification Operations
```
Use deactivation notification for expired units.
Deactivation notification
Block operation
Block operation has already been cancelled.
Block operation has already been recalled.
Block operation has been recalled
Block operation to be recalled is unsuccessful.
Block cancel operation is unsuccessful.
Cancel barcode blocking
Define barcodes block
```

---

## 14. Block/Recall/Deactivation System

### Block Operations
```
Block barcode from usage
Block app from this path
Block  loading ..
Define barcodes block
Download duplicated barcode blocking tool
Invalid block level
Cancel barcode blocking
```

### Recall Operations
```
Invalid recall level
Product has been recalled.
Product has been recalled at another stakeholder level.
Product registered on you has been recalled.
Product registered on you has been recalled at another stakeholder level.
The Product has been recalled.
The product is recalled
Indicated batch number has been recalled.
This GTIN + BN has been recalled
This GTIN/BN has been blocked. First perform recall operation in Block Screen.
Product has been recalled at another stakeholder level.
```

### Deactivation Operations
```
deactivate
Deactivate
The product has already been deactivated.
The product is in deactivated status
The product is not deactivated.
The product is not deactivated by you.
Invalid deactivation reason
Your account is deactivated. Apply to your system manager.
Use deactivation notification for expired units.
```

### Reactivation
```
reactiv (implied from context - product lifecycle management)
```

---

## 15. Product Operations Between Stakeholders

### Export (Supply)
```
Export cancellation operation cannot be performed on the product.
The product is exported by the stakeholder with code GLN1.
The product was exported by another stakeholder.
The product has already been exported.
Product has been exported.
This drug cannot be exported.
This drug can be supplied only by importing.
```

### Import (Receive)
```
Import Cancel operation can not be performed for produced product.
Import from a batch file
Supply Cancel operation can not be performed for imported product.
Importing a transferred invoice from another warehouse or pharmacy
Items imported from a friend's pharmacy
```

### Consume (Hospital)
```
Product has been consumed.
The product is consumed.
The product is consumed by another stakeholder.
The product is consumed by the hospital with code GLN1.
The product has already been consumed.
The product is not consumed.
IS_ONLY_HOSPITAL is empty or invalid
```

### Transfer Between Pharmacies
```
Transfer invoice to another pharmacy
Transfer to a transferred invoice
Transfer to purchase return
Transfer to purchases
Follow-up transfers between pharmacies
Follow up on transferred orders
Transfer money between safes
Transfer and return items
Transfer ID does not exist in the system.
Transfer ID format is not right! Transfer ID can only include numbers.
Entered transfer ID cannot be found in the system.
You can not transfer products to a stakeholder in a different city.
Destination stakeholder must be different from sender stakeholder.
Package you want to receive cannot be found in system!
You can choose "Provide not received transfer information" option for packages sent to you.
```

### Return Operations
```
Return
Returnable
returned
Sales return invoice
Sales returnes
Invalid destination information for Return Notification.
The sale of the product cannot be canceled.
Export cancellation operation cannot be performed on the product.
Operation that belongs to another stakeholder cant be cancelled.
The operation you want to cancel does not belong to you.
```

---

## 16. RASD Configuration Files

### Config Files
```
\Files\DBI\rasd-config.phye
\Files\DBI\rasd-config.txt
\Files\DBI\rasd-oot.phye
\Files\DBI\rsd-oot.phy
\Files\Rsd\
\Files\Rsd\trans\
phar-x.xml
```

### RASD Executables
```
labirdo.rasd.exe
Labirdo\rasd\
http://phycodsystems-001-site12.htempurl.com/900/Labirdo.rasd.exe
```

### RASD XML Storage
```
Labirdo\Titan3-Backup\xj\RSD-XML\
```

---

## 17. Authentication Flow

### RASD Authentication
```
Username
password
Invalid Username or Password.
Invalid password
Password is empty.
Password required
Username is empty.
Username is empty or invalid
Username cannot be null.
Stakeholder user with the specified username not found!
Change password
Change Password
forgot my password
Forgot password
wrong password ! Wrong password !
input database password
```

### RASD Integration
```
Integration tools with RSD
Upload to RSD
View operations reports on the Rasd website
Video explanation of how to activate and operate RASD
Wait for rsd integration : 
Select Rsd type
rasd_Configuration loading ..
```

### DrugEye RSD Integration
```
http://www.drugeye.pharorg.com/rsd-api/start.aspx
```

---

## 18. GS1 Barcode Fields

### GS1 Standards
```
GTIN (Global Trade Item Number) - 14 digits
BN (Batch Number)
XD (Expiry Date) - YYYYMMDD format
SN (Serial Number)
PT (Product Type) - PP for pharmaceutical
PC (Product Control)
UP (Unit Price)
QN (Quantity)
```

### GS1 Encoding
```
ModGS1Reader (24 procedures)
barcode
```

### GS1 Validation
```
The format of the product information of the product (GTIN) is incompatible.
The format of the batch number of the product is incompatible.
The format of the expiry date of the product (XD) is incompatible.
Format of the serial number is invalid.
Product barcode information is missing or invalid
```

---

## 19. Egyptian DTTS Variant

### Module
```
ModDttsEgypt (2 procedures)
```

### Egypt-Specific Endpoints
```
https://api.invoicing.eta.gov.eg        (Production)
https://api.preprod.invoicing.eta.gov.eg (Preprod)
https://invoicing.eta.gov.eg            (Portal)
https://id.eta.gov.eg                    (Auth Production)
https://id.preprod.eta.gov.eg           (Auth Preprod)
```

### Egypt-Specific Tools
```
C:\eta-qr\
C:\eToolKit\appsettings.json
C:\eToolKit\toolkit.exe
```

---

## 20. Error Messages (Complete List)

### GLN/Stakeholder Errors
```
Invalid GLN format.
Invalid destination GLN.
Invalid Buyer Stakeholder number.
Invalid Seller Stakeholder number(GLN)
Invalid Seller Stakeholder number.
Invalid stakeholder type
Sender GLN format is not appropriate! GLN must consist of 13 digits and they must be numbers!
Sender GLN information is missing or invalid.
Receiver GLN format is incorrect. GLN must consist of a 13 digit numeric value.
Source GLN information is missing
Target GLN information is missing
The entered GLN is not a pharmacy GLN.
First 13 characters of user name must be the same with GLN
Undefined Stakeholder number (GLN)
Undefined Seller Stakeholder
Stakeholder not found.
Stakeholder name is empty or invalid
Stakeholder type is empty or invalid
Stakeholder status is empty or invalid
Invalid Seller Stakeholder number(GLN)
Invalid Buyer Stakeholder number.
Indicated seller is deactivated
Sender stakeholder is passive
Receiver stakeholder is passive
The receiver is deactivated.
```

### Product Errors
```
Undefined Drug (GTIN does not exist).
The format of the product information of the product (GTIN) is incompatible.
The format of the batch number of the product is incompatible.
The format of the expiry date of the product (XD) is incompatible.
Format of the serial number is invalid.
Serial number is empty or invalid.
Product barcode information is missing or invalid
Product control status is empty or invalid
Product has expired.
The product has already been deactivated.
The product is in deactivated status
The product is not deactivated.
The product is not deactivated by you.
The product is blocked.
The product is recalled
The Product has been recalled.
The product has already been sold by pharmacy.
The product is already registered in another pharmacy.
The product is already registered in another hospital.
The product is already registered in another hospital's stock.
The product is in another hospital's stock.
The product was sold to the reimbursment institution. The sale should be canceled based on prescription.
The product was exported by another stakeholder.
The product has already been exported.
Product has been exported.
The product has been consumed.
The product is consumed.
The product is consumed by another stakeholder.
The product is consumed by the hospital with code GLN1.
The product has already been consumed.
The product is not consumed.
This GTIN + BN has been recalled
This GTIN/BN has been blocked. First perform recall operation in Block Screen.
Indicated batch number has been recalled.
This batch number was used before with a different expire date or production date.
The product has already been deactivated.
Product has been recalled.
Product has been recalled at another stakeholder level.
Product registered on you has been recalled.
Product registered on you has been recalled at another stakeholder level.
The product is exported by the stakeholder with code GLN1.
The product is sold by the pharmacy with code GLN1.
The product is registered for stakeholder with GLN1 number.
The product is between GLN1 and GLN2.
The product is between GLN2 and you. You can accept products.
The product is consumed by the hospital with code GLN1.
The product is exported by the stakeholder with code GLN1.
```

### Operation Errors
```
Invalid notification type.
Notification ID can not be received.
No dispatch notification found for the specified notification ID.
No block operation related with this notification ID.
Invalid block level
Invalid recall level
Block operation has already been cancelled.
Block operation has already been recalled.
Block operation has been recalled
Block operation to be recalled is unsuccessful.
Block cancel operation is unsuccessful.
Operation that belongs to another stakeholder cant be cancelled.
The operation you want to cancel does not belong to you.
The sale of the product cannot be canceled.
Export cancellation operation cannot be performed on the product.
Import Cancel operation can not be performed for produced product.
Supply Cancel operation can not be performed for imported product.
Invalid destination information for Return Notification.
Invalid deactivation reason
Invalid isExportable value.
Invalid isExported value.
Invalid Prescription Date.
Invalid status.
Invalid authentication code
```

### Transfer Errors
```
Transfer ID does not exist in the system.
Transfer ID format is not right! Transfer ID can only include numbers.
Entered transfer ID cannot be found in the system.
You can not transfer products to a stakeholder in a different city.
Destination stakeholder must be different from sender stakeholder.
Package you want to receive cannot be found in system!
Sync list cannot be receieved.
```

### Prescription Errors
```
Prescription Number must be defined.
Prescription number must not be empty for prescription drugs.
The prescription number has already been registered.
The prescription number is not registered.
The prescription number is already registered
No sale operation has been performed for the indicated prescription number.
This prescription has already been queried by the reimbursment institution. It cannot be canceled.
This prescription has already been registered
```

### General Errors
```
User is not authorized for this service. Apply to your firm.
You are not authorized to use this service.
Your account is deactivated. Apply to your system manager.
Invalid password
Invalid Username or Password.
Password is empty.
Password required
Username is empty.
Username is empty or invalid
Username cannot be null.
Stakeholder user with the specified username not found!
Sent XML data structure is not compatible with the scheme in WSDL document
Maximum inquiry period in package detail service should be 1 month (31 days). Please correct start date and end date!
Start date cannot be later than end date in package details service.
```

---

## 21. DTTS Data Flow

### Sale Flow
```
Pharmacy Sale -> PharmacySaleService Request -> RSD Response -> Notification ID
```

### Cancel Sale Flow
```
Cancel Sale -> PharmacySaleCancelService Request -> RSD Response
```

### Dispatch Flow (Warehouse to Pharmacy)
```
Warehouse Dispatches -> DispatchService Request -> RSD Response -> Notification ID
Pharmacy Accepts -> AcceptDispatchService Request -> RSD Response
```

### Transfer Flow (Pharmacy to Pharmacy)
```
Source Pharmacy -> TransferService Request -> RSD Response -> Notification ID
Destination Pharmacy Accepts -> AcceptDispatchService Request -> RSD Response
```

### Return Flow (Pharmacy to Warehouse)
```
Pharmacy Returns -> ReturnService Request -> RSD Response -> Notification ID
```

---

## 22. Formdtts (26 procedures) - UI Functions

The Formdtts form provides the user interface for:
- Viewing DTTS transactions
- Managing product status (block/recall/deactivate)
- Accepting dispatches
- Handling returns
- Managing prescriptions
- RSD configuration

---

## 23. ModDTTS (48 procedures) - Core Functions

Key procedures include:
- Building SOAP request XML for each service
- Parsing SOAP response XML
- Managing GLN/stakeholder data
- Product status tracking
- Notification management
- Block/recall operations
- Prescription validation
- Receipt management
- Error handling and logging

---

## 24. Country-Specific Handling

### Saudi Arabia (Primary)
```
SFDA/RSD endpoints (rsd.sfda.gov.sa)
All 6 SOAP services active
Full DTTS compliance
```

### Egypt
```
ModDttsEgypt (2 procedures)
ETA endpoints (api.invoicing.eta.gov.eg)
Different drug tracking approach
```

### Other Countries
```
ModCountries (24 procedures)
Country-specific integration handling
```
