"""Inter-pharmacy transfers (#32) — numbering + reads.

Per-source-branch monotonic transfer_no (G07: advisory lock, UNIQUE backstop),
branch-scoped reads, and the legacy_fatid ETL passthrough.
"""
import pytest

from tests import transfers_test_utils as u


@pytest.fixture
async def world(client):
    src = await u._make_branch()
    tgt = await u._make_branch()
    src_name = u._uniq("src")
    tgt_name = u._uniq("tgt")
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


async def _draft(client, world, *, fatid=None):
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
            **({"legacy_fatid": fatid} if fatid is not None else {}),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    world["_transfer_ids"].append(body["id"])
    return body


async def test_transfer_numbers_monotonic_per_source_branch(world):
    client, headers = world["client"], u._headers(world["src_token"])
    first = await _draft(client, world)
    second = await _draft(client, world)
    assert first["transfer_no"] == "1"
    assert second["transfer_no"] == "2"


async def test_legacy_fatid_passthrough_round_trips(world):
    client = world["client"]
    body = await _draft(client, world, fatid="F-8842")
    assert body["legacy_fatid"] == "F-8842"
    r = await client.get(
        f"/api/v1/transfers/{body['id']}", headers=u._headers(world["tgt_token"])
    )
    assert r.status_code == 200
    assert r.json()["legacy_fatid"] == "F-8842"


async def test_reads_scoped_to_participating_branches(world):
    client = world["client"]
    body = await _draft(client, world)

    # both parties see it
    for token in (world["src_token"], world["tgt_token"]):
        r = await client.get("/api/v1/transfers", headers=u._headers(token))
        assert [t["id"] for t in r.json()["transfers"]] == [body["id"]]

    # a foreign branch sees neither the list entry nor the detail
    outsider = await u._make_branch()
    world["_branch_ids"].append(outsider)
    out_name = u._uniq("out")
    user_id = await u._make_user(out_name, level=3, branch_id=outsider)
    world["_user_ids"].append(user_id)
    token = await u._login_token(client, out_name)

    r = await client.get("/api/v1/transfers", headers=u._headers(token))
    assert r.json()["transfers"] == []
    r = await client.get(
        f"/api/v1/transfers/{body['id']}", headers=u._headers(token)
    )
    assert r.status_code == 404
