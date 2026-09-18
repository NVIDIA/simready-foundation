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

"""Tests for tier and external-package discovery used by ``build_tiers``.

These tests exercise pure discovery helpers (no ``uv`` invocation) so they run
in any environment.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_BUILD_TIERS_PATH = Path(__file__).resolve().parents[1] / "build_tiers.py"


def _load_build_tiers():
    spec = importlib.util.spec_from_file_location("simready_build_tiers", _BUILD_TIERS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_tiers = _load_build_tiers()
_TIERS_ROOT = build_tiers._TIERS_ROOT


def test_discover_tiers_includes_core_tier():
    tiers = [os.path.basename(t) for t in build_tiers.discover_tiers(_TIERS_ROOT)]
    assert "simready_foundation_tier_core" in tiers


def test_discover_tiers_skips_tooling_and_workspace_root():
    tiers = [os.path.basename(t) for t in build_tiers.discover_tiers(_TIERS_ROOT)]
    assert "_tooling" not in tiers


def test_discover_external_packages_includes_isaac_transformer():
    external = [os.path.basename(p) for p in build_tiers.discover_external_packages(_TIERS_ROOT)]
    assert "isaac_asset_transformer" in external


def test_external_packages_have_pyproject():
    for pkg_dir in build_tiers.discover_external_packages(_TIERS_ROOT):
        assert os.path.isfile(os.path.join(pkg_dir, "pyproject.toml"))


def test_expected_wheel_count_covers_tiers_and_external():
    tiers = build_tiers.discover_tiers(_TIERS_ROOT)
    external = build_tiers.discover_external_packages(_TIERS_ROOT)
    # At minimum: the core tier plus the standalone Isaac transformer.
    assert len(tiers) + len(external) >= 2
