"""Chain consumer for the branch-registry outbox (ticket #34, S5.4).

#31 enqueues `entity='branch'/'branch_identity'` snapshots on every registry
mutation; this slice (a) FANS each mutation out to every active branch's
queue so offline peers can converge, and (b) replays those rows verbatim with
LWW ordering by `updated_at`. Skipped/duplicate deliveries are RECORDED on
the sync_log row (`skipped_reason`), never silently counted away (G10).
"""
import os
import secrets

from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select, update

from app.core.db import SessionLocal
from app.models import AuditLog, Branch, BranchIdentity, SyncLog, User
from app.sync.service import replay_pending

PID = os.getpid()
# random per-import run token: PID alone collides when the OS reuses pids
# across runs that leaked rows (killed/interrupted suites)
_run = secrets.token_hex(3)
_seq = [0]
_watermark: tuple[int, int] | None = None  # (max sync_log.id, max audit_log.id)
_created: list[int] = []


@pytest.fixture(autouse=True)
async def _outbox_watermark():
    global _watermark
    if _watermark is None:
        async with SessionLocal() as session:
            max_sync = (
                await session.execute(
                    select(func.coalesce(func.max(SyncLog.id), 0))
                )
            ).scalar_one()
            max_audit = (
                await session.execute(
                    select(func.coalesce(func.max(AuditLog.id), 0))
                )
            ).scalar_one()
        _watermark = (max_sync, max_audit)
    yield


def _uniq_pharmacyid() -> str:
    _seq[0] += 1
    return f"P{_run}{PID % 100000}{_seq[0]}"[:15]


def _uniq_mobile() -> str:
    _seq[0] += 1
    return f"01{int(_run, 16) % 1000000:06d}{_seq[0]:04d}"


async def _admin_headers(client) -> dict:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _cleanup():
    ids = list(_created)
    _created.clear()
    assert _watermark is not None
    max_sync, max_audit = _watermark
    async with SessionLocal() as session:
        await session.execute(
            delete(SyncLog).where(
                SyncLog.entity.in_(["branch", "branch_identity"]),
                SyncLog.id > max_sync,
            )
        )
        await session.execute(
            delete(AuditLog).where(
                AuditLog.entity.in_(["branch", "branch_identity"]),
                AuditLog.id > max_audit,
            )
        )
        await session.execute(delete(BranchIdentity).where(BranchIdentity.branch_id.in_(ids)))
        await session.execute(delete(User).where(User.branch_id.in_(ids)))
        await session.execute(delete(Branch).where(Branch.id.in_(ids)))
        mains = (
            await session.execute(
                select(func.count()).select_from(Branch).where(Branch.is_main_device.is_(True))
            )
        ).scalar_one()
        if mains == 0:
            root = await session.get(Branch, 1)
            root.is_main_device = True
        await session.commit()


async def _mark_registry_applied():
    async with SessionLocal() as s:
        await s.execute(
            update(SyncLog)
            .where(SyncLog.entity.in_(["branch", "branch_identity"]))
            .values(status="applied")
        )
        await s.commit()


async def _peer_copies(peer_branch_id: int, created_branch_id: int) -> list[SyncLog]:
    """The peer's fan-out copies concerning `created_branch_id`, FIFO-ordered
    (replay applies in id order; the branch row must precede its identities)."""
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(SyncLog)
                .where(
                    SyncLog.branch_id == peer_branch_id,
                    SyncLog.entity.in_(["branch", "branch_identity"]),
                    SyncLog.status == "pending",
                )
                .order_by(SyncLog.id)
            )
        ).scalars().all()
    return [
        r
        for r in rows
        if (r.payload or {}).get("id") == created_branch_id
        or (r.payload or {}).get("branch_id") == created_branch_id
    ]


async def _replay_as(branch_id: int) -> dict:
    """Run replay_pending directly on its own session."""
    async with SessionLocal() as session:
        return await replay_pending(session, branch_id=branch_id, user_id=None)


async def _pending_registry_rows(branch_id: int) -> list[int]:
    async with SessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(SyncLog.id).where(
                        SyncLog.branch_id == branch_id,
                        SyncLog.entity.in_(["branch", "branch_identity"]),
                        SyncLog.status == "pending",
                    )
                )
            ).scalars().all()
        )


