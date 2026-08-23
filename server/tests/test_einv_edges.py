"""S4.1 edge cases (ticket #28): the legacy header-only seam issues NO tax
document; parallel sales serialize into a gapless chain under the branch lock;
an unconfigured seller RIN still issues and verifies (config gates SUBMISSION
in S4.2, never issuance)."""
import asyncio

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.einvoicing.toolkit import receipt_uuid
from app.models import (
    BranchStock,
    DrawerMovement,
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
from app.einvoicing.chain import verify_chain
from app.sales.service import save_sale
from app.sync.service import replay_pending
from tests.einv_test_utils import (
    _clear_rin,
    _make_tax_party,
    _make_user,
    _set_rin,
    _uniq,
)
from tests.sales_test_utils import _token_for
from tests.test_einv_issue import _cleanup, _log_for
from tests.returns_test_utils import (
    _make_branch,
    _make_drug_and_stock_branch,
)


async def test_header_only_seam_issues_no_tax_document():
    """The plugin-host seam (ticket #3: save_sale with no lines) keeps its
    original contract — an invoice with zero totals and NO einvoice row (a
    zero-total placeholder must never consume a fiscal counter)."""
    from app.models import AuditLog, Invoice, SyncLog
    from tests.sales_test_utils import BRANCH_ID

    async with SessionLocal() as session:
        invoice = await save_sale(
            session,
            branch_id=BRANCH_ID,
            user_id=None,
            lines=None,  # the ORIGINAL seam contract: header-only invoice
        )
        invoice_id = invoice.id
    async with SessionLocal() as session:
        logs = (
            await session.execute(
                select(EInvoiceLog).where(EInvoiceLog.invoice_id == invoice_id)
            )
        ).scalars().all()
        assert logs == []
        # tidy up after ourselves on MAIN branch (tracked ids only)
        await session.execute(
            delete(SyncLog).where(SyncLog.entity_id == invoice_id)
        )
        await session.execute(
            delete(AuditLog).where(AuditLog.entity_id == invoice_id)
        )
        await session.execute(delete(Invoice).where(Invoice.id == invoice_id))
        await session.commit()


async def test_parallel_sales_stay_gapless_under_the_branch_lock(client):
    """8 concurrent sales on one branch: every document gets its own counter,
    the previousUUID links chain correctly, and reconciliation holds."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, stock_qty="100.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)

        async def sale():
            return await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )

        responses = await asyncio.gather(*(sale() for _ in range(8)))
        for r in responses:
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])

        async with SessionLocal() as session:
            logs = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter)
                )
            ).scalars().all()
        counters = sorted(l.counter for l in logs)
        assert counters == list(range(1, 9))  # gapless, distinct
        assert logs[0].previous_uuid == ""
        for prev, cur in zip(logs, logs[1:]):
            assert cur.previous_uuid == prev.uuid

        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_unconfigured_rin_still_issues_and_verifies(client):
    """No eta.rin in app_config: the document still issues (QR carries an
    empty IssuerRIN until configured) and the chain verifies."""
    await _clear_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id)
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(
                        EInvoiceLog.invoice_id == invoice_ids[0]
                    )
                )
            ).scalar_one()
        assert log.qr_data.endswith(",IssuerRIN:")
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_return_replay_reproduces_document_with_reference_intact(client):
    """Return-side replay parity (#28 review edge): the return's tax document
    rebuilds VERBATIM from its outbox snapshot — same counter/uuid AND the
    reference_uuid pointing at the original's uuid."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, stock_qty="20.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    sale: dict | None = None
    try:
        token = _token_for(user_id, branch_id)
        r_sale = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "3"}]},
        )
        assert r_sale.status_code == 201, r_sale.text
        sale = r_sale.json()
        assert sale is not None
        line_id = sale["lines"][0]["id"]
        r_ret = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r_ret.status_code == 201, r_ret.text
        ret = r_ret.json()
        ret_id = ret["id"]
        issued = await _log_for(ret_id)

        # wipe ONLY the return's local write; keep its outbox row pending
        async with SessionLocal() as session:
            jids = (
                await session.execute(
                    select(Journal.id).where(Journal.ref_invoice_id == ret_id)
                )
            ).scalars().all()
            if jids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.journal_id.in_(jids))
                )
                await session.execute(delete(Journal).where(Journal.id.in_(jids)))
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == ret_id)
            )
            await session.execute(
                delete(DrawerMovement).where(DrawerMovement.ref_invoice_id == ret_id)
            )
            await session.execute(
                delete(InvoiceVersion).where(
                    InvoiceVersion.invoice_id == sale["id"]
                )
            )
            await session.execute(
                delete(EInvoiceLog).where(EInvoiceLog.invoice_id == ret_id)
            )
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id == ret_id)
            )
            # the return's NEW stock batch + its branch_stock raise must go
            # too, so the target store looks pre-return
            await session.execute(
                delete(StockBatch).where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.typee == "return",
                )
            )
            stock_row = (
                await session.execute(
                    select(BranchStock).where(
                        BranchStock.branch_id == branch_id,
                        BranchStock.drug_id == drug_id,
                    )
                )
            ).scalar_one()
            stock_row.qty -= 1  # undo the return's raise (returned qty)
            await session.execute(delete(Invoice).where(Invoice.id == ret_id))
            await session.commit()

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=branch_id)
            assert summary["applied"] >= 1, summary

        async with SessionLocal() as session:
            inv = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.branch_id == branch_id,
                        Invoice.invoice_no == ret["invoice_no"],
                    )
                )
            ).scalar_one()
            replayed = (
                await session.execute(
                    select(EInvoiceLog).where(EInvoiceLog.invoice_id == inv.id)
                )
            ).scalar_one()
        assert replayed.uuid == issued.uuid
        assert replayed.reference_uuid == issued.reference_uuid
        assert receipt_uuid(replayed.payload_json) == replayed.uuid
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup(
            [drug_id], [sale["id"]] if sale else [], branch_id
        )


