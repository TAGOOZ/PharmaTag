"""Offline replay of sales-return outbox rows (ticket #11, G10): a return
replayed on a target store re-creates its NEW return batch, raises branch_stock,
links to the original sale (found by original_invoice_no), journals balanced and
snapshots the original into invoice_versions — idempotently, never double-raising
stock. If the original sale has not reached the store the row is recorded failed.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.audit import enqueue_sync
from app.models import (
    AuditLog,
    BranchStock,
    Invoice,
    InvoiceLine,
    InvoiceVersion,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
)
from app.sync.service import replay_pending
from tests.drawer_test_utils import _cleanup_movements_for_invoice
from tests.returns_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _sale,
)

BRANCH_ID = 1


async def _return(client, token: str, sale: dict, qty: str) -> dict:
    r = await client.post(
        f"/api/v1/sales/{sale['id']}/return",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"ref_invoice_line_id": sale["lines"][0]["id"], "qty": qty}]},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _stock_qty(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
                )
            )
        ).scalar_one_or_none()
        return row.qty if row is not None else Decimal("0")


async def _journal_totals(invoice_id: int) -> tuple[Decimal, Decimal]:
    async with SessionLocal() as session:
        journal = (
            await session.execute(select(Journal).where(Journal.ref_invoice_id == invoice_id))
        ).scalar_one()
        lines = (
            await session.execute(
                select(JournalLine).where(JournalLine.journal_id == journal.id)
            )
        ).scalars().all()
        return (
            sum((l.debit for l in lines), Decimal("0")),
            sum((l.credit for l in lines), Decimal("0")),
        )


async def _remove_invoice(session, *, invoice_id: int) -> None:
    """Remove an invoice + all its children (journal, lines, splits, versions,
    sync, audit)."""
    jids = (
        await session.execute(select(Journal.id).where(Journal.ref_invoice_id == invoice_id))
    ).scalars().all()
    if jids:
        await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
        await session.execute(delete(Journal).where(Journal.id.in_(jids)))
    await session.execute(delete(PaymentSplit).where(PaymentSplit.invoice_id == invoice_id))
    await _cleanup_movements_for_invoice(session, invoice_id=invoice_id)
    await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id))
    await session.execute(delete(InvoiceVersion).where(InvoiceVersion.invoice_id == invoice_id))
    await session.execute(delete(SyncLog).where(SyncLog.entity_id == invoice_id))
    await session.execute(delete(AuditLog).where(AuditLog.entity_id == invoice_id))
    await session.execute(delete(Invoice).where(Invoice.id == invoice_id))


async def _remove_return(
    session, *, invoice_id: int, drug_id: int
) -> None:
    """Remove a return invoice + its batch + the version snapshot it put on the
    ORIGINAL, and reset stock to the pre-return level — simulating a target
    store that only ever applied the original sale."""
    ret = await session.get(Invoice, invoice_id)
    ref_invoice_id = ret.ref_invoice_id
    jids = (
        await session.execute(select(Journal.id).where(Journal.ref_invoice_id == invoice_id))
    ).scalars().all()
    if jids:
        await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
        await session.execute(delete(Journal).where(Journal.id.in_(jids)))
    await session.execute(delete(PaymentSplit).where(PaymentSplit.invoice_id == invoice_id))
    await _cleanup_movements_for_invoice(session, invoice_id=invoice_id)
    await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id))
    await session.execute(delete(SyncLog).where(SyncLog.entity_id == invoice_id))
    await session.execute(delete(AuditLog).where(AuditLog.entity_id == invoice_id))
    if ref_invoice_id is not None:
        await session.execute(
            delete(InvoiceVersion).where(InvoiceVersion.invoice_id == ref_invoice_id)
        )
    await session.execute(delete(Invoice).where(Invoice.id == invoice_id))
    await session.execute(delete(StockBatch).where(StockBatch.typee == "return"))
    row = (
        await session.execute(
            select(BranchStock).where(
                BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        session.add(
            BranchStock(branch_id=BRANCH_ID, drug_id=drug_id, qty=Decimal("0"), minimum=0)
        )
    else:
        row.qty = Decimal("0")


async def test_return_replay_applies_and_is_idempotent(client):
    """The return outbox row is replayed onto a store that has the original sale:
    batch + stock + invoice + journal + version snapshot all appear; a second
    replay is a no-op (never raises stock twice)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        ret = await _return(client, token, sale, qty="4")
        invoice_ids.append(ret["id"])
        sale_id, ret_id = sale["id"], ret["id"]
        assert await _stock_qty(drug_id) == Decimal("4")

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id)
            # isolate: clear stray pending (sale invoice/branch_stock) so only the re-enqueued return is counted
            await session.execute(delete(SyncLog).where(SyncLog.branch_id==BRANCH_ID, SyncLog.entity=="branch_stock"))
            await session.execute(delete(SyncLog).where(SyncLog.branch_id==BRANCH_ID, SyncLog.entity=="invoice"))
            await enqueue_sync(
                session,
                branch_id=BRANCH_ID,
                entity="invoice",
                entity_id=ret_id,
                action="insert",
                payload=payload,
            )
            await session.commit()
        assert await _stock_qty(drug_id) == Decimal("0")

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["failed"] == 0
        assert summary["applied"] == 1, summary

        async with SessionLocal() as session:
            replayed = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.branch_id == BRANCH_ID,
                        Invoice.invoice_no == payload["invoice_no"],
                        Invoice.kind == "sale_return",
                    )
                )
            ).scalars().first()
            assert replayed is not None
            new_id = replayed.id
            invoice_ids.append(new_id)
            assert replayed.ref_invoice_id == sale_id
            batches = (
                await session.execute(
                    select(StockBatch).where(
                        StockBatch.typee == "return", StockBatch.drug_id == drug_id
                    )
                )
            ).scalars().all()
            assert len(batches) == 1
            assert str(batches[0].qty) == "4.0000"
            versions = (
                await session.execute(
                    select(InvoiceVersion).where(InvoiceVersion.invoice_id == sale_id)
                )
            ).scalars().all()
            assert len(versions) == 1
            assert versions[0].action == "sale_return"
        assert await _stock_qty(drug_id) == Decimal("4")
        debit, credit = await _journal_totals(new_id)
        assert debit == credit == Decimal("60.00")

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        # drain remaining branch_stock fan-out (LWW absolute, idempotent)
        assert summary["failed"] == 0
        async with SessionLocal() as session:
            summary2 = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary2["applied"] == 0
        assert summary2["failed"] == 0
        assert await _stock_qty(drug_id) == Decimal("4")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_replay_dedupes_online_write(client):
    """A return recorded online (invoice already present) is skipped on replay."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        ret = await _return(client, token, sale, qty="4")
        invoice_ids.append(ret["id"])
        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        # sale/return left branch_stock fan-out pending; return invoice is skipped
        assert summary["skipped"] >= 1
        assert summary["failed"] == 0
        # drain branch_stock
        async with SessionLocal() as session:
            summary2 = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary2["failed"] == 0
        assert await _stock_qty(drug_id) == Decimal("4")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_replay_missing_original_fails_recorded(client):
    """A return whose original sale never reached the store is recorded failed
    (G10) — stock is not touched."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    sync_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        ret = await _return(client, token, sale, qty="4")
        invoice_ids.append(ret["id"])
        sale_id, ret_id = sale["id"], ret["id"]

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id)
            # drop the original sale too + its outbox, so replay can never link
            await _remove_invoice(session, invoice_id=sale_id)
            # isolate: clear stray pending (branch_stock fan-out) so only the test return is counted
            await session.execute(delete(SyncLog).where(SyncLog.branch_id==BRANCH_ID, SyncLog.entity=="branch_stock"))
            await session.execute(delete(SyncLog).where(SyncLog.branch_id==BRANCH_ID, SyncLog.entity=="invoice"))
            new_sync = await enqueue_sync(
                session,
                branch_id=BRANCH_ID,
                entity="invoice",
                entity_id=ret_id,
                action="insert",
                payload=payload,
            )
            sync_ids.append(new_sync.id)
            await session.commit()
        invoice_ids = []  # removed manually

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["failed"] == 1
        assert "original sale missing" in summary["failures"][0]["error"]
        assert await _stock_qty(drug_id) == Decimal("0")
        async with SessionLocal() as session:
            row = await session.get(SyncLog, sync_ids[0])
            assert row.status == "failed"
            assert "failure" in row.payload
        # drain any remaining branch_stock
        async with SessionLocal() as session:
            await replay_pending(session, branch_id=BRANCH_ID)
    finally:
        await _cleanup([drug_id], invoice_ids)
        async with SessionLocal() as session:
            if sync_ids:
                await session.execute(delete(SyncLog).where(SyncLog.id.in_(sync_ids)))
            await session.commit()


