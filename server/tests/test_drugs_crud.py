"""S1.2 drug-master write slice (ticket #8): CRUD + permission gating.

Writes carry the AGENTS.md discipline — every mutation writes its audit_log row
and price changes a price_change_log row, all in the caller's transaction
(plan/02 §4.6, G12). Duplicate drugname / duplicate barcode surface as 409
(partial-unique indexes, plan/01 §1.3#4). Writes are gated by `drugs.manage`
(legacy level-3 area, plan/02 §3) — level 2 denied, level 3+ allowed, admin
(level 9 + role) allowed.
"""
import uuid
from sqlalchemy import delete, func, select

from app.auth.security import create_access_token
from app.core.db import SessionLocal
from app.models import AuditLog, Drug, DrugBarcode, PriceChangeLog, User

PREFIX = "__t8_"


def _token_for(user_id: int, branch_id: int) -> str:
    return create_access_token(
        str(user_id), branch_id=branch_id, roles=["admin"], permission_level=9
    )


async def _make_user(username: str, *, level: int) -> int:
    async with SessionLocal() as session:
        user = User(
            username=username,
            pass_hash="x",
            permission_level=level,
            branch_id=1,
            active=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
        return user_id


async def _cleanup_users(*usernames: str) -> None:
    async with SessionLocal() as session:
        ids = (
            await session.execute(select(User.id).where(User.username.in_(usernames)))
        ).scalars().all()
        if ids:
            await session.execute(delete(User).where(User.id.in_(ids)))
            await session.commit()


async def _login(client, username: str = "admin", password: str = "changeme") -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _cleanup_drug_ids(*drug_ids: int) -> None:
    if not drug_ids:
        return
    async with SessionLocal() as session:
        await session.execute(
            delete(AuditLog).where(AuditLog.drug_id.in_(drug_ids))
        )
        await session.execute(
            delete(PriceChangeLog).where(PriceChangeLog.drug_id.in_(drug_ids))
        )
        await session.execute(
            delete(DrugBarcode).where(DrugBarcode.drug_id.in_(drug_ids))
        )
        await session.execute(delete(Drug).where(Drug.id.in_(drug_ids)))
        await session.commit()


# ---------------------------------------------------------------------------
# create / read roundtrip
# ---------------------------------------------------------------------------
async def test_create_drug_roundtrip(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={
            "drugname": f"{PREFIX}roundtrip",
            "drugnamear": "بانادول إكسترا",
            "generic": "Paracetamol",
            "classy": "Analgesic",
            "co": "GSK",
            "unitsclass": "Oral",
            "tax_type": "14%",
            "units": 1,
            "unitsmall": 10,
            "price": "100.00",
            "price_wholesale": "90.00",
            "price_cost": "80.00",
            "barcodes": ["6291041500056", "6291041500057"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    drug_id = body["id"]
    try:
        assert body["drugname"] == f"{PREFIX}roundtrip"
        assert body["drugnamear"] == "بانادول إكسترا"
        assert body["tax_type"] == "14%"
        assert body["price"] == "100.00"
        assert body["price_wholesale"] == "90.00"
        assert body["price_cost"] == "80.00"
        assert body["price_now"] == "100.00", "price_now defaults to public price"
        assert body["barcodes"] == ["6291041500056", "6291041500057"]
        assert body["active"] is True

        got = await client.get(f"/api/v1/drugs/{drug_id}", headers=_auth(token))
        assert got.status_code == 200
        assert got.json() == body
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_create_sets_price_now_default_and_preserves_explicit(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}price_now_default"},
    )
    assert r.status_code == 201
    assert r.json()["price_now"] == "0.00"
    default_id = r.json()["id"]

    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={
            "drugname": f"{PREFIX}price_now_explicit",
            "price": "50.00",
            "price_now": "45.00",
        },
    )
    assert r.status_code == 201
    assert r.json()["price_now"] == "45.00"
    explicit_id = r.json()["id"]
    try:
        assert r.json()["price"] == "50.00"
    finally:
        await _cleanup_drug_ids(default_id, explicit_id)


async def test_create_writes_audit_and_price_change_log(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}audited", "price": "12.50"},
    )
    assert r.status_code == 201
    drug_id = r.json()["id"]
    try:
        async with SessionLocal() as session:
            audit_count = (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.drug_id == drug_id,
                        AuditLog.action == "insert",
                        AuditLog.field == "drugname",
                    )
                )
            ).scalar_one()
            assert audit_count == 1
            price_log_count = (
                await session.execute(
                    select(func.count())
                    .select_from(PriceChangeLog)
                    .where(PriceChangeLog.drug_id == drug_id)
                )
            ).scalar_one()
            assert price_log_count == 1
    finally:
        await _cleanup_drug_ids(drug_id)


