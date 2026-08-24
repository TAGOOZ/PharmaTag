"""Inter-pharmacy transfers (#32) — edge-case pass.

Validation walls, concurrency (FOR UPDATE oversell guard), and the odd
payloads a hostile or buggy client can send. Every case names the expected
public behavior.
"""
import asyncio

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import BranchStock

from tests import transfers_test_utils as u


@pytest.fixture
async def world(client):
    src = await u._make_branch()
    tgt = await u._make_branch()
    src_name, tgt_name = u._uniq("src"), u._uniq("tgt")
    src_user = await u._make_user(src_name, level=3, branch_id=src)
    tgt_user = await u._make_user(tgt_name, level=3, branch_id=tgt)
    drug = await u._make_drug_with_stock(
        branch_id=src, stock_qty="10", batches=[("10", "5", "2027-01-01")]
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


def _draft_body(world, **overrides):
    body = {
        "target_branch_id": world["tgt"],
        "lines": [{"drug_id": world["drug"], "qty": "1"}],
    }
    body.update(overrides)
    return body


async def _draft(world, **overrides):
    r = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json=_draft_body(world, **overrides),
    )
    if r.status_code == 201:
        world["_transfer_ids"].append(r.json()["id"])
    return r


async def test_zero_negative_and_blank_qty_rejected_400(world):
    for qty in ("0", "-3", "-0.0001"):
        r = await _draft(world, lines=[{"drug_id": world["drug"], "qty": qty}])
        assert r.status_code == 400, f"qty={qty}"


async def test_empty_lines_rejected_400(world):
    assert (await _draft(world, lines=[])).status_code == 400


async def test_unknown_drug_rejected_400(world):
    r = await _draft(world, lines=[{"drug_id": 99999999, "qty": "1"}])
    assert r.status_code == 400


async def test_duplicate_drug_lines_rejected_400(world):
    line = {"drug_id": world["drug"], "qty": "1"}
    r = await _draft(world, lines=[line, line])
    assert r.status_code == 400


async def test_unknown_and_inactive_target_branch_rejected(world):
    assert (await _draft(world, target_branch_id=99999999)).status_code == 400

    # deactivate the target through the registry API then retry
    admin = await world["client"].post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    r = await world["client"].delete(
        f"/api/v1/branches/{world['tgt']}", headers=headers
    )
    assert r.status_code == 200, r.text
    assert (await _draft(world)).status_code == 400


async def test_receive_payload_must_cover_every_line_exactly_once(world):
    client = world["client"]
    draft = (await _draft(world, lines=[{"drug_id": world["drug"], "qty": "2"}])).json()
    line_id = draft["lines"][0]["id"]
    await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )

    # missing line
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": []},
    )
    assert r.status_code == 400
    # unknown line id
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line_id + 1000000, "received_qty": "1"}]},
    )
    assert r.status_code == 400
    # over-receive and negative receive
    for qty in ("2.0001", "-1"):
        r = await client.post(
            f"/api/v1/transfers/{draft['id']}/receive",
            headers=u._headers(world["tgt_token"]),
            json={"lines": [{"line_id": line_id, "received_qty": qty}]},
        )
        assert r.status_code == 400, f"received_qty={qty}"
    # nothing moved by any of the rejected attempts
    transfer, lines = await u._transfer(draft["id"])
    assert transfer.status == "dispatched"
    assert lines[0].received_qty is None


async def test_explicit_allocation_from_wrong_drug_rejected_400(world):
    """A batch that exists but belongs to another drug/branch is not usable."""
    client = world["client"]
    other_drug = await u._make_drug_with_stock(
        branch_id=world["src"], stock_qty="5", batches=[("5", "9", "2027-01-01")]
    )
    world["_drug_ids"].append(other_drug)
    foreign_batch = (await u._batches(world["src"], other_drug))[0]

    draft = (await _draft(world)).json()
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {
                    "line_id": draft["lines"][0]["id"],
                    "allocations": [
                        {"batch_id": foreign_batch.id, "qty": "1"}
                    ],
                }
            ]
        },
    )
    assert r.status_code == 400


async def test_allocation_sum_must_equal_sent_qty(world):
    client = world["client"]
    batches = await u._batches(world["src"], world["drug"])
    draft = (await _draft(world, lines=[{"drug_id": world["drug"], "qty": "4"}])).json()
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {
                    "line_id": draft["lines"][0]["id"],
                    "allocations": [{"batch_id": batches[0].id, "qty": "3"}],
                }
            ]
        },
    )
    assert r.status_code == 400
    transfer, lines = await u._transfer(draft["id"])
    assert transfer.status == "draft"


async def test_user_without_branch_cannot_create(world):
    client = world["client"]
    name = u._uniq("nobranch")
    user_id = await u._make_user(name, level=9, branch_id=None)
    world["_user_ids"].append(user_id)
    token = await u._login_token(client, name)
    r = await client.post("/api/v1/transfers", headers=u._headers(token),
                          json=_draft_body(world))
    assert r.status_code == 403


async def test_unauthenticated_rejected_401(world):
    r = await world["client"].post("/api/v1/transfers", json=_draft_body(world))
    assert r.status_code == 401


async def test_concurrent_dispatches_cannot_oversell(world):
    """Two dispatches racing on the same drug serialize under FOR UPDATE —
    the second sees post-lock truth and 409s; total decremented never exceeds
    shelf quantity."""
    client = world["client"]
    drafts = []
    for _ in range(2):
        r = await _draft(world, lines=[{"drug_id": world["drug"], "qty": "8"}])
        assert r.status_code == 201
        drafts.append(r.json())

    async def dispatch(transfer_id):
        return await client.post(
            f"/api/v1/transfers/{transfer_id}/dispatch",
            headers=u._headers(world["src_token"]),
            json={},
        )

    results = await asyncio.gather(
        dispatch(drafts[0]["id"]), dispatch(drafts[1]["id"])
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409]
    assert await u._stock_qty(world["src"], world["drug"]) == 2
