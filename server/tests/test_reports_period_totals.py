"""S1.9 sales/purchases period-totals report (ticket #15): RPT-OP01/OP03.

Over a date range the report counts + totals each invoice kind (sale, sale
return, purchase, purchase return) and nets the returns out. A range with no
documents is zeros. Dates are inclusive on both ends.
"""
from app.core.time import business_date

from tests.reports_test_utils import (
    _login_token,
    _make_drug_and_stock,
    _cleanup,
)


async def _make_supplier(client, token: str) -> int:
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "supplier", "namee": "t2 rep supplier"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_period_totals_aggregate_sales_and_purchases(client):
    """A sale + a purchase in the range show counts and totals per kind."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2026-01-01")],
    )
    invoice_ids: list[int] = []
    supplier_id = None
    try:
        token = await _login_token(client)
        supplier_id = await _make_supplier(client, token)

        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        assert r.json()["totalvalue"] == "120.00"

        p = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [
                    {
                        "drug_id": drug_id,
                        "qty": "10",
                        "unit_cost": "4.0000",
                        "expire": "2026-12-31",
                    }
                ],
            },
        )
        assert p.status_code == 201, p.text
        invoice_ids.append(p.json()["id"])
        assert p.json()["totalvalue"] == "45.60"

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/period-totals",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        kinds = body["kinds"]
        assert kinds["sale"] == {
            "count": 1, "total": "120.00", "vat": "14.74", "discount": "0.00"
        }
        assert kinds["sale_return"]["count"] == 0
        assert kinds["purchase"] == {
            "count": 1, "total": "45.60", "vat": "5.60", "discount": "0.00"
        }
        assert kinds["purchase_return"]["count"] == 0
        assert body["net_sales"] == "120.00"
        assert body["net_purchases"] == "45.60"
        assert body["net_vat_sales"] == "14.74"
    finally:
        await _cleanup([drug_id], invoice_ids)
        if supplier_id:
            from sqlalchemy import delete
            from app.core.db import SessionLocal
            from app.models import Party

            async with SessionLocal() as session:
                await session.execute(delete(Party).where(Party.id == supplier_id))
                await session.commit()


async def test_period_totals_empty_range_is_zeros(client):
    """A range with no invoices is zeroed per kind."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/period-totals",
        params={"date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    for kind in ("sale", "sale_return", "purchase", "purchase_return"):
        assert body["kinds"][kind] == {
            "count": 0, "total": "0.00", "vat": "0.00", "discount": "0.00"
        }
    assert body["net_sales"] == "0.00"
    assert body["net_purchases"] == "0.00"


async def test_period_totals_respect_date_bounds(client):
    """An invoice outside the range is excluded (inclusive bounds)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000", batches=[("20.0000", "5.0000", None)]
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
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/period-totals",
            params={"date_from": "2050-01-01", "date_to": "2050-01-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        assert rep.json()["kinds"]["sale"]["count"] == 0
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_period_totals_respect_single_sided_bounds(client):
    """A single bound (only date_from or only date_to) still filters."""
    from datetime import date, timedelta

    from app.core.time import business_date

    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000", batches=[("20.0000", "5.0000", None)]
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
        invoice_ids.append(r.json()["id"])

        today = business_date()
        tomorrow = (today + timedelta(days=1)).isoformat()
        yesterday = (today - timedelta(days=1)).isoformat()

        from_only = await client.get(
            "/api/v1/reports/period-totals",
            params={"date_from": tomorrow},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert from_only.status_code == 200, from_only.text
        assert from_only.json()["kinds"]["sale"]["count"] == 0

        to_only = await client.get(
            "/api/v1/reports/period-totals",
            params={"date_to": yesterday},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert to_only.status_code == 200, to_only.text
        assert to_only.json()["kinds"]["sale"]["count"] == 0

        open_range = await client.get(
            "/api/v1/reports/period-totals",
            params={"date_from": yesterday},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert open_range.status_code == 200, open_range.text
        assert open_range.json()["kinds"]["sale"]["count"] == 1
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_period_totals_inverted_date_range_rejected(client):
    """date_from after date_to is a 400, not a silent empty report."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/period-totals",
        params={"date_from": "2026-01-10", "date_to": "2026-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 400


async def test_period_totals_html_renders_printable(client):
    """format=html returns a printable A4 page carrying the period figures."""
    token = await _login_token(client)
    html = await client.get(
        "/api/v1/reports/period-totals",
        params={"format": "html", "date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "ملخص المبيعات والمشتريات" in html.text