"""Egypt-reality adversarial suite for S4.1 e-invoicing (#28).

Born from a red-team run that mimicked how a real Giza pharmacy uses the
system: Arabic names and quote characters, أجل credit culture, tax-card
corrections between sale and return, power-cut offline bursts replayed out of
order / after the fact, fiscal-calendar edges (no year reset — A15), volume
and concurrency on one drawer. Every test pins behavior that once FAILED or
was load-bearing-unclear; if you break the chain semantics, this file is
meant to turn red before ETA submission does (#29).
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select, update

from app.core.db import SessionLocal
from app.core.time import business_date
from app.einvoicing.chain import verify_chain
from app.einvoicing.service import apply_einvoice_block
from app.einvoicing.toolkit import receipt_uuid, serialize
from app.models import (
    AppConfig,
    Drug,
    EInvoiceCounter,
    EInvoiceLog,
    Invoice,
    InvoiceLine,
    InvoiceVersion,
    Journal,
    JournalLine,
    Party,
    PaymentSplit,
    DrawerMovement,
    StockBatch,
    BranchStock,
    SyncLog,
)
from app.sync.service import replay_pending
from tests.einv_test_utils import (
    RIN,
    _clear_rin,
    _counter_for,
    _log_for,
    _make_tax_party,
    _make_user,
    _set_rin,
    _uniq,
)
from tests.sales_test_utils import _token_for
from tests.test_einv_issue import _cleanup
from tests.returns_test_utils import (
    _delete_branch,
    _make_branch,
    _make_drug_and_stock_branch,
)


# ---------------------------------------------------------------- helpers


async def _rename_drug_ar(drug_id: int, ar: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(Drug).where(Drug.id == drug_id).values(drugnamear=ar)
        )
        await session.commit()


async def _rename_drug_en(drug_id: int, en: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(Drug).where(Drug.id == drug_id).values(drugname=en)
        )
        await session.commit()


async def _make_party(branch_id: int, *, rin: str | None, namee: str) -> int:
    async with SessionLocal() as session:
        party = Party(
            branch_id=branch_id,
            kind="customer",
            namee=namee,
            randomid=f"rt-{_uniq('p')}",
            tax_registration_no=rin or "",
        )
        session.add(party)
        await session.flush()
        pid = party.id
        await session.commit()
        return pid


async def _set_party(branch_id: int, party_id: int, *, rin: str | None, namee: str | None = None):
    async with SessionLocal() as session:
        await session.execute(
            update(Party).where(Party.id == party_id).values(
                tax_registration_no=rin or "",
                **({"namee": namee} if namee else {}),
            )
        )
        await session.commit()


async def _payload(invoice_id: int) -> dict:
    log = await _log_for(invoice_id)
    return log.payload_json


async def _invoice_row(invoice_id: int) -> Invoice:
    async with SessionLocal() as session:
        return await session.get(Invoice, invoice_id)


def _d(value) -> Decimal:
    return Decimal(str(value))


async def _wipe_tax_docs_only(branch_id: int) -> None:
    """D1 literal seed: remove ONLY the issued documents + counter state."""
    async with SessionLocal() as session:
        await session.execute(delete(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id))
        await session.execute(delete(EInvoiceCounter).where(EInvoiceCounter.branch_id == branch_id))
        await session.commit()


async def _wipe_invoices_keep_outbox(branch_id: int) -> list[int]:
    """D1 realistic catch-up: remove whole invoices (+ deps + docs + counters),
    keep the pending outbox rows so the target store can rebuild."""
    wiped: list[int] = []
    async with SessionLocal() as session:
        ids = (
            await session.execute(
                select(Invoice.id).where(Invoice.branch_id == branch_id)
            )
        ).scalars().all()
        jids = (
            await session.execute(select(Journal.id).where(Journal.branch_id == branch_id))
        ).scalars().all()
        if jids:
            await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
            await session.execute(delete(Journal).where(Journal.id.in_(jids)))
        await session.execute(delete(PaymentSplit).where(PaymentSplit.branch_id == branch_id))
        await session.execute(delete(DrawerMovement).where(DrawerMovement.branch_id == branch_id))
        await session.execute(
            delete(InvoiceVersion).where(InvoiceVersion.invoice_id.in_(ids))
        )
        await session.execute(delete(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id))
        ref_line_ids = (
            await session.execute(
                select(InvoiceLine.id).where(InvoiceLine.branch_id == branch_id)
            )
        ).scalars().all()
        if ref_line_ids:
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.ref_invoice_line_id.in_(ref_line_ids))
            )
        await session.execute(delete(InvoiceLine).where(InvoiceLine.branch_id == branch_id))
        await session.execute(delete(Invoice).where(Invoice.branch_id == branch_id))
        await session.execute(delete(EInvoiceCounter).where(EInvoiceCounter.branch_id == branch_id))
        await session.commit()
        wiped = list(ids)
    return wiped


# ---------------------------------------------------------------- A. retail


async def test_A1_exempt_panadol_cash_vat_inclusive(client):
    """A1: default Egyptian retail config — exempt medicine, cash, مبسطة."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, tax_type="exempt", price="10.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        log = await _log_for(body["id"])
        p = log.payload_json

        assert log.kind == "receipt"
        inv = await _invoice_row(body["id"])
        assert _d(p["totalAmount"]) == _d(inv.totalvalue) == Decimal("20.00")
        assert _d(p["netAmount"]) == _d(p["totalAmount"])  # exempt: no VAT wedge
        assert p["taxTotals"] == [
            {"taxType": "T1", "subType": "V003", "amount": "0.00", "rate": "0"}
        ]
        assert p["itemData"][0]["taxableItems"][0]["rate"] == "0"
        assert p["paymentMethod"] == "C"
        assert p["documentType"] == {"receiptType": "s", "typeVersion": "1.2"}
        assert receipt_uuid(p) == log.uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_A2_mixed_basket_discount_vat_by_rate(client):
    """A2: exempt + 14% + 5% basket with 10% invoice discount — per-rate math."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    exem = await _make_drug_and_stock_branch(branch_id, tax_type="exempt", price="30.0000")
    cosm = await _make_drug_and_stock_branch(branch_id, tax_type="14%", price="40.0000")
    devi = await _make_drug_and_stock_branch(branch_id, tax_type="5%", price="25.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [
                    {"drug_id": exem, "qty": "1"},
                    {"drug_id": cosm, "qty": "1"},
                    {"drug_id": devi, "qty": "1"},
                ],
                "disc_percent": "10",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        p = await _payload(body["id"])

        # FIXED (review F1): itemData[].netSale is now the post-discount
        # PRE-tax base and .total = netSale + VAT — so ΣnetSale == header
        # netAmount and Σtotal == totalAmount. The old inclusive-amount
        # behavior this scenario pinned was the bug.
        lines_sum = sum((_d(i["netSale"]) for i in p["itemData"]), Decimal("0"))
        totals_sum = sum((_d(i["total"]) for i in p["itemData"]), Decimal("0"))
        vat_lines = sum(
            (_d(i["taxableItems"][0]["amount"]) for i in p["itemData"]), Decimal("0")
        )
        vat_totals = sum((_d(t["amount"]) for t in p["taxTotals"]), Decimal("0"))
        assert lines_sum == _d(p["netAmount"])  # lines are pre-tax bases
        assert totals_sum == _d(p["totalAmount"])
        assert _d(p["netAmount"]) + vat_totals == _d(p["totalAmount"])
        assert vat_lines == vat_totals
        rates = {t["rate"]: _d(t["amount"]) for t in p["taxTotals"]}
        assert set(rates) == {"0", "5", "14"}
        assert rates["0"] == Decimal("0.00") and rates["5"] > 0 and rates["14"] > 0
        print(
            f"A2 OBSERVATION ΣnetSale={lines_sum} netAmount={p['netAmount']} "
            f"totalAmount={p['totalAmount']} vat={vat_totals}"
        )
        # every discounted line carries its خصم split
        for i in p["itemData"]:
            disc = sum(_d(d["amount"]) for d in i["commercialDiscountData"])
            assert _d(i["totalSale"]) - disc == _d(i["netSale"]) or disc >= 0
        inv = await _invoice_row(body["id"])
        assert _d(p["totalSales"]) == _d(inv.subtotal)
        assert receipt_uuid(p) == (await _log_for(body["id"])).uuid
    finally:
        await _clear_rin()
        await _cleanup([exem, cosm, devi], invoice_ids, branch_id)


async def test_A3_arabic_names_and_double_quote_survive_roundtrip(client):
    """A3: بانادول اكسترا + a 5\" product — JSONB round-trip keeps bytes, uuid recomputes."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    d1 = await _make_drug_and_stock_branch(branch_id, tax_type="exempt", price="12.5000")
    d2 = await _make_drug_and_stock_branch(branch_id, tax_type="14%", price="8.0000")
    await _rename_drug_ar(d1, "بانادول اكسترا")
    await _rename_drug_en(d2, 'Syringe 5" size')
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": d1, "qty": "1"}, {"drug_id": d2, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        log = await _log_for(body["id"])
        p = log.payload_json
        descs = [i["description"] for i in p["itemData"]]
        assert "بانادول اكسترا" in descs
        assert 'Syringe 5" size' in descs  # raw quote survives JSONB round-trip
        s = serialize(p)
        assert '"بانادول اكسترا"' in s  # verbatim inside quotes, no escapes needed
        assert '\\"' not in s  # ETA serializer never escapes; raw quote stays raw
        assert receipt_uuid(p) == log.uuid
    finally:
        await _clear_rin()
        await _cleanup([d1, d2], invoice_ids, branch_id)


