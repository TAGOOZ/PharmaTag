"""S3.4 truncation contract (ticket #26 edge pass): the three registers.

The invoice registers follow the stock-family house cap: at most 1000 rows
render, `truncated` marks a cut list, and the summary totals stay WHOLE-PERIOD
(computed in SQL over every matching row) so a printed register still foots to
the journal even when its page list is capped.
"""
from decimal import Decimal

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.core.time import business_date
from app.models import Invoice, InvoiceLine

from tests.reports_test_utils import (
    BRANCH_ID,
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _uniq,
)

_TODAY = None


def _today():
    global _TODAY
    if _TODAY is None:
        _TODAY = business_date()
    return _TODAY


async def _bulk_invoices(kind: str, count: int, *, with_lines: bool, drug_id=None):
    """Insert `count` throwaway invoices (kind) dated today; returns ids."""
    ids: list[int] = []
    async with SessionLocal() as session:
        invoices = [
            Invoice(
                branch_id=BRANCH_ID,
                kind=kind,
                invoice_no=_uniq(f"cap{i}"),
                datee=_today(),
                subtotal=Decimal("10.00"),
                discount=Decimal("0.00"),
                vat=Decimal("0.70"),
                totalvalue=Decimal("10.70"),
                payed=Decimal("10.70"),
                agel=Decimal("0.00"),
            )
            for i in range(count)
        ]
        session.add_all(invoices)
        await session.flush()
        ids = [inv.id for inv in invoices]
        if with_lines:
            session.add_all(
                InvoiceLine(
                    invoice_id=iid,
                    branch_id=BRANCH_ID,
                    drug_id=drug_id,
                    qty=Decimal("1.0000"),
                    unit="pack",
                    unit_price=Decimal("10.0000"),
                    cost=Decimal("9.3000"),
                    vat_amount=Decimal("0.70"),
                    line_total=Decimal("10.00"),
                    expire=_today(),
                )
                for iid in ids
            )
        await session.commit()
    return ids


async def _drop_bulk(ids: list[int]) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(ids)))
        await session.execute(delete(Invoice).where(Invoice.id.in_(ids)))
        await session.commit()


async def test_sales_register_caps_rows_but_totals_stay_whole(client):
    drug_id = None
    ids: list[int] = []
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/sales_invoices",
            params={"date_from": _today().isoformat(), "date_to": _today().isoformat()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200
        baseline_total = Decimal(rep.json()["totals"]["total"])
        baseline_count = rep.json()["totals"]["count"]

        ids = await _bulk_invoices("sale", 1001, with_lines=False)

        body = (
            await client.get(
                "/api/v1/reports/sales_invoices",
                params={
                    "date_from": _today().isoformat(),
                    "date_to": _today().isoformat(),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        assert len(body["rows"]) == 1000
        assert body["truncated"] is True
        assert body["totals"]["count"] == baseline_count + 1001
        assert Decimal(body["totals"]["total"]) == baseline_total + Decimal(
            "10710.70"
        )
    finally:
        await _drop_bulk(ids)
        if drug_id:
            await _cleanup([drug_id], [])


async def test_purchase_register_caps_lines_but_totals_stay_whole(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000", batches=[("5.0000", "1.0000", "2027-01-01")]
    )
    ids: list[int] = []
    try:
        token = await _login_token(client)
        ids = await _bulk_invoices("purchase", 1001, with_lines=True, drug_id=drug_id)

        body = (
            await client.get(
                "/api/v1/reports/purchase_invoices",
                params={
                    "date_from": _today().isoformat(),
                    "date_to": _today().isoformat(),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        assert len(body["rows"]) == 1000
        assert body["truncated"] is True
        assert body["totals"]["line_count"] == 1001
        assert body["totals"]["invoice_count"] == 1001
        assert body["totals"]["total"] == "10710.70"
    finally:
        await _drop_bulk(ids)
        await _cleanup([drug_id], [])


async def test_returns_register_caps_rows_but_summary_stays_whole(client):
    ids: list[int] = []
    try:
        token = await _login_token(client)
        ids = await _bulk_invoices("sale_return", 1001, with_lines=False)

        body = (
            await client.get(
                "/api/v1/reports/returns_period",
                params={
                    "date_from": _today().isoformat(),
                    "date_to": _today().isoformat(),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        ).json()
        assert len(body["rows"]) == 1000
        assert body["truncated"] is True
        assert body["totals"]["count"] == 1001
        assert body["totals"]["sales_returns"] == "-10710.70"
    finally:
        await _drop_bulk(ids)
