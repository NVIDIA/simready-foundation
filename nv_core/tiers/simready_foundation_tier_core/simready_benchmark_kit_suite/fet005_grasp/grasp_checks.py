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
"""Pre-checks for FET005 grasp-and-lift test.

Discovers grasp_identifier Xform prims on the asset. Returns SKIP
if none are found (the asset validator GSP.001 handles structural
validation, the benchmark only needs identifiers to test against).
"""

from pxr import Usd, UsdGeom


def discover_grasp_identifiers(stage, asset_root_path):
    # type: (Usd.Stage, str) -> List[str]
    """Find all grasp_identifier_* Xform prims under the asset.

    Returns a list of absolute prim paths.
    """
    root_prim = stage.GetPrimAtPath(asset_root_path)
    if not root_prim or not root_prim.IsValid():
        return []
    paths = []
    for prim in Usd.PrimRange(root_prim):
        if prim.GetName().startswith("grasp_identifier") and prim.IsA(UsdGeom.Xform):
            paths.append(str(prim.GetPath()))
    return paths


def run_pre_checks(stage, asset_root_path):
    # type: (Usd.Stage, str) -> Tuple[Optional[str], List[str]]
    """Run pre-checks and discover grasp identifiers.

    Returns:
        (result_string, identifier_paths).
        result_string is None if OK to proceed, or "SKIP: ..." if
        the test should be skipped. identifier_paths is the list of
        discovered grasp_identifier prim paths (empty if skipped).
    """
    identifiers = discover_grasp_identifiers(stage, asset_root_path)
    if not identifiers:
        return ("SKIP: no grasp_identifier prims found on asset", [])

    # Kit-plugin guardrail: skip cleanly if the asset's collision setup
    # would crash Kit during physics cooking.
    from simready_benchmark_engine_kit.physics_utils import check_physics_ready

    skip_msg = check_physics_ready(stage, asset_root_path)
    if skip_msg is not None:
        return (skip_msg, [])

    return (None, identifiers)
