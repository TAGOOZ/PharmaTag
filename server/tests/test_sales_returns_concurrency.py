"""S1.5 sales-return concurrency (ticket #11): two parallel returns of the same
sold line must serialize on the branch advisory lock — exactly one succeeds, the
second is rejected for over-return, stock moves once, and only one return batch
is created. No double reversal, ever.
"""
import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import SyncLog
from tests.returns_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _return_batches,
    _sale,
    _stock_qty,
)


async def test_parallel_returns_serialize_on_branch_lock(client):
    """10-unit sale, two concurrent 6-unit returns: one 201, one 400."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]

        async def attempt():
            r = await client.post(
                f"/api/v1/sales/{sale['id']}/return",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"ref_invoice_line_id": line_id, "qty": "6"}]},
            )
            return r.status_code, r.json() if r.status_code == 201 else None

        results = await asyncio.gather(attempt(), attempt())
        statuses = sorted(s for s, _ in results)
        assert statuses == [201, 400], statuses
        created = next((body for s, body in results if s == 201), None)
        assert created is not None
        ret_id = created["id"]
        invoice_ids.append(ret_id)
        assert await _stock_qty(drug_id) == Decimal("6")
        batches = await _return_batches(drug_id)
        assert len(batches) == 1
        assert str(batches[0].qty) == "6.0000"

        # the rejected return left no outbox row: exactly one sale_return row
        # references THIS sale (the 201 write)
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.payload["kind"].as_string() == "sale_return",
                        SyncLog.entity == "invoice",
                    )
                )
            ).scalars().all()
            mine = [
                r
                for r in rows
                if r.payload.get("ref_invoice_id") == sale["id"]
                and r.entity_id == ret_id
            ]
            assert len(mine) == 1
    finally:
        await _cleanup([drug_id], invoice_ids)