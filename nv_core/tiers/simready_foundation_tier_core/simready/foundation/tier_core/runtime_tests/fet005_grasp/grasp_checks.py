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

Discovers direct BasisCurves and legacy wrapped grasp identifiers. Returns SKIP
if none are found (the asset validator GSP.001 handles structural
validation, the benchmark only needs identifiers to test against).
"""

from pxr import Usd, UsdGeom


def grasp_point_source(identifier):
    """Return the authored points prim and values, without inventing a segment.

    GSP.001's direct BasisCurves form owns its points. Legacy Xform wrappers
    retain their first eligible immediate child, including historical Points
    or mesh-based line geometry. Validation of finite nonzero world geometry
    remains required before creating a fixture.
    """
    candidates = (identifier,) if identifier.IsA(UsdGeom.BasisCurves) else identifier.GetChildren()
    for prim in candidates:
        attribute = prim.GetAttribute("points")
        if not attribute:
            continue
        points = attribute.Get()
        if points is not None and hasattr(points, "__len__") and len(points) >= 2:
            return prim, points
    return None


def discover_grasp_identifiers(stage, asset_root_path):
    # type: (Usd.Stage, str) -> list[str]
    """Find named direct curves and legacy Xform identifiers under the asset.

    Returns a list of absolute prim paths.
    """
    root_prim = stage.GetPrimAtPath(asset_root_path)
    if not root_prim or not root_prim.IsValid():
        return []
    identifiers = [
        prim
        for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        if prim.GetName().startswith("grasp_identifier") and (prim.IsA(UsdGeom.Xform) or prim.IsA(UsdGeom.BasisCurves))
    ]
    # A named curve already consumed by a legacy wrapper is the same segment,
    # not a second grasp trial. Other named curves remain separate identifiers.
    wrapped_sources = set()
    for prim in identifiers:
        if prim.IsA(UsdGeom.Xform):
            source = grasp_point_source(prim)
            if source is not None:
                wrapped_sources.add(str(source[0].GetPath()))
    return [str(prim.GetPath()) for prim in identifiers if str(prim.GetPath()) not in wrapped_sources]


def run_pre_checks(stage, asset_root_path):
    # type: (Usd.Stage, str) -> tuple[Optional[str], list[str]]
    """Run pre-checks and discover grasp identifiers.

    Returns:
        (result_string, identifier_paths).
        result_string is None if OK to proceed, or "SKIP: ..." if
        the test should be skipped. identifier_paths is the list of
        discovered grasp_identifier prim paths (empty if skipped).
    """
    identifiers = discover_grasp_identifiers(stage, asset_root_path)
    if not identifiers:
        from simready.foundation.tier_core.runtime_tests._assessment import (
            _has_complete_asset_composition,
        )

        root_prim = stage.GetPrimAtPath(asset_root_path) if stage is not None else None
        if not _has_complete_asset_composition(stage, root_prim, inspection_includes_instance_proxies=True):
            raise RuntimeError(
                "Cannot establish absence of grasp identifiers: asset root or composition is unavailable"
            )
        if any(
            prim.GetName().startswith("grasp_identifier")
            for prim in Usd.PrimRange(root_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))
        ):
            return ("SKIP: grasp_identifier prims exist but use an unsupported runtime form", [])
        return ("SKIP: no grasp_identifier prims found on asset", [])

    # Kit-plugin guardrail: skip cleanly if the asset's collision setup
    # would crash Kit during physics cooking.
    from simready.evaluate_engine_kit.physics_utils import check_physics_ready

    skip_msg = check_physics_ready(stage, asset_root_path)
    if skip_msg is not None:
        return (skip_msg, [])

    return (None, identifiers)
