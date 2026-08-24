"""Offline-peer convergence for `entity='transfer'` outbox rows (#55).

Both branches receive the SAME payload copy of every transition (G12), so
replay dedupe keys on the SOURCE namespace UNIQUE(source_branch_id,
transfer_no) — never on sync_log.branch_id. Replay applies recorded effects
VERBATIM (lot-exact: ETA cost trails and expiry tracking are legally
significant): allocations land exactly as receive_line books them, without
re-running validation or FEFO. A poisoned row fails alone and stays pending
(G10: recorded, never lost).
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, update

from app.core.db import SessionLocal
from app.models import (
    AuditLog,
    BranchStock,
    StockBatch,
    SyncLog,
    Transfer,
    TransferLine,
)
from app.sync.service import replay_pending

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
    # replay recreates transfers/lines under NEW ids — sweep by drug so the
    # FK chain unwinds regardless
    async with SessionLocal() as s:
        line_ids = (
            await s.execute(
                select(TransferLine.transfer_id).where(
                    TransferLine.drug_id == world["drug"]
                )
            )
        ).scalars().all()
        await s.execute(
            delete(TransferLine.__table__).where(
                TransferLine.drug_id == world["drug"]
            )
        )
        if line_ids:
            await s.execute(
                delete(Transfer.__table__).where(Transfer.id.in_(line_ids))
            )
        await s.commit()
    await u._cleanup(
        transfer_ids=world["_transfer_ids"],
        drug_ids=world["_drug_ids"],
        branch_ids=world["_branch_ids"],
        user_ids=world["_user_ids"],
    )


async def _flow(world, received_qty: str) -> dict:
    """create → dispatch → receive through the API; returns the draft body."""
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "10"}],
        },
    )
    assert r.status_code in (200, 201), r.text
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    line_id = draft["lines"][0]["id"]
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    assert r.status_code in (200, 201), r.text
    r = await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={"lines": [{"line_id": line_id, "received_qty": received_qty}]},
    )
    assert r.status_code in (200, 201), r.text
    return draft


async def _transfer_by_no(src_branch: int, transfer_no: str):
    async with SessionLocal() as s:
        transfer = (
            await s.execute(
                select(Transfer).where(
                    Transfer.source_branch_id == src_branch,
                    Transfer.transfer_no == transfer_no,
                )
            )
        ).scalar_one()
        lines = (
            await s.execute(
                select(TransferLine)
                .where(TransferLine.transfer_id == transfer.id)
                .order_by(TransferLine.id)
            )
        ).scalars().all()
    return transfer, list(lines)


async def _pick_row(branch_id: int, status: str) -> int:
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(SyncLog)
                .where(SyncLog.entity == "transfer", SyncLog.branch_id == branch_id)
                .order_by(SyncLog.id)
            )
        ).scalars().all()
    matched = [r for r in rows if (r.payload or {}).get("status") == status]
    assert matched, f"no {status} outbox row for branch {branch_id}"
    return matched[-1].id


async def _only_pending(*keep_ids: int) -> None:
    """Make exactly `keep_ids` the only PENDING entity='transfer' rows so a
    replay sees just the seeded scenario (re-forcing them pending lets a
    later phase redeliver a copy a previous phase marked applied)."""
    async with SessionLocal() as s:
        await s.execute(
            update(SyncLog)
            .where(
                SyncLog.entity == "transfer",
                SyncLog.id.notin_(keep_ids),
            )
            .values(status="applied")
        )
        if keep_ids:
            await s.execute(
                update(SyncLog)
                .where(SyncLog.entity == "transfer", SyncLog.id.in_(keep_ids))
                .values(status="pending")
            )
        await s.commit()


async def _wipe_target_side(world) -> None:
    """Simulate an offline peer that never saw ANY of the flow: no transfers,
    no lines, no target-side stock."""
    async with SessionLocal() as s:
        tids = world["_transfer_ids"]
        await s.execute(delete(Transfer.__table__).where(Transfer.id.in_(tids)))
        await s.execute(
            delete(StockBatch.__table__).where(
                StockBatch.branch_id == world["tgt"],
                StockBatch.drug_id == world["drug"],
            )
        )
        await s.execute(
            delete(BranchStock.__table__).where(
                BranchStock.branch_id == world["tgt"],
                BranchStock.drug_id == world["drug"],
            )
        )
        await s.commit()


async def _batch_snapshot(branch_id: int, drug_id: int) -> list[dict]:
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(StockBatch)
                .where(
                    StockBatch.branch_id == branch_id,
                    StockBatch.drug_id == drug_id,
                )
                .order_by(StockBatch.randomid)
            )
        ).scalars().all()
        return [
            {
                "randomid": b.randomid,
                "qty": str(b.qty),
                "cost": str(b.cost),
                "vat": str(b.vat),
                "price": str(b.price),
                "expire": b.expire.isoformat() if b.expire else None,
                "typee": b.typee,
            }
            for b in rows
        ]


async def _audit_watermark() -> int:
    async with SessionLocal() as s:
        return (
            await s.execute(select(func.coalesce(func.max(AuditLog.id), 0)))
        ).scalar_one()


async def _audits_since(mark: int, action: str, branch_id: int) -> list[AuditLog]:
    async with SessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.id > mark,
                        AuditLog.action == action,
                        AuditLog.branch_id == branch_id,
                    )
                )
            ).scalars().all()
        )


async def _transfers_count(src_branch: int, transfer_no: str) -> int:
    async with SessionLocal() as s:
        return (
            await s.execute(
                select(func.count())
                .select_from(Transfer)
                .where(
                    Transfer.source_branch_id == src_branch,
                    Transfer.transfer_no == transfer_no,
                )
            )
        ).scalar_one()


async def test_replay_recreates_target_side_byte_identical(world):
    draft = await _flow(world, "10")
    before = await _batch_snapshot(world["tgt"], world["drug"])
    assert len(before) == 2  # two lots landed by the live receive
    row_id = await _pick_row(world["tgt"], "received")
    await _wipe_target_side(world)
    await _only_pending(row_id)

    mark = await _audit_watermark()
    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    # header + line recreated with the payload's identity and quantities
    transfer, lines = await _transfer_by_no(world["src"], draft["transfer_no"])
    assert transfer.source_branch_id == world["src"]
    assert transfer.target_branch_id == world["tgt"]
    assert transfer.transfer_no == draft["transfer_no"]
    assert transfer.status == "received"
    assert str(lines[0].sent_qty) == "10.0000"
    assert str(lines[0].received_qty) == "10.0000"

    # batches byte-identical (randomid/qty/cost/vat/price/expire/typee)
    after = await _batch_snapshot(world["tgt"], world["drug"])
    assert after == before

    # branch_stock correct and transfer_in bookkeeping reproduced
    assert await u._stock_qty(world["tgt"], world["drug"]) == Decimal("10")
    audits = await _audits_since(mark, "transfer_in", world["tgt"])
    entities = sorted(a.entity for a in audits)
    assert entities == ["branch_stock", "stock_batches", "stock_batches"]
    assert all(a.typevalue == draft["transfer_no"] for a in audits)

    # second pass over the SAME row is skipped, not re-applied
    async with SessionLocal() as s:
        await s.execute(
            update(SyncLog).where(SyncLog.id == row_id).values(status="pending")
        )
        await s.commit()
    second = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert second["skipped"] == 1
    assert second["applied"] == 0
    assert await _transfers_count(world["src"], draft["transfer_no"]) == 1
    assert await _batch_snapshot(world["tgt"], world["drug"]) == before


async def test_replay_shortfall_restores_source_batches(world):
    """Branch-filtered replay (#55 gap fix): the TARGET copy of a received row
    reproduces only the target landing; the SOURCE copy carries the shortfall
    auto-return to its own batches. Each phase simulates one peer's own DB."""
    await _flow(world, "6")  # 4-unit shortfall auto-returned live
    before = await _batch_snapshot(world["tgt"], world["drug"])
    # target lots ordered by source-batch randomid: lot A (4 taken) and
    # lot B (2 taken) landed head-first from the allocations
    assert [b["qty"] for b in before] == ["4.0000", "2.0000"]
    tgt_row = await _pick_row(world["tgt"], "received")
    src_row = await _pick_row(world["src"], "received")

    # ---- target peer: revert the source side to post-dispatch (shortfall not
    # yet returned) and wipe the landing — its copy must rebuild the TARGET side
    async with SessionLocal() as s:
        await s.execute(
            update(StockBatch.__table__)
            .where(
                StockBatch.branch_id == world["src"],
                StockBatch.drug_id == world["drug"],
            )
            .values(qty=0)
        )
        await s.execute(
            update(BranchStock.__table__)
            .where(
                BranchStock.branch_id == world["src"],
                StockBatch.drug_id == world["drug"],
            )
            .values(qty=0)
        )
        await s.commit()
    await _wipe_target_side(world)
    await _only_pending(tgt_row)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    # target side reproduced …
    assert await _batch_snapshot(world["tgt"], world["drug"]) == before
    assert await u._stock_qty(world["tgt"], world["drug"]) == Decimal("6")
    # … but the SOURCE side is NOT the target copy's business (branch filter)
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == ["0.0000", "0.0000"]
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("0")

    # ---- source peer: fresh local world at pre-dispatch (draft levels, no
    # local row) — ITS copy folds dispatch-decrement + shortfall restore
    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DRAFT_SRC_BATCHES, src_stock="10", wipe_tgt=True
    )
    await _only_pending(src_row)

    summary = await replay_pending(SessionLocal(), branch_id=world["src"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0
    src_batches = await u._batches(world["src"], world["drug"])
    # batch A gets the whole 4-unit shortfall back, batch B stays empty
    assert [str(b.qty) for b in src_batches] == ["4.0000", "0.0000"]
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("4")
    # target landing untouched by the source copy
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []


async def test_concurrent_double_replay_applies_once(world):
    draft = await _flow(world, "10")
    before = await _batch_snapshot(world["tgt"], world["drug"])
    row_id = await _pick_row(world["tgt"], "received")
    await _wipe_target_side(world)
    await _only_pending(row_id)

    results = await asyncio.gather(
        replay_pending(SessionLocal(), branch_id=world["tgt"]),
        replay_pending(SessionLocal(), branch_id=world["tgt"]),
    )
    assert sum(r["applied"] for r in results) == 1
    assert sum(r["failed"] for r in results) == 0
    # no IntegrityError leak: one transfers row, batches landed once
    assert await _transfers_count(world["src"], draft["transfer_no"]) == 1
    assert await _batch_snapshot(world["tgt"], world["drug"]) == before


async def test_payload_carries_updated_at_watermark(world):
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])

    async def _latest_payload(status: str) -> dict:
        async with SessionLocal() as s:
            rows = (
                await s.execute(
                    select(SyncLog)
                    .where(
                        SyncLog.entity == "transfer",
                        SyncLog.branch_id == world["src"],
                    )
                    .order_by(SyncLog.id)
                )
            ).scalars().all()
        matched = [x for x in rows if (x.payload or {}).get("status") == status]
        assert matched
        return matched[-1].payload

    p = await _latest_payload("draft")
    dt = datetime.fromisoformat(p["updated_at"])
    assert dt.tzinfo is not None

    await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    p = await _latest_payload("dispatched")
    transfer, _ = await u._transfer(draft["id"])
    assert datetime.fromisoformat(p["updated_at"]) == transfer.dispatched_at

    await client.post(
        f"/api/v1/transfers/{draft['id']}/receive",
        headers=u._headers(world["tgt_token"]),
        json={
            "lines": [
                {"line_id": draft["lines"][0]["id"], "received_qty": "1"}
            ]
        },
    )
    p = await _latest_payload("received")
    transfer, _ = await u._transfer(draft["id"])
    assert datetime.fromisoformat(p["updated_at"]) == transfer.received_at

    # cancel path (second draft, cancelled by the target party)
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "1"}],
        },
    )
    draft2 = r.json()
    world["_transfer_ids"].append(draft2["id"])
    await client.post(
        f"/api/v1/transfers/{draft2['id']}/cancel",
        headers=u._headers(world["tgt_token"]),
        json={},
    )
    p = await _latest_payload("cancelled")
    transfer, _ = await u._transfer(draft2["id"])
    assert datetime.fromisoformat(p["updated_at"]) == transfer.cancelled_at


