"""S1.8 drawer + day close (ticket #14): the drawer equation
(`expected = drawer_start + (cash_in − drawer_start) − cash_out`, opening float
counted once, `difference = counted − expected`)
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
from tests.purchase_returns_test_utils import _cleanup as _purchase_cleanup, _purchase
from tests.purchase_test_utils import _delete_other_branch, _make_drug, _make_other_branch, _make_supplier
from tests.receivables_test_utils import _cleanup_party, _cleanup_vouchers, _voucher
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
    _mark_closed("2026-01-18")
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


async def test_reclose_resnapshots_drawer_start(client):
    """Re-closing a reopened day re-computes drawer_start from the fresh
    ledger instead of trusting the stored snapshot. The corrected float is
    entered through the API as an opening + a cash correction (drawer_start =
    opening + net corrections), and the re-close reflects it."""
    _mark_closed("2026-01-27")
    admin = await _login_token(client)
    manager = await _make_user(client, "drw_mgr_27", 7)
    try:
        rc = await _close_day(client, admin, datee="2026-01-27", counted_cash="0")
        assert rc.status_code == 200, rc.text
        close_id = rc.json()["id"]
        assert rc.json()["drawer_start"] == "0.00"

        rr = await client.post(
            f"/api/v1/drawer/day-close/{close_id}/reopen",
            headers={"Authorization": f"Bearer {manager}"},
        )
        assert rr.status_code == 200, rr.text

        for body in [
            {"direction": "in", "reason": "opening", "method": "cash", "amount": "50.00"},
            {"direction": "in", "reason": "correction", "method": "cash", "amount": "10.00"},
        ]:
            r = await client.post(
                "/api/v1/drawer/movements",
                headers={"Authorization": f"Bearer {admin}"},
                json={**body, "datee": "2026-01-27"},
            )
            assert r.status_code == 201, r.text

        rc2 = await _close_day(client, admin, datee="2026-01-27", counted_cash="60")
        assert rc2.status_code == 200, rc2.text
        body = rc2.json()
        assert body["id"] == close_id
        assert body["drawer_start"] == "60.00"
        assert body["expected_cash"] == "60.00"
        assert body["manual_cash"] == "60.00"
        assert body["difference"] == "0.00"
    finally:
        await _cleanup_drawer()
        await _delete_users(["drw_mgr_27"])


async def test_correction_out_cannot_take_the_float_below_zero(client):
    """A cash correction adjusts the float record (drawer_start); a
    correction-out that would push the day's float below zero is refused (400),
    so a mis-entered correction can never produce a negative drawer_start. The
    float is consumed down to zero but never past it."""
    _mark_closed("2026-02-07")
    admin = await _login_token(client)
    try:
        for body in [
            {"direction": "in", "reason": "opening", "method": "cash", "amount": "50.00"},
        ]:
            r = await client.post(
                "/api/v1/drawer/movements",
                headers={"Authorization": f"Bearer {admin}"},
                json={**body, "datee": "2026-02-07"},
            )
            assert r.status_code == 201, r.text

        oversized = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "out",
                "reason": "correction",
                "method": "cash",
                "amount": "60.00",
                "datee": "2026-02-07",
            },
        )
        assert oversized.status_code == 400
        assert "below zero" in oversized.text

        ok = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "out",
                "reason": "correction",
                "method": "cash",
                "amount": "40.00",
                "datee": "2026-02-07",
            },
        )
        assert ok.status_code == 201, ok.text

        past_zero = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "out",
                "reason": "correction",
                "method": "cash",
                "amount": "20.00",
                "datee": "2026-02-07",
            },
        )
        assert past_zero.status_code == 400
        assert "below zero" in past_zero.text

        rc = await _close_day(client, admin, datee="2026-02-07", counted_cash="10")
        assert rc.status_code == 200, rc.text
        assert rc.json()["drawer_start"] == "10.00"
        assert rc.json()["expected_cash"] == "10.00"
        assert rc.json()["difference"] == "0.00"
    finally:
        await _cleanup_drawer()


async def test_duplicate_opening_on_a_closed_day_is_409(client):
    """A closed day rejects ANY movement with 409 — even a duplicate opening,
    which (with no existing opening) previously slipped past the opening guard
    to the duplicate check and returned 400. Closed always wins."""
    _mark_closed("2026-02-06")
    admin = await _login_token(client)
    try:
        first = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "50.00",
                "datee": "2026-02-06",
            },
        )
        assert first.status_code == 201, first.text

        rc = await _close_day(client, admin, datee="2026-02-06", counted_cash="50")
        assert rc.status_code == 200, rc.text

        dup = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "20.00",
                "datee": "2026-02-06",
            },
        )
        assert dup.status_code == 409
        assert "closed" in dup.text
    finally:
        await _cleanup_drawer()


async def test_opening_float_counts_once_in_expected_cash(client):
    """An opening movement is the drawer_start; it must NOT also count as a
    cash_in — expected = drawer_start + cash_in − cash_out would double it.
    The opening is also manual cash (net manual = opening − manual out)."""
    _mark_closed("2026-01-22")
    admin = await _login_token(client)
    try:
        r = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "40.00",
                "datee": "2026-01-22",
            },
        )
        assert r.status_code == 201, r.text

        rc = await _close_day(client, admin, datee="2026-01-22", counted_cash="40")
        assert rc.status_code == 200, rc.text
        body = rc.json()
        assert body["drawer_start"] == "40.00"
        assert body["expected_cash"] == "40.00"
        assert body["difference"] == "0.00"
        assert body["manual_cash"] == "40.00"
    finally:
        await _cleanup_drawer()


async def test_purchase_payment_is_not_manual_cash(client):
    """A cash purchase (supplier_pay) is a purchase outflow, not a manual cash
    movement: manual_cash stays 0, purchases carries the total, and the drawer
    equation drops by the cash paid out."""
    _mark_closed("2026-01-23")
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        admin = await _login_token(client)
        pur = await _purchase(
            client,
            admin,
            supplier_id,
            [{"drug_id": drug_id, "qty": "10", "unit_cost": "10.0000"}],
            payments=[{"method": "cash", "amount": "114.00"}],
            datee="2026-01-23",
        )
        invoice_ids.append(pur["id"])

        rc = await _close_day(client, admin, datee="2026-01-23", counted_cash="0")
        assert rc.status_code == 200, rc.text
        body = rc.json()
        assert body["manual_cash"] == "0.00"
        assert body["purchases"] == "114.00"
        assert body["expected_cash"] == "-114.00"
    finally:
        await _cleanup_drawer()
        await _purchase_cleanup([drug_id], invoice_ids, [supplier_id])


async def test_manual_cash_and_card_are_net_manual_movements(client):
    """manual_cash = net of the manual cash movements (opening in − expense
    out); manual_card = net of the manual network movements (customer
    settlement in); neither counts sale/purchase flows."""
    _mark_closed("2026-01-24")
    admin = await _login_token(client)
    try:
        for body in [
            {"direction": "in", "reason": "opening", "method": "cash", "amount": "50.00"},
            {"direction": "out", "reason": "expense", "method": "cash", "amount": "12.50"},
            {"direction": "in", "reason": "customer_settlement", "method": "network", "amount": "30.00"},
        ]:
            r = await client.post(
                "/api/v1/drawer/movements",
                headers={"Authorization": f"Bearer {admin}"},
                json={**body, "datee": "2026-01-24"},
            )
            assert r.status_code == 201, r.text

        rc = await _close_day(client, admin, datee="2026-01-24", counted_cash="37.50")
        assert rc.status_code == 200, rc.text
        body = rc.json()
        assert body["drawer_start"] == "50.00"
        assert body["manual_cash"] == "37.50"
        assert body["manual_card"] == "30.00"
        assert body["expected_cash"] == "37.50"
        assert body["difference"] == "0.00"
    finally:
        await _cleanup_drawer()


async def test_supplier_payment_has_named_day_report_column(client):
    """A payment voucher (سند صرف) is neither a purchase nor a manual movement:
    it gets its own named day-report figure (supplier_payments) so the payment
    shows in the report the way a receipt shows in manual_cash/manual_card
    (#19 review: the day-report classification asymmetry)."""
    _mark_closed("2026-01-26")
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        await _voucher(
            client,
            token,
            voucher_type="payment",
            party_id=supplier_id,
            datee="2026-01-26",
            amount="30.00",
            description="dayreport",
        )
        rc = await _close_day(client, token, datee="2026-01-26", counted_cash="0")
        assert rc.status_code == 200, rc.text
        body = rc.json()
        assert body["supplier_payments"] == "30.00"
        assert body["manual_cash"] == "0.00"
        assert body["manual_card"] == "0.00"
        assert body["purchases"] == "0.00"
        assert body["expected_cash"] == "-30.00"
    finally:
        await _cleanup_drawer()
        await _cleanup_vouchers("dayreport")
        await _cleanup_party(supplier_id)


async def test_card_only_day_close_reports_net_network(client):
    """A card sale is a network split: it never enters the cash drawer equation
    (expected_cash stays 0) but is snapshotted into net_network — manual_card
    stays 0 because card sales are not manual movements."""
    _mark_closed("2026-01-25")
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
                "payments": [{"method": "card", "amount": "120.00"}],
                "datee": "2026-01-25",
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        rc = await _close_day(client, token, datee="2026-01-25", counted_cash="0")
        assert rc.status_code == 200, rc.text
        body = rc.json()
        assert body["drawer_start"] == "0.00"
        assert body["expected_cash"] == "0.00"
        assert body["net_cash"] == "0.00"
        assert body["net_network"] == "120.00"
        assert body["manual_cash"] == "0.00"
        assert body["manual_card"] == "0.00"
        assert body["difference"] == "0.00"
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)


async def test_reopen_of_another_branch_close_is_404(client):
    """A manager of branch 2 cannot reopen branch 1's day close — the row is
    scoped to its branch and the reopen must 404, never touch it."""
    _mark_closed("2026-01-26")
    admin = await _login_token(client)
    other_branch = await _make_other_branch()
    try:
        rc = await _close_day(client, admin, datee="2026-01-26", counted_cash="10")
        assert rc.status_code == 200
        close_id = rc.json()["id"]

        b2 = await _make_user(client, "drw_b2_mgr", 7, branch_id=other_branch)
        rr = await client.post(
            f"/api/v1/drawer/day-close/{close_id}/reopen",
            headers={"Authorization": f"Bearer {b2}"},
        )
        assert rr.status_code == 404

        rows = await _day_rows("2026-01-26")
        assert rows[0].status == "closed"
    finally:
        await _cleanup_drawer()
        await _delete_users(["drw_b2_mgr"])
        await _delete_other_branch(other_branch)
