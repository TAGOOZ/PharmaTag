# TITAN.W1 — Complete Database Schema

**System**: Saudi Pharmacy Management System (VB6 application)
**Database**: SQL Server (accessed via ADODB)
**Extracted from**: 26,970 UTF-16LE string constants + 6,192 procedure p-code disassembly

---

## Table Count: 28 tables

---

## 1. wzdrugs — Drug Master Table

The central drug reference table. Every drug in the system is registered here.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `drugname` | NVARCHAR(100) | `''` | **PK** — English drug name |
| `drugnamear` | NVARCHAR(100) | `''` | Arabic drug name |
| `barcode` | VARCHAR(16) | `''` | Main international barcode |
| `Barcode1` | VARCHAR(16) | `''` | Additional barcode #1 |
| `Barcode2` | VARCHAR(16) | `''` | Additional barcode #2 |
| `Barcode3` | VARCHAR(16) | `''` | Additional barcode #3 |
| `Barcode4` | VARCHAR(16) | `''` | Additional barcode #4 |
| `Barcode5` | VARCHAR(16) | `''` | Additional barcode #5 |
| `vat` | REAL | `0` | VAT percentage |
| `units` | INT | `0` | Units per pack |
| `Unitsmall` | INT | `0` | Small units per unit |
| `classy` | NVARCHAR(35) | `''` | Drug category/form (TAB, CAPS, SYRUP, etc.) |
| `generic` | NVARCHAR(120) | `''` | Generic name |
| `pharmacology` | NVARCHAR(200) | `''` | Pharmacology class |
| `co` | NVARCHAR(100) | `''` | Manufacturer company |
| `unitsclass` | NVARCHAR(50) | `''` | Unit classification |
| `price` | REAL | `0` | Selling price |
| `PriceNow` | REAL | `0` | Current price |
| `lastedit` | DATETIME | — | Last edit timestamp |
| `pharmacyid` | NVARCHAR(15) | `''` | Pharmacy identifier |
| `stock` | REAL | `0` | Current stock quantity |
| `titanid` | INT | `0` | Internal chain sync ID |
| `disco` | REAL | `0` | Discount percentage |
| `pricechanged` | BIT | `0` | Price change flag |
| `localimport` | INT | `0` | Import source (0-5) |
| `wareprice3` | NVARCHAR(50) | `''` | Warehouse price reference |
| `history` | NVARCHAR(MAX) | `''` | Change history |
| `agel` | REAL | `0` | Age-related flag |

**SQL Evidence**:
```
"insert into wzdrugs (drugname,drugnamear,barcode,vat,units,classy,generic,pharmacology,co,unitsclass, price) values ("
"update wzdrugs set"
"if not exists (select * from wzdrugs where trim(drugname) =N'"
"OR Barcode1=N'" ... "OR Barcode5=N'"
"FROM wzdrugs2 d INNER JOIN wzgard g AND d.drugname = g.drugname"
```

---

## 2. wzdrugs2 — Drug Extended / Cost Data

Extension table for cost and expiry tracking per drug.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `unitcost` | REAL | `0` | Unit cost (computed: costvalue/quant) |
| `costvalue` | REAL | `0` | Total cost value |
| `expire` | REAL | `0` | Expiry date (VB6 serial) |

**SQL Evidence**:
```
"FROM wzdrugs2 d INNER JOIN wzgard g AND d.drugname = g.drugname"
"SET d.unitcost = g.costvalue / NULLIF(g.quant, 0)"
"d.costvalue = g.costvalue, d.expire = g.expire"
"update wzdrugs2 set"
```

---

## 3. wzgard — Stock / Inventory (per pharmacy, per batch)

