"""SQLite numbering fallback for offline desktop draft creation (#55).

`pg_advisory_xact_lock` has no SQLite equivalent: on the desktop twin
`acquire_branch_lock` skips the advisory call and monotonic numbering leans
on UNIQUE(source_branch_id, transfer_no) with a bounded savepoint retry in
create_draft (on IntegrityError: rollback to savepoint, recompute MAX+1,
retry — up to 3 attempts).

The repo has no async SQLite harness (the models carry PG-only types), so the
fallback paths are exercised here on the PG suite via a monkeypatched dialect
flag; the SQL executed in the sqlite path (SELECT MAX / INSERT) is plain ANSI
and dialect-neutral. The PG path is covered by the whole transfers suite.
"""
from datetime import datetime, timezone

import pytest

from app.core.db import SessionLocal
from app.models import Transfer
from app.transfers import service as tsvc

from tests import transfers_test_utils as u


@pytest.fixture
async def world(client):
    src = await u._make_branch()
    tgt = await u._make_branch()
    src_name, tgt_name = u._uniq("src"), u._uniq("tgt")
    src_user = await u._make_user(src_name, level=3, branch_id=src)
    tgt_user = await u._make_user(tgt_name, level=3, branch_id=tgt)
    drug = await u._make_drug_with_stock(branch_id=src, stock_qty="10")
    return {
        "client": client,
        "src": src,
        "tgt": tgt,
        "src_token": await u._login_token(client, src_name),
        "drug": drug,
        "_user_ids": [src_user, tgt_user],
        "_branch_ids": [src, tgt],
        "_drug_ids": [drug],
        "_transfer_ids": [],
    }


@pytest.fixture(autouse=True)
async def _cleanup(world):
    yield
    await u._cleanup(
        transfer_ids=world["_transfer_ids"],
        drug_ids=world["_drug_ids"],
        branch_ids=world["_branch_ids"],
        user_ids=world["_user_ids"],
    )


async def _draft(world) -> dict:
    r = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
        },
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    world["_transfer_ids"].append(body["id"])
    return body


async def test_sqlite_flag_skips_advisory_and_numbers_normally(world, monkeypatch):
    monkeypatch.setattr(tsvc, "_is_sqlite", lambda session: True)
    body = await _draft(world)
    assert body["transfer_no"] == "1"


async def test_sqlite_retry_recovers_from_numbering_collision(world, monkeypatch):
    # an existing transfer already holds no "1" for this source branch...
    async with SessionLocal() as s:
        seeded = Transfer(
            source_branch_id=world["src"],
            target_branch_id=world["tgt"],
            transfer_no="1",
            status="cancelled",
            created_at=datetime.now(timezone.utc),
        )
        s.add(seeded)
        await s.flush()
        world["_transfer_ids"].append(seeded.id)
        await s.commit()

    real_next = tsvc.next_transfer_no
    calls = {"n": 0}

    async def flaky_next(session, source_branch_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return "1"  # stale numbering → IntegrityError on the unique key
        return await real_next(session, source_branch_id)

    monkeypatch.setattr(tsvc, "_is_sqlite", lambda session: True)
    monkeypatch.setattr(tsvc, "next_transfer_no", flaky_next)

    body = await _draft(world)
    assert calls["n"] >= 2  # the collision happened and was retried
    assert body["transfer_no"] == "2"
