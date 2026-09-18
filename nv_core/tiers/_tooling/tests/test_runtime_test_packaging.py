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
"""Packaging contract tests for Foundation runtime tests bundled by a tier."""

from __future__ import annotations

import importlib.util
import os
import sys
import tomllib
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_TOOLING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLING_DIR))

import build_tiers as bt  # noqa: E402


def _foundation_root():
    # type: () -> Path
    for parent in Path(__file__).resolve().parents:
        if (parent / "nv_core" / "tiers").is_dir():
            return parent
    raise AssertionError("could not locate the SimReady Foundation root")


def test_core_benchmark_extra_installs_runtime_dependencies():
    root = _foundation_root()
    project = tomllib.loads(
        (root / "nv_core" / "tiers" / "simready_foundation_tier_core" / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert all("simready-benchmark" not in dependency for dependency in project["dependencies"])
    benchmark = project["optional-dependencies"]["benchmark"]
    assert "simready-benchmark[kit]>=2026.6.6" in benchmark
    assert "usd-core>=23.5" in benchmark


def test_core_tier_bundles_and_advertises_runtime_tests():
    root = _foundation_root()
    tier_root = root / "nv_core" / "tiers" / "simready_foundation_tier_core"
    project = tomllib.loads((tier_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "simready",
        "simready_benchmark_kit_suite",
    ]
    assert (tier_root / "simready_benchmark_kit_suite" / "__init__.py").is_file()
    assert project["project"]["entry-points"]["simready.tier"]["tier_core"] == "simready.foundation.tier_core:tier"

    tier_module = (tier_root / "simready" / "foundation" / "tier_core" / "_tier.py").read_text(encoding="utf-8")
    assert "runtime_tests_path=" in tier_module


def test_source_descriptor_resolves_importable_runtime_test_package(monkeypatch):
    root = _foundation_root()
    tier_root = root / "nv_core" / "tiers" / "simready_foundation_tier_core"
    module_path = tier_root / "simready" / "foundation" / "tier_core" / "_tier.py"
    module_name = "simready.foundation.tier_core._tier_contract_test"

    monkeypatch.syspath_prepend(str(tier_root))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    expected = (tier_root / "simready_benchmark_kit_suite").resolve()
    assert module.tier.runtime_tests_path == expected
    assert module.tier.runtime_tests_path.is_dir()
    assert module._owned_package_directory("package_that_does_not_exist_for_simready_tests") is None
    assert module._owned_package_directory("pytest") is None


def test_built_core_tier_wheel_contains_runtime_test_contract():
    if os.environ.get("SIMREADY_REQUIRE_BUILT_TIER_WHEEL") != "1":
        pytest.skip("set SIMREADY_REQUIRE_BUILT_TIER_WHEEL=1 after building the tier wheel")

    root = _foundation_root()
    wheels = sorted((root / "nv_core" / "tiers" / "_build" / "dist").glob("simready_foundation_tier_core-*.whl"))
    if not wheels:
        pytest.fail("the tier build produced no simready-foundation-tier-core wheel")

    assert len(wheels) == 1, [wheel.name for wheel in wheels]
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        assert "simready_benchmark_kit_suite/__init__.py" in names
        assert "simready_benchmark_kit_suite/README.md" in names
        assert "simready_benchmark_kit_suite/docs/authoring.md" in names
        assert "simready_benchmark_kit_suite/docs/tests.md" in names
        assert "simready_benchmark_kit_suite/docs/_images/presence.png" in names
        assert "simready/foundation/tier_core/_tier.py" in names
        entry_point_files = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        assert len(entry_point_files) == 1
        entry_points = archive.read(entry_point_files[0]).decode("utf-8")
        assert "[simready.tier]" in entry_points
        assert "tier_core = simready.foundation.tier_core:tier" in entry_points


def test_tier_builder_emits_only_workspace_tier_wheels(tmp_path, monkeypatch):
    tiers = tmp_path / "tiers"
    for name in ("tier_core",):
        package = tiers / name
        package.mkdir(parents=True)
        (package / "pyproject.toml").write_text("[project]\nname='x'\nversion='1'\n", encoding="utf-8")
    commands = []

    def fake_run(command):
        commands.append(command)
        staging_dir = Path(command[command.index("--out-dir") + 1])
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "tier_core-1-py3-none-any.whl").touch()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bt.subprocess, "run", fake_run)

    built, failures = bt.build_tiers(str(tiers), uv="uv")

    assert failures == []
    assert len(built) == 1
    assert "--all-packages" in commands[0]
    assert len(commands) == 1


def test_tier_builder_preserves_unrelated_output_content(tmp_path, monkeypatch):
    tiers = tmp_path / "tiers"
    package = tiers / "tier_core"
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text("[project]\nname='tier-core'\nversion='1'\n", encoding="utf-8")
    out_dir = tiers / "_build" / "dist"
    out_dir.mkdir(parents=True)
    unrelated_file = out_dir / "keep.txt"
    unrelated_file.write_text("user content", encoding="utf-8")
    unrelated_wheel = out_dir / "another_project-1-py3-none-any.whl"
    unrelated_wheel.touch()
    malformed_wheel = out_dir / "keep.whl"
    malformed_wheel.touch()
    stale_tier_wheel = out_dir / "tier_core-0-py3-none-any.whl"
    stale_tier_wheel.touch()

    def fake_run(command):
        staging_dir = Path(command[command.index("--out-dir") + 1])
        (staging_dir / "tier_core-1-py3-none-any.whl").touch()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bt.subprocess, "run", fake_run)

    built, failures = bt.build_tiers(str(tiers), uv="uv")

    assert failures == []
    assert built == [str(out_dir / "tier_core-1-py3-none-any.whl")]
    assert unrelated_file.read_text(encoding="utf-8") == "user content"
    assert unrelated_wheel.is_file()
    assert malformed_wheel.is_file()
    assert not stale_tier_wheel.exists()


def test_failed_tier_build_does_not_change_published_output(tmp_path, monkeypatch):
    tiers = tmp_path / "tiers"
    package = tiers / "tier_core"
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text("[project]\nname='tier-core'\nversion='1'\n", encoding="utf-8")
    out_dir = tiers / "_build" / "dist"
    out_dir.mkdir(parents=True)
    previous_wheel = out_dir / "tier_core-0-py3-none-any.whl"
    previous_wheel.touch()

    monkeypatch.setattr(bt.subprocess, "run", lambda _command: SimpleNamespace(returncode=1))

    built, failures = bt.build_tiers(str(tiers), uv="uv")

    assert built == []
    assert failures == ["tier uv build exited 1"]
    assert previous_wheel.is_file()
