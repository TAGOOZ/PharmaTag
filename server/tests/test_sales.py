"""S1.3 sales invoicing (ticket #9): write path + money invariants.

Every money/stock slice carries invariant tests (AGENTS.md): the journal is
balanced (SUM debit = SUM credit), the invoice reconciles to the per-line VAT
engine (total = subtotal - discount, vat = Σ per-line vat, net = total - vat),
and the stock/journal/audit/outbox writes land atomically in ONE transaction.

Tests create + clean up their own throwaway drug/batch/stock rows on branch 1
(MAIN, seed admin). Cleanup walks the FK chain (journal_lines → journals →
invoices → batches → drugs) so a mid-suite failure never blocks later deletes.
"""
import asyncio
from datetime import date
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    Balance,
    BranchStock,
    Drug,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    PaymentSplit,
    StockBatch,
    SyncLog,
    User,
)

BRANCH_ID = 1

_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"__t2_sale_{tag}_{_seq[0]}__"


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _make_drug_and_stock(
    *,
    tax_type: str = "14%",
    price: str = "10.0000",
    wholesale: str = "8.0000",
    cost_price: str = "5.0000",
    batches: Optional[list[tuple[str, str, Optional[str]]]] = None,
    stock_qty: str = "20.0000",
) -> int:
    """Create a throwaway drug + branch_stock + batches; returns drug_id."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq("drug"),
            tax_type=tax_type,
            price=Decimal(price),
            price_wholesale=Decimal(wholesale),
            price_cost=Decimal(cost_price),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=BRANCH_ID, drug_id=drug_id, qty=Decimal(stock_qty), minimum=0
            )
        )
        for i, (qty, cost, expire) in enumerate(batches or []):
            session.add(
                StockBatch(
                    branch_id=BRANCH_ID,
                    drug_id=drug_id,
                    randomid=f"{_uniq('b')}{i}",
                    qty=Decimal(qty),
                    cost=Decimal(cost),
                    expire=date.fromisoformat(expire) if expire else None,
                )
            )
        await session.commit()
        return drug_id


async def _cleanup(drug_ids: list[int], invoice_ids: list[int]) -> None:
    async with SessionLocal() as session:
        for iid in invoice_ids:
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
            await session.execute(delete(Balance).where(Balance.branch_id == BRANCH_ID))
            await session.execute(
                delete(PaymentSplit).where(PaymentSplit.invoice_id == iid)
            )
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id == iid)
            )
            await session.execute(
                delete(SyncLog).where(SyncLog.entity_id == iid)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.entity_id == iid)
            )
            await session.execute(delete(Invoice).where(Invoice.id == iid))
        for drug_id in drug_ids:
            await session.execute(
                delete(StockBatch).where(StockBatch.drug_id == drug_id)
            )
            await session.execute(
                delete(BranchStock).where(BranchStock.drug_id == drug_id)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.drug_id == drug_id)
            )
            await session.execute(delete(Drug).where(Drug.id == drug_id))
        await session.commit()


async def _stock_qty(drug_id: int) -> Decimal:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == BRANCH_ID,
                    BranchStock.drug_id == drug_id,
                )
            )
        ).scalar_one()
        return row.qty


async def _journal_totals(invoice_id: int) -> tuple[Decimal, Decimal]:
    async with SessionLocal() as session:
        journal = (
            await session.execute(
                select(Journal).where(Journal.ref_invoice_id == invoice_id)
            )
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


# ---------------------------------------------------------------------------
# happy path + money invariants
# ---------------------------------------------------------------------------


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


async def test_sale_expiry_fifo_cross_batch_cogs(client):
    """Two batches with different costs: allocation walks expiry, COGS = Σ take×cost."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        batches=[("10.0000", "5.0000", "2025-01-01"), ("10.0000", "8.0000", "2026-01-01")],
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
        # COGS = 10×5.00 + 2×8.00 = 66.00 → unit cost 66/12 = 5.50
        assert body["lines"][0]["cost"] == "5.50"
        debit, credit = await _journal_totals(body["id"])
        assert debit == Decimal("186.00")  # 120 drawer + 66 cogs
        assert credit == Decimal("186.00")  # 120 sales + 66 stock
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
        # VAT is per-line on the gross (100 → 12.28); the invoice-level 10%
        # discount is a straight deduction from the inclusive total.
        assert body["subtotal"] == "100.00"
        assert body["discount"] == "10.00"
        assert body["totalvalue"] == "90.00"
        assert body["vat"] == "12.28"
        assert body["net"] == "77.72"
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


