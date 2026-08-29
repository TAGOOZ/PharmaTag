"""G10 sync conflict panel — LWW auto-resolve + non-destructive UI (#60).

Tests: LWW duplicate replay no-op, equal-rev skip, poison row stays pending,
out-of-order fold-forward, auth/cross-branch, parity_check.

Writes already record conflicts in sync_log (skipped_reason) and
branch_stock/transfer rev watermarks; this panel surfaces the loss and allows
manager restore (reapply loser as new rev with audit, never mutating history
in place).
"""
import os
import secrets

import pytest
from sqlalchemy import delete, select, text

from app.core.db import SessionLocal
from app.models import AuditLog, Branch, BranchStock, Drug, StockBatch, SyncLog, Transfer, TransferLine, User
from app.sync.service import replay_pending
from app.sync.conflicts import list_conflicts

PID = os.getpid()
_run = secrets.token_hex(3)
_seq = [0]

def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"T60_{_run}_{PID}_{tag}_{_seq[0]}"

async def _admin_headers(client) -> dict:
    login = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}

async def _make_branch() -> int:
    _seq[0] += 1
    async with SessionLocal() as s:
        b = Branch(
            pharmacyid=f"60{_run}{PID%1000}{_seq[0]}"[:15],
            phar="",
            mobile=f"01{int(_run,16)%1_000_000:06d}{PID%100:02d}{_seq[0]:04d}"[:14],
            pharname=_uniq("branch"),
            is_active=True,
        )
        s.add(b)
        await s.flush()
        bid = b.id
        await s.commit()
        return bid

async def _make_user(username: str, level: int, branch_id: int) -> int:
    from app.auth.security import hash_password
    async with SessionLocal() as s:
        u = User(username=username, pass_hash=hash_password("pw123456"), permission_level=level, branch_id=branch_id, active=True)
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
        return uid

async def _make_drug_with_stock(branch_id: int) -> int:
    from decimal import Decimal
    from datetime import date
    async with SessionLocal() as s:
        d = Drug(drugname=_uniq("drug"), tax_type="14%", price=Decimal("10.0000"))
        s.add(d)
        await s.flush()
        did = d.id
        s.add(BranchStock(branch_id=branch_id, drug_id=did, qty=Decimal("20.0000"), minimum=Decimal("0")))
        s.add(StockBatch(branch_id=branch_id, drug_id=did, randomid=_uniq("batch"), qty=Decimal("10.0000"), cost=Decimal("5.0000")))
        s.add(StockBatch(branch_id=branch_id, drug_id=did, randomid=_uniq("batch2"), qty=Decimal("10.0000"), cost=Decimal("5.0000")))
        await s.commit()
        return did

async def _cleanup(branches, users, drugs, sync_ids):
    async with SessionLocal() as s:
        if sync_ids:
            await s.execute(delete(SyncLog).where(SyncLog.id.in_(sync_ids)))
        # transfers: delete lines by drug first, then headers
        for did in drugs:
            await s.execute(delete(TransferLine).where(TransferLine.drug_id == did))
        await s.execute(delete(Transfer).where(Transfer.source_branch_id.in_(branches)))
        await s.execute(delete(Transfer).where(Transfer.target_branch_id.in_(branches)))
        await s.execute(delete(SyncLog).where(SyncLog.branch_id.in_(branches)))
        await s.execute(delete(AuditLog).where(AuditLog.branch_id.in_(branches)))
        await s.execute(delete(AuditLog).where(AuditLog.user_id.in_(users)))
        for did in drugs:
            await s.execute(delete(StockBatch).where(StockBatch.drug_id == did))
            await s.execute(delete(BranchStock).where(BranchStock.drug_id == did))
            await s.execute(delete(Drug).where(Drug.id == did))
        await s.execute(delete(User).where(User.id.in_(users)))
        await s.execute(delete(Branch).where(Branch.id.in_(branches)))
        await s.commit()

async def _transfer_ids(branches):
    async with SessionLocal() as s:
        rows = (await s.execute(select(Transfer.id).where(Transfer.source_branch_id.in_(branches)))).scalars().all()
        return list(rows)

