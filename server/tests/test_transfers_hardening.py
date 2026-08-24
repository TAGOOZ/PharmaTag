"""Inter-pharmacy transfers (#32) — review hardening.

Regression tests for the review findings: same-transition double-execution
(header row lock), per-take sign validation, and boundary-typed quantity
fields. Each test names the exact bug it pins.
"""
import asyncio

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
        branch_id=src,
        # deliberately generous: enough stock that a DOUBLE dispatch would
        # succeed numerically — only the state machine may stop it
        stock_qty="100",
        batches=[("100", "5", "2027-01-01")],
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


async def _draft(world, qty="10"):
    r = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": qty}],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    world["_transfer_ids"].append(body["id"])
    return body


async def test_concurrent_dispatch_of_same_transfer_executes_once(world):
    """Two racing dispatches of ONE draft: exactly one wins (200), the other
    409s — the header row lock serializes the status transition so the source
    can never be decremented twice for one transfer."""
    client = world["client"]
    draft = await _draft(world)

    async def go():
        return await client.post(
            f"/api/v1/transfers/{draft['id']}/dispatch",
            headers=u._headers(world["src_token"]),
            json={},
        )

    results = await asyncio.gather(go(), go())
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409]
    # one decrement only
    batches = await u._batches(world["src"], world["drug"])
    assert float(batches[0].qty) == 90


async def test_concurrent_receive_of_same_transfer_executes_once(world):
    client = world["client"]
    draft = await _draft(world)
    line_id = draft["lines"][0]["id"]
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    assert r.status_code == 200

    async def go():
        return await client.post(
            f"/api/v1/transfers/{draft['id']}/receive",
            headers=u._headers(world["tgt_token"]),
            json={"lines": [{"line_id": line_id, "received_qty": "10"}]},
        )

    results = await asyncio.gather(go(), go())
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409], [r.text for r in results]
    # the lot landed ONCE — not doubled
    tgt_batches = await u._batches(world["tgt"], world["drug"])
    assert sum(float(b.qty) for b in tgt_batches) == 10


async def test_negative_take_mints_no_phantom_units(world):
    """[(real_lot, +20), (empty_lot, -10)] sums to sent_qty but would credit
    an empty batch with phantom units — per-take sign must be validated."""
    client = world["client"]
    drug2 = await u._make_drug_with_stock(
        branch_id=world["src"],
        stock_qty="20",
        batches=[("20", "5", "2027-01-01"), ("0", "9", "2027-02-01")],
    )
    world["_drug_ids"].append(drug2)
    # FEFO order: the real lot (2027-01) sorts before the empty one (2027-02)
    real_lot, empty_lot = await u._batches(world["src"], drug2)

    draft = (
        await client.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={
                "target_branch_id": world["tgt"],
                "lines": [{"drug_id": drug2, "qty": "10"}],
            },
        )
    ).json()
    world["_transfer_ids"].append(draft["id"])

    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {
                    "line_id": draft["lines"][0]["id"],
                    "allocations": [
                        {"batch_id": real_lot.id, "qty": "20"},
                        {"batch_id": empty_lot.id, "qty": "-10"},
                    ],
                }
            ]
        },
    )
    assert r.status_code == 400, "negative take must be rejected"
    transfer, lines = await u._transfer(draft["id"])
    assert transfer.status == "draft"  # nothing applied


async def test_non_numeric_qty_is_rejected_not_500(world):
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "NaN"}],
        },
    )
    assert r.status_code < 500
    r2 = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "abc"}],
        },
    )
    assert r2.status_code < 500


async def test_unknown_line_id_at_dispatch_is_400_not_silent_fefo(world):
    client = world["client"]
    draft = await _draft(world)
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {"line_id": draft["lines"][0]["id"] + 999999, "allocations": []}
            ]
        },
    )
    assert r.status_code == 400
