"""Branch registry + main/sub device roles (ticket #31, S5.1).

Core `branches` registry CRUD, the single-main-device invariant (legacy
ismaster.txt), the branch_identities alias map (legacy phar/pharmacyid/mobile
→ one canonical branch id), and G12 atomicity of audit + sync-outbox rows.

Cleanup uses an ID watermark captured on first use: a promote DEMOTES the
seeded main branch (id 1) and writes its audit/outbox rows against branch_id=1,
so row cleanup cannot be scoped by created branch ids alone.
"""
import os

import pytest
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal
from app.models import AuditLog, Branch, BranchIdentity, SyncLog, User

PID = os.getpid()
_seq = [0]
_watermark: tuple[int, int] | None = None  # (max sync_log.id, max audit_log.id)


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
    return f"P{PID % 100000}{_seq[0]}"


def _uniq_mobile() -> str:
    _seq[0] += 1
    return f"01{PID % 10_000_000}{_seq[0]:04d}"[:14]


_created: list[int] = []
_created_usernames: list[str] = []


async def _admin_headers(client) -> dict:
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _cleanup():
    if not _created and not _created_usernames:
        return
    ids, usernames = list(_created), list(_created_usernames)
    _created.clear()
    _created_usernames.clear()
    assert _watermark is not None
    max_sync, max_audit = _watermark
    async with SessionLocal() as session:
        # every outbox/audit row this file wrote — including rows stamped with
        # branch_id=1 when a promote demoted the seeded main — dies with us so
        # later suites scanning branch-1 outbox rows see only their own data.
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
        await session.execute(
            delete(BranchIdentity).where(BranchIdentity.branch_id.in_(ids))
        )
        await session.execute(delete(Branch).where(Branch.id.in_(ids)))
        if usernames:
            await session.execute(
                delete(User).where(User.username.in_(usernames))
            )
        # restore the single-main invariant: deleting a branch that had been
        # promoted must never leave the install without its main device.
        mains = (
            await session.execute(
                select(func.count())
                .select_from(Branch)
                .where(Branch.is_main_device.is_(True))
            )
        ).scalar_one()
        if mains == 0:
            root = await session.get(Branch, 1)
            assert root is not None
            root.is_main_device = True
        await session.commit()


async def test_admin_creates_sub_branch(client):
    try:
        headers = await _admin_headers(client)
        r = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={
                "pharmacyid": _uniq_pharmacyid(),
                "mobile": _uniq_mobile(),
                "pharname": "صيدلية النيل",
                "governorate": "القاهرة",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        _created.append(body["id"])
        assert body["pharname"] == "صيدلية النيل"
        assert body["role"] == "sub"
        assert body["active"] is True
    finally:
        await _cleanup()


async def test_list_branches_reports_main_role(client):
    """The seeded install branch is THE main device; a new one is a sub."""
    headers = await _admin_headers(client)
    create = await client.post(
        "/api/v1/branches",
        headers=headers,
        json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
    )
    assert create.status_code == 201, create.text
    sub_id = create.json()["id"]
    _created.append(sub_id)
    try:
        r = await client.get("/api/v1/branches", headers=headers)
        assert r.status_code == 200, r.text
        branches = {b["id"]: b for b in r.json()["branches"]}
        mains = [b for b in branches.values() if b["role"] == "main"]
        assert len(mains) == 1, mains
        assert mains[0]["is_main_device"] is True
        assert branches[sub_id]["role"] == "sub"
    finally:
        await _cleanup()


async def _create_sub(client) -> dict:
    headers = await _admin_headers(client)
    r = await client.post(
        "/api/v1/branches",
        headers=headers,
        json={"pharmacyid": _uniq_pharmacyid(), "mobile": _uniq_mobile()},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    _created.append(body["id"])
    return body


async def test_patch_edits_branch_fields(client):
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        r = await client.patch(
            f"/api/v1/branches/{sub['id']}",
            headers=headers,
            json={"pharname": "صيدلية الأمير", "governorate": "الجيزة"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pharname"] == "صيدلية الأمير"
        assert body["governorate"] == "الجيزة"
        assert body["pharmacyid"] == sub["pharmacyid"]
    finally:
        await _cleanup()


async def test_deactivate_sub_branch_is_soft(client):
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        r = await client.delete(f"/api/v1/branches/{sub['id']}", headers=headers)
        assert r.status_code == 200, r.text
        listing = await client.get("/api/v1/branches", headers=headers)
        rows = {b["id"]: b for b in listing.json()["branches"]}
        assert rows[sub["id"]]["active"] is False

        # double-delete is an idempotent no-op: no second audit/outbox row
        from sqlalchemy import func, select

        async with SessionLocal() as session:
            before = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.entity == "branch", AuditLog.entity_id == sub["id"])
                )
            ).scalar_one()
        again = await client.delete(f"/api/v1/branches/{sub['id']}", headers=headers)
        assert again.status_code == 200
        async with SessionLocal() as session:
            after = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.entity == "branch", AuditLog.entity_id == sub["id"])
                )
            ).scalar_one()
        assert after == before
    finally:
        await _cleanup()


