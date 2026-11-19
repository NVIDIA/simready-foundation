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

"""Owned runtime namespaces resolve without loading runtime or validator code."""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("tier,package", [("core", "tier_core"), ("newton", "tier_newton"), ("sensors", "sensors")])
def test_namespaced_suite_owned_by_its_tier(tier, package):
    root = ROOT / "nv_core/tiers" / ("simready_foundation_tier_" + tier)
    owned = root / "simready/foundation" / package / "runtime_tests"
    assert (owned / "__init__.py").is_file()
    provider = "simready.foundation." + package + ".runtime_tests"
    alias = {
        "core": "simready_benchmark_kit_suite",
        "newton": "simready_benchmark_newton_suite",
        "sensors": "simready_benchmark_sensors_kit_suite",
    }[tier]
    assert json.loads((owned / "benchmark-provider.json").read_text()) == {
        "provider": provider,
        "import_package": provider,
        "aliases": [alias],
    }
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    assert metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["simready"]
    assert "evaluate" in metadata["project"]["optional-dependencies"]
    assert (
        metadata["project"]["optional-dependencies"]["benchmark"]
        == metadata["project"]["optional-dependencies"]["evaluate"]
    )


@pytest.mark.parametrize("tier,package", [("core", "tier_core"), ("newton", "tier_newton"), ("sensors", "sensors")])
def test_descriptor_never_imports_runtime_dependencies(tier, package):
    root = ROOT / "nv_core/tiers" / ("simready_foundation_tier_" + tier)
    descriptor = root / "simready/foundation" / package / "_tier.py"
    code = """
import importlib, importlib.abc, pathlib, sys
class BlockRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(part in fullname for part in ('evaluate', 'runtime_tests', 'rules_and_reqs', 'requirements')) or fullname.split('.')[0] in ('pxr', 'omni', 'isaacsim'):
            raise AssertionError('descriptor attempted runtime import: ' + fullname)
sys.meta_path.insert(0, BlockRuntime())
path = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(path.parents[3]))
name = 'simready.foundation.' + sys.argv[2] + '._tier'
module = importlib.import_module(name)
assert pathlib.Path(module.__file__).resolve() == path.resolve()
assert module.tier.runtime_tests_path == path.parent / 'runtime_tests', module.tier.runtime_tests_path
assert module._owned_package_directory('pytest') is None
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(descriptor), package], text=True, capture_output=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
