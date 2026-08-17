"""S1.2 CC0 catalog import (ticket #8 AC3).

The import job de-dupes against the existing drug master and is idempotent:
re-running the same file adds nothing. Duplicate barcodes win over names; both
dedupe within the batch and against the DB. Malformed rows are skipped and
reported (never fatal); the whole batch commits atomically. Source is the CC0
`karem505/egyptian-drug-database` (G03) — see server/app/drugs/importer.py.
"""
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.auth.security import create_access_token
from app.core.db import SessionLocal
from app.models import AuditLog, Drug, DrugBarcode, PriceChangeLog, User

FIXTURE = Path(__file__).parent / "fixtures" / "cc0_catalog_sample.csv"
PREFIX = "__t8_import_"

SAMPLE = (
    "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,drug_class,"
    "route,price_egp,barcodes,tax_type,price_wholesale,price_cost\n"
    f"{PREFIX}a,أ,Paracetamol,X,Analgesic,Oral,10.00,7770000000011,exempt,9.00,8.00\n"
    f"{PREFIX}b,ب,Amoxicillin,X,Antibiotic,Oral,20.00,,14%,18.00,15.00\n"
)


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


async def _cleanup_prefix() -> None:
    """Remove every row this suite created (drugs, barcodes, audit, price log)."""
    async with SessionLocal() as session:
        ids = (
            await session.execute(select(Drug.id).where(Drug.drugname.like(f"{PREFIX}%")))
        ).scalars().all()
        if ids:
            await session.execute(delete(AuditLog).where(AuditLog.drug_id.in_(ids)))
            await session.execute(
                delete(PriceChangeLog).where(PriceChangeLog.drug_id.in_(ids))
            )
            await session.execute(
                delete(DrugBarcode).where(DrugBarcode.drug_id.in_(ids))
            )
            await session.execute(delete(Drug).where(Drug.id.in_(ids)))
            await session.commit()


@pytest.fixture(autouse=True)
async def _clean_state():
    """The dedupe semantics make this suite sensitive to leftover rows (e.g. an
    earlier interrupted run) — clear the shared prefix before every test."""
    await _cleanup_prefix()
    yield
    await _cleanup_prefix()


async def _import(client, token: str, csv_text: str):
    return await client.post(
        "/api/v1/drugs/import",
        headers={**_auth(token), "Content-Type": "text/csv"},
        content=csv_text,
    )


async def test_import_inserts_rows_and_reports(client):
    token = await _login(client)
    try:
        r = await _import(client, token, SAMPLE)
        assert r.status_code == 200
        body = r.json()
        assert body["inserted"] == 2
        assert body["skipped_duplicate_barcode"] == 0
        assert body["skipped_duplicate_name"] == 0
        assert body["skipped_malformed"] == 0
        assert sorted(body["inserted_names"]) == sorted([f"{PREFIX}a", f"{PREFIX}b"])

        got = await client.get(
            "/api/v1/drugs/search", headers=_auth(token), params={"q": PREFIX}
        )
        names = [d["drugname"] for d in got.json()["drugs"]]
        assert f"{PREFIX}a" in names
        assert f"{PREFIX}b" in names

        async with SessionLocal() as session:
            for name in (f"{PREFIX}a", f"{PREFIX}b"):
                drug_id = (
                    await session.execute(select(Drug.id).where(Drug.drugname == name))
                ).scalar_one()
                audit_count = (
                    await session.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(
                            AuditLog.drug_id == drug_id, AuditLog.action == "insert"
                        )
                    )
                ).scalar_one()
                assert audit_count == 1, "each import row writes its audit row"
                price_log = (
                    await session.execute(
                        select(PriceChangeLog).where(PriceChangeLog.drug_id == drug_id)
                    )
                ).scalar_one()
                assert price_log.price == 10.00 or price_log.price == 20.00
    finally:
        await _cleanup_prefix()


async def test_import_is_idempotent(client):
    token = await _login(client)
    try:
        first = await _import(client, token, SAMPLE)
        assert first.json()["inserted"] == 2
        second = await _import(client, token, SAMPLE)
        assert second.status_code == 200
        assert second.json()["inserted"] == 0
        # row a re-collides on its barcode, row b (no barcode) on its name
        assert second.json()["skipped_duplicate_barcode"] == 1
        assert second.json()["skipped_duplicate_name"] == 1
    finally:
        await _cleanup_prefix()


