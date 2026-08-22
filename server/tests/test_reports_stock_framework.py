"""S3.3 (#25): the four stock reports through the S3.1 framework seams —
grid shape, exports, print-queue params, branch scoping."""
import io
import zipfile

from sqlalchemy import delete as sqld

from app.core.db import SessionLocal
from app.models import PrintJob
from tests.reports_test_utils import (
    _cleanup,
    _login_token,
    _make_drug_and_stock,
)


async def test_stock_reports_answer_through_grid_and_exports(client):
    """Every new code renders the generic grid and exports real files."""
    drug_id = await _make_drug_and_stock(
        tax_type="14%",
        price="10.0000",
        cost_price="5.0000",
        batches=[("6.0000", "2.0000", "2020-03-01")],
        stock_qty="6.0000",
        minimum="10.0000",
    )
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}
        for code in ("stock_current", "stock_expired", "stock_needs"):
            grid = await client.get(
                f"/api/v1/reports/{code}", params={"format": "grid"}, headers=auth
            )
            assert grid.status_code == 200, grid.text
            body = grid.json()
            assert body["title_ar"], code
            assert body["columns"], code
            assert isinstance(body["rows"], list), code

            xlsx = await client.get(
                f"/api/v1/reports/{code}/export", headers=auth
            )
            assert xlsx.status_code == 200, xlsx.text
            zf = zipfile.ZipFile(io.BytesIO(xlsx.content))
            assert "xl/workbook.xml" in set(zf.namelist()), code

        movements_grid = await client.get(
            "/api/v1/reports/stock_movements",
            params={
                "format": "grid",
                "drug_id": drug_id,
                "date_from": "2020-01-01",
                "date_to": "2020-12-31",
            },
            headers=auth,
        )
        assert movements_grid.status_code == 200, movements_grid.text
    finally:
        await _cleanup([drug_id], [])


