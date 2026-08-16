# Titan Cloud/Network Integration - Complete Specification

## Source Modules
- **ModNetwork** (65 procedures) - Core network/FTP operations
- **ModFTP** (29 procedures) - FTP-specific operations
- **ModTitanCloud** (16 procedures) - Cloud storage services
- **ModTitan** (37 procedures) - Titan core operations
- **ModMobile** (9 procedures) - Mobile integration
- **ModRemoteControl** (10 procedures) - Remote control
- **ModOuterConnections** (18 procedures) - External connections
- **ModServerConnections** (1 procedure) - Server connections
- **Modeveryday** (9 procedures) - Daily operations
- **ModSaturn** (29 procedures) - Saturn/ZATCA operations

---

## 1. Cloud Storage Endpoints

### PhycodSystems Azure/App Service
```
Base: http://phycodsystems-001-site12.htempurl.com/

Titan3 Distribution:
  /Titan3/Us/dailynotes.html
  /Titan3/Us/drugeye.html
  /Titan3/Us/paper.html
  /Titan3/Us/programs.html
  /Titan3/Us/titan.html
  /Titan3/Us/upgrade.html
  /Titan3/Us/TitanNews.txt
  /Titan3/Us/easeus.exe
  /Titan3/Us/showme.exe

Titan3 World (Application):
  /Titan3/Us/world/Phye.exe
  /Titan3/Us/world/server.connector.exe
  /Titan3/Us/world/emerg.w.exe
  /Titan3/Us/world/black.list.phar.rar
  /Titan3/Us/world/themes/mainimage/1.jpg
  /Titan3/Us/world/themes/mainimage/2.jpg
  /Titan3/Us/world/themes/mainimage/3.jpg
  /Titan3/Us/world/themes/mainimage/4.jpg
  /Titan3/Us/world/themes/mainimage/5.jpg

Tools:
  /titan3/us/tools/quricol32.dll
  /Titan3/Us/tools/drugeye.update.titan.rar

User Data:
  /titan-users/allinone/data/
  /titan-users/allinone/mobiles/
  /titan-users/drugs-unify/
  /titan-users/send-to/
  /titan-users/t-link/

Saturn/ZATCA Files:
  /900/curl/curl.exe
  /900/curl/curl-ca-bundle.crt
  /900/curl/libcurl-x64.dll
  /900/etatoolkit/appsettings.json
  /900/etatoolkit/toolkit.exe
  /900/etatoolkit/aspnetcorev2_inprocess.dll
  /900/etatoolkit/e_sqlite3.dll
  /900/flex.exe
  /900/Labirdo.rasd.exe
  /900/titan.cloud/anydesk.exe
  /900/titan.cloud/xi.dll
  /900/tracer/tracer.exe

Other:
  /Titan3/Us/world/Phye.exe (main application)
  https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar
```

### PhycodSystems Site 16 (Saturn Distribution)
```
Base: http://phycodsystems-001-site16.htempurl.com/saturnfiles/

  saturn.exe
  BouncyCastle.Crypto.dll
  MessagingToolkit.QRCode.dll
  SDKNETFrameWorkLib.dll
  SDKNETFrameWorkLib.dll.config
  System.Net.Http.dll
  summer.b2b.rar
  xmlauth3.txt
  zatca.onboarding.form.xlsx
```

### PhycodSystems Site 17 (Saturn2 / Developer)
```
Base: http://phycodsystems-001-site17.atempurl.com/

Saturn2 Files:
  /saturnfiles/saturn2.exe
  /saturnfiles/BouncyCastle.Crypto.dll
  /saturnfiles/MessagingToolkit.QRCode.dll
  /saturnfiles/SDKNETFrameWorkLib.dll
  /saturnfiles/SDKNETFrameWorkLib.dll.config
  /saturnfiles/System.Net.Http.dll

Developer Resources:
  /saturn/developers/titan/code/
  /saturn/developers/titan/code/api-sign.rar
  /saturn/developers/titan/code/summer.test.txt

Onboarding:
  /saturn/saturnonboard.exe
```

---

## 2. FTP Operations

### FTP APIs (WinInet)
```
FtpGetFileA          - Download file from FTP
FtpPutFileA          - Upload file to FTP
FtpDeleteFileA       - Delete file on FTP
FtpOpenFileA         - Open file on FTP
FtpGetCurrentDirectoryA - Get current FTP directory
FtpSetCurrentDirectoryA - Set FTP directory
FtpFindFirstFileA    - Find first file on FTP
FtpGetFileSize       - Get file size on FTP
InternetFindNextFileA - Find next file
InternetConnectA     - Establish FTP connection
InternetOpenA        - Open Internet session
InternetCloseHandle  - Close Internet handle
InternetReadFile     - Read from Internet
InternetWriteFile    - Write to Internet
```