async def test_import_duplicate_barcode_wins_over_name(client):
    token = await _login(client)
    try:
        await _import(client, token, SAMPLE)
        # same barcode as 7770000000011 but a different name -> barcode dedupe
        clash = (
            "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,"
            "drug_class,route,price_egp,barcodes,tax_type,price_wholesale,price_cost\n"
            f"{PREFIX}other,أخر,Paracetamol,X,Analgesic,Oral,10.00,7770000000011,exempt,9.00,8.00,\n"
        )
        r = await _import(client, token, clash)
        assert r.status_code == 200
        assert r.json()["inserted"] == 0
        assert r.json()["skipped_duplicate_barcode"] == 1
        assert r.json()["skipped_duplicate_name"] == 0
    finally:
        await _cleanup_prefix()


async def test_import_dedupes_within_batch(client):
    token = await _login(client)
    dup_csv = (
        "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,"
        "drug_class,route,price_egp,barcodes,tax_type,price_wholesale,price_cost\n"
        f"{PREFIX}same,أ,Paracetamol,X,Analgesic,Oral,10.00,7770000000021,exempt,9.00,8.00,\n"
        f"{PREFIX}same,أ,Paracetamol,X,Analgesic,Oral,10.00,7770000000022,exempt,9.00,8.00,\n"
    )
    try:
        r = await _import(client, token, dup_csv)
        assert r.status_code == 200
        assert r.json()["inserted"] == 1
        assert r.json()["skipped_duplicate_name"] == 1
    finally:
        await _cleanup_prefix()


async def test_import_malformed_rows_skipped_and_reported(client):
    token = await _login(client)
    bad_csv = (
        "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,"
        "drug_class,route,price_egp,barcodes,tax_type,price_wholesale,price_cost\n"
        f"{PREFIX}good,جيد,Paracetamol,X,Analgesic,Oral,10.00,7770000000031,exempt,9.00,8.00,\n"
        ",مفقود,Paracetamol,X,Analgesic,Oral,10.00,,exempt,9.00,8.00,\n"
        f"{PREFIX}neg,سلبي,Paracetamol,X,Analgesic,Oral,-5.00,,exempt,9.00,8.00,\n"
        f"{PREFIX}tax,ضريبة,Paracetamol,X,Analgesic,Oral,10.00,,10%,9.00,8.00,\n"
        f"{PREFIX}many,كثير,Paracetamol,X,Analgesic,Oral,10.00,b1|b2|b3|b4|b5|b6|b7,exempt,9.00,8.00,\n"
    )
    try:
        r = await _import(client, token, bad_csv)
        assert r.status_code == 200
        body = r.json()
        assert body["inserted"] == 1
        assert body["skipped_malformed"] == 4
        assert body["errors"] and any("row " in e for e in body["errors"])
        got = await client.get(
            "/api/v1/drugs/search", headers=_auth(token), params={"q": f"{PREFIX}good"}
        )
        assert len(got.json()["drugs"]) == 1
    finally:
        await _cleanup_prefix()


async def test_import_defaults_price_zero_and_tax_exempt(client):
    token = await _login(client)
    minimal = (
        "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,"
        "drug_class,route,price_egp,barcodes,tax_type,price_wholesale,price_cost\n"
        f"{PREFIX}minimal,,,,,,,7770000000041,exempt,,\n"
    )
    try:
        r = await _import(client, token, minimal)
        assert r.status_code == 200
        assert r.json()["inserted"] == 1
        got = await client.get(
            "/api/v1/drugs/search", headers=_auth(token), params={"q": f"{PREFIX}minimal"}
        )
        drug = got.json()["drugs"][0]
        assert drug["price"] == "0.00"
        assert drug["price_wholesale"] == "0.00"
        assert drug["price_cost"] == "0.00"
        assert drug["tax_type"] == "exempt"
    finally:
        await _cleanup_prefix()


async def test_import_empty_csv_400(client):
    token = await _login(client)
    r = await _import(client, token, "")
    assert r.status_code == 400


async def test_import_header_only_inserts_nothing(client):
    token = await _login(client)
    header_only = (
        "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,"
        "drug_class,route,price_egp,barcodes,tax_type,price_wholesale,price_cost\n"
    )
    r = await _import(client, token, header_only)
    assert r.status_code == 200
    assert r.json()["inserted"] == 0


async def test_import_requires_authentication(client):
    r = await _import(client, "", SAMPLE)
    assert r.status_code == 401


async def test_import_denied_below_floor_403(client):
    user_id = await _make_user(f"{PREFIX}low", level=2)
    try:
        r = await _import(client, _token_for(user_id, 1), SAMPLE)
        assert r.status_code == 403
    finally:
        await _cleanup_users(f"{PREFIX}low")