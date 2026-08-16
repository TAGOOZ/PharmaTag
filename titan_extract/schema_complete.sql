-- ============================================================================
-- TITAN.W1 — COMPLETE DATABASE SCHEMA
-- Saudi Pharmacy Management System
-- Extracted from VB6 decompiled strings (26,970 constants) + p-code analysis
-- ============================================================================
-- NOTE: Types marked [INFERRED] are reconstructed from context, not from
--       explicit CREATE TABLE statements. Types marked [EXPLICIT] were found
--       in CREATE TABLE / column-definition fragments in the string pool.
-- ============================================================================

-- ============================================================================
-- 1. wzdrugs — Drug Master Table
-- ============================================================================
CREATE TABLE wzdrugs (
    drugname        NVARCHAR(100) DEFAULT '' NOT NULL,  -- [EXPLICIT] primary key / unique drug name
    drugnamear      NVARCHAR(100) DEFAULT '' NOT NULL,  -- [EXPLICIT] Arabic name
    barcode         VARCHAR(16)   DEFAULT '' NOT NULL,  -- [EXPLICIT] main barcode
    Barcode1        VARCHAR(16)   DEFAULT '',           -- [INFERRED] additional barcodes (up to 5)
    Barcode2        VARCHAR(16)   DEFAULT '',
    Barcode3        VARCHAR(16)   DEFAULT '',
    Barcode4        VARCHAR(16)   DEFAULT '',
    Barcode5        VARCHAR(16)   DEFAULT '',
    vat             REAL          DEFAULT 0,            -- [INFERRED] VAT percentage
    units           INT           DEFAULT 0,            -- [EXPLICIT] units in pack
    Unitsmall       INT           DEFAULT 0,            -- [EXPLICIT] small units
    classy          NVARCHAR(35)  DEFAULT '',           -- [EXPLICIT] drug category/form
    generic         NVARCHAR(120) DEFAULT '',           -- [EXPLICIT] generic name
    pharmacology    NVARCHAR(200) DEFAULT '',           -- [INFERRED] pharmacology class
    co              NVARCHAR(100) DEFAULT '',           -- [INFERRED] company/manufacturer
    unitsclass      NVARCHAR(50)  DEFAULT '',           -- [INFERRED] unit classification
    price           REAL          DEFAULT 0,            -- [INFERRED] selling price
    PriceNow        REAL          DEFAULT 0,            -- [EXPLICIT] current price
    lastedit        DATETIME,                           -- [INFERRED] last edit timestamp
    pharmacyid      NVARCHAR(15)  DEFAULT '',           -- [EXPLICIT] pharmacy identifier
    stock           REAL          DEFAULT 0,            -- [EXPLICIT] current stock
    titanid         INT           DEFAULT 0,            -- [INFERRED] internal ID for chain sync
    disco           REAL          DEFAULT 0,            -- [INFERRED] discount percentage
    pricechanged    BIT           DEFAULT 0,            -- [INFERRED] price change flag
    localimport     INT           DEFAULT 0,            -- [EXPLICIT] import source flag
    wareprice3      NVARCHAR(50)  DEFAULT '',           -- [EXPLICIT] warehouse price reference
    history         NVARCHAR(MAX) DEFAULT '',           -- [EXPLICIT] change history
    agel            REAL          DEFAULT 0             -- [INFERRED] age-related flag
);

-- ============================================================================
-- 2. wzdrugs2 — Drug Extended / Cost Data
-- ============================================================================
CREATE TABLE wzdrugs2 (
    drugname    NVARCHAR(100) DEFAULT '' NOT NULL,       -- [INFERRED] FK to wzdrugs
    unitcost    REAL          DEFAULT 0,                 -- [EXPLICIT] unit cost (computed from wzgard)
    costvalue   REAL          DEFAULT 0,                 -- [EXPLICIT] cost value
    expire      REAL          DEFAULT 0                  -- [EXPLICIT] expiry date (VB6 date serial)
);

