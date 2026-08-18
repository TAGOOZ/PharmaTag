"""S1.5 sales returns (ticket #11): partial return of a saved sale reverses
stock (new return batch), money/journal/balances, writes audit + outbox
atomically, snapshots the original into invoice_versions, and issues a NEW
return invoice with its own invoice_no.
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AuditLog, Invoice, InvoiceLine, InvoiceVersion, SyncLog
from tests.returns_test_utils import (
    _cleanup,
    _journal_totals,
    _login_token,
    _make_drug_and_stock,
    _return_batches,
    _sale,
    _stock_qty,
)


async def test_partial_return_reverses_everything(client):
    """Return 4 of a 10-unit 14% cash sale: stock up via a new return batch,
    journal reversed + balanced, money proportional to the original, new
    invoice_no, audit + outbox rows, invoice_versions snapshot."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(
            client, token, [{"drug_id": drug_id, "qty": "10"}]
        )
        sale_id = sale["id"]
        sale_no = sale["invoice_no"]
        orig_line_id = sale["lines"][0]["id"]
        invoice_ids.append(sale_id)
        assert await _stock_qty(drug_id) == Decimal("0.0000")

        r = await client.post(
            f"/api/v1/sales/{sale_id}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": orig_line_id, "qty": "4"}]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])

        # new return invoice with its own number, linked to the original
        assert ret["kind"] == "sale_return"
        assert ret["invoice_no"] != sale_no
        assert ret["invoice_no"].isdigit()
        assert ret["ref_invoice_id"] == sale_id
        line = ret["lines"][0]
        assert line["ref_invoice_line_id"] == orig_line_id
        assert line["qty"] == "4.0000"
        assert line["unit_price"] == "10.00"
        assert line["tax_type"] == "14%"

        # money reverses per-line at the original price: 4 × 10.00 → vat 4.91
        assert ret["subtotal"] == "40.00"
        assert ret["discount"] == "0.00"
        assert ret["vat"] == "4.91"
        assert ret["totalvalue"] == "40.00"
        assert ret["net"] == "35.09"
        assert ret["payed"] == "40.00"
        assert ret["agel"] == "0.00"

        # stock: a NEW return batch holds the 4 units; branch_stock back up
        batches = await _return_batches(drug_id)
        assert len(batches) == 1
        assert str(batches[0].qty) == "4.0000"
        assert str(batches[0].cost) == "5.0000"
        assert batches[0].typee == "return"
        assert await _stock_qty(drug_id) == Decimal("4.0000")

        # journal reversed + balanced: Dr sales/vat/stock vs Cr drawer/cogs
        debit, credit = await _journal_totals(ret["id"])
        assert debit == Decimal("60.00")  # 35.09 sales + 4.91 vat + 20 stock
        assert credit == Decimal("60.00")  # 40 drawer + 20 cogs
        assert debit == credit, "SUM(debit) must equal SUM(credit)"

        # audit + outbox rows landed with the return (G12)
        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(AuditLog.branch_id == 1)
                )
            ).scalars().all()
            entities = {a.entity for a in audits}
            assert {
                "invoices",
                "invoice_lines",
                "journals",
                "stock_batches",
                "branch_stock",
            }.issubset(entities)
            outbox = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice",
                        SyncLog.entity_id == ret["id"],
                    )
                )
            ).scalars().all()
            assert len(outbox) == 1
            assert outbox[0].status == "pending"
            assert outbox[0].payload["kind"] == "sale_return"
            assert outbox[0].payload["ref_invoice_id"] == sale_id

            # original sale snapshotted into invoice_versions
            versions = (
                await session.execute(
                    select(InvoiceVersion)
                    .where(InvoiceVersion.invoice_id == sale_id)
                    .order_by(InvoiceVersion.version_no)
                )
            ).scalars().all()
            assert len(versions) == 1
            assert versions[0].action == "sale_return"
            assert versions[0].payload["invoice_no"] == sale_no

            # return references the original sale; original untouched
            ret_row = await session.get(Invoice, ret["id"])
            assert ret_row.ref_invoice_id == sale_id
            orig = await session.get(Invoice, sale_id)
            assert orig.status == "saved"
            assert orig.totalvalue == Decimal("100.00")
    finally:
        await _cleanup([drug_id], invoice_ids)