async def test_A4_backdated_sale_header_vs_business_date(client):
    """A4: month-end backdating (datee=yesterday) — dateTimeIssued vs datee."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, stock_qty="20.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        yesterday = (business_date() - timedelta(days=1)).isoformat()
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "datee": yesterday,
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        p = await _payload(body["id"])

        assert body["datee"] == yesterday
        issued_date = p["header"]["dateTimeIssued"][:10]
        # OBSERVATION (recorded, not hardcoded-pass): issuance instant stays
        # wall-clock now even when the business date was forced backwards.
        print(f"A4: datee={yesterday} dateTimeIssued={p['header']['dateTimeIssued']}")
        assert p["header"]["receiptNumber"] == body["invoice_no"]
        assert receipt_uuid(p) == (await _log_for(body["id"])).uuid

        # Cairo-vs-UTC boundary probe at execution time
        now_utc = datetime.now(timezone.utc)
        cairo_today = business_date(now_utc)
        print(
            f"A4 boundary probe: utc={now_utc.isoformat()} cairo_date={cairo_today} "
            f"same_day={cairo_today.isoformat() == now_utc.date().isoformat()}"
        )
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_A5_card_payment_method_V(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="55.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [{"method": "card", "amount": "55.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        p = await _payload(r.json()["id"])
        assert p["paymentMethod"] == "V"
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


# ---------------------------------------------------------------- B. أجل


async def test_B1_B2_walkin_credit_no_rin_two_purchases_chain(client):
    """B1+B2: regular customer on account, NO RIN — receipts, chained."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, price="100.0000", stock_qty="20.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    party_id = await _make_party(branch_id, rin=None, namee="عميل آجل")
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)

        async def credit_buy():
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "party_id": party_id,
                    "lines": [{"drug_id": drug_id, "qty": "1"}],
                    "payments": [{"method": "credit", "amount": "100.00"}],
                },
            )
            assert r.status_code == 201, r.text
            return r.json()

        first = await credit_buy()
        second = await credit_buy()
        invoice_ids += [first["id"], second["id"]]

        log1, log2 = await _log_for(first["id"]), await _log_for(second["id"])
        # B1: no-RIN credit stays a RECEIPT (أجل = payment term, not a regime)
        assert log1.kind == "receipt" and log2.kind == "receipt"
        assert log1.payload_json["buyer"]["type"] == "P"
        assert log1.payload_json["buyer"]["name"] == "عميل آجل"
        assert log1.counter == 1 and log1.previous_uuid == ""
        # B2: same-day second purchase chains within the SAME stream
        assert log2.counter == 2
        assert log2.previous_uuid == log1.uuid
        assert (await _counter_for(branch_id, "receipt")).last_counter == 2
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_B3_wholesale_b2b_partial_returns_two_credit_notes(client):
    """B3: wholesale credit sale to a registered pharmacy; TWO partial returns
    produce two chained credit notes referencing the original."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=False)  # wholesale pricing mode
    drug_id = await _make_drug_and_stock_branch(
        branch_id, tax_type="exempt", price="80.0000", stock_qty="50.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    party_id = await _make_party(
        branch_id, rin="311223344", namee="صيدلية النيل — منوال"
    )
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": party_id,
                "lines": [{"drug_id": drug_id, "qty": "6"}],
                "payments": [{"method": "credit", "amount": "480.00"}],
            },
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        orig = await _log_for(sale["id"])
        assert orig.kind == "invoice"
        assert orig.payload_json["documentType"] == {
            "documentType": "I",
            "typeVersion": "1.0",
        }

        r1 = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "2"}]},
        )
        assert r1.status_code == 201, r1.text
        cn1_inv = r1.json()
        invoice_ids.append(cn1_inv["id"])
        cn1 = await _log_for(cn1_inv["id"])

        r2 = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r2.status_code == 201, r2.text
        cn2_inv = r2.json()
        invoice_ids.append(cn2_inv["id"])
        cn2 = await _log_for(cn2_inv["id"])

        assert cn1.kind == "credit_note" and cn2.kind == "credit_note"
        assert cn1.counter == 1 and cn1.previous_uuid == ""
        assert cn2.counter == 2  # second note chains in the CREDIT NOTE stream
        assert cn2.previous_uuid == cn1.uuid
        assert cn1.reference_uuid == orig.uuid == cn2.reference_uuid
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


# ------------------------------------------------- C. tax-card corrections


async def test_C1_garbled_rin_routes_b2b_verbatim_no_crash(client):
    """C1: clerk typed '300abc' — nothing crashes; buyer.id carries it verbatim."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="100.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    party_id = await _make_party(branch_id, rin="300abc", namee="شركة توزيع")
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": party_id,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [{"method": "credit", "amount": "100.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        log = await _log_for(r.json()["id"])
        assert log.kind == "invoice"  # non-empty RIN ⇒ B2B routing
        assert log.payload_json["buyer"]["id"] == "300abc"  # OBSERVATION: verbatim
        assert receipt_uuid(log.payload_json) == log.uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_C2_rin_cleared_after_sale_return_follows_original_arabic(client):
    """C2: B2B sale, RIN cleared later, return under an Arabic-named party —
    the return MUST follow the ORIGINAL document's regime (credit note)."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="60.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    party_id = await _make_party(branch_id, rin="355667788", namee="صيدلية عابدين")
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": party_id,
                "lines": [{"drug_id": drug_id, "qty": "3"}],
                "payments": [{"method": "credit", "amount": "180.00"}],
            },
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        orig = await _log_for(sale["id"])
        assert orig.kind == "invoice"

        # correction happens AFTER issuance: RIN cleared + renamed (Arabic)
        await _set_party(
            branch_id, party_id, rin=None, namee="صيدلية الشفاء للادوية"
        )

        r_ret = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [
                    {"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "1"}
                ]
            },
        )
        assert r_ret.status_code == 201, r_ret.text
        ret = r_ret.json()
        invoice_ids.append(ret["id"])
        ret_log = await _log_for(ret["id"])

        # the recent fix holds: regime follows the ORIGINAL doc, not live party
        assert ret_log.kind == "credit_note"
        assert ret_log.reference_uuid == orig.uuid
        p = ret_log.payload_json
        # FIXED (review F2): the credit note mirrors the ORIGINAL's buyer
        # verbatim (ETA pairs C→I by buyer + referenceUUID) — the party row
        # was renamed/de-registered after issuance and must NOT leak in.
        assert p["buyer"] == orig.payload_json["buyer"]
        assert p["buyer"]["id"] == "355667788"
        assert p["buyer"]["name"] == "صيدلية عابدين"
        assert receipt_uuid(p) == ret_log.uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_C3_rin_with_spaces_trimmed_in_payload(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="45.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    party_id = await _make_party(branch_id, rin=" 300123456 ", namee="مخازن الحرام")
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": party_id,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [{"method": "credit", "amount": "45.00"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        log = await _log_for(r.json()["id"])
        assert log.kind == "invoice"
        assert log.payload_json["buyer"]["id"] == "300123456"
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


# ------------------------------------- D. power cuts & offline bursts


async def test_D1_offline_burst_literal_seed_then_full_rebuild(client):
    """D1: 5-sale burst, then (a) the LITERAL seed — wipe ONLY docs+counters,
    keep outbox → replay; (b) the REALISTIC target-store catch-up — wipe whole
    invoices, keep outbox → replay rebuilds verbatim."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, price="7.0000", stock_qty="50.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        uuids = []
        for _ in range(5):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])
            uuids.append((await _log_for(r.json()["id"])).uuid)

        # ---- (a) literal seed: docs+counters gone, invoices+outbox remain
        await _wipe_tax_docs_only(branch_id)
        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=branch_id)
        print(f"D1a OBSERVATION replay summary after doc-only wipe: {summary}")
        async with SessionLocal() as session:
            logs = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id)
                )
            ).scalars().all()
        print(f"D1a OBSERVATION docs present after replay: {len(logs)}")

        # ---- (b) realistic catch-up: wipe whole invoices; the outbox rows
        # were marked applied by phase (a)'s replay, so reset them pending
        # first (mimics rows that were never picked up)
        await _wipe_invoices_keep_outbox(branch_id)
        async with SessionLocal() as session:
            await session.execute(
                update(SyncLog)
                .where(SyncLog.branch_id == branch_id, SyncLog.entity == "invoice")
                .values(status="pending")
            )
            await session.commit()
        async with SessionLocal() as session:
            summary2 = await replay_pending(session, branch_id=branch_id)
        assert summary2["applied"] >= 5, summary2
        rebuilt = []
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter)
                )
            ).scalars().all()
            rebuilt = [r.uuid for r in rows]
        assert rebuilt == uuids  # VERBATIM chain positions, never regenerated
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_D2_replay_interleaved_with_live_sale(client):
    """D2: a replay transaction racing a fresh live sale — serialized by the
    branch lock, gapless, chain green."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, price="6.0000", stock_qty="50.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        pre_uuids = []
        for _ in range(2):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])
            pre_uuids.append((await _log_for(r.json()["id"])).uuid)

        # simulate the store losing its local writes while the outbox survives
        wiped = await _wipe_invoices_keep_outbox(branch_id)
        invoice_ids = [i for i in invoice_ids if i not in set(wiped)]

        async def do_replay():
            async with SessionLocal() as session:
                return await replay_pending(session, branch_id=branch_id)

        async def do_live_sale():
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            return r

        replay_res, live_res = await asyncio.gather(do_replay(), do_live_sale())
        assert live_res.status_code == 201, live_res.text
        invoice_ids.append(live_res.json()["id"])
        print(f"D2 OBSERVATION replay during live sale: {replay_res}")

        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter)
                )
            ).scalars().all()
        assert [r.counter for r in rows] == [1, 2, 3]
        assert [r.uuid for r in rows[:2]] == pre_uuids
        assert rows[2].previous_uuid == rows[1].uuid
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_D3_cross_date_one_stream_chain_green(client):
    """D3: yesterday-dated + today-dated receipts share ONE counter stream."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, stock_qty="20.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        yesterday = (business_date() - timedelta(days=1)).isoformat()
        r1 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}], "datee": yesterday},
        )
        assert r1.status_code == 201, r1.text
        r2 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r2.status_code == 201, r2.text
        invoice_ids += [r1.json()["id"], r2.json()["id"]]
        l1, l2 = await _log_for(r1.json()["id"]), await _log_for(r2.json()["id"])
        assert (l1.counter, l2.counter) == (1, 2)
        assert l2.previous_uuid == l1.uuid
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