-- ============================================================================
-- 3. wzgard — Stock / Inventory (per pharmacy)
-- ============================================================================
CREATE TABLE wzgard (
    phar        NVARCHAR(15)  DEFAULT '',                -- [EXPLICIT] pharmacy ID
    randomid    NVARCHAR(50)  DEFAULT '',                -- [EXPLICIT] unique batch identifier
    writer      NVARCHAR(50)  DEFAULT '',                -- [EXPLICIT] user who entered
    datee       REAL          DEFAULT 0,                 -- [EXPLICIT] date (VB6 serial)
    datetimee   DATETIME,                                -- [EXPLICIT] date+time
    classy      NVARCHAR(35)  DEFAULT '',                -- [EXPLICIT] category
    quant       REAL          DEFAULT 0,                 -- [EXPLICIT] quantity
    expire      REAL          DEFAULT 0,                 -- [EXPLICIT] expiry date (VB6 serial)
    price       REAL          DEFAULT 0,                 -- [EXPLICIT] price
    oldstock    REAL          DEFAULT 0,                 -- [EXPLICIT] previous stock
    costvalue   REAL          DEFAULT 0,                 -- [EXPLICIT] cost value
    vatvalue    REAL          DEFAULT 0,                 -- [EXPLICIT] VAT value
    totalwithvat REAL         DEFAULT 0,                 -- [EXPLICIT] total with VAT
    typee       NVARCHAR(50)  DEFAULT '',                -- [EXPLICIT] type (e.g., purchase, return)
    drugname    NVARCHAR(100) DEFAULT ''                 -- [EXPLICIT] FK to wzdrugs
);

-- ============================================================================
-- 4. wzcustomers — Customers
-- ============================================================================
CREATE TABLE wzcustomers (
    randomid    NVARCHAR(50)  DEFAULT '',                -- [EXPLICIT] unique identifier
    phar        NVARCHAR(15)  DEFAULT '',                -- [EXPLICIT] pharmacy ID
    typee       NVARCHAR(50)  DEFAULT '',                -- [EXPLICIT] customer type
    writer      NVARCHAR(50)  DEFAULT '',                -- [EXPLICIT] entered by
    creditlimit REAL          DEFAULT 0,                 -- [EXPLICIT] credit limit
    datee       REAL          DEFAULT 0,                 -- [EXPLICIT] creation date
    namee       NVARCHAR(100) DEFAULT ''                 -- [EXPLICIT] customer name
);

-- ============================================================================
-- 5. companies — Suppliers
-- ============================================================================
CREATE TABLE companies (
    mobile      NVARCHAR(15)  DEFAULT '' NOT NULL,       -- [EXPLICIT] supplier phone/ID (PK)
    pass        NVARCHAR(50)  DEFAULT ''                 -- [EXPLICIT] password/pass code
);

-- ============================================================================
-- 6. titaninn — Inter-Pharmacy Transfers / Purchase Orders
-- ============================================================================
CREATE TABLE titaninn (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    fatid           INT           DEFAULT 0,             -- [EXPLICIT] fat (group) ID
    itemsasstring   NVARCHAR(4000) DEFAULT '',           -- [EXPLICIT] serialized items
    datee           INT           DEFAULT 0,             -- [EXPLICIT] date (integer format)
    source          NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] source pharmacy
    silsilaid       NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] chain/series ID
    target          NVARCHAR(100) DEFAULT ''             -- [EXPLICIT] target pharmacy
);

-- ============================================================================
-- 7. titanksasales — Chain Sales
-- ============================================================================
CREATE TABLE titanksasales (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    invoiceid       REAL          DEFAULT 0,             -- [EXPLICIT] invoice number
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    silsilaid       NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] chain ID
    pharmacyid      NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy ID
    payed           REAL          DEFAULT 0,             -- [EXPLICIT] amount paid
    disc            REAL          DEFAULT 0,             -- [EXPLICIT] discount
    agel            REAL          DEFAULT 0,             -- [EXPLICIT] age/type
    totalvalue      REAL          DEFAULT 0              -- [EXPLICIT] total value
);

