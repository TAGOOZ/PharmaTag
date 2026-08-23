# ADR-0002: S4.1 e-invoice foundations — regime routing, toolkit-faithful QR/UUID, per-device chain

Date: 2026-08-23 · Status: Accepted · Informs: #28 (S4.1), enables #29/#30 · Research: ETA SDK (sdk.invoicing.eta.gov.eg, last update 08-12-2022) re-verified online 2026-08-23

## Context

S4.1 must give every sales invoice a tax-document record with a QR and an
atomic counter/hash chain (A15/A09/G07, plan/02 §6). Open questions the
ticket left unpinned: which ETA regime applies per sale, what the QR
contains, what exactly chains, how offline fits the legal window, and the
template scope.

## Decisions

1. **Regime routing is per document, dual-track.** Retail/walk-in and
   customer sales → **eReceipt v1.2** (JSON-only, B2C; mandated for taxpayers
   under MoF Decision 281/2025 since 15 Sep 2025). Credit sales whose party
   carries a tax registration number → **B2B eInvoice v1.0** (`i`). Returns →
   receipt `receiptType 'r'` (retail) or **credit note `C`** (B2B; references
   the original, never exceeds it). Deferred-payment (أجل) is a payment term,
   not a document type. Legacy templates map: ضريبية→I · مبسطة→receipt ·
   أجل→its sale's type · مرتجع→C/r.
2. **QR/UUID replicate ETA's official toolkit, never invented formats.**
   Egypt is NOT ZATCA-TLV. The SDK's Integration Toolkit derives the receipt
   UUID as SHA-256 over the canonical base structure **+ previousUUID** and
   builds the QR from receipt key fields linking to the consumer verification
   page. `app/einvoicing/toolkit.py` reimplements both in pure Python,
   contract-tested with golden fixtures produced by the official toolkit on
   preprod.
3. **The chain is per POS device.** previousUUID references "the previously
   issued receipt from the same POS device". `einvoice_counters` keys on
   `(branch_id, kind)` and carries a nullable `device_serial` (v1 is single-
   drawer per branch, P1) so S5.1 multi-device needs no migration. Counters
   stay monotonic, gapless, never reset in fiscal year (A15).
4. **Offline = the 24-hour window.** ETA accepts receipts up to 24h after
   issuance, so G12 outbox atomicity (log row + counter bump + audit inside
   the invoice transaction, STRICT per A09) plus the status chain
   pending→submitted→accepted|rejected|failed IS the compliant offline story.
   Both tables mirror to the SQLite twin.
5. **S4.1 ships print templates only** (ضريبية/مبسطة/أجل/مرتجع via the
   print_html pattern, QR embedded as data-URI). Submission JSON generation
   is S4.2/S4.3 work reading `einvoice_log.payload_json`.

## Consequences

- `einvoice_log` gains `uuid`, `previous_uuid`, `device_serial`, `qr_data`,
  and `kind` values distinguishing receipt vs B2B invoice; `einvoice_counters`
  gains `device_serial`.
- Golden-fixture tests require running the official toolkit once (preprod)
  to pin expected UUID/QR outputs; the fixtures then guard every refactor.
- Tax-code mapping (T1–T20 + subtypes V001 etc.) becomes a tested table in
  S4.2 — wrong tax codes are ETA's #1 rejection reason.
- The receipt `contractor` structure (insurer pays part) is the future
  insurance seam (#48) — payload keeps the field even when null.

## Alternatives considered

- **ZATCA-style TLV QR** — rejected: wrong jurisdiction; the corpus's
  "summer" JSON shapes were Saudi dead ends (plan/02 §6).
- **Branch-only chain keyed without device** — rejected: breaks the moment a
  second POS registers (S5.1); the migration would be painful mid-flight.
- **Real-time-only submission** — rejected: violates the offline-first G12
  posture and is unnecessary given the 24h window.
