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
"""PhysxMimicJointAPI detection for the MIM phase.

MCP lookup (resolved 2026-04-24 in plan Task 1 Step 1):
- MCP did not return PhysxMimicJointAPI attribute tokens; accessor names
  verified at test time via PhysxSchema.PhysxMimicJointAPI.Apply on a live
  in-memory stage.
  If the mimic attribute names below do not match the live schema, update
  _read_reference_target, _read_gear, and _read_offset accordingly.
"""
from dataclasses import dataclass
from typing import Optional

from simready_benchmark_kit_suite.articulation_phases.joint_utils import (  # noqa: F401  (imported for parity)
    safe_len,
)


@dataclass(frozen=True)
class MimicJointSpec:
    follower_joint_path: str
    reference_joint_path: str
    gear: float
    offset: float
    follower_dof_index: Optional[int]
    reference_dof_index: Optional[int]


def detect_mimic_joints(stage, asset_prim, robot_prim_path, dof_names):
    # type: (Any, Any, str, List[str]) -> List[MimicJointSpec]
    """Return one MimicJointSpec per joint under asset_prim with PhysxMimicJointAPI.

    Returns [] when stage/asset_prim is invalid or no mimic joints are authored.
    A mimic without a resolvable reference target is skipped (v1 parity).

    Uses Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate) so instanced robots
    are handled correctly (foundation spec 10.5).
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return []
    try:
        from pxr import PhysxSchema, Usd, UsdPhysics  # noqa: F401
    except Exception:
        return []

    # ``asset_prim`` (the articulation-root prim) may be a deep descendant
    # of the asset's wrapper -- e.g. when ``setup_robot_test_scene``
    # normalizes a joint-rooted articulation (Schunk EZU-35's
    # ``root_joint``) into a body-rooted one, ``robot.prim_path`` ends up
    # pointing at the housing body, while the driven joints with
    # ``PhysxMimicJointAPI`` are siblings of the housing under
    # ``/<asset>/joints/...``. ``PrimRange(housing)`` would never see them.
    # Walk up to the first prim under the stage's top-level scope so
    # ``PrimRange`` covers the whole asset subtree regardless of whether
    # the articulation root is on the asset wrapper, on a body inside it,
    # or on a joint inside it. For body-rooted assets like Robotiq 2F-85
    # this lift is also safe (its articulation root is already the asset
    # wrapper, so the loop runs zero or one iterations).
    #
    # The "top-level scope" boundary is, in priority: the stage's
    # default prim path (covers test runners that author under a
    # non-``/World`` root), then ``/World`` (the convention this repo's
    # test runner uses), then pseudo-root. Without the defaultPrim
    # check, a runner that places assets under e.g. ``/TestScene/...``
    # would walk all the way to pseudo-root and ``PrimRange`` would
    # traverse the entire stage -- correct results, but a perf hit on
    # large stages.
    try:
        default_prim = stage.GetDefaultPrim()
        default_prim_path_str = str(default_prim.GetPath()) if default_prim and default_prim.IsValid() else None
    except Exception:
        default_prim_path_str = None
    iter_root = asset_prim
    while True:
        parent = iter_root.GetParent()
        if not parent or not parent.IsValid() or parent.IsPseudoRoot():
            break
        parent_path_str = str(parent.GetPath())
        if default_prim_path_str is not None and parent_path_str == default_prim_path_str:
            break
        if parent_path_str == "/World":
            break
        iter_root = parent

    results = []
    for prim in Usd.PrimRange(iter_root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        if not (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)):
            continue

        # PhysxMimicJointAPI is a multi-apply schema where the instance name IS
        # the axis token (rotX/rotY/rotZ for revolute, transX/transY/transZ for
        # prismatic). A joint may carry one or more applied instances; iterate
        # them all so prismatic joints and joints on Y/Z axes are not silently
        # ignored.
        #
        # IMPORTANT: We iterate ``GetPrimTypeInfo().GetAppliedAPISchemas()``
        # (the raw apiSchemas metadata) rather than ``GetAppliedSchemas()``,
        # because the public accessor filters to REGISTERED schemas only and
        # some assets (e.g. the Schunk EZU-35) carry PhysxMimicJointAPI
        # instances that don't always resolve through the public accessor.
        # The raw metadata accessor never filters and always shows the
        # ``PhysxMimicJointAPI:rotX`` form. We also drop the
        # ``prim.HasAPI(PhysxMimicJointAPI)`` pre-filter (its multi-apply
        # behavior without an instance name is inconsistent across USD
        # versions) and let the schema-name iteration be the only gate.
        try:
            applied_schemas = list(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        except Exception:
            applied_schemas = list(prim.GetAppliedSchemas())
        for schema_name in applied_schemas:
            if not schema_name.startswith("PhysxMimicJointAPI:"):
                continue
            instance_name = schema_name.split(":", 1)[1]
            axis_token = getattr(UsdPhysics.Tokens, instance_name, None)
            if axis_token is None:
                # Unknown instance name (forward-compat with future axes);
                # skip rather than crash so the rest of the suite still runs.
                continue

            mimic = PhysxSchema.PhysxMimicJointAPI(prim, axis_token)
            ref_path = _read_reference_target(mimic)
            if not ref_path:
                continue
            gear = _read_gear(mimic)
            offset = _read_offset(mimic)

            follower_name = prim.GetName()
            ref_name = ref_path.rsplit("/", 1)[-1]
            follower_dof_index = _find_dof_index(dof_names, follower_name)
            reference_dof_index = _find_dof_index(dof_names, ref_name)

            results.append(
                MimicJointSpec(
                    follower_joint_path=str(prim.GetPath()),
                    reference_joint_path=str(ref_path),
                    gear=float(gear),
                    offset=float(offset),
                    follower_dof_index=follower_dof_index,
                    reference_dof_index=reference_dof_index,
                )
            )
    return results


def _read_reference_target(mimic):
    # type: (Any) -> Optional[str]
    try:
        rel = mimic.GetReferenceJointRel()
        if rel is None or not rel.IsValid():
            return None
        targets = rel.GetTargets()
        if not targets:
            return None
        return str(targets[0])
    except Exception:
        return None


def _read_gear(mimic):
    # type: (Any) -> float
    try:
        attr = mimic.GetGearingAttr()
        val = attr.Get()
        if val is None:
            return 1.0
        return float(val)
    except Exception:
        return 1.0


def _read_offset(mimic):
    # type: (Any) -> float
    try:
        attr = mimic.GetOffsetAttr()
        val = attr.Get()
        if val is None:
            return 0.0
        return float(val)
    except Exception:
        return 0.0


def _find_dof_index(dof_names, joint_name):
    # type: (List[str], str) -> Optional[int]
    try:
        return dof_names.index(joint_name)
    except ValueError:
        return None
