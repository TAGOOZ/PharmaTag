"""S1.7 approval gates (ticket #13, plan/02 §3.3): approving or rejecting a
count request requires permission_level >= 7 and an account on the same branch;
rejection must not touch stock."""
from decimal import Decimal

from sqlalchemy import delete, select, update

from app.core.db import SessionLocal
from app.models import AuditLog, Journal, StockBatch, StockCorrectionRequest, User
from tests.stock_test_utils import (
    _cleanup,
    _delete_other_branch,
    _login_token,
    _make_drug_and_stock,
    _make_other_branch,
    _make_user,
    _request,
    _stock_qty,
    _token_for,
    _uniq,
)


async def _submit(client, token, drug_id, counted) -> int:
    r = await client.post(
        "/api/v1/stock/count-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_id": drug_id, "counted": counted},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _decide(client, token, request_id, action: str):
    return await client.post(
        f"/api/v1/stock/count-requests/{request_id}/{action}",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _drop_user(user_id: int) -> None:
    """A decided request references the caller via journals/audit — null those
    FKs before deleting the user (test hygiene on the throwaway DB)."""
    async with SessionLocal() as session:
        for table in (Journal, AuditLog, StockCorrectionRequest, StockBatch):
            if any(c.name == "created_by" for c in table.__table__.columns):
                await session.execute(
                    update(table)
                    .where(getattr(table, "created_by") == user_id)
                    .values(created_by=None)
                )
        if any(c.name == "user_id" for c in AuditLog.__table__.columns):
            await session.execute(
                update(AuditLog).where(AuditLog.user_id == user_id).values(user_id=None)
            )
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_approve_requires_level_7(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    low_user = await _make_user(_uniq("cashier"), permission_level=6, branch_id=1)
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)

        r = await _decide(client, _token_for(low_user, 1), request_id, "approve")
        assert r.status_code == 403
        row = await _request(request_id)
        assert row.status == "pending"
        assert await _stock_qty(drug_id) == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], request_ids)
        await _drop_user(low_user)


async def test_reject_requires_level_7(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    low_user = await _make_user(_uniq("cashier"), permission_level=6, branch_id=1)
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)

        r = await _decide(client, _token_for(low_user, 1), request_id, "reject")
        assert r.status_code == 403
        assert (await _request(request_id)).status == "pending"
    finally:
        await _cleanup([drug_id], request_ids)
        await _drop_user(low_user)


async def test_level_7_can_approve(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    mgr = await _make_user(_uniq("manager"), permission_level=7, branch_id=1)
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)
        r = await _decide(client, _token_for(mgr, 1), request_id, "approve")
        assert r.status_code == 200, r.text
        assert (await _request(request_id)).status == "approved"
    finally:
        await _cleanup([drug_id], request_ids)
        await _drop_user(mgr)


async def test_cross_branch_approve_404(client):
    """A branch-2 manager cannot decide branch-1 requests (feature §2.4)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    other_branch = await _make_other_branch()
    other_mgr = await _make_user(
        _uniq("mgr2"), permission_level=9, branch_id=other_branch
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)
        r = await _decide(client, _token_for(other_mgr, other_branch), request_id, "approve")
        assert r.status_code == 404
        assert (await _request(request_id)).status == "pending"
    finally:
        await _cleanup([drug_id], request_ids)
        await _drop_user(other_mgr)
        await _delete_other_branch(other_branch)


async def test_reject_marks_rejected_without_touching_stock(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)
        r = await _decide(client, token, request_id, "reject")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"
        assert r.json()["decided_at"]
        assert await _stock_qty(drug_id) == Decimal("10.0000")  # untouched

        # batches untouched too
        async with SessionLocal() as session:
            from app.models import StockBatch

            qty = (
                await session.execute(
                    select(StockBatch.qty).where(
                        StockBatch.branch_id == 1, StockBatch.drug_id == drug_id
                    )
                )
            ).scalar_one()
            assert qty == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], request_ids)


async def test_reject_already_decided_409(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)
        assert (await _decide(client, token, request_id, "approve")).status_code == 200
        r = await _decide(client, token, request_id, "reject")
        assert r.status_code == 409
        assert "not pending" in r.json()["detail"]
        assert (await _request(request_id)).status == "approved"
    finally:
        await _cleanup([drug_id], request_ids)


async def test_approve_unauthenticated_401(client):
    r = await _decide(client, "", 1, "approve")
    assert r.status_code == 401

async def test_reject_sets_rejected_by_not_approved_by(client):
    """A rejection records WHO rejected (rejected_by); approved_by must stay
    empty — the shared column is for approvals only (edge pass #7)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        batches=[("10.0000", "5.0000", None)],
        stock_qty="10.0000",
    )
    mgr = await _make_user(_uniq("rejector"), permission_level=9, branch_id=1)
    request_ids: list[int] = []
    try:
        token = await _login_token(client)
        request_id = await _submit(client, token, drug_id, "15")
        request_ids.append(request_id)
        r = await _decide(client, _token_for(mgr, 1), request_id, "reject")
        assert r.status_code == 200, r.text
        assert r.json()["rejected_by"] == mgr
        assert r.json()["approved_by"] is None

        row = await _request(request_id)
        assert row.rejected_by == mgr
        assert row.approved_by is None
    finally:
        await _cleanup([drug_id], request_ids)
        await _drop_user(mgr)
