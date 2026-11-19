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
"""Contract checks for tool content force-included in the tier wheel."""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path


def test_wheel_contains_descriptor_and_adapter_tree(tmp_path: Path) -> None:
    tier_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=tier_root,
        env={**os.environ, "UV_CACHE_DIR": str(tmp_path / "uv-cache")},
        check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
        entry_points_file = next(name for name in members if name.endswith(".dist-info/entry_points.txt"))
        entry_points_text = archive.read(entry_points_file).decode()

    prefix = "simready/foundation/tier_core/"
    assert prefix + "_tier.py" in members
    assert prefix + "asset_handler_modules/__init__.py" in members
    assert prefix + "asset_handler_modules/neutral_to_physx/__init__.py" in members
    assert prefix + "asset_handler_modules/neutral_to_newton/__init__.py" in members
    assert prefix + "asset_handler_modules/neutral_to_mujoco/__init__.py" in members
    assert prefix + "asset_handler_modules/physx_to_isaacsim/__init__.py" in members
    assert prefix + "asset_handler_modules/physx_to_isaacsim/promotion.py" in members
    assert prefix + "asset_handler_modules/physx_to_isaacsim/materialize.py" in members
    assert "simready/asset_transformer/api.py" in members
    assert "simready/asset_transformer/cli.py" in members
    assert "simready/asset_transformer/profile_transforms/simready_physx_to_isaac_prop.json" in members
    assert "simready/asset_transformer/profile_transforms/simready_physx_to_isaac_robot.json" in members
    assert "simready/asset_transformer/patches/apply.py" in members
    assert "simready/asset_transformer/patches/isolated_620.py" in members
    assert "simready/asset_transformer/patches/geometries_601.py" not in members
    assert "simready/asset_transformer/rules/structure/thumbnails.py" in members
    assert "simready/asset_transformer/rules/perf/runtime_instances.py" in members
    assert "simready/asset_transformer/rules/structure/interface.py" in members
    assert "simready/asset_transformer/rules/structure/prop_cleanup.py" in members
    assert "simready/asset_transformer/manager.py" not in members
    assert "simready/asset_transformer/models.py" not in members
    assert "simready/asset_transformer/rules/perf/geometries.py" not in members
    assert "simready/asset_transformer/rules/perf/materials.py" not in members
    assert "simready/asset_transformer/rules/structure/flatten.py" not in members
    assert not any(name.endswith((".pyc", "/__pycache__")) for name in members)

    assert "[simready.feature_adapters]" in entry_points_text
    assert "tier_core = simready.foundation.tier_core.asset_handler_modules:get_feature_adapters" in entry_points_text
    assert "[console_scripts]" in entry_points_text
    assert "simready-transform-asset = simready.asset_transformer.cli:main" in entry_points_text
