# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the distribution boundary of simready-multiphysics-upgrade.

These cover the parts that make the package installable away from a checkout:
the declared console entry points, the protocol version the packaging tools read
without USD, tier-data resolution, and lazy transformer loading.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _PACKAGE_ROOT / "pyproject.toml"
_PROTOCOL_PATH = _PACKAGE_ROOT / "src" / "simready" / "multiphysics_upgrade" / "protocol.py"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Packaging metadata
# ---------------------------------------------------------------------------


def test_declares_the_transformer_as_a_dependency(pyproject):
    """The wheelhouse must be able to install Isaac composition from the pins."""
    dependencies = " ".join(pyproject["project"]["dependencies"])
    assert "simready-foundation-tier-core" in dependencies
    assert "simready-foundation-tier-core[isaac]" in " ".join(
        pyproject["project"]["optional-dependencies"]["isaac"]
    )


def test_ships_simready_as_a_namespace_package(pyproject):
    """Otherwise this wheel would shadow simready.asset_transformer."""
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["namespaces"] is True


def test_supports_the_interpreter_the_blender_addon_bundles(pyproject):
    requires = pyproject["project"]["requires-python"]
    assert ">=3.11" in requires
    assert "<3.14" in requires


@pytest.mark.parametrize(
    "script,target",
    [
        ("simready-multiphysics-sidecar", "simready.multiphysics_upgrade.sidecar:main"),
        ("simready-multiphysics-upgrade", "simready.multiphysics_upgrade.runner:main"),
    ],
)
def test_console_scripts_point_at_real_callables(pyproject, script, target):
    assert pyproject["project"]["scripts"][script] == target

    module_name, _, attribute = target.partition(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, attribute))


# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------


def test_protocol_version_is_importable_without_usd():
    """build_wheelhouse.py loads this file by path on hosts with no USD build."""
    spec = importlib.util.spec_from_file_location("_protocol_isolated", _PROTOCOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.PROTOCOL_VERSION, int)
    assert "pxr" not in _PROTOCOL_PATH.read_text(encoding="utf-8")


def test_the_public_api_reports_the_same_protocol_as_the_manifest_source():
    from simready.multiphysics_upgrade import PROTOCOL_VERSION
    from simready.multiphysics_upgrade.protocol import PROTOCOL_VERSION as declared

    assert PROTOCOL_VERSION == declared, "a wheelhouse manifest would advertise the wrong protocol"


def test_the_sidecar_speaks_the_declared_protocol():
    from simready.multiphysics_upgrade import sidecar
    from simready.multiphysics_upgrade.protocol import PROTOCOL_VERSION

    assert sidecar.PROTOCOL_VERSION == PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Tier data resolution
# ---------------------------------------------------------------------------


def _make_tier_root(root: Path, *, rules: str = "capabilities") -> Path:
    for name in (rules, "features", "profiles"):
        (root / name).mkdir(parents=True)
    return root


@pytest.mark.parametrize("rules", ["capabilities", "rules_and_reqs"])
def test_either_requirement_tree_name_makes_a_tier_root(monkeypatch, tmp_path, rules):
    from simready.multiphysics_upgrade import tier_paths

    override = _make_tier_root(tmp_path / "tier_core", rules=rules)
    monkeypatch.setenv(tier_paths.TIER_ROOT_ENV_VAR, str(override))
    assert tier_paths.find_tier_root() == override.resolve()
    assert tier_paths.rules_dir(override) == override / rules


def test_the_requirement_tree_wins_over_relocated_cap_contracts(tmp_path):
    from simready.multiphysics_upgrade import tier_paths

    root = _make_tier_root(tmp_path / "tier_core", rules="rules_and_reqs")
    (root / "capabilities").mkdir()
    assert tier_paths.rules_dir(root) == root / "rules_and_reqs"


def test_an_explicit_tier_root_wins(monkeypatch, tmp_path):
    from simready.multiphysics_upgrade import tier_paths

    override = _make_tier_root(tmp_path / "tier_core")
    monkeypatch.setenv(tier_paths.TIER_ROOT_ENV_VAR, str(override))
    assert tier_paths.find_tier_root() == override.resolve()


