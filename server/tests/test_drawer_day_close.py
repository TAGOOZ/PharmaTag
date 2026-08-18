"""S1.8 drawer + day close (ticket #14): the drawer equation
(`expected = drawer_start + cash_in − cash_out`, `difference = counted − expected`)
is snapshotted into `daily_close` per (branch, datee); reopening is manager-only
(perm ≥ 7) and always writes a reversal + audit; a closed (branch, date) never
silently receives new movements. Tests drive the public API only (A07, plan/02
§4.5, idx 9883)."""
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AuditLog
from tests.drawer_test_utils import (
    _cleanup_drawer,
    _close_day,
    _day_rows,
    _delete_users,
    _login_token,
    _make_user,
    _mark_closed,
)
from tests.purchase_test_utils import _delete_other_branch, _make_other_branch
from tests.sales_test_utils import _cleanup, _make_drug_and_stock


async def test_close_empty_day_snapshots_the_equation(client):
    """No movements, no start cash: drawer_start 0, expected 0, the counted
    amount is all difference (surplus). Row locks (branch, datee)."""
    datee = _mark_closed("2026-01-05")
    token = await _login_token(client)
    try:
        r = await _close_day(client, token, datee="2026-01-05", counted_cash="100")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "closed"
        assert body["drawer_start"] == "0.00"
        assert body["expected_cash"] == "0.00"
        assert body["counted_cash"] == "100.00"
        assert body["difference"] == "100.00"
        assert body["net_cash"] == "0.00"
        assert body["net_network"] == "0.00"
        assert body["manual_cash"] == "0.00"
        assert body["closed_by"] is not None

        rows = await _day_rows("2026-01-05")
        assert len(rows) == 1
        assert rows[0].difference == Decimal("100.00")

        # audit written atomically with the close
        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.branch_id == 1,
                        AuditLog.entity == "daily_close",
                        AuditLog.entity_id == rows[0].id,
                    )
                )
            ).scalars().all()
            assert len(audits) == 1
            assert audits[0].action == "close"

        # the same (branch, datee) cannot close twice
        dup = await _close_day(client, token, datee="2026-01-05", counted_cash="90")
        assert dup.status_code == 409
    finally:
        await _cleanup_drawer()
        assert await _day_rows("2026-01-05") == []


async def test_close_requires_auth(client):
    r = await client.post(
        "/api/v1/drawer/day-close",
        json={"datee": "2026-01-05", "counted_cash": "100"},
    )
    assert r.status_code == 401


async def test_close_snapshots_day_totals_from_a_real_cash_sale(client):
    """A 120.00 cash sale: expected 120, net_cash 120, COGS 60, VAT 14.74,
    net profit 45.26 — the full drawer equation snapshot."""
    _mark_closed("2026-01-07")
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
                "datee": "2026-01-07",
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rc = await _close_day(client, token, datee="2026-01-07", counted_cash="120")
        assert rc.status_code == 200, rc.text
        body = rc.json()
        assert body["status"] == "closed"
        assert body["drawer_start"] == "0.00"
        assert body["expected_cash"] == "120.00"
        assert body["difference"] == "0.00"
        assert body["net_cash"] == "120.00"
        assert body["net_network"] == "0.00"
        assert body["manual_cash"] == "0.00"
        assert body["manual_card"] == "0.00"
        assert body["purchases"] == "0.00"
        assert body["expenses"] == "0.00"
        assert body["cost_of_sales"] == "60.00"
        assert body["net_profit"] == "45.26"
        assert body["discounts"] == "0.00"
        assert body["vat_sales"] == "14.74"
        assert body["vat_purchases"] == "0.00"
        assert body["vat_expenses"] == "0.00"
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)


async def test_reopen_is_manager_only_and_writes_reversal_audit(client):
    """A level-6 cashier gets 403 on reopen; a level-7 manager gets the
    reversal (status reopened, closed_by nulled) + a `reopen` audit row."""
    _mark_closed("2026-01-11")
    admin = await _login_token(client)
    manager = await _make_user(client, "drw_mgr_reopen", 7)
    cashier = await _make_user(client, "drw_cash_reopen", 6)
    try:
        rc = await _close_day(client, admin, datee="2026-01-11", counted_cash="0")
        assert rc.status_code == 200, rc.text
        close_id = rc.json()["id"]

        blocked = await client.post(
            f"/api/v1/drawer/day-close/{close_id}/reopen",
            headers={"Authorization": f"Bearer {cashier}"},
        )
        assert blocked.status_code == 403

        rr = await client.post(
            f"/api/v1/drawer/day-close/{close_id}/reopen",
            headers={"Authorization": f"Bearer {manager}"},
        )
        assert rr.status_code == 200, rr.text
        body = rr.json()
        assert body["status"] == "reopened"
        assert body["closed_by"] is None

        rows = await _day_rows("2026-01-11")
        assert rows[0].status == "reopened"

        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.branch_id == 1,
                        AuditLog.entity == "daily_close",
                        AuditLog.entity_id == close_id,
                        AuditLog.action == "reopen",
                    )
                )
            ).scalars().all()
            assert len(audits) == 1
            assert audits[0].old_value == "closed"
            assert "reversal" in audits[0].new_value
    finally:
        await _cleanup_drawer()
        await _delete_users(["drw_mgr_reopen", "drw_cash_reopen"])


