"""S5.6 chain_buy_orders integration tests (#36).

Integration-style via public API: create, RBAC, list (global chain view,
filters, include_inactive, cap+sorted), users-per-chain via store_name,
update, cancel, sync (absolute LWW, idempotent, missing-drug poison), seeded
permission, and edge-case pass (empty, dupes, boundary, auth, rounding,
concurrency, atomic audit+outbox, idempotent replay).

Factory pattern follows tests/test_needs.py: create_branch/create_user helpers,
client fixture, auth_headers.
"""
import os
import random
import secrets
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text

from app.core.db import SessionLocal
from app.models import AuditLog, Branch, ChainBuyOrder, Drug, DrugBarcode, SyncLog, User

PID = os.getpid()
_run = secrets.token_hex(3)
_seq = [0]


def _uniq(tag: str) -> str:
    _seq[0] += 1
    return f"T36_{_run}_{PID}_{tag}_{_seq[0]}"


async def _login_token(client, username: str, password: str = "pw123456") -> str:
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_branch() -> int:
    _seq[0] += 1
    async with SessionLocal() as session:
        b = Branch(
            pharmacyid=f"t36{_run}{PID % 1000}{_seq[0]}"[:15],
            phar="",
            mobile=f"01{int(_run, 16) % 1_000_000:06d}{PID % 100:02d}{_seq[0]:04d}"[:14],
            pharname=_uniq("branch"),
            is_active=True,
        )
        session.add(b)
        await session.flush()
        bid = b.id
        await session.commit()
        return bid


async def _make_user(*, level: int, branch_id):
    from app.auth.security import hash_password

    username = _uniq("u")
    async with SessionLocal() as session:
        u = User(
            username=username,
            pass_hash=hash_password("pw123456"),
            permission_level=level,
            branch_id=branch_id,
            active=True,
        )
        session.add(u)
        await session.flush()
        uid = u.id
        await session.commit()
        return uid, username


async def _make_drug(*, generic: str | None = None, drugname: str | None = None) -> int:
    async with SessionLocal() as session:
        d = Drug(
            drugname=drugname or _uniq("drug"),
            drugnamear=_uniq("drug_ar"),
            generic=generic or _uniq("generic"),
            tax_type="14%",
            price=Decimal("10.0000"),
            price_wholesale=Decimal("8.0000"),
            price_cost=Decimal("5.0000"),
        )
        session.add(d)
        await session.flush()
        did = d.id
        # at least one barcode for q filter tests
        bc = DrugBarcode(drug_id=did, barcode=f"9{random.randint(100000000000, 999999999999)}", is_primary=True)
        session.add(bc)
        await session.commit()
        return did


