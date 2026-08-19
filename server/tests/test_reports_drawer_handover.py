"""S1.9 drawer handover report (ticket #15): RPT-A04 تسليم الدرج.

Per cashier over a date range: opening float, cash/card sales in, returns and
expenses out, and the expected net cash (opening + cash sales − returns −
expenses). Sales recorded by a user land on that user's row; manual movements
attribute to whoever posted them. Totals roll the branch up.
"""
from app.core.time import business_date

from tests.reports_test_utils import (
    _login_token,
    _make_drug_and_stock,
    _cleanup,
    _make_user,
)


def _token_for(user_id: int) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=1, roles=[], permission_level=3
    )


async def test_drawer_handover_groups_movements_per_cashier(client):
    """Opening + a cash sale + expenses split across two users' rows."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", None)],
    )
    invoice_ids: list[int] = []
    movement_ids: list[int] = []
    cashier_id = None
    try:
        token = await _login_token(client)
        cashier_id = await _make_user("__t2_rep_cashier__", 3, branch_id=1)

        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        opening = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "direction": "in", "reason": "opening", "method": "cash",
                "amount": "500.00",
            },
        )
        assert opening.status_code == 201, opening.text
        movement_ids.append(opening.json()["id"])

        admin_expense = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "direction": "out", "reason": "expense", "method": "cash",
                "amount": "10.00",
            },
        )
        assert admin_expense.status_code == 201, admin_expense.text
        movement_ids.append(admin_expense.json()["id"])

        cashier_expense = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {_token_for(cashier_id)}"},
            json={
                "direction": "out", "reason": "expense", "method": "cash",
                "amount": "5.00",
            },
        )
        assert cashier_expense.status_code == 201, cashier_expense.text
        movement_ids.append(cashier_expense.json()["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/drawer-handover",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert len(body["cashiers"]) == 2

        by_id = {c["user_id"]: c for c in body["cashiers"]}
        admin = by_id[1]
        assert admin["opening_in"] == "500.00"
        assert admin["cash_sales_in"] == "120.00"
        assert admin["card_sales_in"] == "0.00"
        assert admin["returns_out"] == "0.00"
        assert admin["expenses_out"] == "10.00"
        # opening + cash sales − returns − expenses
        assert admin["net_cash"] == "610.00"

        cashier = by_id[cashier_id]
        assert cashier["name"] == "__t2_rep_cashier__"
        assert cashier["cash_sales_in"] == "0.00"
        assert cashier["expenses_out"] == "5.00"
        assert cashier["net_cash"] == "-5.00"

        totals = body["totals"]
        assert totals["opening_in"] == "500.00"
        assert totals["cash_sales_in"] == "120.00"
        assert totals["expenses_out"] == "15.00"
    finally:
        await _cleanup([drug_id], invoice_ids, movement_ids)
        from sqlalchemy import delete
        from app.core.db import SessionLocal
        from app.models import User

        if cashier_id:
            async with SessionLocal() as session:
                await session.execute(delete(User).where(User.id == cashier_id))
                await session.commit()


async def test_drawer_handover_empty_period(client):
    """A period with no movements returns no cashiers and zeroed totals."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/drawer-handover",
        params={"date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert body["cashiers"] == []
    assert body["totals"]["opening_in"] == "0.00"


async def test_drawer_handover_card_refund_lands_in_card_returns_out(client):
    """A returned card sale nets against card, never against net_cash."""
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
            json={
                "lines": [{"drug_id": drug_id, "qty": "12"}],
                "payments": [{"method": "card", "amount": None}],
            },
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        assert sale["totalvalue"] == "120.00"

        ret = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "12"}]},
        )
        assert ret.status_code == 201, ret.text
        invoice_ids.append(ret.json()["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/drawer-handover",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        admin = next(c for c in body["cashiers"] if c["user_id"] == 1)
        assert admin["card_sales_in"] == "120.00"
        assert admin["card_returns_out"] == "120.00"
        assert admin["returns_out"] == "0.00"
        assert admin["net_cash"] == "0.00"
        assert body["totals"]["card_returns_out"] == "120.00"
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_drawer_handover_surfaces_other_manual_movements(client):
    """Transfer/settlement movements are reported and enter net_cash."""
    token = await _login_token(client)
    movement_ids: list[int] = []
    try:
        t = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "direction": "out", "reason": "transfer", "method": "cash",
                "amount": "50.00",
            },
        )
        assert t.status_code == 201, t.text
        movement_ids.append(t.json()["id"])

        s = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "direction": "in", "reason": "customer_settlement", "method": "cash",
                "amount": "20.00",
            },
        )
        assert s.status_code == 201, s.text
        movement_ids.append(s.json()["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/drawer-handover",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        admin = next(c for c in body["cashiers"] if c["user_id"] == 1)
        assert admin["other_in"] == "20.00"
        assert admin["other_out"] == "50.00"
        assert admin["net_cash"] == "-30.00"
        assert body["totals"]["other_in"] == "20.00"
        assert body["totals"]["other_out"] == "50.00"
    finally:
        await _cleanup([], [], movement_ids)


async def test_drawer_handover_inverted_date_range_rejected(client):
    """date_from after date_to is a 400, not a silent empty report."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/drawer-handover",
        params={"date_from": "2026-01-10", "date_to": "2026-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 400


async def test_drawer_handover_html_renders_printable(client):
    """format=html returns a printable A4 page."""
    token = await _login_token(client)
    html = await client.get(
        "/api/v1/reports/drawer-handover",
        params={"format": "html", "date_from": "2000-01-01", "date_to": "2000-01-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "تسليم الدرج" in html.text