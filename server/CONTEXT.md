# Core context — domain glossary (server/)

The backend implementation of the Core context lives in `server/` (the
monorepo paths in `CONTEXT-MAP.md` are scaffold plans). This glossary holds
the accounting/reporting terms as locked in `plan/00_decisions_master.md`
and `docs/adr/`.

## Accounting

**Account / الحساب**
A node in the branch chart of accounts (`accounts`, code like `1000`).
Codes are stable per-branch handles; ids are not. Seeded: 1000 drawer,
1100 AR, 1200 stock, 2000 AP, 2100 VAT, 4000 sales, 6000 COGS, 5900
corrections.

**Trial balance / ميزان المراجعة**
Every account's opening/period/closing debit and credit for a period;
column pairs must balance. Aggregate only — no movements.

**Ledger by account / دفتر الأستاذ لحساب**
Chronological journal-line ledger for ONE account over a period: opening
balance → movements with running balance → closing. AR/AP rows carry the
contra party (طرف) when one is tagged. Distinct from an Account Statement.

**Account statement / كشف حساب**
A PARTY-scoped ledger on the party's AR or AP side (their pinned accounts
unioned). Answers "what does this customer/supplier owe and why". The
ledger by account answers "what moved through this ACCOUNT".

## VAT

**Output tax / ضريبة المخرجات**
VAT collected on sales; derived from journal legs whose source is
`sale` (returns offset it). Not a separate GL account — see ADR-0001.

**Input tax / ضريبة المدخلات**
VAT paid on purchases; derived from `purchase`-source legs (purchase
returns offset). Deductibility against exempt output is the accountant's
apportionment call — the system presents figures, it does not apportion.

**Net VAT payable / صافي الضريبة المستحقة**
Output tax − input tax for the period. Positive = owed to ETA; negative =
credit carried forward. Mirrors Form 10 (نموذج 10 ق.ض.ق.م), filed monthly.

**Tax type / نوع الضريبة**
Per-invoice-line treatment: `exempt` (medicines, 0%), `5%` (medical
devices), `14%` (standard/cosmetics). Lives on the line, not the invoice,
not the chart.
