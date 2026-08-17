"""Test fixture: a bundled plugin whose manifest is MISSING required fields.

Constructing `PluginManifest` without `slug` raises a pydantic ValidationError
at import time — the registry must treat a package that cannot even import its
manifest as invalid, never crash the whole `load()` (one broken plugin must not
take down every other plugin).
"""
from app.plugins.manifest import PluginManifest

manifest = PluginManifest(
    version="0.0.1",
    name_ar="كسور",
    name_en="Broken",
    core_requires=">=0.1.0,<1.0.0",
    sdk_version="0.1.0",
)