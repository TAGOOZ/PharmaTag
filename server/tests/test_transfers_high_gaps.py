"""HIGH gaps: multi-line, concurrency numbering, no-GL, cancel-vs-dispatch race,
audit branch tagging, terminal states + sequential retry.

Each test pins a concrete HIGH finding from the edge-case audit. All drive
the public API as branch-pinned users — no direct DB writes except stock
fixtures.
"""
import asyncio

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import AuditLog, Balance, BranchStock, DrawerMovement, Journal, JournalLine, StockBatch, SyncLog

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


# ---------- ST-1 multi-line happy flow ----------

async def test_multiline_draft_dispatch_receive_happy(world):
    """Two drugs in one transfer: FEFO per drug, target gets both lots,
    branch_stock sums match."""
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [
                {"drug_id": world["drug_a"], "qty": "8"},
                {"drug_id": world["drug_b"], "qty": "5"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    assert len(draft["lines"]) == 2
    line_a = next(li for li in draft["lines"] if li["drug_id"] == world["drug_a"])
    line_b = next(li for li in draft["lines"] if li["drug_id"] == world["drug_b"])

    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    assert r.status_code == 200, r.text
    assert await u._stock_qty(world["src"], world["drug_a"]) == 12
    assert await u._stock_qty(world["src"], world["drug_b"]) == 10

    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={
            "lines": [
                {"line_id": line_a["id"], "received_qty": "8"},
                {"line_id": line_b["id"], "received_qty": "5"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"
    assert await u._stock_qty(world["tgt"], world["drug_a"]) == 8
    assert await u._stock_qty(world["tgt"], world["drug_b"]) == 5


async def test_cross_drug_batch_contamination_rejected_400(world):
    """Supplying a lot of drug A for drug B's line must 400 — drug_id is
    validated against the batch row."""
    client = world["client"]
    batch_a = (await u._batches(world["src"], world["drug_a"]))[0]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [
                {"drug_id": world["drug_a"], "qty": "2"},
                {"drug_id": world["drug_b"], "qty": "2"},
            ],
        },
    )
    assert r.status_code == 201
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    line_b = next(li for li in draft["lines"] if li["drug_id"] == world["drug_b"])
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {
                    "line_id": line_b["id"],
                    "allocations": [{"batch_id": batch_a.id, "qty": "2"}],
                }
            ]
        },
    )
    assert r.status_code == 400
    transfer, _ = await u._transfer(draft["id"])
    assert transfer.status == "draft"


async def test_multiline_dispatch_atomic_when_second_line_fails(world):
    """Two-line dispatch is all-or-nothing: first line must leave qty/oldstock
    untouched when second line's explicit allocation is bad."""
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [
                {"drug_id": world["drug_a"], "qty": "4"},
                {"drug_id": world["drug_b"], "qty": "4"},
            ],
        },
    )
    assert r.status_code == 201
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    line_a = next(li for li in draft["lines"] if li["drug_id"] == world["drug_a"])
    # good explicit for A, bad sum for B
    batch_b = (await u._batches(world["src"], world["drug_b"]))[0]
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {"line_id": line_a["id"], "allocations": None},  # FEFO -> valid
                {
                    "line_id": next(li for li in draft["lines"] if li["drug_id"] == world["drug_b"])["id"],
                    "allocations": [{"batch_id": batch_b.id, "qty": "3"}],  # 3 != 4
                },
            ]
        },
    )
    assert r.status_code == 400
    transfer, lines = await u._transfer(draft["id"])
    assert transfer.status == "draft"
    assert all(li.alloc_json is None for li in lines)
    assert await u._stock_qty(world["src"], world["drug_a"]) == 20
    assert await u._stock_qty(world["src"], world["drug_b"]) == 15


# ---------- NU-1 concurrent numbering ----------

