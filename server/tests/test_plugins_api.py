"""Plugin registry API (ticket #3 AC1): list / enable / disable per branch.

Management endpoints are authenticated (existing Bearer scaffold) and audited
(action plugin_enable / plugin_disable in audit_log).
"""
import pytest
from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import AppConfig, AppPlugin, PluginBranchGrant
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