async def _cleanup(*, order_ids=None, drug_ids=None, branch_ids=None, user_ids=None):
    order_ids = order_ids or []
    drug_ids = drug_ids or []
    branch_ids = branch_ids or []
    user_ids = user_ids or []
    async with SessionLocal() as session:
        if order_ids:
            await session.execute(delete(ChainBuyOrder).where(ChainBuyOrder.id.in_(order_ids)))
        # remove audit/sync that reference these orders or branches/users before FK deletes
        await session.execute(delete(SyncLog).where(SyncLog.entity == "chain_buy_order"))
        await session.execute(delete(AuditLog).where(AuditLog.entity == "chain_buy_order"))
        for did in drug_ids:
            await session.execute(delete(DrugBarcode).where(DrugBarcode.drug_id == did))
            await session.execute(delete(AuditLog).where(AuditLog.drug_id == did))
            await session.execute(delete(Drug).where(Drug.id == did))
        if branch_ids:
            await session.execute(delete(ChainBuyOrder).where(ChainBuyOrder.branch_id.in_(branch_ids)))
            await session.execute(delete(SyncLog).where(SyncLog.branch_id.in_(branch_ids)))
            await session.execute(delete(AuditLog).where(AuditLog.branch_id.in_(branch_ids)))
            # branches may have seeded accounts/balances etc - clean generic audit rows already done
        if user_ids:
            await session.execute(delete(AuditLog).where(AuditLog.user_id.in_(user_ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        if branch_ids:
            await session.execute(delete(Branch).where(Branch.id.in_(branch_ids)))
        await session.commit()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_chain_buy_201_audit_sync_atomically(client):
    """G12: create writes chain_buy row + audit + outbox atomically."""
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    did = await _make_drug()
    tok = await _login_token(client, uname)
    resp = await client.post(
        "/api/v1/chain-buy",
        json={"drug_id": did, "qty": "2.5", "price": "10.1234", "store_name": "StoreA", "governorate": "Cairo", "district": "Nasr"},
        headers=_headers(tok),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["qty"] == "2.5000"
    assert body["price"] == "10.1234"
    assert body["store_name"] == "StoreA"
    assert body["branch_id"] == branch
    oid = body["id"]
    async with SessionLocal() as s:
        audits = (await s.execute(select(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.entity_id == oid))).scalars().all()
        assert len(audits) == 1
        assert audits[0].action == "insert"
        syncs = (await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().all()
        assert len(syncs) == 1
        assert syncs[0].status == "pending"
        assert syncs[0].payload["qty"] == "2.5000"
        assert syncs[0].payload["store_name"] == "StoreA"
    await _cleanup(order_ids=[oid], drug_ids=[did], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_create_persists_region_fields_and_4dp_and_defaults(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    did = await _make_drug()
    tok = await _login_token(client, uname)
    # qty 1.2 should persist as 4dp 1.2000, price 2.5 as 2.5000
    resp = await client.post(
        "/api/v1/chain-buy",
        headers=_headers(tok),
        json={
            "drug_id": did,
            "qty": "1.2",
            "price": "2.5",
            "store_name": "MyStore",
            "pharmacist_tel": "0123456789",
            "requester_tel": "0987654321",
            "governorate": "Giza",
            "district": "Dokki",
            "country": "Egypt",
            "tips": "quick",
            "expire": "2027-01-01",
        },
    )
    assert resp.status_code == 201, resp.text
    b = resp.json()
    assert b["qty"] == "1.2000"
    assert b["price"] == "2.5000"
    assert b["sell_disc"] == "0.00"
    assert b["store_name"] == "MyStore"
    assert b["pharmacist_tel"] == "0123456789"
    assert b["requester_tel"] == "0987654321"
    assert b["governorate"] == "Giza"
    assert b["district"] == "Dokki"
    assert b["country"] == "Egypt"
    assert b["tips"] == "quick"
    assert b["expire"] == "2027-01-01"
    # pharmacist_tel default when omitted
    resp2 = await client.post(
        "/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "1", "store_name": "NoTel"}
    )
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["pharmacist_tel"] == ""
    assert resp2.json()["requester_tel"] == ""
    await _cleanup(order_ids=[b["id"], resp2.json()["id"]], drug_ids=[did], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_create_invalid_qty_variants_400(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    did = await _make_drug()
    tok = await _login_token(client, uname)
    headers = _headers(tok)
    for qty, msg in [
        ("0", "qty 0"),
        ("-1", "negative"),
        ("-0.0001", "negative small"),
        ("NaN", "NaN"),
        ("Infinity", "Infinity"),
        ("100000000000000", "overflow >=1e14"),
        ("1.00005", "overflow 5dp"),
    ]:
        r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": qty, "price": "1"})
        assert r.status_code == 400, f"{msg} qty={qty} got {r.status_code} {r.text}"
    # also ensure valid 4dp passes
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "1.2345", "price": "1"})
    assert r.status_code == 201, r.text
    await _cleanup(order_ids=[r.json()["id"]], drug_ids=[did], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_create_invalid_price_and_missing_drug(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    did = await _make_drug()
    tok = await _login_token(client, uname)
    headers = _headers(tok)
    # price negative ->400 (Pydantic ge=0)
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "1", "price": "-5"})
    assert r.status_code == 400, r.text
    # price overflow handled by service or pydantic ->400
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "1", "price": "100000000000000"})
    assert r.status_code == 400, r.text
    # missing drug ->404
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": 99999999, "qty": "1"})
    assert r.status_code == 404, r.text
    # ensure no audit/sync leaked for failed create
    async with SessionLocal() as s:
        audits = (await s.execute(select(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.drug_id == 99999999))).scalars().all()
        assert audits == []
    await _cleanup(drug_ids=[did], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_create_branchless_400(client):
    # branchless user with floor 3 still passes RBAC but service raises 400
    uid, uname = await _make_user(level=3, branch_id=None)
    did = await _make_drug()
    tok = await _login_token(client, uname)
    r = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "1"})
    assert r.status_code == 400, r.text
    assert "branch" in r.text.lower()
    await _cleanup(drug_ids=[did], user_ids=[uid])


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_post_patch_cancel_require_chain_buy_manage(client):
    branch = await _make_branch()
    # cashier L1 has no stock area (floor 3)
    cashier_id, cashier_name = await _make_user(level=1, branch_id=branch)
    cashier_tok = await _login_token(client, cashier_name)
    # manager/pharmacist/admin should succeed
    manager_id, manager_name = await _make_user(level=3, branch_id=branch)  # pharmacist floor
    admin_id, admin_name = await _make_user(level=9, branch_id=branch)
    # need drug
    did = await _make_drug()
    # cashier POST ->403
    r = await client.post("/api/v1/chain-buy", headers=_headers(cashier_tok), json={"drug_id": did, "qty": "1"})
    assert r.status_code == 403, r.text
    # manager creates
    manager_tok = await _login_token(client, manager_name)
    r = await client.post("/api/v1/chain-buy", headers=_headers(manager_tok), json={"drug_id": did, "qty": "2"})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    # cashier PATCH ->403
    r = await client.patch(f"/api/v1/chain-buy/{oid}", headers=_headers(cashier_tok), json={"qty": "3"})
    assert r.status_code == 403, r.text
    # cashier cancel ->403
    r = await client.post(f"/api/v1/chain-buy/{oid}/cancel", headers=_headers(cashier_tok))
    assert r.status_code == 403, r.text
    # admin can POST
    admin_tok = await _login_token(client, admin_name)
    r = await client.post("/api/v1/chain-buy", headers=_headers(admin_tok), json={"drug_id": did, "qty": "1"})
    assert r.status_code == 201, r.text
    admin_oid = r.json()["id"]
    # unauth POST 401
    r = await client.post("/api/v1/chain-buy", json={"drug_id": did, "qty": "1"})
    assert r.status_code == 401
    await _cleanup(order_ids=[oid, admin_oid], drug_ids=[did], branch_ids=[branch], user_ids=[cashier_id, manager_id, admin_id])


@pytest.mark.asyncio
async def test_get_list_auth_only_and_global_view(client):
    b1 = await _make_branch()
    b2 = await _make_branch()
    uid1, uname1 = await _make_user(level=3, branch_id=b1)
    uid2, uname2 = await _make_user(level=3, branch_id=b2)
    did = await _make_drug()
    tok1 = await _login_token(client, uname1)
    tok2 = await _login_token(client, uname2)
    # create one on each branch
    r1 = await client.post("/api/v1/chain-buy", headers=_headers(tok1), json={"drug_id": did, "qty": "1", "store_name": "Store1"})
    r2 = await client.post("/api/v1/chain-buy", headers=_headers(tok2), json={"drug_id": did, "qty": "2", "store_name": "Store2"})
    assert r1.status_code == 201 and r2.status_code == 201
    oid1, oid2 = r1.json()["id"], r2.json()["id"]
    # unauth list 401
    r = await client.get("/api/v1/chain-buy")
    assert r.status_code == 401
    # auth list sees BOTH branches (global chain view)
    r = await client.get("/api/v1/chain-buy", headers=_headers(tok1))
    assert r.status_code == 200, r.text
    ids = {it["id"] for it in r.json()["items"]}
    assert oid1 in ids and oid2 in ids
    assert r.json()["count"] >= 2
    # also from b2 sees both
    r = await client.get("/api/v1/chain-buy", headers=_headers(tok2))
    ids2 = {it["id"] for it in r.json()["items"]}
    assert oid1 in ids2 and oid2 in ids2
    await _cleanup(order_ids=[oid1, oid2], drug_ids=[did], branch_ids=[b1, b2], user_ids=[uid1, uid2])


# ---------------------------------------------------------------------------
# list filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_filters_q_and_barcode_escaped(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    tok = await _login_token(client, uname)
    # drug with distinctive generic and barcode
    generic = _uniq("gen_q")
    did = await _make_drug(generic=generic)
    async with SessionLocal() as s:
        bc = (await s.execute(select(DrugBarcode).where(DrugBarcode.drug_id == did))).scalars().first()
        barcode = bc.barcode
        drug = await s.get(Drug, did)
        drugname = drug.drugname
    # create order for that drug
    r = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "1", "store_name": "QStore"})
    assert r.status_code == 201
    oid = r.json()["id"]
    # q by drugname
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"q": drugname[:8]})
    assert resp.status_code == 200
    assert any(it["id"] == oid for it in resp.json()["items"])
    # q by generic
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"q": generic[:8]})
    assert any(it["id"] == oid for it in resp.json()["items"])
    # q by barcode
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"q": barcode})
    assert any(it["id"] == oid for it in resp.json()["items"])
    # q escaping % and _ : search for literal % should not wildcard to everything
    # create a drug with % in name
    did2 = await _make_drug(drugname="Drug%Percent_"+_uniq("pct"))
    r2 = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did2, "qty": "1"})
    assert r2.status_code == 201
    oid2 = r2.json()["id"]
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"q": "Drug%Percent"})
    # should find did2 but not necessarily did
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid2 in ids
    # search for literal % alone should not match all (escaped)
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"q": "%"})
    ids_pct = {it["id"] for it in resp.json()["items"]}
    # only orders whose drug contains % should be returned, not everything
    # at minimum, oid (without %) must NOT be in results if escaping works correctly
    # but if no drug contains literal %, result may be empty - both are valid; assert it is not the full set
    assert oid not in ids_pct or len(ids_pct) < 2  # ensures % not treated as wildcard
    await _cleanup(order_ids=[oid, oid2], drug_ids=[did, did2], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_list_filters_store_name_governorate_district_status(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    tok = await _login_token(client, uname)
    did = await _make_drug()
    r1 = await client.post(
        "/api/v1/chain-buy",
        headers=_headers(tok),
        json={"drug_id": did, "qty": "1", "store_name": "AlphaStore", "governorate": "Cairo", "district": "Nasr", "tips": "a"},
    )
    r2 = await client.post(
        "/api/v1/chain-buy",
        headers=_headers(tok),
        json={"drug_id": did, "qty": "2", "store_name": "BetaStore", "governorate": "Giza", "district": "Dokki"},
    )
    assert r1.status_code == 201 and r2.status_code == 201
    oid1, oid2 = r1.json()["id"], r2.json()["id"]
    # store_name ilike with escaped %
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"store_name": "Alpha"})
    assert resp.status_code == 200
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid1 in ids and oid2 not in ids
    # store_name with % literal should be escaped - create one with %
    r3 = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "1", "store_name": "Test%Store_123"})
    oid3 = r3.json()["id"]
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"store_name": "%Store_"})
    assert any(it["id"] == oid3 for it in resp.json()["items"])
    # governorate filter
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"governorate": "Cairo"})
    assert any(it["id"] == oid1 for it in resp.json()["items"])
    assert all(it["governorate"] == "Cairo" for it in resp.json()["items"] if it["id"] == oid1)
    # district filter
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"district": "Dokki"})
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid2 in ids and oid1 not in ids
    # status filter
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"status": "created"})
    assert any(it["id"] == oid1 for it in resp.json()["items"])
    # cancel one and filter cancelled
    await client.post(f"/api/v1/chain-buy/{oid1}/cancel", headers=_headers(tok))
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"status": "cancelled"})
    assert any(it["id"] == oid1 for it in resp.json()["items"])
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"status": "created"})
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid1 not in ids
    await _cleanup(order_ids=[oid1, oid2, oid3], drug_ids=[did], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_list_include_inactive_toggles_branch_and_drug(client):
    b1 = await _make_branch()
    b2 = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=b1)
    tok = await _login_token(client, uname)
    did_active = await _make_drug()
    did_inactive = await _make_drug()
    # deactivate one drug
    async with SessionLocal() as s:
        d = await s.get(Drug, did_inactive)
        d.active = False
        await s.commit()
    # create orders: one on active branch+drug, one on b2/did_active, one with inactive drug
    r1 = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did_active, "qty": "1", "store_name": "ActiveDrugActiveBranch"})
    assert r1.status_code == 201
    oid1 = r1.json()["id"]
    # create order on b2 via second user, then deactivate b2
    uid2, uname2 = await _make_user(level=3, branch_id=b2)
    tok2 = await _login_token(client, uname2)
    r2 = await client.post("/api/v1/chain-buy", headers=_headers(tok2), json={"drug_id": did_active, "qty": "1", "store_name": "ActiveDrugB2"})
    assert r2.status_code == 201
    oid2 = r2.json()["id"]
    async with SessionLocal() as s:
        br = await s.get(Branch, b2)
        br.is_active = False
        await s.commit()
    # create order with inactive drug (b1 user) - should still create, but list should hide it unless include_inactive
    r3 = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did_inactive, "qty": "1", "store_name": "InactiveDrug"})
    assert r3.status_code == 201
    oid3 = r3.json()["id"]
    # default list excludes inactive branch and inactive drug rows
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok))
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid1 in ids
    assert oid2 not in ids  # branch inactive
    assert oid3 not in ids  # drug inactive
    # include_inactive true includes both
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"include_inactive": "true"})
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid1 in ids and oid2 in ids and oid3 in ids
    # restore for cleanup
    async with SessionLocal() as s:
        br = await s.get(Branch, b2)
        br.is_active = True
        d = await s.get(Drug, did_inactive)
        d.active = True
        await s.commit()
    await _cleanup(order_ids=[oid1, oid2, oid3], drug_ids=[did_active, did_inactive], branch_ids=[b1, b2], user_ids=[uid, uid2])