async def test_cannot_deactivate_the_main_device(client):
    """The main device anchors numbering/sync — transfer first, never delete."""
    headers = await _admin_headers(client)
    listing = await client.get("/api/v1/branches", headers=headers)
    main = next(b for b in listing.json()["branches"] if b["role"] == "main")
    r = await client.delete(f"/api/v1/branches/{main['id']}", headers=headers)
    assert r.status_code == 409, r.text


async def test_promote_transfers_main_role_atomically(client):
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        listing = await client.get("/api/v1/branches", headers=headers)
        old_main_id = next(
            b["id"] for b in listing.json()["branches"] if b["role"] == "main"
        )
        r = await client.post(f"/api/v1/branches/{sub['id']}/promote", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "main"
        after = {
            b["id"]: b
            for b in (await client.get("/api/v1/branches", headers=headers)).json()[
                "branches"
            ]
        }
        assert after[sub["id"]]["role"] == "main"
        assert after[old_main_id]["role"] == "sub"
        mains = [b for b in after.values() if b["role"] == "main"]
        assert len(mains) == 1
    finally:
        await _cleanup()


async def test_promote_requires_legacy_floor_7(client):
    """Moving the main device is owner-tier: a level-6 manager grant is not enough."""
    import uuid

    try:
        sub = await _create_sub(client)
        admin_headers = await _admin_headers(client)
        weak = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "username": f"mgr{uuid.uuid4().hex[:8]}",
                "permission_level": 6,
                "initial_password": "weak-pass-1",
            },
        )
        assert weak.status_code == 201, weak.text
        _created_usernames.append(weak.json()["username"])
        weak_token = (
            await client.post(
                "/api/v1/auth/login",
                json={
                    "username": weak.json()["username"],
                    "password": "weak-pass-1",
                },
            )
        ).json()["access_token"]
        r = await client.post(
            f"/api/v1/branches/{sub['id']}/promote",
            headers={"Authorization": f"Bearer {weak_token}"},
        )
        assert r.status_code == 403, r.text
        listing = await client.get("/api/v1/branches", headers=admin_headers)
        after = {b["id"]: b for b in listing.json()["branches"]}
        assert after[sub["id"]]["role"] == "sub"
    finally:
        await _cleanup()


async def test_identity_attach_list_detach(client):
    """The alias map: a legacy (table, column, value) triple pins to ONE branch."""
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        r = await client.post(
            f"/api/v1/branches/{sub['id']}/identities",
            headers=headers,
            json={
                "legacy_table": "wzphar",
                "legacy_column": "pharmacyid",
                "legacy_value": sub["pharmacyid"],
            },
        )
        assert r.status_code == 201, r.text
        listed = await client.get(
            f"/api/v1/branches/{sub['id']}/identities", headers=headers
        )
        assert listed.status_code == 200, listed.text
        rows = listed.json()["identities"]
        assert len(rows) == 1
        assert rows[0]["branch_id"] == sub["id"]
        assert rows[0]["legacy_value"] == sub["pharmacyid"]

        # resolver: the seam #34/#35 replay will call
        from app.branches.service import resolve_branch
        from app.core.db import SessionLocal

        async with SessionLocal() as session:
            resolved = await resolve_branch(
                session,
                legacy_table="wzphar",
                legacy_column="pharmacyid",
                legacy_value=sub["pharmacyid"],
            )
            assert resolved is not None
            assert resolved.id == sub["id"]

        det = await client.delete(
            f"/api/v1/branches/{sub['id']}/identities/"
            f"wzphar/pharmacyid/{sub['pharmacyid']}",
            headers=headers,
        )
        assert det.status_code == 200, det.text
        # same convention as branch DELETE: echo the removed row
        assert det.json()["legacy_value"] == sub["pharmacyid"]
        listed = await client.get(
            f"/api/v1/branches/{sub['id']}/identities", headers=headers
        )
        assert listed.json()["identities"] == []
    finally:
        await _cleanup()


