"""S4.1 issue-path tests (ticket #28): sale ⇒ log + counter + chain + QR,
regime routing, STRICT atomicity, offline replay parity."""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    BranchStock,
    DrawerMovement,
    Drug,
    EInvoiceCounter,
    EInvoiceLog,
    Invoice,
    InvoiceLine,
    InvoiceVersion,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from app.einvoicing.toolkit import PROD_PORTAL_URL, qr_string, receipt_uuid
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
from tests.returns_test_utils import (
    _delete_branch,
    _make_branch,
    _make_drug_and_stock_branch,
)


async def _cleanup(drug_ids: list[int], invoice_ids: list[int], branch_id: int) -> None:
    """Purge EVERYTHING on the throwaway branch (einvoice/version rows first —
    they FK other tables), then the drug/branch rows. Branch-scoped on
    purpose: replayed invoices get fresh ids the test never sees."""
    async with SessionLocal() as session:
        all_ids = (
            await session.execute(
                select(Invoice.id).where(Invoice.branch_id == branch_id)
            )
        ).scalars().all()
        jids = (
            await session.execute(
                select(Journal.id).where(Journal.branch_id == branch_id)
            )
        ).scalars().all()
        if jids:
            await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
            await session.execute(delete(Journal).where(Journal.id.in_(jids)))
        await session.execute(delete(Balance).where(Balance.branch_id == branch_id))
        await session.execute(
            delete(PaymentSplit).where(PaymentSplit.branch_id == branch_id)
        )
        await session.execute(
            delete(DrawerMovement).where(DrawerMovement.branch_id == branch_id)
        )
        # children before parents: ref lines → versions/einvoice → lines → invoices
        await session.execute(
            delete(InvoiceLine).where(
                InvoiceLine.ref_invoice_line_id.in_(
                    select(InvoiceLine.id).where(InvoiceLine.branch_id == branch_id)
                )
            )
        )
        await session.execute(
            delete(InvoiceVersion).where(InvoiceVersion.invoice_id.in_(all_ids))
        )
        await session.execute(
            delete(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id)
        )
        await session.execute(delete(AuditLog).where(AuditLog.branch_id == branch_id))
        await session.execute(delete(SyncLog).where(SyncLog.branch_id == branch_id))
        await session.execute(
            delete(InvoiceLine).where(InvoiceLine.branch_id == branch_id)
        )
        await session.execute(delete(Invoice).where(Invoice.branch_id == branch_id))
        await session.execute(
            delete(EInvoiceCounter).where(EInvoiceCounter.branch_id == branch_id)
        )
        # this slice's tests create tax-registered parties on the throwaway
        # branch — they must go before the branch itself
        from app.models import Party

        await session.execute(delete(Party).where(Party.branch_id == branch_id))
        for drug_id in drug_ids:
            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == drug_id))
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()
    await _delete_branch(branch_id)