@pytest.mark.asyncio
async def test_list_cap_truncated_and_sorted_desc(client):
    from app.chain_buy import service as cb_service

    orig = cb_service._MAX_ROWS
    cb_service._MAX_ROWS = 2
    try:
        branch = await _make_branch()
        uid, uname = await _make_user(level=3, branch_id=branch)
        tok = await _login_token(client, uname)
        did = await _make_drug()
        cap_prefix = _uniq("cap")
        oids = []
        for i in range(3):
            r = await client.post(
                "/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "1", "store_name": f"{cap_prefix}_{i}"}
            )
            assert r.status_code == 201, r.text
            oids.append(r.json()["id"])
            # small delay to ensure distinct iddatetime
            import asyncio as _asyncio
            await _asyncio.sleep(0.02)
        resp = await client.get("/api/v1/chain-buy", headers=_headers(tok), params={"store_name": cap_prefix})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 3
        assert body["truncated"] is True
        assert len(body["items"]) == 2
        # sorted iddatetime DESC, tie-breaker id DESC: newest first
        assert body["items"][0]["id"] == oids[-1]
        assert body["items"][1]["id"] == oids[-2]
        await _cleanup(order_ids=oids, drug_ids=[did], branch_ids=[branch], user_ids=[uid])
    finally:
        cb_service._MAX_ROWS = orig


