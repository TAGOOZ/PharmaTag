# DrugEye Data Legal/Licensing Analysis

## TL;DR — CAN WE USE DRUGEYE DATA IN OUR OWN APP?

**SHORT ANSWER: We don't know for certain, and the signs are NOT favorable.**

DrugEye is described as **"Proprietary" (freeware)** across multiple distribution sites. The app is free to *use*, but there is **no publicly visible Terms of Service, license agreement, or API documentation** that grants any right to *redistribute* or *integrate* the data into a third-party application. Using DrugEye data in our own app without explicit permission would be **legally risky**.

---

## Step 1: DrugEye Terms of Service

### What We Searched
- `drugeye.pharorg.com` — **Transport error** (site unreachable or returns 403)
- `pharorg.com/drugeye/` — Marketing page only, no ToS/license/privacy policy
- Google Play listing (`com.phycod.drugeye`) — No EULA or license linked
- APKPure, Uptodown, Phoneky listings — All describe it as "Proprietary"
- Searched TITAN decompiled strings for: terms, license, copyright, agreement, privacy, policy, intellectual property

### What We Found

| Source | Finding |
|--------|---------|
| Uptodown | **"License: Proprietary"** — Copyright © 2026 phycod.systems |
| Phoneky | **"许可: 专有（免费软件）"** = "License: Proprietary (Freeware)" — "All copyright, trademark, and intellectual property belong to their respective developers" |
| Soft112 | "License Type: Free" — no further terms |
| Google Play | No EULA, no privacy policy linked (developer email: dr.saleh.mansour@gmail.com) |
| pharorg.com/drugeye/ | Marketing page only — "free and small-size", "enjoy all features without paying fees" — no legal terms |
| drugeye.pharorg.com | **Unreachable** — returns transport error |

