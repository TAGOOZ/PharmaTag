"""MEDIUM + LOW gaps from edge-case audit: vat/price/expire preservation,
validation boundaries, RB walls, receive duplicate line_id, shortfall spanning
lots, G12 payload, concurrency, and assorted LOW checks."""
import pytest
from sqlalchemy import func, select
from sqlalchemy import delete as sql_delete

from app.core.db import SessionLocal
from app.models import AuditLog, Branch, BranchStock, Journal, StockBatch, SyncLog, Transfer, TransferLine

from tests import transfers_test_utils as u


@pytest.fixture
async def world(client):
    src = await u._make_branch()
    tgt = await u._make_branch()
    src_name, tgt_name = u._uniq("src"), u._uniq("tgt")
    src_user = await u._make_user(src_name, level=3, branch_id=src)
    tgt_user = await u._make_user(tgt_name, level=3, branch_id=tgt)
    drug_a = await u._make_drug_with_stock(
        branch_id=src, stock_qty="20", batches=[("10", "5", "2027-01-01"), ("10", "7", "2027-06-01")]
    )
    drug_b = await u._make_drug_with_stock(
        branch_id=src, stock_qty="15", batches=[("15", "9", "2027-03-01")]
    )
    return {
        "client": client,
        "src": src,
        "tgt": tgt,
        "src_token": await u._login_token(client, src_name),
        "tgt_token": await u._login_token(client, tgt_name),
        "drug_a": drug_a,
        "drug_b": drug_b,
        "_user_ids": [src_user, tgt_user],
        "_branch_ids": [src, tgt],
        "_drug_ids": [drug_a, drug_b],
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


# ---------- ST-3 vat/price/expire=None ----------

async def test_vat_price_expire_preserved_on_receive(world):
    """5% vat + custom price + NULL expire is carried verbatim to transfer_in."""
    client = world["client"]
    # add a batch with vat/price and NULL expire on src
    async with SessionLocal() as s:
        s.add(StockBatch(branch_id=world["src"], drug_id=world["drug_a"], randomid=u._uniq("b"), qty=5, cost=12, vat=5, price=20, expire=None, oldstock=0))
        # bump branch_stock to cover it
        bs = await s.execute(select(BranchStock).where(BranchStock.branch_id == world["src"], BranchStock.drug_id == world["drug_a"]))
        bs.scalar_one().qty += 5
        await s.commit()

    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "5"}]},
    )
    assert r.status_code == 201
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    # dispatch the NULL-expire lot explicitly (FEFO would pick dated lots first)
    null_batch = [b for b in await u._batches(world["src"], world["drug_a"]) if b.expire is None][0]
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={"lines": [{"line_id": draft["lines"][0]["id"], "allocations": [{"batch_id": null_batch.id, "qty": "5"}]}]},
    )
    assert r.status_code == 200, r.text
    line = (await u._transfer(draft["id"]))[1][0]
    alloc = line.alloc_json[0]
    assert alloc["vat"] == "5.00" or float(alloc["vat"]) == 5.0
    assert alloc["price"] == "20.0000" or float(alloc["price"]) == 20.0
    assert alloc["expire"] is None

    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "5"}]},
    )
    assert r.status_code == 200
    tgt_lots = [b for b in await u._batches(world["tgt"], world["drug_a"]) if b.randomid == null_batch.randomid]
    assert len(tgt_lots) == 1 and tgt_lots[0].typee == "transfer_in"
    assert float(tgt_lots[0].vat) == 5.0 and float(tgt_lots[0].price) == 20.0 and tgt_lots[0].expire is None


# ---------- VA-1 boundaries ----------

async def test_qty_5dp_and_overflow_rejected_400(world):
    c = world["client"]
    for qty in ("1.00005", "0.00001", "99999999999999.99999"):
        r = await c.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": qty}]},
        )
        assert r.status_code in (400, 422), f"qty={qty} -> {r.status_code}"
    # smallest valid 4dp passes
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "0.0001"}]},
    )
    assert r.status_code == 201
    world["_transfer_ids"].append(r.json()["id"])


