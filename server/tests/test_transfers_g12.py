"""Inter-pharmacy transfers (#32) — G12 atomicity invariants.

Every transition writes its audit row(s) and one `entity='transfer'` outbox
row PER AFFECTED BRANCH inside the SAME transaction — and a rejected
transition (insufficient stock, bad allocations) leaves NOTHING behind:
no audit, no outbox, no stock movement.
"""
import pytest
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.models import AuditLog, BranchStock, StockBatch, SyncLog

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
        stock_qty="10",
        batches=[("4", "5", "2026-12-01"), ("6", "7", "2027-06-01")],
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


async def _watermarks() -> tuple[int, int]:
    async with SessionLocal() as session:
        max_audit = (
            await session.execute(select(func.coalesce(func.max(AuditLog.id), 0)))
        ).scalar_one()
        max_sync = (
            await session.execute(select(func.coalesce(func.max(SyncLog.id), 0)))
        ).scalar_one()
    return max_audit, max_sync


async def _rows_since(max_audit: int, max_sync: int) -> tuple[list, list]:
    async with SessionLocal() as session:
        audits = (
            (
                await session.execute(
                    select(AuditLog).where(AuditLog.id > max_audit).order_by(AuditLog.id)
                )
            )
            .scalars()
            .all()
        )
        syncs = (
            (
                await session.execute(
                    select(SyncLog).where(SyncLog.id > max_sync).order_by(SyncLog.id)
                )
            )
            .scalars()
            .all()
        )
    return list(audits), list(syncs)


async def test_every_transition_writes_audit_and_outbox_for_both_branches(world):
    client = world["client"]
    drug = world["drug"]

    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": drug, "qty": "8"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    line_id = draft["lines"][0]["id"]

    mark = await _watermarks()

    await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    audits, syncs = await _rows_since(*mark)
    dispatch_actions = [(a.entity, a.action) for a in audits]
    # 2 batch decrements + 1 branch_stock decrement, then the header flip
    assert dispatch_actions == [
        ("stock_batches", "transfer_out"),
        ("stock_batches", "transfer_out"),
        ("branch_stock", "transfer_out"),
        ("transfer", "update"),
    ]
    assert {a.typevalue for a in audits} == {draft["transfer_no"]}
    assert all(
        a.drug_id == drug for a in audits if a.entity != "transfer"
    )
    # one outbox row PER AFFECTED BRANCH so both peers converge
    assert [s.branch_id for s in syncs] == [world["src"], world["tgt"]]
    assert all(s.entity == "transfer" and s.action == "update" for s in syncs)

    mark = await _watermarks()
    await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line_id, "received_qty": "6"}]},
    )
    audits, syncs = await _rows_since(*mark)
    receive_actions = [(a.entity, a.action) for a in audits]
    # 2 target lots landed + 1 target branch_stock + 1 shortfall batch restore
    # + 1 shortfall branch_stock restore, then the header flip
    assert receive_actions == [
        ("stock_batches", "transfer_in"),
        ("stock_batches", "transfer_in"),
        ("branch_stock", "transfer_in"),
        ("stock_batches", "transfer_shortage_return"),
        ("branch_stock", "transfer_shortage_return"),
        ("transfer", "update"),
    ]
    assert [s.branch_id for s in syncs] == [world["src"], world["tgt"]]


async def test_rejected_dispatch_leaves_no_trace(world):
    client = world["client"]
    drug = world["drug"]
    batches = await u._batches(world["src"], drug)

    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": drug, "qty": "3"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])

    mark = await _watermarks()
    # nominate more than shelf B holds
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={
            "lines": [
                {
                    "line_id": draft["lines"][0]["id"],
                    "allocations": [{"batch_id": batches[1].id, "qty": "99"}],
                }
            ]
        },
    )
    assert r.status_code == 409

    audits, syncs = await _rows_since(*mark)
    assert audits == [] and syncs == []
    # stock untouched, transfer still draft
    assert await u._stock_qty(world["src"], drug) == 10
    transfer, lines = await u._transfer(draft["id"])
    assert transfer.status == "draft"
    assert lines[0].alloc_json is None


async def test_batch_sum_matches_branch_stock_after_flow(world):
    """Stock invariant: SUM(batches.qty) == branch_stock.qty on both sides."""
    client = world["client"]
    drug = world["drug"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": drug, "qty": "7"}],
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
        json={"lines": [{"line_id": line_id, "received_qty": "5"}]},
    )

    for branch_id in (world["src"], world["tgt"]):
        async with SessionLocal() as session:
            batches = (
                await session.execute(
                    select(func.coalesce(func.sum(StockBatch.qty), 0)).where(
                        StockBatch.branch_id == branch_id,
                        StockBatch.drug_id == drug,
                    )
                )
            ).scalar_one()
            stock = (
                await session.execute(
                    select(BranchStock.qty).where(
                        BranchStock.branch_id == branch_id,
                        BranchStock.drug_id == drug,
                    )
                )
            ).scalar_one()
        assert batches == stock, f"batch sum != branch_stock on branch {branch_id}"
