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

import importlib.util
import os
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[4]
_TIERS = _ROOT / "nv_core" / "tiers"


def _test_config():
    return tomllib.loads((_ROOT / "repo.toml").read_text(encoding="utf-8"))["repo_test"]


def test_default_suites_preserve_upstream_coverage_and_add_newton():
    config = _test_config()
    assert config["default_suite"] == [
        "tier_tooling",
        "all_tiers",
        "isaac_asset_transformer",
        "tier_core",
        "tier_aif",
        "tier_newton",
    ]
    assert len({config["suites"][name]["log_file"] for name in config["default_suite"]}) == 6


@pytest.mark.parametrize("tier", ["core", "newton"])
def test_runtime_suite_venvs(tier):
    suite = _test_config()["suites"]["tier_" + tier]
    relative = "nv_core/tiers/simready_foundation_tier_" + tier
    assert suite["kind"] == "pytest"
    assert suite["discover_path"] == "${root}/" + relative + "/tests"
    assert suite["python_source_path"] == "${root}/" + relative
    assert len(suite["venv"]) == 1
    venv = suite["venv"][0]
    assert venv["pip_requirements"] == "${root}/" + relative + "/tests/requirements.txt"
    assert venv["path"] == "${test_root}/_build/venvs/${suite_name}"
    assert venv["packman_package_version"] == "3.12.10+nv3-${platform}"
    assert venv["pip_extra_index_urls"] == [
        "https://artifactory.nvidia.com/artifactory/api/pypi/ct-omniverse-pypi/simple",
    ]


@pytest.mark.parametrize("tier", ["core", "newton"])
@pytest.mark.parametrize("installed", [False, True])
def test_runtime_bootstrap_adds_source_only_without_an_installed_tier(tier, installed, monkeypatch):
    monkeypatch.delenv('SIMREADY_FOUNDATION_SOURCE_ROOTS', raising=False)
    generated = []
    monkeypatch.setattr(sys, "path", list(sys.path))
    source_names = ("core",) if tier == "core" else ("core", "newton")
    roots = [_TIERS / ("simready_foundation_tier_" + name) for name in source_names]
    for root in roots:
        while str(root) in sys.path:
            sys.path.remove(str(root))
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: SimpleNamespace() if installed else None)
    monkeypatch.setitem(
        sys.modules, "checkout_requirements", SimpleNamespace(ensure_checkout_requirements=generated.append)
    )
    runpy.run_path(str(_TIERS / ("simready_foundation_tier_" + tier) / "tests/conftest.py"))
    assert generated == roots
    assert all((str(root) in sys.path) is (not installed) for root in roots)


def test_explicit_source_selection_overrides_an_installed_tier_without_replacing_namespace(tmp_path):
    source = tmp_path / 'source'
    installed = tmp_path / 'installed'
    for root, value in ((source, 'selected'), (installed, 'wrong')):
        package = root / 'simready/foundation/tier_core'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text(f'OWNER = {value!r}\n')
    code = '''
import sys
sys.path[:0] = sys.argv[1:4]
import simready, simready.foundation
parent = simready.foundation
from source_tiers import select_source_tiers
select_source_tiers()
from simready.foundation import tier_core
assert tier_core.OWNER == 'selected', tier_core.__file__
assert sys.modules['simready.foundation'] is parent
'''
    env = dict(os.environ, SIMREADY_FOUNDATION_SOURCE_ROOTS=str(source))
    env.pop('SIMREADY_REQUIRE_BUILT_TIER_WHEEL', None)
    result = subprocess.run([sys.executable, '-B', '-c', code, str(installed), str(source), str(_TIERS / '_tooling')], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_source_selection_rejects_an_already_imported_installed_copy(tmp_path):
    source = tmp_path / 'source'
    installed = tmp_path / 'installed'
    for root in (source, installed):
        package = root / 'simready/foundation/tier_core'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('')
    code = '''
import sys
sys.path[:0] = sys.argv[1:4]
import simready.foundation.tier_core
from source_tiers import select_source_tiers
try:
    select_source_tiers()
except RuntimeError as exc:
    assert 'already imported' in str(exc)
else:
    raise AssertionError('installed copy was silently reused')
'''
    env = dict(os.environ, SIMREADY_FOUNDATION_SOURCE_ROOTS=str(source))
    env.pop('SIMREADY_REQUIRE_BUILT_TIER_WHEEL', None)
    result = subprocess.run([sys.executable, '-B', '-c', code, str(installed), str(source), str(_TIERS / '_tooling')], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('source_selected', [False, True])
def test_built_wheel_selection_rejects_source_conflicts_before_import_mutations(tmp_path, source_selected):
    source = tmp_path / 'source'
    installed = tmp_path / 'installed'
    for root, content in (
        (source, 'raise AssertionError("source tier must not be imported")\n'),
        (installed, 'OWNER = "installed"\n'),
    ):
        package = root / 'simready/foundation/tier_core'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text(content)
    code = '''
import os, sys
sys.path[:0] = sys.argv[1:3]
import simready, simready.foundation
from source_tiers import select_source_tiers
namespaces = (simready, simready.foundation)
paths = list(sys.path)
namespace_paths = tuple(namespace.__path__ for namespace in namespaces)
locations = tuple(list(path) for path in namespace_paths)
modules = dict(sys.modules)
try:
    select_source_tiers()
except RuntimeError as exc:
    assert os.environ['SIMREADY_FOUNDATION_SOURCE_ROOTS']
    assert 'SIMREADY_FOUNDATION_SOURCE_ROOTS' in str(exc)
    assert 'SIMREADY_REQUIRE_BUILT_TIER_WHEEL' in str(exc)
else:
    assert not os.environ['SIMREADY_FOUNDATION_SOURCE_ROOTS'], 'conflicting modes accepted'
assert sys.path == paths
assert all(namespace.__path__ is path for namespace, path in zip(namespaces, namespace_paths))
assert tuple(list(namespace.__path__) for namespace in namespaces) == locations
if os.environ['SIMREADY_FOUNDATION_SOURCE_ROOTS']:
    assert sys.modules == modules
assert 'simready.foundation.tier_core' not in sys.modules
from simready.foundation import tier_core
assert tier_core.OWNER == 'installed', tier_core.__file__
'''
    env = dict(
        os.environ,
        SIMREADY_FOUNDATION_SOURCE_ROOTS=str(source) if source_selected else '',
        SIMREADY_REQUIRE_BUILT_TIER_WHEEL='1',
    )
    result = subprocess.run(
        [sys.executable, '-B', '-c', code, str(installed), str(_TIERS / '_tooling')],
        env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
