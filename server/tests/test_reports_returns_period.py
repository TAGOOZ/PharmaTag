"""S3.4 returns register (ticket #26): RPT-S02 + purchase returns.

مرتجعات الفترة lists sale and purchase return invoices over a date range with
the invoice they reverse, their value as a NEGATIVE figure (a credit note
reduces the period's VAT and sales — it is never positive income), and a
summary that nets into `period_totals`'s return kinds and the journal's
opposite legs.
"""
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import Party

from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def _make_party(client, token: str, kind: str) -> int:
    r = await client.post(
        "/api/v1/parties",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": kind, "namee": f"t2 s34 ret {kind}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _drop_party(party_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Party).where(Party.id == party_id))
        await session.commit()


async def test_returns_register_lists_both_kinds_as_negatives(client):
    """A sale return of 4 units and a purchase return list negative; the
    summary equals minus period_totals' return totals."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("40.0000", "5.0000", "2027-01-01")],
        stock_qty="40.0000",
    )
    invoice_ids: list[int] = []
    customer_id = None
    supplier_id = None
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        customer_id = await _make_party(client, token, "customer")
        supplier_id = await _make_party(client, token, "supplier")

        s = await client.post(
            "/api/v1/sales", headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert s.status_code == 201, s.text
        sale = s.json()
        invoice_ids.append(sale["id"])

        p = await client.post(
            "/api/v1/purchases", headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            },
        )
        assert p.status_code == 201, p.text
        purchase = p.json()
        invoice_ids.append(purchase["id"])

        sr = await client.post(
            f"/api/v1/sales/{sale['id']}/return", headers=auth,
            json={"lines": [{"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "4"}]},
        )
        assert sr.status_code == 201, sr.text
        sale_return = sr.json()
        invoice_ids.append(sale_return["id"])
        assert sale_return["totalvalue"] == "40.00"

        pr = await client.post(
            f"/api/v1/purchases/{purchase['id']}/return", headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [
                    {"ref_invoice_line_id": purchase["lines"][0]["id"], "qty": "2"}
                ],
            },
        )
        assert pr.status_code == 201, pr.text
        purchase_return = pr.json()
        invoice_ids.append(purchase_return["id"])

        today = business_date().isoformat()
        rep = await client.get(
            "/api/v1/reports/returns_period",
            params={"date_from": today, "date_to": today},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert len(body["rows"]) == 2

        by_kind = {row["kind"]: row for row in body["rows"]}
        srow = by_kind["sale_return"]
        assert srow["invoice_no"] == sale_return["invoice_no"]
        assert srow["ref_invoice_no"] == sale["invoice_no"]
        assert srow["totalvalue"] == "-40.00"
        prow = by_kind["purchase_return"]
        assert prow["ref_invoice_no"] == purchase["invoice_no"]
        assert float(prow["totalvalue"]) < 0

        assert body["totals"]["count"] == 2
        assert body["totals"]["sales_returns"] == "-40.00"
        assert float(body["totals"]["purchase_returns"]) < 0
        assert float(body["totals"]["net"]) < 0

        pt = (
            await client.get(
                "/api/v1/reports/period_totals",
                params={"date_from": today, "date_to": today},
                headers=auth,
            )
        ).json()
        from decimal import Decimal

        assert Decimal(body["totals"]["sales_returns"]) == -Decimal(
            pt["kinds"]["sale_return"]["total"]
        )
        assert Decimal(body["totals"]["purchase_returns"]) == -Decimal(
            pt["kinds"]["purchase_return"]["total"]
        )
    finally:
        await _cleanup([drug_id], invoice_ids)
        for party_id in (customer_id, supplier_id):
            if party_id:
                await _drop_party(party_id)