@pytest.mark.asyncio
async def test_lww_duplicate_replay_noop_and_listed_as_conflict(client):
    """Duplicate delivery (same rev) is idempotent no-op and appears as LWW loss."""
    branch = await _make_branch()
    other = await _make_branch()
    user_admin = await _make_user(_uniq("admin"), 9, branch)
    drug = await _make_drug_with_stock(branch)
    sync_ids = []
    try:
        headers = await _admin_headers(client)
        # create transfer via API
        r = await client.post(
            "/api/v1/transfers",
            headers=headers,
            json={"source_branch_id": branch, "target_branch_id": other, "lines": [{"drug_id": drug, "qty": "5"}]},
        )
        # if we used admin's branch is 1, not our new branch; create via direct service instead?
        # Instead, create transfer directly via service using user_admin
        from app.transfers.service import create_draft
        from app.models import User as UserM
        async with SessionLocal() as s:
            caller = await s.get(UserM, user_admin)
            # need to set caller branch correctly for create_draft
        # fallback: create via DB directly
        async with SessionLocal() as s:
            t = Transfer(source_branch_id=branch, target_branch_id=other, transfer_no="1", status="draft", rev=1)
            s.add(t)
            await s.flush()
            tid = t.id
            s.add(TransferLine(transfer_id=tid, drug_id=drug, sent_qty=5))
            await s.commit()
        # dispatch to rev 2
        async with SessionLocal() as s:
            from app.transfers.service import dispatch
            from app.models import User as U
            caller = await s.get(U, user_admin)
            caller.branch_id = branch
            t = await s.get(Transfer, tid)
            # we need to call dispatch via API would be easier: login as user_admin
            # create user for branch and login
            pass
        # Simpler: directly test replay duplicate handling via sync_log
        # Insert a pending transfer payload with rev 2
        payload_rev2 = {
            "id": tid,
            "transfer_no": "1",
            "source_branch_id": branch,
            "target_branch_id": other,
            "status": "dispatched",
            "rev": 2,
            "lines": [{"drug_id": drug, "sent_qty": "5.0000", "allocations": []}],
            "updated_at": "2026-08-27T10:00:00+00:00",
        }
        async with SessionLocal() as s:
            row = SyncLog(branch_id=branch, entity="transfer", entity_id=tid, action="update", payload=payload_rev2, status="pending")
            s.add(row)
            await s.flush()
            first_id = row.id
            sync_ids.append(first_id)
            await s.commit()
        # first replay should apply
        async with SessionLocal() as s:
            summary = await replay_pending(s, branch_id=branch, user_id=user_admin)
            assert summary["applied"] >= 1
        # duplicate delivery same rev
        async with SessionLocal() as s:
            row2 = SyncLog(branch_id=branch, entity="transfer", entity_id=tid, action="update", payload=payload_rev2, status="pending")
            s.add(row2)
            await s.flush()
            dup_id = row2.id
            sync_ids.append(dup_id)
            await s.commit()
        async with SessionLocal() as s:
            summary2 = await replay_pending(s, branch_id=branch, user_id=user_admin)
            assert summary2["skipped"] >= 1
            # check that dup row is now applied with skipped_reason
            dup_row = await s.get(SyncLog, dup_id)
            assert dup_row.status == "applied"
            assert dup_row.payload.get("skipped_reason")
        # list conflicts should include the dup
        async with SessionLocal() as s:
            conflicts = await list_conflicts(s, branch_id=branch, entity="transfer")
            ids = [c["id"] for c in conflicts]
            assert dup_id in ids
            c = [x for x in conflicts if x["id"] == dup_id][0]
            assert c["loser"]["transfer_no"] == "1"
            assert c["winner"] is not None
            assert c["updated_at"] is not None
            assert c["skipped_reason"]
    finally:
        await _cleanup([branch, other], [user_admin], [drug], sync_ids)

