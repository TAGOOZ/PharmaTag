"""S1.9 basic reports (ticket #15) + S3.2 money reports (ticket #24) + S3.3
stock reports (ticket #25): the report catalog + access gate.

The v1 slice shipped four reports; S3.2 added day totals (الإجماليات
اليومية); S3.3 adds the four stock reports (current, movements, expired,
needs). `GET /api/v1/reports` lists the catalog of those reports (code +
Arabic/English titles + params) so a screen can render the menu; everything
is gated by the seeded `reports` permission (admin level-9 or the
accountant role).
"""
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import User

BRANCH_ID = 1

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


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def test_catalog_lists_the_four_basic_reports(client):
    """The catalog lists exactly the four v1 reports with bilingual titles."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    reports = r.json()["reports"]
    assert {rep["code"] for rep in reports} == EXPECTED_CODES

    by_code = {rep["code"]: rep for rep in reports}
    day = by_code["day_profit"]
    assert day["title_ar"] == "ربح اليوم"
    assert "title_en" in day and day["title_en"]
    assert "params" in day and day["params"]
    assert "category" in day


async def test_catalog_requires_auth(client):
    r = await client.get("/api/v1/reports")
    assert r.status_code == 401


async def test_reports_require_reports_permission(client):
    """A level-3 user (drugs.manage) cannot read reports; admin (9) can."""
    username = "__t2_rep_noperm__"
    user_id = None
    try:
        async with SessionLocal() as session:
            user = User(
                username=username,
                pass_hash="x",
                permission_level=3,
                branch_id=BRANCH_ID,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        from app.auth.security import create_access_token

        token = create_access_token(
            str(user_id), branch_id=BRANCH_ID, roles=[], permission_level=3
        )
        r = await client.get(
            "/api/v1/reports", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 403, r.text
    finally:
        if user_id:
            async with SessionLocal() as session:
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