async def test_concurrent_drafts_number_monotonically_per_source(world):
    client = world["client"]

    async def go():
        return await client.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={
                "target_branch_id": world["tgt"],
                "lines": [{"drug_id": world["drug_a"], "qty": "1"}],
            },
        )

    results = await asyncio.gather(go(), go(), go())
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    nos = sorted(int(r.json()["transfer_no"]) for r in results)
    assert nos == [1, 2, 3]
    for r in results:
        world["_transfer_ids"].append(r.json()["id"])
    # cross-source isolation: tgt as source starts at 1
    tgt_name = u._uniq("tgt2")
    tgt_user = await u._make_user(tgt_name, level=3, branch_id=world["tgt"])
    world["_user_ids"].append(tgt_user)
    tok = await u._login_token(client, tgt_name)
    drug_t = await u._make_drug_with_stock(
        branch_id=world["tgt"], stock_qty="10", batches=[("10", "5", "2027-01-01")]
    )
    world["_drug_ids"].append(drug_t)
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(tok),
        json={"target_branch_id": world["src"], "lines": [{"drug_id": drug_t, "qty": "1"}]},
    )
    assert r.status_code == 201
    assert r.json()["transfer_no"] == "1"
    world["_transfer_ids"].append(r.json()["id"])


# ---------- G12-3 no-GL invariant ----------

async def test_no_journals_through_full_transfer_flow(world):
    client = world["client"]

    async def _counts(s):
        tables = (Journal, JournalLine, DrawerMovement, Balance)
        return [
            (await s.execute(select(func.count()).select_from(t))).scalar_one()
            for t in tables
        ]

    async with SessionLocal() as s:
        before = await _counts(s)
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug_a"], "qty": "4"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    line_id = draft["lines"][0]["id"]
    await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line_id, "received_qty": "3"}]},
    )
    async with SessionLocal() as s:
        after = await _counts(s)
        # T3 no-GL: no journal header/line, drawer movement, or balance row may
        # be created by any transfer transition (balances may pre-exist as
        # seed data — the invariant is a ZERO DELTA)
        assert after == before


# ---------- SM-4 cancel vs dispatch race ----------

async def test_concurrent_cancel_vs_dispatch_exactly_one_wins(world):
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug_a"], "qty": "5"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])

    async def dispatch():
        return await client.post(
            f"/api/v1/transfers/{draft['id']}/dispatch",
            headers=u._headers(world["src_token"]),
            json={},
        )

    async def cancel():
        return await client.post(
            f"/api/v1/transfers/{draft['id']}/cancel",
            headers=u._headers(world["tgt_token"]),
        )

    results = await asyncio.gather(dispatch(), cancel())
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409]
    transfer, _ = await u._transfer(draft["id"])
    assert transfer.status in ("dispatched", "cancelled")
    # zero-or-once decrement invariant
    qty = await u._stock_qty(world["src"], world["drug_a"])
    assert qty is not None and float(qty) in (15.0, 20.0)


# ---------- SM-1/SM-6 terminal + sequential retry ----------