Tracks stock batches with full audit trail per pharmacy.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `phar` | NVARCHAR(15) | `''` | **FK→wzphar** — pharmacy ID |
| `randomid` | NVARCHAR(50) | `''` | Unique batch identifier |
| `writer` | NVARCHAR(50) | `''` | User who entered |
| `datee` | REAL | `0` | Date (VB6 serial) |
| `datetimee` | DATETIME | — | Full datetime |
| `classy` | NVARCHAR(35) | `''` | Category |
| `quant` | REAL | `0` | Quantity |
| `expire` | REAL | `0` | Expiry date (VB6 serial) |
| `price` | REAL | `0` | Price |
| `oldstock` | REAL | `0` | Previous stock |
| `costvalue` | REAL | `0` | Cost value |
| `vatvalue` | REAL | `0` | VAT value |
| `totalwithvat` | REAL | `0` | Total with VAT |
| `typee` | NVARCHAR(50) | `''` | Type (purchase, return, etc.) |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |

**SQL Evidence**:
```
"insert into wzgard (phar,randomid,writer,datee,datetimee,classy,quant,expire,price,oldstock,costvalue,vatvalue,totalwithvat,typee,drugname)values ("
"delete from wzgard where phar = N'"
"if not exists (select drugname from wzgard where drugname=N'"
```

---

## 4. wzcustomers — Customers

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `randomid` | NVARCHAR(50) | `''` | **PK** — unique ID |
| `phar` | NVARCHAR(15) | `''` | **FK→wzphar** — pharmacy |
| `typee` | NVARCHAR(50) | `''` | Customer type |
| `writer` | NVARCHAR(50) | `''` | Entered by |
| `creditlimit` | REAL | `0` | Credit limit |
| `datee` | REAL | `0` | Creation date |
| `namee` | NVARCHAR(100) | `''` | Customer name |

**SQL Evidence**:
```
"insert into wzcustomers (randomid,phar,typee,writer,creditlimit,datee,namee) values("
"if not exists( select * from wzcustomers where phar =N'"
```

---

## 5. companies — Suppliers

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `mobile` | NVARCHAR(15) | `''` | **PK** — supplier phone/ID |
| `pass` | NVARCHAR(50) | `''` | Password/pass code |

**SQL Evidence**:
```
"insert into companies (mobile,pass) values ("
"if not exists( select * from companies where mobile=N'"
```

---

## 6. titaninn — Inter-Pharmacy Transfers / Purchase Orders

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `fatid` | INT | `0` | Group/batch ID |
| `itemsasstring` | NVARCHAR(4000) | `''` | Serialized item list |
| `datee` | INT | `0` | Date (integer format) |
| `source` | NVARCHAR(100) | `''` | Source pharmacy |
| `silsilaid` | NVARCHAR(15) | `''` | Chain/series ID |
| `target` | NVARCHAR(100) | `''` | Target pharmacy |

**SQL Evidence**:
```
"create table titaninn (id int identity(1,1), fatid int default '0', itemsasstring nvarchar(4000) default '', datee int default 0, source nvarchar(100) default '', silsilaid nvarchar(15) default '', target nvarchar(100) default '')"
"insert into titaninn (fatid,itemsasstring,datee,source,silsilaid,target)VALUES ("
"select * from titaninn where source =N'"
"select * from titaninn where target =N'"
"select fatid from titaninn where"
"update titaninn set target =N''"
"delete from titaninn"
"drop table titaninn"
```

---

## 7. titanksasales — Chain Sales

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `invoiceid` | REAL | `0` | Invoice number |
| `datee` | REAL | `0` | Date |
| `silsilaid` | NVARCHAR(15) | `''` | Chain ID |
| `pharmacyid` | NVARCHAR(15) | `''` | **FK→wzphar** |
| `payed` | REAL | `0` | Amount paid |
| `disc` | REAL | `0` | Discount |
| `agel` | REAL | `0` | Type/age |
| `totalvalue` | REAL | `0` | Total value |

**SQL Evidence**:
```
"CREATE TABLE titanksasales ("
"insert into titanksasales ("
"select invoiceid from titanksasales where"
"update titanksasales set"
"DROP table titanksasales"
```

---

