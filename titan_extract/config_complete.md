# TITAN.W1 - Complete Configuration Settings

## 1. DATABASE CONNECTION SETTINGS

### Database Connection String
```
Driver={SQL Server};SERVER=
```

### Database Files
- `Files\DBI\` - Main database information folder
- `Files\DB\` - Database files folder
- `Files\DBI\*.bak` - Database backup files
- `Files\DB\Restore.bak` - Restore backup file
- `Files\DB\DDI.Phy` - DDI database
- `Files\DB\Install.rf` - Installation file

### Database Tables
- `usersourceupdate` - User source update table
- `ChainBuyUsers` - Chain buy users table
- `TitanUserAction` - User action tracking table
- `RawakidTablew` - Rawakid table
- `storediscount` - Store discount table
- `orders` - Orders table
- `wzgard` - wzgard table

## 2. PRINTER SETTINGS

### Printer Configuration
- `Printer settings in titan` - Titan printer settings
- `Printer settings in windows` - Windows printer settings
- `A4 Paper Printer` - A4 printer type
- `Barcode label Printer` - Barcode printer type
- `Cash Printer` - Cash printer type
- `Barcode label settings` - Barcode label settings
- `Drawer settings` - Cash drawer settings

### Printer Operations
- `(No Printer Installed)` - No printer detected
- `Printer Error` - Printer error
- `No Printers` - No printers available
- `Drawer connected to the printer` - Cash drawer connection
- `Open the drawer connected to the printer` - Open cash drawer
- `Print barcode for this drug` - Print drug barcode
- `Print a barcode for this item individually` - Print individual barcode
- `Print the attendance and departure barcode` - Print attendance barcode
- `Print returns report` - Print returns report
- `Do not print prices on the barcode label` - Barcode price printing option

## 3. COMPANY/PHARMACY INFO SETTINGS

### Pharmacy Information
- `<pharmacy-name-arabic>` - Arabic pharmacy name
- `<pharmacy-name-engilsh>` - English pharmacy name
- `<pharmacy-Adress>` - Pharmacy address
- `<pharmacy-CRN>` - Pharmacy commercial register number
- `<pharmacy-Mobile>` - Pharmacy mobile number
- `<pharmacy-mobile>` - Pharmacy mobile number
- `<pharmacy-vatnumber>` - Pharmacy VAT number

### Company Information
- `<company-name>` - Company name
- `<\\company-name>` - Company name end tag
- `CompanyName` - Company name field
- `CompanyName is empty or invalid` - Validation message
- `CompanyType is invalid` - Validation message
- `Company / Individual` - Company type
- `Company dues` - Company dues
- `Company not found` - Company search result

### Pharmacy Types
- `Normal pharmacy` - Standard pharmacy
- `Pharmacy store` - Pharmacy store
- `Pharmacy warehouse ` - Pharmacy warehouse
- `Pharmacy No. 0` - Pharmacy number
- `Pharmacy manager` - Pharmacy manager role

## 4. TAX/VAT SETTINGS

### VAT Configuration
- `<pharmacy-vatnumber>` - Pharmacy VAT number
- `<seller-vat-number>` - Seller VAT number
- `<buyer-vat-number>` - Buyer VAT number
- `<tax-percent>` - Tax percentage
- `<taxableItems>` - Taxable items
- `<taxTotals>` - Tax totals

### VAT Operations
- `Add or Remove Vat` - Add/remove VAT
- `Change Vat status` - Change VAT status
- `Change tax value` - Change tax value
- `Change value of VAT for tax items` - Change VAT value
- `Changing tax value with final price` - Price includes VAT
- `Edit the VAT value for this item` - Edit item VAT
- `Apply a sale discount for tax items` - Apply tax discount
- `Cancellation of the vat with an increase in the price of items` - VAT cancellation
- `Ensure that the vat value on the sale price is included in all invoices` - VAT enforcement
- `Copy the VAT as it is to the item cards for the current invoice` - Copy VAT
- `Re-apply vat on invoices` - Re-apply VAT
- `Manually resetting the Vat value in old invoices` - Reset VAT

### VAT Reports
- `Quarterly VAT report` - Quarterly VAT report
- `Net with VAT` - Net with VAT
- `Total VAT` - Total VAT
- `Expenses vat  ` - Expenses VAT
- `<masrofat-vat>` - Expenses VAT tag
- `<purchases-vat>` - Purchases VAT tag
- `<sales-vat>` - Sales VAT tag

## 5. BACKUP PATHS AND SCHEDULES

### Backup Paths
- `Labirdo\Titan3-Backup` - Main backup folder
- `Labirdo\Titan3-Backup\` - Backup folder
- `Labirdo\Titan3-Backup\Daily` - Daily backups
- `Labirdo\Titan3-Backup\Daily\` - Daily backup folder
- `Labirdo\Titan3-Backup\Export\` - Export backups
- `Labirdo\Titan3-Backup\Export\Del\` - Delete exports
- `Labirdo\Titan3-Backup\History.txt` - Backup history
- `Labirdo\Titan3-Backup\Monthly` - Monthly backups
- `Labirdo\Titan3-Backup\Monthly\` - Monthly backup folder
- `Labirdo\Titan3-Backup\Rur\` - Rur backups
- `Labirdo\Titan3-Backup\daily\` - Daily backup folder
- `Labirdo\Titan3-Backup\images\` - Image backups
- `Labirdo\Titan3-Backup\tars-copy\` - Tars copy backups
- `Labirdo\Titan3-Backup\titan-info.txt` - Titan info
- `Labirdo\Titan3-Backup\xj\` - XJ backups
- `Labirdo\Titan3-Backup\xj\Customers\` - Customer backups
- `Labirdo\Titan3-Backup\xj\Phye.safer\` - Phye safer backups
- `Labirdo\Titan3-Backup\xj\Phye.zip` - Phye zip backup
- `Labirdo\Titan3-Backup\xj\RSD-XML\` - RSD XML backups
- `Labirdo\Titan3-Backup\xj\internet-backup.txt` - Internet backup
- `Labirdo\Titan3-Backup\xj\stock\` - Stock backups
- `Labirdo\Titan3-Backup\xj\xj-data\` - XJ data backups
- `Labirdo\Titan3-Backup\xj\xj-data\bin\` - XJ data bin
- `Labirdo\Titan3-Backup\xj\xj-data\zip\` - XJ data zip

### Backup Operations
- `Save a backup` - Save backup
- `Restore backup` - Restore backup
- `Backup folder` - Backup folder setting
- `Create Internet backup` - Create internet backup
- `Clean backups` - Clean old backups
- `Back up is ignored by 'no-backup' folder` - Backup exclusion
- `Titan3-Backup\\Daily\\` - Daily backup path
- `sever backup contibued` - Server backup continued
- `sever backup stopped` - Server backup stopped
- `failed to backup copy` - Backup failure

## 6. CLOUD SYNC SETTINGS

### Cloud Storage
- `Cloud copy` - Cloud copy option
- `Cloud storage of stock` - Cloud stock storage
- `Mobile number for cloud connectivity` - Cloud mobile number
- `Mobile number for current cloud connectivity` - Current cloud mobile

### Cloud URLs
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/data/` - All-in-one data
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/mobiles/` - All-in-one mobiles
- `http://phycodsystems-001-site12.htempurl.com/titan-users/drugs-unify/` - Drugs unify
- `http://phycodsystems-001-site12.htempurl.com/titan-users/send-to/` - Send to
- `http://phycodsystems-001-site12.htempurl.com/titan-users/t-link/` - T-link