async def test_draft_and_cancelled_payloads_are_metadata_only(world):
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "2"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    await client.post(
        f"/api/v1/transfers/{draft['id']}/cancel",
        headers=u._headers(world["src_token"]),
        json={},
    )

    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(SyncLog)
                .where(SyncLog.entity == "transfer", SyncLog.branch_id == world["tgt"])
                .order_by(SyncLog.id)
            )
        ).scalars().all()
    cancelled_row = [x for x in rows if x.payload.get("status") == "cancelled"][-1]

    async with SessionLocal() as s:
        await s.execute(delete(Transfer.__table__).where(Transfer.id == draft["id"]))
        await s.commit()
    await _only_pending(cancelled_row.id)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1

    transfer, lines = await _transfer_by_no(world["src"], draft["transfer_no"])
    assert transfer.status == "cancelled"
    assert str(lines[0].sent_qty) == "2.0000"
    assert lines[0].received_qty is None
    # nothing moved: no target batches, no branch_stock row
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []
    assert await u._stock_qty(world["tgt"], world["drug"]) is None
    assert cancelled_row.payload["updated_at"]


async def test_poisoned_row_isolated_and_stays_pending(world):
    draft = await _flow(world, "10")
    good_row = await _pick_row(world["tgt"], "received")
    await _wipe_target_side(world)

    async with SessionLocal() as s:
        bad = SyncLog(
            branch_id=world["tgt"],
            entity="transfer",
            entity_id=draft["id"],
            action="update",
            payload={
                "kind": "transfer",
                "source_branch_id": world["src"],
                "target_branch_id": world["tgt"],
                "transfer_no": "999999",
                "status": "received",
                "lines": [{"drug_id": None}],  # poison: int(None) explodes
            },
        )
        s.add(bad)
        await s.flush()
        bad_id = bad.id
        await s.commit()

    await _only_pending(good_row, bad_id)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1
    assert summary["failed"] == 1

    async with SessionLocal() as s:
        good = await s.get(SyncLog, good_row)
        bad = await s.get(SyncLog, bad_id)
    assert good.status == "applied"
    # the bad row is NOT consumed: still retryable, failure recorded (G10)
    assert bad.status == "pending"
    assert bad.payload.get("failure")
    # the good row's effects landed despite the poisoned sibling
    assert await _transfers_count(world["src"], draft["transfer_no"]) == 1