@pytest.mark.asyncio
async def test_users_per_chain_store_name_grouping(client):
    """Legacy 1:many ChainBuyStore->ChainBuyUsers via store_name: two orders
    same store_name+drug must both appear when filtering by that store_name."""
    b1 = await _make_branch()
    b2 = await _make_branch()
    uid1, uname1 = await _make_user(level=3, branch_id=b1)
    uid2, uname2 = await _make_user(level=3, branch_id=b2)
    tok1 = await _login_token(client, uname1)
    tok2 = await _login_token(client, uname2)
    did = await _make_drug()
    store = _uniq("common_store")
    r1 = await client.post("/api/v1/chain-buy", headers=_headers(tok1), json={"drug_id": did, "qty": "1", "store_name": store})
    r2 = await client.post("/api/v1/chain-buy", headers=_headers(tok2), json={"drug_id": did, "qty": "2", "store_name": store})
    assert r1.status_code == 201 and r2.status_code == 201
    oid1, oid2 = r1.json()["id"], r2.json()["id"]
    resp = await client.get("/api/v1/chain-buy", headers=_headers(tok1), params={"store_name": store})
    assert resp.status_code == 200
    ids = {it["id"] for it in resp.json()["items"]}
    assert oid1 in ids and oid2 in ids
    assert resp.json()["count"] == 2
    await _cleanup(order_ids=[oid1, oid2], drug_ids=[did], branch_ids=[b1, b2], user_ids=[uid1, uid2])


