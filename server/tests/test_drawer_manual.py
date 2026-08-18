"""S1.8 manual drawer movements (ticket #14, A07).

Manual movements (opening/expense/transfer/correction/supplier pay/customer
settlement) are gated by `drawer.manage` (legacy floor 3, customizable via
roles); each writes its audit row atomically (G12) and a closed day rejects
them with 409 — reopen first. AC3 holds under concurrency too: the movement
writer takes the same per-branch advisory lock as the day close, so a movement
can never read "open" and then land on a (branch, datee) that was just closed.
"""
import asyncio

from app.core.db import SessionLocal
from app.sales.numbering import acquire_branch_lock
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
from tests.purchase_test_utils import _delete_other_branch, _make_other_branch
from tests.sales_test_utils import _cleanup, _make_drug_and_stock


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


async def test_only_one_opening_per_day(client):
    """An opening float is set once per (branch, datee); a duplicate opening is
    refused (400) so it can never inflate drawer_start, while another date is
    unaffected."""
    _mark_closed("2026-01-25")
    _mark_closed("2026-01-26")
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
                "datee": "2026-01-25",
            },
        )
        assert first.status_code == 201, first.text

        dup = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "20.00",
                "datee": "2026-01-25",
            },
        )
        assert dup.status_code == 400
        assert "opening" in dup.text

        other_day = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {admin}"},
            json={
                "direction": "in",
                "reason": "opening",
                "method": "cash",
                "amount": "30.00",
                "datee": "2026-01-26",
            },
        )
        assert other_day.status_code == 201, other_day.text
    finally:
        await _cleanup_drawer()


async def test_movement_blocks_until_the_branch_lock_is_free(client):
    """AC3 under concurrency: while another transaction holds the branch
    advisory lock, a manual movement cannot proceed (its guard must not read
    "open" and then commit after a close lands). The same lock the day close
    takes serializes movement writes."""
    _mark_closed("2026-01-21")
    admin = await _login_token(client)
    blocker = SessionLocal()
    try:
        await acquire_branch_lock(blocker, 1)

        task = asyncio.create_task(
            client.post(
                "/api/v1/drawer/movements",
                headers={"Authorization": f"Bearer {admin}"},
                json={
                    "direction": "in",
                    "reason": "opening",
                    "method": "cash",
                    "amount": "40.00",
                    "datee": "2026-01-21",
                },
            )
        )
        await asyncio.sleep(0.5)
        assert not task.done(), "movement must block until the branch lock is free"

        await blocker.commit()  # release the lock -> the movement proceeds
        mv = await task
        assert mv.status_code == 201, mv.text
        assert mv.json()["reason"] == "opening"
        assert mv.json()["amount"] == "40.00"
    finally:
        await blocker.rollback()
        await _cleanup_drawer()


async def test_manual_movement_ref_invoice_must_be_in_caller_branch(client):
    """ref_invoice_id is a cross-branch leak vector: a manual movement can only
    reference a money document of the caller's branch (400 otherwise)."""
    _mark_closed("2026-01-28")
    drug_id = await _make_drug_and_stock(
        price="10.0000", batches=[("20.0000", "5.0000", "2026-06-01")]
    )
    invoice_ids: list[int] = []
    other_branch = await _make_other_branch()
    try:
        admin = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {admin}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}], "datee": "2026-01-28"},
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])

        b2 = await _make_user(client, "drw_b2_refinv", 7, branch_id=other_branch)
        r2 = await client.post(
            "/api/v1/drawer/movements",
            headers={"Authorization": f"Bearer {b2}"},
            json={
                "direction": "out",
                "reason": "expense",
                "method": "cash",
                "amount": "5.00",
                "ref_invoice_id": invoice_ids[0],
                "datee": "2026-01-28",
            },
        )
        assert r2.status_code == 400, r2.text
        assert "ref_invoice_id" in r2.text
    finally:
        await _cleanup_drawer()
        await _cleanup([drug_id], invoice_ids)
        await _delete_users(["drw_b2_refinv"])
        await _delete_other_branch(other_branch)