-- ============================================================================
-- 8. titanksastock — Chain Stock (drug stock per chain pharmacy)
-- ============================================================================
CREATE TABLE titanksastock (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] FK to wzdrugs
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    silsilaid       NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] chain ID
    minimum         REAL          DEFAULT 0,             -- [EXPLICIT] minimum stock level
    pharmacyid      NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy ID
    classy          NVARCHAR(35)  DEFAULT '',            -- [EXPLICIT] category
    stock           REAL          DEFAULT 0              -- [EXPLICIT] current stock
);

-- ============================================================================
-- 9. titanstock — Stock (per pharmacy, drug-level)
-- ============================================================================
CREATE TABLE titanstock (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] FK to wzdrugs
    lastedit        DATETIME,                            -- [EXPLICIT] last edit timestamp
    pharmacyid      NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy ID
    price           REAL          DEFAULT 0,             -- [EXPLICIT] selling price
    stock           REAL          DEFAULT 0,             -- [EXPLICIT] current stock
    barcode         VARCHAR(16)   DEFAULT '',            -- [EXPLICIT] barcode
    titanid         INT           DEFAULT 0              -- [EXPLICIT] chain sync ID
);

-- ============================================================================
-- 10. titanneed — Inter-Pharmacy Needs / Orders
-- ============================================================================
CREATE TABLE titanneed (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] FK to wzdrugs
    quant           REAL          DEFAULT 0,             -- [EXPLICIT] quantity needed
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    sender          NVARCHAR(20)  DEFAULT '',            -- [EXPLICIT] requesting pharmacy
    target          NVARCHAR(20)  DEFAULT ''             -- [EXPLICIT] fulfilling pharmacy
);

-- ============================================================================
-- 11. invoicedata — Invoice Header / Line Items
-- ============================================================================
CREATE TABLE invoicedata (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    invoiceid       REAL          DEFAULT 0,             -- [EXPLICIT] invoice number
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    silsilaid       NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] chain ID
    pharmacyid      NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy ID
    payed           REAL          DEFAULT 0,             -- [EXPLICIT] amount paid
    disc            REAL          DEFAULT 0,             -- [EXPLICIT] discount
    agel            REAL          DEFAULT 0,             -- [EXPLICIT] type/age
    totalvalue      REAL          DEFAULT 0,             -- [EXPLICIT] total value
    -- Additional columns from invoice line inserts:
    IdDateTime      DATETIME,                            -- [INFERRED] item entry timestamp
    Quant           REAL          DEFAULT 0,             -- [INFERRED] quantity
    DrugName        NVARCHAR(100) DEFAULT '',            -- [INFERRED] FK to wzdrugs
    SellDisc        REAL          DEFAULT 0,             -- [INFERRED] sale discount
    Tips            NVARCHAR(50)  DEFAULT '',            -- [INFERRED] tips/notes
    Expire          REAL          DEFAULT 0,             -- [INFERRED] expiry date
    Minimum         REAL          DEFAULT 0,             -- [INFERRED] minimum
    price           REAL          DEFAULT 0              -- [INFERRED] unit price
);

-- ============================================================================
-- 12. orders — Orders
-- ============================================================================
CREATE TABLE orders (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    orderid         NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] order identifier
    orderdate       DATETIME,                            -- [EXPLICIT] order date
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date (VB6 serial)
    status          NVARCHAR(50)  DEFAULT NULL,          -- [EXPLICIT] NULL=pending, 'saved'=done
    pharmacyid      NVARCHAR(15)  DEFAULT ''             -- [EXPLICIT] pharmacy ID
);

