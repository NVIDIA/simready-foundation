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
"""Bbox snapshot + explode canary + articulation root helper.

Ported from v1 test_infra/bbox.py and shared_phases/shared_utils.check_bbox_explode.
"""
from dataclasses import dataclass
from typing import Tuple


def detect_loop_joints(stage, robot_root_path, dof_names):
    # type: (Any, str, List[str]) -> Tuple[Set[int], List[str]]
    """Detect articulation joints constrained by a sanctioned closed loop that
    are NOT independently position-commandable, and return (dof_indices, names).

    Spec basis -- DJ.011 ("no articulation loops"): PhysX articulations are
    trees, but a physical loop (e.g. a 4-bar / parallelogram counterbalance on a
    heavy industrial arm such as the FANUC M-2000) is explicitly permitted when
    ONE joint in the loop sets ``physics:excludeFromArticulation = true``. That
    joint is simulated as a maximal-coordinate constraint OUTSIDE the
    articulation tree, keeping the articulation graph acyclic. The remaining
    joints on the loop stay in the articulation but are kinematically
    constrained by that maximal constraint, so per-joint motion tests
    (FRS / STA / MJC / VEL / EFF / DGV) and the Jacobian IK solver cannot drive
    them to independent targets. They are excluded the same way passive and
    mimic-follower joints are.

    Detection is grounded in the authoritative ``excludeFromArticulation``
    signal rather than topology guessing:
      * Each excluded joint marks a sanctioned loop closure.
      * The loop is that joint plus the articulation-tree path between its two
        bodies (built from the joints that remain IN the articulation).
      * A loop joint is excluded when at least one endpoint body is "loop-only"
        -- every movable joint on that body lies on the loop -- i.e. it is a
        parallel-branch link, not a main-chain link that continues out to the
        rest of the robot. This keeps genuine main-chain joints drivable (e.g.
        the M-2000 elbow J3) while excluding the parallel bar (P2 / P2_01).

    A topological loop with NO ``excludeFromArticulation`` joint is a DJ.011
    VIOLATION; this function does not mask it (it returns nothing for that loop)
    so the joints fail naturally and the spec-side validator flags the asset.

    Returns an empty set for normal open-chain robots (no loops).
    """
    out_idx = set()  # type: Set[int]
    try:
        from pxr import Usd, UsdPhysics
    except Exception:
        return out_idx, []
    root = stage.GetPrimAtPath(robot_root_path) if stage is not None else None
    if not root or not root.IsValid():
        return out_idx, []

    # The ArticulationRootAPI can sit on a prim whose subtree holds no joints --
    # on these FANUC arms it is applied to the fixed `root_joint`, a leaf, while
    # the movable joints live as siblings under the parent robot Xform. Walk up
    # to the nearest ancestor whose subtree actually contains movable joints so
    # the loop search sees the whole kinematic graph rather than an empty branch.
    def _collect_movable(scan_root):
        found = []  # type: List[Tuple[str, str, str, bool]]
        for prim in Usd.PrimRange(scan_root):
            if not prim.IsA(UsdPhysics.Joint) or prim.IsA(UsdPhysics.FixedJoint):
                continue
            b0 = prim.GetRelationship("physics:body0").GetTargets()
            b1 = prim.GetRelationship("physics:body1").GetTargets()
            if not b0 or not b1:
                continue
            attr = prim.GetAttribute("physics:excludeFromArticulation")
            excluded = bool(attr.Get()) if attr and attr.HasAuthoredValue() else False
            found.append((prim.GetName(), str(b0[0]), str(b1[0]), excluded))
        return found

    # 1. Collect movable joints as (name, body0, body1, excluded), climbing if
    #    needed. The exclude flag is the authoritative loop-closure marker.
    jl = []  # type: List[Tuple[str, str, str, bool]]
    scan = root
    while scan and scan.IsValid():
        jl = _collect_movable(scan)
        if jl:
            break
        scan = scan.GetParent()
    if not jl:
        return out_idx, []

    # 2. Build the articulation adjacency from joints that remain IN the
    #    articulation (excluded joints become maximal constraints, not edges).
    #    body_joints spans ALL movable joints so "loop-only" sees the full
    #    connectivity of a body, including the excluded closure.
    art_adj = {}  # type: dict  # body -> [(other_body, joint_name)]
    body_joints = {}  # type: dict  # body -> set(joint_name)
    name_to_bodies = {}  # type: dict
    excluded_joints = []  # type: List[Tuple[str, str, str]]
    for n, b0, b1, excluded in jl:
        name_to_bodies[n] = (b0, b1)
        body_joints.setdefault(b0, set()).add(n)
        body_joints.setdefault(b1, set()).add(n)
        if excluded:
            excluded_joints.append((n, b0, b1))
        else:
            art_adj.setdefault(b0, []).append((b1, n))
            art_adj.setdefault(b1, []).append((b0, n))
    if not excluded_joints:
        # No sanctioned loop closure. Either an open chain, or a topological
        # loop that violates DJ.011 -- which we deliberately do not mask.
        return out_idx, []

    # 3. Each excluded joint closes a loop with the articulation-tree path
    #    between its two bodies. Collect all loop joints.
    def tree_path_joints(a, b):
        from collections import deque

        prev = {a: (None, None)}
        dq = deque([a])
        while dq:
            cur = dq.popleft()
            if cur == b:
                break
            for nb, jn in art_adj.get(cur, []):
                if nb not in prev:
                    prev[nb] = (cur, jn)
                    dq.append(nb)
        if b not in prev:
            return []
        names, cur = [], b
        while prev[cur][0] is not None:
            names.append(prev[cur][1])
            cur = prev[cur][0]
        return names

    cycle_joints = set()  # type: Set[str]
    for n, b0, b1 in excluded_joints:
        path = tree_path_joints(b0, b1)
        if not path:
            continue  # excluded joint does not close a loop inside the articulation
        cycle_joints.add(n)
        cycle_joints.update(path)
    if not cycle_joints:
        return out_idx, []

    # 4. A loop joint is excluded when at least one endpoint body is loop-only
    #    (every movable joint on it lies on the loop) -- a parallel-branch link,
    #    not a main-chain link that continues out to the rest of the robot.
    def loop_only(body):
        js = body_joints.get(body, set())
        return bool(js) and all(j in cycle_joints for j in js)

    exclude_names = set()  # type: Set[str]
    for n in cycle_joints:
        b0, b1 = name_to_bodies[n]
        if loop_only(b0) or loop_only(b1):
            exclude_names.add(n)

    # 5. Map joint prim names -> DOF indices (the excluded closure joint is a
    #    maximal constraint and is normally absent from dof_names).
    name_to_dof = {str(dn): i for i, dn in enumerate(dof_names)}
    out_names = []  # type: List[str]
    for n in exclude_names:
        if n in name_to_dof:
            out_idx.add(int(name_to_dof[n]))
            out_names.append(n)
    return out_idx, sorted(out_names)