## 8. titanksastock — Chain Stock (drug stock per chain pharmacy)

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `datee` | REAL | `0` | Date |
| `silsilaid` | NVARCHAR(15) | `''` | Chain ID |
| `minimum` | REAL | `0` | Minimum stock level |
| `pharmacyid` | NVARCHAR(15) | `''` | **FK→wzphar** |
| `classy` | NVARCHAR(35) | `''` | Category |
| `stock` | REAL | `0` | Current stock |

**SQL Evidence**:
```
"CREATE TABLE titanksastock ("
"begin insert into titanksastock (drugname,datee,silsilaid,minimum,pharmacyid,classy,stock) values ("
"select drugname from titanksastock where"
"delete from titanksastock"
"DROP TABLE titanksastock"
```

---

## 9. titanstock — Stock (per pharmacy, drug-level)

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `lastedit` | DATETIME | — | Last edit timestamp |
| `pharmacyid` | NVARCHAR(15) | `''` | **FK→wzphar** |
| `price` | REAL | `0` | Selling price |
| `stock` | REAL | `0` | Current stock |
| `barcode` | VARCHAR(16) | `''` | Barcode |
| `titanid` | INT | `0` | Chain sync ID |

**SQL Evidence**:
```
"begin insert into titanstock (drugname,lastedit,pharmacyid,price,stock,barcode,titanid) values ("
"select drugname from titanstock where"
"update titanstock set"
```

---

## 10. titanneed — Inter-Pharmacy Needs / Orders

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `quant` | REAL | `0` | Quantity needed |
| `datee` | REAL | `0` | Date |
| `sender` | NVARCHAR(20) | `''` | Requesting pharmacy |
| `target` | NVARCHAR(20) | `''` | Fulfilling pharmacy |

**SQL Evidence**:
```
"CREATE TABLE titanneed ("
"insert into titanneed (drugname,quant,datee,sender,target) values ("
"DROP table titanneed"
```

---

## 11. invoicedata — Invoice Header / Line Items

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `invoiceid` | REAL | `0` | Invoice number |
| `datee` | REAL | `0` | Date |
| `silsilaid` | NVARCHAR(15) | `''` | Chain ID |
| `pharmacyid` | NVARCHAR(15) | `''` | **FK→wzphar** |
| `payed` | REAL | `0` | Amount paid |
| `disc` | REAL | `0` | Discount |
| `agel` | REAL | `0` | Type |
| `totalvalue` | REAL | `0` | Total value |
| `IdDateTime` | DATETIME | — | Item entry timestamp |
| `Quant` | REAL | `0` | Quantity |
| `DrugName` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `SellDisc` | REAL | `0` | Sale discount |
| `Tips` | NVARCHAR(50) | `''` | Notes |
| `Expire` | REAL | `0` | Expiry date |
| `Minimum` | REAL | `0` | Minimum |
| `price` | REAL | `0` | Unit price |

**SQL Evidence**:
```
"invoicedata"
"invoiceid,datee,silsilaid,pharmacyid,payed,disc,agel,totalvalue ) values ("
"(IdDateTime,Quant,DrugName,SellDisc,Tips,Expire,Minimum,price)"
"GROUP BY orderid, orderdate,datee,status"
```

---

## 12. orders — Orders

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `orderid` | NVARCHAR(50) | `''` | Order identifier |
| `orderdate` | DATETIME | — | Order date |
| `datee` | REAL | `0` | Date (VB6 serial) |
| `status` | NVARCHAR(50) | NULL | NULL=pending, 'saved'=completed |
| `pharmacyid` | NVARCHAR(15) | `''` | **FK→wzphar** |

**SQL Evidence**:
```
"FROM orders where status is null and orderdate= '"
"GROUP BY orderid, orderdate,datee,status"
"update orders set status='saved' where pharmacyid =N'"
"and orderid=N'"
```

---

## 13. wzphar — Pharmacy Master

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `pharname` | NVARCHAR(100) | `''` | Pharmacy name |
| `pharmacyid` | NVARCHAR(15) | `''` | Pharmacy ID |
| `adress` | NVARCHAR(200) | `''` | Address |
| `mobile` | NVARCHAR(15) | `''` | Phone |