async def test_sale_issues_receipt_log_counter_qr_atomically(client):
    """A cash sale on a fresh branch: log row counter=1 with an EMPTY
    previousUUID, uuid recomputable from the stored payload, QR per the ETA
    template — plus audit and the outbox snapshot carrying the document."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, tax_type="14%")
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
        assert log.kind == "receipt"
        assert log.status == "pending"  # offline rows stay pending (S4.2 submits)
        assert log.counter == 1
        assert log.previous_uuid == ""  # first-of-device
        assert log.reference_uuid == ""

        # UUID verifies against the STORED payload (with uuid emptied)
        payload = dict(log.payload_json)
        assert payload["header"]["receiptNumber"] == body["invoice_no"]
        assert payload["header"]["previousUUID"] == ""
        assert receipt_uuid(payload) == log.uuid

        # QR links the consumer verification page with total + issuer RIN
        assert log.qr_data == qr_string(
            uuid=log.uuid,
            datetime_issued_utc=payload["header"]["dateTimeIssued"],
            total=payload["totalAmount"],
            issuer_rin=RIN,
            portal_url=PROD_PORTAL_URL,
        )
        assert f"#Total:{payload['totalAmount']},IssuerRIN:{RIN}" in log.qr_data
        assert "/receipts/search/" in log.qr_data and "/share/" in log.qr_data

        # the outbox snapshot carries the tax document verbatim (G12)
        async with SessionLocal() as session:
            sync_row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice",
                        SyncLog.entity_id == body["id"],
                    )
                )
            ).scalar_one()
            block = sync_row.payload["einvoice"]
            assert block["kind"] == "receipt"
            assert block["uuid"] == log.uuid
            assert block["previous_uuid"] == ""
            assert block["counter"] == 1
            # G12: an audit row for the tax document rode the same transaction
            audit_row = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity == "einvoice_log",
                        AuditLog.entity_id == log.id,
                    )
                )
            ).scalar_one()
            assert log.uuid[:16] in audit_row.new_value

        counter = await _counter_for(branch_id, "receipt")
        assert counter.last_counter == 1
        assert counter.last_uuid == log.uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_second_sale_chains_previous_uuid(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)

        async def _sale():
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            return r.json()

        first = await _sale()
        second = await _sale()
        invoice_ids += [first["id"], second["id"]]

        log1 = await _log_for(first["id"])
        log2 = await _log_for(second["id"])
        assert log1.counter == 1 and log2.counter == 2
        assert log2.previous_uuid == log1.uuid
        assert receipt_uuid(log2.payload_json) == log2.uuid
        assert log2.uuid != log1.uuid  # content + previousUUID feed the hash

        counter = await _counter_for(branch_id, "receipt")
        assert counter.last_counter == 2
        assert counter.last_uuid == log2.uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_credit_sale_to_tax_registered_party_routes_b2b(client):
    """Regime routing is per document (ADR-0002): a deferred sale whose party
    carries a tax registration number issues a B2B eInvoice; a deferred sale
    to an unregistered party stays a receipt (أجل = payment term)."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="100.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    rin_party = await _make_tax_party(branch_id, rin="300123456")
    plain_party = await _make_tax_party(branch_id, rin=None)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)

        r_b2b = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": rin_party,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [{"method": "credit", "amount": "100.00"}],
            },
        )
        assert r_b2b.status_code == 201, r_b2b.text
        invoice_ids.append(r_b2b.json()["id"])
        log_b2b = await _log_for(r_b2b.json()["id"])
        assert log_b2b.kind == "invoice"
        assert log_b2b.payload_json["buyer"]["id"] == "300123456"

        r_b2c = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": plain_party,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [{"method": "credit", "amount": "100.00"}],
            },
        )
        assert r_b2c.status_code == 201, r_b2c.text
        invoice_ids.append(r_b2c.json()["id"])
        log_b2c = await _log_for(r_b2c.json()["id"])
        assert log_b2c.kind == "receipt"

        # separate gapless streams per kind
        assert (await _counter_for(branch_id, "invoice")).last_counter == 1
        assert (await _counter_for(branch_id, "receipt")).last_counter == 1
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_return_issues_return_receipt_referencing_original(client):
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids = []
    try:
        token = _token_for(user_id, branch_id)
        r_sale = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "3"}]},
        )
        assert r_sale.status_code == 201, r_sale.text
        sale = r_sale.json()
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]

        r_ret = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r_ret.status_code == 201, r_ret.text
        ret = r_ret.json()
        invoice_ids.append(ret["id"])

        orig_log = await _log_for(sale["id"])
        ret_log = await _log_for(ret["id"])
        assert ret_log.kind == "return_receipt"
        assert ret_log.reference_uuid == orig_log.uuid
        assert ret_log.previous_uuid == ""  # first of its own kind stream
        assert ret_log.counter == 1
        assert receipt_uuid(ret_log.payload_json) == ret_log.uuid
        assert ret_log.payload_json["header"]["referenceUUID"] == orig_log.uuid

        assert (await _counter_for(branch_id, "return_receipt")).last_counter == 1
        # original's own stream untouched by the return
        assert (await _counter_for(branch_id, "receipt")).last_counter == 1
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_strict_failure_blocks_the_whole_sale(client):
    """STRICT counters (A09): if the tax-document write fails inside the
    transaction, the SALE dies with it — no half-written invoice, stock,
    journal, audit or outbox rows survive (G12 atomicity)."""
    from unittest.mock import patch

    import app.einvoicing.service as einv_service
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    try:
        async with SessionLocal() as session:
            before_invoices = len(
                (await session.execute(
                    select(Invoice.id).where(Invoice.branch_id == branch_id)
                )).scalars().all()
            )

        token = _token_for(user_id, branch_id)
        # ASGITransport re-raises in-app exceptions; we want the 500 response
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            with patch.object(
                einv_service, "build_document", side_effect=RuntimeError("eta boom")
            ):
                r = await c.post(
                    "/api/v1/sales",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"lines": [{"drug_id": drug_id, "qty": "2"}]},
                )
        assert r.status_code == 500

        async with SessionLocal() as session:
            after = len(
                (await session.execute(
                    select(Invoice.id).where(Invoice.branch_id == branch_id)
                )).scalars().all()
            )
            assert after == before_invoices  # nothing persisted at all
            logs = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id)
                )
            ).scalars().all()
            counters = (
                await session.execute(
                    select(EInvoiceCounter).where(
                        EInvoiceCounter.branch_id == branch_id
                    )
                )
            ).scalars().all()
            assert logs == [] and counters == []

            qty = (
                await session.execute(
                    select(BranchStock.qty).where(
                        BranchStock.branch_id == branch_id,
                        BranchStock.drug_id == drug_id,
                    )
                )
            ).scalar_one()
            assert Decimal(qty) == Decimal("10.0000")  # stock untouched too
    finally:
        await _clear_rin()
        await _cleanup([drug_id], [], branch_id)


