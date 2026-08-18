"""S1.7 count-request submission (ticket #13): a staff user enters the
physical counted qty; the server derives the signed delta and stores a pending
`stock_correction_requests` row for manager approval (feature_stock_counting
§2.4, plan/02 §4.4)."""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import StockCorrectionRequest, User
from tests.stock_test_utils import (
    _cleanup,
    _delete_other_branch,
    _login_token,
    _make_drug_and_stock,
    _make_other_branch,
    _make_user,
    _request,
    _token_for,
    _uniq,
)


async def test_submit_count_request_stores_delta(client):
    """counted 12 vs system 10 -> delta +2, pending, no stock touched."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "12"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["delta"] == "2.0000"
        assert body["system_qty"] == "10.0000"
        request_ids.append(body["id"])

        row = await _request(request_ids[0])
        assert row.delta == Decimal("2.0000")
        assert row.status == "pending"
        assert row.decided_at is None
        assert row.requested_by is not None
    finally:
        await _cleanup([drug_id], request_ids)


async def test_submit_count_deficit_stores_negative_delta(client):
    """counted 3 vs system 10 -> delta -7."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "3"},
        )
        assert r.status_code == 201, r.text
        request_ids.append(r.json()["id"])
        assert r.json()["delta"] == "-7.0000"
    finally:
        await _cleanup([drug_id], request_ids)


async def test_submit_counted_matches_system_rejected(client):
    """counted == system -> no correction; the request is rejected (400)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "10"},
        )
        assert r.status_code == 400
        assert "nothing to correct" in r.json()["detail"]
    finally:
        await _cleanup([drug_id])


async def test_submit_negative_counted_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "-1"},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id])


async def test_submit_unknown_drug_404(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/stock/count-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_id": 99999999, "counted": "5"},
    )
    assert r.status_code == 404


async def test_submit_inactive_drug_rejected(client):
    drug_id = await _make_drug_and_stock(tax_type="exempt")
    async with SessionLocal() as session:
        from app.models import Drug

        drug = await session.get(Drug, drug_id)
        drug.active = False
        await session.commit()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "5"},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id])


async def test_submit_unauthenticated_401(client):
    r = await client.post(
        "/api/v1/stock/count-requests", json={"drug_id": 1, "counted": "5"}
    )
    assert r.status_code == 401


async def test_submit_user_without_branch_400(client):
    user_id = await _make_user(_uniq("user"), permission_level=9, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
            json={"drug_id": 1, "counted": "5"},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            from app.models import User

            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_submit_any_authenticated_user_allowed(client):
    """The modern flow lets any staff user submit (feature §2.4) — level 1 ok."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    user_id = await _make_user(_uniq("cashier"), permission_level=1, branch_id=1)
    request_ids: list[int] = []
    try:
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
            json={"drug_id": drug_id, "counted": "11"},
        )
        assert r.status_code == 201, r.text
        request_ids.append(r.json()["id"])
        assert r.json()["requested_by"] == user_id
    finally:
        await _cleanup([drug_id], request_ids)
        async with SessionLocal() as session:
            from app.models import User

            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_list_count_requests(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        for counted in ["12", "8"]:
            r = await client.post(
                "/api/v1/stock/count-requests",
                headers={"Authorization": f"Bearer {token}"},
                json={"drug_id": drug_id, "counted": counted},
            )
            assert r.status_code == 201, r.text
            request_ids.append(r.json()["id"])

        g = await client.get(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert g.status_code == 200
        ids = [item["id"] for item in g.json()["requests"]]
        assert set(request_ids) <= set(ids)
        by_id = {item["id"]: item for item in g.json()["requests"]}
        assert by_id[request_ids[0]]["delta"] == "2.0000"
        assert by_id[request_ids[1]]["delta"] == "-2.0000"
        assert all(item["status"] == "pending" for item in g.json()["requests"])

        g2 = await client.get(
            "/api/v1/stock/count-requests?status_filter=approved",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert all(item["status"] == "approved" for item in g2.json()["requests"])
    finally:
        await _cleanup([drug_id], request_ids)


async def test_list_requests_scoped_to_own_branch(client):
    """A request submitted on branch 1 is invisible to a branch-2 caller."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    other_branch = await _make_other_branch()
    other_user_id = await _make_user(
        _uniq("other"), permission_level=9, branch_id=other_branch
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {token}"},
            json={"drug_id": drug_id, "counted": "12"},
        )
        request_ids.append(r.json()["id"])
        g = await client.get(
            "/api/v1/stock/count-requests",
            headers={"Authorization": f"Bearer {_token_for(other_user_id, other_branch)}"},
        )
        assert g.status_code == 200
        assert all(item["id"] != request_ids[0] for item in g.json()["requests"])
    finally:
        await _cleanup([drug_id], request_ids)
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == other_user_id))
            await session.commit()
        await _delete_other_branch(other_branch)