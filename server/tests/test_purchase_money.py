"""S1.4 purchase money invariants (ticket #10): VAT-inclusive net split,
stock-up batches at net cost, supplier payable (AP), payment splits, audit +
outbox, and the balanced journal.

Every money slice carries invariant tests (AGENTS.md): SUM(debit) ==
SUM(credit) per journal, and the invoice reconciles to the per-line VAT engine
(total = subtotal - discount, vat = Σ per-line vat, net = total - vat). The
batch cost stored on the new stock_batches row is the NET (ex-VAT) unit cost so
later sale COGS never includes reclaimable input VAT.
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AuditLog, Invoice, InvoiceLine, Party, SyncLog
from tests.purchase_test_utils import (
    _batches,
    _cleanup,
    _delete_other_branch,
    _journal_source,
    _journal_totals,
    _login_token,
    _make_drug,
    _make_other_branch,
    _make_supplier,
    _stock_qty,
)


async def test_purchase_happy_path_money_invariants(client):
    """A 14% purchase of 10 units at 10.00: net 87.72 / vat 12.28, batch lands
    at net unit cost 8.7720, journal balanced, audit + outbox written."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        # invoice reconciles to the money engine (per-line VAT, half-up)
        assert body["invoice_no"].isdigit()
        assert body["subtotal"] == "100.00"
        assert body["discount"] == "0.00"
        assert body["vat"] == "12.28"
        assert body["totalvalue"] == "100.00"
        assert body["net"] == "87.72"
        assert body["payed"] == "100.00"
        assert body["agel"] == "0.00"

        line = body["lines"][0]
        assert line["qty"] == "10.0000"
        assert line["unit_price"] == "10.00"  # gross unit cost as charged
        assert line["cost"] == "8.7720"  # net (ex-VAT) unit cost on the batch
        assert line["tax_type"] == "14%"
        assert line["vat_amount"] == "12.28"
        assert line["line_total"] == "100.00"

        # stock: one NEW purchase batch landed at net unit cost, branch_stock up
        batches = await _batches(drug_id)
        assert len(batches) == 1
        batch = batches[0]
        assert batch.qty == Decimal("10.0000")
        assert batch.cost == Decimal("8.7720")
        assert batch.price == Decimal("10.0000")
        assert batch.vat == Decimal("14.00")
        assert batch.vatvalue == Decimal("12.28")
        assert batch.totalwithvat == Decimal("100.00")
        assert batch.typee == "purchase"
        assert await _stock_qty(drug_id) == Decimal("10.0000")

        # journal is balanced: Dr stock net + Dr input VAT = Cr drawer payed
        debit, credit = await _journal_totals(body["id"])
        assert debit == Decimal("100.00")  # 87.72 stock + 12.28 input VAT
        assert credit == Decimal("100.00")  # 100.00 drawer
        assert debit == credit, "SUM(debit) must equal SUM(credit)"
        assert await _journal_source(body["id"]) == "purchase"

        # audit + outbox rows landed with the purchase
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
                "parties",
            }.issubset(entities)
            outbox = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "invoice",
                        SyncLog.entity_id == body["id"],
                    )
                )
            ).scalars().all()
            assert len(outbox) == 1
            assert outbox[0].status == "pending"
            assert outbox[0].payload["kind"] == "purchase"
            assert outbox[0].payload["invoice_no"] == body["invoice_no"]
            assert outbox[0].payload["totalvalue"] == "100.00"
            assert outbox[0].payload["lines"][0]["unit_cost"] == "8.7720"
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_credit_split_posts_supplier_payable(client):
    """cash 60 + credit 40: payed + agel = totalvalue and the AP leg of the
    journal is exactly the credit portion (supplier payable)."""
    drug_id = await _make_drug(tax_type="exempt", active=True)
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
                "payments": [
                    {"method": "cash", "amount": "60.00"},
                    {"method": "credit", "amount": "40.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["payed"] == "60.00"
        assert body["agel"] == "40.00"
        assert body["totalvalue"] == "100.00"
        assert {p["method"]: p["amount"] for p in body["payments"]} == {
            "cash": "60.00",
            "credit": "40.00",
        }
        debit, credit = await _journal_totals(body["id"])
        assert debit == Decimal("100.00")  # 100 stock (exempt, net == total)
        assert credit == Decimal("100.00")  # 60 drawer + 40 AP
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_party_scoped_to_branch(client):
    """The purchase is bound to the caller's branch AND to a supplier party of
    the SAME branch — a supplier from another branch is rejected."""
    drug_id = await _make_drug(tax_type="exempt")
    other_branch = await _make_other_branch()
    other_supplier_id = await _make_supplier(branch_id=other_branch)
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": other_supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 404
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], invoice_ids, [other_supplier_id])
        await _delete_other_branch(other_branch)