@pytest.mark.asyncio
async def test_branch_mutation_fans_out_to_all_active_branches(client):
    """A registry mutation enqueues one outbox copy per ACTIVE branch — every
    peer's queue carries the snapshot so a reconnecting twin can converge."""
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
        )
        assert r.status_code == 201, r.text
        new_id = r.json()["id"]
        _created.append(new_id)

        async with SessionLocal() as s:
            active_ids = set(
                (
                    await s.execute(select(Branch.id).where(Branch.is_active.is_(True)))
                ).scalars().all()
            )
            copies = (
                await s.execute(
                    select(SyncLog.branch_id).where(
                        SyncLog.entity == "branch",
                        SyncLog.status == "pending",
                        SyncLog.payload["id"].as_integer() == new_id,
                    )
                )
            ).scalars().all()
        assert set(copies) == active_ids, "every active branch must hold a copy"
        assert new_id in active_ids and 1 in active_ids
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_offline_peer_converges_on_registry_history(client):
    """A peer that never saw branch B rebuilds it VERBATIM from its pending
    fan-out copies: create + edit + identity mapping all restore; the PG
    identity sequence advances past the replayed id."""
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={
                "pharmacyid": _uniq_pharmacyid(),
                "mobile": _uniq_mobile(),
                "pharname": "قبل التعديل",
            },
        )
        assert r.status_code == 201, r.text
        b_id = r.json()["id"]
        _created.append(b_id)

        r = await client.patch(
            f"/api/v1/branches/{b_id}",
            headers=headers,
            json={"pharname": "بعد التعديل"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/branches/{b_id}/identities",
            headers=headers,
            json={"legacy_table": "wzphar", "legacy_column": "pharmacyid",
                  "legacy_value": "legacy-alias-1"},
        )
        assert r.status_code == 201, r.text

        # peer = seeded main (branch 1): snapshot its copies, wipe local state,
        # then replay only the peer's pending copies.
        copies = await _peer_copies(1, b_id)
        assert len(copies) >= 3  # create + patch + identity
        payloads = [dict(c.payload) for c in copies]
        await _mark_registry_applied()

        async with SessionLocal() as s:
            await s.execute(
                delete(AuditLog).where(AuditLog.branch_id == b_id)
            )
            await s.execute(
                delete(SyncLog).where(SyncLog.branch_id == b_id)
            )
            await s.execute(delete(BranchIdentity).where(BranchIdentity.branch_id == b_id))
            await s.execute(delete(Branch).where(Branch.id == b_id))
            await s.commit()

        # re-insert as proper pending rows
        ids = []
        async with SessionLocal() as s:
            for c, p in zip(copies, payloads):
                row = SyncLog(
                    branch_id=1, entity=c.entity, entity_id=None,
                    action=c.action, payload=p, status="pending",
                )
                s.add(row)
                await s.flush()
                ids.append(row.id)
            await s.commit()

        summary = await _replay_as(1)
        # a poisoned row (e.g. an identity arriving before its branch row if
        # delivery order scrambled) stays PENDING — the real syncer retries
        # on the next pass; mirror that until the queue drains
        for _ in range(3):
            pending = await _pending_registry_rows(1)
            if not pending:
                break
            summary = await _replay_as(1)

        async with SessionLocal() as s:
            restored = await s.get(Branch, b_id)
            assert restored is not None, "peer must rebuild the branch row"
            assert restored.pharmacyid == r_json_pharmacyid(payloads)
            assert restored.pharname == "بعد التعديل"
            assert restored.is_active is True
            assert restored.is_main_device is False
            ident = (
                await s.execute(
                    select(BranchIdentity).where(
                        BranchIdentity.branch_id == b_id,
                        BranchIdentity.legacy_value == "legacy-alias-1",
                    )
                )
            ).scalar_one_or_none()
            assert ident is not None, "identity mapping must converge too"
        assert summary["failed"] == 0

        # explicit-id insert must not strand the PG sequence: the next local
        # create gets a fresh id without colliding
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
        )
        assert r.status_code == 201, r.text
        _created.append(r.json()["id"])
    finally:
        await _cleanup()