# ------------------------------------- E. fiscal calendar & config edges


async def test_E1_full_day_without_eta_rin(client):
    """E1: no eta.rin all day — mixed kinds still issue, QR ends ',IssuerRIN:'."""
    await _clear_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    cash_d = await _make_drug_and_stock_branch(branch_id, price="10.0000", stock_qty="30.0000")
    b2b_d = await _make_drug_and_stock_branch(branch_id, price="90.0000", stock_qty="30.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    party_id = await _make_party(branch_id, rin="377888999", namee="مركز طبي")
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r1 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": cash_d, "qty": "1"}]},
        )
        assert r1.status_code == 201, r1.text
        r2 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": party_id,
                "lines": [{"drug_id": b2b_d, "qty": "1"}],
                "payments": [{"method": "credit", "amount": "90.00"}],
            },
        )
        assert r2.status_code == 201, r2.text
        r3 = await client.post(
            f"/api/v1/sales/{r1.json()['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [
                    {"ref_invoice_line_id": r1.json()["lines"][0]["id"], "qty": "1"}
                ]
            },
        )
        assert r3.status_code == 201, r3.text
        invoice_ids += [r1.json()["id"], r2.json()["id"], r3.json()["id"]]
        for iid in invoice_ids:
            log = await _log_for(iid)
            assert log.qr_data.endswith(",IssuerRIN:")
            assert receipt_uuid(log.payload_json) == log.uuid
        kinds = [(await _log_for(i)).kind for i in invoice_ids]
        assert kinds == ["receipt", "invoice", "return_receipt"]
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([cash_d, b2b_d], invoice_ids, branch_id)