-- ============================================================================
-- 13. wzphar — Pharmacy Master
-- ============================================================================
CREATE TABLE wzphar (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    pharname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] pharmacy name
    pharmacyid      NVARCHAR(15)  DEFAULT '',            -- [INFERRED] pharmacy ID
    adress          NVARCHAR(200) DEFAULT '',            -- [INFERRED] address
    mobile          NVARCHAR(15)  DEFAULT ''             -- [INFERRED] phone
);

-- ============================================================================
-- 14. storediscount — Discount Records
-- ============================================================================
CREATE TABLE storediscount (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    adress          NVARCHAR(200) DEFAULT '',            -- [EXPLICIT] branch/address
    storename       NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] store name
    pharmacyname    NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] pharmacy name
    pharmacyname2   NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] pharmacy name (alt)
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    tips            NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] notes/type
    titanver        NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] Titan version
    country         NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] country
    drugname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] FK to wzdrugs
    barcode         VARCHAR(16)   DEFAULT '',            -- [EXPLICIT] barcode
    price           REAL          DEFAULT 0,             -- [EXPLICIT] price
    disco           REAL          DEFAULT 0,             -- [EXPLICIT] discount %
    units           INT           DEFAULT 0,             -- [EXPLICIT] units
    pricechanged    BIT           DEFAULT 0,             -- [EXPLICIT] price changed flag
    localimport     INT           DEFAULT 0,             -- [EXPLICIT] import flag
    quant           REAL          DEFAULT 0              -- [EXPLICIT] quantity
);

-- ============================================================================
-- 15. drgserver — Drug Server Config / Drug List
-- ============================================================================
CREATE TABLE drgserver (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    silsila         NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] chain/series ID
    mobile          NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy phone
    drugname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] FK to wzdrugs
    price           REAL          DEFAULT 0,             -- [EXPLICIT] price
    barcode         VARCHAR(16)   DEFAULT '',            -- [EXPLICIT] barcode
    units           INT           DEFAULT 0,             -- [EXPLICIT] units
    vat             REAL          DEFAULT 0,             -- [EXPLICIT] VAT
    shape           INT           DEFAULT 0,             -- [EXPLICIT] shape/form code
    localimport     INT           DEFAULT 0              -- [EXPLICIT] import source
);

-- ============================================================================
-- 16. remotecontrol — Remote Control / Function Upload Log
-- ============================================================================
CREATE TABLE remotecontrol (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    datee           REAL          DEFAULT 0,             -- [EXPLICIT] date
    mobile          NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy phone
    copyid          NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] copy identifier
    passedfunctions NVARCHAR(MAX) DEFAULT ''             -- [EXPLICIT] uploaded functions data
);

-- ============================================================================
-- 17. TitanUserAction — Audit / User Action Log
-- ============================================================================
CREATE TABLE TitanUserAction (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '0',           -- [EXPLICIT] drug affected
    typevalue       NVARCHAR(100) DEFAULT '0',           -- [EXPLICIT] action type
    oldvalue        NVARCHAR(100) DEFAULT '0',           -- [EXPLICIT] previous value
    newvalue        NVARCHAR(100) DEFAULT '0',           -- [EXPLICIT] new value
    mobile          NVARCHAR(15)  DEFAULT '0',           -- [EXPLICIT] user/phone
    namee           NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] user name
    curbarcode      VARCHAR(15)   DEFAULT '0',           -- [EXPLICIT] current barcode
    curprice        REAL          DEFAULT '0',           -- [EXPLICIT] current price
    units           INT           DEFAULT 0,             -- [EXPLICIT] units
    datee           REAL          DEFAULT '0'            -- [EXPLICIT] date
);

-- ============================================================================
-- 18. usersourceupdate — Sync / Source Update Log
-- ============================================================================
CREATE TABLE usersourceupdate (
    id              INT IDENTITY(1,1),                   -- [EXPLICIT] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] FK to wzdrugs
    price           REAL          DEFAULT 0,             -- [EXPLICIT] price
    units           INT           DEFAULT 0,             -- [EXPLICIT] units
    localimport     INT           DEFAULT 0,             -- [EXPLICIT] import source
    datee           REAL          DEFAULT 0              -- [EXPLICIT] date
);