@pytest.mark.asyncio
async def test_equal_rev_skip(client):
    """Payload with rev equal to local rev is stale and skipped."""
    branch = await _make_branch()
    other = await _make_branch()
    user = await _make_user(_uniq("mgr"), 7, branch)
    drug = await _make_drug_with_stock(branch)
    sync_ids = []
    try:
        async with SessionLocal() as s:
            t = Transfer(source_branch_id=branch, target_branch_id=other, transfer_no="2", status="dispatched", rev=2)
            s.add(t)
            await s.flush()
            tid = t.id
            s.add(TransferLine(transfer_id=tid, drug_id=drug, sent_qty=3))
            await s.commit()
        payload = {"id": tid, "transfer_no": "2", "source_branch_id": branch, "target_branch_id": other, "status": "dispatched", "rev": 2, "lines": [{"drug_id": drug, "sent_qty": "3.0000", "allocations": []}], "updated_at": "2026-08-27T10:00:00+00:00"}
        async with SessionLocal() as s:
            row = SyncLog(branch_id=branch, entity="transfer", entity_id=tid, action="update", payload=payload, status="pending")
            s.add(row)
            await s.flush()
            sync_ids.append(row.id)
            await s.commit()
        async with SessionLocal() as s:
            summary = await replay_pending(s, branch_id=branch, user_id=user)
            assert summary["skipped"] >= 1
            row_after = await s.get(SyncLog, sync_ids[0])
            assert row_after.payload.get("skipped_reason")
            assert "duplicate" in row_after.payload.get("skipped_reason", "").lower() or "stale" in row_after.payload.get("skipped_reason", "").lower()
    finally:
        await _cleanup([branch, other], [user], [drug], sync_ids)

@pytest.mark.asyncio
async def test_poison_row_stays_pending(client):
    """Malformed payload stays pending with failure, never silently dropped."""
    branch = await _make_branch()
    user = await _make_user(_uniq("mgr"), 7, branch)
    sync_ids = []
    try:
        payload = {"malformed": True}  # missing required fields
        async with SessionLocal() as s:
            row = SyncLog(branch_id=branch, entity="transfer", entity_id=None, action="update", payload=payload, status="pending")
            s.add(row)
            await s.flush()
            sync_ids.append(row.id)
            await s.commit()
        async with SessionLocal() as s:
            summary = await replay_pending(s, branch_id=branch, user_id=user)
            assert summary["failed"] >= 1
            row_after = await s.get(SyncLog, sync_ids[0])
            # poison stays pending (retryable) or failed? For transfer, malformed stays pending? Check service: transfer poison stays pending? Actually transfer except marks payload failure but stays pending? Let's check: in service, transfer exception marks payload failure but does NOT set status to failed? Wait transfer except does row.payload = {**payload, failure} but does NOT set row.status = "failed", it just counts failed and leaves status pending? Actually check code: for transfer, except block does row.payload = {...failure} and summary failed +=1 but does NOT set row.status, so it stays pending. Let's verify.
            # For this test, we expect pending
            assert row_after.status == "pending"
            assert row_after.payload.get("failure")
        # list conflicts should NOT include poison row (only skipped)
        async with SessionLocal() as s:
            conflicts = await list_conflicts(s, branch_id=branch)
            assert sync_ids[0] not in [c["id"] for c in conflicts]
    finally:
        await _cleanup([branch], [user], [], sync_ids)