# ---------------------------------------------------------------------------
# Versioned apply (rev watermark) — #55 gap fix
# ---------------------------------------------------------------------------

DRAFT_SRC_BATCHES = ["4.0000", "6.0000"]  # batch A / batch B before dispatch
DISPATCHED_SRC_BATCHES = ["0.0000", "0.0000"]  # after dispatch took everything


async def _latest_payload(branch_id: int, status: str) -> dict:
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(SyncLog)
                .where(
                    SyncLog.entity == "transfer",
                    SyncLog.branch_id == branch_id,
                )
                .order_by(SyncLog.id)
            )
        ).scalars().all()
    matched = [x for x in rows if (x.payload or {}).get("status") == status]
    assert matched, f"no {status} outbox row for branch {branch_id}"
    return dict(matched[-1].payload)


async def _seed_pending(branch_id: int, payload: dict) -> int:
    async with SessionLocal() as s:
        row = SyncLog(
            branch_id=branch_id,
            entity="transfer",
            entity_id=None,
            action="update",
            payload=dict(payload),
        )
        s.add(row)
        await s.flush()
        row_id = row.id
        await s.commit()
        return row_id


async def _delete_transfers_for_drug(drug_id: int) -> None:
    async with SessionLocal() as s:
        tids = (
            await s.execute(
                select(TransferLine.transfer_id).where(
                    TransferLine.drug_id == drug_id
                )
            )
        ).scalars().all()
        await s.execute(
            delete(TransferLine.__table__).where(TransferLine.drug_id == drug_id)
        )
        if tids:
            await s.execute(delete(Transfer.__table__).where(Transfer.id.in_(tids)))
        await s.commit()


