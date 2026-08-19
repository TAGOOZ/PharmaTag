"""S1.9 reports edge cases (ticket #15): branch scoping.

Reports are read-only and branch-scoped to the caller: a user on branch 2 must
never see branch-1 rows, even with the reports permission. The aggregates come
back as the branch's own (empty/zeroed when the branch has no documents).
"""
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import Branch, User

from tests.reports_test_utils import _uniq, _make_drug_and_stock

_seq = [0]


def _token_for(user_id: int, branch_id: int) -> str:
    from app.auth.security import create_access_token

    return create_access_token(
        str(user_id), branch_id=branch_id, roles=[], permission_level=9
    )


async def _make_other_branch_user() -> tuple[int, int]:
    async with SessionLocal() as session:
        branch = Branch(
            pharmacyid=f"b{_seq[0]}", mobile="0", pharname="Other"
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
        return user_id, branch_id


async def test_reports_are_branch_scoped(client):
    """Branch-2 user sees branch-2 (empty) aggregates, not branch-1 rows."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("20.0000", "5.0000", "2026-01-01")],
        minimum="1.0000",  # branch-1 stock qty 20 > minimum: not a shortage
    )
    user_id = None
    branch_id = None
    try:
        # a real branch-1 sale so branch 1 has data
        token = await _login_token(client)
        r = await client.post(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {token}"},
            json={"lines": [{"drug_id": drug_id, "qty": "12"}]},
        )
        assert r.status_code == 201, r.text
        sale_id = r.json()["id"]

        user_id, branch_id = await _make_other_branch_user()
        other = _token_for(user_id, branch_id)

        dp = await client.get(
            "/api/v1/reports/day-profit",
            headers={"Authorization": f"Bearer {other}"},
        )
        assert dp.status_code == 200, dp.text
        body = dp.json()
        assert body["branch_id"] == branch_id
        assert body["sales_count"] == 0  # branch 1's sale is invisible
        assert body["net_revenue"] == "0.00"

        sm = await client.get(
            "/api/v1/reports/stock-minimum",
            headers={"Authorization": f"Bearer {other}"},
        )
        assert sm.status_code == 200, sm.text
        assert sm.json()["items"] == []

        pt = await client.get(
            "/api/v1/reports/period-totals",
            headers={"Authorization": f"Bearer {other}"},
        )
        assert pt.status_code == 200, pt.text
        assert pt.json()["kinds"]["sale"]["count"] == 0
    finally:
        from tests.reports_test_utils import _cleanup

        await _cleanup([drug_id], [sale_id])
        if user_id and branch_id:
            async with SessionLocal() as session:
                await session.execute(delete(User).where(User.id == user_id))
                await session.execute(delete(Branch).where(Branch.id == branch_id))
                await session.commit()


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]