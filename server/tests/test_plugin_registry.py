"""Plugin registry: load/validation, per-branch enable/disable, branch-gated
hook dispatch, and the stub `pharmatag-eta` subscribing to `sale.saved`
end-to-end (ticket #3 AC1 + AC3, plan/08 §2.1/§4.3).

The registry is DB-backed: `app_plugins.status` is the global toggle,
`plugin_branch_grants.enabled` is the per-branch toggle. No plugin code runs
without both — "no plugin code runs without its enabled bit" (plan/08 §5.2).
"""
from sqlalchemy import delete, select, update

from app.core.db import SessionLocal
from app.core.events import SALE_SAVED, bus
from app.models import (
    AppConfig,
    AppPlugin,
    AuditLog,
    Branch,
    Invoice,
    PluginBranchGrant,
)
from app.plugins.registry import registry
from app.sales.service import save_sale

BRANCH_ID = 1
USER_ID = 1

_invoice_seq = [20000]


def _next_invoice_no() -> str:
    _invoice_seq[0] += 1
    return str(_invoice_seq[0])


async def _reset_plugin_rows():
    async with SessionLocal() as session:
        await session.execute(update(AppPlugin).values(status="installed"))
        await session.execute(update(PluginBranchGrant).values(enabled=False))
        cfg = await session.get(AppConfig, "plugins_enabled")
        cfg.value = "true"
        await session.execute(delete(AuditLog).where(AuditLog.entity == "app_plugins"))
        await session.execute(delete(AuditLog).where(AuditLog.entity == "plugin_eta"))
        await session.execute(delete(AuditLog).where(AuditLog.entity == "invoices"))
        await session.execute(delete(Invoice))
        await session.commit()
        await registry.load(session)


async def _stub_rows(entity: str = "plugin_eta"):
    async with SessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.entity == entity).order_by(AuditLog.id)
        )
        return result.scalars().all()


async def _save_sale():
    async with SessionLocal() as session:
        invoice = await save_sale(
            session, branch_id=BRANCH_ID, user_id=USER_ID, invoice_no=_next_invoice_no()
        )
    # the seam path writes a header-only invoice; delete it so this test file
    # never leaks rows (the plugin audit rows above survive — no FK to invoices)
    async with SessionLocal() as session:
        await session.execute(delete(Invoice).where(Invoice.id == invoice.id))
        await session.commit()
    return invoice


async def test_load_surfaces_installed_plugins_with_grants_and_validation():
    await _reset_plugin_rows()
    assert set(registry.plugins) == {"pharmatag-eta", "pharmatag-ledger"}

    eta = registry.plugins["pharmatag-eta"]
    assert eta.db_status == "installed"
    assert eta.valid is True, eta.errors
    assert eta.grants.get(BRANCH_ID) is False

    ledger = registry.plugins["pharmatag-ledger"]
    assert ledger.valid is False
    assert any("not found" in e for e in ledger.errors)
    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False


async def test_enable_activates_plugin_for_branch():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is True

    async with SessionLocal() as session:
        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == "pharmatag-eta"))
        ).scalar_one()
        assert row.status == "enabled"
        grant = await session.get(
            PluginBranchGrant, {"plugin_id": row.id, "branch_id": BRANCH_ID}
        )
        assert grant is not None and grant.enabled is True


async def test_enable_is_audited():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    rows = await _stub_rows("app_plugins")
    assert len(rows) == 1
    assert rows[0].action == "plugin_enable"
    assert rows[0].user_id == USER_ID
    assert rows[0].new_value == "pharmatag-eta"


async def test_enable_refuses_a_plugin_with_an_invalid_manifest():
    await _reset_plugin_rows()
    # pharmatag-ledger is seeded installed but ships no code in this ticket
    async with SessionLocal() as session:
        try:
            await registry.enable(session, "pharmatag-ledger", branch_id=BRANCH_ID, user_id=USER_ID)
        except ValueError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("enable must refuse a plugin that cannot validate")
    assert registry.is_active("pharmatag-ledger", BRANCH_ID) is False


async def test_disable_deactivates_plugin_and_lowers_global_status():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)
    async with SessionLocal() as session:
        await registry.disable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
    async with SessionLocal() as session:
        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == "pharmatag-eta"))
        ).scalar_one()
        assert row.status == "disabled"
        grant = await session.get(
            PluginBranchGrant, {"plugin_id": row.id, "branch_id": BRANCH_ID}
        )
        assert grant.enabled is False
    rows = await _stub_rows("app_plugins")
    assert [r.action for r in rows] == ["plugin_enable", "plugin_disable"]


async def test_stub_plugin_subscribes_to_sale_saved_end_to_end():
    """AC3: enable pharmatag-eta, save a sale — its in_txn AND after_commit
    hooks both run, recording observable audit rows."""
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is True
    assert len(bus.handlers_for(SALE_SAVED, phase="in_txn")) == 1
    assert len(bus.handlers_for(SALE_SAVED, phase="after_commit")) == 1

    invoice = await _save_sale()

    rows = await _stub_rows("plugin_eta")
    assert [r.action for r in rows] == ["in_txn", "after_commit"]
    assert all(r.entity_id == invoice.id for r in rows)
    assert all(r.namee == "pharmatag-eta" for r in rows)


async def test_disabled_branch_grant_stops_the_hooks_even_when_globally_enabled():
    await _reset_plugin_rows()
    # globally enabled, but the branch-1 grant stays disabled
    async with SessionLocal() as session:
        await session.execute(update(AppPlugin).values(status="enabled"))
        await session.commit()
        await registry.load(session)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
    await _save_sale()
    assert await _stub_rows("plugin_eta") == [], "branch-gated hooks must not run"