### Cloud Paths
- `/titan-users/allinone/data/` - All-in-one data path
- `/titan-users/allinone/mobiles/` - All-in-one mobiles path
- `/titan-users/by-dos/` - By DOS path
- `/titan-users/data-for-sale/avros/egypt/` - Avros Egypt
- `/titan-users/data-for-sale/avros/saudi/` - Avros Saudi
- `/titan-users/data-for-sale/avros/world/` - Avros World
- `/titan-users/floor2/` - Floor 2 path
- `/titan-users/titan-mobile/files/` - Titan mobile files
- `titan-users/dbi-zipped/Bux-w-backup/` - Bux backup
- `titan-users/dbi-zipped/Bux-w-egypt/` - Bux Egypt
- `titan-users/dbi-zipped/Bux-w-saudia/` - Bux Saudi
- `titan-users/dbi-zipped/Bux-w-world/` - Bux World
- `titan-users/drugs-unify/` - Drugs unify path
- `titan-users/fary-net/` - Fary net path
- `titan-users/send-to/` - Send to path
- `titan-users/data-for-sale/nielsen-curl` - Nielsen curl
- `titan-users/data-for-sale/nielsen/egypt` - Nielsen Egypt
- `titan-users/data-for-sale/nielsen/members-only/data/` - Nielsen members
- `titan-users/data-for-sale/nielsen/saudi` - Nielsen Saudi

