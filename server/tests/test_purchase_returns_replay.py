"""Offline replay of purchase-return outbox rows (ticket #12, G10): a return
replayed on a target store decrements the ORIGINAL purchase batch + branch_stock,
links to the original purchase (found by original_invoice_no), journals balanced
and snapshots the original into invoice_versions — idempotently, never
double-decrementing. If the original purchase (or its batch) has not reached
the store the row is recorded failed.
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
from tests.purchase_returns_test_utils import (
    _cleanup,
    _login_token,
    _make_drug,
    _make_supplier,
    _purchase,
)

BRANCH_ID = 1


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


async def _batch(drug_id: int) -> StockBatch:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(StockBatch).where(StockBatch.drug_id == drug_id)
            )
        ).scalars().one()


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


async def _remove_return(session, *, invoice_id: int, drug_id: int, restore_qty: str) -> None:
    """Remove a return invoice + all its children and restore the batch +
    branch_stock to the pre-return level — simulating a target store that only
    ever applied the original purchase."""
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
    batch = (
        await session.execute(select(StockBatch).where(StockBatch.drug_id == drug_id))
    ).scalars().one()
    batch.qty = Decimal(restore_qty)
    row = (
        await session.execute(
            select(BranchStock).where(
                BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
            )
        )
    ).scalar_one()
    row.qty = Decimal(restore_qty)


async def test_return_replay_applies_and_is_idempotent(client):
    """The return outbox row is replayed onto a store that has the original
    purchase: batch + stock + invoice + journal + version snapshot all appear; a
    second replay is a no-op (never decrements stock twice)."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]},
        )
        assert ret.status_code == 201, ret.text
        ret = ret.json()
        invoice_ids.append(ret["id"])
        purchase_id, ret_id = pur["id"], ret["id"]
        assert await _stock_qty(drug_id) == Decimal("6.0000")

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            assert payload["kind"] == "purchase_return"
            assert payload["original_invoice_no"] == pur["invoice_no"]
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id, restore_qty="10")
            await enqueue_sync(
                session,
                branch_id=BRANCH_ID,
                entity="invoice",
                entity_id=ret_id,
                action="insert",
                payload=payload,
            )
            await session.commit()
        assert await _stock_qty(drug_id) == Decimal("10.0000")

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["applied"] == 1, summary
        assert summary["failed"] == 0

        async with SessionLocal() as session:
            replayed = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.branch_id == BRANCH_ID,
                        Invoice.invoice_no == payload["invoice_no"],
                        Invoice.kind == "purchase_return",
                    )
                )
            ).scalars().first()
            assert replayed is not None
            new_id = replayed.id
            invoice_ids.append(new_id)
            assert replayed.ref_invoice_id == purchase_id
            assert replayed.kind == "purchase_return"
            batch = (
                await session.execute(
                    select(StockBatch).where(StockBatch.drug_id == drug_id)
                )
            ).scalars().one()
            assert str(batch.qty) == "6.0000"
            versions = (
                await session.execute(
                    select(InvoiceVersion).where(InvoiceVersion.invoice_id == purchase_id)
                )
            ).scalars().all()
            assert len(versions) == 1
            assert versions[0].action == "purchase_return"
        assert await _stock_qty(drug_id) == Decimal("6.0000")
        debit, credit = await _journal_totals(new_id)
        assert debit == credit == Decimal("45.60")

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["applied"] == 0
        assert await _stock_qty(drug_id) == Decimal("6.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_return_replay_dedupes_online_write(client):
    """A return recorded online (invoice already present) is skipped on replay."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]},
        )
        assert ret.status_code == 201, ret.text
        invoice_ids.append(ret.json()["id"])
        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["applied"] == 0
        assert summary["skipped"] >= 1
        assert await _stock_qty(drug_id) == Decimal("6.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_return_replay_missing_original_fails_recorded(client):
    """A return whose original purchase never reached the store is recorded
    failed (G10) — stock is not touched."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    sync_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]},
        )
        assert ret.status_code == 201, ret.text
        ret_id = ret.json()["id"]
        invoice_ids.append(ret_id)
        purchase_id = pur["id"]

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id, restore_qty="10")
            # drop the original purchase too + its outbox, so replay can never link
            jids = (
                await session.execute(
                    select(Journal.id).where(Journal.ref_invoice_id == purchase_id)
                )
            ).scalars().all()
            if jids:
                await session.execute(delete(JournalLine).where(JournalLine.journal_id.in_(jids)))
                await session.execute(delete(Journal).where(Journal.id.in_(jids)))
            await session.execute(delete(PaymentSplit).where(PaymentSplit.invoice_id == purchase_id))
            await _cleanup_movements_for_invoice(session, invoice_id=purchase_id)
            await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == purchase_id))
            await session.execute(delete(SyncLog).where(SyncLog.entity_id == purchase_id))
            await session.execute(delete(AuditLog).where(AuditLog.entity_id == purchase_id))
            await session.execute(delete(Invoice).where(Invoice.id == purchase_id))
            await session.execute(delete(StockBatch).where(StockBatch.drug_id == drug_id))
            row = (
                await session.execute(
                    select(BranchStock).where(
                        BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
                    )
                )
            ).scalar_one()
            row.qty = Decimal("0")
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
        assert summary["applied"] == 0
        assert summary["failed"] == 1
        assert "original purchase missing" in summary["failures"][0]["error"]
        assert await _stock_qty(drug_id) == Decimal("0")
        async with SessionLocal() as session:
            row = await session.get(SyncLog, sync_ids[0])
            assert row.status == "failed"
            assert "failure" in row.payload
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])
        async with SessionLocal() as session:
            if sync_ids:
                await session.execute(delete(SyncLog).where(SyncLog.id.in_(sync_ids)))
            await session.commit()