### FTP Upload Pattern (PowerShell)
```
$wc = New-Object System.Net.WebClient
$wc.UploadFile($remoteFile, "STOR", $localFile)

$server = "..."
$cred = New-Object System.Net.NetworkCredential($username, $password)
$remoteFile = $server + [System.IO.Path]::GetFileName($localFile)
```

### FTP Upload Pattern (Batch)
```
echo open ftp.server.com> ftpcmd.dat
echo username>> ftpcmd.dat
echo password>> ftpcmd.dat
echo binary>> ftpcmd.dat
echo put %1>> ftpcmd.dat
echo quit>> ftpcmd.dat
ftp -n -s:ftpcmd.dat
```

### FTP with curl
```
C:\curl\curl.exe
C:\curl\libcurl-x64.dll
C:\curl\curl-ca-bundle.crt
C:\curl\curl_upload.log

curl command pattern:
--ftp-pasv --retry 3 --retry-delay 2
```

### FTP Config Files
```
\Files\DBI\myftp.phy
\ftp_upload_temp.ps1
```

### FTP Operations
```
ftp://
FTP://
input your ftp hostname
input your ftp pass
input your ftp username
input remote path like /myfolder/
```

---

## 3. HTTP/HTTPS APIs

### HTTP Methods
```
POST
GET
```

### HTTP Libraries
```
MSXML2.XMLHTTP
Msxml2.ServerXMLHTTP.6.0
MSXML2.DOMDocument
MSXML.DomDocument
WinInet (InternetOpenA, InternetConnectA, etc.)
```

### Content Types
```
application/json
application/x-www-form-urlencoded
text/xml; charset=utf-8
```

### HTTP Functions
```
InternetCheckConnectionA  - Check internet connectivity
InternetGetConnectedStateEx - Get connection state
InternetReadFile          - Read response
InternetWriteFile         - Send request body
InternetOpenUrlA          - Open URL
InternetGetLastResponseInfoA - Get error info
```

---

## 4. Hunger Station Integration

### OAuth Endpoint
```
https://hungerstation.partner.deliveryhero.io/v2/oauth/token
```

### OAuth Parameters
```
grant_type=client_credentials
client_id
client_secret
```

### Hunger Station API
```
https://hungerstation.partner.deliveryhero.io/v2/chains/
```

### Token Storage
```
\Files\DBI\hungerstation.token.txt
```

---

## 5. ETA (Egyptian Tax Authority) Integration

### Endpoints
```
Production:
  https://api.invoicing.eta.gov.eg
  https://id.eta.gov.eg

Preprod:
  https://api.preprod.invoicing.eta.gov.eg
  https://id.preprod.eta.gov.eg

Portal:
  https://invoicing.eta.gov.eg
```

### ETA API
```
/connect/token
```

### ETA Authentication
```
client_id
client_secret
grant_type=client_credentials
```

### ETA Toolkit
```
C:\eToolKit\toolkit.exe
C:\eToolKit\appsettings.json
C:\eToolKit\summer_without_uuid.json
C:\eToolKit\summer_with_uuid.json

Download URL: http://phycodsystems-001-site12.htempurl.com/900/etatoolkit/
Files:
  toolkit.exe
  appsettings.json
  aspnetcorev2_inprocess.dll
  e_sqlite3.dll
```

### ETA QR
```
C:\eta-qr\
```

### ETA Signing
```
/api-sign.aspx
C:\api-sign.aspx
```

### ETA Receipt API
```
/api/v1/receipts/recent
/api/v1/receipts/recent?ReceiptNumber=
/api/v1/receiptsubmissions
/receipts/search/
```

### ETA Invoice Structure
```json
{
    "documentType": {},
    "receiptType": "",
    "receiptNumber": "",
    "branchCode": "",
    "branchAddress": {},
    "receipts": [],
    "extraReceiptDiscountData": []
}
```

---

## 6. Titan Cloud Sync

### Cloud Operations
```
Cloud copy
Cloud storage of stock
Upload allinone
Upload Mobile
Upload the drug database to the cloud storage
Upload to mobile
Upload to RSD
Upload zipped DBI
Upload Merge File
```

