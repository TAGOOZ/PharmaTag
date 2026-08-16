-- ============================================================================
-- TITAN Pharmacy Management System - Database Schema
-- Extracted from: TITAN.W1 (Phye.exe) VB6 P-Code
-- Source: String constants with embedded SQL
-- Generated: 2026-08-15
-- ============================================================================

-- ============================================================================
-- 1. CORE DRUG TABLES
-- ============================================================================

-- wzdrugs: Master drug list (main drugs table)
CREATE TABLE wzdrugs (
    drugname    NVARCHAR(100) DEFAULT '' NOT NULL,
    barcode     VARCHAR(16) DEFAULT '',
    CoName      NVARCHAR(50) DEFAULT '',
    Generic     NVARCHAR(120) DEFAULT '',
    PriceNow    REAL DEFAULT 0,
    Units       INT DEFAULT 0,
    Unitsmall   INT DEFAULT 0,
    Datee       REAL DEFAULT 0,
    lastmonth   REAL DEFAULT 0,
    localimport INT DEFAULT 0,
    shape       INT DEFAULT 0,
    minimum     REAL DEFAULT 0,
    stock       REAL DEFAULT 0
);

-- wzdrugs2: Secondary drug data (likely extended fields or backup)
CREATE TABLE wzdrugs2 (
    drugname    NVARCHAR(100) DEFAULT '',
    -- Columns mirror wzdrugs for update operations
    lastedit    VARCHAR(50) DEFAULT '',
    pharmacyid  NVARCHAR(15) DEFAULT ''
);

-- ============================================================================
-- 2. PHARMACY NETWORK / CHAIN TABLES
-- ============================================================================

-- titanpharmalist: List of pharmacies in the network
CREATE TABLE titanpharmalist (
    mobile      NVARCHAR(15) DEFAULT '' NOT NULL,
    pharmacyid  NVARCHAR(15) DEFAULT '',
    pharname    NVARCHAR(100) DEFAULT '',
    phar        NVARCHAR(100) DEFAULT '',
    address     NVARCHAR(200) DEFAULT '',
    tip         NVARCHAR(50) DEFAULT ''
);

-- wzphar: Pharmacy names (reference table)
CREATE TABLE wzphar (
    pharname    NVARCHAR(100) DEFAULT ''
);

-- wzaccfreetree: Pharmacy hierarchy / linking tree
CREATE TABLE wzaccfreetree (
    mobile      NVARCHAR(15) DEFAULT '' NOT NULL,
    master      NVARCHAR(15) DEFAULT '',
    fary        NVARCHAR(15) DEFAULT ''
);

-- ============================================================================
-- 3. INVENTORY TRANSFER TABLES
-- ============================================================================

-- titaninn: Inventory transfer records between pharmacies
CREATE TABLE titaninn (
    ID              INT IDENTITY(1,1) NOT NULL,
    fatid           INT DEFAULT 0,
    itemsasstring   NVARCHAR(4000) DEFAULT '',
    datee           INT DEFAULT 0,
    source          NVARCHAR(100) DEFAULT '',
    silsilaid       NVARCHAR(15) DEFAULT '',
    target          NVARCHAR(100) DEFAULT ''
);

-- titanksasales: Chain pharmacy sales transfer data
CREATE TABLE titanksasales (
    invoiceid   REAL DEFAULT 0,
    drugname    NVARCHAR(100) DEFAULT '',
    datee       REAL DEFAULT 0,
    silsilaid   NVARCHAR(15) DEFAULT '',
    pharmacyid  NVARCHAR(15) DEFAULT '',
    price       REAL DEFAULT 0,
    stock       REAL DEFAULT 0,
    barcode     VARCHAR(16) DEFAULT '',
    titanid     NVARCHAR(20) DEFAULT ''
);

-- titanksastock: Chain pharmacy stock transfer data
CREATE TABLE titanksastock (
    drugname    NVARCHAR(100) DEFAULT '',
    datee       REAL DEFAULT 0,
    silsilaid   NVARCHAR(15) DEFAULT '',
    minimum     REAL DEFAULT 0,
    pharmacyid  NVARCHAR(15) DEFAULT '',
    classy      NVARCHAR(35) DEFAULT '',
    stock       REAL DEFAULT 0
);

-- titanstock: Stock data for chain operations
CREATE TABLE titanstock (
    drugname    NVARCHAR(100) DEFAULT '',
    lastedit    VARCHAR(50) DEFAULT '',
    pharmacyid  NVARCHAR(15) DEFAULT '',
    price       REAL DEFAULT 0,
    stock       REAL DEFAULT 0,
    barcode     VARCHAR(16) DEFAULT '',
    titanid     NVARCHAR(20) DEFAULT ''
);

