"""Manifest validation rules (ticket #3 AC1, plan/08 §2.1/§4.2).

The manifest is a frozen Pydantic model — the frozen contract a plugin declares.
`validate_manifest` is the single validation authority: it runs at registry load
and again when a plugin is enabled (enable refuses a broken manifest). Rules:

  1. the plugin's declared `slug` must match the installed DB row;
  2. `version` must be valid semver;
  3. `core_requires` must be a valid version range containing CORE_VERSION;
  4. `sdk_version` must equal the core's supported SDK version (one shared
     number gates both sides — the SDK contract);
  5. every `depends_on` entry must be installed and its version must satisfy the
     declared min/max range;
  6. `hooks` may only reference core-owned event names (an event name is a
     stable API, versioned with the SDK).

Resolution is strict-but-explicit: an incompatible combination BLOCKS enable,
never a silent half-activation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from app.core.events import IN_TXN, KNOWN_EVENTS

# SDK contract version — the single number gating plugin/core compatibility
# (plan/08 §4.2). Must match the seeds' sdk_version ('0.1.0') and pyproject.
CORE_VERSION = "0.1.0"
SDK_VERSION = "0.1.0"


class PluginDependency(BaseModel):
    slug: str
    min_version: str
    max_version: Optional[str] = None


class PluginManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+.*$")
    name_ar: str
    name_en: str
    core_requires: str
    sdk_version: str
    depends_on: list[PluginDependency] = Field(default_factory=list)


@dataclass(frozen=True)
class HookSpec:
    """One event handler a plugin wants the bus to wire up.

    `phase` places the handler in the two-phase lifecycle (in_txn / after_commit);
    `strict` is the in_txn failure policy (A09: mandatory legal state is strict).
    The registry wraps every handler with the per-branch enablement gate.
    """

    handler: Callable[[Any], Awaitable[None]]
    phase: str = IN_TXN
    strict: bool = False
    name: str = ""


def _range_contains(spec: str, version: str) -> Optional[bool]:
    try:
        return SpecifierSet(spec).contains(Version(version))
    except (InvalidSpecifier, InvalidVersion):
        return None


def validate_manifest(
    manifest: PluginManifest,
    *,
    slug: str,
    installed: dict[str, str],
) -> list[str]:
    """Return a list of validation errors (empty = manifest is valid)."""
    errors: list[str] = []

    if manifest.slug != slug:
        errors.append(
            f"manifest slug {manifest.slug!r} does not match installed slug {slug!r}"
        )
    try:
        Version(manifest.version)
    except InvalidVersion:
        errors.append(f"manifest version {manifest.version!r} is not valid semver")

    core_ok = _range_contains(manifest.core_requires, CORE_VERSION)
    if core_ok is None:
        errors.append(
            f"core_requires {manifest.core_requires!r} is not a valid version range"
        )
    elif not core_ok:
        errors.append(
            f"core_requires {manifest.core_requires!r} does not accept core "
            f"version {CORE_VERSION}"
        )

    if manifest.sdk_version != SDK_VERSION:
        errors.append(
            f"sdk_version {manifest.sdk_version!r} != core SDK {SDK_VERSION}"
        )

    for dep in manifest.depends_on:
        installed_version = installed.get(dep.slug)
        if installed_version is None:
            errors.append(
                f"dependency {dep.slug!r} is not installed"
            )
            continue
        dep_spec = f">={dep.min_version}" + (f",<{dep.max_version}" if dep.max_version else "")
        dep_ok = _range_contains(dep_spec, installed_version)
        if dep_ok is None:
            errors.append(
                f"dependency {dep.slug!r} range {dep_spec!r} is invalid"
            )
        elif not dep_ok:
            errors.append(
                f"dependency {dep.slug!r} installed {installed_version} "
                f"does not satisfy {dep_spec!r}"
            )

    return errors


def validate_hooks(hooks: Mapping[str, object]) -> list[str]:
    """Every subscribed event must be a core-owned event name."""
    return [
        f"plugin subscribes to unknown core event {event!r}"
        for event in hooks
        if event not in KNOWN_EVENTS
    ]