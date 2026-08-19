"""S1.3 sales money invariants (ticket #9): invoice reconciliation, per-line
VAT, payment splits, discounts and price levels.

Every money slice carries invariant tests (AGENTS.md): the journal is balanced
(SUM debit = SUM credit), and the invoice reconciles to the per-line VAT engine
(total = subtotal - discount, vat = Σ per-line vat, net = total - vat).
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AuditLog, StockBatch, SyncLog
from tests.sales_test_utils import (
    BRANCH_ID,
    _cleanup,
    _journal_totals,
    _login_token,
    _make_drug_and_stock,
    _stock_qty,
)


async def test_sale_happy_path_money_invariants(client):
    """A 14% sale of 12 units: invoice reconciles, journal balanced, stock
    expiry-FIFO, audit + outbox rows written in the same transaction."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2025-01-01"), ("10.0000", "5.0000", "2026-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])

        # invoice reconciles to the money engine (per-line VAT, half-up)
        assert body["invoice_no"].isdigit()
        assert body["subtotal"] == "120.00"
        assert body["discount"] == "0.00"
        assert body["vat"] == "14.74"
        assert body["totalvalue"] == "120.00"
        assert body["net"] == "105.26"
        assert body["payed"] == "120.00"
        assert body["agel"] == "0.00"

        line = body["lines"][0]
        assert line["qty"] == "12.0000"
        assert line["unit_price"] == "10.00"
        assert line["tax_type"] == "14%"
        assert line["vat_amount"] == "14.74"
        assert line["line_total"] == "120.00"
        assert line["cost"] == "5.00"

        # stock: 10 from the 2025 batch (expiry-FIFO) + 2 from the 2026 batch
        async with SessionLocal() as session:
            batches = (
                await session.execute(
                    select(StockBatch)
                    .where(StockBatch.drug_id == drug_id)
                    .order_by(StockBatch.id)
                )
            ).scalars().all()
            assert {str(b.expire): str(b.qty) for b in batches} == {
                "2025-01-01": "0.0000",
                "2026-01-01": "8.0000",
            }
        assert await _stock_qty(drug_id) == Decimal("8.0000")

        # journal is balanced and reflects payed/sales/vat/cogs/stock
        debit, credit = await _journal_totals(body["id"])
        assert debit == Decimal("180.00")  # 120 drawer + 60 cogs
        assert credit == Decimal("180.00")  # 105.26 sales + 14.74 vat + 60 stock
        assert debit == credit, "SUM(debit) must equal SUM(credit)"

        # audit + outbox rows landed with the sale
        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(AuditLog.branch_id == BRANCH_ID)
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
                        SyncLog.entity_id == body["id"],
                    )
                )
            ).scalars().all()
            assert len(outbox) == 1
            assert outbox[0].status == "pending"
            assert outbox[0].payload["invoice_no"] == body["invoice_no"]
            assert outbox[0].payload["totalvalue"] == "120.00"
            assert outbox[0].payload["lines"][0]["allocations"] == [
                {"batch_id": batches[0].id, "randomid": batches[0].randomid, "take": "10.0000", "cost": "5.0000", "expire": "2025-01-01"},
                {"batch_id": batches[1].id, "randomid": batches[1].randomid, "take": "2.0000", "cost": "5.0000", "expire": "2026-01-01"},
            ]
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_vat_per_line_rounding_not_aggregate(client):
    """Two 1.00 lines at 14%: per-line vat 0.12 each → 0.24 total (never the
    aggregate-rounding 0.25)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="1.0000",
        batches=[("20.0000", "0.5000", "2025-01-01")],
        stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [
                    {"drug_id": drug_id, "qty": "1"},
                    {"drug_id": drug_id, "qty": "1"},
                ]
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["subtotal"] == "2.00"
        assert body["vat"] == "0.24"
        assert body["totalvalue"] == "2.00"
        assert body["net"] == "1.76"
        assert [l["vat_amount"] for l in body["lines"]] == ["0.12", "0.12"]
        debit, credit = await _journal_totals(body["id"])
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_mixed_tax_types_per_line(client):
    """exempt + 5% + 14% lines resolve their own VAT per line (G06)."""
    exempt = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    five = await _make_drug_and_stock(
        tax_type="5%", price="100.0000",
        batches=[("10.0000", "40.0000", None)], stock_qty="10.0000",
    )
    fourteen = await _make_drug_and_stock(
        tax_type="14%", price="50.0000",
        batches=[("10.0000", "20.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [
                    {"drug_id": exempt, "qty": "1"},
                    {"drug_id": five, "qty": "1"},
                    {"drug_id": fourteen, "qty": "1"},
                ]
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        # exempt: net 10.00 vat 0 — 5%: net 95.24 vat 4.76 — 14%: net 43.86 vat 6.14
        assert body["subtotal"] == "160.00"
        assert body["vat"] == "10.90"
        assert body["totalvalue"] == "160.00"
        assert body["net"] == "149.10"
        assert [l["tax_type"] for l in body["lines"]] == ["exempt", "5%", "14%"]
        assert [l["vat_amount"] for l in body["lines"]] == ["0.00", "4.76", "6.14"]
        debit, credit = await _journal_totals(body["id"])
        assert debit == credit
    finally:
        await _cleanup([exempt, five, fourteen], invoice_ids)


async def test_sale_credit_split_payment(client):
    """cash + credit split: payed + agel = totalvalue, AR journal debit = agel."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="100.0000",
        batches=[("10.0000", "50.0000", None)],
        stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "1"}],
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
        assert debit == Decimal("150.00")  # 60 drawer + 40 AR + 50 cogs
        assert credit == Decimal("150.00")  # 100 sales + 50 stock
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_payment_mismatch_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "2"}],
                "payments": [{"method": "cash", "amount": "1.00"}],
            },
        )
        assert r.status_code == 400
        assert "payment total does not match" in r.json()["detail"]
    finally:
        await _cleanup([drug_id], [])