async def test_stock_expired_print_queue_accepts_horizon_param(client):
    """The non-date horizon_days param validates as an integer."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/reports/stock_expired/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={"params": {"horizon_days": "60"}},
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["params"]["horizon_days"] == "60"

    bad = await client.post(
        "/api/v1/reports/stock_expired/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={"params": {"horizon_days": "soon"}},
    )
    assert bad.status_code == 400

    async with SessionLocal() as session:
        await session.execute(sqld(PrintJob).where(PrintJob.id == job["id"]))
        await session.commit()


async def test_stock_reports_branch_scoped(client):
    """A branch-2 user's current-stock sheet shows only branch-2 rows."""
    from app.auth.security import create_access_token
    from app.models import Branch, User

    from tests.reports_test_utils import BRANCH_ID, _make_user

    drug_id = await _make_drug_and_stock(stock_qty="9.0000")
    user_id = None
    branch_id = None
    try:
        token = await _login_token(client)

        async with SessionLocal() as session:
            branch = Branch(pharmacyid="stkb", mobile="0", pharname="STKB")
            session.add(branch)
            await session.flush()
            branch_id = branch.id
            user = User(
                username="__t2_stk_b2__",
                pass_hash="x",
                permission_level=9,
                branch_id=branch_id,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        other_token = create_access_token(
            str(user_id), branch_id=branch_id, roles=[], permission_level=9
        )
        rep = await client.get(
            "/api/v1/reports/stock_current",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["branch_id"] == branch_id
        assert all(i["drug_id"] != drug_id for i in body["items"])
    finally:
        if user_id is not None:
            async with SessionLocal() as session:
                await session.execute(sqld(User).where(User.id == user_id))
                await session.execute(sqld(Branch).where(Branch.id == branch_id))
                await session.commit()
        await _cleanup([drug_id], [])


async def test_stock_current_and_needs_truncation_flags(client):
    """Over the 1000-row cap: truncated=true, count is the true total
    (baseline-relative — this DB is shared with other suites)."""
    from decimal import Decimal

    from sqlalchemy import func as sa_func, select as sa_sel

    from app.models import BranchStock, Drug
    from tests.reports_test_utils import BRANCH_ID, _uniq

    created_ids: list[int] = []
    async with SessionLocal() as session:
        baseline = (
            await session.execute(
                sa_sel(sa_func.count())
                .select_from(BranchStock)
                .where(BranchStock.branch_id == BRANCH_ID)
            )
        ).scalar_one()
        drugs = [
            Drug(
                drugname=_uniq(f"bulk{i}"),
                tax_type="exempt",
                price=Decimal("1.0000"),
                price_cost=Decimal("3.0000"),
            )
            for i in range(1001)
        ]
        session.add_all(drugs)
        await session.flush()
        created_ids = [d.id for d in drugs]
        session.add_all(
            BranchStock(
                branch_id=BRANCH_ID,
                drug_id=d.id,
                # first drug below minimum → needs list has exactly 1 row
                qty=Decimal("0.0000") if i == 0 else Decimal("9.0000"),
                minimum=Decimal("5.0000"),
            )
            for i, d in enumerate(drugs)
        )
        await session.commit()
    try:
        token = await _login_token(client)
        auth = {"Authorization": f"Bearer {token}"}

        cur = await client.get("/api/v1/reports/stock_current", headers=auth)
        assert cur.status_code == 200, cur.text
        body = cur.json()
        assert body["truncated"] is True
        assert body["count"] == baseline + 1001
        assert len(body["items"]) == 1000

        needs = await client.get("/api/v1/reports/stock_needs", headers=auth)
        assert needs.status_code == 200, needs.text
        nbody = needs.json()
        assert nbody["truncated"] is False
        assert nbody["count"] == 1
        assert nbody["items"][0]["suggested_order"] == "5.0000"
        # never-purchased drug falls back to the drug-master cost (3.0000)
        assert nbody["items"][0]["last_cost"] == "3.0000"
    finally:
        async with SessionLocal() as session:
            await session.execute(
                sqld(BranchStock).where(BranchStock.drug_id.in_(created_ids))
            )
            await session.execute(sqld(Drug).where(Drug.id.in_(created_ids)))
            await session.commit()


async def test_stock_reports_require_reports_permission(client):
    """The generic dispatcher enforces the same reports gate per code."""
    from sqlalchemy import delete as sqld, select as sa_sel

    from app.auth.security import create_access_token
    from app.core.db import SessionLocal
    from app.models import User

    username = "__t2_stk_noperm__"
    async with SessionLocal() as session:
        session.add(
            User(
                username=username,
                pass_hash="x",
                permission_level=3,
                branch_id=1,
            )
        )
        await session.commit()
        user = (
            await session.execute(sa_sel(User).where(User.username == username))
        ).scalar_one()
        user_id = user.id
        token = create_access_token(
            str(user_id), branch_id=1, roles=[], permission_level=3
        )
    try:
        for url in ("/api/v1/reports/stock_current", "/api/v1/reports/stock_needs"):
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 403, url
    finally:
        async with SessionLocal() as session:
            await session.execute(sqld(User).where(User.id == user_id))
            await session.commit()


async def test_stock_movements_print_queue_accepts_drug_id(client):
    """Regression (review): the catalog row must declare drug_id so a queued
    job can actually render; enqueue-time bounds match render-time bounds."""
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/v1/reports/stock_movements/print-queue",
        headers=auth,
        json={"params": {"drug_id": "42"}},
    )
    assert r.status_code == 201, r.text
    job = r.json()

    # horizon_days must be rejected at ENQUEUE when out of the render bounds
    bad = await client.post(
        "/api/v1/reports/stock_expired/print-queue",
        headers=auth,
        json={"params": {"horizon_days": "5000"}},
    )
    assert bad.status_code == 400

    async with SessionLocal() as session:
        await session.execute(sqld(PrintJob).where(PrintJob.id == job["id"]))
        await session.commit()


async def test_stock_movements_queue_rejects_missing_drug_id(client):
    """Regression (review r2): a job missing its required param never queues."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/reports/stock_movements/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={"params": {}},
    )
    assert r.status_code == 400
    assert "drug_id" in r.text


async def test_stock_expired_truncation_flags_and_sql_total(client):
    """Expired report follows the house cap convention: truncated=true,
    true count, SQL-side total — over 1001 expired batches."""
    from datetime import timedelta
    from decimal import Decimal

    from sqlalchemy import select as sa_sel

    from app.core.time import business_date
    from app.models import Drug, StockBatch
    from tests.reports_test_utils import BRANCH_ID

    created_ids: list[int] = []
    async with SessionLocal() as session:
        drug = Drug(drugname="__t2_stk_exp_bulk__", tax_type="exempt",
                    price=Decimal("1.0000"), price_cost=Decimal("0.5000"))
        session.add(drug)
        await session.flush()
        created_ids.append(drug.id)
        past = business_date() - timedelta(days=365)
        session.add_all(
            StockBatch(
                branch_id=BRANCH_ID,
                drug_id=drug.id,
                randomid=f"__t2_expb_{i}__",
                qty=Decimal("1.0000"),
                cost=Decimal("2.0000"),
                expire=past,
            )
            for i in range(1001)
        )
        await session.commit()
    try:
        token = await _login_token(client)
        rep = await client.get(
            "/api/v1/reports/stock_expired",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rep.status_code == 200, rep.text
        body = rep.json()
        assert body["truncated"] is True
        assert body["count"] == 1001
        assert len(body["items"]) == 1000
        assert body["total_value"] == "2002.00"
    finally:
        async with SessionLocal() as session:
            batch_ids = (
                await session.execute(
                    sa_sel(StockBatch.id).where(StockBatch.drug_id.in_(created_ids))
                )
            ).scalars().all()
            if batch_ids:
                await session.execute(
                    sqld(StockBatch).where(StockBatch.id.in_(batch_ids))
                )
            await session.execute(sqld(Drug).where(Drug.id.in_(created_ids)))
            await session.commit()


async def test_movements_expired_needs_branch_scoped(client):
    """Regression (review r2 #7): all four stock codes scope to the caller's
    branch — a branch-2 user gets empty results for branch-1 data, and a
    foreign drug_id yields an empty track rather than another branch's rows."""
    from app.auth.security import create_access_token
    from app.models import Branch, User

    from tests.reports_test_utils import _uniq

    drug_id = await _make_drug_and_stock(
        stock_qty="8.0000",
        minimum="2.0000",
        batches=[("1.0000", "1.0000", "2020-01-01")],
    )
    user_id = None
    branch_id = None
    try:
        token = await _login_token(client)
        async with SessionLocal() as session:
            # branches.pharmacyid is varchar(15) — keep the tag short but
            # process-unique
            tag = _uniq("bsc")[:15]
            branch = Branch(pharmacyid=tag, mobile="0", pharname="BS")
            session.add(branch)
            await session.flush()
            branch_id = branch.id
            user = User(
                username=_uniq("bsu"),
                pass_hash="x",
                permission_level=9,
                branch_id=branch_id,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()

        other = create_access_token(
            str(user_id), branch_id=branch_id, roles=[], permission_level=9
        )
        auth = {"Authorization": f"Bearer {other}"}

        cur = await client.get("/api/v1/reports/stock_current", headers=auth)
        assert cur.status_code == 200
        assert cur.json()["items"] == []

        needs = await client.get("/api/v1/reports/stock_needs", headers=auth)
        assert needs.status_code == 200
        assert needs.json()["count"] == 0

        exp = await client.get("/api/v1/reports/stock_expired", headers=auth)
        assert exp.status_code == 200
        assert exp.json()["count"] == 0

        mv = await client.get(
            "/api/v1/reports/stock_movements",
            params={"drug_id": drug_id},  # exists globally, belongs to branch 1
            headers=auth,
        )
        assert mv.status_code == 200, mv.text
        assert mv.json()["days"] == []
        assert mv.json()["current_qty"] == "0.0000"
    finally:
        if user_id is not None:
            async with SessionLocal() as session:
                await session.execute(sqld(User).where(User.id == user_id))
                await session.execute(sqld(Branch).where(Branch.id == branch_id))
                await session.commit()
        await _cleanup([drug_id], [])
