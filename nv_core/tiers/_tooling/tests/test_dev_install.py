# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for ``dev_install`` tier selection and the editable codegen mirror.

These exercise pure helpers and the build hook's mirror step -- no ``pip``
install and no ``uv`` invocation -- so they run in any environment. The hook's
codegen itself needs ``usd_profiles_nvidia``, so the mirror is tested directly
against a stand-in generated tree rather than by running a real build.

``build_hook`` imports ``hatchling`` (present only in a PEP 517 build env), so
that one import is stubbed here to keep these tests dependency-free.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

_TOOLING = Path(__file__).resolve().parents[1]


def _stub_hatchling() -> None:
    """Register a minimal ``hatchling`` so ``build_hook`` imports without a build env."""
    if "hatchling" in sys.modules:
        return
    interface = ModuleType("hatchling.builders.hooks.plugin.interface")
    interface.BuildHookInterface = type("BuildHookInterface", (), {})
    for name in (
        "hatchling",
        "hatchling.builders",
        "hatchling.builders.hooks",
        "hatchling.builders.hooks.plugin",
    ):
        module = ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    sys.modules["hatchling.builders.hooks.plugin.interface"] = interface


def _load(name: str, filename: str):
    # dev_install imports build_tiers as a sibling top-level module, so the
    # tooling dir has to be importable before it is executed.
    if str(_TOOLING) not in sys.path:
        sys.path.insert(0, str(_TOOLING))
    spec = importlib.util.spec_from_file_location(name, _TOOLING / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stub_hatchling()
dev_install = _load("simready_dev_install", "dev_install.py")
build_hook = _load("simready_build_hook", "build_hook.py")
_TIERS_ROOT = dev_install._TIERS_ROOT


# ===========================================================================
# resolve_tiers
# ===========================================================================


def test_resolve_tiers_defaults_to_every_discovered_tier():
    resolved = [os.path.basename(t) for t in dev_install.resolve_tiers(_TIERS_ROOT)]
    assert "simready_foundation_tier_core" in resolved
    assert "_tooling" not in resolved


def test_resolve_tiers_selects_by_name():
    resolved = dev_install.resolve_tiers(_TIERS_ROOT, ["simready_foundation_tier_core"])
    assert [os.path.basename(t) for t in resolved] == ["simready_foundation_tier_core"]


def test_resolve_tiers_accepts_a_path():
    tier_path = os.path.join(_TIERS_ROOT, "simready_foundation_tier_core")
    resolved = dev_install.resolve_tiers(_TIERS_ROOT, [tier_path])
    assert [os.path.basename(t) for t in resolved] == ["simready_foundation_tier_core"]


def test_resolve_tiers_deduplicates_repeated_selection():
    resolved = dev_install.resolve_tiers(
        _TIERS_ROOT,
        ["simready_foundation_tier_core", "simready_foundation_tier_core"],
    )
    assert len(resolved) == 1


def test_resolve_tiers_rejects_unknown_tier():
    with pytest.raises(dev_install.DevInstallError, match="unknown tier"):
        dev_install.resolve_tiers(_TIERS_ROOT, ["not_a_tier"])


def test_resolve_tiers_agrees_with_build_tiers_discovery():
    # The two commands must never disagree on what counts as a tier.
    from build_tiers import discover_tiers

    assert dev_install.resolve_tiers(_TIERS_ROOT) == discover_tiers(_TIERS_ROOT)


# ===========================================================================
# build_hook editable mirror
# ===========================================================================

_MODULE = "simready.foundation.tier_probe"
_REQUIREMENTS_MODULE = f"{_MODULE}.requirements"


def _fake_generated_tree(build_python: Path) -> Path:
    """Create a stand-in for what PythonGenerator writes into the scratch dir."""
    generated = build_python / Path(*_REQUIREMENTS_MODULE.split("."))
    generated.mkdir(parents=True)
    (generated / "__init__.py").write_text("REQUIREMENTS = 1\n", encoding="utf-8")
    (generated / "_requirements.py").write_text("# generated\n", encoding="utf-8")
    (generated / "capabilities.json").write_text("{}\n", encoding="utf-8")
    return generated


def _sync(root: Path, build_python: Path, *, editable: bool) -> None:
    build_hook.CustomBuildHook._sync_checkout_mirror(
        root, build_python, _REQUIREMENTS_MODULE, editable=editable
    )


def test_editable_build_mirrors_generated_package_into_checkout(tmp_path):
    build_python = tmp_path / "_build" / "python"
    _fake_generated_tree(build_python)

    _sync(tmp_path, build_python, editable=True)

    mirrored = tmp_path / Path(*_REQUIREMENTS_MODULE.split("."))
    assert (mirrored / "__init__.py").read_text(encoding="utf-8") == "REQUIREMENTS = 1\n"
    assert (mirrored / "_requirements.py").is_file()
    assert (mirrored / "capabilities.json").is_file()


def test_mirror_lands_beside_the_tier_package(tmp_path):
    # The mirror must be importable as <module>.requirements, i.e. a sibling of
    # the tier package's other subpackages -- not a nested duplicate.
    build_python = tmp_path / "_build" / "python"
    _fake_generated_tree(build_python)

    _sync(tmp_path, build_python, editable=True)

    assert (tmp_path / Path(*_MODULE.split(".")) / "requirements" / "__init__.py").is_file()


def test_editable_build_replaces_a_stale_previous_mirror(tmp_path):
    mirrored = tmp_path / Path(*_REQUIREMENTS_MODULE.split("."))
    mirrored.mkdir(parents=True)
    (mirrored / "__init__.py").write_text("STALE = 1\n", encoding="utf-8")
    (mirrored / "removed_requirement.py").write_text("# gone next build\n", encoding="utf-8")

    build_python = tmp_path / "_build" / "python"
    _fake_generated_tree(build_python)

    _sync(tmp_path, build_python, editable=True)

    assert (mirrored / "__init__.py").read_text(encoding="utf-8") == "REQUIREMENTS = 1\n"
    # A requirement page deleted since the last install must not survive.
    assert not (mirrored / "removed_requirement.py").exists()


def test_standard_build_clears_a_mirror_left_by_an_editable_install(tmp_path):
    # Regression: a leftover mirror sits inside the committed tree, so the wheel
    # builder would ship it via `packages` AND via `force-include` and abort with
    # "A second file is being added to the wheel archive at the same path".
    build_python = tmp_path / "_build" / "python"
    _fake_generated_tree(build_python)
    _sync(tmp_path, build_python, editable=True)
    mirrored = tmp_path / Path(*_REQUIREMENTS_MODULE.split("."))
    assert mirrored.is_dir()

    _sync(tmp_path, build_python, editable=False)

    assert not mirrored.exists()
    # The scratch the wheel force-includes must survive the cleanup.
    assert (build_python / Path(*_REQUIREMENTS_MODULE.split(".")) / "__init__.py").is_file()


def test_standard_build_is_a_no_op_without_a_mirror(tmp_path):
    build_python = tmp_path / "_build" / "python"
    _fake_generated_tree(build_python)

    _sync(tmp_path, build_python, editable=False)

    assert not (tmp_path / Path(*_REQUIREMENTS_MODULE.split("."))).exists()


def test_generated_requirements_are_git_ignored():
    # The mirror lives inside the committed package tree, so this rule is what
    # keeps generated code out of commits and `git status` clean during
    # development. It is NOT what keeps wheels clean -- hatchling resolves ignore
    # files relative to the tier directory, so the build hook clears the mirror
    # itself (see test_standard_build_clears_a_mirror_left_by_an_editable_install).
    gitignore = (Path(_TIERS_ROOT) / ".gitignore").read_text(encoding="utf-8")
    assert "*/simready/foundation/*/requirements/" in gitignore
