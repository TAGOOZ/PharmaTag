"""S1.5 sales-return validation (ticket #11): bad input, over-return, double
return, wrong entity, auth/permission and branch-scoping rejections.

Edge-case pass required before every close (AGENTS.md): empty/missing data,
dupes, boundary values, auth/permission failures, cross-branch isolation.
"""
from decimal import Decimal

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import User
from tests.purchase_test_utils import (
    _delete_other_branch,
    _make_drug,
    _make_other_branch,
    _make_supplier,
    _uniq,
)
from tests.purchase_test_utils import _cleanup as _purchase_cleanup
from tests.returns_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _return_batches,
    _sale,
    _stock_qty,
)
from tests.sales_test_utils import _make_user, _token_for


async def test_return_zero_or_negative_qty_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        for qty in ["0", "-3"]:
            r = await client.post(
                f"/api/v1/sales/{sale['id']}/return",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"ref_invoice_line_id": line_id, "qty": qty}]},
            )
            assert r.status_code == 400, qty
        assert await _stock_qty(drug_id) == Decimal("0")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_over_quantity_rejected(client):
    """Returning more than the sold qty is rejected; stock untouched."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "11"}]},
        )
        assert r.status_code == 400
        assert "cannot return more" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("0")
        assert await _return_batches(drug_id) == []
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_same_line_twice_rejected(client):
    """A second return may only cover what the first left (qty - returned)."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        first = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "4"}]},
        )
        assert first.status_code == 201, first.text
        invoice_ids.append(first.json()["id"])
        assert await _stock_qty(drug_id) == Decimal("4")
        second = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "7"}]},
        )
        assert second.status_code == 400
        assert "cannot return more" in second.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("4")
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_line_from_another_invoice_rejected(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale_a = await _sale(client, token, [{"drug_id": drug_id, "qty": "2"}])
        sale_b = await _sale(client, token, [{"drug_id": drug_id, "qty": "3"}])
        invoice_ids += [sale_a["id"], sale_b["id"]]
        other_line_id = sale_b["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale_a['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": other_line_id, "qty": "1"}]},
        )
        assert r.status_code == 400
        assert "does not reference a line" in r.json()["detail"]
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_return_unknown_invoice_404(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/sales/99999999/return",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
    )
    assert r.status_code == 404


async def test_return_non_sale_invoice_rejected(client):
    """A purchase invoice is not returnable via the sales-return endpoint."""
    drug_id = await _make_drug(tax_type="14%")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await client.post(
            "/api/v1/purchases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "supplier_id": supplier_id,
                "lines": [{"drug_id": drug_id, "qty": "5", "unit_cost": "5.0000"}],
            },
        )
        assert pur.status_code == 201, pur.text
        invoice_ids.append(pur.json()["id"])
        r = await client.post(
            f"/api/v1/purchases/{pur.json()['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
        )
        assert r.status_code in (400, 404), r.text
        r2 = await client.post(
            f"/api/v1/sales/{pur.json()['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur.json()["lines"][0]["id"], "qty": "1"}]},
        )
        assert r2.status_code == 400
        assert "saved sale" in r2.json()["detail"]
    finally:
        await _purchase_cleanup([drug_id], invoice_ids, [supplier_id])


async def test_return_unauthenticated_401(client):
    r = await client.post(
        "/api/v1/sales/1/return",
        json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
    )
    assert r.status_code == 401


async def test_return_forbidden_when_no_permission(client):
    """A level-0 user holds no sale.create (legacy floor is level 1)."""
    user_id = await _make_user(_uniq("user"), permission_level=0, branch_id=1)
    try:
        r = await client.post(
            "/api/v1/sales/1/return",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
            json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 403
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_return_user_without_branch_rejected(client):
    user_id = await _make_user(_uniq("user"), permission_level=9, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/sales/1/return",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
            json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_return_cross_branch_404(client):
    """A sale made on branch 1 is invisible to a branch-2 caller."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    other_branch = await _make_other_branch()
    other_user_id = await _make_user(
        _uniq("other"), permission_level=9, branch_id=other_branch
    )
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "2"}])
        invoice_ids.append(sale["id"])
        line_id = sale["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/sales/{sale['id']}/return",
            headers={"Authorization": f"Bearer {_token_for(other_user_id, other_branch)}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "1"}]},
        )
        assert r.status_code == 404
    finally:
        await _cleanup([drug_id], invoice_ids)
        await _delete_other_branch(other_branch)