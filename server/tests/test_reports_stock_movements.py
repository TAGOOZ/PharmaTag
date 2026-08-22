"""S3.3 drug movement track (ticket #25): تتبع تغيير الرصيد (RPT-ST06).

Per-drug daily opening / purchases / sales / returns / adjustments / closing
derived on read from `invoice_lines` by parent invoice kind plus approved
stock corrections. The invariant: over full history, the last closing must
equal the branch's running `branch_stock.qty`.
"""
from tests.purchase_test_utils import _cleanup as _cleanup_purchase_chain
from tests.purchase_test_utils import _make_supplier
from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def _purge_corrections(request_ids: list[int], drug_id: int) -> None:
    """Correction requests, their journals, price-change log rows, and the
    branch_stock OUTBOX row the approval enqueued must all go before the
    invoice/batch chain — otherwise later replay tests see a pending row
    whose drug no longer exists (failed=1 / KeyError 'invoice_no')."""
    from sqlalchemy import delete as sqld
    from sqlalchemy import select as sa_sel

    from app.core.db import SessionLocal
    from app.models import (
        Journal,
        JournalLine,
        PriceChangeLog,
        StockCorrectionRequest,
        SyncLog,
    )

    async with SessionLocal() as session:
        if request_ids:
            await session.execute(
                sqld(StockCorrectionRequest).where(
                    StockCorrectionRequest.id.in_(request_ids)
                )
            )
        jids = (
            await session.execute(
                sa_sel(Journal.id).where(Journal.source == "correction")
            )
        ).scalars().all()
        if jids:
            await session.execute(
                sqld(JournalLine).where(JournalLine.journal_id.in_(jids))
            )
            await session.execute(sqld(Journal).where(Journal.id.in_(jids)))
        await session.execute(
            sqld(PriceChangeLog).where(PriceChangeLog.drug_id == drug_id)
        )
        for row in (await session.execute(sa_sel(SyncLog))).scalars().all():
            if row.payload and row.payload.get("drug_id") == drug_id:
                await session.execute(sqld(SyncLog).where(SyncLog.id == row.id))
        await session.commit()