async def test_replay_reproduces_the_document_verbatim_and_is_idempotent(client):
    """Offline replay: the target store rebuilds the SAME tax document from the
    outbox snapshot (never re-generates — no counter drift), and replaying the
    batch twice changes nothing."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
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
        invoice_ids.append(r.json()["id"])
        issued = await _log_for(r.json()["id"])
        invoice_no = r.json()["invoice_no"]

        # wipe the local write but keep the pending outbox row → replay it
        async with SessionLocal() as session:
            iid = r.json()["id"]
            jids = (
                await session.execute(
                    select(Journal.id).where(Journal.ref_invoice_id == iid)
                )
            ).scalars().all()
            if jids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.journal_id.in_(jids))
                )
                await session.execute(delete(Journal).where(Journal.id.in_(jids)))
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == iid)
            )
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == iid)
            )
            await session.execute(
                delete(EInvoiceLog).where(EInvoiceLog.invoice_id == iid)
            )
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
            )
            await session.execute(delete(Invoice).where(Invoice.id == iid))
            await session.commit()

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=branch_id)
            assert summary["applied"] >= 1, summary

        replayed = await _log_for_by_invoice_no(branch_id, invoice_no)
        assert replayed.id != issued.id  # a new row...
        assert (replayed.counter, replayed.uuid, replayed.previous_uuid) == (
            issued.counter,
            issued.uuid,
            issued.previous_uuid,
        )  # ...with the EXACT same chain position
        assert receipt_uuid(replayed.payload_json) == replayed.uuid

        async with SessionLocal() as session:
            summary2 = await replay_pending(session, branch_id=branch_id)
            assert summary2["applied"] == 0 and summary2["failed"] == 0
            # nothing changed: still exactly one document at the same position
            rows = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id)
                )
            ).scalars().all()
            assert len(rows) == 1
            assert (rows[0].counter, rows[0].uuid) == (replayed.counter, replayed.uuid)
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def _log_for_by_invoice_no(branch_id: int, invoice_no: str) -> EInvoiceLog:
    async with SessionLocal() as session:
        inv = (
            await session.execute(
                select(Invoice).where(
                    Invoice.branch_id == branch_id,
                    Invoice.invoice_no == invoice_no,
                )
            )
        ).scalar_one()
        return (
            await session.execute(
                select(EInvoiceLog).where(EInvoiceLog.invoice_id == inv.id)
            )
        ).scalar_one()