async def _reset_stock(
    world,
    *,
    src_batches: list[str],
    src_stock: str,
    wipe_tgt: bool = True,
) -> None:
    """Force the source batches/branch_stock to an exact state; optionally
    wipe every target-side trace of the drug."""
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(StockBatch)
                .where(
                    StockBatch.branch_id == world["src"],
                    StockBatch.drug_id == world["drug"],
                )
                .order_by(StockBatch.id)
            )
        ).scalars().all()
        assert len(rows) == len(src_batches)
        for batch, qty in zip(rows, src_batches):
            batch.qty = Decimal(qty)
            batch.oldstock = Decimal(qty)
        branch = (
            await s.execute(
                select(BranchStock).where(
                    BranchStock.branch_id == world["src"],
                    BranchStock.drug_id == world["drug"],
                )
            )
        ).scalar_one()
        branch.qty = Decimal(src_stock)
        if wipe_tgt:
            await s.execute(
                delete(StockBatch.__table__).where(
                    StockBatch.branch_id == world["tgt"],
                    StockBatch.drug_id == world["drug"],
                )
            )
            await s.execute(
                delete(BranchStock.__table__).where(
                    BranchStock.branch_id == world["tgt"],
                    StockBatch.drug_id == world["drug"],
                )
            )
        await s.commit()


