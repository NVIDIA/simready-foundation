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
"""Shared pre-simulation safeguards for FET003 physics tests.

These checks run before any physics simulation to catch common issues
that would cause false failures or hangs.
"""


def check_world_anchor(ctx):
    # type: (Any) -> bool
    """Check if the asset is world-anchored via FixedJoint.

    Returns True if anchored (the drop test is not applicable and should skip).
    Matches the joint with ``IsA(UsdPhysics.FixedJoint)`` so a renamed or
    typeless fixed-joint prim is not missed; a literal GetTypeName string
    compare would skip those.
    """
    try:
        import omni.usd
        from pxr import UsdPhysics

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return False

        asset_root = ctx.scene.asset
        if asset_root is None:
            return False
        asset_path = asset_root.prim_path

        for prim in stage.Traverse():
            if prim.IsA(UsdPhysics.FixedJoint):
                body0_rel = prim.GetRelationship("physics:body0")
                body1_rel = prim.GetRelationship("physics:body1")
                body0_targets = body0_rel.GetTargets() if body0_rel.IsValid() else []
                body1_targets = body1_rel.GetTargets() if body1_rel.IsValid() else []
                all_targets = list(body0_targets) + list(body1_targets)

                has_asset = False
                has_world = False
                for target in all_targets:
                    target_str = str(target)
                    if target_str.startswith(asset_path):
                        has_asset = True
                    else:
                        has_world = True

                if has_asset and has_world:
                    return True
                if has_asset and (not body0_targets or not body1_targets):
                    return True
    except Exception:
        pass
    return False


def check_has_rigid_body(ctx):
    # type: (Any) -> bool
    """Check if the asset has at least one prim with RigidBodyAPI.

    Returns True if rigid body found (test can proceed).
    """
    try:
        import omni.usd
        from pxr import Usd, UsdPhysics

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return False

        asset_root = ctx.scene.asset
        if asset_root is None:
            return False

        root_prim = stage.GetPrimAtPath(asset_root.prim_path)
        if not root_prim.IsValid():
            return False

        for prim in Usd.PrimRange(root_prim):
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                return True
    except Exception:
        pass
    return False


def run_pre_checks(ctx):
    # type: (Any) -> Optional[str]
    """Run all pre-simulation safeguards.

    Returns None if all checks pass (proceed with test).
    Returns a string message if the test should stop:
      - Starts with "NA:" -> test is not applicable; skip with this reason
        (unconditional, e.g. a world-anchored asset that cannot fall)
      - Starts with "SKIP:" -> prerequisite not met; fail if the asset claims
        this feature is validated, otherwise skip
    """
    if check_world_anchor(ctx):
        return (
            "NA: Asset is world-anchored (FixedJoint to world) -- "
            "test not applicable. World-anchored assets cannot fall or slide."
        )

    if not check_has_rigid_body(ctx):
        return (
            "SKIP: Asset has no UsdPhysics.RigidBodyAPI -- not validated "
            "for physics. Apply RigidBodyAPI to the asset root prim."
        )

    # Kit-plugin guardrail: skip if the asset's collision meshes have
    # approximations PhysX cannot cook for dynamic bodies, or if the
    # asset has no collision geometry at all.  Both conditions otherwise
    # crash or hang Kit inside physics.play().
    import omni.usd
    from simready_benchmark_engine_kit.physics_utils import check_physics_ready

    stage = omni.usd.get_context().get_stage()
    asset_root = ctx.scene.asset
    if stage is not None and asset_root is not None:
        skip_msg = check_physics_ready(stage, asset_root.prim_path)
        if skip_msg is not None:
            return skip_msg

    return None