async def test_purchase_mixed_tax_types_net_split(client):
    """exempt + 5% + 14% purchase lines: each resolves its own net/vat; the
    batch cost stored is per-line net; journal balances to the gross total."""
    exempt = await _make_drug(tax_type="exempt")
    five = await _make_drug(tax_type="5%")
    fourteen = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [
                    {"drug_id": exempt, "qty": "1", "unit_cost": "10.0000"},
                    {"drug_id": five, "qty": "1", "unit_cost": "100.0000"},
                    {"drug_id": fourteen, "qty": "1", "unit_cost": "50.0000"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        # exempt: 10.00 net / 0 vat — 5%: 95.24 / 4.76 — 14%: 43.86 / 6.14
        assert body["subtotal"] == "160.00"
        assert body["vat"] == "10.90"
        assert body["totalvalue"] == "160.00"
        assert body["net"] == "149.10"
        assert [l["tax_type"] for l in body["lines"]] == ["exempt", "5%", "14%"]
        assert [l["vat_amount"] for l in body["lines"]] == ["0.00", "4.76", "6.14"]
        assert [l["cost"] for l in body["lines"]] == ["10.0000", "95.2400", "43.8600"]
        debit, credit = await _journal_totals(body["id"])
        assert debit == Decimal("160.00")
        assert credit == Decimal("160.00")
        assert debit == credit
    finally:
        await _cleanup([exempt, five, fourteen], invoice_ids, [supplier_id])


async def test_purchase_zero_cost_giveaway_balanced(client):
    """A zero-cost received line (sample/donation) still lands in stock with a
    zero-cost batch and a balanced journal."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "5", "unit_cost": "0.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["totalvalue"] == "0.00"
        assert body["payed"] == "0.00"
        assert body["net"] == "0.00"
        debit, credit = await _journal_totals(body["id"])
        assert debit == credit == Decimal("0")
        assert await _stock_qty(drug_id) == Decimal("5.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_invoice_level_discount(client):
    """An invoice-level discount reduces the total; per-line VAT is still
    computed on the gross (never re-apportioned)."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "100.0000"}],
                "disc_percent": "10",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["subtotal"] == "100.00"
        assert body["discount"] == "10.00"
        assert body["totalvalue"] == "90.00"
        assert body["vat"] == "12.28"  # per-line on the gross 100
        assert body["net"] == "77.72"
        debit, credit = await _journal_totals(body["id"])
        assert debit == Decimal("90.00")  # 77.72 stock + 12.28 vat
        assert credit == Decimal("90.00")  # 90.00 drawer
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_reads_back_party_and_lines(client):
    """GET /purchases/{id} returns the invoice with its supplier party and lines."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier(namee="مورد الاختبار")
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "3", "unit_cost": "4.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        g = await client.get(
            f"/api/v1/purchases/{body['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200
        got = g.json()
        assert got["party_id"] == supplier_id
        assert got["totalvalue"] == "12.00"
        assert got["lines"][0]["drug_id"] == drug_id
        assert got["journal"]["balanced"] is True
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])