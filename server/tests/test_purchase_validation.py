"""S1.4 purchase validation (ticket #10): bad input, missing/inactive entities,
auth failures, permission and branch-scoping rejections.

Edge-case pass required before every close (AGENTS.md): empty/missing data,
dupes, boundary values, auth/permission failures.
"""
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Party, User
from tests.purchase_test_utils import (
    _cleanup,
    _delete_other_branch,
    _login_token,
    _make_drug,
    _make_other_branch,
    _make_supplier,
    _make_user,
    _stock_qty,
    _token_for,
    _uniq,
)


async def test_purchase_zero_or_negative_qty_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        for qty in ["0", "-3"]:
            r = await client.post(
                "/api/v1/purchases",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "supplier_id": supplier_id,
                    "lines": [{"drug_id": drug_id, "qty": qty, "unit_cost": "5.0000"}],
                },
            )
            assert r.status_code == 400, qty
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], [], [supplier_id])


async def test_purchase_empty_lines_rejected(client):
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={"supplier_id": supplier_id, "lines": []},
        )
        assert r.status_code == 400
    finally:
        await _cleanup([], [], [supplier_id])


async def test_purchase_unknown_drug_404(client):
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": 99999999, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 404
    finally:
        await _cleanup([], [], [supplier_id])


async def test_purchase_inactive_drug_rejected(client):
    drug_id = await _make_drug(tax_type="exempt", active=False)
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 400
    finally:
        await _cleanup([drug_id], [], [supplier_id])


async def test_purchase_unknown_supplier_404(client):
    drug_id = await _make_drug(tax_type="exempt")
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": 99999999,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 404
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], [], [])


async def test_purchase_customer_as_supplier_rejected(client):
    """A party whose kind is customer cannot be the supplier of a purchase."""
    drug_id = await _make_drug(tax_type="exempt")
    async with SessionLocal() as session:
        party = Party(
            branch_id=1,
            kind="customer",
            namee=_uniq("cust"),
            randomid=_uniq("custid"),
            active=True,
        )
        session.add(party)
        await session.flush()
        customer_id = party.id
        await session.commit()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": customer_id,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 400
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], [], [customer_id])


async def test_purchase_inactive_supplier_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier(active=False)
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 400
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], [], [supplier_id])


async def test_purchase_payment_mismatch_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "2", "unit_cost": "10.0000"}],
                "payments": [{"method": "cash", "amount": "1.00"}],
            },
        )
        assert r.status_code == 400
        assert "payment total does not match" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], [], [supplier_id])


async def test_purchase_discount_exceeds_total_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "2", "unit_cost": "10.0000"}],
                "disc_percent": "200",
            },
        )
        assert r.status_code == 400
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], [], [supplier_id])


async def test_purchase_unauthenticated_401(client):
    r = await client.post(
        "/api/v1/purchases",
        json={"supplier_id": 1, "lines": [{"drug_id": 1, "qty": "1", "unit_cost": "1"}]},
    )
    assert r.status_code == 401


async def test_purchase_forbidden_below_purchases_level(client):
    """The purchases area needs legacy level >= 2 (permission '2' المشتريات);
    a level-1 (sales-only) user is forbidden."""
    user_id = await _make_user(_uniq("user"), permission_level=1, branch_id=1)
    try:
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
            json={"supplier_id": 1, "lines": [{"drug_id": 1, "qty": "1", "unit_cost": "1"}]},
        )
        assert r.status_code == 403
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_purchase_user_without_branch_rejected(client):
    user_id = await _make_user(_uniq("user"), permission_level=9, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
            json={"supplier_id": 1, "lines": [{"drug_id": 1, "qty": "1", "unit_cost": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_purchase_read_scoped_to_own_branch(client):
    """A purchase made by branch 1 is invisible to a branch-2 caller."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    other_branch = await _make_other_branch()
    other_user_id = await _make_user(
        _uniq("other"), permission_level=9, branch_id=other_branch
    )
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "1", "unit_cost": "5.0000"}],
            },
        )
        assert r.status_code == 201, r.text
        invoice_ids.append(r.json()["id"])
        g = await client.get(
            f"/api/v1/purchases/{invoice_ids[0]}",
            headers={"Authorization": f"Bearer {_token_for(other_user_id, other_branch)}"},
        )
        assert g.status_code == 404
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])
        await _delete_other_branch(other_branch)