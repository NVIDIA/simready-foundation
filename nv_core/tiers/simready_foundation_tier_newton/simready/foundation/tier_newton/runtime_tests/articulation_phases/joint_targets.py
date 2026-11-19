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

import math

_FLOAT32_LIMIT_SENTINEL = float.fromhex("0x1.fffffep+127")


def unbounded_joint_limits(lower, upper):
    """Recognize signed infinity or the narrowly rounded SDK float32 sentinel."""
    return (
        lower == -math.inf or math.isclose(lower, -_FLOAT32_LIMIT_SENTINEL, rel_tol=1e-6, abs_tol=0.0),
        upper == math.inf or math.isclose(upper, _FLOAT32_LIMIT_SENTINEL, rel_tol=1e-6, abs_tol=0.0),
    )


def joint_is_angular(scene_info, name):
    """Require an unambiguous selected physical revolute joint."""
    from pxr import UsdPhysics
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_identity import (
        joint_for_native_name,
        selected_joint_prims,
    )

    root = scene_info.get("robot_root_prim") or scene_info.get("asset_prim")
    if root is None or not root.IsValid():
        return False
    joints = selected_joint_prims(root.GetStage(), str(root.GetPath()), [name], scene_info.get("asset_prim"))
    joint = joint_for_native_name(joints, name)
    return bool(joint and joint.IsA(UsdPhysics.RevoluteJoint))


def bounded_joint_range(lower, upper, center, angular=False):
    """Keep finite stops; use local +/- pi only for positively angular DOFs.

    Correctly signed infinite/SDK-extreme limits are unbounded. Unknown and
    prismatic unbounded coordinates have no inferred excursion. NaN, reversed,
    locked, or nonfinite-center ranges cannot authorize a target.
    """
    lo, hi, anchor = float(lower), float(upper), float(center)
    if not math.isfinite(anchor) or math.isnan(lo) or math.isnan(hi) or lo >= hi:
        return None
    lo_unbounded, hi_unbounded = unbounded_joint_limits(lo, hi)
    if not lo_unbounded and not math.isfinite(lo):
        return None
    if not hi_unbounded and not math.isfinite(hi):
        return None
    if not lo_unbounded and not hi_unbounded:
        return (lo, hi) if math.isfinite(hi - lo) else None
    if not angular:
        return None
    if not lo_unbounded:
        anchor = max(anchor, lo)
    if not hi_unbounded:
        anchor = min(anchor, hi)
    lo = anchor - math.pi if lo_unbounded else max(lo, anchor - math.pi)
    hi = anchor + math.pi if hi_unbounded else min(hi, anchor + math.pi)
    return (lo, hi) if math.isfinite(lo) and math.isfinite(hi) and hi > lo else None
