"""legacy_fatid ETL idempotency (#56).

Legacy Titan FAT imports are RE-RUN after failures: re-importing the same
FAT row must converge on ONE transfer, never mint a second one with a fresh
transfer_no (dispatching both would double-move stock). Contract:

* same (source, fatid) → same target  ⇒ replay: return the EXISTING
  transfer (200), still exactly one row — regardless of its status
  (the ETL genuinely imported it; convergence, not an error)
* same (source, fatid) → DIFFERENT target ⇒ 409 (fatid is already claimed)
* different sources may reuse one fatid freely
* NULL fatid rows are exempt from all of this (unlimited drafts)

The per-source advisory lock serializes creates, so even two racing ETL
calls land exactly one row.
"""
import asyncio

import pytest
from sqlalchemy import func, select

from app.models import Transfer
from tests import transfers_test_utils as u


@pytest.fixture
async def world(client):
    src = await u._make_branch()
    tgt = await u._make_branch()
    src_name, tgt_name = u._uniq("src"), u._uniq("tgt")
    src_user = await u._make_user(src_name, level=3, branch_id=src)
    tgt_user = await u._make_user(tgt_name, level=3, branch_id=tgt)
    drug = await u._make_drug_with_stock(
        branch_id=src, stock_qty="100", batches=[("100", "5", "2027-01-01")]
    )
    return {
        "client": client,
        "src": src,
        "tgt": tgt,
        "src_token": await u._login_token(client, src_name),
        "tgt_token": await u._login_token(client, tgt_name),
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


async def _draft(world, *, target=None, fatid: str | None = "F-1"):
    """POST a draft WITHOUT asserting the status code (200 vs 201 is the
    contract under test). Returns (status_code, body)."""
    r = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"] if target is None else target,
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
            **({"legacy_fatid": fatid} if fatid is not None else {}),
        },
    )
    assert r.status_code < 500, r.text
    body = r.json()
    if isinstance(body, dict) and "id" in body:
        if body["id"] not in world["_transfer_ids"]:
            world["_transfer_ids"].append(body["id"])
    return r.status_code, body


async def _count(world) -> int:
    async with u.SessionLocal() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(Transfer)
                .where(Transfer.source_branch_id == world["src"])
            )
        ).scalar_one()


async def test_same_fatid_twice_replays_existing_transfer_once(world):
    """Re-running the same FAT import converges: second call is 200 with the
    SAME transfer id and there is still exactly ONE row."""
    code1, first = await _draft(world, fatid="FAT-8842")
    code2, second = await _draft(world, fatid="FAT-8842")
    assert code1 == 201
    assert code2 == 200
    assert second["id"] == first["id"]
    assert await _count(world) == 1


async def test_replay_after_status_advanced_also_converges(world):
    """The ETL may retry long after dispatch: same source+target+fatid returns
    the existing transfer whatever its state (no new draft, no 409)."""
    code1, first = await _draft(world, fatid="FAT-9000")
    assert code1 == 201
    r = await world["client"].post(
        f"/api/v1/transfers/{first['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    assert r.status_code == 200, r.text

    code2, second = await _draft(world, fatid="FAT-9000")
    assert code2 == 200
    assert second["id"] == first["id"]
    assert second["status"] == "dispatched"
    assert await _count(world) == 1


async def test_same_fatid_different_target_is_conflict_409(world):
    """One fatid is bound to the target it was first imported for; pointing a
    re-run at another target is a data error, not a replay."""
    other_tgt = await u._make_branch()
    world["_branch_ids"].append(other_tgt)
    other_name = u._uniq("tgt2")
    uid = await u._make_user(other_name, level=3, branch_id=other_tgt)
    world["_user_ids"].append(uid)
    await u._login_token(world["client"], other_name)  # sanity: account works

    code1, _ = await _draft(world, fatid="FAT-777")
    code2, body = await _draft(world, target=other_tgt, fatid="FAT-777")
    assert code1 == 201
    assert code2 == 409
    assert "different target" in body["detail"]
    # only the first transfer exists for that fatid
    assert await _count(world) == 1


async def test_different_sources_may_reuse_the_same_fatid(world):
    """Two pharmacies importing their own copies of the same legacy FAT row:
    each gets its own transfer (uniqueness is per SOURCE branch)."""
    src2 = await u._make_branch()
    world["_branch_ids"].append(src2)
    src2_name = u._uniq("src2")
    uid = await u._make_user(src2_name, level=3, branch_id=src2)
    world["_user_ids"].append(uid)
    token2 = await u._login_token(world["client"], src2_name)

    code1, first = await _draft(world, fatid="SHARED-FAT")
    r2 = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(token2),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
            "legacy_fatid": "SHARED-FAT",
        },
    )
    assert r2.status_code == 201, r2.text
    world["_transfer_ids"].append(r2.json()["id"])
    assert code1 == 201
    assert r2.json()["id"] != first["id"]


async def test_null_fatid_drafts_are_unlimited(world):
    """Interactive drafts carry no fatid: every call mints a fresh transfer —
    the unique index must be partial (NULL rows exempt)."""
    codes = set()
    ids = []
    for _ in range(3):
        code, body = await _draft(world, fatid=None)
        codes.add(code)
        ids.append(body["id"])
    assert codes == {201}
    assert len(set(ids)) == 3
    assert await _count(world) == 3


async def test_concurrent_same_fatid_creates_land_exactly_one_row(world):
    """Two racing ETL calls (crashed job retried while the original was still
    in flight): the per-source advisory lock serializes them so the loser
    sees the winner's committed row and replays it — no 500, one row."""
    client = world["client"]

    async def go():
        return await client.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={
                "target_branch_id": world["tgt"],
                "lines": [{"drug_id": world["drug"], "qty": "1"}],
                "legacy_fatid": "RACE-FAT",
            },
        )

    results = await asyncio.gather(go(), go())
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 201], [r.text for r in results]
    bodies = [r.json() for r in results]
    if bodies[0]["id"] not in world["_transfer_ids"]:
        world["_transfer_ids"].append(bodies[0]["id"])
    assert bodies[0]["id"] == bodies[1]["id"]
    assert await _count(world) == 1