async def _seed_local_transfer(
    world,
    *,
    transfer_no: str,
    status: str,
    rev: int,
) -> int:
    """Insert a local transfers row as a peer that saw exactly `status`."""
    async with SessionLocal() as s:
        transfer = Transfer(
            source_branch_id=world["src"],
            target_branch_id=world["tgt"],
            transfer_no=transfer_no,
            status=status,
            rev=rev,
            created_at=datetime.now(timezone.utc),
        )
        s.add(transfer)
        await s.flush()
        s.add(
            TransferLine(
                transfer_id=transfer.id,
                drug_id=world["drug"],
                sent_qty=Decimal("10"),
            )
        )
        tid = transfer.id
        await s.commit()
        return tid


async def test_offline_whole_flow_jump_target_peer(world):
    """A target peer that only ever saw the DRAFT converges to received from
    ONE rev=3 copy — and never touches the source side's stock."""
    await _flow(world, "6")
    payload = await _latest_payload(world["tgt"], "received")
    assert payload["rev"] == 3

    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DRAFT_SRC_BATCHES, src_stock="10", wipe_tgt=True
    )
    row_id = await _seed_pending(world["tgt"], payload)
    await _only_pending(row_id)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    transfer, lines = await _transfer_by_no(world["src"], payload["transfer_no"])
    assert transfer.status == "received"
    assert transfer.rev == 3
    assert str(lines[0].received_qty) == "6.0000"

    # target landed lot-exact
    after = await _batch_snapshot(world["tgt"], world["drug"])
    assert [b["qty"] for b in after] == ["4.0000", "2.0000"]
    assert await u._stock_qty(world["tgt"], world["drug"]) == Decimal("6")

    # SOURCE untouched by the target copy (branch-filtered effects)
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == DRAFT_SRC_BATCHES
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("10")

    # duplicate redelivery after convergence → skipped, stock unchanged
    async with SessionLocal() as s:
        await s.execute(
            update(SyncLog).where(SyncLog.id == row_id).values(status="pending")
        )
        await s.commit()
    second = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert second["skipped"] == 1
    assert second["applied"] == 0
    assert await _batch_snapshot(world["tgt"], world["drug"]) == after