async def test_reopened_day_can_be_closed_again(client):
    """After a reopen, a new close updates the SAME (branch, datee) row back to
    closed with a fresh ledger, and a close of an already-closed day stays 409."""
    _mark_closed("2026-01-12")
    admin = await _login_token(client)
    manager = await _make_user(client, "drw_mgr_reclose", 7)
    try:
        rc = await _close_day(client, admin, datee="2026-01-12", counted_cash="50")
        assert rc.status_code == 200
        close_id = rc.json()["id"]

        await client.post(
            f"/api/v1/drawer/day-close/{close_id}/reopen",
            headers={"Authorization": f"Bearer {manager}"},
        )
        # re-close the reopened day: same row flips back to closed
        rc2 = await _close_day(client, admin, datee="2026-01-12", counted_cash="60")
        assert rc2.status_code == 200, rc2.text
        assert rc2.json()["id"] == close_id
        assert rc2.json()["status"] == "closed"
        assert rc2.json()["difference"] == "60.00"

        rows = await _day_rows("2026-01-12")
        assert len(rows) == 1  # still one row for (branch, datee)
        assert rows[0].status == "closed"

        dup = await _close_day(client, admin, datee="2026-01-12", counted_cash="70")
        assert dup.status_code == 409
    finally:
        await _cleanup_drawer()
        await _delete_users(["drw_mgr_reclose"])


async def test_sale_on_a_closed_day_is_rejected(client):
    """AC3: a closed (branch, datee) never silently receives new movements —
    even a money document is refused until the day is reopened."""
    _mark_closed("2026-01-15")
    drug_id = await _make_drug_and_stock(
        price="10.0000", batches=[("20.0000", "5.0000", "2026-06-01")]
    )
    invoice_ids: list[int] = []
    try:
        admin = await _login_token(client)
        rc = await _close_day(client, admin, datee="2026-01-15", counted_cash="0")
        assert rc.status_code == 200

        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {admin}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}], "datee": "2026-01-15"},
        )
        assert r.status_code == 409
        assert "closed" in r.text
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)


async def test_reopened_day_accepts_new_movements_and_reclose_recomputes(client):
    """Reopen -> new sale lands in the drawer -> re-close recomputes the ledger
    (expected 120, net_cash 120, COGS 60)."""
    _mark_closed("2026-01-16")
    drug_id = await _make_drug_and_stock(
        price="10.0000", batches=[("20.0000", "5.0000", "2026-06-01")]
    )
    invoice_ids: list[int] = []
    try:
        admin = await _login_token(client)
        manager = await _make_user(client, "drw_mgr_16", 7)
        rc = await _close_day(client, admin, datee="2026-01-16", counted_cash="0")
        close_id = rc.json()["id"]
        await client.post(
            f"/api/v1/drawer/day-close/{close_id}/reopen",
            headers={"Authorization": f"Bearer {manager}"},
        )

        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {admin}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}], "datee": "2026-01-16"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rc2 = await _close_day(client, admin, datee="2026-01-16", counted_cash="120")
        assert rc2.status_code == 200, rc2.text
        body = rc2.json()
        assert body["status"] == "closed"
        assert body["expected_cash"] == "120.00"
        assert body["net_cash"] == "120.00"
        assert body["cost_of_sales"] == "60.00"
        assert body["difference"] == "0.00"
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)
        await _delete_users(["drw_mgr_16"])


async def test_difference_is_surplus_or_deficit(client):
    """counted above expected shows a surplus difference; below shows deficit."""
    _mark_closed("2026-01-17")
    admin = await _login_token(client)
    try:
        surplus = await _close_day(client, admin, datee="2026-01-17", counted_cash="150")
        assert surplus.status_code == 200
        assert surplus.json()["difference"] == "150.00"

        deficit = await _close_day(client, admin, datee="2026-01-18", counted_cash="-5")
        assert deficit.status_code == 400

        neg = await client.post(
            "/api/v1/drawer/day-close",
            headers={"Authorization": f"Bearer {admin}"},
            json={"datee": "2026-01-18", "counted_cash": "-5"},
        )
        assert neg.status_code == 400
    finally:
        await _cleanup_drawer()


async def test_day_close_and_movements_list_back(client):
    """The list endpoints return the snapshots + movements for a date."""
    _mark_closed("2026-01-19")
    admin = await _login_token(client)
    try:
        rc = await _close_day(client, admin, datee="2026-01-19", counted_cash="10")
        assert rc.status_code == 200

        r = await client.get(
            "/api/v1/drawer/day-close",
            params={"datee": "2026-01-19"},
            headers={"Authorization": f"Bearer {admin}"},
        )
        assert r.status_code == 200, r.text
        rows = r.json()["day_closes"]
        assert len(rows) == 1
        assert rows[0]["status"] == "closed"
        assert rows[0]["counted_cash"] == "10.00"

        m = await client.get(
            "/api/v1/drawer/movements",
            params={"datee": "2026-01-19"},
            headers={"Authorization": f"Bearer {admin}"},
        )
        assert m.status_code == 200, m.text
        assert m.json()["movements"] == []
    finally:
        await _cleanup_drawer()


async def test_drawer_is_scoped_per_branch(client):
    """A branch-2 user never sees branch-1's drawer closes or movements."""
    _mark_closed("2026-01-20")
    admin = await _login_token(client)
    other_branch = await _make_other_branch()
    try:
        rc = await _close_day(client, admin, datee="2026-01-20", counted_cash="10")
        assert rc.status_code == 200

        b2 = await _make_user(client, "drw_b2_user", 7, branch_id=other_branch)
        r = await client.get(
            "/api/v1/drawer/day-close",
            params={"datee": "2026-01-20"},
            headers={"Authorization": f"Bearer {b2}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["day_closes"] == []
    finally:
        await _cleanup_drawer()
        await _delete_users(["drw_b2_user"])
        await _delete_other_branch(other_branch)