async def test_return_replay_fails_when_target_batch_insufficient(client):
    """Offline conflict: the target store sold part of the purchased batch
    locally before the return replayed. The return needs 4 but the batch only
    holds 2 → recorded failed (G10), stock untouched, never over-decremented."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    sync_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]},
        )
        assert ret.status_code == 201, ret.text
        ret_id = ret.json()["id"]
        invoice_ids.append(ret_id)

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id, restore_qty="10")
            # local store sold 8 of the batch before this return arrived
            batch = (
                await session.execute(select(StockBatch).where(StockBatch.drug_id == drug_id))
            ).scalars().one()
            batch.qty = Decimal("2")
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
        invoice_ids = []

        async with SessionLocal() as session:
            summary = await replay_pending(session, branch_id=BRANCH_ID)
        assert summary["applied"] == 0
        assert summary["failed"] == 1
        assert "batch" in summary["failures"][0]["error"]
        async with SessionLocal() as session:
            batch = (
                await session.execute(select(StockBatch).where(StockBatch.drug_id == drug_id))
            ).scalars().one()
            assert batch.qty == Decimal("2")
            # branch_stock was never decremented — the batch check fires first
            stock = (
                await session.execute(
                    select(BranchStock).where(
                        BranchStock.branch_id == BRANCH_ID, BranchStock.drug_id == drug_id
                    )
                )
            ).scalar_one()
            assert stock.qty == Decimal("10.0000")
            row = await session.get(SyncLog, sync_ids[0])
            assert row.status == "failed"
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])
        async with SessionLocal() as session:
            if sync_ids:
                await session.execute(delete(SyncLog).where(SyncLog.id.in_(sync_ids)))
            await session.commit()


async def test_return_replay_recreates_credit_split(client):
    """A return whose original was paid 100% credit replays with the credit
    split: the target store recreates the AP debit (agel), not the drawer."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            payments=[{"method": "credit", "amount": "100.00"}],
        )
        invoice_ids.append(pur["id"])
        ret = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]},
        )
        assert ret.status_code == 201, ret.text
        ret = ret.json()
        invoice_ids.append(ret["id"])
        assert ret["payed"] == "0.00"
        assert ret["agel"] == "40.00"
        purchase_id, ret_id = pur["id"], ret["id"]

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice", SyncLog.entity_id == ret_id
                    )
                )
            ).scalar_one()
            payload = dict(row.payload)
            await _remove_return(session, invoice_id=ret_id, drug_id=drug_id, restore_qty="10")
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
        assert summary["applied"] == 1, summary

        async with SessionLocal() as session:
            replayed = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.branch_id == BRANCH_ID,
                        Invoice.invoice_no == payload["invoice_no"],
                        Invoice.kind == "purchase_return",
                    )
                )
            ).scalars().first()
            assert replayed is not None
            new_id = replayed.id
            invoice_ids.append(new_id)
            assert replayed.ref_invoice_id == purchase_id
            assert replayed.payed == Decimal("0")
            assert replayed.agel == Decimal("40.00")
            splits = (
                await session.execute(
                    select(PaymentSplit).where(PaymentSplit.invoice_id == new_id)
                )
            ).scalars().all()
            assert [(p.method, p.amount) for p in splits] == [
                ("credit", Decimal("40.00"))
            ]
        debit, credit = await _journal_totals(new_id)
        assert debit == credit == Decimal("40.00")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])