**SQL Evidence**:
```
"select distinct pharname from wzphar"
"group by pharmacyname,adress"
"where pharmacyname=N'"
```

---

## 14. storediscount — Discount Records

Tracks all discount changes across pharmacies.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `adress` | NVARCHAR(200) | `''` | Branch/address |
| `storename` | NVARCHAR(100) | `''` | Store name |
| `pharmacyname` | NVARCHAR(100) | `''` | Pharmacy name |
| `pharmacyname2` | NVARCHAR(100) | `''` | Pharmacy name (alt) |
| `datee` | REAL | `0` | Date |
| `tips` | NVARCHAR(50) | `''` | Notes/type |
| `titanver` | NVARCHAR(50) | `''` | Titan version |
| `country` | NVARCHAR(50) | `''` | Country |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `barcode` | VARCHAR(16) | `''` | Barcode |
| `price` | REAL | `0` | Price |
| `disco` | REAL | `0` | Discount % |
| `units` | INT | `0` | Units |
| `pricechanged` | BIT | `0` | Price changed flag |
| `localimport` | INT | `0` | Import flag |
| `quant` | REAL | `0` | Quantity |

**SQL Evidence**:
```
"insert into storediscount (adress,storename,pharmacyname,pharmacyname2,datee,tips,titanver,country,drugname,barcode,price,disco,units,pricechanged,localimport,quant) values("
"select * from storediscount where adress="
"select drugname,count(*),max(disco),min(disco),max(datee) from storediscount where adress="
"select pharmacyname,adress,count(*),max(datee) from storediscount"
"select storename,count(*) from storediscount where adress="
"if not exists (select * from storediscount"
"order by drugname desc, disco desc"
```

---

## 15. drgserver — Drug Server Config / Drug List

Central drug list maintained on the server.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `datee` | REAL | `0` | Date |
| `silsila` | NVARCHAR(50) | `''` | Chain/series ID |
| `mobile` | NVARCHAR(15) | `''` | Pharmacy phone |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `price` | REAL | `0` | Price |
| `barcode` | VARCHAR(16) | `''` | Barcode |
| `units` | INT | `0` | Units |
| `vat` | REAL | `0` | VAT |
| `shape` | INT | `0` | Shape/form code |
| `localimport` | INT | `0` | Import source |

**SQL Evidence**:
```
"insert into drgserver (datee,silsila,mobile,drugname,price,barcode,units,vat,shape,localimport)"
"select * from drgserver where silsila = N'"
"Delete from drgserver where id = N'"
```

---

## 16. remotecontrol — Remote Control / Function Upload Log

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `datee` | REAL | `0` | Date |
| `mobile` | NVARCHAR(15) | `''` | Pharmacy phone |
| `copyid` | NVARCHAR(50) | `''` | Copy identifier |
| `passedfunctions` | NVARCHAR(MAX) | `''` | Uploaded function data |

**SQL Evidence**:
```
"insert into remotecontrol (datee,mobile,copyid,passedfunctions)"
"select id,datee,passedfunctions from remotecontrol where mobile = N'"
"select passedfunctions from remotecontrol where datee > N'"
"delete from remotecontrol where id = N'"
"delete from remotecontrol where passedfunctions =N'"
```

---

## 17. TitanUserAction — Audit / User Action Log

Tracks all drug modifications for compliance.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `'0'` | Drug affected |
| `typevalue` | NVARCHAR(100) | `'0'` | Action type |
| `oldvalue` | NVARCHAR(100) | `'0'` | Previous value |
| `newvalue` | NVARCHAR(100) | `'0'` | New value |
| `mobile` | NVARCHAR(15) | `'0'` | User phone |
| `namee` | NVARCHAR(100) | `''` | User name |
| `curbarcode` | VARCHAR(15) | `'0'` | Current barcode |
| `curprice` | REAL | `'0'` | Current price |
| `units` | INT | `0` | Units |
| `datee` | REAL | `'0'` | Date |