@dataclass
class BBoxSnapshot:
    """World-aligned axis-aligned bounding box snapshot."""

    min_point: Tuple[float, float, float]
    max_point: Tuple[float, float, float]

    @property
    def volume(self):
        # type: () -> float
        dx = self.max_point[0] - self.min_point[0]
        dy = self.max_point[1] - self.min_point[1]
        dz = self.max_point[2] - self.min_point[2]
        return max(0.0, dx) * max(0.0, dy) * max(0.0, dz)


def compute_world_aligned_bbox(prim):
    # type: (Any) -> BBoxSnapshot
    """Compute the world-aligned AABB of a USD prim. Lazy imports pxr."""
    from pxr import Usd, UsdGeom

    if prim is None or not prim.IsValid():
        return BBoxSnapshot((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    bbox = bbox_cache.ComputeWorldBound(prim)
    aligned = bbox.ComputeAlignedBox()
    mn = aligned.GetMin()
    mx = aligned.GetMax()
    return BBoxSnapshot(
        min_point=(float(mn[0]), float(mn[1]), float(mn[2])),
        max_point=(float(mx[0]), float(mx[1]), float(mx[2])),
    )


def check_bbox_explode(current, baseline, ratio):
    # type: (BBoxSnapshot, BBoxSnapshot, float) -> Optional[str]
    """Return an error message when current volume exceeds baseline * ratio.

    Returns None when within bounds or when baseline volume is zero/degenerate.
    """
    if baseline is None or current is None:
        return None
    base_vol = baseline.volume
    cur_vol = current.volume
    if base_vol <= 1e-9:
        return None
    if cur_vol > base_vol * float(ratio):
        return "bbox explode detected: current volume %.3f > baseline %.3f * ratio %.1f" % (cur_vol, base_vol, ratio)
    return None


def get_articulation_root_path(stage, asset_prim):
    # type: (Any, Any) -> Optional[str]
    """Return the USD path of the articulation root under asset_prim, or None.

    The Isaac helper ``get_articulation_root_api_prim_path`` can return a
    non-empty path even when the asset has no ``PhysicsArticulationRootAPI``
    anywhere (observed on food assets with physics-ready variants where the
    helper falls back to ``asset_prim`` itself). Trusting that path and
    feeding it into ``SingleArticulation`` / ``World.reset_async()`` makes
    PhysX fail to find any articulation under it and the test then
    crashes later with a confusing ``'NoneType' has no attribute
    'is_homogeneous'`` from a downstream transform read.

    Both the Isaac-helper result AND the traversal fallback are now
    verified: we only return a path whose prim actually carries
    ``UsdPhysics.ArticulationRootAPI``. When neither path finds one we
    return None, which ``setup_robot_test_scene`` turns into a clean
    ``precheck_failure`` -> skip for assets that aren't robots.
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return None
    try:
        from pxr import UsdPhysics
    except Exception:
        return None

    def _is_valid_articulation_root(path_str):
        if not path_str:
            return False
        prim = stage.GetPrimAtPath(str(path_str))
        if not prim or not prim.IsValid():
            return False
        return prim.HasAPI(UsdPhysics.ArticulationRootAPI)

    try:
        from isaacsim.core.utils.prims import get_articulation_root_api_prim_path

        path = get_articulation_root_api_prim_path(str(asset_prim.GetPath()))
        if _is_valid_articulation_root(path):
            return str(path)
    except Exception:
        pass

    try:
        from pxr import Usd

        for prim in Usd.PrimRange(asset_prim):
            if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                return str(prim.GetPath())
    except Exception:
        pass
    return None


def safe_len(obj):
    # type: (Any) -> int
    """Length of obj, or 0 when obj is None or not sized."""
    if obj is None:
        return 0
    try:
        return len(obj)
    except Exception:
        return 0
