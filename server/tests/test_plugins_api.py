"""Plugin registry API (ticket #3 AC1): list / enable / disable per branch.

Management endpoints are authenticated (existing Bearer scaffold) and audited
(action plugin_enable / plugin_disable in audit_log).
"""
import pytest
from sqlalchemy import delete, update

from app.core.db import SessionLocal
from app.models import AppConfig, AppPlugin, AuditLog, Branch, PluginBranchGrant
from app.plugins.registry import registry

BRANCH_ID = 1


@pytest.fixture
async def seeded(client):
    async with SessionLocal() as session:
        await session.execute(update(AppPlugin).values(status="installed"))
        await session.execute(update(PluginBranchGrant).values(enabled=False))
        cfg = await session.get(AppConfig, "plugins_enabled")
        cfg.value = "true"
        await session.commit()
        await registry.load(session)
    yield client


async def _token(client) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert r.status_code == 200
    return r.json()["access_token"]


async def _auth(client) -> dict:
    return {"Authorization": f"Bearer {await _token(client)}"}


async def test_list_requires_auth(client):
    r = await client.get("/api/v1/system/plugins")
    assert r.status_code == 401


async def test_list_plugins_shows_installed_with_grants(seeded):
    r = await seeded.get("/api/v1/system/plugins", headers=await _auth(seeded))
    assert r.status_code == 200
    body = r.json()["plugins"]
    assert {p["slug"] for p in body} == {"pharmatag-eta", "pharmatag-ledger"}
    eta = next(p for p in body if p["slug"] == "pharmatag-eta")
    assert eta["status"] == "installed"
    assert eta["validation"]["ok"] is True
    assert eta["branch_grants"] == {"1": False}
    assert eta["active"] is False


async def test_enable_plugin_for_branch(seeded):
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/enable",
        json={"branch_id": BRANCH_ID},
        headers=await _auth(seeded),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "pharmatag-eta"
    assert body["enabled"] is True

    r = await seeded.get("/api/v1/system/plugins", headers=await _auth(seeded))
    eta = next(p for p in r.json()["plugins"] if p["slug"] == "pharmatag-eta")
    assert eta["status"] == "enabled"
    assert eta["branch_grants"] == {"1": True}
    assert eta["active"] is True


async def test_disable_plugin_for_branch(seeded):
    h = await _auth(seeded)
    await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/enable",
        json={"branch_id": BRANCH_ID},
        headers=h,
    )
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/disable",
        json={"branch_id": BRANCH_ID},
        headers=h,
    )
    assert r.status_code == 200

    r = await seeded.get("/api/v1/system/plugins", headers=h)
    eta = next(p for p in r.json()["plugins"] if p["slug"] == "pharmatag-eta")
    assert eta["status"] == "disabled"
    assert eta["branch_grants"] == {"1": False}
    assert eta["active"] is False


async def test_enable_refuses_a_broken_manifest(seeded):
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-ledger/enable",
        json={"branch_id": BRANCH_ID},
        headers=await _auth(seeded),
    )
    assert r.status_code == 400
    assert "not found" in r.json()["detail"]


async def test_enable_unknown_plugin_returns_404(seeded):
    r = await seeded.post(
        "/api/v1/system/plugins/ghost/enable",
        json={"branch_id": BRANCH_ID},
        headers=await _auth(seeded),
    )
    assert r.status_code == 404


async def test_disable_unknown_plugin_returns_404(seeded):
    r = await seeded.post(
        "/api/v1/system/plugins/ghost/disable",
        json={"branch_id": BRANCH_ID},
        headers=await _auth(seeded),
    )
    assert r.status_code == 404


async def test_enable_and_disable_require_auth(seeded):
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/enable", json={"branch_id": BRANCH_ID}
    )
    assert r.status_code == 401
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/disable", json={"branch_id": BRANCH_ID}
    )
    assert r.status_code == 401


async def test_enable_requires_branch_id_and_rejects_zero(seeded):
    h = await _auth(seeded)
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/enable", json={}, headers=h
    )
    assert r.status_code == 400, "missing branch_id is a validation error, not a silent enable"
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/enable",
        json={"branch_id": 0},
        headers=h,
    )
    assert r.status_code == 400, "branch_id must be > 0"
    r = await seeded.post(
        "/api/v1/system/plugins/pharmatag-eta/disable",
        json={"branch_id": 0},
        headers=h,
    )
    assert r.status_code == 400


async def test_enable_plugin_for_another_branch_is_forbidden(seeded):
    """Branch-scoped authz: the caller may only manage their own branch's grant
    (plan/02 §3: cross-branch access is a permission, not a default)."""
    branch_2_id: int = 0
    async with SessionLocal() as session:
        branch_2 = Branch(pharmacyid="__t3_api_b2__", mobile="0", pharname="Branch 2")
        session.add(branch_2)
        await session.flush()
        branch_2_id = branch_2.id
        await session.commit()
    try:
        h = await _auth(seeded)  # admin is on branch 1
        r = await seeded.post(
            "/api/v1/system/plugins/pharmatag-eta/enable",
            json={"branch_id": branch_2_id},
            headers=h,
        )
        assert r.status_code == 403, "must not enable another branch's grant"
        r = await seeded.post(
            "/api/v1/system/plugins/pharmatag-eta/disable",
            json={"branch_id": branch_2_id},
            headers=h,
        )
        assert r.status_code == 403
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(PluginBranchGrant).where(PluginBranchGrant.branch_id == branch_2_id)
            )
            await session.execute(
                delete(AuditLog).where(AuditLog.branch_id == branch_2_id)
            )
            await session.execute(delete(Branch).where(Branch.id == branch_2_id))
            await session.commit()


async def test_plugins_enabled_false_returns_all_inactive(seeded):
    async with SessionLocal() as session:
        cfg = await session.get(AppConfig, "plugins_enabled")
        cfg.value = "false"
        await session.commit()
        await registry.load(session)
    try:
        r = await seeded.get("/api/v1/system/plugins", headers=await _auth(seeded))
        assert r.status_code == 200
        plugins = r.json()["plugins"]
        assert plugins, "list still returns plugins"
        assert all(p["active"] is False for p in plugins), "kill switch must show every plugin inactive"
    finally:
        async with SessionLocal() as session:
            cfg = await session.get(AppConfig, "plugins_enabled")
            cfg.value = "true"
            await session.commit()
            await registry.load(session)