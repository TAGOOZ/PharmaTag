"""S1.3 sales stock behavior (ticket #9): expiry-FIFO COGS, atomic rejection on
insufficient stock, and concurrency (no oversell under parallel requests)."""
import asyncio
from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import AuditLog, InvoiceLine, SyncLog
from tests.sales_test_utils import (
    _cleanup,
    _journal_totals,
    _login_token,
    _make_drug_and_stock,
    _stock_qty,
)


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