## 7. EMAIL SETTINGS

### Email Configuration
- `Email cannot be null.` - Email validation
- `Email is empty or invalid` - Email validation
- `&username=` - Username parameter
- `&client_secret=` - Client secret parameter

### Email URLs
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/data/` - Data endpoint
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/mobiles/` - Mobiles endpoint

## 8. SMS SETTINGS

### SMS Configuration
- `Mobile number for cloud connectivity` - Mobile number
- `Mobile number for current cloud connectivity` - Current mobile
- `PharmacistTel` - Pharmacist telephone
- `PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,SourceIdDateTime,price` - Pharmacist telephone fields

## 9. BARCODE SCANNER SETTINGS

### Barcode Configuration
- `Barcode` - Barcode field
- `Barcode label settings` - Barcode label settings
- `Barcode options` - Barcode options
- `Barcode printing` - Barcode printing
- `Barcode1` - Barcode 1
- `Barcode2` - Barcode 2
- `Barcodes.txt` - Barcodes text file
- `Add barcode` - Add barcode
- `Add or Remove Vat` - Add/remove VAT
- `Apply barcode printing to all items` - Apply to all items
- `Apply barcode printing to medicines without international barcode` - Apply to non-international
- `Block barcode from usage` - Block barcode
- `Cancel barcode blocking` - Unblock barcode
- `Change international barcode` - Change international barcode
- `Clean duplicate barcode` - Clean duplicate barcodes
- `Define barcodes block` - Define barcode block
- `Download duplicated barcode blocking tool` - Download blocking tool
- `International barcode` - International barcode
- `Print barcode for this drug` - Print drug barcode
- `Print a barcode for this item individually` - Print individual barcode
- `Remove duplicate barcodes for items` - Remove duplicates
- `Do not print prices on the barcode label` - Price printing option

### Barcode Types
- `Barcode1` through `Barcode5` - Multiple barcode fields
- `OR Barcode1=N'` through `OR Barcode5=N'` - Barcode search
- `International barcode` - International barcode
- `Short code` - Short code

## 10. CURRENCY SETTINGS

### Currency Configuration
- `"currency": "` - Currency field in JSON
- `"exchangeRate": ` - Exchange rate field
- `Discount by currency` - Currency-based discount

### Currency Fields
- `currency` - Currency field
- `exchangeRate` - Exchange rate
- `valueDifference` - Value difference

## 11. DATE FORMAT SETTINGS

### Date Configuration
- `datee int   default '0' ,` - Date field definition
- `datee` - Date field
- `datetimee` - DateTime field
- `dateemanual` - Manual date field
- `monthe` - Month field
- `yearo` - Year field