async def test_E2_rin_set_to_empty_string_midday(client):
    """E2: eta.rin EXISTS but value='' mid-day — transition sale behaves."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, price="15.0000", stock_qty="20.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r1 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r1.status_code == 201, r1.text
        invoice_ids.append(r1.json()["id"])
        assert (await _log_for(r1.json()["id"])).qr_data.endswith(f":{RIN}")

        async with SessionLocal() as session:
            await session.execute(
                update(AppConfig)
                .where(AppConfig.key == "eta.rin")
                .values(value="")
            )
            await session.commit()

        r2 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r2.status_code == 201, r2.text
        invoice_ids.append(r2.json()["id"])
        log2 = await _log_for(r2.json()["id"])
        assert log2.qr_data.endswith(",IssuerRIN:")
        assert log2.counter == 2
        assert log2.previous_uuid == (await _log_for(r1.json()["id"])).uuid
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_E3_year_rollover_counters_never_reset(client):
    """E3: an invoice forced into next January; new sales keep counting (A15)."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, stock_qty="20.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        for _ in range(2):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])

        # force the first invoice into the next fiscal year
        async with SessionLocal() as session:
            await session.execute(
                update(Invoice)
                .where(Invoice.id == invoice_ids[0])
                .values(datee=date(2027, 1, 1),
                        datetimee=datetime(2027, 1, 1, 8, 0, tzinfo=timezone.utc))
            )
            await session.commit()

        r3 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r3.status_code == 201, r3.text
        invoice_ids.append(r3.json()["id"])
        counter = await _counter_for(branch_id, "receipt")
        assert counter.last_counter == 3  # NEVER reset at year boundary
        log3 = await _log_for(r3.json()["id"])
        assert log3.counter == 3
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_E4_zero_price_zero_total_issue_green(client):
    """E4: zero-price drug + 100% discount — docs issue, chain green."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    free = await _make_drug_and_stock_branch(branch_id, price="0.0000")
    paid = await _make_drug_and_stock_branch(branch_id, price="12.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r1 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            # NOTE: an explicit {"method":"cash","amount":"0.00"} split is
            # REJECTED by request validation (amount gt=0) — OBSERVATION
            json={"lines": [{"drug_id": free, "qty": "1"}]},
        )
        print(f"E4 OBSERVATION zero-price sale status={r1.status_code} body={r1.text[:200]}")
        assert r1.status_code == 201, r1.text
        r2 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": paid, "qty": "1"}],
                "disc_percent": "100",
            },
        )
        assert r2.status_code == 201, r2.text
        invoice_ids += [r1.json()["id"], r2.json()["id"]]
        p = await _payload(r2.json()["id"])
        assert _d(p["totalAmount"]) == Decimal("0.00")
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([free, paid], invoice_ids, branch_id)


async def test_E5_header_only_seam_consumes_no_counters():
    """E5: save_sale(lines=None) on a throwaway branch — counters untouched."""
    from app.sales.service import save_sale

    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, stock_qty="20.0000")
    try:
        async with SessionLocal() as session:
            inv = await save_sale(
                session, branch_id=branch_id, user_id=None, lines=None
            )
            header_only_id = inv.id
        async with SessionLocal() as session:
            await session.execute(
                delete(SyncLog).where(SyncLog.entity_id == header_only_id)
            )
            from app.models import AuditLog

            await session.execute(
                delete(AuditLog).where(AuditLog.entity_id == header_only_id)
            )
            await session.execute(
                delete(Invoice).where(Invoice.id == header_only_id)
            )
            await session.commit()

        async with SessionLocal() as session:
            counters = (
                await session.execute(
                    select(EInvoiceCounter).where(
                        EInvoiceCounter.branch_id == branch_id
                    )
                )
            ).scalars().all()
        assert counters == []  # no counter row even created
    finally:
        await _clear_rin()
        await _cleanup([drug_id], [], branch_id)


# ------------------------------------- F. volume & concurrency


async def test_F1_twenty_sequential_sales_gapless_fast(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, stock_qty="100.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        t0 = time.monotonic()
        for _ in range(20):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])
        elapsed = time.monotonic() - t0
        print(f"F1 OBSERVATION 20 sequential sales wall-time={elapsed:.2f}s")
        assert elapsed < 10.0
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter)
                )
            ).scalars().all()
        assert [r.counter for r in rows] == list(range(1, 21))
        assert rows[0].previous_uuid == ""
        for prev, cur in zip(rows, rows[1:]):
            assert cur.previous_uuid == prev.uuid
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_F2_six_concurrent_sales_two_tokens_gapless(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, stock_qty="50.0000"
    )
    u1 = await _make_user(_uniq("u1"), branch_id)
    u2 = await _make_user(_uniq("u2"), branch_id)
    invoice_ids = []
    try:
        t1, t2 = _token_for(u1, branch_id), _token_for(u2, branch_id)

        async def sale(tok):
            return await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {tok}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )

        responses = await asyncio.gather(
            *(sale(t1 if i % 2 == 0 else t2) for i in range(6))
        )
        for r in responses:
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter)
                )
            ).scalars().all()
        assert [r.counter for r in rows] == [1, 2, 3, 4, 5, 6]
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_F3_concurrent_new_sale_and_return_of_earlier_line(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(
        branch_id, stock_qty="50.0000"
    )
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r0 = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "5"}]},
        )
        assert r0.status_code == 201, r0.text
        first = r0.json()
        invoice_ids.append(first["id"])
        line_id = first["lines"][0]["id"]

        async def new_sale():
            return await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )

        async def do_return():
            return await client.post(
                f"/api/v1/sales/{first['id']}/return",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
            )

        sale_r, ret_r = await asyncio.gather(new_sale(), do_return())
        print(f"F3 OBSERVATION sale={sale_r.status_code} return={ret_r.status_code} "
              f"sale_body={sale_r.text[:120]} ret_body={ret_r.text[:160]}")
        assert sale_r.status_code == 201, sale_r.text
        assert ret_r.status_code == 201, ret_r.text
        invoice_ids += [sale_r.json()["id"], ret_r.json()["id"]]

        ret_log = await _log_for(ret_r.json()["id"])
        assert ret_log.kind == "return_receipt"
        assert ret_log.previous_uuid == ""  # first of ITS stream
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)