async def test_sale_invoice_level_discount(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="100.0000",
        batches=[("10.0000", "50.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}], "disc_percent": "10"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        # the invoice-level 10% is apportioned to the line, so the VAT base is
        # the discounted price: split_vat(90, 14%) = 78.95 / 11.05 (Egypt law:
        # taxable base = price actually paid).
        assert body["subtotal"] == "100.00"
        assert body["discount"] == "10.00"
        assert body["totalvalue"] == "90.00"
        assert body["vat"] == "11.05"
        assert body["net"] == "78.95"
        assert body["lines"][0]["line_total"] == "90.00"
        assert body["lines"][0]["vat_amount"] == "11.05"
        debit, credit = await _journal_totals(body["id"])
        assert debit == credit
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_price_levels(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000", wholesale="8.0000", cost_price="5.0000",
        batches=[("10.0000", "4.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        for level, expected in [("public", "10.00"), ("wholesale", "8.00"), ("cost", "5.00")]:
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1", "price_level": level}]},
            )
            assert r.status_code == 201, r.text
            body = r.json()
            invoice_ids.append(body["id"])
            assert body["lines"][0]["unit_price"] == expected, level
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_zero_price_giveaway_balanced(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="0.0000",
        batches=[("10.0000", "0.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["totalvalue"] == "0.00"
        assert body["payed"] == "0.00"
        debit, credit = await _journal_totals(body["id"])
        assert debit == credit == Decimal("0")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_deep_discount_keeps_journal_balanced(client):
    """A 95% discount takes the taxable line almost to zero: because the VAT
    re-splits on the discounted total, net stays non-negative and the journal
    balances (the old engine split VAT on the gross 100 → net went negative,
    the 4000 leg was skipped and the journal went out of balance)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="100.0000",
        batches=[("10.0000", "50.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}], "disc_percent": "95"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["totalvalue"] == "5.00"
        assert body["vat"] == "0.61"  # split_vat(5.00, 14%) — the discounted base
        assert body["net"] == "4.39"
        assert Decimal(body["net"]) >= 0
        # the journal is balanced even though the discount ate 95% of the line:
        # Dr drawer 5.00 + Dr cogs 50.00 vs Cr sales 4.39 + Cr VAT 0.61 + Cr stock 50.00
        debit, credit = await _journal_totals(body["id"])
        assert debit == credit == Decimal("55.00")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_discount_over_subtotal_rejected_atomically(client):
    """A 100%+ discount (10.00 line + 95% header) exceeds the subtotal → 400
    DISCOUNT_OVERFLOW and NOTHING is written: no invoice, no stock movement,
    no outbox row (the apportionment must never produce a negative line)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        async with SessionLocal() as session:
            from app.models import Invoice, SyncLog
            before_inv = set(
                (
                    await session.execute(
                        select(Invoice.id).where(Invoice.branch_id == BRANCH_ID)
                    )
                ).scalars()
            )
            before_outbox = set(
                (
                    await session.execute(
                        select(SyncLog.id).where(SyncLog.entity == "invoice")
                    )
                ).scalars()
            )
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1", "disc_percent": "10"}], "disc_percent": "95"},
        )
        assert r.status_code == 400, r.text
        assert "discount exceeds" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("10.0000")
        async with SessionLocal() as session:
            from app.models import Invoice, SyncLog
            n_inv = set(
                (
                    await session.execute(
                        select(Invoice.id).where(Invoice.branch_id == BRANCH_ID)
                    )
                ).scalars()
            )
            assert n_inv == before_inv  # no new invoice written
            n_outbox = set(
                (
                    await session.execute(
                        select(SyncLog.id).where(SyncLog.entity == "invoice")
                    )
                ).scalars()
            )
            assert n_outbox == before_outbox  # no new outbox row enqueued
    finally:
        await _cleanup([drug_id], [])