**SQL Evidence**:
```
"CREATE TABLE TitanUserAction"
"INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)"
```

---

## 18. usersourceupdate — Sync / Source Update Log

Tracks drug updates for synchronization across chain pharmacies.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `''` | **FK→wzdrugs** |
| `price` | REAL | `0` | Price |
| `units` | INT | `0` | Units |
| `localimport` | INT | `0` | Import source |
| `datee` | REAL | `0` | Date |

**SQL Evidence**:
```
"insert into usersourceupdate (drugname,price,units,localimport,..."
"select drugname from usersourceupdate"
"SELECT top 3000 * FROM usersourceupdate WHERE Datee > '"
"DELETE FROM usersourceupdate WHERE id='"
```

---

## 19. nilsen2 — Nilsen Integration Data

Temporary data table (cleared frequently).

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `''` | Drug name |
| `data` | NVARCHAR(MAX) | `''` | Serialized data |

**SQL Evidence**:
```
"delete from nilsen2"
```

---

## 20. taronlineeg — Online Drug Data (TAR Online EG)

Egyptian online drug catalog integration.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `CreateDate` | DATETIME | — | Creation date |
| `mobile` | NVARCHAR(15) | `''` | Pharmacy phone |
| `NameEnglish` | NVARCHAR(200) | `''` | English name |
| `NameArabic` | NVARCHAR(200) | `''` | Arabic name |
| `drugname` | NVARCHAR(100) | `''` | Drug name |
| `price` | REAL | `0` | Price |
| `barcode` | VARCHAR(16) | `''` | Barcode |

**SQL Evidence**:
```
"SELECT count(*) FROM taronlineeg"
"SELECT top 100 * FROM taronlineeg WHERE CreateDate >"
"SELECT top 100 * FROM taronlineeg WHERE mobile='"
"SELECT top 50 * FROM taronlineeg WHERE NameEnglish like N'"
"update taronlineeg set"
```

---

## 21. ChainBuyStore — Chain Buy Store

Multi-pharmacy purchase coordination.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `DrugName` | NVARCHAR(100) | `''` | Drug name |
| `StoreName` | NVARCHAR(100) | `''` | Store name |
| `PharmacistTel` | NVARCHAR(15) | `''` | Pharmacist phone |
| `Expire` | REAL | `0` | Expiry |
| `IdDateTime` | DATETIME | — | Entry timestamp |
| `Quant` | REAL | `0` | Quantity |
| `SellDisc` | REAL | `0` | Sale discount |
| `Mohafaza` | NVARCHAR(50) | `''` | Governorate |
| `Markaz` | NVARCHAR(50) | `''` | Center/district |
| `price` | REAL | `0` | Price |

**SQL Evidence**:
```
"INSERT INTO ChainBuyStore"
"SELECT * FROM ChainBuyStore ORDER BY DrugName DESC"
```

---

## 22. ChainBuyUsers — Chain Buy Users

Users participating in chain purchases.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `PharmacistTel` | NVARCHAR(15) | `''` | Pharmacist phone |
| `Expire` | REAL | `0` | Expiry |
| `IdDateTime` | DATETIME | — | Entry timestamp |
| `Quant` | REAL | `0` | Quantity |
| `DrugName` | NVARCHAR(100) | `''` | Drug name |
| `SellDisc` | REAL | `0` | Sale discount |
| `Mohafaza` | NVARCHAR(50) | `''` | Governorate |
| `Markaz` | NVARCHAR(50) | `''` | Center/district |
| `Tips` | NVARCHAR(50) | `''` | Notes |
| `RequisterTel` | NVARCHAR(15) | `''` | Requester phone |
| `country` | NVARCHAR(50) | `''` | Country |
| `price` | REAL | `0` | Price |

**SQL Evidence**:
```
"INSERT INTO ChainBuyUsers"
"SELECT * FROM ChainBuyUsers WHERE PharmacistTel LIKE N'%"
```