### Cloud User Data Paths
```
/titan-users/allinone/data/
/titan-users/allinone/mobiles/
/titan-users/by-dos/
/titan-users/data-for-sale/avros/egypt/
/titan-users/data-for-sale/avros/saudi/
/titan-users/data-for-sale/avros/world/
/titan-users/data-for-sale/nielsen-curl
/titan-users/data-for-sale/nielsen/egypt
/titan-users/data-for-sale/nielsen/members-only/data/
/titan-users/data-for-sale/nielsen/saudi
/titan-users/dbi-zipped/Bux-w-backup/
/titan-users/dbi-zipped/Bux-w-egypt/
/titan-users/dbi-zipped/Bux-w-saudia/
/titan-users/dbi-zipped/Bux-w-world/
/titan-users/drugs-unify/
/titan-users/fary-net/
/titan-users/floor2/
titan-users/new
titan-users/send-to/
/titan-users/titan-mobile/files/
```

---

## 7. File Download/Update System

### Application Downloads
```
Download new software
Titan 336 publish 1-4-2018
Titan 337 publish 1-5-2018
Titan 338 publish 1-9-2018
TITAN.UPDATOR
titan.updator.exe
```

### Component Downloads
```
C:\saturn\saturn.exe (from site16)
C:\saturn\saturn2.exe (from site17)
C:\Files\Zatca\saturnonboard.exe
C:\curl\curl.exe (from site12)
C:\eToolKit\toolkit.exe (from site12)
labirdo.rasd.exe (from site12)
server.connector.exe (from site12)
```

### Update Patterns
```
write 500 to download new themes
Drugeye update: /Titan3/Us/tools/drugeye.update.titan.rar
```

---

## 8. Network Connectivity

### Connectivity Check
```
InternetCheckConnectionA
InternetGetConnectedStateEx
No internet connection
press ok to start check network connectivity
```

### Connection Types
```
Network-activation
Mobile number for cloud connectivity
Mobile number for current cloud connectivity
```

### Network Sharing
```
net share Titan.master=
net share Titan.master /delete
```

### Server Connector
```
server.connector.exe
labirdo-server-connector
\Files\DB\server.connector.exe
\Files\DB\server.connection.report.txt
world/serverconnect/
```

---

## 9. Remote Control

### Remote Control Module
```
ModRemoteControl (10 procedures)
```

### Remote Control Database
```
remotecontrol table:
  datee
  mobile
  copyid
  passedfunctions

Commands:
  insert into remotecontrol (datee,mobile,copyid,passedfunctions)
  delete from remotecontrol where id = N''
  delete from remotecontrol where passedfunctions = N''
  select * from remotecontrol where mobile = N''
  select id,datee,passedfunctions from remotecontrol where mobile = N''
  select passedfunctions from remotecontrol where datee > N''
```

### Remote Operations
```
Remote Control
FormRemoteControl
Remote-control
Log in as Technical Support
```

---

## 10. Backup System

### Backup Locations
```
\Labirdo\Titan3-Backup\
\Labirdo\Titan3-Backup\Daily\
\Labirdo\Titan3-Backup\Export\
\Labirdo\Titan3-Backup\Export\Del\
\Labirdo\Titan3-Backup\History.txt
\Labirdo\Titan3-Backup\images\
\Labirdo\Titan3-Backup\Monthly
\Labirdo\Titan3-Backup\qr\
\Labirdo\Titan3-Backup\Rur\
\Labirdo\Titan3-Backup\tars-copy\
\Labirdo\Titan3-Backup\titan-info.txt
\Labirdo\Titan3-Backup\xj\
\Labirdo\Titan3-Backup\xj\Customers\
\Labirdo\Titan3-Backup\xj\internet-backup.txt
\Labirdo\Titan3-Backup\xj\Phye.safer\
\Labirdo\Titan3-Backup\xj\Phye.zip
\Labirdo\Titan3-Backup\xj\RSD-XML\
\Labirdo\Titan3-Backup\xj\stock\
\Labirdo\Titan3-Backup\xj\xj-data\
\Labirdo\Titan3-Backup\xj\xj-data\bin\
\Labirdo\Titan3-Backup\xj\xj-data\zip\
```

### Backup Operations
```
Save a backup
Create Internet backup
Restore backup
Backup folder
sever backup contibued
sever backup stopped
Back up is ignored by 'no-backup' folder
no-backup
```

### Cloud Backup
```
GoogleDrive\Titan
```

---

## 11. Export/Import System

### Export Paths
```
\Files\Export\
\Files\Export\DrugEye
\Files\Export\Titan
\Files\Accounting\
\Files\Accounting\monthly\
\Files\Accounting\monthly\ascode\
\Files\Accounting\Vat-reports\
\Files\DBI\
\Files\Ned\
```

