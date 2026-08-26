"""S3.1 report framework (ticket #23): the RPT catalog schema.

The catalog moves from a hardcoded list (#15) into the `report_catalog`
table so every later report slice (S3.2–S3.5) adds rows instead of code:
`GET /api/v1/reports` reads the table (seeded with the four v1 reports),
shows only active rows ordered by sort/code, and the generic engine
resolves any catalog code.
"""
from sqlalchemy import text

from app.core.db import SessionLocal
from tests.reports_test_utils import _login_token

EXPECTED_CODES = {
    "day_profit",
    "day_totals",
    "period_totals",
    "stock_minimum",
    "drawer_handover",
    # S3.3 (#25)
    "stock_current",
    "stock_movements",
    "stock_expired",
    "stock_needs",
    # S3.4 (#26)
    "sales_invoices",
    "purchase_invoices",
    "returns_period",
    "party_totals",
    "ledger_account",
    "vat_summary",
    # S5.4 (#34) — the titanksasales projection (A06)
    "chain_sales",
}


async def _add_row(code: str, *, active: bool = True, sort: int = 99) -> None:
    async with SessionLocal() as session:
        await session.execute(
            text(
                "INSERT INTO report_catalog "
                "(code, category, title_ar, title_en, params, paper, sort, active) "
                "VALUES (:code, 'money', 'تقرير تجريبي', 'Test Report', "
                "'[]'::jsonb, 'A4', :sort, :active)"
            ),
            {"code": code, "sort": sort, "active": active},
        )
        await session.commit()


async def _drop_row(code: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            text("DELETE FROM report_catalog WHERE code = :code"), {"code": code}
        )
        await session.commit()


async def test_catalog_is_seeded_with_the_four_v1_reports(client):
    token = await _login_token(client)
    r = await client.get("/api/v1/reports", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    reports = r.json()["reports"]
    assert {rep["code"] for rep in reports} == EXPECTED_CODES
    day = next(rep for rep in reports if rep["code"] == "day_profit")
    assert day["title_ar"] == "ربح اليوم"
    assert day["paper"] == "A4"


async def test_catalog_rows_added_to_the_table_appear_and_inactive_hide(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _add_row("__t2_rep_extra__")
    try:
        r = await client.get("/api/v1/reports", headers=headers)
        codes = {rep["code"] for rep in r.json()["reports"]}
        assert "__t2_rep_extra__" in codes

        await _drop_row("__t2_rep_extra__")
        await _add_row("__t2_rep_off__", active=False)
        try:
            r = await client.get("/api/v1/reports", headers=headers)
            codes = {rep["code"] for rep in r.json()["reports"]}
            assert "__t2_rep_off__" not in codes
        finally:
            await _drop_row("__t2_rep_off__")
    finally:
        await _drop_row("__t2_rep_extra__")


async def test_catalog_orders_by_sort_then_code(client):
    """Deterministic menu order: sort asc, then code as tiebreak."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports", headers={"Authorization": f"Bearer {token}"}
    )
    codes = [rep["code"] for rep in r.json()["reports"]]
    assert codes == [
        "drawer_handover",
        "day_profit",
        "day_totals",
        "period_totals",
        "stock_minimum",
        "stock_current",
        "stock_movements",
        "stock_expired",
        "stock_needs",
        "sales_invoices",
        "purchase_invoices",
        "returns_period",
        "party_totals",
        "ledger_account",
        "vat_summary",
        "chain_sales",
    ]