-- ============================================================================
-- 4. NEEDS / SHORTAGES TABLE
-- ============================================================================

-- titanneed: Shortage/drug request tracking between pharmacies
CREATE TABLE titanneed (
    drugname    NVARCHAR(100) DEFAULT '',
    quant       REAL DEFAULT 0,
    datee       REAL DEFAULT 0,
    sender      NVARCHAR(20) DEFAULT '',
    target      NVARCHAR(20) DEFAULT ''
);

-- ============================================================================
-- 5. SALES / INVOICE TABLES
-- ============================================================================

-- invoicedata: Sales invoice header data
CREATE TABLE invoicedata (
    invoiceid   REAL DEFAULT 0,
    datee       REAL DEFAULT 0,
    silsilaid   NVARCHAR(15) DEFAULT '',
    pharmacyid  NVARCHAR(15) DEFAULT '',
    payed       REAL DEFAULT 0,
    disc        REAL DEFAULT 0,
    agel        REAL DEFAULT 0,
    totalvalue  REAL DEFAULT 0
);

-- wzgard: Sales invoice line items (detailed items per invoice)
CREATE TABLE wzgard (
    phar        NVARCHAR(100) DEFAULT '',
    randomid    NVARCHAR(50) DEFAULT '',
    writer      NVARCHAR(50) DEFAULT '',
    datee       REAL DEFAULT 0,
    datetimee   REAL DEFAULT 0,
    classy      NVARCHAR(35) DEFAULT '',
    quant       REAL DEFAULT 0,
    expire      REAL DEFAULT 0,
    price       REAL DEFAULT 0,
    oldstock    REAL DEFAULT 0,
    costvalue   REAL DEFAULT 0,
    vatvalue    REAL DEFAULT 0,
    totalwithvat REAL DEFAULT 0,
    typee       NVARCHAR(20) DEFAULT '',
    drugname    NVARCHAR(100) DEFAULT ''
);

-- orders: Pharmacy orders (for transfer/fulfillment)
CREATE TABLE orders (
    orderid     NVARCHAR(20) DEFAULT '',
    orderdate   NVARCHAR(20) DEFAULT '',
    datee       NVARCHAR(20) DEFAULT '',
    status      NVARCHAR(20) DEFAULT '',
    pharmacyid  NVARCHAR(15) DEFAULT ''
);

-- ============================================================================
-- 6. CUSTOMER / CLIENT TABLES
-- ============================================================================

-- wzcustomers: Customer/patient records
CREATE TABLE wzcustomers (
    randomid    NVARCHAR(50) DEFAULT '',
    phar        NVARCHAR(100) DEFAULT '',
    typee       NVARCHAR(20) DEFAULT '',
    writer      NVARCHAR(50) DEFAULT '',
    creditlimit REAL DEFAULT 0,
    datee       REAL DEFAULT 0,
    namee       NVARCHAR(100) DEFAULT ''
);

-- ============================================================================
-- 7. SUPPLIER / COMPANY TABLES
-- ============================================================================

-- companies: Supplier/company records
CREATE TABLE companies (
    mobile      NVARCHAR(15) DEFAULT '' NOT NULL,
    pass        NVARCHAR(50) DEFAULT '',
    CoName      NVARCHAR(50) DEFAULT ''
);

-- ============================================================================
-- 8. DISCOUNT / PRICING TABLES
-- ============================================================================

-- storediscount: Discount tracking per store
CREATE TABLE storediscount (
    id              INT IDENTITY(1,1) NOT NULL,
    drugname        NVARCHAR(100) DEFAULT '',
    disco           REAL DEFAULT 0,
    datee           REAL DEFAULT 0,
    pharmacyname    NVARCHAR(100) DEFAULT '',
    adress          NVARCHAR(200) DEFAULT '',
    storename       NVARCHAR(100) DEFAULT '',
    tips            NVARCHAR(50) DEFAULT ''
);

-- ============================================================================
-- 9. SERVER / REMOTE CONNECTION TABLES
-- ============================================================================

-- drgserver: Drug data uploaded to central server
CREATE TABLE drgserver (
    id          INT IDENTITY(1,1) NOT NULL,
    datee       REAL DEFAULT 0,
    silsila     NVARCHAR(50) DEFAULT '',
    mobile      NVARCHAR(15) DEFAULT '',
    drugname    NVARCHAR(100) DEFAULT '',
    price       REAL DEFAULT 0,
    barcode     VARCHAR(16) DEFAULT '',
    units       INT DEFAULT 0,
    vat         REAL DEFAULT 0,
    shape       INT DEFAULT 0,
    localimport INT DEFAULT 0
);