def test_an_override_that_is_not_a_tier_root_is_ignored(monkeypatch, tmp_path):
    from simready.multiphysics_upgrade import tier_paths

    empty = tmp_path / "not_a_tier"
    empty.mkdir()
    monkeypatch.setenv(tier_paths.TIER_ROOT_ENV_VAR, str(empty))
    found = tier_paths.find_tier_root()
    assert found != empty.resolve()


def test_a_blank_override_falls_through(monkeypatch):
    from simready.multiphysics_upgrade import tier_paths

    monkeypatch.setenv(tier_paths.TIER_ROOT_ENV_VAR, "   ")
    assert tier_paths._from_environment() is None


def test_missing_tier_data_names_both_ways_to_fix_it(monkeypatch):
    from simready.multiphysics_upgrade import tier_paths

    monkeypatch.setattr(tier_paths, "find_tier_root", lambda: None)
    with pytest.raises(tier_paths.TierDataUnavailableError) as excinfo:
        tier_paths.require_tier_root()

    message = str(excinfo.value)
    assert "simready-foundation-tier-core" in message
    assert tier_paths.TIER_ROOT_ENV_VAR in message


def test_the_neutral_pipeline_never_needs_tier_data(monkeypatch):
    """Prop upgrades from Blender must work without any Foundation tier install."""
    from simready.multiphysics_upgrade import tier_paths

    def _explode():
        raise AssertionError("neutral_to_runtimes must not require tier data")

    monkeypatch.setattr(tier_paths, "require_tier_root", _explode)
    monkeypatch.setattr(tier_paths, "find_tier_root", _explode)

    module = importlib.import_module("simready.multiphysics_upgrade.neutral_to_runtimes")
    assert module is not None


# ---------------------------------------------------------------------------
# Lazy transformer loading
# ---------------------------------------------------------------------------


def test_the_transformer_is_resolved_lazily():
    from simready.multiphysics_upgrade import transformer_bootstrap

    transform_package = transformer_bootstrap.load_transform_package()
    assert callable(transform_package)


def test_an_absent_transformer_is_reported_with_the_install_command(monkeypatch):
    from simready.multiphysics_upgrade import transformer_bootstrap

    monkeypatch.setattr(transformer_bootstrap, "ensure_transformer_importable", lambda: None)
    # A None entry in sys.modules is the documented way to make `import` fail.
    monkeypatch.setitem(sys.modules, "simready.asset_transformer", None)

    with pytest.raises(transformer_bootstrap.TransformerUnavailableError) as excinfo:
        transformer_bootstrap.load_transform_package()
    assert "simready-foundation-tier-core[isaac]" in str(excinfo.value)


def test_source_transformer_fallback_points_to_tier_tools():
    from simready.multiphysics_upgrade import transformer_bootstrap

    src = transformer_bootstrap._find_in_repo_src()
    assert src is not None
    assert "simready_foundation_tier_core" in src.parts
    assert (src / "simready" / "asset_transformer" / "__init__.py").is_file()


def test_profiles_resolve_to_dotted_contract_ids():
    from simready.multiphysics_upgrade import runner

    required, optional = runner._load_profile_features("Robotics-Prop", "3.1.0")
    assert "FET001_MinimalPlaceableVisual.1-0-1" in required
    assert "CAP000_Core.0-1-0" in required
    assert "FET003_RigidBody.PhysX.0-4-0" in optional
    assert "FET003_RigidBody.Newton.0-1-0" in optional


# ---------------------------------------------------------------------------
# Legacy adapter path
# ---------------------------------------------------------------------------


def test_the_legacy_adapter_bootstrap_does_not_need_an_installed_wheel():
    """The in-repo CIP adapter path must keep working from a plain checkout."""
    bootstrap = _PACKAGE_ROOT.parent / "asset_handler_modules" / "multiphysics_upgrade" / "_bootstrap.py"
    assert bootstrap.is_file()
    source = bootstrap.read_text(encoding="utf-8")
    assert "multiphysics_upgrade" in source
    assert "sys.path" in source