async def test_plugins_enabled_kill_switch_stops_all_plugin_code():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)
        cfg = await session.get(AppConfig, "plugins_enabled")
        cfg.value = "false"
        await session.commit()
        await registry.load(session)

    assert registry.plugins_enabled is False
    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
    await _save_sale()
    assert await _stub_rows("plugin_eta") == []


async def test_enable_twice_is_idempotent_no_duplicate_hooks_or_grants():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is True
    assert len(bus.handlers_for(SALE_SAVED, phase="in_txn")) == 1, "no double subscription"
    assert len(bus.handlers_for(SALE_SAVED, phase="after_commit")) == 1

    async with SessionLocal() as session:
        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == "pharmatag-eta"))
        ).scalar_one()
        grants = (
            await session.execute(
                select(PluginBranchGrant).where(PluginBranchGrant.plugin_id == row.id)
            )
        ).scalars().all()
        assert len(grants) == 1, "a second enable must not duplicate the grant row"
        assert grants[0].enabled is True
    rows = await _stub_rows("app_plugins")
    assert [r.action for r in rows] == ["plugin_enable", "plugin_enable"]


async def test_disable_plugin_that_was_never_enabled_is_not_an_error():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.disable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
    async with SessionLocal() as session:
        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == "pharmatag-eta"))
        ).scalar_one()
        assert row.status == "disabled"
        grants = (
            await session.execute(
                select(PluginBranchGrant).where(PluginBranchGrant.plugin_id == row.id)
            )
        ).scalars().all()
        assert all(not g.enabled for g in grants)
    rows = await _stub_rows("app_plugins")
    assert [r.action for r in rows] == ["plugin_disable"]


async def test_disable_twice_is_idempotent():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)
    async with SessionLocal() as session:
        await registry.disable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)
    async with SessionLocal() as session:
        await registry.disable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
    async with SessionLocal() as session:
        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == "pharmatag-eta"))
        ).scalar_one()
        assert row.status == "disabled"


async def test_cross_branch_grants_are_independent():
    """Two branches enable/disable independently; one branch's disable does not
    demote the plugin while the other branch still holds it enabled."""
    await _reset_plugin_rows()
    branch_2_id: int = 0
    async with SessionLocal() as session:
        branch_2 = Branch(pharmacyid="__t3_b2__", mobile="0", pharname="Branch 2")
        session.add(branch_2)
        await session.flush()
        branch_2_id = branch_2.id
        await session.commit()
    try:
        async with SessionLocal() as session:
            await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

        assert registry.is_active("pharmatag-eta", BRANCH_ID) is True
        assert registry.is_active("pharmatag-eta", branch_2_id) is False, "no grant leak to branch 2"

        async with SessionLocal() as session:
            await registry.enable(session, "pharmatag-eta", branch_id=branch_2_id, user_id=USER_ID)
        assert registry.is_active("pharmatag-eta", branch_2_id) is True

        async with SessionLocal() as session:
            await registry.disable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)
        assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
        assert registry.is_active("pharmatag-eta", branch_2_id) is True, "branch 2 unaffected"
        async with SessionLocal() as session:
            row = (
                await session.execute(select(AppPlugin).where(AppPlugin.slug == "pharmatag-eta"))
            ).scalar_one()
            assert row.status == "enabled", "global status stays enabled while any branch holds it"
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(PluginBranchGrant).where(PluginBranchGrant.branch_id == branch_2_id)
            )
            await session.execute(delete(AuditLog).where(AuditLog.branch_id == branch_2_id))
            await session.execute(delete(Branch).where(Branch.id == branch_2_id))
            await session.commit()
            await registry.load(session)


async def test_enable_while_kill_switch_off_does_not_activate():
    await _reset_plugin_rows()
    async with SessionLocal() as session:
        cfg = await session.get(AppConfig, "plugins_enabled")
        cfg.value = "false"
        await session.commit()
        await registry.load(session)

    async with SessionLocal() as session:
        await registry.enable(session, "pharmatag-eta", branch_id=BRANCH_ID, user_id=USER_ID)

    assert registry.plugins_enabled is False
    assert registry.is_active("pharmatag-eta", BRANCH_ID) is False, "kill switch still wins"
    await _save_sale()
    assert await _stub_rows("plugin_eta") == []


async def test_plugin_with_malformed_manifest_does_not_crash_load():
    """A bundled plugin whose manifest is MISSING required fields raises at
    import; load() must mark it invalid instead of crashing the whole registry."""
    await _reset_plugin_rows()
    # heal any row left behind by an earlier crashed run (test isolation)
    async with SessionLocal() as session:
        await session.execute(delete(AppPlugin).where(AppPlugin.slug == "pharmatag-broken"))
        await session.commit()
    try:
        async with SessionLocal() as session:
            session.add(
                AppPlugin(
                    slug="pharmatag-broken",
                    name_ar="كسور",
                    name_en="Broken",
                    version="0.0.1",
                    core_requires=">=0.1.0,<1.0.0",
                    sdk_version="0.1.0",
                )
            )
            await session.commit()
            await registry.load(session)  # must NOT raise

        assert "pharmatag-broken" in registry.plugins
        broken = registry.plugins["pharmatag-broken"]
        assert broken.valid is False
        assert any("import" in e.lower() for e in broken.errors), broken.errors
        assert registry.plugins["pharmatag-eta"].valid is True, "other plugins must load fine"
        assert registry.is_active("pharmatag-eta", BRANCH_ID) is False
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(AppPlugin).where(AppPlugin.slug == "pharmatag-broken"))
            await session.commit()
            await registry.load(session)
    assert "pharmatag-broken" not in registry.plugins