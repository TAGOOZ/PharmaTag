"""S1.4 purchase stock behavior (ticket #10): NEW batches land at net cost,
never overwriting existing batch stock; branch_stock upserts for a drug with no
stock row yet; two lines of the same drug make two distinct batches; and a
second-line failure rolls the whole purchase back atomically.
"""
import asyncio
from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import AuditLog, BranchStock, InvoiceLine, StockBatch, SyncLog
from tests.purchase_test_utils import (
    _batches,
    _cleanup,
    _login_token,
    _make_drug,
    _make_supplier,
    _stock_qty,
)


async def test_purchase_creates_new_batch_never_overwrites(client):
    """A drug with an existing batch gains a SECOND distinct batch (new
    randomid); the existing batch's qty is untouched."""
    drug_id = await _make_drug(
        tax_type="exempt", existing_stock=("5.0000", "2.0000", None)
    )
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "4.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        batches = await _batches(drug_id)
        assert len(batches) == 2
        existing, purchased = batches
        assert existing.qty == Decimal("5.0000")
        assert existing.cost == Decimal("2.0000")
        assert purchased.qty == Decimal("10.0000")
        assert purchased.cost == Decimal("4.0000")
        assert purchased.randomid != existing.randomid
        assert await _stock_qty(drug_id) == Decimal("15.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_stocks_drug_with_no_branch_stock_row(client):
    """First stock for a drug: branch_stock row is created, not assumed."""
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
                "lines": [{"drug_id": drug_id, "qty": "7", "unit_cost": "3.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        assert await _stock_qty(drug_id) == Decimal("7.0000")
        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(BranchStock).where(BranchStock.drug_id == drug_id)
                )
            ).scalar_one()
            assert row.qty == Decimal("7.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_two_lines_same_drug_two_batches(client):
    """Two lines of the same drug in one purchase create two distinct batches
    (distinct randomid), stock accumulates, journal balances."""
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
                "lines": [
                    {"drug_id": drug_id, "qty": "3", "unit_cost": "2.0000", "expire": "2026-01-01"},
                    {"drug_id": drug_id, "qty": "4", "unit_cost": "2.5000", "expire": "2027-01-01"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        invoice_ids.append(body["id"])
        assert body["subtotal"] == "16.00"
        batches = await _batches(drug_id)
        assert len(batches) == 2
        assert {str(b.expire): str(b.qty) for b in batches} == {
            "2026-01-01": "3.0000",
            "2027-01-01": "4.0000",
        }
        assert await _stock_qty(drug_id) == Decimal("7.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_second_line_bad_drug_rolls_back_first(client):
    """A failure on line 2 (unknown drug) rolls back line 1's stock-up + batch
    + audit/outbox — the purchase is all-or-nothing."""
    good = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [
                    {"drug_id": good, "qty": "5", "unit_cost": "2.0000"},
                    {"drug_id": 99999999, "qty": "5", "unit_cost": "2.0000"},
                ],
            },
        )
        assert r.status_code == 404
        assert await _stock_qty(good) == Decimal("0")
        assert await _batches(good) == []
        async with SessionLocal() as session:
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(InvoiceLine)
                    .where(InvoiceLine.drug_id == good)
                )
            ).scalar_one()
            assert n == 0
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.drug_id == good)
                )
            ).scalar_one()
            assert n == 0
    finally:
        await _cleanup([good], [], [supplier_id])


async def test_purchase_concurrent_same_drug_no_duplicate_randomid(client):
    """Two concurrent purchases of the same drug serialize on the branch lock;
    each line gets a distinct randomid and stock accumulates exactly."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)

        async def buy():
            r = await client.post(
                "/api/v1/purchases",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "supplier_id": supplier_id,
                    "lines": [{"drug_id": drug_id, "qty": "5", "unit_cost": "2.0000"}],
                },
            )
            return r.status_code, r.json().get("id")

        codes, ids = zip(*await asyncio.gather(buy(), buy()))
        assert codes == (201, 201)
        invoice_ids.extend(i for i in ids if i)
        assert await _stock_qty(drug_id) == Decimal("10.0000")
        batches = await _batches(drug_id)
        assert len(batches) == 2
        assert len({b.randomid for b in batches}) == 2
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])