async def test_offline_whole_flow_jump_source_peer(world):
    """A source peer that only ever saw the DRAFT folds dispatch-decrement AND
    shortfall restore from ONE rev=3 copy — without landing any target lots."""
    await _flow(world, "6")
    payload = await _latest_payload(world["src"], "received")
    assert payload["rev"] == 3

    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DRAFT_SRC_BATCHES, src_stock="10", wipe_tgt=True
    )
    row_id = await _seed_pending(world["src"], payload)
    await _only_pending(row_id)

    summary = await replay_pending(SessionLocal(), branch_id=world["src"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    transfer, _ = await _transfer_by_no(world["src"], payload["transfer_no"])
    assert transfer.status == "received"
    assert transfer.rev == 3

    # source side: dispatch decremented everything, receive restored the
    # 4-unit shortfall head-first into batch A
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == ["4.0000", "0.0000"]
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("4")

    # TARGET untouched by the source copy (branch-filtered effects)
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []
    assert await u._stock_qty(world["tgt"], world["drug"]) is None


async def test_dispatch_upgrade_from_local_draft_on_each_peer(world):
    """peer-at-draft + rev=2 dispatched copy: the SOURCE peer decrements its
    batches; the TARGET peer flips header-only and touches nothing."""
    client = world["client"]
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug"], "qty": "10"}],
        },
    )
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    await client.post(
        f"/api/v1/transfers/{draft['id']}/dispatch",
        headers=u._headers(world["src_token"]),
        json={},
    )
    p_src = await _latest_payload(world["src"], "dispatched")
    p_tgt = await _latest_payload(world["tgt"], "dispatched")
    assert p_src["rev"] == 2 and p_tgt["rev"] == 2
    transfer_no = p_src["transfer_no"]

    # ---- source peer: local draft + rev=2 copy → decrement source batches
    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DRAFT_SRC_BATCHES, src_stock="10", wipe_tgt=True
    )
    await _seed_local_transfer(world, transfer_no=transfer_no, status="draft", rev=1)
    await _seed_pending(world["src"], p_src)

    summary = await replay_pending(SessionLocal(), branch_id=world["src"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    transfer, _ = await _transfer_by_no(world["src"], transfer_no)
    assert transfer.status == "dispatched"
    assert transfer.rev == 2
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == DISPATCHED_SRC_BATCHES
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("0")
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []

    # ---- target peer: same local draft + ITS rev=2 copy → header only
    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DRAFT_SRC_BATCHES, src_stock="10", wipe_tgt=True
    )
    await _seed_local_transfer(world, transfer_no=transfer_no, status="draft", rev=1)
    await _seed_pending(world["tgt"], p_tgt)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    transfer, _ = await _transfer_by_no(world["src"], transfer_no)
    assert transfer.status == "dispatched"
    assert transfer.rev == 2
    # no stock moved anywhere: dispatch effects belong to the source copy only
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == DRAFT_SRC_BATCHES
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("10")
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []


async def test_receive_upgrade_shortfall_on_each_peer(world):
    """local dispatched (rev=2) + rev=3 received copy: the TARGET peer lands
    the lots; the SOURCE peer restores the shortfall — each on its side only."""
    await _flow(world, "6")
    p_tgt = await _latest_payload(world["tgt"], "received")
    p_src = await _latest_payload(world["src"], "received")
    transfer_no = p_src["transfer_no"]

    # ---- target peer upgrade: dispatched → received lands the lots
    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DISPATCHED_SRC_BATCHES, src_stock="0", wipe_tgt=True
    )
    await _seed_local_transfer(
        world, transfer_no=transfer_no, status="dispatched", rev=2
    )
    await _seed_pending(world["tgt"], p_tgt)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    transfer, lines = await _transfer_by_no(world["src"], transfer_no)
    assert transfer.status == "received"
    assert transfer.rev == 3
    assert str(lines[0].received_qty) == "6.0000"
    assert [b["qty"] for b in await _batch_snapshot(world["tgt"], world["drug"])] == [
        "4.0000",
        "2.0000",
    ]
    assert await u._stock_qty(world["tgt"], world["drug"]) == Decimal("6")
    # source side untouched by the target copy
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == DISPATCHED_SRC_BATCHES
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("0")

    # ---- source peer upgrade: dispatched → received restores the shortfall
    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DISPATCHED_SRC_BATCHES, src_stock="0", wipe_tgt=True
    )
    await _seed_local_transfer(
        world, transfer_no=transfer_no, status="dispatched", rev=2
    )
    await _seed_pending(world["src"], p_src)

    summary = await replay_pending(SessionLocal(), branch_id=world["src"])
    assert summary["applied"] == 1
    assert summary["failed"] == 0

    transfer, _ = await _transfer_by_no(world["src"], transfer_no)
    assert transfer.status == "received"
    assert transfer.rev == 3
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == ["4.0000", "0.0000"]
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("4")
    # target side untouched by the source copy
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []
    assert await u._stock_qty(world["tgt"], world["drug"]) is None


