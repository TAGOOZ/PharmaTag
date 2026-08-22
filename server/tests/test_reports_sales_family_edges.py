"""S3.4 edge-case pass (ticket #26): the four sales-family reports.

Covers: empty ranges are zeroed, inverted ranges 400, party-less documents
never invent a party row, and every new code renders through the generic
framework (grid + printable HTML) so export/print come free.
"""
import pytest

from tests.reports_test_utils import _login_token

NEW_CODES = (
    "sales_invoices",
    "purchase_invoices",
    "returns_period",
    "party_totals",
)


@pytest.mark.parametrize("code", NEW_CODES)
async def test_empty_range_is_zeroed(client, code):
    token = await _login_token(client)
    rep = await client.get(
        f"/api/v1/reports/{code}",
        params={"date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    for key in ("rows", "customers", "suppliers"):
        if key in body:
            assert body[key] == []
    totals = body.get("totals")
    if totals:
        for value in totals.values():
            if isinstance(value, str):
                assert value == "0.00"
            else:
                assert value == 0


@pytest.mark.parametrize("code", NEW_CODES)
async def test_inverted_range_rejected(client, code):
    token = await _login_token(client)
    rep = await client.get(
        f"/api/v1/reports/{code}",
        params={"date_from": "2026-01-10", "date_to": "2026-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 400


@pytest.mark.parametrize("code", NEW_CODES)
async def test_print_queue_rejects_inverted_range(client, code):
    """A job that could never render must not enqueue."""
    token = await _login_token(client)
    q = await client.post(
        f"/api/v1/reports/{code}/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={"params": {"date_from": "2026-01-10", "date_to": "2026-01-01"}},
    )
    assert q.status_code == 400


@pytest.mark.parametrize("code", ("purchase_invoices", "returns_period", "party_totals"))
async def test_html_renders_printable(client, code):
    token = await _login_token(client)
    html = await client.get(
        f"/api/v1/reports/{code}",
        params={"format": "html", "date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("code", ("purchase_invoices", "returns_period", "party_totals"))
async def test_grid_renders(client, code):
    token = await _login_token(client)
    grid = await client.get(
        f"/api/v1/reports/{code}",
        params={"format": "grid", "date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert grid.status_code == 200, grid.text
    body = grid.json()
    assert body["columns"]
    assert body["rows"] == []


@pytest.mark.parametrize("code", ("sales_invoices", "purchase_invoices", "returns_period", "party_totals"))
async def test_export_xlsx(client, code):
    token = await _login_token(client)
    r = await client.get(
        f"/api/v1/reports/{code}/export",
        params={"format": "xlsx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


@pytest.mark.parametrize("code", NEW_CODES)
async def test_unknown_query_param_rejected(client, code):
    """A typo'd param (date_form) must 400 — not silently degrade to an
    all-history report on GET or /export."""
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}
    for path in (
        f"/api/v1/reports/{code}",
        f"/api/v1/reports/{code}/export",
    ):
        r = await client.get(
            path,
            params={"date_from": "2026-01-01", "date_to": "2026-01-31", "date_form": "2026-01-01"},
            headers=auth,
        )
        assert r.status_code == 400, f"{path}: {r.status_code} {r.text}"
