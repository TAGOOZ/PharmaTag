"""S3.3 minimum-based needs report (ticket #25): احتياجات الطلب.

The S1.9 below-minimum shortage list extended with a suggested order
quantity — max(minimum − qty, 0) — and the latest purchase cost, so the
sheet doubles as an order worksheet (RPT-ST01/ST03 shape). Sales-rate
auto-order suggestions are explicitly OUT of scope here: they belong to
the chain auto-order engine (#33 / F06.3).
"""
from tests.purchase_test_utils import _cleanup as _cleanup_purchase_chain
from tests.purchase_test_utils import _make_supplier
from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def test_needs_suggests_minimum_minus_qty(client):
    """A drug at qty 4 with minimum 10 suggests ordering 6; drugs at or
    above their minimum never appear."""
    low = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="4.0000",
        stock_qty="4.0000",
        minimum="10.0000",
    )
    ok = await _make_drug_and_stock(
        tax_type="exempt",
        price="8.0000",
        cost_price="3.0000",
        stock_qty="12.0000",
        minimum="10.0000",
    )
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        # a real purchase lot (cost 7) + an older one (cost 5): latest wins
        for unit_cost in ("5.0000", "7.0000"):
            r = await client.post(
                "/api/v1/purchases",
                headers=auth,
                json={
                    "supplier_id": supplier_id,
                    "lines": [{"drug_id": low, "qty": "1", "unit_cost": unit_cost}],
                },
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/stock_needs",
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        items = {i["drug_id"]: i for i in body["items"]}

        assert low in items
        row = items[low]
        # the two test lots raised stock from 4 to 6
        assert row["qty"] == "6.0000"
        assert row["minimum"] == "10.0000"
        assert row["suggested_order"] == "4.0000"
        # latest purchase lot's cost (max id), not the older one, not master
        assert row["last_cost"] == "7.0000"
        assert ok not in items

        # needs count == the below-minimum count of the underlying engine
        mini = await client.get(
            "/api/v1/reports/stock-minimum",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert mini.status_code == 200, mini.text
        assert body["count"] == mini.json()["count"]
    finally:
        await _cleanup_purchase_chain([low], invoice_ids, [supplier_id])
        await _cleanup([ok], [])


async def test_needs_boundary_at_minimum_not_listed(client):
    """qty == minimum is NOT a shortage; suggested order can't go negative."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="5.0000",
        cost_price="2.0000",
        stock_qty="7.0000",
        minimum="7.0000",
    )
    zero_min = await _make_drug_and_stock(
        tax_type="14%",
        price="5.0000",
        cost_price="2.0000",
        stock_qty="3.0000",
        minimum="0.0000",
    )
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_needs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        ids = {i["drug_id"] for i in rep.json()["items"]}
        assert drug_id not in ids
        assert zero_min not in ids
    finally:
        await _cleanup([drug_id, zero_min], [])