async def test_out_of_order_rev3_before_rev2_converges_then_skips_stale(world):
    """Deliver the rev=3 received copy BEFORE the rev=2 dispatched copy: the
    first fully converges the source side, the stale rev=2 arrives later and
    must be skipped without double-moving stock."""
    await _flow(world, "6")
    p_recv = await _latest_payload(world["src"], "received")
    p_disp = await _latest_payload(world["src"], "dispatched")

    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DRAFT_SRC_BATCHES, src_stock="10", wipe_tgt=True
    )
    recv_row = await _seed_pending(world["src"], p_recv)
    disp_row = await _seed_pending(world["src"], p_disp)
    await _only_pending(recv_row, disp_row)

    summary = await replay_pending(SessionLocal(), branch_id=world["src"])
    assert summary["applied"] == 1  # the rev=3 row
    assert summary["skipped"] == 1  # the stale rev=2 row
    assert summary["failed"] == 0

    transfer, _ = await _transfer_by_no(world["src"], p_recv["transfer_no"])
    assert transfer.status == "received"
    assert transfer.rev == 3
    # converged exactly once — no double dispatch-decrement
    src_batches = await u._batches(world["src"], world["drug"])
    assert [str(b.qty) for b in src_batches] == ["4.0000", "0.0000"]
    assert await u._stock_qty(world["src"], world["drug"]) == Decimal("4")


async def test_illegal_transition_is_poisoned_and_state_unchanged(world):
    """local received (terminal) vs an edited cancelled payload with a higher
    rev: not a legal chain → the row fails ALONE and stays pending; local
    state and stock are untouched."""
    await _flow(world, "10")
    payload = await _latest_payload(world["tgt"], "received")

    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(world, src_batches=DRAFT_SRC_BATCHES, src_stock="10")
    await _seed_pending(world["tgt"], payload)
    await replay_pending(SessionLocal(), branch_id=world["tgt"])
    before = await _batch_snapshot(world["tgt"], world["drug"])

    evil = {**payload, "status": "cancelled", "rev": 4}
    row_id = await _seed_pending(world["tgt"], evil)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["failed"] == 1
    assert summary["applied"] == 0

    async with SessionLocal() as s:
        row = await s.get(SyncLog, row_id)
    assert row.status == "pending"
    assert row.payload.get("failure")

    transfer, _ = await _transfer_by_no(world["src"], payload["transfer_no"])
    assert transfer.status == "received"
    assert transfer.rev == 3
    assert await _batch_snapshot(world["tgt"], world["drug"]) == before


async def test_mid_upgrade_failure_rolls_back_atomically(world):
    """A crash MID-upgrade leaves NO partial stock: a second line whose drug
    FK explodes after the first line's lots already landed rolls the whole
    fold back — header stays at dispatched/rev2, zero batches, row
    retryable-pending."""
    await _flow(world, "6")
    payload = await _latest_payload(world["tgt"], "received")
    transfer_no = payload["transfer_no"]

    await _delete_transfers_for_drug(world["drug"])
    await _reset_stock(
        world, src_batches=DISPATCHED_SRC_BATCHES, src_stock="0", wipe_tgt=True
    )
    await _seed_local_transfer(
        world, transfer_no=transfer_no, status="dispatched", rev=2
    )

    good_line = dict(payload["lines"][0])
    poisoned = {
        **good_line,
        "drug_id": 99999999,  # FK violation — but only AFTER line 1 landed
    }
    broken = {**payload, "lines": [good_line, poisoned]}
    row_id = await _seed_pending(world["tgt"], broken)
    await _only_pending(row_id)

    summary = await replay_pending(SessionLocal(), branch_id=world["tgt"])
    assert summary["failed"] == 1
    assert summary["applied"] == 0

    async with SessionLocal() as s:
        row = await s.get(SyncLog, row_id)
    assert row.status == "pending"
    assert row.payload.get("failure")

    transfer, _ = await _transfer_by_no(world["src"], transfer_no)
    assert transfer.status == "dispatched"  # flip rolled back with the stock
    assert transfer.rev == 2
    assert await _batch_snapshot(world["tgt"], world["drug"]) == []
    assert await u._stock_qty(world["tgt"], world["drug"]) is None
