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


def _resolves_to_rigid_body(stage, target):
    # type: (Any, Any) -> bool
    """True if ``target`` or any ancestor carries UsdPhysics.RigidBodyAPI.

    A joint body relationship often targets a collider mesh child rather than the
    rigid-body prim, so resolving up the hierarchy is what tells a real dynamic
    body from a static frame.
    """
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(target)
    while prim and prim.IsValid() and prim != stage.GetPseudoRoot():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            return True
        prim = prim.GetParent()
    return False


def check_world_anchor(ctx):
    # type: (Any) -> bool
    """Check if the asset is anchored to a static frame via a FixedJoint.

    An asset cannot fall or slide when a FixedJoint ties a rigid body to the
    world: either an empty joint side, or a static frame that has no RigidBodyAPI
    anywhere up its hierarchy. The static frame may live INSIDE the asset -- a
    fixed-base robot anchors its base_link to its own non-dynamic root Xform, so
    a same-prefix path is not a reliable "not world" signal. Instead, a joint
    anchors the asset when exactly one of its two sides resolves to a rigid body
    (the other being that static/world frame).

    Matches with ``IsA(UsdPhysics.FixedJoint)`` so a renamed or typeless
    fixed-joint prim is not missed. Returns True if anchored (the drop/slide test
    is not applicable and should skip).
    """
    try:
        import omni.usd
        from pxr import UsdPhysics

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return False
        if ctx.scene.asset is None:
            return False

        for prim in stage.Traverse():
            if not prim.IsA(UsdPhysics.FixedJoint):
                continue
            body0_rel = prim.GetRelationship("physics:body0")
            body1_rel = prim.GetRelationship("physics:body1")
            body0_targets = list(body0_rel.GetTargets()) if body0_rel.IsValid() else []
            body1_targets = list(body1_rel.GetTargets()) if body1_rel.IsValid() else []

            side0_rigid = any(_resolves_to_rigid_body(stage, t) for t in body0_targets)
            side1_rigid = any(_resolves_to_rigid_body(stage, t) for t in body1_targets)

            # Anchored when one side is a rigid body and the other is the world:
            # an empty side, or a static frame with no rigid body up its chain.
            if side0_rigid != side1_rigid:
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