async def test_resolver_normalizes_like_attach(client):
    """resolve_branch must strip exactly like attach_identity — a raw caller
    value from the ETL can never silently miss a stored mapping."""
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        attached = await client.post(
            f"/api/v1/branches/{sub['id']}/identities",
            headers=headers,
            json={
                "legacy_table": "wzphar",
                "legacy_column": "pharmacyid",
                "legacy_value": f"  {sub['pharmacyid']} ",
            },
        )
        assert attached.status_code == 201, attached.text
        # stored stripped; raw lookup with whitespace must still hit
        from app.branches.service import resolve_branch
        from app.core.db import SessionLocal

        async with SessionLocal() as session:
            resolved = await resolve_branch(
                session,
                legacy_table=" wzphar ",
                legacy_column=" pharmacyid ",
                legacy_value=f" {sub['pharmacyid']} ",
            )
            assert resolved is not None
            assert resolved.id == sub["id"]
    finally:
        await _cleanup()


async def test_inactive_branch_accepts_metadata_edits(client):
    """Documented intent: soft-deleted branches keep their identity rows and
    remain editable — deactivation hides them from ops, it does not freeze
    their record (no un-delete endpoint exists yet)."""
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        assert (
            await client.delete(f"/api/v1/branches/{sub['id']}", headers=headers)
        ).status_code == 200
        r = await client.patch(
            f"/api/v1/branches/{sub['id']}",
            headers=headers,
            json={"pharname": "مؤرشفة"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["active"] is False
        assert r.json()["pharname"] == "مؤرشفة"
    finally:
        await _cleanup()


async def test_identity_duplicate_triple_conflicts(client):
    try:
        sub = await _create_sub(client)
        other = await _create_sub(client)
        headers = await _admin_headers(client)
        identity = {
            "legacy_table": "titanksastock",
            "legacy_column": "mobile",
            "legacy_value": sub["pharmacyid"],
        }
        first = await client.post(
            f"/api/v1/branches/{sub['id']}/identities",
            headers=headers,
            json=identity,
        )
        assert first.status_code == 201, first.text
        dup = await client.post(
            f"/api/v1/branches/{other['id']}/identities",
            headers=headers,
            json=identity,
        )
        assert dup.status_code == 409, dup.text
    finally:
        await _cleanup()


async def test_writes_need_branches_manage_reads_open_to_authenticated(client):
    """A cashier (floor 1, no manage grant) can list branches but never mutate."""
    import uuid

    try:
        cashier_username = f"cash{uuid.uuid4().hex[:8]}"
        _created_usernames.append(cashier_username)
        admin_headers = await _admin_headers(client)
        made = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "username": cashier_username,
                "permission_level": 1,
                "initial_password": "weak-pass-1",
            },
        )
        assert made.status_code == 201, made.text
        cashier_token = (
            await client.post(
                "/api/v1/auth/login",
                json={"username": cashier_username, "password": "weak-pass-1"},
            )
        ).json()["access_token"]
        cash_headers = {"Authorization": f"Bearer {cashier_token}"}

        # reads are open to any authenticated user
        assert (
            await client.get("/api/v1/branches", headers=cash_headers)
        ).status_code == 200

        # every write is gated by branches.manage
        assert (
            await client.post(
                "/api/v1/branches",
                headers=cash_headers,
                json={"pharmacyid": "x", "mobile": "y"},
            )
        ).status_code == 403

        sub = await _create_sub(client)
        assert (
            await client.patch(
                f"/api/v1/branches/{sub['id']}",
                headers=cash_headers,
                json={"pharname": "nope"},
            )
        ).status_code == 403
        assert (
            await client.delete(f"/api/v1/branches/{sub['id']}", headers=cash_headers)
        ).status_code == 403
        assert (
            await client.post(
                f"/api/v1/branches/{sub['id']}/promote", headers=cash_headers
            )
        ).status_code == 403

        # unauthenticated is rejected outright
        assert (await client.get("/api/v1/branches")).status_code == 401
    finally:
        await _cleanup()


