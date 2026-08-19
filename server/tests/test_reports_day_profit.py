"""S1.9 day profit report (ticket #15): ربح اليوم matches the day ledger.

After a real sale (and an expense movement), the report's sales_net, cogs,
expenses, net_profit and VAT must match what the drawer day ledger computes
(so report and day close can never disagree). A day with no data returns
zeros. `format=html` renders a printable page.
"""
from app.core.time import business_date

from tests.reports_test_utils import (
    _login_token,
    _make_drug_and_stock,
    _cleanup,
)

EXPECTED_TOTAL = "120.00"
EXPECTED_VAT = "14.74"
EXPECTED_COGS = "60.00"
EXPECTED_EXPENSES = "10.00"


async def test_day_profit_totals_match_a_real_sale(client):
    """A cash sale + expense movement produce the exact ledger figures."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2026-01-01")],
    )
    invoice_ids: list[int] = []
    movement_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        assert r.json()["totalvalue"] == EXPECTED_TOTAL
        assert r.json()["vat"] == EXPECTED_VAT

        mv = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "direction": "out",
                "reason": "expense",
                "method": "cash",
                "amount": EXPECTED_EXPENSES,
            },
        )
        assert mv.status_code == 201, mv.text
        movement_ids.append(mv.json()["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/day-profit",
            params={"datee": today},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["datee"] == today
        assert body["sales_count"] == 1
        assert body["sales_returns_count"] == 0
        assert body["net_revenue"] == "105.26"
        assert body["cogs"] == EXPECTED_COGS
        assert body["expenses"] == EXPECTED_EXPENSES
        assert body["net_profit"] == "35.26"
        assert body["discounts"] == "0.00"
        assert body["vat_sales"] == EXPECTED_VAT
        assert body["net_cash"] == "120.00"
    finally:
        await _cleanup([drug_id], invoice_ids, movement_ids)


async def test_day_profit_empty_day_returns_zeros(client):
    """A day with no documents is a zeroed ledger, not an error."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/day-profit",
        params={"datee": "2000-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert body["sales_count"] == 0
    assert body["net_revenue"] == "0.00"
    assert body["cogs"] == "0.00"
    assert body["net_profit"] == "0.00"


async def test_day_profit_html_renders_printable(client):
    """format=html returns a black-on-white printable A4 page with the totals."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", None)],
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "5"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        html = await client.get(
            "/api/v1/reports/day-profit",
            params={"format": "html"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert html.status_code == 200
        assert html.headers["content-type"].startswith("text/html")
        assert "ربح اليوم" in html.text
        assert "50.00" in html.text  # exempt: total == net
    finally:
        await _cleanup([drug_id], invoice_ids)