### Date Operations
- `Date:` - Date display
- `Expire date : ` - Expiry date display
- `datee > ` - Date comparison
- `ORDER BY Datee desc;` - Date ordering

## 12. LANGUAGE SETTINGS (ARABIC/ENGLISH)

### Language Configuration
- `language Settings` - Language settings
- `Language switching` - Language switching
- `Arabic Transparent` - Arabic font
- `Arabic name` - Arabic name field
- `Name Arabic` - Arabic name
- `Name english` - English name
- `NameArabic` - Arabic name field
- `NameEnglish` - English name field

### Language Operations
- `Click  'adminstartive'   then  'change system locale'  then  'Arabic Egypt' ` - Locale change
- `If you see the letters as unreadable language` - Language issue
- `powershell.exe -ExecutionPolicy Bypass -File "` - Language script
- `rundll32.exe shell32.dll,Control_RunDLL intl.cpl` - Regional settings

## 13. THEME/COLOR SETTINGS

### Color Configuration
- `BColor` - Background color
- `BackColor` - Back color
- `CellBackColor` - Cell back color
- `CellForeColor` - Cell front color
- `Color blindness` - Color blindness mode
- `Colors` - Colors settings
- `ForeColor` - Front color

### Font Configuration
- `Font` - Font field
- `FontName` - Font name
- `FontSize` - Font size
- `Fonts` - Fonts settings
- `ButtonFontSize` - Button font size

## 14. NETWORK SETTINGS

### Network Configuration
- `Network` - Network settings
- `Network-activation` - Network activation
- `ConnectionTimeout` - Connection timeout
- `FTP://` - FTP protocol
- `ftp-pasv --retry 3 --retry-delay 2` - FTP passive mode

### FTP Settings
- `input your ftp username` - FTP username
- `FTP://` - FTP server
- `ftpcmd.dat` - FTP command file
- `curl-ignore.txt` - Curl ignore file

### API Settings
- `<url>` - URL field
- `<server>` - Server field
- `<host>` - Host field
- `<secret>` - Secret field
- `<client-secret>` - Client secret field
- `<authid>` - Auth ID field
- `<userid>` - User ID field
- `<username>` - Username field
- `<password>` - Password field

### API URLs
- `/api-sign.aspx` - API sign endpoint
- `/api/v1/receipts/recent` - Receipts recent
- `/api/v1/receipts/recent?ReceiptNumber=` - Receipt by number
- `/api/v1/receiptsubmissions` - Receipt submissions
- `/connect/token` - Token endpoint

## 15. LICENSE/ACTIVATION SETTINGS

### License Configuration
- `License` - License field
- `License number is empty` - Validation
- `License number used by someone else` - Validation
- `Activate your app` - Activation option
- `Register your app with technical support` - Registration
- `Register your program with technical support` - Registration
- `Register for the first time` - First-time registration
- `Successfull activation` - Activation success
- `Temporary activation for 3 days` - Temporary activation
- `TRial No:  ` - Trial number
- `Trial No : ` - Trial number display
- `you choosed to remove your activation` - Remove activation

### Activation Files
- `Files\DBI\mandoup.phy` - Mandoup activation file
- `C:\eToolKit\appsettings.json` - EToolKit settings
- `C:\etoolkit\appsettings.json` - EToolKit settings
- `C:\saturn\SDKNETFrameWorkLib.dll.config` - Saturn settings
- `C:\saturn\help\xmlauth3.txt` - Saturn auth file
- `Files\DBI\xmlauth3.txt` - XML auth file
- `Files\Zatca\xmlauth3.txt` - Zatca auth file

## 16. FILE PATHS

