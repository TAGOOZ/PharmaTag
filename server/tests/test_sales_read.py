"""S1.3 sales reads + numbering (ticket #9): invoice-number monotonicity,
branch-scoped list/detail, and cross-branch invisibility."""
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import User
from tests.sales_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
    _seq,
    _token_for,
    _uniq,
)


async def test_sale_invoice_numbers_monotonic(client):
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("20.0000", "5.0000", None)], stock_qty="20.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        numbers = []
        for _ in range(2):
            r = await client.post(
                "/api/v1/sales",
                headers={"Authorization": f"Bearer {token}"},
                json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
            )
            assert r.status_code == 201, r.text
            body = r.json()
            invoice_ids.append(body["id"])
            numbers.append(int(body["invoice_no"]))
        assert numbers[1] > numbers[0], "invoice numbers must be monotonic"
        assert len(set(numbers)) == 2
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_get_list_and_detail(client):
    drug_id = await _make_drug_and_stock(
        tax_type="14%", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "2"}]},
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]
        invoice_ids.append(sale_id)

        lst = await client.get(
            "/api/v1/sales", headers={"Authorization": f"Bearer {token}"}
        )
        assert lst.status_code == 200
        assert any(s["id"] == sale_id for s in lst.json()["sales"])

        det = await client.get(
            f"/api/v1/sales/{sale_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert det.status_code == 200
        body = det.json()
        assert body["invoice_no"].isdigit()
        assert body["journal"]["balanced"] is True
        assert body["journal"]["debit_total"] == body["journal"]["credit_total"]
        assert body["journal"]["debit_total"] == "30.00"  # 20 drawer + 10 cogs
    finally:
        await _cleanup([drug_id], invoice_ids)


async def test_sale_cross_branch_read_404(client):
    """A sale on branch 1 is invisible to a branch-2 user (branch-scoped read)."""
    drug_id = await _make_drug_and_stock(
        tax_type="exempt", price="10.0000",
        batches=[("10.0000", "5.0000", None)], stock_qty="10.0000",
    )
    invoice_ids: list[int] = []
    branch_id = None
    user_id = None
    try:
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "1"}]},
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]
        invoice_ids.append(sale_id)

        async with SessionLocal() as session:
            Branch = __import__("app.models", fromlist=["Branch"]).Branch
            branch = Branch(
                pharmacyid=f"t2ph{_seq[0]}",
                mobile="0",
                pharname="Other Branch",
            )
            session.add(branch)
            await session.flush()
            branch_id = branch.id
            user = User(
                username=_uniq("user"),
                pass_hash="x",
                permission_level=9,
                branch_id=branch_id,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        other = await client.get(
            f"/api/v1/sales/{sale_id}",
            headers={"Authorization": f"Bearer {_token_for(user_id, branch_id)}"},
        )
        assert other.status_code == 404
    finally:
        async with SessionLocal() as session:
            if user_id:
                await session.execute(delete(User).where(User.id == user_id))
            if branch_id:
                await session.execute(
                    delete(__import__("app.models", fromlist=["Branch"]).Branch).where(
                        __import__("app.models", fromlist=["Branch"]).Branch.id == branch_id
                    )
                )
            await session.commit()
        await _cleanup([drug_id], invoice_ids)