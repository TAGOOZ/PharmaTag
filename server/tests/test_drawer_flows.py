"""S1.8 drawer movements from money documents (ticket #14, A17).

Sales (cash/card), sales returns, purchases and purchase returns all feed the
drawer equation: each payment split becomes a `drawer_movements` row in the
SAME transaction as the invoice (G12), attributed to the cashier (user_id) and
the document (ref_invoice_id). Credit never touches the drawer.
"""
from app.core.db import SessionLocal
from app.models import Invoice
from sqlalchemy import select

from tests.drawer_test_utils import (
    _cleanup_drawer,
    _close_day,
    _mark_closed,
    _movements,
    _login_token,
)
from tests.purchase_returns_test_utils import (
    _cleanup as _purchase_cleanup,
    _purchase,
    _return as _purchase_return,
)
from tests.purchase_test_utils import _make_drug, _make_supplier
from tests.returns_test_utils import _cleanup as _return_cleanup
from tests.sales_test_utils import _cleanup, _make_drug_and_stock
from tests.test_sales_replay import (
    _batch_ids as _replay_batch_ids,
    _cleanup as _replay_cleanup,
    _enqueue,
    _make_drug as _make_replay_drug,
    _payload,
    _replay,
)


async def test_cash_and_card_sale_write_drawer_movements(client):
    """Each paid split -> one movement: cash->cash, card->network, both in,
    reason cash_sale, tied to the invoice and the cashier."""
    _mark_closed("2026-01-06")
    drug_id = await _make_drug_and_stock(
        price="10.0000", batches=[("20.0000", "5.0000", "2026-06-01")]
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
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
        sale = r.json()
        invoice_ids.append(sale["id"])
        assert sale["payed"] == "120.00"

        movements = await _movements(client, token, datee="2026-01-06")
        assert len(movements) == 2
        by_method = {m["method"]: m for m in movements}
        cash_mv = by_method["cash"]
        net_mv = by_method["network"]
        for mv in movements:
            assert mv["datee"] == "2026-01-06"
            assert mv["direction"] == "in"
            assert mv["reason"] == "cash_sale"
            assert mv["ref_invoice_id"] == sale["id"]
        assert cash_mv["amount"] == "50.00"
        assert net_mv["amount"] == "70.00"
        assert cash_mv["user_id"] is not None
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)


async def test_credit_sale_never_touches_the_drawer(client):
    """A credit sale writes no drawer movement (agel stays on the balances)."""
    _mark_closed("2026-01-06")
    drug_id = await _make_drug_and_stock(
        price="10.0000", batches=[("20.0000", "5.0000", "2026-06-01")]
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"drug_id": drug_id, "qty": "12"}],
                "payments": [{"method": "credit", "amount": "120.00"}],
                "datee": "2026-01-06",
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        assert await _movements(client, token, datee="2026-01-06") == []
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)


async def test_sale_return_refunds_cash_out_of_the_drawer(client):
    """A returned cash sale writes a cash_out cash_return movement tied to the
    return invoice (A17)."""
    _mark_closed("2026-01-08")
    drug_id = await _make_drug_and_stock(
        price="10.0000", batches=[("20.0000", "5.0000", "2026-06-01")]
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}], "datee": "2026-01-08"},
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        orig_line_id = sale["lines"][0]["id"]

        rr = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lines": [{"ref_invoice_line_id": orig_line_id, "qty": "12"}],
                "datee": "2026-01-08",
            },
        )
        assert rr.status_code == 201, rr.text
        ret = rr.json()
        invoice_ids.append(ret["id"])
        assert ret["payed"] == "120.00"

        movements = await _movements(client, token, datee="2026-01-08")
        cash_out = [m for m in movements if m["direction"] == "out" and m["method"] == "cash"]
        assert len(cash_out) == 1
        mv = cash_out[0]
        assert mv["reason"] == "cash_return"
        assert mv["amount"] == "120.00"
        assert mv["ref_invoice_id"] == ret["id"]
    finally:
        await _cleanup_drawer()
        await _return_cleanup([drug_id], invoice_ids)


async def test_purchase_pays_cash_out_of_the_drawer(client):
    """A cash purchase writes a cash_out supplier_pay movement (A17)."""
    _mark_closed("2026-01-09")
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client,
            token,
            supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            payments=[{"method": "cash", "amount": "100.00"}],
            datee="2026-01-09",
        )
        invoice_ids.append(pur["id"])

        movements = await _movements(client, token, datee="2026-01-09")
        assert len(movements) == 1
        mv = movements[0]
        assert mv["direction"] == "out"
        assert mv["reason"] == "supplier_pay"
        assert mv["method"] == "cash"
        assert mv["amount"] == "100.00"
        assert mv["ref_invoice_id"] == pur["id"]
    finally:
        await _cleanup_drawer()
        await _purchase_cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_refunds_cash_in(client):
    """A returned cash purchase refunds cash IN with reason supplier_pay (A17)."""
    _mark_closed("2026-01-10")
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client,
            token,
            supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            payments=[{"method": "cash", "amount": "100.00"}],
            datee="2026-01-10",
        )
        invoice_ids.append(pur["id"])
        ret = await _purchase_return(
            client,
            token,
            pur,
            [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "10"}],
            datee="2026-01-10",
        )
        invoice_ids.append(ret["id"])

        movements = await _movements(client, token, datee="2026-01-10")
        cash_in = [m for m in movements if m["direction"] == "in" and m["method"] == "cash"]
        assert len(cash_in) == 1
        mv = cash_in[0]
        assert mv["reason"] == "supplier_pay"
        assert mv["amount"] == "100.00"
        assert mv["ref_invoice_id"] == ret["id"]
    finally:
        await _cleanup_drawer()
        await _purchase_cleanup([drug_id], invoice_ids, [supplier_id])


async def test_replayed_sale_writes_drawer_movement(client):
    """A sale applied through the offline replay path lands in the drawer too:
    its payment split becomes a cash_sale movement tied to the replayed invoice
    (G10 parity), and a day close counts it in net_cash."""
    _mark_closed("2026-08-17")
    drug_id = await _make_replay_drug([("10.0000", "5.0000", None)])
    batch_ids = await _replay_batch_ids(drug_id)
    sync_ids: list[int] = []
    invoice_ids: list[int] = []
    try:
        key = list(batch_ids)[0]
        payload = _payload("70006", drug_id, batch_ids[key], key)
        await _enqueue(payload)
        summary = await _replay()
        assert summary["applied"] == 1

        async with SessionLocal() as session:
            invoice = (
                await session.execute(select(Invoice).where(Invoice.invoice_no == "70006"))
            ).scalar_one()
            invoice_ids.append(invoice.id)

        token = await _login_token(client)
        movements = await _movements(client, token, datee="2026-08-17")
        assert len(movements) == 1
        mv = movements[0]
        assert mv["reason"] == "cash_sale"
        assert mv["direction"] == "in"
        assert mv["method"] == "cash"
        assert mv["amount"] == "40.00"
        assert mv["ref_invoice_id"] == invoice_ids[0]

        rc = await _close_day(
            client, token, datee="2026-08-17", counted_cash="40"
        )
        assert rc.status_code == 200, rc.text
        assert rc.json()["net_cash"] == "40.00"
    finally:
        await _cleanup_drawer()
        await _replay_cleanup([drug_id], invoice_ids, sync_ids)