"""S3.1 report framework (ticket #23): the generic report engine.

One dispatcher renders ANY active catalog row: `GET /api/v1/reports/{code}`
answers JSON by default, or a black-on-white printable page with
`format=html` (plan/09 P06 — theme never leaks into print). `paper`
selects A4/A5 (@page size). Unknown or deactivated codes are 404.
"""
from sqlalchemy import text

from app.core.db import SessionLocal
from tests.reports_test_utils import _login_token


async def _set_active(code: str, active: bool) -> None:
    async with SessionLocal() as session:
        await session.execute(
            text("UPDATE report_catalog SET active = :a WHERE code = :c"),
            {"a": active, "c": code},
        )
        await session.commit()


async def test_unknown_code_is_404(client):
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/no_such_report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


async def test_deactivated_code_is_404(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        await _set_active("stock_minimum", False)
        r = await client.get("/api/v1/reports/stock_minimum", headers=headers)
        assert r.status_code == 404
        # the menu hides it too
        menu = await client.get("/api/v1/reports", headers=headers)
        assert "stock_minimum" not in {x["code"] for x in menu.json()["reports"]}
    finally:
        await _set_active("stock_minimum", True)


async def test_generic_json_matches_the_legacy_endpoint(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    legacy = await client.get(
        "/api/v1/reports/day-profit", headers=headers
    )
    generic = await client.get("/api/v1/reports/day_profit", headers=headers)
    assert legacy.status_code == generic.status_code == 200
    assert generic.json() == legacy.json()


async def test_html_defaults_to_a4_and_paper_selects_a5(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    a4 = await client.get(
        "/api/v1/reports/day_profit",
        params={"format": "html"},
        headers=headers,
    )
    assert a4.status_code == 200
    assert a4.headers["content-type"].startswith("text/html")
    assert "@page" in a4.text and "size: A4" in a4.text
    assert "ربح اليوم" in a4.text

    a5 = await client.get(
        "/api/v1/reports/stock_minimum",
        params={"format": "html", "paper": "A5"},
        headers=headers,
    )
    assert a5.status_code == 200
    assert "size: A5" in a5.text


async def test_invalid_paper_is_rejected(client):
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/day_profit",
        params={"format": "html", "paper": "Letter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


async def test_table_report_renders_rows_through_the_generic_path(client):
    """stock_minimum over an empty branch still renders header + zero count."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/stock_minimum",
        params={"format": "html"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "النواقص" in r.text
    assert "<table" in r.text


async def test_grid_format_returns_the_generic_spec_for_any_entry(client):
    """format=grid = the JSON grid spec the web ReportView renders."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/stock_minimum",
        params={"format": "grid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    spec = r.json()
    assert spec["title_ar"] == "النواقص (أقل من الحد الأدنى)"
    assert spec["title_en"] == "Stock Below Minimum"
    assert spec["columns"][0] == "الصنف"
    assert isinstance(spec["rows"], list)
    assert spec["note"] is None


async def test_generic_path_validates_dates_and_order(client):
    """Bad ISO dates and inverted ranges are 400 through /{code} too."""
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad = await client.get(
        "/api/v1/reports/period_totals",
        params={"format": "grid", "date_from": "not-a-date"},
        headers=headers,
    )
    assert bad.status_code == 400
    inverted = await client.get(
        "/api/v1/reports/period_totals",
        params={"format": "grid", "date_from": "2026-02-01", "date_to": "2026-01-01"},
        headers=headers,
    )
    assert inverted.status_code == 400


async def test_empty_result_renders_header_only_grid(client):
    """A period with no invoices yields zero rows but intact columns/foot."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports/period_totals",
        params={"format": "grid", "date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    spec = r.json()
    assert spec["columns"][0] == "البيان"
    # four kind rows, all zero-count over an empty period, totals row present
    assert len(spec["rows"]) == 4
    assert all(int(row[1]) == 0 for row in spec["rows"])
    assert spec["foot"] is not None