async def test_float_json_qty_coerced_safely(world):
    # JSON number 1.1 arrives as Python float; Decimal field coerces via str() so no 500
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": 1.1}]},
    )
    # must not 500 — either accepted as 1.1000 or clean 400; we pin accepted
    assert r.status_code == 201
    world["_transfer_ids"].append(r.json()["id"])


# ---------- RB-1 dispatch/receive/cancel as level 2 on correct branch ----------

async def test_level2_on_correct_branch_cannot_dispatch_receive_cancel(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "1"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    line = (await u._transfer(d["id"]))[1][0]
    # create level 2 users on both branches
    for branch, token_branch in [(world["src"], world["src"]), (world["tgt"], world["tgt"])]:
        name = u._uniq("low")
        uid = await u._make_user(name, level=2, branch_id=branch)
        world["_user_ids"].append(uid)
        tok = await u._login_token(c, name)
        for path, body in [
            (f"/api/v1/transfers/{d['id']}/dispatch", {}),
            (f"/api/v1/transfers/{d['id']}/receive", {"lines": [{"line_id": line.id, "received_qty": "1"}]}),
            (f"/api/v1/transfers/{d['id']}/cancel", None),
        ]:
            r = await c.post(path, headers=u._headers(tok), json=body if body is not None else {})
            assert r.status_code == 403, f"{path} as level2 on correct branch should 403"


# ---------- VA-7 duplicate line_id ----------

async def test_receive_duplicate_line_id_rejected_400(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "2"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    lid = (await u._transfer(d["id"]))[1][0].id
    r = await c.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": lid, "received_qty": "1"}, {"line_id": lid, "received_qty": "1"}]},
    )
    assert r.status_code == 400


# ---------- ST-7 shortfall spanning 2 lots ----------

async def test_shortfall_spanning_two_lots_restores_both(world):
    c = world["client"]
    # drug_a has 10+10, dispatch 15 splits 10+5, receive 4 → shortfall 11 spans both
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "15"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    line = (await u._transfer(d["id"]))[1][0]
    r = await c.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "4"}]},
    )
    assert r.status_code == 200
    src = await u._batches(world["src"], world["drug_a"])
    # dispatch: lot1 10→0, lot2 10→5; shortfall 11 restores 10 to lot1, 1 to lot2
    assert [float(b.qty) for b in src] == [10.0, 6.0]
    tgt = await u._batches(world["tgt"], world["drug_a"])
    assert sum(float(b.qty) for b in tgt) == 4.0


# ---------- G12-2 payload ----------

async def test_sync_payload_contains_allocations_and_received_qty(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "3"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    async with SessionLocal() as s:
        sync = (
            await s.execute(
                select(SyncLog).where(SyncLog.entity == "transfer", SyncLog.entity_id == d["id"]).order_by(SyncLog.id.desc())
            )
        ).scalars().first()
        assert sync.payload["lines"][0]["allocations"]  # non-empty after dispatch

    line = (await u._transfer(d["id"]))[1][0]
    await c.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "2"}]},
    )
    async with SessionLocal() as s:
        sync = (
            await s.execute(
                select(SyncLog).where(SyncLog.entity == "transfer", SyncLog.entity_id == d["id"]).order_by(SyncLog.id.desc())
            )
        ).scalars().first()
        assert sync.payload["lines"][0]["received_qty"] == "2.0000"


# ---------- CC-1 concurrent dispatch different drugs both succeed ----------