async def test_sale_invoice_numbers_monotonic(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("20.0000", "5.0000", None)], stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        numbers = []
        for _ in range(2):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            body = r.json()
            invoice_ids.append(body["id"])
            numbers.append(int(body["invoice_no"]))
        assert numbers[1] > numbers[0], "invoice numbers must be monotonic"
        assert len(set(numbers)) == 2
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_get_list_and_detail(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]
        invoice_ids.append(sale_id)

        lst = await client.get(
            "/api/v1/sales", headers={"Authorization": f"Bearer {token}"}
        )
        assert lst.status_code == 200
        assert any(s["id"] == sale_id for s in lst.json()["sales"])

        det = await client.get(
            f"/api/v1/sales/{sale_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert det.status_code == 200
        body = det.json()
        assert body["invoice_no"].isdigit()
        assert body["journal"]["balanced"] is True
        assert body["journal"]["debit_total"] == body["journal"]["credit_total"]
        assert body["journal"]["debit_total"] == "30.00"  # 20 drawer + 10 cogs
    finally:
        await _cleanup([drug_id], invoice_ids)


# ---------------------------------------------------------------------------
# edge cases (required before close — AGENTS.md)
# ---------------------------------------------------------------------------


async def test_sale_insufficient_stock_rejected_atomically(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 409
        # nothing persisted: stock unchanged, no line/audit/outbox for the drug
        assert await _stock_qty(drug_id) == Decimal("10.0000")
        async with SessionLocal() as session:
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(InvoiceLine)
                    .where(InvoiceLine.drug_id == drug_id)
                )
            ).scalar_one()
            assert n == 0
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.drug_id == drug_id)
                )
            ).scalar_one()
            assert n == 0
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(SyncLog)
                    .where(SyncLog.entity == "invoice")
                )
            ).scalar_one()
            assert n == 0
    finally:
        await _cleanup([drug_id], [])


async def test_sale_second_line_insufficient_rolls_back_first_line(client):
    """A failure on line 2 rolls back line 1's decrement + everything else."""
    drug_a = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    drug_b = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("2.0000", "5.0000", None)], stock_qty="2.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [
                    {"drug_id": drug_a, "qty": "5"},
                    {"drug_id": drug_b, "qty": "5"},  # exceeds the 2-unit batch
                ]
            },
        )
        assert r.status_code == 409
        assert await _stock_qty(drug_a) == Decimal("10.0000")
        assert await _stock_qty(drug_b) == Decimal("2.0000")
        async with SessionLocal() as session:
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(InvoiceLine)
                    .where(InvoiceLine.drug_id.in_([drug_a, drug_b]))
                )
            ).scalar_one()
            assert n == 0
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.drug_id.in_([drug_a, drug_b]))
                )
            ).scalar_one()
            assert n == 0
    finally:
        await _cleanup([drug_a, drug_b], [])


async def test_sale_zero_or_negative_qty_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        for qty in ["0", "-3"]:
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": qty}]},
            )
            assert r.status_code == 400, qty
        assert await _stock_qty(drug_id) == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], [])


async def test_sale_empty_lines_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": []},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id], [])


async def test_sale_unknown_drug_404(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"drug_id": 99999999, "qty": "1"}]},
    )
    assert r.status_code == 404


async def test_sale_inactive_drug_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    async with SessionLocal() as session:
        drug = await session.get(Drug, drug_id)
        drug.active = False
        await session.commit()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            drug = await session.get(Drug, drug_id)
            drug.active = True
            await session.commit()
        await _cleanup([drug_id], [])


async def test_sale_discount_exceeds_total_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "2"}], "disc_percent": "200"},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id], [])


async def test_sale_unauthenticated_401(client):
    r = await client.post(
        "/api/v1/sales",
        json={"lines": [{"drug_id": 1, "qty": "1"}]},
    )
    assert r.status_code == 401


async def _make_user(username: str, permission_level: int, branch_id=None, active=True) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash="x",
            permission_level=permission_level,
            branch_id=branch_id,
            active=active,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


def _token_for(user_id: int, branch_id) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=branch_id or 0, roles=[], permission_level=0
    )


async def test_sale_forbidden_when_no_permission(client):
    """A level-0 user holds no sale.create (legacy floor is level 1)."""
    user_id = await _make_user(_uniq("user"), permission_level=0, branch_id=1)
    try:
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
            json={"lines": [{"drug_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 403
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_sale_user_without_branch_rejected(client):
    user_id = await _make_user(_uniq("user"), permission_level=9, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
            json={"lines": [{"drug_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_sale_cross_branch_read_404(client):
    """A sale on branch 1 is invisible to a branch-2 user (branch-scoped read)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    branch_id = None
    user_id = None
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]
        invoice_ids.append(sale_id)

        async with SessionLocal() as session:
            Branch = __import__("app.models", fromlist=["Branch"]).Branch
            branch = Branch(
                pharmacyid=f"t2ph{_seq[0]}",
                mobile="0",
                pharname="Other Branch",
            )
            session.add(branch)
            await session.flush()
            branch_id = branch.id
            user = User(
                username=_uniq("user"),
                pass_hash="x",
                permission_level=9,
                branch_id=branch_id,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        other = await client.get(
            f"/api/v1/sales/{sale_id}",
            headers={"Authorization": f"Bearer {_token_for(user_id, branch_id)}"},
        )
        assert other.status_code == 404
    finally:
        async with SessionLocal() as session:
            if user_id:
                await session.execute(delete(User).where(User.id == user_id))
            if branch_id:
                await session.execute(
                    delete(__import__("app.models", fromlist=["Branch"]).Branch).where(
                        __import__("app.models", fromlist=["Branch"]).Branch.id == branch_id
                    )
                )
            await session.commit()
        await _cleanup([drug_id], invoice_ids)


async def test_sale_concurrent_sales_no_oversell(client):
    """Two concurrent 7-unit sales on a 10-unit drug: one succeeds, one gets 409,
    and stock never goes negative."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)

        async def sell():
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "7"}]},
            )
            return r.status_code, r.json().get("id")

        codes, ids = zip(*await asyncio.gather(sell(), sell()))
        assert sorted(codes) == [201, 409]
        invoice_ids.extend(i for i in ids if i)
        assert await _stock_qty(drug_id) == Decimal("3.0000")
    finally:
        await _cleanup([drug_id], invoice_ids)