async def test_mutations_write_audit_and_outbox_atomically(client):
    """G12: every branch mutation lands its audit_log + sync_log rows in the
    same transaction — the chain consumer (#34) finds intent already queued."""
    from sqlalchemy import select

    try:
        headers = await _admin_headers(client)
        sub = await _create_sub(client)

        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity == "branch",
                        AuditLog.entity_id == sub["id"],
                    )
                )
            ).scalars().all()
            assert len(audits) == 1, audits
            assert audits[0].action == "insert"

            syncs = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "branch",
                        SyncLog.entity_id == sub["id"],
                    )
                )
            ).scalars().all()
            assert len(syncs) == 1, syncs
            payload = syncs[0].payload
            assert payload["pharmacyid"] == sub["pharmacyid"]
            assert payload["role"] == "sub"

        # a second mutation (deactivate) appends its own audit+outbox rows
        await client.delete(f"/api/v1/branches/{sub['id']}", headers=headers)
        async with SessionLocal() as session:
            audits = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity == "branch",
                        AuditLog.entity_id == sub["id"],
                    )
                )
            ).scalars().all()
            assert [a.action for a in audits] == ["insert", "delete"]
            syncs = (
                await session.execute(
                    select(SyncLog).where(
                        SyncLog.entity == "branch",
                        SyncLog.entity_id == sub["id"],
                    )
                )
            ).scalars().all()
            assert len(syncs) == 2
    finally:
        await _cleanup()


# --- edge cases (AGENTS.md edge-case pass, ticket #31) ---


async def test_duplicate_pharmacyid_or_mobile_conflict(client):
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        dup_pid = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": sub["pharmacyid"], "mobile": _uniq_mobile()},
        )
        assert dup_pid.status_code == 409
        # the conflict message names the actual key (scenario-QA feedback)
        assert "pharmacyid" in dup_pid.text and "mobile" not in (
            dup_pid.json()["detail"].replace("pharmacyid or mobile", "")
        )
        dup_mob = await client.post(
            "/api/v1/branches",
            headers=headers,
            json={"pharmacyid": _uniq_pharmacyid(), "mobile": sub["mobile"]},
        )
        assert dup_mob.status_code == 409
        assert "mobile already exists" in dup_mob.json()["detail"]
    finally:
        await _cleanup()


async def test_active_filter_for_picker_screens(client):
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        assert (
            await client.delete(f"/api/v1/branches/{sub['id']}", headers=headers)
        ).status_code == 200
        only_active = await client.get(
            "/api/v1/branches", headers=headers, params={"active": "true"}
        )
        assert all(b["active"] for b in only_active.json()["branches"])
        assert sub["id"] not in {b["id"] for b in only_active.json()["branches"]}
        only_inactive = await client.get(
            "/api/v1/branches", headers=headers, params={"active": "false"}
        )
        inactive = only_inactive.json()["branches"]
        assert [b["id"] for b in inactive] == [sub["id"]]
        everything = await client.get("/api/v1/branches", headers=headers)
        assert len(everything.json()["branches"]) == len(
            only_active.json()["branches"]
        ) + len(inactive)
    finally:
        await _cleanup()


async def test_blank_and_oversized_natural_keys_rejected(client):
    headers = await _admin_headers(client)
    blank = await client.post(
        "/api/v1/branches",
        headers=headers,
        json={"pharmacyid": "   ", "mobile": "0100"},
    )
    assert blank.status_code == 400
    long_pid = await client.post(
        "/api/v1/branches",
        headers=headers,
        json={"pharmacyid": "x" * 16, "mobile": "0100"},
    )
    assert long_pid.status_code == 400
    # pydantic length caps surface as 400 (plan/02 §2 validation rule)
    cap = await client.post(
        "/api/v1/branches",
        headers=headers,
        json={"pharmacyid": "ok", "mobile": "y" * 16},
    )
    assert cap.status_code == 400