-- ============================================================================
-- 19. nilsen2 — Nilsen Integration Data
-- ============================================================================
CREATE TABLE nilsen2 (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '',            -- [INFERRED] drug name
    -- Additional columns TBD — table is cleared with DELETE but no INSERT found
    data            NVARCHAR(MAX) DEFAULT ''             -- [INFERRED] serialized data
);

-- ============================================================================
-- 20. taronlineeg — Online Drug Data (TAR Online EG)
-- ============================================================================
CREATE TABLE taronlineeg (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    CreateDate      DATETIME,                            -- [EXPLICIT] creation date
    mobile          NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy phone
    NameEnglish     NVARCHAR(200) DEFAULT '',            -- [EXPLICIT] English name
    NameArabic      NVARCHAR(200) DEFAULT '',            -- [EXPLICIT] Arabic name
    -- Additional columns from update context:
    drugname        NVARCHAR(100) DEFAULT '',            -- [INFERRED] drug name
    price           REAL          DEFAULT 0,             -- [INFERRED] price
    barcode         VARCHAR(16)   DEFAULT ''             -- [INFERRED] barcode
);

-- ============================================================================
-- 21. ChainBuyStore — Chain Buy Store
-- ============================================================================
CREATE TABLE ChainBuyStore (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    DrugName        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] drug name
    -- Additional columns inferred from context:
    StoreName       NVARCHAR(100) DEFAULT '',            -- [INFERRED] store name
    PharmacistTel   NVARCHAR(15)  DEFAULT '',            -- [INFERRED] pharmacist phone
    Expire          REAL          DEFAULT 0,             -- [INFERRED] expiry
    IdDateTime      DATETIME,                            -- [INFERRED] entry timestamp
    Quant           REAL          DEFAULT 0,             -- [INFERRED] quantity
    SellDisc        REAL          DEFAULT 0,             -- [INFERRED] sale discount
    Mohafaza        NVARCHAR(50)  DEFAULT '',            -- [INFERRED] governorate
    Markaz          NVARCHAR(50)  DEFAULT '',            -- [INFERRED] center/district
    price           REAL          DEFAULT 0              -- [INFERRED] price
);

-- ============================================================================
-- 22. ChainBuyUsers — Chain Buy Users
-- ============================================================================
CREATE TABLE ChainBuyUsers (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    PharmacistTel   NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacist phone
    -- Additional columns inferred from RawakidTablew context:
    Expire          REAL          DEFAULT 0,             -- [INFERRED] expiry
    IdDateTime      DATETIME,                            -- [INFERRED] entry timestamp
    Quant           REAL          DEFAULT 0,             -- [INFERRED] quantity
    DrugName        NVARCHAR(100) DEFAULT '',            -- [INFERRED] drug name
    SellDisc        REAL          DEFAULT 0,             -- [INFERRED] sale discount
    Mohafaza        NVARCHAR(50)  DEFAULT '',            -- [INFERRED] governorate
    Markaz          NVARCHAR(50)  DEFAULT '',            -- [INFERRED] center/district
    Tips            NVARCHAR(50)  DEFAULT '',            -- [INFERRED] notes
    RequisterTel    NVARCHAR(15)  DEFAULT '',            -- [INFERRED] requester phone
    country         NVARCHAR(50)  DEFAULT '',            -- [INFERRED] country
    price           REAL          DEFAULT 0              -- [INFERRED] price
);

