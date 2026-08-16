"""Manifest validation rules (ticket #3 AC1, plan/08 §2.1/§4.2).

The manifest is the frozen contract a plugin declares; validation is strict and
explicit — a mismatch BLOCKS activation, never a silent half-enable.
"""
from app.core.events import SALE_SAVED
from app.plugins.manifest import (
    CORE_VERSION,
    SDK_VERSION,
    PluginDependency,
    PluginManifest,
    validate_hooks,
    validate_manifest,
)


def _valid() -> PluginManifest:
    return PluginManifest(
        slug="pharmatag-eta",
        version="0.0.1",
        name_ar="الفوترة الإلكترونية",
        name_en="E-invoicing (ETA)",
        core_requires=f">={CORE_VERSION},<1.0.0",
        sdk_version=SDK_VERSION,
    )


INSTALLED = {"pharmatag-eta": "0.0.1", "pharmatag-chain": "1.2.0"}


def test_valid_manifest_passes():
    assert validate_manifest(_valid(), slug="pharmatag-eta", installed=INSTALLED) == []


def test_slug_mismatch_fails():
    errors = validate_manifest(_valid(), slug="pharmatag-ledger", installed=INSTALLED)
    assert any("slug" in e for e in errors)


def test_core_version_mismatch_fails():
    manifest = _valid().model_copy(update={"core_requires": ">=9.0.0,<10.0.0"})
    errors = validate_manifest(manifest, slug="pharmatag-eta", installed=INSTALLED)
    assert any("core" in e and "requires" in e for e in errors)


def test_invalid_core_requires_range_fails():
    manifest = _valid().model_copy(update={"core_requires": "not-a-range"})
    errors = validate_manifest(manifest, slug="pharmatag-eta", installed=INSTALLED)
    assert any("not a valid version range" in e for e in errors)


def test_sdk_version_mismatch_fails():
    manifest = _valid().model_copy(update={"sdk_version": "0.2.0"})
    errors = validate_manifest(manifest, slug="pharmatag-eta", installed=INSTALLED)
    assert any("sdk" in e.lower() for e in errors)


def test_missing_dependency_fails():
    manifest = _valid().model_copy(
        update={"depends_on": [PluginDependency(slug="pharmatag-chain", min_version="1.0.0")]}
    )
    errors = validate_manifest(manifest, slug="pharmatag-eta", installed={"pharmatag-eta": "0.0.1"})
    assert any("pharmatag-chain" in e and "not installed" in e for e in errors)


def test_out_of_range_dependency_version_fails():
    manifest = _valid().model_copy(
        update={
            "depends_on": [
                PluginDependency(slug="pharmatag-chain", min_version="2.0.0"),
            ]
        }
    )
    errors = validate_manifest(manifest, slug="pharmatag-eta", installed=INSTALLED)
    assert any("does not satisfy" in e for e in errors)


def test_non_semver_version_fails_validation():
    manifest = _valid().model_copy(update={"version": "not-semver"})
    errors = validate_manifest(manifest, slug="pharmatag-eta", installed=INSTALLED)
    assert any("not valid semver" in e for e in errors)


def test_unknown_hook_event_fails_validation():
    errors = validate_hooks({"mystery.event": []})
    assert len(errors) == 1
    assert "unknown core event" in errors[0]


def test_known_hook_event_passes_validation():
    assert validate_hooks({SALE_SAVED: []}) == []