"""S1.2 search-as-you-type (ticket #8 AC2).

Active drugs matched by name AR/EN (case-insensitive ILIKE) or barcode prefix;
empty query returns []; inactive drugs are excluded. Wildcards in user input
(`%`/`_`) are escaped so they match literally.
"""
from sqlalchemy import delete

from app.auth.security import create_access_token
from app.core.db import SessionLocal
from app.models import AuditLog, Drug, DrugBarcode, PriceChangeLog, User

PREFIX = "__t8_search_"


def _token_for(user_id: int, branch_id: int) -> str:
    return create_access_token(
        str(user_id), branch_id=branch_id, roles=["admin"], permission_level=9
    )


async def _login(client) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create(client, token: str, *, name: str, **extra) -> int:
    payload = {"drugname": name}
    payload.update(extra)
    r = await client.post("/api/v1/drugs", headers=_auth(token), json=payload)
    assert r.status_code == 201
    return r.json()["id"]


async def _cleanup_drug_ids(*drug_ids: int) -> None:
    if not drug_ids:
        return
    async with SessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.drug_id.in_(drug_ids)))
        await session.execute(delete(PriceChangeLog).where(PriceChangeLog.drug_id.in_(drug_ids)))
        await session.execute(delete(DrugBarcode).where(DrugBarcode.drug_id.in_(drug_ids)))
        await session.execute(delete(Drug).where(Drug.id.in_(drug_ids)))
        await session.commit()


async def test_search_returns_empty_for_blank_query(client):
    token = await _login(client)
    for q in ("", "   "):
        r = await client.get(
            "/api/v1/drugs/search", headers=_auth(token), params={"q": q}
        )
        assert r.status_code == 200
        assert r.json()["drugs"] == []


async def test_search_by_english_name_fragment(client):
    token = await _login(client)
    r = await client.get(
        "/api/v1/drugs/search", headers=_auth(token), params={"q": "panad"}
    )
    assert r.status_code == 200
    names = [d["drugname"] for d in r.json()["drugs"]]
    assert "Panadol Extra" in names


async def test_search_case_insensitive(client):
    token = await _login(client)
    r = await client.get(
        "/api/v1/drugs/search", headers=_auth(token), params={"q": "PANADOL"}
    )
    names = [d["drugname"] for d in r.json()["drugs"]]
    assert "Panadol Extra" in names


async def test_search_by_arabic_name_fragment(client):
    token = await _login(client)
    r = await client.get(
        "/api/v1/drugs/search", headers=_auth(token), params={"q": "باناد"}
    )
    names = [d["drugname"] for d in r.json()["drugs"]]
    assert "Panadol Extra" in names


async def test_search_by_barcode_prefix(client):
    token = await _login(client)
    drug_id = await _create(
        client, token, name=f"{PREFIX}barcode", barcodes=["6291041500056"]
    )
    try:
        r = await client.get(
            "/api/v1/drugs/search", headers=_auth(token), params={"q": "629104"}
        )
        assert r.status_code == 200
        found = [d for d in r.json()["drugs"] if d["id"] == drug_id]
        assert found, "search matches the barcode prefix"
        assert found[0]["barcodes"] == ["6291041500056"]
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_search_no_match_returns_empty(client):
    token = await _login(client)
    r = await client.get(
        "/api/v1/drugs/search", headers=_auth(token), params={"q": "zzzzz-not-a-drug"}
    )
    assert r.status_code == 200
    assert r.json()["drugs"] == []


async def test_search_respects_limit(client):
    token = await _login(client)
    ids = [
        await _create(client, token, name=f"{PREFIX}lim 1"),
        await _create(client, token, name=f"{PREFIX}lim 2"),
        await _create(client, token, name=f"{PREFIX}lim 3"),
    ]
    try:
        r = await client.get(
            "/api/v1/drugs/search",
            headers=_auth(token),
            params={"q": f"{PREFIX}lim", "limit": 2},
        )
        assert r.status_code == 200
        assert len(r.json()["drugs"]) <= 2

        r = await client.get(
            "/api/v1/drugs/search",
            headers=_auth(token),
            params={"q": f"{PREFIX}lim"},
        )
        assert len(r.json()["drugs"]) == 3
    finally:
        await _cleanup_drug_ids(*ids)


async def test_search_excludes_inactive_drugs(client):
    token = await _login(client)
    async with SessionLocal() as session:
        drug = Drug(drugname=f"{PREFIX}ghost", active=False)
        session.add(drug)
        await session.commit()
        ghost_id = drug.id
    try:
        r = await client.get(
            "/api/v1/drugs/search", headers=_auth(token), params={"q": f"{PREFIX}ghost"}
        )
        assert r.json()["drugs"] == []
    finally:
        await _cleanup_drug_ids(ghost_id)


async def test_search_matches_wildcards_literally(client):
    token = await _login(client)
    drug_id = await _create(client, token, name=f"{PREFIX}100% Pure")
    try:
        r = await client.get(
            "/api/v1/drugs/search",
            headers=_auth(token),
            params={"q": f"{PREFIX}100%"},
        )
        assert r.status_code == 200
        assert any(d["id"] == drug_id for d in r.json()["drugs"])
    finally:
        await _cleanup_drug_ids(drug_id)


async def test_search_requires_auth(client):
    r = await client.get("/api/v1/drugs/search", params={"q": "panad"})
    assert r.status_code == 401


async def test_search_limits_capped(client):
    token = await _login(client)
    r = await client.get(
        "/api/v1/drugs/search", headers=_auth(token), params={"q": "panad", "limit": 9999}
    )
    assert r.status_code == 200
    assert len(r.json()["drugs"]) <= 200