### What We Did NOT Find
- ❌ No Terms of Service page
- ❌ No End User License Agreement (EULA)
- ❌ No Privacy Policy (Google Play listing references one but it's not linked)
- ❌ No API Terms of Use
- ❌ No developer/partner program documentation

### Conclusion
**The absence of any public ToS is itself a red flag.** It means:
1. There are no terms granting you permission to use the data
2. Default copyright law applies: all rights reserved by Pharorg
3. "Free to use the app" ≠ "free to use the data"

---

## Step 2: API Availability

### What Exists
| Endpoint | Purpose |
|----------|---------|
| `drugeye.pharorg.com/rsd-api/start.aspx` | **NOT a drug database API** — this is an RSD (Saudi Drug Track and Trace) integration proxy |
| `drugeye.pharorg.com/drugeyeapp/android-search/drugeye-android-live-go.aspx` | Web-based drug search (returns HTML, not structured data) |
| `db_9ffe55_apifordrugeye` | MySQL backend database name (found in TITAN strings) |
| `db_9ffe55_apifordrugeye_admin` | Admin access to the same database |

### What Does NOT Exist
- ❌ No public REST API for drug data
- ❌ No API documentation
- ❌ No API key system (beyond TITAN's internal integration)
- ❌ No developer portal or partner program
- ❌ No rate limits or usage terms (because there's no API)

### TITAN Integration (Internal Only)
TITAN has special integration with DrugEye because they share the same developer (Pharorg/Phycod):
- Downloads `drugeye.update.titan.rar` from `phycodsystems-001-site12.htempurl.com` — **⚠️ VERIFIED 2026-08-15: the file is NOT a RAR (it is a ROT-4-obfuscated text feed of 23,452 drug records), and this download path is dead code in the analyzed build (0 p-code refs); the live integration is a `drugeye.pharorg.com` web service + native `.phy` record I/O (drugeye_complete.md §7A, §9)**
- Reads `drugeye-for-titan.phy` (proprietary binary format)
- Has a dedicated `ModDrugEye` module with 8 procedures
- Has a dedicated `FFFDrugEye` form with 22 procedures

**This integration is NOT a public API — it's a proprietary integration built by the same company for its own product.**

### Conclusion
**There is no public API to access DrugEye data.** The only data access mechanism is:
1. The Android app (for end users)
2. The Windows desktop app (for end users)
3. The web search page (HTML only)
4. TITAN's proprietary integration (internal, same developer)

---

## Step 3: Data Format

### The .phy Format
- **Proprietary binary format** (PHYCOD Programming Language)
- Created by TITAN/Phye system: `created by titan www.pharorg.com/phye`
- Cannot be read without the PHYCOD runtime
- No public documentation for the format

### Can You Use It Without Permission?
**No.** The `.phy` format is:
1. Proprietary to Pharorg/Phycod
2. Requires their runtime to read
3. Not documented anywhere publicly
4. Subject to their intellectual property rights

### Is the Data Freely Redistributable?
**No evidence suggests it is.** The data appears to be:
1. Collected/maintained by Pharorg (a private company)
2. Provided through their proprietary apps
3. Marked as "Proprietary" on distribution sites
4. Not under any open license

---

## Step 4: Data Ownership

### Who Owns the Data?

| Candidate | Evidence |
|-----------|----------|
| **Pharorg (شركة التجمع الصيدلي للادوية)** | Most likely owner — they built the app, maintain the database, and distribute it |
| Egyptian Drug Authority (EDA) | Source of *some* data (registration info), but not the *curated dataset* |
| Egyptian Government | Drug registration data may be public, but the *compilation* is Pharorg's |
| Community/Users | No evidence of user-contributed data |

### What We Know
- Pharorg is an Egyptian joint stock company (شركة مساهمة مصرية)
- Founded by the Egyptian Pharmaceutical Union (التجمع الصيدلي المصري)
- They describe DrugEye as their product: "الإصدار الأحدث من إنتاج التجمع الصيدلي المصري"
- The database includes "all drugs registered in Egypt" — this is their curation of public + proprietary data
- Drug prices, barcodes, and company info may be public, but the *compilation and presentation* is Pharorg's work

### Copyright Law
Under Egyptian copyright law (and most international copyright law):
- **Facts are not copyrightable** (individual drug names, prices)
- **Compilations of facts ARE copyrightable** if there's original selection/arrangement
- **Database rights** may apply (though Egypt doesn't have EU-style sui generis database rights)
- Pharorg's compilation likely has copyright protection

### Conclusion
**Pharorg almost certainly owns the copyright to the DrugEye database compilation.** Even if individual facts (drug names, prices) are public, the specific arrangement, selection, and presentation are protected.

---

## Step 5: Business Model Analysis

### What "Free" Means

| Interpretation | Evidence |
|----------------|----------|
| Free to VIEW | ✅ Yes — the app is free to download and use |
| Free to REDISTRIBUTE | ❌ No evidence — no license grants this right |
| Free to INTEGRATE | ❌ No evidence — no API or developer program |
| Free to RESELL | ❌ Definitely not — no license, proprietary software |

### Revenue Strategy
DrugEye is a **loss leader** for the TITAN ecosystem:
1. **DrugEye is free** → drives adoption of TITAN
2. **TITAN is paid** → pharmacy management system (paid product)
3. **Pharorg manufactures drugs** → the parent company produces pharmaceuticals
4. **Investment opportunity** → shares available at 200 EGP each
5. **Pharmacy chain** → "سلسلة صيدليات التجمع" (Union Pharmacy Chain)

### Key Insight
DrugEye exists to promote TITAN and the Pharorg ecosystem. It is NOT a public good or open data project. The "free" label refers to end-user access, not data licensing.

---

## Step 6: Alternatives

### ✅ GOOD NEWS: There ARE alternatives for Egyptian drug data

#### 1. Egyptian Drug Authority (EDA) — EDDB
- **URL**: http://eservices.edaegypt.gov.eg/EDASearch/SearchRegDrugs.aspx
- **What**: Official Egyptian Drug Database with ALL registered pharmaceuticals
- **Data**: Trade name, registration number, generic name, applicant, dosage, shelf life, route, strength
- **License**: Government public database — likely public domain (government works)
- **Limitations**: No prices, no barcodes, web-only search (no API)
- **PDF Guide**: https://www.edaegypt.gov.eg/media/ajqiccqc/np-ppma-18-mechanism-of-egyptian-drug-database-eddb-searching-tool.pdf

#### 2. CC0 Egyptian Drug Database (GitHub)
- **URL**: https://github.com/karem505/egyptian-drug-database
- **What**: 25,070 medicines with Arabic + English names, scientific composition, manufacturer, drug class, route, price
- **License**: **CC0-1.0 (Public Domain)** — copy, modify, redistribute freely
- **Formats**: CSV + JSON
- **Last Updated**: June 2026
- **Best option for**: Any use case — no restrictions

#### 3. FDA-Enriched Egyptian Drug Database (GitHub)
- **URL**: https://github.com/mahmoudfalous/eg-drugs
- **What**: 26,562 drugs with FDA mapping, Arabic/English info, prices, barcodes, safety warnings
- **License**: Personal, educational, research, non-commercial. **Commercial use requires permission**
- **Formats**: CSV + JSON
- **Last Updated**: June 2026
- **Best option for**: Non-commercial apps, research, education

#### 4. SafeRx API (Egyptian)
- **URL**: https://docs.saferx.online
- **What**: Drug safety API — 66,704 products, 7 safety domains
- **License**: API key required, free tier (100 checks/month), paid tiers available
- **Best option for**: Drug safety checking, clinical decision support

### Saudi Arabia Alternatives

#### 5. SFDA Open Data
- **URL**: https://betasfda.sfda.gov.sa/en/open-data
- **What**: Saudi Food and Drug Authority official open data
- **License**: Open data — "can be used freely by any individual without technical, financial, or legal restrictions"
- **Formats**: Various formats available

#### 6. SFDA Developer API
- **URL**: https://developer.sfda.gov.sa
- **What**: Registered Drug Service API — search by barcode, registration number, keyword
- **License**: Free registration, OAuth authentication
- **Documentation**: https://developer.sfda.gov.sa/apidoc/registered-drug-service/84

### International Alternatives

#### 7. DrugBank
- **URL**: https://go.drugbank.com
- **License**: Free for academic/non-commercial, **commercial license required**
- **Note**: Not Egypt-specific but has some Egyptian drugs

#### 8. Elsevier Drug Information API
- **URL**: https://druginfo.elsevier.com
- **License**: Commercial license required
- **Note**: Gold Standard Drug Database

---

## Step 7: What Other Apps Do

### Do Other Apps Use DrugEye?
Based on our analysis, **no other apps appear to use DrugEye data**:
- DrugEye is a direct competitor to other pharmacy apps
- There's no public API to enable integration
- The proprietary `.phy` format prevents external use
- No developer documentation exists

### What Other Pharmacy Apps in Egypt/Saudi Do Instead
1. **Use EDA/EDDB** — the official government database
2. **Use SFDA open data** — for Saudi market
3. **Build their own databases** — from public sources
4. **Use CC0/open-source datasets** — like the GitHub repositories above
5. **License commercial databases** — like DrugBank or Elsevier

---

## Final Verdict

### CAN WE USE DRUGEYE DATA?

| Question | Answer |
|----------|--------|
| Can we use the DrugEye app? | ✅ Yes — it's free |
| Can we scrape DrugEye data? | ❌ No — likely violates ToS (even if not written) |
| Can we use the .phy files? | ❌ No — proprietary format, no license |
| Can we use DrugEye data in our app? | ❌ **No** — no license grants this right |
| Can we call the DrugEye API? | ❌ No public API exists |

### RECOMMENDED ACTION

1. **DO NOT use DrugEye data** in your app without explicit written permission from Pharorg
2. **Contact Pharorg** at 01062700020 or dr.saleh.mansour@gmail.com to request data licensing
3. **Use alternatives instead**:
   - **For Egyptian drugs**: Use the CC0-licensed dataset from `github.com/karem505/egyptian-drug-database`
   - **For Saudi drugs**: Use SFDA's open data/API at `developer.sfda.gov.sa`
   - **For drug safety**: Use SafeRx API at `saferx.online`
   - **For registration data**: Use EDA's official database at `edaegypt.gov.eg`

### Risk Assessment

| Risk | Likelihood | Impact |
|------|------------|--------|
| Pharorg sends cease & desist | HIGH | App takedown |
| Pharorg sues for copyright infringement | MEDIUM | Financial damages |
| Google Play removes app | MEDIUM | Loss of distribution |
| Reputational damage | HIGH | Loss of user trust |

---

## What We Don't Know (Honest Gaps)

1. **Pharorg's actual licensing terms** — they may have terms we can't find
2. **Whether EDA data is truly public domain** — we assume but haven't confirmed
3. **Whether drug prices are copyrightable** — legal gray area
4. **Whether Pharorg would actually enforce** — some companies don't
5. **Whether there's a hidden partner program** — we couldn't find one
6. **The exact source of DrugEye's data** — some may be from EDA, some proprietary

---

## Sources

- Google Play: https://play.google.com/store/apps/details?id=com.phycod.drugeye
- Uptodown: https://drug-eye-index.en.uptodown.com/android
- Phoneky: https://cn.phoneky.co/android/?id=d1d275946
- Pharorg: https://www.pharorg.com/drugeye/
- EDA: https://edaegypt.gov.eg/en/services/databases/
- CC0 Dataset: https://github.com/karem505/egyptian-drug-database
- FDA Dataset: https://github.com/mahmoudfalous/eg-drugs
- SFDA: https://developer.sfda.gov.sa
- SafeRx: https://saferx.online
- TITAN strings analysis: /tmp/titan_decompile/strings_utf16.txt
- TITAN disassembly: /tmp/titan_decompile/pcode_disasm.txt
- DrugEye analysis: titan_extract/drugeye_complete.md

---

*Analysis date: August 2026*
*Analyst: Automated investigation*
*Disclaimer: This is not legal advice. Consult a lawyer for legal decisions.*