-- ============================================================================
-- 23. RawakidTablew — Rawakid Table (multi-pharmacy order items)
-- ============================================================================
CREATE TABLE RawakidTablew (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    PharmacistTel   NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacist phone
    Expire          REAL          DEFAULT 0,             -- [EXPLICIT] expiry
    IdDateTime      DATETIME,                            -- [EXPLICIT] entry timestamp
    Quant           REAL          DEFAULT 0,             -- [EXPLICIT] quantity
    DrugName        NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] drug name
    SellDisc        REAL          DEFAULT 0,             -- [EXPLICIT] sale discount
    Mohafaza        NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] governorate
    Markaz          NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] center/district
    SourceIdDateTime DATETIME,                           -- [EXPLICIT] source timestamp
    price           REAL          DEFAULT 0,             -- [EXPLICIT] price
    Tips            NVARCHAR(50)  DEFAULT '',            -- [EXPLICIT] notes
    RequisterTel    NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] requester phone
    country         NVARCHAR(50)  DEFAULT ''             -- [EXPLICIT] country
);

-- ============================================================================
-- 24. drugeyedash2 — Drug Eye Dashboard
-- ============================================================================
CREATE TABLE drugeyedash2 (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    drugname        NVARCHAR(100) DEFAULT '',            -- [INFERRED] drug name
    -- Columns TBD — table is SELECTed but no INSERT found
    data            NVARCHAR(MAX) DEFAULT ''             -- [INFERRED] dashboard data
);

-- ============================================================================
-- 25. wzaccfreetree — Accounting Hierarchy / Free Tree
-- ============================================================================
CREATE TABLE wzaccfreetree (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    mobile          NVARCHAR(15)  DEFAULT '',            -- [EXPLICIT] pharmacy phone
    master          NVARCHAR(100) DEFAULT '',            -- [EXPLICIT] master account
    fary            NVARCHAR(100) DEFAULT ''             -- [EXPLICIT] sub-account (fary)
);

-- ============================================================================
-- 26. titanpharmalist — Pharmacy List (registered pharmacies)
-- ============================================================================
CREATE TABLE titanpharmalist (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    mobile          NVARCHAR(15)  DEFAULT '' NOT NULL,   -- [EXPLICIT] pharmacy phone (PK)
    -- Additional columns from update context:
    pharmacyname    NVARCHAR(100) DEFAULT '',            -- [INFERRED] pharmacy name
    barcode         VARCHAR(16)   DEFAULT '',            -- [INFERRED] barcode
    changed         DATETIME,                            -- [INFERRED] last changed
    apptype         NVARCHAR(50)  DEFAULT ''             -- [INFERRED] app type
);

-- ============================================================================
-- 27. farysales — Fary (Branch) Sales
-- ============================================================================
CREATE TABLE farysales (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    mobile          NVARCHAR(15)  DEFAULT '' NOT NULL,   -- [EXPLICIT] pharmacy phone
    -- Columns from context:
    grand           REAL          DEFAULT 0,             -- [INFERRED] grand total
    father          NVARCHAR(100) DEFAULT '',            -- [INFERRED] parent account
    son             NVARCHAR(100) DEFAULT '',            -- [INFERRED] child account
    datee           REAL          DEFAULT 0,             -- [INFERRED] date
    datetimee       DATETIME,                            -- [INFERRED] datetime
    dateemanual     REAL          DEFAULT 0,             -- [INFERRED] manual date
    monthe          NVARCHAR(10)  DEFAULT '',            -- [INFERRED] month
    yearo           NVARCHAR(10)  DEFAULT '',            -- [INFERRED] year
    payed           REAL          DEFAULT 0,             -- [INFERRED] amount paid
    creditdebit     NVARCHAR(20)  DEFAULT '',            -- [INFERRED] credit/debit flag
    typee           NVARCHAR(50)  DEFAULT '',            -- [INFERRED] type
    phar            NVARCHAR(15)  DEFAULT '',            -- [INFERRED] pharmacy ID
    randomid        NVARCHAR(50)  DEFAULT '',            -- [INFERRED] unique ID
    tips            NVARCHAR(50)  DEFAULT '',            -- [INFERRED] notes
    writer          NVARCHAR(50)  DEFAULT '',            -- [INFERRED] entered by
    classy          NVARCHAR(35)  DEFAULT ''             -- [INFERRED] category
);

