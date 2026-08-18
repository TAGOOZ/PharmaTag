"""S1.8 manual drawer movements (ticket #14, A07).

Manual movements (opening/expense/transfer/correction/supplier pay/customer
settlement) are gated by `drawer.manage` (legacy floor 3, customizable via
roles); each writes its audit row atomically (G12) and a closed day rejects
them with 409 — reopen first.
"""
from tests.drawer_test_utils import (
    _cleanup_drawer,
    _close_day,
    _delete_users,
    _login_token,
    _make_user,
    _mark_closed,
    _movement_rows,
    _movements,
)


async def test_manual_movement_needs_drawer_manage(client):
    """A level-2 user (below the floor 3) gets 403; admin records a manual
    opening + expense with audit, attributed to the cashier."""
    _mark_closed("2026-01-13")
    admin = await _login_token(client)
    low = await _make_user(client, "drw_low_manual", 2)
    try:
        blocked = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {low}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "50.00",
                "datee": "2026-01-13",
            },
        )
        assert blocked.status_code == 403

        r = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "50.00",
                "datee": "2026-01-13",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["direction"] == "in"
        assert body["reason"] == "opening"
        assert body["method"] == "cash"
        assert body["amount"] == "50.00"

        r2 = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "out",
                "reason": "expense",
                "method": "cash",
                "amount": "12.50",
                "datee": "2026-01-13",
            },
        )
        assert r2.status_code == 201, r2.text

        movements = await _movements(client, admin, datee="2026-01-13")
        assert len(movements) == 2
        by = {(m["reason"], m["direction"]): m["amount"] for m in movements}
        assert by == {("opening", "in"): "50.00", ("expense", "out"): "12.50"}

        rows = await _movement_rows("2026-01-13")
        assert len(rows) == 2
        assert all(r.user_id is not None for r in rows)
    finally:
        await _cleanup_drawer()
        await _delete_users(["drw_low_manual"])


async def test_manual_movement_rejects_closed_day_and_bad_amount(client):
    """A closed (branch, datee) takes no manual movements (409); amount must be
    positive (400)."""
    _mark_closed("2026-01-14")
    admin = await _login_token(client)
    try:
        rc = await _close_day(client, admin, datee="2026-01-14", counted_cash="0")
        assert rc.status_code == 200

        r = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "out",
                "reason": "expense",
                "method": "cash",
                "amount": "5.00",
                "datee": "2026-01-14",
            },
        )
        assert r.status_code == 409

        zero = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "out",
                "reason": "expense",
                "method": "cash",
                "amount": "0.00",
                "datee": "2026-01-14",
            },
        )
        assert zero.status_code == 400
    finally:
        await _cleanup_drawer()