async def test_concurrent_dispatch_different_drugs_both_succeed(world):
    import asyncio

    c = world["client"]
    drafts = []
    for drug in (world["drug_a"], world["drug_b"]):
        r = await c.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={"target_branch_id": world["tgt"], "lines": [{"drug_id": drug, "qty": "5"}]},
        )
        drafts.append(r.json())
        world["_transfer_ids"].append(drafts[-1]["id"])

    async def go(did):
        return await c.post(f"/api/v1/transfers/{did}/dispatch", headers=u._headers(world["src_token"]), json={})

    results = await asyncio.gather(go(drafts[0]["id"]), go(drafts[1]["id"]))
    assert all(r.status_code == 200 for r in results)


# ---------- LOW ----------

async def test_duplicate_batch_id_within_line_400(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "4"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    b = (await u._batches(world["src"], world["drug_a"]))[0]
    r = await c.post(
        f"/api/v1/transfers/{d['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={"lines": [{"line_id": d["lines"][0]["id"], "allocations": [{"batch_id": b.id, "qty": "2"}, {"batch_id": b.id, "qty": "2"}]}]},
    )
    assert r.status_code == 400


async def test_empty_allocations_list_400(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "4"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    r = await c.post(
        f"/api/v1/transfers/{d['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={"lines": [{"line_id": d["lines"][0]["id"], "allocations": []}]},
    )
    assert r.status_code == 400


async def test_missing_branch_stock_dispatch_409(world):
    # drug never stocked on src
    c = world["client"]
    fresh = await u._make_drug_with_stock(branch_id=world["tgt"], stock_qty="10", batches=[("10", "5", "2027-01-01")])
    world["_drug_ids"].append(fresh)
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": fresh, "qty": "2"}]},
    )
    assert r.status_code == 201
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    r = await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    assert r.status_code == 409


async def test_dispatch_after_target_deactivated_400(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "2"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    admin = await c.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    hdr = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    await c.delete(f"/api/v1/branches/{world['tgt']}", headers=hdr)
    r = await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    assert r.status_code == 400
    # restore for cleanup's FK checks (reactivate via direct DB)
    async with SessionLocal() as s:
        b = await s.get(Branch, world["tgt"])
        b.is_active = True
        await s.commit()


async def test_missing_batch_id_400(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "2"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    r = await c.post(
        f"/api/v1/transfers/{d['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={"lines": [{"line_id": d["lines"][0]["id"], "allocations": [{"batch_id": 99999999, "qty": "2"}]}]},
    )
    assert r.status_code == 400


async def test_note_and_legacy_fatid_length_400(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "1"}], "note": "x" * 201},
    )
    assert r.status_code in (400, 422)
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "1"}], "legacy_fatid": "x" * 51},
    )
    assert r.status_code in (400, 422)


async def test_stock_never_negative_after_flow(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "8"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    line = (await u._transfer(d["id"]))[1][0]
    await c.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "2"}]},
    )
    async with SessionLocal() as s:
        for b in (await s.execute(select(StockBatch).where(StockBatch.drug_id == world["drug_a"]))).scalars():
            assert float(b.qty) >= 0 and float(b.oldstock) >= 0
        for bs in (await s.execute(select(BranchStock).where(BranchStock.drug_id == world["drug_a"]))).scalars():
            assert float(bs.qty) >= 0


async def test_branchless_read_returns_empty_not_403(world):
    c = world["client"]
    name = u._uniq("nobody")
    uid = await u._make_user(name, level=9, branch_id=None)
    world["_user_ids"].append(uid)
    tok = await u._login_token(c, name)
    r = await c.get("/api/v1/transfers", headers=u._headers(tok))
    assert r.status_code == 200 and r.json()["transfers"] == []


async def test_received_qty_wire_null_vs_zero(world):
    c = world["client"]
    r = await c.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "2"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    assert d["lines"][0]["received_qty"] is None
    await c.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    line = (await u._transfer(d["id"]))[1][0]
    await c.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "0"}]},
    )
    r = await c.get(f"/api/v1/transfers/{d['id']}", headers=u._headers(world["src_token"]))
    assert r.json()["lines"][0]["received_qty"] == "0.0000"