async def test_movements_flow_purchase_sale_and_return(client):
    """Purchase in → sale out → sale-return back lands on its own days with
    rolling opening/closing."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[],
        stock_qty="0.0000",
    )
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/v1/purchases",
            headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "4.0000"}],
                "datee": "2026-05-02",
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "4"}], "datee": "2026-05-03"},
        )
        assert r.status_code == 201, r.text
        sale = r.json()
        invoice_ids.append(sale["id"])
        sale_line_id = sale["lines"][0]["id"]

        rr = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers=auth,
            json={
                "lines": [{"ref_invoice_line_id": sale_line_id, "qty": "2"}],
                "datee": "2026-05-04",
            },
        )
        assert rr.status_code == 201, rr.text
        invoice_ids.append(rr.json()["id"])

        rep = await client.get(
            "/api/v1/reports/stock_movements",
            params={"drug_id": drug_id, "date_from": "2026-05-01", "date_to": "2026-05-31"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()

        days = body["days"]
        assert [d["datee"] for d in days] == [
            "2026-05-02",
            "2026-05-03",
            "2026-05-04",
        ]

        d1, d2, d3 = days
        assert d1["opening"] == "0.0000"
        assert d1["purchases"] == "10.0000"
        assert d1["closing"] == "10.0000"

        assert d2["opening"] == "10.0000"
        assert d2["sales"] == "4.0000"
        assert d2["closing"] == "6.0000"

        assert d3["opening"] == "6.0000"
        assert d3["sales_returns"] == "2.0000"
        assert d3["closing"] == "8.0000"

        # nothing else moved on these days
        assert d1["sales"] == "0.0000"
        assert d2["purchases"] == "0.0000"
        assert all(d["adjustments"] == "0.0000" for d in days)
    finally:
        await _purge_corrections([], drug_id)
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_purchase_chain([], [], [supplier_id])


async def test_movements_full_history_closes_at_branch_stock(client):
    """Invariant: over an open-ended window, the final closing equals the
    branch's running `branch_stock.qty` — purchases − sales + returns +
    corrections reconcile to the stock engine."""
    from sqlalchemy import select as sa_select

    from app.core.db import SessionLocal
    from app.models import BranchStock

    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[],
        stock_qty="0.0000",
    )
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/v1/purchases",
            headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "20", "unit_cost": "6.0000"}],
                "datee": "2026-06-01",
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "7"}], "datee": "2026-06-02"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        # approved correction: counted 10 vs system 13 → delta −3
        cr = await client.post(
            "/api/v1/stock/count-requests",
            headers=auth,
            json={"drug_id": drug_id, "counted": "10"},
        )
        assert cr.status_code == 201, cr.text
        request_ids.append(cr.json()["id"])
        ap = await client.post(
            f"/api/v1/stock/count-requests/{cr.json()['id']}/approve", headers=auth
        )
        assert ap.status_code == 200, ap.text

        rep = await client.get(
            "/api/v1/reports/stock_movements",
            params={"drug_id": drug_id},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        days = body["days"]
        # purchase day, sale day, then the correction day (today)
        assert [d["datee"] for d in days[:2]] == ["2026-06-01", "2026-06-02"]
        assert len(days) == 3

        async with SessionLocal() as session:
            qty = (
                await session.execute(
                    sa_select(BranchStock.qty).where(
                        BranchStock.branch_id == 1, BranchStock.drug_id == drug_id
                    )
                )
            ).scalar_one()

        # THE invariant: last closing == branch_stock.qty
        assert days[-1]["closing"] == format(qty, "f")
        assert days[-1]["closing"] == body["current_qty"] == "10.0000"
        # correction day carries the −3 adjustment column
        assert days[-1]["adjustments"] == "-3.0000"
        # rolling math checks out across the window
        assert days[0]["opening"] == "0.0000"
        assert days[0]["purchases"] == "20.0000"
        assert days[0]["closing"] == "20.0000"
        assert days[1]["sales"] == "7.0000"
        assert days[1]["closing"] == "13.0000"
    finally:
        await _purge_corrections(request_ids, drug_id)
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_purchase_chain([], [], [supplier_id])


async def test_movements_requires_drug_and_rejects_unknown(client):
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}

    missing = await client.get(
        "/api/v1/reports/stock_movements", headers=auth
    )
    assert missing.status_code == 400

    bad = await client.get(
        "/api/v1/reports/stock_movements",
        params={"drug_id": "abc"},
        headers=auth,
    )
    assert bad.status_code == 400

    unknown = await client.get(
        "/api/v1/reports/stock_movements",
        params={"drug_id": "999999999"},
        headers=auth,
    )
    assert unknown.status_code == 400


async def test_movements_empty_window_is_empty(client):
    """A window with no documents for the drug has no day rows."""
    drug_id = await _make_drug_and_stock(stock_qty="5.0000")
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_movements",
            params={
                "drug_id": drug_id,
                "date_from": "1999-01-01",
                "date_to": "1999-01-31",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["days"] == []
        assert body["current_qty"] == "5.0000"
    finally:
        await _cleanup([drug_id], [])


async def test_movements_purchase_return_reconciles(client):
    """Invariant extension: the purchase_return leg flows through the track —
    purchase 10 → sale 3 → supplier return 2 closes at branch_stock.qty."""
    from sqlalchemy import select as sa_select

    from app.core.db import SessionLocal
    from app.models import BranchStock

    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[],
        stock_qty="0.0000",
    )
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/v1/purchases",
            headers=auth,
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "10", "unit_cost": "4.0000"}],
                "datee": "2026-07-01",
            },
        )
        assert r.status_code == 201, r.text
        pur = r.json()
        invoice_ids.append(pur["id"])

        r = await client.post(
            "/api/v1/sales",
            headers=auth,
            json={"lines": [{"drug_id": drug_id, "qty": "3"}], "datee": "2026-07-02"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rr = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers=auth,
            json={"lines": [{
                "ref_invoice_line_id": pur["lines"][0]["id"],
                "qty": "2",
            }]},
        )
        assert rr.status_code == 201, rr.text
        ret_datee = rr.json()["datee"]
        invoice_ids.append(rr.json()["id"])

        rep = await client.get(
            "/api/v1/reports/stock_movements",
            params={"drug_id": drug_id},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        days = body["days"]
        assert [d["datee"] for d in days[:2]] == ["2026-07-01", "2026-07-02"]
        assert len(days) == 3

        async with SessionLocal() as session:
            qty = (
                await session.execute(
                    sa_select(BranchStock.qty).where(
                        BranchStock.branch_id == 1, BranchStock.drug_id == drug_id
                    )
                )
            ).scalar_one()

        # 10 in − 3 sold − 2 returned to supplier = 5
        assert days[-1]["purchase_returns"] == "2.0000"
        assert days[-1]["closing"] == body["current_qty"] == format(qty, "f")
        assert days[-1]["closing"] == "5.0000"
    finally:
        await _purge_corrections([], drug_id)
        await _cleanup([drug_id], invoice_ids)
        await _cleanup_purchase_chain([], [], [supplier_id])
