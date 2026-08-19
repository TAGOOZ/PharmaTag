"""S1.9 stock-below-minimum report (ticket #15): RPT-ST01 النواقص.

Only drugs whose current qty is strictly below the reorder point appear;
shortage = minimum − qty; rows sort by shortage descending; drugs above or at
the minimum are excluded.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import BranchStock, Drug

from tests.reports_test_utils import (
    _login_token,
    _uniq,
    _cleanup,
)


async def _make_below_drug(name: str, *, qty: str, minimum: str) -> int:
    """Create a throwaway drug + branch_stock with the given qty/minimum."""
    async with SessionLocal() as session:
        drug = Drug(
            drugname=_uniq(name),
            tax_type="exempt",
            price=Decimal("10.0000"),
        )
        session.add(drug)
        await session.flush()
        drug_id = drug.id
        session.add(
            BranchStock(
                branch_id=1,
                drug_id=drug_id,
                qty=Decimal(qty),
                minimum=Decimal(minimum),
            )
        )
        await session.commit()
        return drug_id


async def test_stock_minimum_lists_only_below_minimum(client):
    """Below-min drugs appear with shortage = min − qty, sorted desc."""
    low_id = await _make_below_drug("low", qty="3.0000", minimum="10.0000")
    high_id = await _make_below_drug("high", qty="5.0000", minimum="6.0000")
    at_min_id = await _make_below_drug("atmin", qty="5.0000", minimum="5.0000")
    above_id = await _make_below_drug("above", qty="20.0000", minimum="5.0000")
    try:
        token = await _login_token(client)
        r = await client.get(
            "/api/v1/reports/stock-minimum",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        items = body["items"]
        # at-min and above excluded
        assert {item["drug_id"] for item in items} == {low_id, high_id}
        assert body["count"] == 2
        # shortage = minimum - qty
        by_id = {item["drug_id"]: item for item in items}
        assert by_id[low_id]["shortage"] == "7.0000"
        assert by_id[high_id]["shortage"] == "1.0000"
        # sorted by shortage desc: low first
        assert items[0]["drug_id"] == low_id
        assert items[0]["qty"] == "3.0000"
        assert items[0]["minimum"] == "10.0000"
        assert items[0]["price"] == "10.0000"
    finally:
        await _cleanup([low_id, high_id, at_min_id, above_id], [])


async def test_stock_minimum_empty_when_none_below(client):
    """No drugs below minimum -> empty list, count 0."""
    ok_id = await _make_below_drug("ok", qty="20.0000", minimum="10.0000")
    try:
        token = await _login_token(client)
        r = await client.get(
            "/api/v1/reports/stock-minimum",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 0
        assert body["items"] == []
    finally:
        await _cleanup([ok_id], [])


async def test_stock_minimum_truncation_surfaces_flag_and_true_count(client):
    """Over the 1000-item cap: truncated=true and count is the true total."""
    created_ids: list[int] = []
    async with SessionLocal() as session:
        drugs = [
            Drug(
                drugname=_uniq(f"bulk{i}"),
                tax_type="exempt",
                price=Decimal("1.0000"),
            )
            for i in range(1001)
        ]
        session.add_all(drugs)
        await session.flush()
        created_ids = [d.id for d in drugs]
        session.add_all(
            BranchStock(
                branch_id=1,
                drug_id=d.id,
                qty=Decimal("1.0000"),
                minimum=Decimal("5.0000"),
            )
            for d in drugs
        )
        await session.commit()
    try:
        token = await _login_token(client)
        r = await client.get(
            "/api/v1/reports/stock-minimum",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["truncated"] is True
        assert body["count"] == 1001
        assert len(body["items"]) == 1000
    finally:
        await _cleanup(created_ids, [])


async def test_stock_minimum_html_renders_printable(client):
    """format=html returns a printable A4 shortage page."""
    low_id = await _make_below_drug("low", qty="3.0000", minimum="10.0000")
    try:
        token = await _login_token(client)
        html = await client.get(
            "/api/v1/reports/stock-minimum",
            params={"format": "html"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert html.status_code == 200
        assert html.headers["content-type"].startswith("text/html")
        assert "النواقص" in html.text
        assert "7.0000" in html.text
    finally:
        await _cleanup([low_id], [])