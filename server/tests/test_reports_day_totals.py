"""S3.2 day totals report (ticket #24): الإجماليات اليومية.

One row per day over a range with the payment splits (cash/network sales,
cash/network returns, manual cash/card, expenses, supplier payments,
expected cash) plus the day's P&L columns — the Z-report grid across
periods. Totals foot rolls the window; Σ(rows) must equal the ranged
day_profit figures (same ledger math).
"""
from app.core.time import business_date

from tests.reports_test_utils import (
    _login_token,
    _make_drug_and_stock,
    _cleanup,
    _uniq,
)


async def test_day_totals_answers_through_the_dispatcher(client):
    """A real cash sale lands on its day row: cash split + P&L columns."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2026-01-01")],
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/day_totals",
            params={"date_from": today, "date_to": today},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["date_from"] == today
        assert body["date_to"] == today
        assert len(body["days"]) == 1
        day = body["days"][0]
        assert day["datee"] == today
        assert day["cash_sales"] == "120.00"
        assert day["network_sales"] == "0.00"
        assert day["expenses"] == "0.00"
        assert day["net_profit"] == "45.26"
        assert day["expected_cash"] == "120.00"

        totals = body["totals"]
        assert totals["cash_sales"] == "120.00"
        assert totals["net_profit"] == "45.26"
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_day_totals_splits_land_per_day_and_roll_up(client):
    """Cash vs network sales, manual cash/card, expenses and supplier
    payments land in their own columns on their own days; the foot rolls
    the window exactly."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
    )
    invoice_ids: list[int] = []
    movement_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        # day 1: 50 cash + 70 card sale, 10 cash expense, 30 manual card in
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={
                "lines": [{"drug_id": drug_id, "qty": "12"}],
                "payments": [
                    {"method": "cash", "amount": "50.00"},
                    {"method": "card", "amount": "70.00"},
                ],
                "datee": "2026-01-06",
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        for payload in (
            {"direction": "out", "reason": "expense", "method": "cash", "amount": "10.00", "datee": "2026-01-06"},
            {"direction": "in", "reason": "transfer", "method": "network", "amount": "30.00", "datee": "2026-01-06"},
        ):
            mv = await client.post("/api/v1/drawer/movements", headers=auth, json=payload)
            assert mv.status_code == 201, mv.text
            movement_ids.append(mv.json()["id"])

        # day 2: 40 supplier payment out, 25 customer settlement in (cash)
        for payload in (
            {"direction": "out", "reason": "supplier_pay", "method": "cash", "amount": "40.00", "datee": "2026-01-07"},
            {"direction": "in", "reason": "customer_settlement", "method": "cash", "amount": "25.00", "datee": "2026-01-07"},
        ):
            mv = await client.post("/api/v1/drawer/movements", headers=auth, json=payload)
            assert mv.status_code == 201, mv.text
            movement_ids.append(mv.json()["id"])

        rep = await client.get(
            "/api/v1/reports/day_totals",
            params={"date_from": "2026-01-06", "date_to": "2026-01-07"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert [d["datee"] for d in body["days"]] == ["2026-01-06", "2026-01-07"]

        day1, day2 = body["days"]
        assert day1["cash_sales"] == "50.00"
        assert day1["network_sales"] == "70.00"
        assert day1["expenses"] == "10.00"
        assert day1["manual_card"] == "30.00"
        assert day1["manual_cash"] == "-10.00"  # expense nets in
        assert day1["expected_cash"] == "40.00"  # 50 in − 10 out

        assert day2["supplier_payments"] == "40.00"
        assert day2["manual_cash"] == "25.00"
        assert day2["expected_cash"] == "-15.00"  # 25 in − 40 out
        assert day2["cash_sales"] == "0.00"

        totals = body["totals"]
        assert totals["cash_sales"] == "50.00"
        assert totals["network_sales"] == "70.00"
        assert totals["expenses"] == "10.00"
        assert totals["manual_card"] == "30.00"
        assert totals["manual_cash"] == "15.00"  # −10 + 25
        assert totals["supplier_payments"] == "40.00"
        assert totals["expected_cash"] == "25.00"  # 75 in − 50 out
    finally:
        await _cleanup([drug_id], invoice_ids, movement_ids)


async def test_day_totals_rows_sum_to_the_ranged_day_profit(client):
    """Σ(day rows) == day_profit over the same window — one ledger engine."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("60.0000", "5.0000", "2027-01-01")],
        stock_qty="60.0000",
    )
    invoice_ids: list[int] = []
    movement_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "12"}], "datee": "2026-03-02"},
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={
                "lines": [{"drug_id": drug_id, "qty": "6"}],
                "payments": [{"method": "card", "amount": "60.00"}],
                "datee": "2026-03-03",
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
                "amount": "7.50",
                "datee": "2026-03-03",
            },
        )
        assert mv.status_code == 201, mv.text
        movement_ids.append(mv.json()["id"])

        window = {"date_from": "2026-03-01", "date_to": "2026-03-31"}
        grid = (
            await client.get("/api/v1/reports/day_totals", params=window, headers=auth)
        ).json()
        profit = (
            await client.get(
                "/api/v1/reports/day-profit", params=window, headers=auth
            )
        ).json()

        from decimal import Decimal

        def _sum(key: str) -> Decimal:
            return sum(Decimal(d[key]) for d in grid["days"])

        # day_profit renames the grid's cost_of_sales to cogs
        shared = (
            ("expenses", "expenses"),
            ("expected_cash", "expected_cash"),
            ("purchases", "purchases"),
            ("discounts", "discounts"),
            ("vat_sales", "vat_sales"),
            ("vat_purchases", "vat_purchases"),
            ("cost_of_sales", "cogs"),
            ("net_profit", "net_profit"),
        )
        for grid_key, profit_key in shared:
            assert _sum(grid_key) == Decimal(profit[profit_key]), grid_key
        # and the gross splits reconcile to the profit report's nets
        assert _sum("cash_sales") - _sum("cash_returns") == Decimal(profit["net_cash"])
        assert (
            _sum("network_sales") - _sum("network_returns")
            == Decimal(profit["net_network"])
        )
        assert len(grid["days"]) == 2
    finally:
        await _cleanup([drug_id], invoice_ids, movement_ids)


async def test_day_totals_empty_range_is_zeroed(client):
    """A window with no documents is an empty grid with zeroed totals."""
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/day_totals",
        params={"date_from": "1999-01-01", "date_to": "1999-01-31"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 200, rep.text
    body = rep.json()
    assert body["days"] == []
    assert body["totals"]["cash_sales"] == "0.00"
    assert body["totals"]["net_profit"] == "0.00"


async def test_day_totals_inverted_range_rejected(client):
    token = await _login_token(client)
    rep = await client.get(
        "/api/v1/reports/day_totals",
        params={"date_from": "2026-01-31", "date_to": "2026-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rep.status_code == 400


async def test_day_totals_open_ended_bounds(client):
    """One-sided windows are open-ended, not errors."""
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
            json={"lines": [{"drug_id": drug_id, "qty": "3"}], "datee": "2026-02-15"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rep = await client.get(
            "/api/v1/reports/day_totals",
            params={"date_from": "2026-02-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["date_to"] is None
        assert [d["datee"] for d in body["days"]] == ["2026-02-15"]
        assert body["days"][0]["cash_sales"] == "30.00"
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_day_totals_html_renders_printable(client):
    """format=html returns the black-on-white A4 page with title + foot."""
    token = await _login_token(client)
    html = await client.get(
        "/api/v1/reports/day_totals",
        params={
            "date_from": "2026-01-06",
            "date_to": "2026-01-07",
            "format": "html",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "الإجماليات اليومية" in html.text
    assert "مبيعات كاش" in html.text
    assert "الإجمالي" in html.text


async def test_day_totals_exports_are_real_files(client):
    import io
    import zipfile

    token = await _login_token(client)
    xlsx = await client.get(
        "/api/v1/reports/day_totals/export",
        params={"format": "xlsx"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert xlsx.status_code == 200, xlsx.text
    assert "spreadsheetml" in xlsx.headers["content-type"]
    zf = zipfile.ZipFile(io.BytesIO(xlsx.content))
    assert "xl/workbook.xml" in set(zf.namelist())

    pdf = await client.get(
        "/api/v1/reports/day_totals/export",
        params={"format": "pdf"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"


async def test_day_totals_print_queue_round_trip(client):
    """The queue accepts a day_totals job with its params snapshot."""
    from sqlalchemy import delete as sqld

    from app.core.db import SessionLocal
    from app.models import PrintJob

    token = await _login_token(client)
    r = await client.post(
        "/api/v1/reports/day_totals/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={"params": {"date_from": "2026-01-01", "date_to": "2026-01-31"}},
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["report_code"] == "day_totals"
    assert job["params"]["date_from"] == "2026-01-01"

    done = await client.post(
        f"/api/v1/reports/print-queue/{job['id']}/done",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "done"

    async with SessionLocal() as session:
        await session.execute(sqld(PrintJob).where(PrintJob.id == job["id"]))
        await session.commit()


async def test_day_totals_branch_scoped(client):
    """A branch-2 user sees only branch-2 days, never branch-1 rows."""
    from sqlalchemy import delete as sqld

    from app.core.db import SessionLocal
    from app.models import Branch, User
    from app.auth.security import create_access_token

    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2027-01-01")],
    )
    user_id = None
    branch_id = None
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "5"}], "datee": "2026-04-01"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        async with SessionLocal() as session:
            branch = Branch(pharmacyid="dtot", mobile="0", pharname="DTOT")
            session.add(branch)
            await session.flush()
            branch_id = branch.id
            user = User(
                username=_uniq("b2"),
                pass_hash="x",
                permission_level=9,
                branch_id=branch_id,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        other_token = create_access_token(
            str(user_id), branch_id=branch_id, roles=[], permission_level=9
        )
        rep = await client.get(
            "/api/v1/reports/day_totals",
            params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["branch_id"] == branch_id
        assert body["days"] == []
        assert body["totals"]["cash_sales"] == "0.00"
    finally:
        if user_id is not None:
            async with SessionLocal() as session:
                await session.execute(sqld(User).where(User.id == user_id))
                await session.execute(sqld(Branch).where(Branch.id == branch_id))
                await session.commit()
        await _cleanup([drug_id], invoice_ids)
