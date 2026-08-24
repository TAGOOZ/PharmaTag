"""Inter-pharmacy transfers (ticket #32, S5.2) — the delivery flow.

A drafted transfer moves stock from the source branch to the target branch
through the locked state machine draft → dispatched → received: dispatch
decrements source stock, receive creates target stock at the sent lots'
cost/expiry. Every test drives the public API as two branch-pinned users.
"""
import pytest

from tests import transfers_test_utils as u


@pytest.fixture
async def world(client):
    """Source branch (with a level-3 dispatcher user) + target branch
    (with a level-3 receiver user) + one stocked drug on the source."""
    src = await u._make_branch()
    tgt = await u._make_branch()
    src_name, tgt_name = u._uniq("src"), u._uniq("tgt")
    src_user = await u._make_user(src_name, level=3, branch_id=src)
    tgt_user = await u._make_user(tgt_name, level=3, branch_id=tgt)
    drug = await u._make_drug_with_stock(
        branch_id=src,
        stock_qty="10",
        batches=[("10", "5", "2027-01-01")],
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


async def test_draft_dispatch_receive_moves_stock_between_branches(world):
    client = world["client"]
    drug = world["drug"]

    # the source branch's user drafts an outbound transfer of 4 units
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": drug, "qty": "4"}]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    transfer_id = body["id"]
    world["_transfer_ids"].append(transfer_id)
    assert body["status"] == "draft"
    assert body["source_branch_id"] == world["src"]
    assert body["target_branch_id"] == world["tgt"]
    assert body["lines"][0]["sent_qty"] == "4.0000"

    # drafting alone moves nothing
    assert await u._stock_qty(world["src"], drug) == 10

    # the source dispatches: stock leaves the source branch
    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "dispatched"
    assert await u._stock_qty(world["src"], drug) == 6

    # the target receives in full: stock arrives on the target branch
    lines = (await u._transfer(transfer_id))[1]
    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        headers=u._headers(world["tgt_token"]),
        json={
            "lines": [{"line_id": lines[0].id, "received_qty": "4"}]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"
    assert await u._stock_qty(world["tgt"], drug) == 4
    assert await u._stock_qty(world["src"], drug) == 6


@pytest.fixture(autouse=True)
async def _cleanup(world):
    yield
    await u._cleanup(
        transfer_ids=world["_transfer_ids"],
        drug_ids=world["_drug_ids"],
        branch_ids=world["_branch_ids"],
        user_ids=world["_user_ids"],
    )