# ---------------------------------------------------------------------------
# validation failures (plan/02 §3: validation → 400)
# ---------------------------------------------------------------------------
async def test_create_requires_drugname(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs", headers=_auth(token), json={"drugname": ""}
    )
    assert r.status_code == 400
    r = await client.post("/api/v1/drugs", headers=_auth(token), json={})
    assert r.status_code == 400


async def test_create_rejects_negative_and_huge_prices(client):
    token = await _login(client)
    for payload in (
        {"drugname": f"{PREFIX}neg", "price": "-0.01"},
        {"drugname": f"{PREFIX}neg2", "price_wholesale": "-1"},
        {"drugname": f"{PREFIX}neg3", "price_cost": "-5.00"},
        {"drugname": f"{PREFIX}huge", "price": "9999999999999999999999.00"},
        {"drugname": f"{PREFIX}dp", "price": "1.23456789"},
        {"drugname": f"{PREFIX}garbage", "price": "abc"},
    ):
        r = await client.post("/api/v1/drugs", headers=_auth(token), json=payload)
        assert r.status_code == 400, payload


async def test_create_accepts_huge_but_valid_price(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}big", "price": "99999999999999.00"},
    )
    assert r.status_code == 201
    try:
        assert r.json()["price"] == "99999999999999.00"
    finally:
        await _cleanup_drug_ids(r.json()["id"])


async def test_create_rejects_invalid_tax_type_and_seventh_barcode(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}bad_tax", "tax_type": "10%"},
    )
    assert r.status_code == 400
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={
            "drugname": f"{PREFIX}many_bc",
            "barcodes": [f"bc{i}" for i in range(7)],
        },
    )
    assert r.status_code == 400


async def test_create_duplicate_name_409(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}dup_name"},
    )
    assert r.status_code == 201
    first_id = r.json()["id"]
    try:
        r = await client.post(
            "/api/v1/drugs",
            headers=_auth(token),
            json={"drugname": f"{PREFIX}dup_name"},
        )
        assert r.status_code == 409
    finally:
        await _cleanup_drug_ids(first_id)


async def test_create_duplicate_barcode_409(client):
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}bc_a", "barcodes": ["1112223334445"]},
    )
    assert r.status_code == 201
    first_id = r.json()["id"]
    try:
        r = await client.post(
            "/api/v1/drugs",
            headers=_auth(token),
            json={"drugname": f"{PREFIX}bc_b", "barcodes": ["1112223334445"]},
        )
        assert r.status_code == 409
    finally:
        await _cleanup_drug_ids(first_id)


async def test_create_rejects_blank_barcodes(client):
    """Empty-string barcodes are dropped; whitespace-only entries don't count."""
    token = await _login(client)
    r = await client.post(
        "/api/v1/drugs",
        headers=_auth(token),
        json={"drugname": f"{PREFIX}blank_bc", "barcodes": ["", "  ", "6291041500056"]},
    )
    assert r.status_code == 201
    try:
        assert r.json()["barcodes"] == ["6291041500056"]
    finally:
        await _cleanup_drug_ids(r.json()["id"])


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
async def _create(client, token: str, *, name: str | None = None, **extra) -> int:
    payload = {"drugname": name or f"{PREFIX}update_target_{uuid.uuid4().hex[:6]}"}
    payload.update(extra)
    r = await client.post("/api/v1/drugs", headers=_auth(token), json=payload)
    assert r.status_code == 201
    return r.json()["id"]