async def test_cancel_terminal_and_sequential_retry_idempotent(world):
    client = world["client"]
    # cancel terminal
    for status in ("received", "cancelled"):
        r = await client.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={
                "target_branch_id": world["tgt"],
                "lines": [{"drug_id": world["drug_a"], "qty": "1"}],
            },
        )
        d = r.json()
        world["_transfer_ids"].append(d["id"])
        await client.post(f"/api/v1/transfers/{d['id']}/cancel", headers=u._headers(world["src_token"]))
        r = await client.post(f"/api/v1/transfers/{d['id']}/cancel", headers=u._headers(world["src_token"]))
        assert r.status_code == 409, "double cancel"
        if status == "received":
            # drive one to received then try cancel
            d2 = (await client.post(
                "/api/v1/transfers",
                headers=u._headers(world["src_token"]),
                json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "1"}]},
            )).json()
            world["_transfer_ids"].append(d2["id"])
            await client.post(f"/api/v1/transfers/{d2['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
            line = (await u._transfer(d2["id"]))[1][0]
            await client.post(
                f"/api/v1/transfers/{d2['id']}/receive",
                headers=u._headers(world["tgt_token"]),
                json={"lines": [{"line_id": line.id, "received_qty": "1"}]},
            )
            r = await client.post(f"/api/v1/transfers/{d2['id']}/cancel", headers=u._headers(world["src_token"]))
            assert r.status_code == 409
            r = await client.post(f"/api/v1/transfers/{d2['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
            assert r.status_code == 409

    # sequential retry: dispatch then dispatch again -> 409, stock moved once
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "2"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await client.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    r2 = await client.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    assert r2.status_code == 409


# ---------- G12-1/G12-2 create/cancel audit+outbox, rejected receive no trace ----------

async def test_create_and_cancel_write_audit_and_both_branch_outboxes(world):
    from sqlalchemy import func as F

    async def watermarks():
        async with SessionLocal() as s:
            a = (await s.execute(select(F.coalesce(F.max(AuditLog.id), 0)))).scalar_one()
            sy = (await s.execute(select(F.coalesce(F.max(SyncLog.id), 0)))).scalar_one()
            return a, sy

    async def since(ma, ms):
        async with SessionLocal() as s:
            audits = (await s.execute(select(AuditLog).where(AuditLog.id > ma))).scalars().all()
            syncs = (await s.execute(select(SyncLog).where(SyncLog.id > ms))).scalars().all()
            return list(audits), list(syncs)

    ma, ms = await watermarks()
    r = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "1"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    audits, syncs = await since(ma, ms)
    assert any(a.entity == "transfer" and a.action == "insert" for a in audits)
    assert {s.branch_id for s in syncs} == {world["src"], world["tgt"]}

    ma, ms = await watermarks()
    r = await world["client"].post(f"/api/v1/transfers/{d['id']}/cancel", headers=u._headers(world["src_token"]))
    assert r.status_code == 200
    audits, syncs = await since(ma, ms)
    assert any(a.entity == "transfer" and a.action == "update" for a in audits)
    assert {s.branch_id for s in syncs} == {world["src"], world["tgt"]}


async def test_rejected_receive_leaves_no_trace(world):
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "4"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await client.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    line = (await u._transfer(d["id"]))[1][0]

    async with SessionLocal() as s:
        ma = (await s.execute(select(func.coalesce(func.max(AuditLog.id), 0)))).scalar_one()
        ms = (await s.execute(select(func.coalesce(func.max(SyncLog.id), 0)))).scalar_one()
        stock_before = (await s.execute(select(BranchStock.qty).where(BranchStock.branch_id == world["tgt"], BranchStock.drug_id == world["drug_a"]))).scalar_one_or_none()

    r = await client.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "99"}]},
    )
    assert r.status_code == 400
    transfer, lines = await u._transfer(d["id"])
    assert transfer.status == "dispatched" and lines[0].received_qty is None
    async with SessionLocal() as s:
        assert (await s.execute(select(func.coalesce(func.max(AuditLog.id), 0)))).scalar_one() == ma
        assert (await s.execute(select(func.coalesce(func.max(SyncLog.id), 0)))).scalar_one() == ms
        after = (await s.execute(select(BranchStock.qty).where(BranchStock.branch_id == world["tgt"], BranchStock.drug_id == world["drug_a"]))).scalar_one_or_none()
        assert after == stock_before


async def test_header_audit_branch_is_source_even_for_target_acts(world):
    """_record always stamps AuditLog.branch_id = source — documented 'source
    book' semantics (T3). Pin it so a future refactor doesn't silently split."""
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "2"}]},
    )
    d = r.json()
    world["_transfer_ids"].append(d["id"])
    await client.post(f"/api/v1/transfers/{d['id']}/dispatch", headers=u._headers(world["src_token"]), json={})
    line = (await u._transfer(d["id"]))[1][0]
    await client.post(
        f"/api/v1/transfers/{d['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line.id, "received_qty": "2"}]},
    )
    async with SessionLocal() as s:
        rows = (await s.execute(select(AuditLog).where(AuditLog.entity == "transfer", AuditLog.entity_id == d["id"]).order_by(AuditLog.id))).scalars().all()
        assert [r.branch_id for r in rows] == [world["src"], world["src"], world["src"]], "create/dispatch/receive headers all source-book"
        assert [r.action for r in rows] == ["insert", "update", "update"]
