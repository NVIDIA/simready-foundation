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

"""Keep standalone source validation and installed-tier CI on the same schemas."""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

_ROOT = Path(__file__).resolve().parents[4]
_CORE = _ROOT / "nv_core" / "tiers" / "simready_foundation_tier_core"
_NEWTON = _ROOT / "nv_core" / "tiers" / "simready_foundation_tier_newton"


def _package_requirement(requirements, name):
    return next(requirement for requirement in map(Requirement, requirements) if requirement.name == name)


def _core_schema_requirement():
    project = tomllib.loads((_CORE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return _package_requirement(project["dependencies"], "physx-usd-schemas")


def _aif_version_requirement():
    project = tomllib.loads(
        (_ROOT / "nv_core/tiers/simready_foundation_tier_aif/pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    return _package_requirement(project["dependencies"], "semver")


def test_core_installs_newton_without_runtime_extras_or_a_base_dependency_cycle():
    core = tomllib.loads((_CORE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    newton = tomllib.loads((_NEWTON / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependency = _package_requirement(core["dependencies"], newton["name"])
    assert not dependency.extras
    assert dependency.marker is None
    assert dependency.specifier.contains(newton["version"], prereleases=True)
    assert not dependency.specifier.contains("2026.10.0rc1", prereleases=True)
    assert all(Requirement(item).name != core["name"] for item in newton["dependencies"])
    for extra in newton["optional-dependencies"].values():
        assert all(Requirement(item).name != core["name"] for item in extra)
    test_requirements = (_CORE / "tests/requirements.txt").read_text(encoding="utf-8").splitlines()
    dependencies = [line for line in test_requirements if line and not line.startswith(("#", "-"))]
    assert _package_requirement(dependencies, newton["name"]).specifier == dependency.specifier


def test_cross_tier_dependencies_have_workspace_sources():
    workspace_root = _ROOT / "nv_core" / "tiers"
    workspace = tomllib.loads((workspace_root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["uv"]
    members = {}
    for member in workspace["workspace"]["members"]:
        config = tomllib.loads((workspace_root / member / "pyproject.toml").read_text(encoding="utf-8"))
        members[config["project"]["name"]] = config
    for name, config in members.items():
        project = config["project"]
        dependencies = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            dependencies.extend(extra)
        sources = dict(workspace.get("sources", {}))
        sources.update(config.get("tool", {}).get("uv", {}).get("sources", {}))
        for dependency in map(Requirement, dependencies):
            if dependency.name in members:
                assert sources.get(dependency.name, {}).get("workspace") is True, (name, dependency.name)


@pytest.mark.parametrize("python", ["3.11", "3.12", "3.13"])
def test_required_newton_tier_supports_core_python_versions(python):
    core = tomllib.loads((_CORE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    newton = tomllib.loads((_NEWTON / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert python in SpecifierSet(core["requires-python"])
    assert python in SpecifierSet(newton["requires-python"])


def _ci_job(name):
    text = (_ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^" + re.escape(name) + r":\s*\n(.*?)(?=^[^\s#]|\Z)", text)
    assert match is not None, name
    return match.group(1)


@pytest.mark.parametrize(
    "job, script",
    [
        ("test-sample-content-validation", "tests/validate_sample_content.py"),
        ("test-spec-consistency", "tests/validate_requirement_examples.py"),
        ("test-spec-consistency", "tests/validate_feature_versions.py"),
    ],
)
def test_source_validation_ci_installs_core_schema_dependency(job, script):
    commands = re.findall(r"(?m)^    - >\n((?:^      .*\n)+)", _ci_job(job))
    selected = [command for command in commands if script in shlex.split(command)]
    assert len(selected) == 1, selected
    tokens = shlex.split(selected[0])
    dependencies = [tokens[index + 1] for index, token in enumerate(tokens) if token == "--with"]
    assert _package_requirement(dependencies, "physx-usd-schemas").specifier == _core_schema_requirement().specifier
    assert _package_requirement(dependencies, "semver").specifier == _aif_version_requirement().specifier
    validator = _package_requirement(dependencies, "simready-validate")
    assert not validator.specifier.contains("2026.10.0rc0", prereleases=True)
    assert validator.specifier.contains("2026.10.0rc1", prereleases=True)


@pytest.mark.parametrize("relative_path", ["requirements.txt", "nv_core/sr_specs/tests/requirements.txt"])
def test_source_validation_requirements_include_core_schema_dependency(relative_path):
    lines = (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
    dependencies = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith(("#", "-"))]
    assert _package_requirement(dependencies, "physx-usd-schemas").specifier == _core_schema_requirement().specifier
    assert _package_requirement(dependencies, "semver").specifier == _aif_version_requirement().specifier


@pytest.mark.parametrize(
    "relative_path",
    [
        "requirements.txt",
        "nv_core/sr_specs/tests/requirements.txt",
        "nv_core/tiers/simready_foundation_tier_aif/tests/requirements.txt",
    ],
)
def test_validation_requirements_exclude_the_old_neutral_id_reader(relative_path):
    lines = (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
    dependencies = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith(("#", "-"))]
    validator = _package_requirement(dependencies, "simready-validate")
    assert not validator.specifier.contains("2026.10.0rc0", prereleases=True)
    assert validator.specifier.contains("2026.10.0rc1", prereleases=True)


def test_core_ci_runs_real_physx_schema_compatibility_regressions():
    test_path = "nv_core/tiers/simready_foundation_tier_core/tests/test_physx_schema_compatibility.py"
    assert test_path in _ci_job("test-tier-wheels")
    assert (_ROOT / test_path).is_file()


def test_tier_wheel_ci_environment_resolves_an_index_only_package(tmp_path):
    """Catch pip-only index settings silently ignored by the CI uv resolver."""
    # uv run exposes its own executable even when repoman did not add it to PATH.
    uv = os.environ.get("UV") or shutil.which("uv")
    if uv is None:
        assert os.environ.get("SIMREADY_REQUIRE_BUILT_TIER_WHEEL") != "1", "Tier-wheel CI must expose its uv executable"
        pytest.skip("uv executable is required for the CI resolver regression")

    index = tmp_path / "index"
    package = index / "simready-ci-index-probe"
    package.mkdir(parents=True)
    wheel = package / "simready_ci_index_probe-1.0-py3-none-any.whl"
    dist_info = "simready_ci_index_probe-1.0.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\nName: simready-ci-index-probe\nVersion: 1.0\n",
        )
        archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr(f"{dist_info}/RECORD", "")
    (package / "index.html").write_text(f'<a href="{wheel.name}">{wheel.name}</a>', encoding="utf-8")
    empty_index = tmp_path / "empty-index"
    empty_index.mkdir()
    requirements = tmp_path / "requirements.in"
    requirements.write_text("simready-ci-index-probe==1.0\n", encoding="utf-8")

    # Preserve the job's variable names, redirecting registry URLs to a local
    # simple index. Neither the corporate registry nor PyPI is contacted.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(("UV_", "PIP_"))}
    variables = re.search(r"(?ms)^  variables:\n(.*?)(?=^  \S)", _ci_job("test-tier-wheels"))
    assert variables is not None
    for key, value in re.findall(r"(?m)^    (\w+):\s*([^\n]+)", variables.group(1)):
        value = shlex.split(value)[0]
        environment[key] = index.as_uri() if value.startswith("https://") else value
    resolved = subprocess.run(
        [
            uv,
            "--no-config",
            "--no-cache",
            "--offline",
            "pip",
            "compile",
            "--index-url",
            empty_index.as_uri(),
            "--python",
            sys.executable,
            "--no-python-downloads",
            str(requirements),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert resolved.returncode == 0, resolved.stderr
    assert "simready-ci-index-probe==1.0" in resolved.stdout.splitlines()


def test_source_prebundle_installs_aif_version_parser():
    config = tomllib.loads((_ROOT / "deps/pip.toml").read_text(encoding="utf-8"))
    packages = [package for dependency in config["dependency"] for package in dependency["packages"]]
    assert _package_requirement(packages, "semver").specifier == _aif_version_requirement().specifier
