"""Audit-hardening theme: gaps surfaced by the 4-domain audit of #32
(RBAC/auth, stock+concurrency, validation/numbering, audit/outbox).

Pins: 401 wall on every endpoint, third-branch scoping matrix, branchless
user matrix, role-grant bypassing the legacy floor, 404 on missing ids,
wrong-branch batch rejection, expired-lot dispatch behavior (pinned as
allowed), and the concurrent-receive same-randomid merge race that motivated
the per-target-branch receive advisory lock.
"""
import asyncio

import pytest
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.models import Branch, BranchStock, StockBatch, user_roles_table

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
    return {
        "client": client,
        "src": src,
        "tgt": tgt,
        "src_token": await u._login_token(client, src_name),
        "tgt_token": await u._login_token(client, tgt_name),
        "drug_a": drug_a,
        "_user_ids": [src_user, tgt_user],
        "_branch_ids": [src, tgt],
        "_drug_ids": [drug_a],
        "_transfer_ids": [],
    }


@pytest.fixture(autouse=True)
async def _cleanup(world):
    yield
    async with SessionLocal() as s:
        from app.models import user_roles_table as urt

        await s.execute(urt.delete().where(urt.c.user_id.in_(world["_user_ids"])))
        await s.commit()
    await u._cleanup(
        transfer_ids=world["_transfer_ids"],
        drug_ids=world["_drug_ids"],
        branch_ids=world["_branch_ids"],
        user_ids=world["_user_ids"],
    )


async def _draft(world) -> dict:
    r = await world["client"].post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug_a"], "qty": "2"}],
        },
    )
    assert r.status_code == 201, r.text
    draft = r.json()
    world["_transfer_ids"].append(draft["id"])
    return draft


# ---------- AUTH-1: the 401 wall on EVERY endpoint ----------

@pytest.mark.parametrize(
    ("method", "path_builder"),
    [
        ("get", lambda tid: "/api/v1/transfers"),
        ("get", lambda tid: f"/api/v1/transfers/{tid}"),
        ("post", lambda tid: "/api/v1/transfers"),
        ("post", lambda tid: f"/api/v1/transfers/{tid}/dispatch"),
        ("post", lambda tid: f"/api/v1/transfers/{tid}/receive"),
        ("post", lambda tid: f"/api/v1/transfers/{tid}/cancel"),
    ],
)
async def test_401_unauthenticated_on_every_endpoint(world, method, path_builder):
    client = world["client"]
    tid = (await _draft(world))["id"]
    path = path_builder(tid)
    body = {} if method == "post" else None

    no_header = await client.request(method, path, json=body)
    assert no_header.status_code == 401
    assert no_header.json()["detail"] == "Not authenticated"

    garbage = await client.request(
        method, path, json=body, headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert garbage.status_code == 401
    assert garbage.json()["detail"] == "Invalid or expired token"


async def test_401_refresh_token_is_not_a_bearer_credential(world):
    client = world["client"]
    name = u._uniq("refreshy")
    uid = await u._make_user(name, level=3, branch_id=world["src"])
    world["_user_ids"].append(uid)
    login = await client.post(
        "/api/v1/auth/login", json={"username": name, "password": "pw123456"}
    )
    assert login.status_code == 200
    refresh = login.json()["refresh_token"]
    r = await client.get(
        "/api/v1/transfers", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert r.status_code == 401


# ---------- AUTH-2: third-branch scoping is consistent ----------

async def test_third_branch_scoping_matrix(world):
    client = world["client"]
    out_branch = await u._make_branch()
    world["_branch_ids"].append(out_branch)
    out_name = u._uniq("outsider")
    out_user = await u._make_user(out_name, level=3, branch_id=out_branch)
    world["_user_ids"].append(out_user)
    out_tok = await u._login_token(client, out_name)

    tid = (await _draft(world))["id"]

    r = await client.get("/api/v1/transfers", headers=u._headers(out_tok))
    assert r.status_code == 200 and r.json()["transfers"] == []

    r = await client.get(f"/api/v1/transfers/{tid}", headers=u._headers(out_tok))
    assert r.status_code == 404 and r.json()["detail"] == "transfer not found"

    for path, body in [
        (f"/api/v1/transfers/{tid}/dispatch", {}),
        (f"/api/v1/transfers/{tid}/receive", {"lines": []}),
        (f"/api/v1/transfers/{tid}/cancel", {}),
    ]:
        r = await client.post(path, headers=u._headers(out_tok), json=body)
        assert r.status_code == 403, (path, r.status_code)
        assert r.json()["detail"] == "caller is not a party to this transfer"


# ---------- AUTH-3: branchless user cannot read one nor write any ----------

async def test_branchless_user_matrix(world):
    client = world["client"]
    name = u._uniq("branchless")
    uid = await u._make_user(name, level=9, branch_id=None)
    world["_user_ids"].append(uid)
    tok = await u._login_token(client, name)

    tid = (await _draft(world))["id"]

    r = await client.get("/api/v1/transfers", headers=u._headers(tok))
    assert r.status_code == 200 and r.json()["transfers"] == []

    r = await client.get(f"/api/v1/transfers/{tid}", headers=u._headers(tok))
    assert r.status_code == 404

    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(tok),
        json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "1"}]},
    )
    assert r.status_code == 403

    for path, body in [
        (f"/api/v1/transfers/{tid}/dispatch", {}),
        (f"/api/v1/transfers/{tid}/receive", {"lines": []}),
        (f"/api/v1/transfers/{tid}/cancel", {}),
    ]:
        r = await client.post(path, headers=u._headers(tok), json=body)
        assert r.status_code == 403, (path, r.status_code)


