"""S3.1 report framework (ticket #23): the durable print queue.

`POST /api/v1/reports/{code}/print-queue` enqueues a branch-scoped job
(report code + params snapshot + paper); `GET /api/v1/reports/print-queue`
lists the caller's branch queue (newest first); `POST
.../print-queue/{id}/done` flips queued→done with a timestamp atomically
(a second done — or a concurrent one — is a 409). Jobs survive restarts so
an offline desktop can drain them later — the ModPrint job side of the
legacy print engine.
"""
from datetime import date

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models import PrintJob, User

BRANCH_ID = 1


async def _login_token(client) -> str:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _cleanup_job(job_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(PrintJob).where(PrintJob.id == job_id))
        await session.commit()


async def test_enqueue_list_and_mark_done(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today().isoformat()

    enq = await client.post(
        "/api/v1/reports/day_profit/print-queue",
        headers=headers,
        json={"params": {"datee": today}, "paper": "A5"},
    )
    assert enq.status_code == 201, enq.text
    job = enq.json()
    assert job["report_code"] == "day_profit"
    assert job["status"] == "queued"
    assert job["paper"] == "A5"
    assert job["params"]["datee"] == today
    try:
        listing = await client.get("/api/v1/reports/print-queue", headers=headers)
        assert listing.status_code == 200
        rows = [j for j in listing.json()["jobs"] if j["id"] == job["id"]]
        assert rows and rows[0]["status"] == "queued"

        done = await client.post(
            f"/api/v1/reports/print-queue/{job['id']}/done", headers=headers
        )
        assert done.status_code == 200
        assert done.json()["status"] == "done"
        assert done.json()["done_at"]

        again = await client.post(
            f"/api/v1/reports/print-queue/{job['id']}/done", headers=headers
        )
        assert again.status_code == 409
    finally:
        await _cleanup_job(job["id"])


async def test_enqueue_unknown_or_inactive_code_is_404(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    missing = await client.post(
        "/api/v1/reports/nope/print-queue", headers=headers, json={}
    )
    assert missing.status_code == 404


async def test_enqueue_rejects_bad_paper_and_bad_params(client):
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    bad_paper = await client.post(
        "/api/v1/reports/day_profit/print-queue",
        headers=headers,
        json={"params": {}, "paper": "Letter"},
    )
    assert bad_paper.status_code == 400
    bad_date = await client.post(
        "/api/v1/reports/day_profit/print-queue",
        headers=headers,
        json={"params": {"datee": "not-a-date"}},
    )
    assert bad_date.status_code == 400


async def test_queue_is_branch_scoped(client):
    """Another branch's job is invisible in the list and not markable."""
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    other_branch_job = None
    async with SessionLocal() as session:
        from sqlalchemy import text

        row = await session.execute(
            text(
                "INSERT INTO branches (pharmacyid, mobile, pharname) "
                "VALUES ('__t2_rep_b2__', '000', 'فرع تجريبي') RETURNING id"
            )
        )
        branch2_id = row.scalar_one()
        user = User(
            username="__t2_rep_qb__",
            pass_hash="x",
            permission_level=9,
            branch_id=branch2_id,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        job = PrintJob(
            branch_id=branch2_id,
            user_id=user_id,
            report_code="day_profit",
            params={},
            paper="A4",
        )
        session.add(job)
        await session.flush()
        other_branch_job = job.id
        await session.commit()

    try:
        listing = await client.get("/api/v1/reports/print-queue", headers=headers)
        ids = [j["id"] for j in listing.json()["jobs"]]
        assert other_branch_job not in ids

        cross = await client.post(
            f"/api/v1/reports/print-queue/{other_branch_job}/done", headers=headers
        )
        assert cross.status_code == 404
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(PrintJob).where(PrintJob.id == other_branch_job)
            )
            await session.execute(delete(User).where(User.id == user_id))
            await session.execute(
                text("DELETE FROM branches WHERE id = :b"), {"b": branch2_id}
            )
            await session.commit()


async def test_queue_requires_reports_permission(client):
    username = "__t2_rep_noperm2__"
    user_id = None
    try:
        async with SessionLocal() as session:
            user = User(
                username=username,
                pass_hash="x",
                permission_level=3,
                branch_id=BRANCH_ID,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            await session.commit()
        from app.auth.security import create_access_token

        token = create_access_token(
            str(user_id), branch_id=BRANCH_ID, roles=[], permission_level=3
        )
        r = await client.get(
            "/api/v1/reports/print-queue",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
    finally:
        if user_id:
            async with SessionLocal() as session:
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()


async def test_enqueue_rejects_unknown_params(client):
    """A param outside the catalog row's list is rejected (snapshot integrity)."""
    token = await _login_token(client)
    r = await client.post(
        "/api/v1/reports/day_profit/print-queue",
        headers={"Authorization": f"Bearer {token}"},
        json={"params": {"bogus": "1"}},
    )
    assert r.status_code == 400


async def test_queue_requires_authentication(client):
    r = await client.get("/api/v1/reports/print-queue")
    assert r.status_code == 401


async def test_enqueue_catalog_row_without_engine_is_404(client):
    """An active catalog row with no registry engine can't be queued."""
    token = await _login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    async with SessionLocal() as session:
        await session.execute(
            text(
                "INSERT INTO report_catalog (code, category, title_ar, title_en, "
                "params, paper, sort) VALUES ('__t2_rep_noengine__', 'money', "
                "'بلا محرك', 'No Engine', '[]'::jsonb, 'A4', 99)"
            )
        )
        await session.commit()
    try:
        r = await client.post(
            "/api/v1/reports/__t2_rep_noengine__/print-queue",
            headers=headers,
            json={},
        )
        assert r.status_code == 404
    finally:
        async with SessionLocal() as session:
            await session.execute(
                text("DELETE FROM report_catalog WHERE code = '__t2_rep_noengine__'")
            )
            await session.commit()