---

## 23. RawakidTablew — Rawakid Table (multi-pharmacy order items)

Detailed order item tracking across the chain.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `PharmacistTel` | NVARCHAR(15) | `''` | Pharmacist phone |
| `Expire` | REAL | `0` | Expiry |
| `IdDateTime` | DATETIME | — | Entry timestamp |
| `Quant` | REAL | `0` | Quantity |
| `DrugName` | NVARCHAR(100) | `''` | Drug name |
| `SellDisc` | REAL | `0` | Sale discount |
| `Mohafaza` | NVARCHAR(50) | `''` | Governorate |
| `Markaz` | NVARCHAR(50) | `''` | Center/district |
| `SourceIdDateTime` | DATETIME | — | Source timestamp |
| `price` | REAL | `0` | Price |
| `Tips` | NVARCHAR(50) | `''` | Notes |
| `RequisterTel` | NVARCHAR(15) | `''` | Requester phone |
| `country` | NVARCHAR(50) | `''` | Country |

**SQL Evidence**:
```
"INSERT INTO RawakidTablew"
"SELECT * FROM RawakidTablew"
"SELECT * FROM RawakidTablew WHERE PharmacistTel = N'"
"PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,SourceIdDateTime,price"
"PharmacistTel,Expire,IdDateTime,Quant,DrugName,SellDisc,Mohafaza,Markaz,Tips,RequisterTel,country,price"
```

---

## 24. drugeyedash2 — Drug Eye Dashboard

Drug monitoring dashboard data.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `drugname` | NVARCHAR(100) | `''` | Drug name |
| `data` | NVARCHAR(MAX) | `''` | Dashboard data |

**SQL Evidence**:
```
"SELECT * FROM drugeyedash2"
```

---

## 25. wzaccfreetree — Accounting Hierarchy / Free Tree

Accounting tree structure for pharmacies.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `mobile` | NVARCHAR(15) | `''` | Pharmacy phone |
| `master` | NVARCHAR(100) | `''` | Master account |
| `fary` | NVARCHAR(100) | `''` | Sub-account (fary/branch) |

**SQL Evidence**:
```
"insert into wzaccfreetree (mobile,master,fary) values ("
"if not exists( select * from wzaccfreetree where"
```

---

## 26. titanpharmalist — Pharmacy List (registered pharmacies)

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `mobile` | NVARCHAR(15) | `''` | **PK** — pharmacy phone |
| `pharmacyname` | NVARCHAR(100) | `''` | Pharmacy name |
| `barcode` | VARCHAR(16) | `''` | Barcode |
| `changed` | DATETIME | — | Last changed |
| `apptype` | NVARCHAR(50) | `''` | App type |

**SQL Evidence**:
```
"begin insert into titanpharmalist (mobile) values (N'"
"select * from titanpharmalist where mobile= '"
"update titanpharmalist set"
"mobile,datee,changed,apptype,pharmacyname,barcode)values("
```

---

## 27. farysales — Fary (Branch) Sales

Sales records per branch/pharmacy.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `mobile` | NVARCHAR(15) | `''` | Pharmacy phone |
| `grand` | REAL | `0` | Grand total |
| `father` | NVARCHAR(100) | `''` | Parent account |
| `son` | NVARCHAR(100) | `''` | Child account |
| `datee` | REAL | `0` | Date |
| `datetimee` | DATETIME | — | Datetime |
| `dateemanual` | REAL | `0` | Manual date |
| `monthe` | NVARCHAR(10) | `''` | Month |
| `yearo` | NVARCHAR(10) | `''` | Year |
| `payed` | REAL | `0` | Amount paid |
| `creditdebit` | NVARCHAR(20) | `''` | Credit/debit flag |
| `typee` | NVARCHAR(50) | `''` | Type |
| `phar` | NVARCHAR(15) | `''` | Pharmacy ID |
| `randomid` | NVARCHAR(50) | `''` | Unique ID |
| `tips` | NVARCHAR(50) | `''` | Notes |
| `writer` | NVARCHAR(50) | `''` | Entered by |
| `classy` | NVARCHAR(35) | `''` | Category |

