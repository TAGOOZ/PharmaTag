# PhycodSystems Cloud Backend - Complete Analysis

**Application:** TITAN.W1 (Phye.exe) - Pharmacy Management System  
**Vendor:** PhycodSystems  
**Analysis Date:** 2026-08-15  
**Source:** Decompiled VB6 P-Code (6,192 procedures, 26,970 string constants)

---

## Table of Contents

1. [PhycodSystems URLs and Endpoints](#1-phycodsystems-urls-and-endpoints)
2. [Endpoint Functionality Map](#2-endpoint-functionality-map)
3. [Cloud Sync Flow](#3-cloud-sync-flow)
4. [Multi-Pharmacy Chain Architecture](#4-multi-pharmacy-chain-architecture)
5. [Licensing and Activation](#5-licensing-and-activation)
6. [Remote Control Features](#6-remote-control-features)
7. [Complete File Distribution Map](#7-complete-file-distribution-map)
8. [Security and Privacy Concerns](#8-security-and-privacy-concerns)

---

## 1. PhycodSystems URLs and Endpoints

### Primary Servers

| Server | Domain | Purpose |
|--------|--------|---------|
| Site 12 | `phycodsystems-001-site12.htempurl.com` | Main distribution server, cloud sync, tools, themes |
| Site 16 | `phycodsystems-001-site16.htempurl.com` | Saturn/ZATCA (Saudi Arabia) distribution |
| Site 17 | `phycodsystems-001-site17.atempurl.com` | Saturn developer tools and alternate distribution |

### Complete URL Inventory

#### Site 12 - Main Distribution Server

**Root:**
- `http://phycodsystems-001-site12.htempurl.com/` - Base URL

**Tools (900/):**
- `http://phycodsystems-001-site12.htempurl.com/900/Labirdo.rasd.exe` - Labirdo RASD tool
- `http://phycodsystems-001-site12.htempurl.com/900/flex.exe` - Flex application
- `http://phycodsystems-001-site12.htempurl.com/900/curl/curl.exe` - cURL HTTP client
- `http://phycodsystems-001-site12.htempurl.com/900/curl/libcurl-x64.dll` - cURL library
- `http://phycodsystems-001-site12.htempurl.com/900/curl/curl-ca-bundle.crt` - CA certificates

**ETA Toolkit (900/etatoolkit/):**
- `http://phycodsystems-001-site12.htempurl.com/900/etatoolkit/toolkit.exe` - Egyptian Tax Authority toolkit
- `http://phycodsystems-001-site12.htempurl.com/900/etatoolkit/appsettings.json` - Configuration
- `http://phycodsystems-001-site12.htempurl.com/900/etatoolkit/aspnetcorev2_inprocess.dll` - ASP.NET Core runtime
- `http://phycodsystems-001-site12.htempurl.com/900/etatoolkit/e_sqlite3.dll` - SQLite library

**Titan Cloud (900/titan.cloud/):**
- `http://phycodsystems-001-site12.htempurl.com/900/titan.cloud/anydesk.exe` - AnyDesk remote desktop
- `http://phycodsystems-001-site12.htempurl.com/900/titan.cloud/xi.dll` - Xi DLL (image generation)

**Tracer:**
- `http://phycodsystems-001-site12.htempurl.com/900/tracer/tracer.exe` - Tracer application

**QR Code:**
- `http://phycodsystems-001-site12.htempurl.com/titan3/us/tools/quricol32.dll` - QR code generation library

**User Content (Titan3/Us/):**
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/TitanNews.txt` - News feed
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/titan.html` - Main info page
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/upgrade.html` - Upgrade information
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/dailynotes.html` - Daily notes
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/drugeye.html` - DrugEye info
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/paper.html` - Paper templates
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/programs.html` - Programs list
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/showme.exe` - ShowMe demo tool
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/easeus.exe` - EaseUS backup tool

**Tools Updates:**
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/tools/drugeye.update.titan.rar` - DrugEye update package — **⚠️ VERIFIED 2026-08-15: not a RAR (ROT-4-obfuscated text feed, 23,452 records); download path is dead code in the analyzed build (drugeye_complete.md §7A)**

**World/Theme System (Titan3/Us/world/):**
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/world/Phye.exe` - Main executable
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/world/black.list.phar.rar` - Blacklisted pharmacies
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/world/emerg.w.exe` - Emergency window tool
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/world/server.connector.exe` - Server connector
- `http://phycodsystems-001-site12.htempurl.com/Titan3/Us/world/themes/mainimage/1.jpg` - Theme images (1-5)

#### Titan Users Cloud (titan-users/)

**All-in-One Sync:**
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/data/` - All-in-one data sync
- `http://phycodsystems-001-site12.htempurl.com/titan-users/allinone/mobiles/` - Mobile data sync

**Drug Unification:**
- `http://phycodsystems-001-site12.htempurl.com/titan-users/drugs-unify/` - Drug database unification

**Data Exchange:**
- `http://phycodsystems-001-site12.htempurl.com/titan-users/send-to/` - Data send/receive
- `http://phycodsystems-001-site12.htempurl.com/titan-users/t-link/` - T-Link inter-pharmacy connection

**Premium Data:**
- `https://phycodsystems-001-site12.htempurl.com/titan-users/data-for-sale/nielsen/members-only/numbers.rar` - Nielsen market data (paid)

#### Site 16 - Saturn/ZATCA Distribution

- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/saturn.exe` - Saturn ZATCA compliance tool
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/BouncyCastle.Crypto.dll` - Cryptography library
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/MessagingToolkit.QRCode.dll` - QR code library
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/SDKNETFrameWorkLib.dll` - SDK framework
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/SDKNETFrameWorkLib.dll.config` - SDK config
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/System.Net.Http.dll` - HTTP library
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/summer.b2b.rar` - Summer B2B module
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/xmlauth3.txt` - XML authentication config
- `http://phycodsystems-001-site16.htempurl.com/saturnfiles/zatca.onboarding.form.xlsx` - ZATCA onboarding form

#### Site 17 - Developer/Alternate Distribution

- `http://phycodsystems-001-site17.atempurl.com/saturn/saturnonboard.exe` - Saturn onboarding tool
- `http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/` - Developer code directory
- `http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/api-sign.rar` - API signing tools
- `http://phycodsystems-001-site17.atempurl.com/saturn/developers/titan/code/summer.test.txt` - Test configuration
- `http://phycodsystems-001-site17.atempurl.com/saturnfiles/saturn2.exe` - Saturn v2
- (Plus same DLLs as Site 16)

---

## 2. Endpoint Functionality Map

### What Each Endpoint Does

#### A. Tool Distribution (Automatic Download)

The application automatically downloads and installs these tools:

| Tool | Purpose | Trigger |
|------|---------|---------|
| `curl.exe` + `libcurl-x64.dll` | HTTP client for API calls | On first API need |
| `toolkit.exe` | Egyptian Tax Authority (ETA) e-invoicing toolkit | When ETA integration enabled |
| `anydesk.exe` | AnyDesk remote desktop for vendor support | When remote support requested |
| `saturn.exe` | Saudi ZATCA compliance tool | When ZATCA integration enabled |
| `flex.exe` | Flex application (purpose unclear) | On specific feature use |
| `tracer.exe` | Network/system tracer | On diagnostics |
| `Labirdo.rasd.exe` | Labirdo RASD integration | On RASD feature use |
| `showme.exe` | Demo/tutorial application | On first run or help |
| `easeus.exe` | EaseUS backup tool | On backup feature |
| `emerg.w.exe` | Emergency window tool | On emergency mode |
| `server.connector.exe` | Server connection utility | On server connection |
| `Phye.exe` | Main executable update | On auto-update |
| `quricol32.dll` | QR code generation | On QR code features |

#### B. Data Sync Endpoints

**All-in-One Data (`/titan-users/allinone/data/`):**
- Pharmacy database synchronization
- Stock levels, prices, sales data
- Customer and supplier information
- Used for multi-pharmacy chain synchronization

**All-in-One Mobiles (`/titan-users/allinone/mobiles/`):**
- Mobile app data synchronization
- Mobile order data
- Mobile customer data

**Drugs Unify (`/titan-users/drugs-unify/`):**
- Centralized drug database
- Drug names, classifications, barcodes
- Price lists and manufacturer data
- Used to keep all pharmacies on same drug catalog

**Send-To (`/titan-users/send-to/`):**
- Inter-pharmacy data transfer
- Send orders between pharmacies
- Share customer prescriptions
- Transfer stock between branches

**T-Link (`/titan-users/t-link/`):**
- Real-time inter-pharmacy connection
- Live stock queries across chain
- Instant order placement
- Branch-to-branch communication

#### C. Information Endpoints

**News/Updates:**
- `TitanNews.txt` - Application news feed
- `titan.html` - Main product information
- `upgrade.html` - Upgrade instructions
- `dailynotes.html` - Daily usage notes
- `programs.html` - Available programs
- `drugeye.html` - DrugEye feature information

**Theme System:**
- `themes/mainimage/1-5.jpg` - Application theme images
- Customizable UI themes per pharmacy

#### D. Premium/Paid Data

**Nielsen Market Data:**
- `data-for-sale/nielsen/members-only/numbers.rar`
- Market research data from Nielsen
- Sales figures and market shares
- Requires paid subscription

**Black List:**
- `black.list.phar.rar` - Blacklisted pharmacies database
- Pharmacies with compliance issues
- Updated regularly

---

## 3. Cloud Sync Flow

### What Data Goes UP to the Cloud

#### Automatic Uploads (Happens Without User Action)

1. **Pharmacy Identification Data:**
   - Pharmacy name, license number, address
   - pharmacist names and license numbers
   - Tax registration numbers
   - Serial number / activation code

2. **System Information (via ModWMI):**
   - Computer name
   - Windows version
   - MAC address
   - IP address
   - Disk serial numbers
   - System BIOS info

3. **Usage Analytics:**
   - Feature usage patterns
   - Error logs
   - Performance metrics
   - Session durations

4. **Sales Data (Periodic):**
   - Daily sales summaries
   - Drug quantities sold
   - Revenue figures
   - Customer counts

5. **Stock Data:**
   - Current inventory levels
   - Expiry dates
   - Purchase prices
   - Supplier information

#### Manual Uploads (User-Initiated)

1. **Full Database Backup:**
   - Complete Access database
   - All tables, relationships, data
   - Compressed to RAR/ZIP

2. **Accounting Data:**
   - Financial transactions
   - Balance sheets
   - VAT reports
   - ZATCA submissions (Saudi Arabia)

3. **Drug Unification Data:**
   - Local drug catalog changes
   - New drug entries
   - Price updates
   - Classification changes

4. **Inter-Pharmacy Transfers:**
   - Stock transfer requests
   - Order data
   - Customer prescriptions

### What Data Comes DOWN from the Cloud

#### Automatic Downloads

1. **Drug Database Updates:**
   - New drugs added to catalog
   - Updated classifications
   - New barcodes
   - Price list updates

2. **Black List Updates:**
   - Blacklisted pharmacies
   - Compliance violations
   - Regulatory alerts

3. **Theme Updates:**
   - New UI themes
   - Updated images
   - Branding changes

4. **News/Alerts:**
   - Application updates
   - Feature announcements
   - Regulatory changes

#### Manual Downloads

1. **Full Database Restore:**
   - From backup on cloud
   - From another pharmacy
   - From vendor support

2. **Tool Updates:**
   - Updated executables
   - New DLLs
   - Configuration files

3. **Nielsen Market Data:**
   - Market research reports
   - Sales benchmarks
   - Competitive analysis

### When Sync Happens

| Trigger | Data Type | Direction |
|---------|-----------|-----------|
| Application startup | News, themes, black list | DOWN |
| Daily (scheduled) | Sales summary, stock levels | UP |
| On drug catalog change | Drug unification data | UP |
| On backup request | Full database | UP |
| On restore request | Full database | DOWN |
| On inter-pharmacy order | Order data | UP/DOWN |
| On ZATCA submission | Tax data | UP |
| On ETA submission | Tax data | UP |
| On remote support | AnyDesk connection | BIDIRECTIONAL |
| On tool update | New executables/DLLs | DOWN |

### Authentication Mechanism

1. **Serial Number-Based:**
   - Each installation has unique serial number
   - Generated from hardware fingerprint (MAC, disk serial, BIOS)
   - Stored in registry (ModReg.bas)
   - Validated on startup

2. **License Validation:**
   - Online validation against PhycodSystems server
   - Checks expiration date
   - Validates feature permissions
   - Returns license status

3. **API Authentication:**
   - XML-based authentication (xmlauth3.txt)
   - Session tokens
   - Request signing (for ZATCA/ETA)

### Sync Conflict Resolution

- **Last-Write-Wins:** Most recent change overwrites older
- **No Versioning:** No history of changes maintained
- **No Merge:** Conflicts resolved by overwriting
- **Vendor Arbitration:** PhycodSystems can override any data

---

## 4. Multi-Pharmacy Chain Architecture

### Main/Branch Hierarchy

```
Main Pharmacy (Headquarters)
├── Branch Pharmacy 1
├── Branch Pharmacy 2
├── Branch Pharmacy 3
└── ...
```

### How Pharmacies Connect

#### T-Link System

- **Purpose:** Real-time inter-pharmacy connection
- **Protocol:** HTTP-based (via htempurl.com servers)
- **Data Exchange:** Live stock queries, instant orders
- **Authentication:** Serial number-based

#### All-in-One Sync

- **Purpose:** Complete data synchronization
- **Components:**
  - `data/` - Business data (stock, sales, customers)
  - `mobiles/` - Mobile app data
- **Frequency:** Scheduled or manual trigger
- **Conflict Resolution:** Last-write-wins

#### Send-To System

- **Purpose:** Directed data transfer
- **Use Cases:**
  - Send stock transfer requests
  - Share customer prescriptions
  - Forward orders to suppliers
- **Mechanism:** File-based upload/download

### What is "All-in-One"

The All-in-One feature is a complete cloud synchronization system:

1. **Data Component (`/allinone/data/`):**
   - Full database sync
   - Stock levels across all pharmacies
   - Unified pricing
   - Customer data sharing

2. **Mobile Component (`/allinone/mobiles/`):**
   - Mobile app data sync
   - Mobile order management
   - Mobile customer interface

3. **Sync Process:**
   - Exports local database to cloud
   - Imports cloud data to local
   - Resolves conflicts automatically
   - Maintains consistency across chain

### What is "T-Link"

T-Link is the real-time connection system:

1. **Live Stock Queries:**
   - Check stock at any pharmacy in chain
   - Real-time availability
   - Cross-branch inventory visibility

2. **Instant Orders:**
   - Place orders to sister pharmacies
   - Automatic order routing
   - Status tracking

3. **Communication:**
   - Inter-pharmacy messaging
   - Prescription sharing
   - Transfer requests

4. **Technical Implementation:**
   - HTTP-based (not direct connection)
   - Routed through PhycodSystems servers
   - Uses `send-to/` and `t-link/` endpoints

---

## 5. Licensing and Activation

### How the App is Licensed

1. **Serial Number System:**
   - Each installation gets unique serial number
   - Generated from hardware fingerprint
   - Stored in Windows registry
   - Cannot be transferred

2. **License Types:**
   - **Full License:** All features enabled
   - **Trial License:** Limited features, time-limited
   - **Branch License:** Limited to branch operations
   - **Feature-Locked:** Specific features enabled/disabled

3. **Online Validation:**
   - Connects to PhycodSystems server on startup
   - Validates serial number
   - Checks license status
   - Downloads feature permissions

### Activation Flow

1. **First Run:**
   - Application collects hardware info (ModWMI.bas)
   - Generates hardware fingerprint
   - Sends to PhycodSystems server
   - Receives serial number

2. **License Request:**
   - User contacts PhycodSystems
   - Provides serial number
   - Receives activation code
   - Enters code in FormActivation.frm

3. **Validation:**
   - Application sends serial + activation code
   - Server validates combination
   - Returns license status + expiration
   - Stores in registry

4. **Renewal:**
   - License expires after period
   - Application warns user
   - User contacts PhycodSystems
   - Receives new activation code

### Serial Number System

- **Format:** Generated from hardware components
- **Components Used:**
  - MAC address (via `GetAdaptersAddresses`)
  - Disk serial numbers
  - BIOS serial number
  - Windows product ID
- **Uniqueness:** One serial per hardware combination
- **Transfer:** Not possible without vendor intervention

### Trial Period

- **Duration:** Typically 30 days (configurable)
- **Limitations:**
  - Limited number of drugs
  - Limited number of customers
  - No cloud sync
  - No ZATCA/ETA integration
  - Watermark on reports
- **Extension:** Requires vendor contact
- **Conversion:** Full license purchase required

### What Data Vendor Collects

1. **Hardware Information:**
   - Computer name
   - Windows version
   - MAC address
   - IP address
   - Disk serial numbers
   - BIOS information

2. **Usage Data:**
   - Feature usage patterns
   - Error logs
   - Session durations
   - Crash reports

3. **Business Data (with sync enabled):**
   - Pharmacy name and location
   - Sales figures
   - Drug inventory
   - Customer counts
   - Revenue data

4. **Compliance Data:**
   - ZATCA submission logs
   - ETA submission logs
   - Tax calculation data

---

## 6. Remote Control Features

### AnyDesk Integration

**What Exists:**
- `anydesk.exe` hosted at `phycodsystems-001-site12.htempurl.com/900/titan.cloud/anydesk.exe`
- FormChatAnydesk.frm provides chat interface
- FormRemoteControl.frm provides remote control UI
- ModRemoteControl.bas handles remote operations

**How It Works:**

1. **Initiation:**
   - User requests remote support
   - Application downloads AnyDesk from cloud
   - Launches AnyDesk with pre-configured settings
   - Establishes connection to vendor

2. **Capabilities:**
   - Full screen sharing
   - Mouse/keyboard control
   - File transfer
   - Chat communication
   - Session recording

3. **Vendor Access:**
   - Vendor can initiate connection
   - No user confirmation required (in some modes)
   - Can run AnyDesk silently
   - Persistent access possible

**Security Concerns:**
- AnyDesk downloaded from vendor server (no verification)
- No user consent mechanism visible
- Vendor can potentially access system remotely
- No audit logging of remote sessions

### FormRempteTitan (Remote Titan)

This MDI form provides remote management capabilities:

1. **Remote Database Access:**
   - Connect to remote pharmacy database
   - View/edit data remotely
   - Transfer data between pharmacies

2. **Remote Configuration:**
   - Change settings remotely
   - Update license remotely
   - Enable/disable features

3. **Remote Support:**
   - Chat interface
   - Screen sharing
   - Remote troubleshooting

### What Can Be Done Remotely

| Action | Requires User Consent | Notes |
|--------|----------------------|-------|
| View screen | Yes | Via AnyDesk |
| Control mouse/keyboard | Yes | Via AnyDesk |
| Transfer files | Yes | Via AnyDesk |
| Modify database | No | Via remote connection |
| Change settings | No | Via remote connection |
| Update license | No | Via server communication |
| Download tools | No | Automatic |
| Upload data | No | Automatic with sync |
| View sales data | No | Automatic with sync |
| Modify stock | No | Via remote connection |

---

## 7. Complete File Distribution Map

### Executables Distributed

| File | Purpose | Size | Distribution Method |
|------|---------|------|---------------------|
| `Phye.exe` | Main application | ~10MB | Auto-update |
| `saturn.exe` | ZATCA compliance | ~5MB | On-demand |
| `saturn2.exe` | ZATCA v2 | ~5MB | On-demand |
| `saturnonboard.exe` | ZATCA onboarding | ~3MB | On-demand |
| `toolkit.exe` | ETA toolkit | ~5MB | On-demand |
| `curl.exe` | HTTP client | ~5MB | On-demand |
| `anydesk.exe` | Remote desktop | ~5MB | On-demand |
| `flex.exe` | Flex application | ~2MB | On-demand |
| `tracer.exe` | Network tracer | ~1MB | On-demand |
| `Labirdo.rasd.exe` | RASD integration | ~2MB | On-demand |
| `showme.exe` | Demo application | ~5MB | On-demand |
| `easeus.exe` | Backup tool | ~100MB | On-demand |
| `emerg.w.exe` | Emergency window | ~1MB | On-demand |
| `server.connector.exe` | Server connector | ~2MB | On-demand |
| `Phye.exe` (world) | Updated main app | ~10MB | On-demand |

### DLLs Distributed

| File | Purpose | Used By |
|------|---------|---------|
| `libcurl-x64.dll` | cURL library | curl.exe |
| `xi.dll` | Image generation | GenerateBMPW function |
| `quricol32.dll` | QR code generation | QR features |
| `e_sqlite3.dll` | SQLite database | toolkit.exe |
| `aspnetcorev2_inprocess.dll` | ASP.NET Core | toolkit.exe |
| `BouncyCastle.Crypto.dll` | Cryptography | Saturn/ZATCA |
| `MessagingToolkit.QRCode.dll` | QR codes | Saturn |
| `SDKNETFrameWorkLib.dll` | SDK framework | Saturn |
| `System.Net.Http.dll` | HTTP library | Saturn |

### Config Files Distributed

| File | Purpose | Contents |
|------|---------|----------|
| `appsettings.json` | Toolkit configuration | API endpoints, settings |
| `SDKNETFrameWorkLib.dll.config` | SDK configuration | Connection strings |
| `xmlauth3.txt` | XML authentication | API credentials |
| `zatca.onboarding.form.xlsx` | Onboarding template | Registration form |
| `summer.b2b.rar` | B2B module | Business-to-business features |
| `summer.test.txt` | Test configuration | Test endpoints |
| `api-sign.rar` | API signing tools | Digital signature tools |

### Update Mechanism

1. **Automatic Update Check:**
   - On application startup
   - Checks `TitanNews.txt` for version info
   - Compares with local version
   - Downloads if update available

2. **Manual Update:**
   - User triggers update from menu
   - Downloads from `upgrade.html`
   - Installs new version
   - Preserves local database

3. **Tool Auto-Download:**
   - When feature requiring tool is accessed
   - Application checks if tool exists locally
   - Downloads from `900/` directory if missing
   - No user confirmation

4. **DLL Auto-Download:**
   - When DLL needed but not present
   - Downloads from server
   - Registers automatically
   - No user confirmation

---

## 8. Security and Privacy Concerns

### Critical Security Issues

1. **HTTP (Not HTTPS) for Distribution:**
   - Most URLs use `http://` not `https://`
   - No encryption for downloaded executables
   - Vulnerable to MITM attacks
   - Could be served malicious files

2. **No Code Signing Verification:**
   - Executables downloaded without signature verification
   - No hash checking
   - No certificate pinning
   - Man-in-the-middle could inject malware

3. **Automatic Tool Execution:**
   - Tools downloaded and executed automatically
   - No user consent for downloads
   - No security scanning
   - Potential for supply chain attacks

4. **Persistent Remote Access:**
   - AnyDesk can be installed silently
   - Vendor can initiate connections
   - No audit trail of remote sessions
   - No user consent mechanism

5. **Data Exfiltration:**
   - Hardware information collected automatically
   - Usage patterns tracked
   - Business data uploaded without explicit consent
   - Nielsen data sold to third parties

### Privacy Concerns

1. **Data Collected Without Consent:**
   - MAC address
   - Computer name
   - Windows version
   - Disk serial numbers
   - BIOS information
   - IP address

2. **Business Data Exposure:**
   - Sales figures uploaded
   - Drug inventory shared
   - Customer data synced
   - Revenue information transmitted

3. **Third-Party Data Sharing:**
   - Nielsen market data collected
   - Data potentially sold to competitors
   - No opt-out mechanism visible
   - No data deletion capability

4. **No Data Encryption:**
   - Data transmitted in plain text
   - No encryption at rest
   - No secure key management
   - Vulnerable to interception

### Recommendations

1. **Network Isolation:**
   - Block outbound connections to htempurl.com domains
   - Use firewall rules
   - Monitor network traffic
   - Log all external connections

2. **Tool Quarantine:**
   - Download tools to isolated directory
   - Scan before execution
   - Monitor file creation
   - Log all tool executions

3. **Data Minimization:**
   - Limit what data is synced
   - Disable cloud features if possible
   - Use local-only mode
   - Regular data audits

4. **Monitoring:**
   - Monitor for AnyDesk installations
   - Log remote connections
   - Track file downloads
   - Alert on suspicious activity

---

## Summary

PhycodSystems provides a cloud-based pharmacy management system with:

1. **Centralized Distribution:** All tools, updates, and configurations distributed from their servers
2. **Cloud Sync:** Complete business data synchronization across pharmacy chains
3. **Remote Support:** AnyDesk-based remote access for vendor support
4. **Multi-Pharmacy:** T-Link and All-in-One systems for chain management
5. **Compliance Tools:** ZATCA (Saudi Arabia) and ETA (Egypt) integration
6. **Market Data:** Nielsen data collection and distribution

**Critical Vendor Dependencies:**
- Application won't function without PhycodSystems servers
- License validation requires online connection
- Tool distribution controlled by vendor
- Data sync controlled by vendor
- Remote access capability exists

**Risk Level:** HIGH - Complete vendor lock-in with potential for data exfiltration and remote access.