@pytest.mark.asyncio
async def test_out_of_order_fold_forward(client):
    """Rev 3 arriving before rev 2 folds both stages; later rev 2 is stale skip."""
    branch = await _make_branch()
    other = await _make_branch()
    user = await _make_user(_uniq("mgr"), 7, branch)
    drug = await _make_drug_with_stock(branch)
    sync_ids = []
    try:
        async with SessionLocal() as s:
            t = Transfer(source_branch_id=branch, target_branch_id=other, transfer_no="3", status="draft", rev=1)
            s.add(t)
            await s.flush()
            tid = t.id
            s.add(TransferLine(transfer_id=tid, drug_id=drug, sent_qty=4))
            await s.commit()
        # payload rev 3 = received (dispatch+receive folded)
        payload_rev3 = {"id": tid, "transfer_no": "3", "source_branch_id": branch, "target_branch_id": other, "status": "received", "rev": 3, "lines": [{"drug_id": drug, "sent_qty": "4.0000", "received_qty": "4.0000", "allocations": []}], "updated_at": "2026-08-27T12:00:00+00:00"}
        async with SessionLocal() as s:
            row3 = SyncLog(branch_id=branch, entity="transfer", entity_id=tid, action="update", payload=payload_rev3, status="pending")
            s.add(row3)
            await s.flush()
            sync_ids.append(row3.id)
            await s.commit()
        async with SessionLocal() as s:
            summary = await replay_pending(s, branch_id=branch, user_id=user)
            assert summary["applied"] >= 1
            t = await s.get(Transfer, tid)
            assert t.status == "received"
            assert t.rev == 3
        # now stale rev 2 arrives
        payload_rev2 = {"id": tid, "transfer_no": "3", "source_branch_id": branch, "target_branch_id": other, "status": "dispatched", "rev": 2, "lines": [{"drug_id": drug, "sent_qty": "4.0000", "allocations": []}], "updated_at": "2026-08-27T11:00:00+00:00"}
        async with SessionLocal() as s:
            row2 = SyncLog(branch_id=branch, entity="transfer", entity_id=tid, action="update", payload=payload_rev2, status="pending")
            s.add(row2)
            await s.flush()
            sync_ids.append(row2.id)
            await s.commit()
        async with SessionLocal() as s:
            summary2 = await replay_pending(s, branch_id=branch, user_id=user)
            assert summary2["skipped"] >= 1
            row2_after = await s.get(SyncLog, sync_ids[1])
            assert row2_after.payload.get("skipped_reason")
        async with SessionLocal() as s:
            t2 = await s.get(Transfer, tid)
            assert t2.status == "received"  # winner kept
            assert t2.rev == 3
    finally:
        await _cleanup([branch, other], [user], [drug], sync_ids)