async def test_unknown_branch_ids_are_404(client):
    headers = await _admin_headers(client)
    assert (
        await client.patch("/api/v1/branches/999999", headers=headers, json={})
    ).status_code == 404
    assert (await client.delete("/api/v1/branches/999999", headers=headers)).status_code == 404
    assert (
        await client.post("/api/v1/branches/999999/promote", headers=headers)
    ).status_code == 404
    assert (
        await client.get("/api/v1/branches/999999/identities", headers=headers)
    ).status_code == 404


async def test_detach_unknown_identity_is_404(client):
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        r = await client.delete(
            f"/api/v1/branches/{sub['id']}/identities/wzphar/pharmacyid/nope",
            headers=headers,
        )
        assert r.status_code == 404
    finally:
        await _cleanup()


async def test_promote_is_idempotent_and_patch_noop_writes_nothing(client):
    """Replay safety: promoting the current main twice changes nothing;
    an empty PATCH writes no audit/outbox rows."""
    from sqlalchemy import func, select

    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        first = await client.post(
            f"/api/v1/branches/{sub['id']}/promote", headers=headers
        )
        assert first.status_code == 200

        async with SessionLocal() as session:
            before_audits = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.entity == "branch", AuditLog.entity_id == sub["id"])
                )
            ).scalar_one()

        second = await client.post(
            f"/api/v1/branches/{sub['id']}/promote", headers=headers
        )
        assert second.status_code == 200

        async with SessionLocal() as session:
            after_audits = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.entity == "branch", AuditLog.entity_id == sub["id"])
                )
            ).scalar_one()
        assert after_audits == before_audits  # replay wrote nothing

        noop = await client.patch(
            f"/api/v1/branches/{sub['id']}",
            headers=headers,
            json={"pharname": None},
        )
        assert noop.status_code == 200
        async with SessionLocal() as session:
            final_audits = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.entity == "branch", AuditLog.entity_id == sub["id"])
                )
            ).scalar_one()
        assert final_audits == after_audits
    finally:
        await _cleanup()


async def test_concurrent_promotes_leave_exactly_one_main(client):
    import asyncio

    try:
        a = await _create_sub(client)
        b = await _create_sub(client)
        c = await _create_sub(client)
        headers = await _admin_headers(client)
        results = await asyncio.gather(
            client.post(f"/api/v1/branches/{a['id']}/promote", headers=headers),
            client.post(f"/api/v1/branches/{b['id']}/promote", headers=headers),
            client.post(f"/api/v1/branches/{c['id']}/promote", headers=headers),
            return_exceptions=True,
        )
        statuses = [
            r.status_code for r in results if not isinstance(r, BaseException)
        ]
        assert all(s == 200 for s in statuses), results
        listing = await client.get("/api/v1/branches", headers=headers)
        mains = [
            x for x in listing.json()["branches"] if x["role"] == "main"
        ]
        assert len(mains) == 1, mains
        assert mains[0]["id"] in {a["id"], b["id"], c["id"]}
    finally:
        await _cleanup()


async def test_inactive_branch_stays_resolvable_via_identity(client):
    """Historical rows must keep mapping to their origin branch even after it
    is deactivated — resolution returns it; callers decide policy."""
    try:
        sub = await _create_sub(client)
        headers = await _admin_headers(client)
        attached = await client.post(
            f"/api/v1/branches/{sub['id']}/identities",
            headers=headers,
            json={
                "legacy_table": "wzphar",
                "legacy_column": "mobile",
                "legacy_value": sub["mobile"],
            },
        )
        assert attached.status_code == 201
        assert (
            await client.delete(f"/api/v1/branches/{sub['id']}", headers=headers)
        ).status_code == 200

        from app.branches.service import resolve_branch
        from app.core.db import SessionLocal

        async with SessionLocal() as session:
            resolved = await resolve_branch(
                session,
                legacy_table="wzphar",
                legacy_column="mobile",
                legacy_value=sub["mobile"],
            )
            assert resolved is not None
            assert resolved.id == sub["id"]
            assert resolved.is_active is False
    finally:
        await _cleanup()