-- remotecontrol: Remote control / command relay
CREATE TABLE remotecontrol (
    id              INT IDENTITY(1,1) NOT NULL,
    datee           NVARCHAR(50) DEFAULT '',
    mobile          NVARCHAR(15) DEFAULT '',
    copyid          NVARCHAR(50) DEFAULT '',
    passedfunctions NVARCHAR(4000) DEFAULT ''
);

-- ============================================================================
-- 10. USER ACTION LOGGING
-- ============================================================================

-- TitanUserAction: Audit trail for user modifications
CREATE TABLE TitanUserAction (
    drugname    NVARCHAR(100) DEFAULT '',
    typevalue   NVARCHAR(100) DEFAULT '0',
    oldvalue    NVARCHAR(200) DEFAULT '',
    newvalue    NVARCHAR(200) DEFAULT '',
    mobile      NVARCHAR(15) DEFAULT '',
    namee       NVARCHAR(100) DEFAULT '',
    curbarcode  VARCHAR(16) DEFAULT '',
    curprice    REAL DEFAULT 0,
    units       INT DEFAULT 0,
    datee       REAL DEFAULT 0
);

-- ============================================================================
-- 11. USER DATA SYNC TABLE
-- ============================================================================

-- usersourceupdate: Drug price/stock updates shared between pharmacies
CREATE TABLE usersourceupdate (
    id              INT IDENTITY(1,1) NOT NULL,
    drugname        NVARCHAR(100) DEFAULT '',
    price           REAL DEFAULT 0,
    units           INT DEFAULT 0,
    localimport     INT DEFAULT 0,
    datee           REAL DEFAULT 0,
    barcode         VARCHAR(16) DEFAULT '',
    pharmacyid      NVARCHAR(15) DEFAULT '',
    lastedit        VARCHAR(50) DEFAULT ''
);

-- ============================================================================
-- 12. NILSEN REPORTING TABLE
-- ============================================================================

-- nilsen2: Nilsen market research reporting data
CREATE TABLE nilsen2 (
    id          INT IDENTITY(1,1) NOT NULL,
    datee       REAL DEFAULT 0,
    drugname    NVARCHAR(100) DEFAULT '',
    pharmacyid  NVARCHAR(15) DEFAULT '',
    data        NVARCHAR(4000) DEFAULT ''
);

-- ============================================================================
-- 13. ONLINE GATHERING TABLE
-- ============================================================================

-- taronlineeg: Online data collection / e-government integration
CREATE TABLE taronlineeg (
    id              INT IDENTITY(1,1) NOT NULL,
    CreateDate      DATETIME DEFAULT GETDATE(),
    mobile          NVARCHAR(15) DEFAULT '',
    NameEnglish     NVARCHAR(100) DEFAULT '',
    -- Additional columns used in queries
    Data1           NVARCHAR(500) DEFAULT '',
    Data2           NVARCHAR(500) DEFAULT ''
);

-- ============================================================================
-- 14. CHAIN BUY TABLES
-- ============================================================================

-- ChainBuyStore: Chain pharmacy store registry
CREATE TABLE ChainBuyStore (
    DrugName        NVARCHAR(100) DEFAULT '',
    PharmacyId      NVARCHAR(15) DEFAULT '',
    PharmacistTel   NVARCHAR(15) DEFAULT '',
    StoreName       NVARCHAR(100) DEFAULT '',
    Address         NVARCHAR(200) DEFAULT ''
);

-- ChainBuyUsers: Chain pharmacy user registry
CREATE TABLE ChainBuyUsers (
    PharmacistTel   NVARCHAR(15) DEFAULT '',
    Name            NVARCHAR(100) DEFAULT '',
    PharmacyId      NVARCHAR(15) DEFAULT '',
    -- Additional user fields
    Datee           REAL DEFAULT 0
);

-- ============================================================================
-- 15. RAWAKID (WAREHOUSE) TABLE
-- ============================================================================

-- RawakidTablew: Warehouse/shelf tracking data
CREATE TABLE RawakidTablew (
    PharmacistTel   NVARCHAR(15) DEFAULT '',
    DrugName        NVARCHAR(100) DEFAULT '',
    Shelf           NVARCHAR(50) DEFAULT '',
    Datee           REAL DEFAULT 0,
    -- Additional warehouse fields
    Data1           NVARCHAR(200) DEFAULT '',
    Data2           NVARCHAR(200) DEFAULT ''
);

-- ============================================================================
-- 16. DRUG EYE DASHBOARD TABLE
-- ============================================================================

-- drugeyedash2: Drug monitoring dashboard data
CREATE TABLE drugeyedash2 (
    id          INT IDENTITY(1,1) NOT NULL,
    drugname    NVARCHAR(100) DEFAULT '',
    datee       REAL DEFAULT 0,
    data        NVARCHAR(4000) DEFAULT ''
);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