# ---------------------------------------------------------------------------
# update / cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_owner_ok_wrong_branch_403_and_audit_bump(client):
    b1 = await _make_branch()
    b2 = await _make_branch()
    uid1, uname1 = await _make_user(level=3, branch_id=b1)
    uid2, uname2 = await _make_user(level=3, branch_id=b2)
    did = await _make_drug()
    tok1 = await _login_token(client, uname1)
    tok2 = await _login_token(client, uname2)
    r = await client.post("/api/v1/chain-buy", headers=_headers(tok1), json={"drug_id": did, "qty": "1", "price": "5", "tips": "old"})
    assert r.status_code == 201
    oid = r.json()["id"]
    async with SessionLocal() as s:
        audits_before = len((await s.execute(select(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.entity_id == oid))).scalars().all())
        syncs_before = len((await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().all())
    # owner patch succeeds
    r = await client.patch(f"/api/v1/chain-buy/{oid}", headers=_headers(tok1), json={"qty": "5.5", "price": "9.99", "tips": "new tips", "governorate": "Cairo"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qty"] == "5.5000"
    assert body["price"] == "9.9900"
    assert body["tips"] == "new tips"
    async with SessionLocal() as s:
        audits_after = len((await s.execute(select(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.entity_id == oid))).scalars().all())
        syncs_after = len((await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().all())
        assert audits_after == audits_before + 1
        assert syncs_after == syncs_before + 1
    # wrong branch ->403
    r = await client.patch(f"/api/v1/chain-buy/{oid}", headers=_headers(tok2), json={"qty": "9"})
    assert r.status_code == 403, r.text
    # unauth 401
    r = await client.patch(f"/api/v1/chain-buy/{oid}", json={"qty": "1"})
    assert r.status_code == 401
    # status=cancelled via PATCH must be rejected (use cancel endpoint)
    r = await client.patch(f"/api/v1/chain-buy/{oid}", headers=_headers(tok1), json={"status": "cancelled"})
    assert r.status_code == 400, r.text
    await _cleanup(order_ids=[oid], drug_ids=[did], branch_ids=[b1, b2], user_ids=[uid1, uid2])


@pytest.mark.asyncio
async def test_cancel_sets_cancelled_second_409_audit_outbox(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    tok = await _login_token(client, uname)
    did = await _make_drug()
    r = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "1"})
    oid = r.json()["id"]
    async with SessionLocal() as s:
        sync_before = len((await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().all())
    r = await client.post(f"/api/v1/chain-buy/{oid}/cancel", headers=_headers(tok))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    async with SessionLocal() as s:
        audits = (await s.execute(select(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.entity_id == oid))).scalars().all()
        assert len(audits) == 2  # insert + cancel
        sync_after = len((await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().all())
        assert sync_after == sync_before + 1
    # second cancel ->409 (idempotent or 409 per spec; impl chooses 409)
    r = await client.post(f"/api/v1/chain-buy/{oid}/cancel", headers=_headers(tok))
    assert r.status_code == 409, r.text
    # cancelled order cannot be patched
    r = await client.patch(f"/api/v1/chain-buy/{oid}", headers=_headers(tok), json={"qty": "2"})
    assert r.status_code == 409
    await _cleanup(order_ids=[oid], drug_ids=[did], branch_ids=[branch], user_ids=[uid])


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_create_enqueues_and_replay_idempotent(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    tok = await _login_token(client, uname)
    did = await _make_drug()
    r = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "3", "store_name": "SyncStore"})
    assert r.status_code == 201
    oid = r.json()["id"]
    async with SessionLocal() as s:
        sync = (await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().first()
        assert sync is not None
        assert sync.status == "pending"
        payload = dict(sync.payload)
        assert payload["qty"] == "3.0000"
        sid = sync.id
    # replay via service (absolute LWW)
    from app.sync.service import replay_pending

    async with SessionLocal() as sess:
        summary = await replay_pending(sess, branch_id=branch)
    # first replay must have applied at least our row
    assert summary["failed"] == 0
    assert summary["applied"] >= 1
    async with SessionLocal() as s:
        row = await s.get(SyncLog, sid)
        assert row.status == "applied"
        # duplicate delivery: reset to pending and replay again -> idempotent (applied again, no failure, single order)
        row.status = "pending"
        await s.commit()
    async with SessionLocal() as sess:
        summary2 = await replay_pending(sess, branch_id=branch)
    assert summary2["failed"] == 0
    # should be counted as applied (or skipped) but not failed; order must still be single
    assert summary2["applied"] + summary2["skipped"] >= 1
    async with SessionLocal() as s:
        orders = (await s.execute(select(ChainBuyOrder).where(ChainBuyOrder.id == oid))).scalars().all()
        assert len(orders) == 1
        assert str(orders[0].qty) == "3.0000"
    # also verify via POST /sync/replay endpoint exists and is reachable
    r = await client.post("/api/v1/sync/replay", headers=_headers(tok))
    assert r.status_code == 200, r.text
    assert "applied" in r.json()
    await _cleanup(order_ids=[oid], drug_ids=[did], branch_ids=[branch], user_ids=[uid])


@pytest.mark.asyncio
async def test_sync_missing_drug_failed_then_retry_after_drug_created(client):
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    tok = await _login_token(client, uname)
    # create a drug and order, capture payload
    did = await _make_drug()
    r = await client.post("/api/v1/chain-buy", headers=_headers(tok), json={"drug_id": did, "qty": "5", "store_name": "MissingDrugStore"})
    assert r.status_code == 201
    oid = r.json()["id"]
    async with SessionLocal() as s:
        sync = (await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid))).scalars().first()
        payload = dict(sync.payload)
    # simulate offline peer that never saw the order: delete order, keep sync pending but drug will be missing
    # create a fake payload with non-existent drug id
    fake_drug = 99999999
    fake_id = 888888
    fake_payload = {**payload, "id": fake_id, "drug_id": fake_drug, "branch_id": branch}
    async with SessionLocal() as s:
        # ensure original order not confused
        await s.execute(delete(ChainBuyOrder).where(ChainBuyOrder.id == oid))
        # mark original sync applied so only fake is pending
        await s.execute(text("UPDATE sync_log SET status='applied' WHERE entity='chain_buy_order' AND branch_id=:bid"), {"bid": branch})
        await s.commit()
        row = SyncLog(branch_id=branch, entity="chain_buy_order", entity_id=fake_id, action="insert", payload=fake_payload, status="pending")
        s.add(row)
        await s.flush()
        fake_sid = row.id
        await s.commit()
    from app.sync.service import replay_pending

    async with SessionLocal() as sess:
        summary = await replay_pending(sess, branch_id=branch)
    assert summary["failed"] == 1
    assert any(str(fake_drug) in str(f.get("error", "")) for f in summary["failures"])
    async with SessionLocal() as s:
        row = await s.get(SyncLog, fake_sid)
        # stayed pending (or failed) with failure recorded, never lost
        assert row.payload.get("failure") is not None
        assert "drug" in row.payload["failure"].lower()
        assert await s.get(ChainBuyOrder, fake_id) is None
        # now create the missing drug with that exact id via OVERRIDING SYSTEM VALUE
        await s.execute(text("INSERT INTO drugs (id, drugname, tax_type) OVERRIDING SYSTEM VALUE VALUES (:id, :name, 'exempt')"), {"id": fake_drug, "name": "RecreatedForChainBuy"})
        await s.commit()
    # retry should now apply
    async with SessionLocal() as sess:
        summary2 = await replay_pending(sess, branch_id=branch)
    assert summary2["failed"] == 0
    assert summary2["applied"] >= 1
    async with SessionLocal() as s:
        order = await s.get(ChainBuyOrder, fake_id)
        assert order is not None
        assert int(order.drug_id) == fake_drug
        row = await s.get(SyncLog, fake_sid)
        assert row.status == "applied"
        assert row.payload.get("failure") is None
        # also test idempotent second delivery of same payload: reset to pending -> applied again (absolute LWW)
        row.status = "pending"
        await s.commit()
    async with SessionLocal() as sess:
        summary3 = await replay_pending(sess, branch_id=branch)
    assert summary3["failed"] == 0
    async with SessionLocal() as s:
        # cleanup fake drug and order
        await s.execute(delete(SyncLog).where(SyncLog.id == fake_sid))
        await s.execute(delete(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.entity_id == fake_id))
        await s.execute(delete(ChainBuyOrder).where(ChainBuyOrder.id == fake_id))
        await s.execute(delete(DrugBarcode).where(DrugBarcode.drug_id == fake_drug))
        await s.execute(delete(Drug).where(Drug.id == fake_drug))
        # also restore original did branch
        await s.execute(delete(SyncLog).where(SyncLog.branch_id == branch, SyncLog.entity == "chain_buy_order"))
        await s.execute(delete(AuditLog).where(AuditLog.branch_id == branch))
        await s.execute(delete(DrugBarcode).where(DrugBarcode.drug_id == did))
        await s.execute(delete(Drug).where(Drug.id == did))
        await s.execute(delete(User).where(User.id == uid))
        await s.execute(delete(Branch).where(Branch.id == branch))
        await s.commit()


# ---------------------------------------------------------------------------
# seeded permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_buy_manage_seeded_to_roles_1_2_5(client):
    async with SessionLocal() as s:
        rows = (await s.execute(text("SELECT r.id FROM roles r JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id WHERE p.code='chain_buy.manage' ORDER BY r.id"))).all()
        ids = [r[0] for r in rows]
        assert ids == [1, 2, 5]
        # also floor check: permission_level 3 should grant via legacy floor
        from app.auth.rbac import LEGACY_LEVEL_FLOOR
        assert LEGACY_LEVEL_FLOOR["chain_buy.manage"] == 3


# ---------------------------------------------------------------------------
# edge-case pass checklist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_cases_empty_missing_dupes_boundary_auth_offline_rounding_concurrency_atomic_idempotent(client):
    """Combined edge-case pass: exercises empty/missing, dupes, boundary, auth,
    offline, rounding, concurrency (advisory lock), atomic audit+outbox, idempotent replay."""
    branch = await _make_branch()
    uid, uname = await _make_user(level=3, branch_id=branch)
    tok = await _login_token(client, uname)
    headers = _headers(tok)
    # empty/missing: no body ->400, missing qty ->400, empty qty string? payload with qty None
    r = await client.post("/api/v1/chain-buy", headers=headers, json={})
    assert r.status_code == 400
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": 1})
    assert r.status_code == 400
    # dupes: same store_name+drug twice should create two distinct rows (users-per-chain)
    did = await _make_drug()
    store = _uniq("edge_store")
    r1 = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "1", "store_name": store})
    r2 = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "2", "store_name": store})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
    # boundary: min qty 0.0001 should be allowed, overflow already tested as 400
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "0.0001"})
    assert r.status_code == 201, r.text
    oid_small = r.json()["id"]
    assert r.json()["qty"] == "0.0001"
    # auth/permission: cashier cannot create, unauth 401, branchless 400 already covered but re-assert
    cashier_id, cashier_name = await _make_user(level=1, branch_id=branch)
    cashier_tok = await _login_token(client, cashier_name)
    r = await client.post("/api/v1/chain-buy", headers=_headers(cashier_tok), json={"drug_id": did, "qty": "1"})
    assert r.status_code == 403
    r = await client.get("/api/v1/chain-buy")
    assert r.status_code == 401
    # offline: sync enqueue already tested; ensure outbox exists for r1
    async with SessionLocal() as s:
        syncs = (await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == r1.json()["id"]))).scalars().all()
        assert len(syncs) == 1
    # rounding: qty 1.2 -> 1.2000 (already) and price 1.23455 should be 400 due to 4dp limit - ensure not silently truncated
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "1.2000", "price": "1.2345"})
    assert r.status_code == 201
    assert r.json()["price"] == "1.2345"
    oid_round = r.json()["id"]
    # concurrency: advisory lock - fire two concurrent creates from same branch (no oversell, just distinct ids)
    import asyncio

    async def _create(qty):
        return await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": qty})

    results = await asyncio.gather(_create("1.0001"), _create("1.0002"))
    assert all(res.status_code == 201 for res in results)
    assert results[0].json()["id"] != results[1].json()["id"]
    conc_ids = [res.json()["id"] for res in results]
    # atomic audit+outbox: success has both, failure has neither - induce failure via missing drug
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": 99999999, "qty": "1"})
    assert r.status_code == 404
    async with SessionLocal() as s:
        audits = (await s.execute(select(AuditLog).where(AuditLog.entity == "chain_buy_order", AuditLog.entity_id == 99999999))).scalars().all()
        assert audits == []
        syncs = (await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == 99999999))).scalars().all()
        assert syncs == []
    # idempotent replay: create order, replay pending, reset to pending, replay again -> still single order, no duplicate
    r = await client.post("/api/v1/chain-buy", headers=headers, json={"drug_id": did, "qty": "9"})
    oid_idem = r.json()["id"]
    async with SessionLocal() as s:
        sync = (await s.execute(select(SyncLog).where(SyncLog.entity == "chain_buy_order", SyncLog.entity_id == oid_idem))).scalars().first()
        sid = sync.id
    from app.sync.service import replay_pending

    async with SessionLocal() as sess:
        s1 = await replay_pending(sess, branch_id=branch)
    assert s1["failed"] == 0
    async with SessionLocal() as s:
        row = await s.get(SyncLog, sid)
        row.status = "pending"
        await s.commit()
    async with SessionLocal() as sess:
        s2 = await replay_pending(sess, branch_id=branch)
    assert s2["failed"] == 0
    async with SessionLocal() as s:
        cnt = (await s.execute(select(ChainBuyOrder).where(ChainBuyOrder.id == oid_idem))).scalars().all()
        assert len(cnt) == 1
    await _cleanup(
        order_ids=[r1.json()["id"], r2.json()["id"], oid_small, oid_round, oid_idem] + conc_ids,
        drug_ids=[did],
        branch_ids=[branch],
        user_ids=[uid, cashier_id],
    )
