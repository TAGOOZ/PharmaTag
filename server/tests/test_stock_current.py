"""S1.7 count-sheet (ticket #13): GET /stock/current shows each branch drug with
its system qty and expiry batches (feature_stock_counting §2.1 — the counting
screen lists the balance and expiry dates)."""
from tests.stock_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def test_current_stock_lists_drug_with_batches(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        batches=[
            ("5.0000", "5.0000", "2025-01-01"),
            ("5.0000", "8.0000", "2026-01-01"),
        ],
        stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.get(
            "/api/v1/stock/current",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        item = next(i for i in items if i["drug_id"] == drug_id)
        assert item["qty"] == "10.0000"
        assert item["price"] == "10.0000"
        assert len(item["batches"]) == 2
        # FIFO ordering: expiry asc
        assert item["batches"][0]["expire"] == "2025-01-01"
        assert item["batches"][0]["qty"] == "5.0000"
        assert item["batches"][1]["expire"] == "2026-01-01"
    finally:
        await _cleanup([drug_id])


async def test_current_stock_search_filter(client):
    drug_a = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("3.0000", "5.0000", None)],
        stock_qty="3.0000",
    )
    drug_b = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("7.0000", "5.0000", None)],
        stock_qty="7.0000",
    )
    try:
        token = await _login_token(client)
        # pull both names from the API, then search by the first one's prefix
        r = await client.get(
            "/api/v1/stock/current?limit=500",
            headers={"Authorization": f"Bearer {token}"},
        )
        names = {i["drug_id"]: i["drugname"] for i in r.json()["items"]}
        name_a = names[drug_a]
        prefix = name_a.split("_")[0]  # shared namespace prefix — expect both
        g = await client.get(
            f"/api/v1/stock/current?q={prefix}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200
        found = {i["drug_id"] for i in g.json()["items"]}
        assert drug_a in found
        assert drug_b in found
    finally:
        await _cleanup([drug_a, drug_b])


async def test_current_stock_requires_auth(client):
    r = await client.get("/api/v1/stock/current")
    assert r.status_code == 401