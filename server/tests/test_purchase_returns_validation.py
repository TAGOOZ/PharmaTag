"""S1.6 purchase-return validation (ticket #12): bad input, over-return,
double return, wrong entity, auth/permission and branch-scoping rejections.

Edge-case pass required before every close (AGENTS.md): empty/missing data,
dupes, boundary values, auth/permission failures, cross-branch isolation.
"""
from decimal import Decimal

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import User
from tests.purchase_test_utils import (
    _delete_other_branch,
    _make_other_branch,
    _make_user,
    _token_for,
    _uniq,
)
from tests.purchase_returns_test_utils import (
    _batches,
    _cleanup,
    _login_token,
    _make_drug,
    _make_supplier,
    _purchase,
    _stock_qty,
)


async def test_purchase_return_zero_or_negative_qty_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "5.0000"}]
        )
        invoice_ids.append(pur["id"])
        line_id = pur["lines"][0]["id"]
        for qty in ["0", "-3"]:
            r = await client.post(
                f"/api/v1/purchases/{pur['id']}/return",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"ref_invoice_line_id": line_id, "qty": qty}]},
            )
            assert r.status_code == 400, qty
        assert await _stock_qty(drug_id) == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_over_quantity_rejected(client):
    """Returning more than the purchased qty is rejected; stock untouched."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "5.0000"}]
        )
        invoice_ids.append(pur["id"])
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "11"}]},
        )
        assert r.status_code == 400
        assert "cannot return more" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("10.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_same_line_twice_rejected(client):
    """A second return may only cover what the first left (qty - returned)."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "5.0000"}]
        )
        invoice_ids.append(pur["id"])
        line_id = pur["lines"][0]["id"]
        first = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "4"}]},
        )
        assert first.status_code == 201, first.text
        invoice_ids.append(first.json()["id"])
        assert await _stock_qty(drug_id) == Decimal("6.0000")
        second = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "7"}]},
        )
        assert second.status_code == 400
        assert "cannot return more" in second.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("6.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_line_from_another_invoice_rejected(client):
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur_a = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "2", "unit_cost": "5.0000"}]
        )
        pur_b = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "3", "unit_cost": "5.0000"}]
        )
        invoice_ids += [pur_a["id"], pur_b["id"]]
        r = await client.post(
            f"/api/v1/purchases/{pur_a['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": pur_b["lines"][0]["id"], "qty": "1"}]},
        )
        assert r.status_code == 400
        assert "does not reference a line" in r.json()["detail"]
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_unknown_invoice_404(client):
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/purchases/99999999/return",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
    )
    assert r.status_code == 404


async def test_purchase_return_non_purchase_invoice_rejected(client):
    """A sale invoice is not returnable via the purchase-return endpoint."""
    from tests.returns_test_utils import _sale
    from tests.sales_test_utils import _make_drug_and_stock

    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        sale = await _sale(client, token, [{"drug_id": drug_id, "qty": "10"}])
        invoice_ids.append(sale["id"])
        r = await client.post(
            f"/api/v1/purchases/{sale['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": sale["lines"][0]["id"], "qty": "1"}]},
        )
        assert r.status_code == 400
        assert "saved purchase" in r.json()["detail"]
    finally:
        await _cleanup([drug_id], invoice_ids, [])


async def test_purchase_return_chained_return_rejected(client):
    """A purchase_return invoice is itself not returnable."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "5.0000"}]
        )
        invoice_ids.append(pur["id"])
        ret = await _return_direct(client, token, pur, "4")
        invoice_ids.append(ret["id"])
        ret_line_id = ret["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/purchases/{ret['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": ret_line_id, "qty": "1"}]},
        )
        assert r.status_code == 400
        assert "saved purchase" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("6.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_limited_by_batch_after_sale(client):
    """A batch partly sold can only give back what physically remains: after
    selling 5 of the 10 purchased, returning 6 is rejected; 4 succeeds."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "10", "unit_cost": "5.0000"}]
        )
        invoice_ids.append(pur["id"])
        # sell 5 against the purchased batch (exempt, price 0)
        from tests.returns_test_utils import _sale

        await _sale(
            client, token, [{"drug_id": drug_id, "qty": "5"}],
        )
        assert await _stock_qty(drug_id) == Decimal("5.0000")
        line_id = pur["lines"][0]["id"]
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "6"}]},
        )
        assert r.status_code == 400
        assert "batch" in r.json()["detail"]
        assert await _stock_qty(drug_id) == Decimal("5.0000")
        ok = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"ref_invoice_line_id": line_id, "qty": "4"}]},
        )
        assert ok.status_code == 201, ok.text
        invoice_ids.append(ok.json()["id"])
        assert await _stock_qty(drug_id) == Decimal("1.0000")
        batches = await _batches(drug_id)
        assert batches[0].qty == Decimal("1.0000")
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])


async def test_purchase_return_unauthenticated_401(client):
    r = await client.post(
        "/api/v1/purchases/1/return",
        json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
    )
    assert r.status_code == 401


async def test_purchase_return_forbidden_below_purchases_level(client):
    """The purchases area needs legacy level >= 2; a level-1 (sales-only) user
    is forbidden."""
    user_id = await _make_user(_uniq("user"), permission_level=1, branch_id=1)
    try:
        r = await client.post(
            "/api/v1/purchases/1/return",
            headers={"Authorization": f"Bearer {_token_for(user_id, 1)}"},
            json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 403
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_purchase_return_user_without_branch_rejected(client):
    user_id = await _make_user(_uniq("user"), permission_level=9, branch_id=None)
    try:
        r = await client.post(
            "/api/v1/purchases/1/return",
            headers={"Authorization": f"Bearer {_token_for(user_id, None)}"},
            json={"lines": [{"ref_invoice_line_id": 1, "qty": "1"}]},
        )
        assert r.status_code == 400
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_purchase_return_cross_branch_404(client):
    """A purchase made on branch 1 is invisible to a branch-2 caller."""
    drug_id = await _make_drug(tax_type="exempt")
    supplier_id = await _make_supplier()
    invoice_ids: list[int] = []
    other_branch = await _make_other_branch()
    other_user_id = await _make_user(
        _uniq("other"), permission_level=9, branch_id=other_branch
    )
    try:
        token = await _login_token(client)
        pur = await _purchase(
            client, token, supplier_id, [{"drug_id": drug_id, "qty": "2", "unit_cost": "5.0000"}]
        )
        invoice_ids.append(pur["id"])
        r = await client.post(
            f"/api/v1/purchases/{pur['id']}/return",
            headers={"Authorization": f"Bearer {_token_for(other_user_id, other_branch)}"},
            json={"lines": [{"ref_invoice_line_id": pur["lines"][0]["id"], "qty": "1"}]},
        )
        assert r.status_code == 404
    finally:
        await _cleanup([drug_id], invoice_ids, [supplier_id])
        await _delete_other_branch(other_branch)


async def _return_direct(client, token: str, purchase: dict, qty: str) -> dict:
    r = await client.post(
        f"/api/v1/purchases/{purchase['id']}/return",
        headers={"Authorization": f"Bearer {token}"},
        json={"lines": [{"ref_invoice_line_id": purchase["lines"][0]["id"], "qty": qty}]},
    )
    assert r.status_code == 201, r.text
    return r.json()