### Export Operations
```
Export-Data
Export-Data-all
Export-Data-Worked
Export stocks and data
Export database to Excel
Export to file
Export to one file
Export to purchase file
Export to sales file
Export to a batch file
Export to a merge file
Export to current country is forbidden
Export to drugeye
Export invoice to another pharmacy
Export invoices that contain a problem in calculating debts
Export in debt values ??in sales invoices
Export the price change to a file
Export the prices to a file
Export international barcode change to a file
Export the current pharmacology to all instances
export drug name as drugs.csv to report it in another instance of the same pharmacy
Export-Many_Sales
Export_Drug_Upgrading_Data_Base
```

### Import Operations
```
Import
IMPORT
Import-Export
Import from file
Import from a batch file
Import from another software
Import customers from excel file
Import database from Excel
Import item updates from a friend
Import the new items from the Merge file
Import the prices from excel file
Import the prices from old data
Import price adjustments from the group
Imports discount
Import_Volume_Points
Import-Many_Sales
```

### Export File Formats
```
exported.data.all.csv
exported.data.stock.csv
exported.worked.data.csv
Cusom-export.csv
Custom-Export
drugs-stock2.csv
```

---

## 12. Database Operations

### Database Files
```
\Files\DB\drugeye-for-titan.phy
\Files\DB\drugeye-for-titan.rar
\Files\db\drugeye.update.titan.rar
\Files\DB\server.connection.report.txt
\Files\DB\server.connector.exe
\Files\DB\TitanNews.phy
\Files\DB\summer.txt
\Files\DB\ChilkatAx-win32.dll
\Files\DB\egypt.cosmo.phy
```

### SQL Server Connection
```
Driver={SQL Server};SERVER=
```

### Database Tables
```
titanstock
titanksastock
titanksasales
titaninn
titanneed
titanpharmalist
titanuseraction
usersourceupdate
storediscount
remotecontrol
orders
```

---

## 13. File Types

### Titan File Types
```
.phy     - Titan data files
.phye    - Titan data files (extended)
.sdd     - Titan data files
.txt     - Text files
.xml     - XML files
.csv     - CSV files
.zip     - ZIP archives
.rar     - RAR archives
.exe     - Executables
.dll     - Dynamic link libraries
.bat     - Batch scripts
.ps1     - PowerShell scripts
.html    - HTML files
.json    - JSON files
.jpg     - Image files
```

---

## 14. ModNetwork Procedures (65 total)

### Key Procedures
- FTP upload/download operations
- HTTP request handling
- Cloud sync operations
- Database replication
- File transfer management
- Connection monitoring
- Error handling

### Data Flow
```
Local Titan Data -> Export to CSV/XML
    ↓
FTP/HTTP Upload -> Cloud Storage
    ↓
Other Titan Instance Downloads
    ↓
Import into Local Database
```

---

## 15. ModFTP Procedures (29 total)

### Key Procedures
- FTP connection management
- File upload/download
- Directory operations
- File listing
- Error handling
- Retry logic

---

## 16. ModTitanCloud Procedures (16 total)

### Key Procedures
- Cloud storage API integration
- File sync operations
- User data management
- Backup/restore from cloud
- Update distribution

---

## 17. Additional Network Features

### QR Code via HTTP
```
http://api.qrserver.com/v1/create-qr-code/?
http://chart.googleapis.com/chart?
```

### Drug Eye Integration
```
http://www.drugeye.pharorg.com
http://www.drugeye.pharorg.com/rsd-api/start.aspx
\Files\DB\drugeye-for-titan.phy
\Files\Export\DrugEye
\Files\db\drugeye.update.titan.rar
/Titan3/Us/tools/drugeye.update.titan.rar
```

### External APIs
```
http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso
http://www.oorsprong.org/websamples.countryinfo
http://footballpool.dataaccess.eu/info.wso
```

### Nielsen Data
```
titan-users/data-for-sale/nielsen-curl
titan-users/data-for-sale/nielsen/egypt
titan-users/data-for-sale/nielsen/saudi
titan-users/data-for-sale/nielsen/members-only/data/
https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar
```

---

## 18. Network Security

### SSL/TLS
```
C:\curl\curl-ca-bundle.crt
```

### Authentication
```
Bearer token
OAuth2 client_credentials
Username/Password
```

---

## 19. ModSaturn (29 procedures) - ZATCA Network Operations

### Key Procedures
- Saturn service communication
- ZATCA API calls
- XML/JSON signing via network
- Response handling
- File management
- Error handling

---

## 20. ModOuterConnections (18 procedures)

### External System Integrations
- Third-party pharmacy systems
- Insurance companies
- Hospital systems
- Supply chain partners
