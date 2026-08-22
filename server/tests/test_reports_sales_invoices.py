"""S3.4 sales-invoice register (ticket #26): RPT-S01.

فواتير المبيعات lists every `sale` invoice in a branch over a date range —
invoice number, date, customer (walk-ins stay party-less), gross/paid/credit
and VAT — and its summary must equal both the summary report's sale figures
and the journal's own debit legs (drawer 1000 + AR 1100, source=sale).
"""
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import Account, Journal, JournalLine, Party

from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def _make_party(client, token: str, kind: str) -> int:
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": kind, "namee": f"t2 s34 {kind}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _drop_party(party_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def _sale_journal_legs(account_code: str, invoice_ids: list[int]) -> str:
    """Σdebit on an account code over this test's sale journals."""
    async with SessionLocal() as session:
        account_id = (
            await session.execute(
                select(Account.id).where(
                    Account.branch_id == 1, Account.code == account_code
                )
            )
        ).scalar_one()
        total = (
            await session.execute(
                select(func.coalesce(func.sum(JournalLine.debit), 0)).where(
                    JournalLine.account_id == account_id,
                    JournalLine.journal_id.in_(
                        select(Journal.id).where(
                            Journal.source == "sale",
                            Journal.ref_invoice_id.in_(invoice_ids),
                        )
                    ),
                )
            )
        ).scalar_one()
        return f"{total:.2f}"


async def test_sales_invoice_register_lists_rows_and_reconciles(client):
    """Two sales (walk-in cash + part-credit to a customer) list with their
    header figures; the register's totals tie to period_totals and to the
    journal's drawer+AR debit legs."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    customer_id = None
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        customer_id = await _make_party(client, token, "customer")

        # walk-in cash sale: 12 × 10 → 120.00 gross, 14.74 VAT
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        walkin = r.json()
        invoice_ids.append(walkin["id"])

        # part-credit sale to the customer: 5 × 10 → 50.00, paid 20 / credit 30
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={
                "party_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "5"}],
                "payments": [
                    {"method": "cash", "amount": "20.00"},
                    {"method": "credit", "amount": "30.00"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        credit_sale = r.json()
        invoice_ids.append(credit_sale["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/sales_invoices",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        by_id = {row["invoice_no"]: row for row in body["rows"]}
        assert len(body["rows"]) == 2

        walkin_row = by_id[walkin["invoice_no"]]
        assert walkin_row["datee"] == today
        assert walkin_row["party_namee"] is None
        assert walkin_row["totalvalue"] == "120.00"
        assert walkin_row["payed"] == "120.00"
        assert walkin_row["agel"] == "0.00"
        assert walkin_row["vat"] == "14.74"
        assert walkin_row["writer"] == "admin"

        credit_row = by_id[credit_sale["invoice_no"]]
        assert credit_row["party_namee"] == "t2 s34 customer"
        assert credit_row["totalvalue"] == "50.00"
        assert credit_row["payed"] == "20.00"
        assert credit_row["agel"] == "30.00"

        assert body["totals"] == {
            "count": 2,
            "total": "170.00",
            "payed": "140.00",
            "agel": "30.00",
            "vat": "20.88",
        }

        # reconciliation 1: equals the summary report's sale kind
        pt = await client.get(
            "/api/v1/reports/period_totals",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert pt.status_code == 200, pt.text
        assert body["totals"]["count"] == pt.json()["kinds"]["sale"]["count"]
        assert (
            body["totals"]["total"]
            == pt.json()["kinds"]["sale"]["total"]
        )

        # reconciliation 2: equals the journal's own debit legs (source=sale)
        drawer = await _sale_journal_legs("1000", invoice_ids)
        ar = await _sale_journal_legs("1100", invoice_ids)
        from decimal import Decimal

        assert Decimal(body["totals"]["total"]) == Decimal(drawer) + Decimal(ar)
    finally:
        await _cleanup([drug_id], invoice_ids)
        if customer_id:
            await _drop_party(customer_id)


async def test_sales_invoices_in_catalog(client):
    """The register is a first-class catalog row (menu + dispatcher)."""
    token = await _login_token(client)
    r = await client.get(
        "/api/v1/reports", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    entry = next(x for x in r.json()["reports"] if x["code"] == "sales_invoices")
    assert entry["title_ar"] == "فواتير المبيعات"
    assert entry["category"] == "sales"
    assert entry["params"] == ["date_from", "date_to"]


async def test_sales_invoices_respect_date_bounds(client):
    """Only sales inside the inclusive range list; outside ones don't, and a
    purchase never appears in the sales register."""
    from datetime import timedelta

    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000", batches=[("20.0000", "5.0000", None)]
    )
    invoice_ids: list[int] = []
    supplier_id = None
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        sale_no = r.json()["invoice_no"]
        invoice_ids.append(r.json()["id"])

        supplier_id = await _make_party(client, token, "supplier")
        p = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "5", "unit_cost": "4.0000"}],
            },
        )
        assert p.status_code == 201, p.text
        purchase_no = p.json()["invoice_no"]
        invoice_ids.append(p.json()["id"])

        today = business_date().isoformat()
        tomorrow = (business_date() + timedelta(days=1)).isoformat()

        today_rep = await client.get(
            "/api/v1/reports/sales_invoices",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert [row["invoice_no"] for row in today_rep.json()["rows"]] == [sale_no]

        future_rep = await client.get(
            "/api/v1/reports/sales_invoices",
            params={"date_from": tomorrow},
            headers=auth,
        )
        assert future_rep.json()["rows"] == []
        assert future_rep.json()["totals"]["count"] == 0
        assert future_rep.json()["totals"]["total"] == "0.00"
        assert purchase_no not in {row["invoice_no"] for row in today_rep.json()["rows"]}
    finally:
        await _cleanup([drug_id], invoice_ids)
        if supplier_id:
            await _drop_party(supplier_id)


async def test_sales_invoices_renders_through_the_framework(client):
    """grid, printable HTML, xlsx export and the print queue all serve the
    register like any catalog report."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000", batches=[("20.0000", "5.0000", None)]
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/sales", headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        invoice_no = r.json()["invoice_no"]
        invoice_ids.append(r.json()["id"])
        today = business_date().isoformat()
        window = {"date_from": today, "date_to": today}

        grid = await client.get(
            "/api/v1/reports/sales_invoices",
            params={**window, "format": "grid"},
            headers=auth,
        )
        assert grid.status_code == 200, grid.text
        g = grid.json()
        assert g["title_ar"] == "فواتير المبيعات"
        assert "رقم الفاتورة" in g["columns"]
        assert len(g["rows"]) == 1
        assert g["rows"][0][0] == invoice_no
        assert g["foot"][3] == "20.00"

        html = await client.get(
            "/api/v1/reports/sales_invoices",
            params={**window, "format": "html"},
            headers=auth,
        )
        assert html.status_code == 200
        assert "فواتير المبيعات" in html.text

        xlsx = await client.get(
            "/api/v1/reports/sales_invoices/export",
            params=window,
            headers=auth,
        )
        assert xlsx.status_code == 200
        assert (
            xlsx.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        q = await client.post(
            "/api/v1/reports/sales_invoices/print-queue",
            headers=auth,
            json={"params": window},
        )
        assert q.status_code == 201, q.text
        assert q.json()["status"] == "queued"
    finally:
        await _cleanup([drug_id], invoice_ids)
