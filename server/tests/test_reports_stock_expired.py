"""S3.3 expired/expiring stock report (ticket #25).

RPT-D01 + RPT-EXP01 merged: batch-level listing of stock that is already
expired (`expire ≤ as-of date`) or expiring within a warning horizon
(default 30 days). Zero-qty batches never appear — there is nothing to
write off. The boundary is inclusive: a pack expiring ON the as-of day is
expired, not warning.
"""
from datetime import date, timedelta

from app.core.time import business_date

from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


def _day(offset: int) -> str:
    return (business_date() + timedelta(days=offset)).isoformat()


async def test_expired_lists_expired_and_warning_batches(client):
    """Expired + within-horizon batches list with statuses; zero-qty and
    healthy lots stay off the sheet."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[
            ("5.0000", "2.0000", "2020-01-01"),   # long expired
            ("7.0000", "3.0000", _day(10)),       # warning window
            ("9.0000", "4.0000", _day(400)),      # healthy — excluded
            ("0.0000", "1.0000", "2019-01-01"),   # zero qty — excluded
        ],
        stock_qty="21.0000",
    )
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_expired",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["branch_id"] == 1
        assert body["horizon_days"] == 30

        items = body["items"]
        assert len(items) == 2
        expired = next(i for i in items if i["status"] == "expired")
        warning = next(i for i in items if i["status"] == "warning")

        assert expired["qty"] == "5.0000"
        assert int(expired["days_to_expiry"]) < 0  # in the past
        assert (
            expired["days_to_expiry"]
            == str(date(2020, 1, 1).toordinal() - business_date().toordinal())
        )
        assert expired["value"] == "10.00"

        assert warning["qty"] == "7.0000"
        assert warning["days_to_expiry"] == "10"
        assert warning["value"] == "21.00"
    finally:
        await _cleanup([drug_id], [])


async def test_expired_boundary_expire_today_is_expired(client):
    """expire == as-of day ⇒ Expired (the shelf life ended)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        price="6.0000",
        cost_price="2.0000",
        batches=[("4.0000", "2.0000", _day(0))],
        stock_qty="4.0000",
    )
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_expired",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        items = rep.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "expired"
        assert items[0]["days_to_expiry"] == "0"
    finally:
        await _cleanup([drug_id], [])


async def test_expired_horizon_param_narrows_window(client):
    """horizon_days=10 keeps a +5d lot but excludes a +20d lot; a negative
    horizon is rejected."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[
            ("3.0000", "1.0000", _day(5)),
            ("4.0000", "1.0000", _day(20)),
        ],
        stock_qty="7.0000",
    )
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        rep = await client.get(
            "/api/v1/reports/stock_expired",
            params={"horizon_days": "10"},
            headers=auth,
        )
        assert rep.status_code == 200, rep.text
        items = rep.json()["items"]
        assert [i["expire"] for i in items] == [_day(5)]
        assert rep.json()["horizon_days"] == 10

        neg = await client.get(
            "/api/v1/reports/stock_expired",
            params={"horizon_days": "-1"},
            headers=auth,
        )
        assert neg.status_code == 400
    finally:
        await _cleanup([drug_id], [])