async def test_return_replay_recreates_credit_split(client):
    """A return whose original was paid 100% credit replays with the credit
    split: the target store recreates the AR refund (agel), not the drawer."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(
            client, token,
            [{"drug_id": drug_id, "qty": "10"}],
            payments=[{"method": "credit", "amount": "100.00"}],
        )
        invoice_ids.append(sale["id"])
        ret = await _return(client, token, sale, qty="4")
        invoice_ids.append(ret["id"])
        assert ret["payed"] == "0.00"
        assert ret["agel"] == "40.00"
        sale_id, ret_id = sale["id"], ret["id"]

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id)
            await enqueue_sync(
                session,
                branch_id=BRANCH_ID,
                entity="invoice",
                entity_id=ret_id,
                action="insert",
                payload=payload,
            )
            await session.commit()

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["failed"] == 0
        assert summary["applied"] >= 1, summary
        # drain branch_stock fan-out
        async with SessionLocal() as session:
            await replay_pending(session, branch_id=BRANCH_ID)

        async with SessionLocal() as session:
            replayed = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.branch_id == BRANCH_ID,
                        Invoice.invoice_no == payload["invoice_no"],
                        Invoice.kind == "sale_return",
                    )
                )
            ).scalars().first()
            assert replayed is not None
            new_id = replayed.id
            invoice_ids.append(new_id)
            assert replayed.ref_invoice_id == sale_id
            assert replayed.payed == Decimal("0")
            assert replayed.agel == Decimal("40.00")
            splits = (
                await session.execute(
                    select(PaymentSplit).where(
                        PaymentSplit.invoice_id == new_id
                    )
                )
            ).scalars().all()
            assert [(p.method, p.amount) for p in splits] == [
                ("credit", Decimal("40.00"))
            ]
        debit, credit = await _journal_totals(new_id)
        assert debit == credit == Decimal("60.00")
    finally:
        await _cleanup([drug_id], invoice_ids)