async def test_update_renames_with_audit(client):
    token = await _login(client)
    source_name = f"{PREFIX}rename_source"
    drug_id = await _create(client, token, name=source_name)
    try:
        r = await client.patch(
            f"/api/v1/drugs/{drug_id}",
            headers=_auth(token),
            json={"drugname": f"{PREFIX}renamed"},
        )
        assert r.status_code == 200
        assert r.json()["drugname"] == f"{PREFIX}renamed"

        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.drug_id == drug_id,
                        AuditLog.field == "drugname",
                        AuditLog.action == "update",
                    )
                    .order_by(AuditLog.id)
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[-1].old_value == source_name
            assert rows[-1].new_value == f"{PREFIX}renamed"
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_update_price_logs_change(client):
    token = await _login(client)
    drug_id = await _create(client, token, price="10.00")
    try:
        r = await client.patch(
            f"/api/v1/drugs/{drug_id}",
            headers=_auth(token),
            json={"price": "15.50", "price_wholesale": "13.00", "price_cost": "11.00"},
        )
        assert r.status_code == 200
        assert r.json()["price"] == "15.50"
        assert r.json()["price_wholesale"] == "13.00"
        assert r.json()["price_cost"] == "11.00"

        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(PriceChangeLog)
                    .where(PriceChangeLog.drug_id == drug_id)
                    .order_by(PriceChangeLog.id)
                )
            ).scalars().all()
            assert len(rows) == 2, "one price_change_log per create, one per price change"
            assert rows[-1].price == 15.50
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_update_same_price_no_extra_price_change_log(client):
    token = await _login(client)
    drug_id = await _create(client, token, price="10.00")
    try:
        r = await client.patch(
            f"/api/v1/drugs/{drug_id}", headers=_auth(token), json={"price": "10.00"}
        )
        assert r.status_code == 200
        async with SessionLocal() as session:
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(PriceChangeLog)
                    .where(PriceChangeLog.drug_id == drug_id)
                )
            ).scalar_one()
            assert count == 1, "no-op price update writes no new log row"
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_update_barcodes_replaces_set(client):
    token = await _login(client)
    drug_id = await _create(client, token, barcodes=["1112223334445"])
    try:
        r = await client.patch(
            f"/api/v1/drugs/{drug_id}",
            headers=_auth(token),
            json={"barcodes": ["9998887776665", "5554443332221"]},
        )
        assert r.status_code == 200
        assert r.json()["barcodes"] == ["9998887776665", "5554443332221"]
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_update_duplicate_name_409(client):
    token = await _login(client)
    first = await _create(client, token, drugname=f"{PREFIX}uname_a")
    second = await _create(client, token, drugname=f"{PREFIX}uname_b")
    try:
        r = await client.patch(
            f"/api/v1/drugs/{second}",
            headers=_auth(token),
            json={"drugname": f"{PREFIX}uname_a"},
        )
        assert r.status_code == 409
    finally:
        await _cleanup_drug_ids(first, second)


async def test_update_duplicate_barcode_409(client):
    token = await _login(client)
    first = await _create(
        client, token, name=f"{PREFIX}ubc_a", barcodes=["7778889990001"]
    )
    second = await _create(client, token, name=f"{PREFIX}ubc_b")
    try:
        r = await client.patch(
            f"/api/v1/drugs/{second}",
            headers=_auth(token),
            json={"barcodes": ["7778889990001"]},
        )
        assert r.status_code == 409
    finally:
        await _cleanup_drug_ids(first, second)


async def test_update_not_found_404(client):
    token = await _login(client)
    r = await client.patch(
        f"/api/v1/drugs/99999999",
        headers=_auth(token),
        json={"drugname": "nope"},
    )
    assert r.status_code == 404


async def test_get_not_found_404(client):
    token = await _login(client)
    r = await client.get("/api/v1/drugs/99999999", headers=_auth(token))
    assert r.status_code == 404


async def test_read_requires_auth(client):
    r = await client.get("/api/v1/drugs/1")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# permission gating (plan/02 §3: drugs.manage, legacy floor 3)
# ---------------------------------------------------------------------------
async def test_write_requires_authentication(client):
    r = await client.post("/api/v1/drugs", json={"drugname": f"{PREFIX}nope"})
    assert r.status_code == 401


async def test_write_denied_below_floor_403(client):
    user_id = await _make_user(f"{PREFIX}low", level=2)
    try:
        r = await client.post(
            "/api/v1/drugs",
            headers=_auth(_token_for(user_id, 1)),
            json={"drugname": f"{PREFIX}denied"},
        )
        assert r.status_code == 403
    finally:
        await _cleanup_users(f"{PREFIX}low")


async def test_write_allowed_at_floor_3(client):
    user_id = await _make_user(f"{PREFIX}mid", level=3)
    try:
        r = await client.post(
            "/api/v1/drugs",
            headers=_auth(_token_for(user_id, 1)),
            json={"drugname": f"{PREFIX}floor3"},
        )
        assert r.status_code == 201
        try:
            assert r.json()["drugname"] == f"{PREFIX}floor3"
        finally:
            await _cleanup_drug_ids(r.json()["id"])
    finally:
        await _cleanup_users(f"{PREFIX}mid")