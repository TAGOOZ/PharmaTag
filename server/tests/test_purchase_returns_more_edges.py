"""S1.6 purchase-return edge-case pass, part 2 (ticket #12).

Real-world scenarios that the first pass did not exercise:
* combined per-line + header discount on the SAME purchase (regression for the
  double-count bug — the return must reverse the line share and the
  header-only share separately);
* stacking partial returns (a second return after a first succeeds, then an
  over-return is still rejected);
* duplicate ref_invoice_line_id inside ONE request (client double-tap / bad
  payload) — must be atomic, no partial decrement;
* an empty lines payload (no-op return) must be rejected, not silently saved;
* a zero-cost (free-goods) line returns without crashing or writing a phantom
  journal;
* the GET /purchases/returns list endpoint (today's returns, with their
  original-invoice link).
"""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Invoice, Journal
from tests.purchase_returns_test_utils import (
    _cleanup,
    _journal_totals,
    _login_token,
    _make_drug,
    _make_supplier,
    _purchase,
    _return,
    _stock_qty,
)


async def test_return_combines_line_and_header_discount_without_double_count(client):
    """Original 10 × 10.00 with a 10% LINE discount AND a 10% HEADER discount:
    discount 20, total 80. Returning 4 reverses the line share (4.00) + the
    header-only share (4.00) = 8.00 — never the buggy 8.00-with-double-count
    from treating the header discount as including the line discount."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000", "disc_percent": "10"}],
            disc_percent="10",
        )
        assert pur["discount"] == "20.00"
        assert pur["totalvalue"] == "80.00"
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["subtotal"] == "40.00"
        assert ret["discount"] == "8.00"
        assert ret["vat"] == "4.42"
        assert ret["totalvalue"] == "32.00"
        assert ret["net"] == "27.58"
        assert ret["payed"] == "32.00"
        debit, credit = await _journal_totals(ret["id"])
        assert debit == credit == Decimal("32.00")
        assert await _stock_qty(drug_id) == Decimal("6.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_second_partial_return_then_over(client):
    """Real supplier-pickup flow: return 4 now, return 3 later (cumulative 7 ≤
    10), then a 4th over-return is rejected — cumulative cap holds across
    multiple partial returns."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        line_id = pur["lines"][0]["id"]
        r1 = await _return(
            client, token, pur, [{"ref_invoice_line_id": line_id, "qty": "4"}]
        )
        invoice_ids.append(r1["id"])
        assert await _stock_qty(drug_id) == Decimal("6.0000")
        r2 = await _return(
            client, token, pur, [{"ref_invoice_line_id": line_id, "qty": "3"}]
        )
        invoice_ids.append(r2["id"])
        assert r2["totalvalue"] == "30.00"
        assert await _stock_qty(drug_id) == Decimal("3.0000")
        r3 = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "4"}]},
        )
        assert r3.status_code == 400
        assert "cannot return more" in r3.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("3.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_duplicate_ref_line_in_one_request_cumulative_cap(client):
    """The same line twice in ONE payload is legal but the CUMULATIVE cap still
    holds: 4 + 4 = 8 ≤ 10 succeeds; a follow-up 4 more is rejected — the cap is
    enforced across lines in a request just like across separate requests."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        line_id = pur["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [
                {"ref_invoice_line_id": line_id, "qty": "4"},
                {"ref_invoice_line_id": line_id, "qty": "4"},
            ]},
        )
        assert r.status_code == 201, r.text
        ret = r.json()
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "80.00"
        assert ret["payed"] == "80.00"
        assert len(ret["lines"]) == 2
        assert await _stock_qty(drug_id) == Decimal("2.0000")
        over = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "3"}]},
        )
        assert over.status_code == 400
        assert "cannot return more" in over.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("2.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_empty_lines_request_rejected(client):
    """An empty return payload is a no-op and must be rejected, never saved."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": []},
        )
        assert r.status_code == 400
        assert "at least 1 item" in str(r.json()["detail"])
        assert await _stock_qty(drug_id) == Decimal("10.0000")
        async with SessionLocal() as session:
            n = (
                await session.execute(
                    select(Invoice).where(
                        Invoice.kind == "purchase_return",
                        Invoice.ref_invoice_id == pur["id"],
                    )
                )
            ).scalars().all()
            assert n == []
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_free_goods_zero_cost_return(client):
    """Free-of-charge goods (unit_cost 0.00) can still be returned: stock goes
    down, the invoice totals are zero and no phantom journal is written."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "0.0000"}]
        )
        invoice_ids.append(pur["id"])
        assert pur["totalvalue"] == "0.00"
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        assert ret["totalvalue"] == "0.00"
        assert ret["payed"] == "0.00"
        assert ret["agel"] == "0.00"
        assert await _stock_qty(drug_id) == Decimal("6.0000")
        async with SessionLocal() as session:
            journals = (
                await session.execute(
                    select(Journal).where(Journal.ref_invoice_id == ret["id"])
                )
            ).scalars().all()
            assert journals == [], "a zero-total return must not post a journal"
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_returns_list_endpoint(client):
    """GET /purchases/returns lists today's purchase returns with their
    original-invoice link and totals."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return(
            client, token, pur, [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "4"}]
        )
        invoice_ids.append(ret["id"])
        r = await client.get(
            "/api/v1/purchases/returns",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        returns = r.json()["returns"]
        assert any(x["id"] == ret["id"] for x in returns)
        match = next(x for x in returns if x["id"] == ret["id"])
        assert match["ref_invoice_id"] == pur["id"]
        assert match["totalvalue"] == "40.00"
        assert match["invoice_no"] == ret["invoice_no"]
        empty = await client.get(
            "/api/v1/purchases/returns?datee=2000-01-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert empty.status_code == 200
        assert empty.json()["returns"] == []
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])