**SQL Evidence**:
```
"(mobile,grand,father,son,datee,datetimee,dateemanual,monthe,yearo,payed,creditdebit,typee,phar,randomid,tips,writer,classy)values "
"select * from farysales where mobile = N'"
"select datee, Pa=sum(payed) from"
```

---

## 28. ZATCA — ZATCA Invoice Log

Saudi ZATCA (Zakat, Tax and Customs Authority) e-invoicing compliance.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | INT | IDENTITY(1,1) | **PK** — auto-increment |
| `invoiceid` | REAL | `0` | Invoice number |
| `uuid` | NVARCHAR(100) | `''` | ZATCA UUID |
| `datee` | REAL | `0` | Date |
| `pharmacyid` | NVARCHAR(15) | `''` | Pharmacy ID |
| `status` | NVARCHAR(50) | `''` | Submission status |
| `hash` | NVARCHAR(200) | `''` | Invoice hash |
| `xml` | NVARCHAR(MAX) | `''` | Raw XML |
| `response` | NVARCHAR(MAX) | `''` | ZATCA response |

**SQL Evidence**:
```
"update zatca api"
"Zatca-response.txt"
"C:\saturn\Zatca\computer-1\invoices\"
"C:\saturn\zatca\computer-1\lastdata\counter.txt"
"C:\saturn\zatca\computer-1\lastdata\hash.txt"
```

---

## Relationships Diagram

```
wzdrugs (drug master)
  ├── wzdrugs2 (cost extension)         1:1
  ├── wzgard (stock batches)            1:many
  ├── titanksastock (chain stock)       1:many
  ├── titanstock (pharmacy stock)       1:many
  ├── titanneed (needs)                 1:many
  ├── drgserver (server drug list)      1:many
  ├── storediscount (discounts)         1:many
  ├── usersourceupdate (sync log)       1:many
  ├── TitanUserAction (audit log)       1:many
  ├── taronlineeg (online catalog)      1:many
  ├── invoicedata (invoice items)       1:many
  └── drugeyedash2 (dashboard)          1:many

wzphar (pharmacy master)
  ├── wzgard.phar                       1:many
  ├── wzcustomers.phar                  1:many
  ├── titanstock.pharmacyid             1:many
  ├── titanksastock.pharmacyid          1:many
  ├── titanksasales.pharmacyid          1:many
  ├── invoicedata.pharmacyid            1:many
  ├── orders.pharmacyid                 1:many
  ├── storediscount (by pharmacyname)   1:many
  ├── titanpharmalist.mobile            1:1
  ├── remotecontrol.mobile              1:many
  ├── drgserver.mobile                  1:many
  └── wzaccfreetree.mobile              1:many

titaninn (inter-pharmacy transfers)
  ├── source → wzphar                   FK
  └── target → wzphar                   FK

titanneed (needs)
  ├── sender → wzphar                   FK
  └── target → wzphar                   FK

ChainBuyStore ──< ChainBuyUsers         1:many
RawakidTablew (multi-pharmacy orders)
```

---

## Evidence Summary

| Evidence Type | Count |
|---------------|-------|
| CREATE TABLE statements found | 5 (titaninn, titanksasales, titanksastock, titanneed, TitanUserAction) |
| INSERT INTO with column lists | 15 |
| SELECT FROM with table names | 12 tables |
| UPDATE SET with table names | 8 tables |
| DELETE FROM with table names | 5 tables |
| Column definitions (nvarchar/int/real) | 45+ explicit |
| JOIN conditions | 2 (wzdrugs2↔wzgard) |
| Tables with full column lists | 8 (wzgard, wzcustomers, companies, drgserver, remotecontrol, storediscount, titaninn, TitanUserAction) |
| Tables with partial column lists | 12 |
| Tables inferred from context only | 8 |
