"""S3.3 current-stock report (ticket #25): رصيد الأصناف.

Branch stock listing with quantity and value at cost — the printable,
catalog-driven counterpart of the counting sheet (`/stock/current`).
"""
from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def test_stock_current_answers_through_the_dispatcher(client):
    """A drug with batches lists its running qty and its value at batch cost."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[
            ("12.0000", "5.0000", "2027-01-01"),
            ("8.0000", "6.0000", "2027-06-01"),
        ],
        stock_qty="20.0000",
    )
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_current",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["branch_id"] == 1
        item = next(i for i in body["items"] if i["drug_id"] == drug_id)
        assert body["count"] >= len(body["items"])
        assert body["truncated"] is False
        assert item["qty"] == "20.0000"
        # Σ batch.qty × batch.cost = 12×5 + 8×6 = 108.00
        assert item["value"] == "108.00"
    finally:
        await _cleanup([drug_id], [])


async def test_stock_current_includes_zero_qty_drugs(client):
    """A stocked-out drug still lists, with qty 0 and no phantom value."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="8.0000",
        cost_price="3.0000",
        batches=[],
        stock_qty="0.0000",
    )
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_current",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        item = next(
            i for i in rep.json()["items"] if i["drug_id"] == drug_id
        )
        assert item["qty"] == "0.0000"
        assert item["value"] == "0.00"
    finally:
        await _cleanup([drug_id], [])