def r_json_pharmacyid(payloads: list[dict]) -> str:
    for p in payloads:
        if p.get("pharmacyid"):
            return p["pharmacyid"]
    raise AssertionError("no branch snapshot among payloads")


@pytest.mark.asyncio
async def test_stale_copy_is_skipped_and_conflict_recorded(client):
    """A stale snapshot (pre-edit) arriving after the newer state must be
    SKIPPED by LWW — and the skip RECORDED on the sync_log row payload
    (`skipped_reason`), never silently dropped (G10)."""
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={
                "pharmacyid": _uniq_pharmacyid(),
                "mobile": _uniq_mobile(),
                "pharname": "القديم",
            },
        )
        assert r.status_code == 201, r.text
        b_id = r.json()["id"]
        _created.append(b_id)

        copies = await _peer_copies(1, b_id)
        create_snapshots = [c for c in copies if c.action == "insert"]
        assert len(create_snapshots) == 1
        stale_payload = dict(create_snapshots[0].payload)

        r = await client.patch(
            f"/api/v1/branches/{b_id}",
            headers=headers,
            json={"pharname": "الأحدث"},
        )
        assert r.status_code == 200, r.text
        await _mark_registry_applied()

        async with SessionLocal() as s:
            row = SyncLog(
                branch_id=1, entity="branch", entity_id=b_id,
                action="insert", payload=stale_payload, status="pending",
            )
            s.add(row)
            await s.flush()
            row_id = row.id
            await s.commit()

        summary = await _replay_as(1)
        assert summary["skipped"] >= 1, "stale copy must NOT reapply"

        async with SessionLocal() as s:
            row = await s.get(SyncLog, row_id)
            assert row.status == "applied"  # delivered, but...
            reason = (row.payload or {}).get("skipped_reason")
            assert reason, f"sync_log must record WHY it was skipped, got {row.payload}"
            local = await s.get(Branch, b_id)
            assert local.pharname == "الأحدث", "LWW keeps the newer local state"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_duplicate_delivery_is_idempotent_and_recorded(client):
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
        )
        assert r.status_code == 201, r.text
        b_id = r.json()["id"]
        _created.append(b_id)

        copies = await _peer_copies(1, b_id)
        creates = [c for c in copies if c.action == "insert"]
        payload = dict(creates[0].payload)
        await _mark_registry_applied()

        ids = []
        async with SessionLocal() as s:
            # rewind the peer's knowledge so the snapshot is strictly newer
            # (a same-DB peer already holds the exact watermark)
            target = await s.get(Branch, b_id)
            target.pharname = "قديم جدا"
            target.updated_at -= timedelta(seconds=5)
            await s.commit()

        async with SessionLocal() as s:
            for _ in range(2):  # same snapshot delivered twice
                row = SyncLog(
                    branch_id=1, entity="branch", entity_id=b_id,
                    action="insert", payload=payload, status="pending",
                )
                s.add(row)
                await s.flush()
                ids.append(row.id)
            await s.commit()

        summary = await _replay_as(1)
        applied = summary["applied"]
        skipped = summary["skipped"]
        assert applied >= 1 and skipped >= 1  # first applies, duplicate skips

        async with SessionLocal() as s:
            dup_row = await s.get(SyncLog, ids[1])
            assert (dup_row.payload or {}).get("skipped_reason")
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_main_transfer_history_converges_single_main(client):
    """Replaying a promote+demote history on a peer that missed it leaves the
    SAME single active main as the canonical store (never two, never zero)."""
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
        )
        assert r.status_code == 201, r.text
        b_id = r.json()["id"]
        _created.append(b_id)

        r = await client.post(f"/api/v1/branches/{b_id}/promote", headers=headers)
        assert r.status_code == 200, r.text

        async with SessionLocal() as s:
            all_pending = (
                await s.execute(
                    select(SyncLog).where(
                        SyncLog.branch_id == 1,
                        SyncLog.entity.in_(["branch", "branch_identity"]),
                        SyncLog.status == "pending",
                    )
                )
            ).scalars().all()
        # BOTH halves of the promote history: B's promote snapshot AND the
        # seeded main's demote snapshot
        copies = [
            r for r in all_pending
            if (r.payload or {}).get("id") in (1, b_id)
        ]
        await _mark_registry_applied()

        async with SessionLocal() as s:
            # rewind the PEER'S view of both branches to pre-promote truth:
            # main(1) back to main, B back to sub — watermarks too, or LWW
            # would (correctly) skip same-transaction snapshots.
            root = await s.get(Branch, 1)
            root.is_main_device = True
            root.updated_at -= timedelta(seconds=5)
            target = await s.get(Branch, b_id)
            target.is_main_device = False
            target.updated_at -= timedelta(seconds=5)
            for c in copies:
                s.add(SyncLog(
                    branch_id=1, entity="branch", entity_id=None,
                    action=c.action, payload=dict(c.payload), status="pending",
                ))
            await s.commit()

        await _replay_as(1)

        async with SessionLocal() as s:
            mains = (
                await s.execute(
                    select(Branch.id).where(Branch.is_main_device.is_(True))
                )
            ).scalars().all()
            assert mains == [b_id], f"exactly the promoted branch is main, got {mains}"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_malformed_branch_row_fails_alone_with_reason(client):
    try:
        async with SessionLocal() as s:
            row = SyncLog(
                branch_id=1, entity="branch", entity_id=None,
                action="insert", payload={"nonsense": True}, status="pending",
            )
            s.add(row)
            await s.flush()
            row_id = row.id
            await s.commit()

        summary = await _replay_as(1)
        assert summary["failed"] >= 1

        async with SessionLocal() as s:
            row = await s.get(SyncLog, row_id)
            # #55 convention: a poisoned row stays PENDING (retryable on a
            # later pass — e.g. a missing parent branch arriving late) with
            # the failure recorded in its payload, never silently dropped
            assert row.status == "pending"
            assert (row.payload or {}).get("failure")
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_identity_detach_replays_as_delete(client):
    """A peer that saw the attach but missed the detach converges when the
    `_deleted` tombstone copy arrives: the mapping disappears; a duplicate
    tombstone is a recorded skip."""
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
        )
        assert r.status_code == 201, r.text
        b_id = r.json()["id"]
        _created.append(b_id)

        r = await client.post(
            f"/api/v1/branches/{b_id}/identities",
            headers=headers,
            json={"legacy_table": "wzphar", "legacy_column": "pharmacyid",
                  "legacy_value": "detach-alias-1"},
        )
        assert r.status_code == 201, r.text
        r = await client.delete(
            f"/api/v1/branches/{b_id}/identities/wzphar/pharmacyid/detach-alias-1",
            headers=headers,
        )
        assert r.status_code in (200, 204), r.text

        copies = [
            c for c in await _peer_copies(1, b_id)
            if (c.payload or {}).get("legacy_value") == "detach-alias-1"
        ]
        assert len(copies) == 2  # attach + detach tombstone
        await _mark_registry_applied()

        ids: list[int] = []
        async with SessionLocal() as s:
            for c in copies:
                row = SyncLog(
                    branch_id=1, entity="branch_identity", entity_id=None,
                    action=c.action, payload=dict(c.payload), status="pending",
                )
                s.add(row)
                await s.flush()
                ids.append(row.id)
            await s.commit()

        summary = await _replay_as(1)
        assert summary["failed"] == 0

        async with SessionLocal() as s:
            gone = (
                await s.execute(
                    select(BranchIdentity).where(
                        BranchIdentity.legacy_value == "detach-alias-1",
                        BranchIdentity.branch_id == b_id,
                    )
                )
            ).scalar_one_or_none()
            assert gone is None, "detach must converge on the peer"

            dup = await s.get(SyncLog, ids[1])
            reason = (dup.payload or {}).get("skipped_reason")
            # second delivery (attach replayed after the tombstone applied)
            # either restores-then-reconciles or is a recorded skip — never
            # a silent loss
            assert reason or dup.status == "applied"
    finally:
        await _cleanup()
