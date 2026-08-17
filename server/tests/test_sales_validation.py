"""S1.3 sales validation (ticket #9): bad input, missing/inactive entities,
auth failures, permission and branch-scoping rejections.

Edge-case pass required before every close (AGENTS.md): empty/missing data,
dupes, boundary values, auth/permission failures.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Drug, User
from tests.sales_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _make_user,
    _stock_qty,
    _token_for,
    _uniq,
)


async def test_sale_zero_or_negative_qty_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        for qty in ["0", "-3"]:
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": qty}]},
            )
            assert r.status_code == 400, qty
        assert await _stock_qty(drug_id) == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], [])


async def test_sale_empty_lines_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": []},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id], [])


async def test_sale_unknown_drug_404(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/sales",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"drug_id": 99999999, "qty": "1"}]},
    )
    assert r.status_code == 404


async def test_sale_inactive_drug_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    async with SessionLocal() as session:
        drug = await session.get(Drug, drug_id)
        drug.active = False
        await session.commit()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            drug = await session.get(Drug, drug_id)
            drug.active = True
            await session.commit()
        await _cleanup([drug_id], [])


async def test_sale_discount_exceeds_total_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "2"}], "disc_percent": "200"},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id], [])


async def test_sale_unauthenticated_401(client):
    r = await client.post(
        "/api/v1/sales",
        json={"lines": [{"drug_id": 1, "qty": "1"}]},
    )
    assert r.status_code == 401


async def test_sale_forbidden_when_no_permission(client):
    """A level-0 user holds no sale.create (legacy floor is level 1)."""
    user_id = await _make_user(_uniq("user"), permission_level=0, branch_id=1)
    try:
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
            json={"lines": [{"drug_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 403
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_sale_user_without_branch_rejected(client):
    user_id = await _make_user(_uniq("user"), permission_level=9, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
            json={"lines": [{"drug_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()