"""Inter-pharmacy transfers (#32) — batch provenance (T2/T4).

Dispatch takes explicit-or-FEFO batch allocations from the source (qty +
oldstock snapshots, `transfer_out` audits); receive lands the units on the
target branch as `typee='transfer_in'` lots at the SENT cost/expiry VERBATIM
(EDA traceability), merging into an existing same-randomid lot rather than
re-costing it.
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
        branch_id=src,
        stock_qty="14",
        # two lots: earlier expiry first (FEFO order)
        batches=[("4", "5.5000", "2026-12-01"), ("10", "7.2500", "2027-06-01")],
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


async def _draft_and_dispatch(client, world, *, qty="8", lines=None):
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": lines or [{"drug_id": world["drug"], "qty": qty}],
        },
    )
    assert r.status_code == 201, r.text
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    assert r.status_code == 200, r.text
    return draft["id"], r.json()


async def test_dispatch_splits_fefo_with_oldstock_snapshots(world):
    client = world["client"]
    transfer_id, body = await _draft_and_dispatch(client, world)

    src_batches = await u._batches(world["src"], world["drug"])
    assert [(float(b.qty), float(b.oldstock)) for b in src_batches] == [
        (0, 4),  # earliest-expiry lot drained first
        (6, 10),
    ]
    assert await u._stock_qty(world["src"], world["drug"]) == 6

    # the line records exactly which lots went out (replay seed)
    allocations = body["lines"][0]["allocations"]
    assert [(a["qty"], a["cost"], a["expire"]) for a in allocations] == [
        ("4.0000", "5.5000", "2026-12-01"),
        ("4.0000", "7.2500", "2027-06-01"),
    ]
    _ = transfer_id


async def test_receive_lands_one_lot_per_sent_lot_at_preserved_cost_expire(world):
    """The line spans two source lots ⇒ receiving in full creates TWO target
    lots, each carrying its lot's cost/expiry VERBATIM (EDA traceability —
    expiry is never merged across lots)."""
    client = world["client"]
    transfer_id, dispatched = await _draft_and_dispatch(client, world)
    src_batches = await u._batches(world["src"], world["drug"])
    sent_randomids = [b.randomid for b in src_batches]

    lines = (await u._transfer(transfer_id))[1]
    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": lines[0].id, "received_qty": "8"}]},
    )
    assert r.status_code == 200, r.text

    tgt_batches = await u._batches(world["tgt"], world["drug"])
    assert [(float(b.qty), float(b.cost), str(b.expire), b.typee) for b in tgt_batches] == [
        (4, 5.5, "2026-12-01", "transfer_in"),
        (4, 7.25, "2027-06-01", "transfer_in"),
    ]
    # same physical lots: randomids carry across (per-branch UNIQUE allows it)
    assert [b.randomid for b in tgt_batches] == sent_randomids
    assert await u._stock_qty(world["tgt"], world["drug"]) == 8
    _ = dispatched


async def test_explicit_allocations_override_fefo(world):
    """A client may nominate which lots go (offline dispatch); the server
    validates availability under lock and honors the nomination."""
    client = world["client"]
    src_batches = await u._batches(world["src"], world["drug"])
    lot_a, lot_b = src_batches  # FEFO order: a=earliest expiry

    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "5"}],
        },
    )
    assert r.status_code == 201, r.text
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    line_id = draft["lines"][0]["id"]

    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {
                    "line_id": line_id,
                    "allocations": [
                        {"batch_id": lot_b.id, "qty": "5"},  # NOT the FEFO choice
                    ],
                }
            ]
        },
    )
    assert r.status_code == 200, r.text

    after = await u._batches(world["src"], world["drug"])
    assert (float(after[0].qty), float(after[1].qty)) == (4, 5)


async def test_partial_receive_auto_returns_shortfall_to_source(world):
    client = world["client"]
    transfer_id, _ = await _draft_and_dispatch(client, world, qty="8")
    lines = (await u._transfer(transfer_id))[1]

    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": lines[0].id, "received_qty": "6"}]},
    )
    assert r.status_code == 200, r.text

    # target got the first 6 units in allocation order...
    tgt_batches = await u._batches(world["tgt"], world["drug"])
    assert [(float(b.qty), float(b.cost)) for b in tgt_batches] == [(4, 5.5), (2, 7.25)]
    assert await u._stock_qty(world["tgt"], world["drug"]) == 6

    # ...and the shortfall went back to the source batches (allocation order)
    src_batches = await u._batches(world["src"], world["drug"])
    assert [(float(b.qty), float(b.oldstock)) for b in src_batches] == [(2, 0), (6, 10)]
    assert await u._stock_qty(world["src"], world["drug"]) == 8


async def test_zero_receive_returns_everything_to_source(world):
    client = world["client"]
    transfer_id, _ = await _draft_and_dispatch(client, world, qty="8")
    lines = (await u._transfer(transfer_id))[1]

    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": lines[0].id, "received_qty": "0"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"

    assert await u._stock_qty(world["tgt"], world["drug"]) == 0
    src_batches = await u._batches(world["src"], world["drug"])
    assert [float(b.qty) for b in src_batches] == [4, 10]
    assert await u._stock_qty(world["src"], world["drug"]) == 14


async def test_receive_merges_into_existing_target_lot_without_recosting(world):
    """If the target shelf already holds a lot with the sent randomid, the
    received units join it — its cost/typee stay untouched (no mixed-lot
    re-costing)."""
    from sqlalchemy import select as _select

    from app.core.db import SessionLocal
    from app.models import StockBatch

    client = world["client"]
    transfer_id, dispatched = await _draft_and_dispatch(client, world, qty="4")
    lines = (await u._transfer(transfer_id))[1]
    allocations = dispatched["lines"][0]["allocations"]
    incoming_randomid = None
    async with SessionLocal() as session:
        batch = (
            await session.execute(
                _select(StockBatch).where(StockBatch.id == allocations[0]["batch_id"])
            )
        ).scalar_one()
        incoming_randomid = batch.randomid

    # pre-seed the target with a DIFFERENT-cost lot under the same randomid
    async with SessionLocal() as session:
        session.add(
            StockBatch(
                branch_id=world["tgt"],
                drug_id=world["drug"],
                randomid=incoming_randomid,
                qty=1,
                cost=99,
                typee="purchase",
            )
        )
        await session.commit()

    r = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": lines[0].id, "received_qty": "4"}]},
    )
    assert r.status_code == 200, r.text

    tgt_batches = await u._batches(world["tgt"], world["drug"])
    merged = [b for b in tgt_batches if b.randomid == incoming_randomid][0]
    assert float(merged.qty) == 5          # 1 existing + 4 received
    assert float(merged.cost) == 99.0      # cost NOT overwritten
    assert merged.typee == "purchase"      # provenance untouched on merge
    assert len(tgt_batches) == 1           # no duplicate lot row