async def test_out_of_order_replay_keeps_chain_green(client):
    """G10 retry semantics (review edge): documents may arrive out of order —
    applying counter 2 BEFORE counter 1 still lands every document at its own
    chain position and verification stays green."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, stock_qty="20.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
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

        from app.einvoicing.service import apply_einvoice_block

        async with SessionLocal() as session:
            blocks = {}
            for iid in invoice_ids:
                sync_row = (
                    await session.execute(
                        select(SyncLog).where(
                            SyncLog.entity == "invoice", SyncLog.entity_id == iid
                        )
                    )
                ).scalar_one()
                blocks[sync_row.payload["einvoice"]["counter"]] = (
                    sync_row.payload["einvoice"]
                )
            # wipe local docs + counter state, then replay OUT OF ORDER
            await session.execute(
                delete(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id)
            )
            from app.models import EInvoiceCounter

            await session.execute(
                delete(EInvoiceCounter).where(
                    EInvoiceCounter.branch_id == branch_id
                )
            )
            await session.flush()
            for counter in sorted(blocks, reverse=True):  # 2 before 1
                await apply_einvoice_block(
                    session,
                    branch_id=branch_id,
                    invoice_id=invoice_ids[counter - 1],
                    block=blocks[counter],
                )
            await session.commit()

        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
        async with SessionLocal() as session:
            logs = (
                await session.execute(
                    select(EInvoiceLog)
                    .where(EInvoiceLog.branch_id == branch_id)
                    .order_by(EInvoiceLog.counter)
                )
            ).scalars().all()
        assert [l.counter for l in logs] == [1, 2]
        assert logs[0].previous_uuid == ""
        assert logs[1].previous_uuid == logs[0].uuid
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_mixed_cash_credit_sale_to_registered_party_routes_b2b(client):
    """Pinned behavior (review edge): ANY credit portion routes a registered
    party's sale to B2B 'I'; the paymentMethod collapses to the largest split
    (cash → C). Full multi-method payment modeling stays an S4.2 concern."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="100.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    rin_party = await _make_tax_party(branch_id, rin="300111222")
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "party_id": rin_party,
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "payments": [
                    {"method": "cash", "amount": "99.00"},
                    {"method": "credit", "amount": "1.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        async with SessionLocal() as session:
            log = (
                await session.execute(
                    select(EInvoiceLog).where(
                        EInvoiceLog.invoice_id == invoice_ids[0]
                    )
                )
            ).scalar_one()
        assert log.kind == "invoice"
        assert log.payload_json["paymentMethod"] == "C"
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_zero_total_sale_still_issues_and_verifies(client):
    """Pinned behavior (review edge): a 100%-discount zero-total sale issues a
    document and consumes its fiscal position (AC: EVERY sale ⇒ record).
    Whether S4.2 skips zero-total docs at SUBMISSION is that ticket's call."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, price="10.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "1"}],
                "disc_percent": "100",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["totalvalue"] == "0.00"

        log = await _log_for(invoice_ids[0])
        assert log.kind == "receipt"
        assert log.payload_json["totalAmount"] == "0.00"
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)


async def test_repair_path_rebuilds_lost_documents_for_existing_invoices(client):
    """Recovery edge (red-team D1a): an invoice that EXISTS but whose tax
    document was lost (partial restore / manual surgery) is repaired from the
    pending outbox snapshot instead of being skipped as 'already synced'."""
    await _set_rin()
    branch_id = await _make_branch(vat_inclusive=True)
    drug_id = await _make_drug_and_stock_branch(branch_id, stock_qty="30.0000")
    user_id = await _make_user(_uniq("u"), branch_id)
    invoice_ids: list[int] = []
    try:
        token = _token_for(user_id, branch_id)
        uuids = []
        for _ in range(3):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])
            log = await _log_for(invoice_ids[-1])
            uuids.append(log.uuid)

        # lose the DOCUMENTS (log + chain state) but keep invoices + outbox
        async with SessionLocal() as session:
            from app.models import EInvoiceCounter

            await session.execute(
                delete(EInvoiceLog).where(EInvoiceLog.branch_id == branch_id)
            )
            await session.execute(
                delete(EInvoiceCounter).where(
                    EInvoiceCounter.branch_id == branch_id
                )
            )
            await session.commit()

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=branch_id)
            assert summary["applied"] >= 3, summary

        # every invoice has its document back, verbatim, chain intact
        rebuilt = []
        for iid in invoice_ids:
            log = await _log_for(iid)
            rebuilt.append(log)
        assert [l.uuid for l in rebuilt] == uuids  # exact same documents
        report = await verify_chain(branch_id=branch_id)
        assert report["ok"] is True, report["problems"]
    finally:
        await _clear_rin()
        await _cleanup([drug_id], invoice_ids, branch_id)