# ---------- AUTH-4: granular role grant bypasses the legacy floor ----------

async def _add_role(user_id: int, role_id: int) -> None:
    async with SessionLocal() as s:
        await s.execute(
            user_roles_table.insert().values(user_id=user_id, role_id=role_id)
        )
        await s.commit()


async def test_role_grant_beats_low_level_and_missing_grant_denies(world):
    client = world["client"]

    # level-1 + pharmacist role (seeded transfers.manage in 027) → allowed
    pharm_name = u._uniq("pharm")
    pharm_uid = await u._make_user(pharm_name, level=1, branch_id=world["src"])
    world["_user_ids"].append(pharm_uid)
    await _add_role(pharm_uid, 2)
    tok = await u._login_token(client, pharm_name)
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(tok),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug_a"], "qty": "1"}],
        },
    )
    assert r.status_code == 201, r.text
    world["_transfer_ids"].append(r.json()["id"])

    # level-2 + cashier role (sale.create only, NO transfers.manage) → denied
    cash_name = u._uniq("cash")
    cash_uid = await u._make_user(cash_name, level=2, branch_id=world["src"])
    world["_user_ids"].append(cash_uid)
    await _add_role(cash_uid, 3)
    tok = await u._login_token(client, cash_name)
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(tok),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug_a"], "qty": "1"}],
        },
    )
    assert r.status_code == 403


# ---------- VA-8: writes on a missing transfer id are 404 ----------

@pytest.mark.parametrize(
    "action,body",
    [
        ("dispatch", {}),
        ("receive", {"lines": []}),
        ("cancel", {}),
    ],
)
async def test_missing_transfer_id_on_writes_404(world, action, body):
    r = await world["client"].post(
        f"/api/v1/transfers/99999999/{action}",
        headers=u._headers(world["src_token"]),
        json=body,
    )
    assert r.status_code == 404 and r.json()["detail"] == "transfer not found"


# ---------- ST-12: batch from the WRONG BRANCH is rejected at dispatch ----------