-- ============================================================================
-- 28. ZATCA — ZATCA (Zakat, Tax and Customs Authority) Invoice Log
-- ============================================================================
CREATE TABLE ZATCA (
    id              INT IDENTITY(1,1),                   -- [INFERRED] auto-increment PK
    invoiceid       REAL          DEFAULT 0,             -- [INFERRED] invoice number
    uuid            NVARCHAR(100) DEFAULT '',            -- [INFERRED] ZATCA UUID
    datee           REAL          DEFAULT 0,             -- [INFERRED] date
    pharmacyid      NVARCHAR(15)  DEFAULT '',            -- [INFERRED] pharmacy ID
    status          NVARCHAR(50)  DEFAULT '',            -- [INFERRED] submission status
    hash            NVARCHAR(200) DEFAULT '',            -- [INFERRED] invoice hash
    xml             NVARCHAR(MAX) DEFAULT '',            -- [INFERRED] raw XML
    response        NVARCHAR(MAX) DEFAULT ''             -- [INFERRED] ZATCA response
);

-- ============================================================================
-- RELATIONSHIPS (inferred from JOIN conditions and FK references)
-- ============================================================================
-- wzdrugs.drugname  ──< wzdrugs2.drugname          (1:1 cost extension)
-- wzdrugs.drugname  ──< wzgard.drugname             (1:many stock batches)
-- wzdrugs.drugname  ──< titanksastock.drugname       (1:many chain stock)
-- wzdrugs.drugname  ──< titanstock.drugname          (1:many pharmacy stock)
-- wzdrugs.drugname  ──< titanneed.drugname           (1:many needs)
-- wzdrugs.drugname  ──< drgserver.drugname           (1:many server drug list)
-- wzdrugs.drugname  ──< storediscount.drugname       (1:many discount records)
-- wzdrugs.drugname  ──< usersourceupdate.drugname    (1:many sync records)
-- wzdrugs.drugname  ──< TitanUserAction.drugname     (1:many audit log)
-- wzdrugs.drugname  ──< taronlineeg.drugname         (1:many online records)
-- wzphar.pharmacyid ──< wzgard.phar                  (1:many stock per pharmacy)
-- wzphar.pharmacyid ──< wzcustomers.phar             (1:many customers per pharmacy)
-- wzphar.pharmacyid ──< titanstock.pharmacyid        (1:many stock per pharmacy)
-- wzphar.pharmacyid ──< titanksastock.pharmacyid     (1:many chain stock per pharmacy)
-- wzphar.pharmacyid ──< titanksasales.pharmacyid     (1:many chain sales per pharmacy)
-- wzphar.pharmacyid ──< invoicedata.pharmacyid       (1:many invoices per pharmacy)
-- wzphar.pharmacyid ──< orders.pharmacyid            (1:many orders per pharmacy)
-- wzphar.pharmacyid ──< storediscount.pharmacyname   (1:many discounts per pharmacy)
-- wzphar.pharmacyid ──< titanpharmalist.mobile       (1:1 pharmacy registration)
-- wzphar.pharmacyid ──< remotecontrol.mobile         (1:many remote commands)
-- wzphar.pharmacyid ──< drgserver.mobile             (1:many drug server entries)
-- wzaccfreetree.mobile ──< wzphar (pharmacy link)    (hierarchy tree)
-- companies.mobile  ──< wzcustomers (supplier link)  (credit accounts)
-- titaninn.source   ──< wzphar                       (transfer source)
-- titaninn.target   ──< wzphar                       (transfer target)
-- titanneed.sender  ──< wzphar                       (need source)
-- titanneed.target  ──< wzphar                       (need target)
-- ============================================================================
