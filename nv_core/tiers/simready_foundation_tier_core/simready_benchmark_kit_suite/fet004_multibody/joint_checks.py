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
"""Pre-simulation checks for FET004 joint movement test.

Checks whether the asset has movable (non-fixed) joints.
Unlike FET003, world-anchored assets are NOT skipped -- a pinned root
is ideal for joint testing since force goes directly into joint motion.
"""


def is_movable_joint(prim):
    # type: (Any) -> bool
    """True for any UsdPhysics joint prim that is not a FixedJoint.

    Detection mirrors the spec validators, which discover joints via
    ``prim.IsA(UsdPhysics.Joint)`` rather than a USD type-name allow-list. A
    type-name allow-list silently misses typeless prims carrying a joint API
    and any future or renamed joint subclass; ``IsA`` catches every
    UsdPhysics.Joint subclass. FixedJoint is excluded because it cannot move.
    """
    from pxr import UsdPhysics

    return bool(prim.IsA(UsdPhysics.Joint) and not prim.IsA(UsdPhysics.FixedJoint))


def run_pre_checks(ctx):
    # type: (Any) -> Optional[str]
    """Run pre-simulation checks for joint movement test.

    Returns None if checks pass (proceed with test).
    Returns a string starting with 'SKIP:' if the test should skip.
    """
    try:
        import omni.usd
        from pxr import Usd, UsdPhysics

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return "SKIP: No USD stage available"

        asset_root = ctx.scene.asset
        if asset_root is None:
            return "SKIP: No asset loaded"
        root_prim = stage.GetPrimAtPath(asset_root.prim_path)
        if not root_prim.IsValid():
            return "SKIP: Asset root prim is invalid"

        has_any_joint = False
        has_movable_joint = False
        for prim in Usd.PrimRange(root_prim):
            if not prim.IsA(UsdPhysics.Joint):
                continue
            has_any_joint = True
            if not prim.IsA(UsdPhysics.FixedJoint):
                has_movable_joint = True
                break  # one movable joint is enough

        if not has_any_joint:
            return "SKIP: No joints found -- joint movement test not applicable"
        if not has_movable_joint:
            return "SKIP: All joints are FixedJoint -- no movable joints"

        # Kit-plugin guardrail: assets whose collision meshes use a
        # dynamic-body approximation PhysX cannot cook would crash Kit
        # during physics.play().  Skip cleanly instead. Note: joint
        # motion does NOT require any colliders at all -- an articulation
        # can be driven without contact geometry -- so we intentionally
        # do not call check_has_colliders() here.
        from simready_benchmark_engine_kit.physics_utils import check_physics_cookable

        skip_msg = check_physics_cookable(stage, asset_root.prim_path)
        if skip_msg is not None:
            return skip_msg

    except Exception:
        pass

    return None