### Database Files
- `Files\DBI\` - Main database information folder
- `Files\DB\` - Database files folder
- `Files\DBI\*.bak` - Database backup files
- `Files\DB\Restore.bak` - Restore backup file
- `Files\DB\DDI.Phy` - DDI database
- `Files\DB\Install.rf` - Installation file
- `Files\DBI\DBS320.mdb` - Access database

### Configuration Files
- `Files\DBI\colors.phy` - Colors configuration
- `Files\DBI\print.phy` - Print configuration
- `Files\DBI\us.phy` - User settings
- `Files\DBI\myftp.phy` - FTP configuration
- `Files\DBI\integrations.phy` - Integrations
- `Files\DBI\rasd-config.phye` - RASD configuration
- `Files\DBI\rasd-config.txt` - RASD configuration text
- `Files\DBI\isbranch.txt` - Branch flag
- `Files\DBI\ismaster.txt` - Master flag
- `Files\DBI\app.version.txt` - App version
- `Files\DBI\login-h.phy` - Login history
- `Files\DBI\titanver.phy` - Titan version

### Export Files
- `Files\Export\DrugEye` - DrugEye export
- `Files\Export\Titan` - Titan export
- `Program Folder\Files\Export\DrugEye` - DrugEye export path
- `Program Folder\Files\Export\Titan` - Titan export path

### Log Files
- `Files\DBI\myhistory.txt` - User history
- `Files\DBI\processing.txt` - Processing log
- `Files\DBI\stoped.txt` - Stopped log
- `Files\DBI\summer.test.txt` - Summer test
- `Files\DBI\curl.ignore.txt` - Curl ignore
- `Files\DB\server.connection.report.txt` - Server connection report

### Temp Files
- `Files\DBI\salesfulltemp.phy` - Temp sales
- `Files\DBI\pruchworldtemp.phy` - Temp purchases
- `C:\ftpdbi.zip` - FTP zip temp
- `D:\ftpdbi.zip` - FTP zip temp
- `E:\ftpdbi.zip` - FTP zip temp
- `F:\ftpdbi.zip` - FTP zip temp
- `G:\ftpdbi.zip` - FTP zip temp
- `H:\ftpdbi.zip` - FTP zip temp
- `I:\ftpdbi.zip` - FTP zip temp
- `J:\ftpdbi.zip` - FTP zip temp
- `K:\ftpdbi.zip` - FTP zip temp
- `L:\ftpdbi.zip` - FTP zip temp
- `M:\ftpdbi.zip` - FTP zip temp
- `N:\ftpdbi.zip` - FTP zip temp
- `O:\ftpdbi.zip` - FTP zip temp
- `P:\ftpdbi.zip` - FTP zip temp

### Zatca Files
- `C:\saturn\Zatca\computer-1\invoices\` - Zatca invoices
- `C:\saturn\zatca\` - Zatca folder
- `C:\saturn\zatca\computer-1\` - Zatca computer 1
- `C:\saturn\zatca\computer-1\lastdata` - Zatca last data
- `C:\saturn\zatca\computer-1\lastdata\counter.txt` - Zatca counter
- `C:\saturn\zatca\computer-1\lastdata\hash.txt` - Zatca hash

## 17. REGISTRY/CONFIG KEYS

### Registry References
- `WScript.Shell` - Windows Script Host
- `Shell.Application` - Shell application
- `GetSetting` - Get setting function
- `SaveSetting` - Save setting function

### Configuration Files
- `appsettings.json` - Application settings
- `C:\eToolKit\appsettings.json` - EToolKit settings
- `C:\etoolkit\appsettings.json` - EToolKit settings
- `C:\saturn\SDKNETFrameWorkLib.dll.config` - Saturn DLL config

## 18. BRANCH/MULTI-STORE CONFIGURATION

### Branch Hierarchy
- `Input Branch Code` - Branch code input
- `Input Branch Code As it is in Portal` - Branch code in portal
- `<branchcode>` - Branch code field
- `<branchAddress>` - Branch address field
- `branchcode` - Branch code

### Master/Branch System
- `Files\DBI\isbranch.txt` - Branch flag file
- `Files\DBI\ismaster.txt` - Master flag file
- `Convert database from pharmacy to warehouse` - Convert to warehouse
- `Export invoice to another pharmacy` - Export to pharmacy
- `Importing a transferred invoice from another warehouse or pharmacy` - Import from pharmacy
- `Transfer invoice to another pharmacy` - Transfer to pharmacy
- `Unlink current pharmacy` - Unlink pharmacy

### Inter-Branch Transfer
- `Export invoice to another pharmacy` - Export invoice
- `Importing a transferred invoice from another warehouse or pharmacy` - Import invoice
- `Transfer invoice to another pharmacy` - Transfer invoice
- `Import from a batch file` - Import batch
- `Export to a batch file` - Export batch
- `Import from another software` - Import from software

### Stock Synchronization
- `Cloud storage of stock` - Cloud stock storage
- `Export stocks and data` - Export stocks
- `Import the prices from old data` - Import prices
- `Import price adjustments from the group` - Import group prices
- `Share between my group - Show` - Group sharing show
- `Share between my group - upload` - Group sharing upload

### Pharmacy Types
- `Normal pharmacy` - Standard pharmacy
- `Pharmacy store` - Pharmacy store
- `Pharmacy warehouse ` - Pharmacy warehouse
- `Pharmacy No. 0` - Pharmacy number

## 19. ADDITIONAL SETTINGS

### Application Settings
- `Advanced settings` - Advanced settings
- `Debug Mode Activated ` - Debug mode
- `AllowUserResizing` - Allow user resizing
- `Caps Lock` - Caps lock state
- `Scroll Lock` - Scroll lock state

### Sound Settings
- `Sounds` - Sounds settings (22 procedures)

### Style Settings
- `Styles` - Styles settings (11 procedures)

### Screen Settings
- `ModScreen` - Screen module (7 procedures)
- `FFFScreens` - Screens form (11 procedures)

### Color Settings
- `ModColors` - Colors module (3 procedures)
- `FFFColors` - Colors form (4 procedures)
- `colors.phy` - Colors file

## 20. EXTERNAL API IMPORTS

### Windows API
- `SetCapture` - Set capture
- `GetCursorPos` - Get cursor position
- `WindowFromPoint` - Window from point
- `DeleteObject` - Delete object
- `CreateRoundRectRgn` - Create round rect region
- `SetWindowRgn` - Set window region
- `CreateDirectoryW` - Create directory
- `GetFileAttributesW` - Get file attributes
- `DosDateTimeToFileTime` - DOS date time to file time
- `FindNextFileW` - Find next file
- `SafeArrayCreateVector` - Create safe array
- `FileTimeToDosDateTime` - File time to DOS date time
- `SetEnvironmentVariableA` - Set environment variable
- `GetEnvironmentVariableA` - Get environment variable
- `GetStdHandle` - Get standard handle
- `CoTaskMemFree` - Free COM memory
- `CallWindowProcA` - Call window procedure
- `VariantTimeToSystemTime` - Variant time to system time
- `SystemTimeToVariantTime` - System time to variant time
- `LocalFileTimeToFileTime` - Local file time to file time
- `SystemTimeToFileTime` - System time to file time
- `FileTimeToSystemTime` - File time to system time
- `SetEndOfFile` - Set end of file
- `SetFilePointer` - Set file pointer
- `WriteFile` - Write file
- `ReadFile` - Read file
- `CreateFileW` - Create file
- `FindClose` - Find close
- `FindFirstFileW` - Find first file

### Internet API
- `InternetCheckConnectionA` - Check internet connection
- `InternetReadFile` - Read internet file
- `InternetOpenUrlA` - Open internet URL
- `InternetGetLastResponseInfoA` - Get last response
- `FtpGetFileSize` - Get FTP file size
- `FtpGetFileA` - Get FTP file
- `InternetConnectA` - Connect to internet
- `InternetOpenA` - Open internet
- `InternetCloseHandle` - Close internet handle
- `FtpDeleteFileA` - Delete FTP file
- `FtpPutFileA` - Put FTP file
- `FtpOpenFileA` - Open FTP file
- `InternetWriteFile` - Write internet file
- `FtpGetCurrentDirectoryA` - Get FTP current directory
- `FtpSetCurrentDirectoryA` - Set FTP current directory
- `FileTimeToLocalFileTime` - File time to local file time
- `FtpFindFirstFileA` - Find first FTP file
- `InternetFindNextFileA` - Find next internet file
- `InternetGetConnectedStateEx` - Get connected state
- `InternetCheckConnectionA` - Check connection

### Cryptography API
- `CryptStringToBinaryW` - String to binary
- `CryptBinaryToStringW` - Binary to string

### Shell API
- `SHFileOperationA` - Shell file operation
- `FindExecutableA` - Find executable
- `ShellExecuteA` - Shell execute

### Process API
- `CreateToolhelp32Snapshot` - Create snapshot
- `Process32First` - Process first
- `Process32Next` - Process next
- `OpenProcess` - Open process
- `WaitForSingleObject` - Wait for object
- `CloseHandle` - Close handle

### Memory API
- `VirtualAlloc` - Virtual allocate
- `VirtualFree` - Virtual free
- `GlobalAlloc` - Global allocate
- `GlobalFree` - Global free
- `RtlMoveMemory` - Move memory

### Window API
- `GetWindowRect` - Get window rectangle
- `GetForegroundWindow` - Get foreground window
- `PostMessageA` - Post message
- `SendMessageA` - Send message
- `FindWindowA` - Find window
- `GetSystemDirectoryA` - Get system directory
- `GetWindowsDirectoryA` - Get Windows directory
- `GetKeyboardLayoutNameA` - Get keyboard layout
- `SetWindowPos` - Set window position
- `SetParent` - Set parent window
- `GetWindowLongA` - Get window long
- `SetWindowLongA` - Set window long
- `SetLayeredWindowAttributes` - Set layered window attributes

### Display API
- `ChangeDisplaySettingsA` - Change display settings
- `GetSystemMetrics` - Get system metrics
- `EnumDisplaySettingsA` - Enum display settings
- `GetDriveTypeA` - Get drive type
- `SHGetDiskFreeSpaceA` - Get disk free space

### MIDI API
- `midiOutShortMsg` - MIDI short message
- `midiOutOpen` - MIDI open
- `midiOutClose` - MIDI close

### Other API
- `GetAsyncKeyState` - Get async key state
- `GetKeyState` - Get key state
- `DrawFocusRect` - Draw focus rectangle
- `GetCapture` - Get capture
- `SetCapture` - Set capture
- `ReleaseCapture` - Release capture
- `SetTimer` - Set timer
- `KillTimer` - Kill timer
- `GetFocus` - Get focus
- `OffsetRect` - Offset rectangle
- `SetRect` - Set rectangle
- `DrawTextA` - Draw text
- `DrawEdge` - Draw edge
- `WideCharToMultiByte` - Wide char to multi byte
- `MultiByteToWideChar` - Multi byte to wide char
- `ExitWindowsEx` - Exit Windows
- `fCreateShellLink` - Create shell link
- `GetThreadLocale` - Get thread locale
- `Sleep` - Sleep
- `GetModuleHandleA` - Get module handle
- `FormatMessageA` - Format message
- `GetLocaleInfoEx` - Get locale info
- `GenerateBMPW` - Generate BMP
- `GetAdaptersAddresses` - Get adapters addresses
- `GetParent` - Get parent window
- `ScreenToClient` - Screen to client
- `IsCharAlphaA` - Is character alpha
- `IsCharAlphaNumericA` - Is character alpha numeric
- `LoadKeyboardLayoutW` - Load keyboard layout
- `LoadKeyboardLayoutA` - Load keyboard layout
- `IsBadCodePtr` - Is bad code pointer
- `GetProcAddress` - Get proc address
