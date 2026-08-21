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


async def test_day_profit_across_a_period_aggregates_the_window(client):
    """date_from..date_to sums every day's figures and echoes the window."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    movement_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        for datee in ("2026-01-06", "2026-01-07"):
            r = await client.post(
                "/api/v1/sales",
                headers=auth,
                json={
                    "lines": [{"drug_id": drug_id, "qty": "12"}],
                    "datee": datee,
                },
            )
            assert r.status_code == 201, r.text
            invoice_ids.append(r.json()["id"])
        mv = await client.post(
            "/api/v1/drawer/movements",
            headers=auth,
            json={
                "direction": "out",
                "reason": "expense",
                "method": "cash",
                "amount": "10.00",
                "datee": "2026-01-07",
            },
        )
        assert mv.status_code == 201, mv.text
        movement_ids.append(mv.json()["id"])

        rep = await client.get(
            "/api/v1/reports/day-profit",
            params={"date_from": "2026-01-06", "date_to": "2026-01-07"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["date_from"] == "2026-01-06"
        assert body["date_to"] == "2026-01-07"
        assert "datee" not in body
        assert body["sales_count"] == 2
        assert body["net_revenue"] == "210.52"  # 2 × 105.26
        assert body["cogs"] == "120.00"
        assert body["expenses"] == "10.00"
        assert body["net_profit"] == "80.52"

        # single-sided bound stays open-ended, not an error
        rep = await client.get(
            "/api/v1/reports/day-profit",
            params={"date_from": "2026-01-07"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["sales_count"] == 1
        assert body["expenses"] == "10.00"
    finally:
        await _cleanup([drug_id], invoice_ids, movement_ids)


async def test_day_profit_rejects_mixed_and_inverted_windows(client):
    """Mixing datee with a range is ambiguous (400); an inverted range is 400."""
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}

    mixed = await client.get(
        "/api/v1/reports/day-profit",
        params={
            "datee": "2026-01-06",
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        },
        headers=auth,
    )
    assert mixed.status_code == 400

    inverted = await client.get(
        "/api/v1/reports/day-profit",
        params={"date_from": "2026-01-31", "date_to": "2026-01-01"},
        headers=auth,
    )
    assert inverted.status_code == 400


async def test_day_profit_no_params_defaults_to_the_business_day(client):
    """ربح اليوم with no params means TODAY, never lifetime-to-date."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        # an old sale far outside the business month must not leak in
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "12"}], "datee": "2020-01-01"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "6"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        for path in ("/api/v1/reports/day-profit", "/api/v1/reports/day_profit"):
            rep = await client.get(path, headers=auth)
            assert rep.status_code == 200, rep.text
            body = rep.json()
            assert body["datee"] == business_date().isoformat(), path
            assert body["sales_count"] == 1, path
            assert body["net_revenue"] == "52.63", path
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_day_profit_ranged_payload_has_no_drawer_start(client):
    """Σ of daily opening floats is meaningless across a window — omit it."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/day-profit",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert "drawer_start" not in body
    assert "expected_cash" in body  # cash in − out stays meaningful


async def test_print_queue_rejects_mixed_day_profit_params(client):
    """A queued job mixing datee with a range could never render — 400 up front."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/reports/day_profit/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "params": {
                "datee": "2026-01-06",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
            }
        },
    )
    assert r.status_code == 400