async def test_dispatch_batch_from_wrong_branch_rejected(world):
    client = world["client"]
    # a batch that lives on the TARGET branch must not be dispatchable from src
    async with SessionLocal() as s:
        s.add(
            StockBatch(
                branch_id=world["tgt"],
                drug_id=world["drug_a"],
                randomid=u._uniq("wrongbranch"),
                qty=50,
                cost=1,
                expire=None,
            )
        )
        await s.commit()
    wrong = [
        b
        for b in await u._batches(world["tgt"], world["drug_a"])
        if b.branch_id == world["tgt"]
    ][0]

    tid = (await _draft(world))["id"]
    line_id = (
        await u._transfer(tid)
    )[1][0].id
    r = await client.post(
        f"/api/v1/transfers/{tid}/dispatch",
        headers=u._headers(world["src_token"]),
        json={"lines": [{"line_id": line_id, "allocations": [{"batch_id": wrong.id, "qty": "2"}]}]},
    )
    assert r.status_code == 400


# ---------- ST-13: expired lots CAN be moved between pharmacies (pinned) ----------

async def test_expired_batch_dispatch_allowed_pinned(world):
    """Titan parity: inter-pharmacy moves may include near/expired stock —
    the receiving pharmacist inspects on arrival. FEFO never *suggests*
    expired first (NULLS LAST ordering is by date, not vs today), so pin via
    explicit allocation."""
    client = world["client"]
    async with SessionLocal() as s:
        s.add(
            StockBatch(
                branch_id=world["src"],
                drug_id=world["drug_a"],
                randomid=u._uniq("expired"),
                qty=5,
                cost=3,
                expire=__import__("datetime").date(2020, 1, 1),
            )
        )
        bs = await s.execute(
            select(BranchStock).where(
                BranchStock.branch_id == world["src"], BranchStock.drug_id == world["drug_a"]
            )
        )
        bs.scalar_one().qty += 5
        await s.commit()
    expired = [b for b in await u._batches(world["src"], world["drug_a"]) if b.expire and b.expire.year == 2020][0]

    tid = (await _draft(world))["id"]
    line_id = (await u._transfer(tid))[1][0].id
    r = await client.post(
        f"/api/v1/transfers/{tid}/dispatch",
        headers=u._headers(world["src_token"]),
        json={"lines": [{"line_id": line_id, "allocations": [{"batch_id": expired.id, "qty": "2"}]}]},
    )
    assert r.status_code == 200, r.text


# ---------- CC-2: two receives, SAME randomid → merge, never 500 ----------

async def test_concurrent_receive_same_randomid_merges_into_one_row(world):
    """Both source batches share one forced randomid; both transfers land on
    the same target drug concurrently. Before the per-target advisory receive
    lock the loser died on uq_stock_batches / BranchStock PK with a 500."""
    client = world["client"]
    # ONE source lot split across TWO shipments: both transfers carry the
    # same randomid to the target, and both receives run concurrently.
    rid = u._uniq("RACE")
    async with SessionLocal() as s:
        s.add(
            StockBatch(
                branch_id=world["src"], drug_id=world["drug_a"], randomid=rid,
                qty=12, cost=5, expire=None,
            )
        )
        bs = await s.execute(
            select(BranchStock).where(
                BranchStock.branch_id == world["src"], BranchStock.drug_id == world["drug_a"]
            )
        )
        bs.scalar_one().qty = 12
        await s.commit()

    tids = []
    allocs = []
    for _ in range(2):
        r = await client.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={"target_branch_id": world["tgt"], "lines": [{"drug_id": world["drug_a"], "qty": "6"}]},
        )
        assert r.status_code == 201, r.text
        draft = r.json()
        tids.append(draft["id"])
        world["_transfer_ids"].append(draft["id"])
        line_id = draft["lines"][0]["id"]
        batch = [
            b for b in await u._batches(world["src"], world["drug_a"]) if b.randomid == rid
        ][0]
        rd = await client.post(
            f"/api/v1/transfers/{draft['id']}/dispatch",
            headers=u._headers(world["src_token"]),
            json={"lines": [{"line_id": line_id, "allocations": [{"batch_id": batch.id, "qty": "6"}]}]},
        )
        assert rd.status_code == 200, rd.text
        allocs.append({"line_id": line_id, "received_qty": "6"})
    assert len(tids) == 2

    results = await asyncio.gather(*[
        client.post(
            f"/api/v1/transfers/{tid}/receive",
            headers=u._headers(world["tgt_token"]),
            json={"lines": [receipt]},
        )
        for tid, receipt in zip(tids, allocs)
    ])
    assert all(r.status_code == 200 for r in results), [r.text for r in results]

    landed = [
        b for b in await u._batches(world["tgt"], world["drug_a"]) if b.randomid == rid
    ]
    assert len(landed) == 1, "same-randomid receives must merge into ONE row"
    assert float(landed[0].qty) == 12.0
    assert float(await u._stock_qty(world["tgt"], world["drug_a"])) == 12.0


