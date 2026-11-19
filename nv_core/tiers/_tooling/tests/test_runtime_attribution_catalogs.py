# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""QA profile overrides retain the selected Foundation validation catalogs."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

CHECK_PATH = Path(__file__).resolve().parents[3] / "sr_specs/tests/validate_runtime_attribution.py"
spec = importlib.util.spec_from_file_location("validate_runtime_attribution", CHECK_PATH)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def values(command, flag):
    return [command[index + 1] for index, value in enumerate(command) if value == flag]


@pytest.fixture
def cli_calls(monkeypatch):
    """Capture public CLI arguments without needing USD or validator packages."""
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        # Empty reports remain failed QA evidence; these tests inspect catalog
        # selection, not simulated validator outcomes.
        Path(values(command, "--output")[0]).write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(check.subprocess, "run", run)
    monkeypatch.setattr(check, "make_fixture", lambda directory, case: directory / "asset.usda")
    return commands


def descriptor(root, name):
    package = root / name
    for directory in ("rules_and_reqs", "features", "capabilities"):
        (package / directory).mkdir(parents=True)
    if name == "tier_core":
        (package / "profiles").mkdir()
    return SimpleNamespace(
        name=name,
        rules_and_requirements_path=package / "rules_and_reqs",
        feature_contracts_path=package / "features",
        capability_contracts_path=package / "capabilities",
        profile_contracts_path=package / "profiles",
    )


def test_default_commands_keep_installed_catalogs_with_qa_profiles(tmp_path, monkeypatch, cli_calls):
    core = descriptor(tmp_path, "tier_core")
    newton = descriptor(tmp_path, "tier_newton")
    # Entry-point names vary between wheels; the native descriptor identifies
    # the tier. Newton contributes contracts without a profiles directory.
    entries = [SimpleNamespace(name="newton", value="newton:tier", load=lambda: newton),
               SimpleNamespace(name="tier_core", value="core:tier", load=lambda: core)]

    def entry_points(*, group):
        assert group == "simready.tier"
        return entries

    monkeypatch.setattr(check, "entry_points", entry_points)
    output = tmp_path / "evidence"
    monkeypatch.setattr(check.sys, "argv", [str(CHECK_PATH), "--output", str(output), "--validator", "simready-validate"])
    assert check.main() == 1  # Empty reports cannot pass the attribution gate.
    assert len(cli_calls) == 3
    for index, command in enumerate(cli_calls):
        assert set(values(command, "--rules-path")) == {
            str(core.rules_and_requirements_path), str(newton.rules_and_requirements_path)}
        assert set(values(command, "--features-path")) == {
            str(tier_path) for tier in (core, newton)
            for tier_path in (tier.feature_contracts_path, tier.capability_contracts_path)}
        profiles = values(command, "--profiles-path")
        assert str(core.profile_contracts_path) in profiles
        assert str(newton.profile_contracts_path) not in profiles
        if index == 0:
            assert values(command, "--profile") == ["Robotics-Prop"]
            assert values(command, "--version") == ["5.0.0"]
            assert profiles == [str(core.profile_contracts_path)]
        else:
            assert len(profiles) == 2
            assert Path(profiles[-1]).is_file()
            assert Path(profiles[-1]).parent == output
    assert json.loads((output / "qa_result.json").read_text())["qa_passed"] is False


def test_source_commands_do_not_discover_installed_tiers(tmp_path, monkeypatch, cli_calls):
    source = tmp_path / "source"
    for name in ("core", "newton"):
        package = source / f"nv_core/tiers/simready_foundation_tier_{name}/simready/foundation/tier_{name}"
        for directory in ("rules_and_reqs", "features", "capabilities", "profiles"):
            (package / directory).mkdir(parents=True)

    def unexpected_discovery(**kwargs):
        pytest.fail("--catalog-root must not load installed tier entry points")

    monkeypatch.setattr(check, "entry_points", unexpected_discovery)
    monkeypatch.setattr(check.sys, "argv", [str(CHECK_PATH), "--output", str(tmp_path / "evidence"),
                                          "--validator", "simready-validate", "--catalog-root", str(source)])
    assert check.main() == 1
    assert len(cli_calls) == 3
    for command in cli_calls:
        for flag, count in (("--rules-path", 2), ("--features-path", 4)):
            paths = values(command, flag)
            assert len(paths) == count
            assert all(Path(path).is_relative_to(source) for path in paths)
        profiles = values(command, "--profiles-path")
        assert sum(Path(path).is_relative_to(source) for path in profiles) == 2


def test_missing_installed_tier_reports_the_dependency(tmp_path, monkeypatch):
    core = descriptor(tmp_path, "tier_core")
    monkeypatch.setattr(check, "entry_points", lambda **kwargs: [
        SimpleNamespace(name="tier_core", value="core:tier", load=lambda: core)])
    with pytest.raises(RuntimeError, match="Missing installed simready.tier descriptors: tier_newton"):
        check.installed_catalog_args()
