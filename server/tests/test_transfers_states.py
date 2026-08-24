"""Inter-pharmacy transfers (#32) — state machine + transition authority (T2/T7).

`draft → dispatched → received`; `cancelled` only from draft. Dispatch is the
SOURCE branch's call, receive the TARGET's (self-receive impossible —
source == target is rejected at creation); a draft may be cancelled by either
party. Writes ride `transfers.manage` (legacy floor 3).
"""
import pytest

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


async def _draft(client, world, *, status_code=201):
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "4"}],
        },
    )
    assert r.status_code == status_code, r.text
    if status_code == 201:
        body = r.json()
        world["_transfer_ids"].append(body["id"])
        return body
    return r


async def _dispatch(client, world, transfer_id, token=None, *, status_code=200):
    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/dispatch",
        headers=u._headers(token or world["src_token"]),
        json={},
    )
    if status_code:
        assert r.status_code == status_code, r.text
    return r


async def _receive(client, world, transfer_id, qty="4", token=None, *, status_code=200):
    lines = (await u._transfer(transfer_id))[1]
    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        headers=u._headers(token or world["tgt_token"]),
        json={"lines": [{"line_id": lines[0].id, "received_qty": qty}]},
    )
    if status_code:
        assert r.status_code == status_code, r.text
    return r


async def test_wrong_branch_cannot_dispatch_or_receive(world):
    client = world["client"]
    draft = await _draft(client, world)

    # the TARGET cannot dispatch its own inbound delivery
    r = await _dispatch(client, world, draft["id"], world["tgt_token"], status_code=403)
    assert r.json()["detail"] == "caller is not a party to this transfer"
    # and the SOURCE cannot self-receive what it sent
    await _dispatch(client, world, draft["id"])
    await _receive(client, world, draft["id"], token=world["src_token"], status_code=403)


async def test_state_machine_rejects_illegal_transitions(world):
    client = world["client"]
    draft = await _draft(client, world)

    # receive before dispatch is meaningless
    await _receive(client, world, draft["id"], status_code=409)
    await _dispatch(client, world, draft["id"])
    # double-dispatch
    await _dispatch(client, world, draft["id"], status_code=409)
    # a dispatched transfer can no longer be cancelled
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/cancel",
        headers=u._headers(world["tgt_token"]),
    )
    assert r.status_code == 409
    await _receive(client, world, draft["id"])
    # terminal: no further transitions
    await _dispatch(client, world, draft["id"], status_code=409)
    await _receive(client, world, draft["id"], status_code=409)


async def test_cancel_draft_by_either_party_moves_nothing(world):
    client = world["client"]

    # target cancels an unwanted draft...
    draft = await _draft(client, world)
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/cancel",
        headers=u._headers(world["tgt_token"]),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    assert await u._stock_qty(world["src"], world["drug"]) == 10

    # ...and source cancels another one
    other = await _draft(client, world)
    r = await client.post(
        f"/api/v1/transfers/{other['id']}/cancel",
        headers=u._headers(world["src_token"]),
    )
    assert r.status_code == 200, r.text


async def test_source_and_target_must_differ(world):
    """A branch transferring to itself would mint free stock — rejected."""
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["src"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
        },
    )
    assert r.status_code == 400


async def test_cashier_below_stock_floor_is_walled(world):
    client = world["client"]
    outsider = await u._make_branch()
    world["_branch_ids"].append(outsider)
    name = u._uniq("cashier")
    user_id = await u._make_user(name, level=2, branch_id=outsider)  # below floor 3
    world["_user_ids"].append(user_id)
    token = await u._login_token(client, name)

    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(token),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
        },
    )
    assert r.status_code == 403
