"""Plugin registry + lifecycle manager (plan/08 §2.1, §5, ticket #3 AC1/AC3).

The registry is the single mutable object every worker holds. It is DB-backed:
`app_plugins` (installed metadata + global status), `plugin_dependencies` and
`plugin_branch_grants` (per-branch on/off) are the source of truth; the plugin
code is bundled in-process and loaded from disk by slug (A12 bundle-all).

`load()` reads the DB, loads each installed plugin's package, validates its
manifest (core range, SDK version, dependency graph — strict block, plan/08
§4.2) and subscribes the hooks of globally-enabled, valid plugins. Every
subscribed handler is wrapped in a per-branch gate so no plugin code runs
without its `plugin_branch_grants.enabled` bit — even when the plugin is
globally enabled (plan/08 §5.2).

`enable`/`disable` are the management operations: DB first, then an in-process
refresh (workers restart in prod). Both write an `audit_log` row (action
`plugin_enable` / `plugin_disable`).
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import settings
from app.core.events import EventBus, bus
from app.models import AppConfig, AppPlugin, PluginBranchGrant
from app.plugins.manifest import (
    PluginManifest,
    validate_hooks,
    validate_manifest,
)


@dataclass
class PluginState:
    """Runtime state for one installed plugin (DB row + loaded code + validation)."""

    slug: str
    db_status: str
    version: str
    name_ar: str
    name_en: str
    manifest: Optional[PluginManifest]
    hooks: dict[str, list[Any]]
    grants: dict[int, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def _load_plugin_module(slug: str) -> Optional[Any]:
    """Import the bundled plugin package by slug (A12: bundle-all + runtime gate).

    Map `pharmatag-eta` -> module `pharmatag_eta` under settings.plugins_dir.
    Returns None when no package ships for this slug.
    """
    module_name = slug.replace("-", "_")
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = settings.plugins_dir / slug / "__init__.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class PluginRegistry:
    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus
        self.plugins: dict[str, PluginState] = {}
        self.plugins_enabled: bool = True

    # --- loading / validation ---

    async def load(self, session: AsyncSession) -> None:
        """Rebuild the registry from the DB: validate manifests, subscribe hooks."""
        self.bus.reset()
        self.plugins = {}

        cfg = (
            await session.execute(
                select(AppConfig).where(AppConfig.key == "plugins_enabled")
            )
        ).scalar_one_or_none()
        self.plugins_enabled = cfg.value != "false" if cfg else True

        rows = (await session.execute(select(AppPlugin).order_by(AppPlugin.id))).scalars().all()
        grant_rows = (await session.execute(select(PluginBranchGrant))).scalars().all()
        grants: dict[int, dict[int, bool]] = {}
        for grant in grant_rows:
            grants.setdefault(grant.plugin_id, {})[grant.branch_id] = grant.enabled

        installed = {row.slug: row.version for row in rows}

        for row in rows:
            module = _load_plugin_module(row.slug)
            manifest: Optional[PluginManifest] = None
            hooks: dict[str, list[Any]] = {}
            errors: list[str] = []
            if module is None:
                errors.append("plugin package not found")
            else:
                candidate = getattr(module, "manifest", None)
                if not isinstance(candidate, PluginManifest):
                    errors.append("plugin package does not expose a PluginManifest")
                else:
                    manifest = candidate
                    hooks = getattr(module, "hooks", {}) or {}
                    errors += validate_manifest(manifest, slug=row.slug, installed=installed)
                    errors += validate_hooks(hooks)

            self.plugins[row.slug] = PluginState(
                slug=row.slug,
                db_status=row.status,
                version=row.version,
                name_ar=row.name_ar,
                name_en=row.name_en,
                manifest=manifest,
                hooks=hooks,
                grants=grants.get(row.id, {}),
                errors=errors,
            )

        # subscribe globally-enabled, valid plugins; per-branch gate at dispatch
        for state in self.plugins.values():
            if state.db_status != "enabled" or not state.valid:
                continue
            for event, specs in state.hooks.items():
                for spec in specs:
                    self.bus.subscribe(
                        event,
                        self._gated(state.slug, spec.handler),
                        phase=spec.phase,
                        strict=spec.strict,
                        name=spec.name or f"{state.slug}.{getattr(spec.handler, '__name__', 'handler')}",
                    )

    def _gated(self, slug: str, handler):
        """Wrap a plugin handler with the per-branch enablement gate (plan/08 §5.2)."""

        async def wrapper(ctx: Any) -> None:
            if self.is_active(slug, ctx.branch_id):
                await handler(ctx)

        return wrapper

    # --- enablement queries ---

    def is_active(self, slug: str, branch_id: int) -> bool:
        """A plugin runs for a branch iff globally enabled AND granted AND valid
        (and the global plugins_enabled kill-switch is on)."""
        if not self.plugins_enabled:
            return False
        state = self.plugins.get(slug)
        if state is None or not state.valid:
            return False
        if state.db_status != "enabled":
            return False
        return state.grants.get(branch_id, False) is True

    def list_for(self, branch_id: Optional[int] = None) -> list[dict[str, Any]]:
        return [
            {
                "slug": state.slug,
                "version": state.version,
                "name_ar": state.name_ar,
                "name_en": state.name_en,
                "status": state.db_status,
                "validation": {"ok": state.valid, "errors": state.errors},
                "branch_grants": state.grants,
                "active": self.is_active(state.slug, branch_id) if branch_id else None,
            }
            for state in self.plugins.values()
        ]

    # --- lifecycle operations ---

    async def enable(self, session: AsyncSession, slug: str, *, branch_id: int, user_id: int) -> None:
        """Enable a plugin for a branch: global status -> enabled, branch grant -> on.

        Revalidates the manifest first — a broken plugin cannot be enabled.
        """
        await self.load(session)
        state = self.plugins.get(slug)
        if state is None:
            raise KeyError(f"plugin {slug!r} is not installed")
        if not state.valid:
            raise ValueError(f"plugin {slug!r} cannot be enabled: " + "; ".join(state.errors))

        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == slug))
        ).scalar_one()
        row.status = "enabled"
        grant = await session.get(PluginBranchGrant, {"plugin_id": row.id, "branch_id": branch_id})
        if grant is None:
            session.add(PluginBranchGrant(plugin_id=row.id, branch_id=branch_id, enabled=True))
        else:
            grant.enabled = True
        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="app_plugins",
            entity_id=row.id,
            action="plugin_enable",
            new_value=slug,
        )
        await session.commit()
        await self.load(session)

    async def disable(self, session: AsyncSession, slug: str, *, branch_id: int, user_id: int) -> None:
        """Disable a plugin for a branch. When no branch keeps it enabled the
        global status drops to `disabled` (plan/08 §5.2). Data is retained."""
        row = (
            await session.execute(select(AppPlugin).where(AppPlugin.slug == slug))
        ).scalar_one_or_none()
        if row is None:
            raise KeyError(f"plugin {slug!r} is not installed")

        grant = await session.get(PluginBranchGrant, {"plugin_id": row.id, "branch_id": branch_id})
        if grant is not None:
            grant.enabled = False

        still_enabled = (
            await session.execute(
                select(PluginBranchGrant).where(
                    PluginBranchGrant.plugin_id == row.id,
                    PluginBranchGrant.enabled.is_(True),
                )
            )
        ).scalar_one_or_none()
        if still_enabled is None:
            row.status = "disabled"

        await audit(
            session,
            branch_id=branch_id,
            user_id=user_id,
            entity="app_plugins",
            entity_id=row.id,
            action="plugin_disable",
            new_value=slug,
        )
        await session.commit()
        await self.load(session)


registry = PluginRegistry(bus)