@pytest.mark.asyncio
async def test_conflicts_auth_and_cross_branch(client):
    """GET requires auth, branch-scoped; POST restore requires manager floor 7."""
    branch = await _make_branch()
    other = await _make_branch()
    mgr = await _make_user(_uniq("mgr"), 7, branch)
    cashier = await _make_user(_uniq("cash"), 1, branch)
    other_user = await _make_user(_uniq("other"), 1, other)
    drug = await _make_drug_with_stock(branch)
    sync_ids = []
    try:
        # create a conflict for branch
        payload = {"branch_id": branch, "drug_id": drug, "qty": "1.0000", "skipped_reason": "test"}
        async with SessionLocal() as s:
            row = SyncLog(branch_id=branch, entity="branch_stock", entity_id=drug, action="update", payload=payload, status="applied")
            s.add(row)
            await s.flush()
            sync_ids.append(row.id)
            await s.commit()
        # unauthenticated GET -> 401
        r = await client.get("/api/v1/sync/conflicts")
        assert r.status_code == 401
        # authenticated GET -> 200, branch-scoped
        headers_mgr = {"Authorization": f"Bearer {(await client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'changeme'})).json()['access_token']}"}
        r = await client.get("/api/v1/sync/conflicts", headers=headers_mgr)
        assert r.status_code == 200
        # cross-branch read as cashier (level 1) -> 403
        # login as cashier
        login = await client.post("/api/v1/auth/login", json={"username": await _username(cashier), "password": "pw123456"})
        # we need to get username: we have user id, fetch username
        async with SessionLocal() as s:
            u = await s.get(User, cashier)
            c_username = u.username
            u2 = await s.get(User, other_user)
            o_username = u2.username
        r_cash = await client.post("/api/v1/auth/login", json={"username": c_username, "password": "pw123456"})
        tok_cash = r_cash.json()["access_token"]
        r = await client.get(f"/api/v1/sync/conflicts?branch_id={other}", headers={"Authorization": f"Bearer {tok_cash}"})
        assert r.status_code == 403
        # other branch user requesting branch's conflicts -> 403
        r_other = await client.post("/api/v1/auth/login", json={"username": o_username, "password": "pw123456"})
        tok_other = r_other.json()["access_token"]
        r = await client.get(f"/api/v1/sync/conflicts?branch_id={branch}", headers={"Authorization": f"Bearer {tok_other}"})
        assert r.status_code == 403
        # manager can read own branch
        r_mgr_cash = await client.post("/api/v1/auth/login", json={"username": c_username, "password": "pw123456"})
        # cashier is not manager, but GET should still succeed for own branch (any authenticated)
        r = await client.get("/api/v1/sync/conflicts", headers={"Authorization": f"Bearer {tok_cash}"})
        assert r.status_code == 200
        # POST restore as cashier -> 403
        r = await client.post(f"/api/v1/sync/conflicts/{sync_ids[0]}/restore", headers={"Authorization": f"Bearer {tok_cash}"})
        assert r.status_code == 403
        # POST restore as manager -> 200, and is non-destructive (winner becomes loser, old conflict marked resolved, new sync row added)
        # need manager token for branch
        async with SessionLocal() as s:
            u_mgr = await s.get(User, mgr)
            mgr_username = u_mgr.username
        r_mgr_login = await client.post("/api/v1/auth/login", json={"username": mgr_username, "password": "pw123456"})
        tok_mgr = r_mgr_login.json()["access_token"]
        # ensure branch_stock current is different from loser so restore changes it
        async with SessionLocal() as s:
            bs = await s.get(BranchStock, (branch, drug))
            bs.qty = 50
            await s.commit()
        r = await client.post(f"/api/v1/sync/conflicts/{sync_ids[0]}/restore", headers={"Authorization": f"Bearer {tok_mgr}"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["restored"] is True
        # verify winner is now loser value (1.0000)
        async with SessionLocal() as s:
            bs2 = await s.get(BranchStock, (branch, drug))
            assert str(bs2.qty) == "1.0000"
            # conflict marked resolved
            row_after = await s.get(SyncLog, sync_ids[0])
            assert row_after.payload.get("resolved") is True
            # new sync row enqueued
            new_sync = (await s.execute(select(SyncLog).where(SyncLog.branch_id==branch, SyncLog.entity=="branch_stock", SyncLog.status=="pending").order_by(SyncLog.id.desc()).limit(1))).scalar_one_or_none()
            # if restore enqueued as pending, it should exist (or applied if replayed immediately? Our restore enqueues as pending, not applied)
            assert new_sync is not None
            assert new_sync.payload.get("qty") == "1.0000"
        # second restore -> 409
        r = await client.post(f"/api/v1/sync/conflicts/{sync_ids[0]}/restore", headers={"Authorization": f"Bearer {tok_mgr}"})
        assert r.status_code == 409
        # cross-branch restore -> 403 (mgr of branch trying to restore other branch's conflict)
        payload_other = {"branch_id": other, "drug_id": drug, "qty": "9.0000", "skipped_reason": "x"}
        async with SessionLocal() as s:
            row_other = SyncLog(branch_id=other, entity="branch_stock", entity_id=drug, action="update", payload=payload_other, status="applied")
            s.add(row_other)
            await s.flush()
            other_cid = row_other.id
            sync_ids.append(other_cid)
            await s.commit()
        r = await client.post(f"/api/v1/sync/conflicts/{other_cid}/restore", headers={"Authorization": f"Bearer {tok_mgr}"})
        assert r.status_code == 403
    finally:
        await _cleanup([branch, other], [mgr, cashier, other_user], [drug], sync_ids)

async def _username(uid: int) -> str:
    async with SessionLocal() as s:
        u = await s.get(User, uid)
        return u.username

def test_parity_check():
    """Twin parity guard must stay green after this slice."""
    import subprocess, sys
    from pathlib import Path
    result = subprocess.run([sys.executable, "scripts/parity_check.py"], cwd=Path("server"), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARITY OK" in result.stdout