# ---------- VA-9: inactive SOURCE branch cannot create drafts ----------

async def test_inactive_source_branch_cannot_create_draft(world):
    client = world["client"]
    async with SessionLocal() as s:
        src = await s.get(Branch, world["src"])
        src.is_active = False
        await s.commit()
    r = await client.post(
        "/api/v1/transfers",
        headers=u._headers(world["src_token"]),
        json={
            "target_branch_id": world["tgt"],
            "lines": [{"drug_id": world["drug_a"], "qty": "1"}],
        },
    )
    assert r.status_code == 400 and "inactive" in r.json()["detail"]


# ---------- CC-3: opposite-order multi-line dispatches never deadlock ----------

async def test_concurrent_opposite_order_multiline_dispatch(world):
    """Two same-source transfers whose lines were created in opposite drug
    order must both dispatch: lock order is deterministic (sorted by drug_id),
    so the second waits instead of cross-locking."""
    client = world["client"]
    drug_b = await u._make_drug_with_stock(
        branch_id=world["src"], stock_qty="10", batches=[("10", "8", "2027-09-01")]
    )
    world["_drug_ids"].append(drug_b)

    drafts = []
    for order in [(world["drug_a"], drug_b), (drug_b, world["drug_a"])]:
        r = await client.post(
            "/api/v1/transfers",
            headers=u._headers(world["src_token"]),
            json={
                "target_branch_id": world["tgt"],
                "lines": [
                    {"drug_id": d, "qty": "2" if d == world["drug_a"] else "3"}
                    for d in order
                ],
            },
        )
        assert r.status_code == 201, r.text
        drafts.append(r.json())
        world["_transfer_ids"].append(r.json()["id"])
    # line ids really are in opposite drug order across the two transfers
    order_1 = [ln["drug_id"] for ln in sorted(drafts[0]["lines"], key=lambda l: l["id"])]
    order_2 = [ln["drug_id"] for ln in sorted(drafts[1]["lines"], key=lambda l: l["id"])]
    assert order_1 != order_2

    results = await asyncio.gather(*[
        client.post(
            f"/api/v1/transfers/{d['id']}/dispatch",
            headers=u._headers(world["src_token"]),
            json={},
        )
        for d in drafts
    ])
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert await u._stock_qty(world["src"], world["drug_a"]) == 16
    assert await u._stock_qty(world["src"], drug_b) == 4


# ---------- RB-4: level-2 on own branch can READ (writes stay blocked) ----------

async def test_level2_own_branch_reads_allowed_writes_blocked(world):
    client = world["client"]
    name = u._uniq("l2reader")
    uid = await u._make_user(name, level=2, branch_id=world["src"])
    world["_user_ids"].append(uid)
    tok = await u._login_token(client, name)
    tid = (await _draft(world))["id"]

    r = await client.get("/api/v1/transfers", headers=u._headers(tok))
    assert r.status_code == 200
    assert len(r.json()["transfers"]) == 1

    r = await client.get(f"/api/v1/transfers/{tid}", headers=u._headers(tok))
    assert r.status_code == 200

    r = await client.post(
        f"/api/v1/transfers/{tid}/dispatch", headers=u._headers(tok), json={}
    )
    assert r.status_code == 403
