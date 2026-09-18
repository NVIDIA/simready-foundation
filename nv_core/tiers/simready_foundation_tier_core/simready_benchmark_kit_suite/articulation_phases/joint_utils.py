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
    def _collect_joints(scan_root):
        found = []  # type: List[Tuple[str, str, str, bool, bool]]
        for prim in Usd.PrimRange(scan_root):
            if not prim.IsA(UsdPhysics.Joint):
                continue
            b0 = prim.GetRelationship("physics:body0").GetTargets()
            b1 = prim.GetRelationship("physics:body1").GetTargets()
            if not b0 or not b1:
                continue
            attr = prim.GetAttribute("physics:excludeFromArticulation")
            excluded = bool(attr.Get()) if attr and attr.HasAuthoredValue() else False
            found.append(
                (
                    prim.GetName(),
                    str(b0[0]),
                    str(b1[0]),
                    excluded,
                    not prim.IsA(UsdPhysics.FixedJoint),
                )
            )
        return found

    # 1. Collect movable joints as (name, body0, body1, excluded), climbing if
    #    needed. The exclude flag is the authoritative loop-closure marker.
    jl = []  # type: List[Tuple[str, str, str, bool, bool]]
    scan = root
    while scan and scan.IsValid():
        jl = _collect_joints(scan)
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
    for n, b0, b1, excluded, movable in jl:
        name_to_bodies[n] = (b0, b1)
        if movable:
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
    #
    #    Preserve an explicitly controlled loop driver. Four-bar grippers are
    #    themselves a closed linkage: one joint is deliberately actuated while
    #    the other joints are passive/mimic followers and a maximal-coordinate
    #    closure completes the mechanism. Treating every joint in that loop as
    #    non-commandable removes the only valid FET022 target.
    def loop_only(body):
        js = body_joints.get(body, set())
        return bool(js) and all(j in cycle_joints for j in js)

    exclude_names = set()  # type: Set[str]
    for n in cycle_joints:
        b0, b1 = name_to_bodies[n]
        if loop_only(b0) or loop_only(b1):
            exclude_names.add(n)

    try:
        from simready_benchmark_kit_suite.articulation_phases.passive_joints import (
            _actuator_target_paths,
            _joint_is_passive,
        )

        actuator_targets = _actuator_target_paths(stage, str(scan.GetPath()))
        prims_by_name = {
            prim.GetName(): prim
            for prim in Usd.PrimRange(scan)
            if prim.IsA(UsdPhysics.Joint) and not prim.IsA(UsdPhysics.FixedJoint)
        }
        exclude_names = {
            name
            for name in exclude_names
            if name not in prims_by_name or _joint_is_passive(prims_by_name[name], actuator_targets)
        }
    except Exception:
        # Retain the conservative topology-only result if drive inspection is
        # unavailable. The runtime tests will still fail safely rather than
        # independently commanding a constrained passive branch.
        pass

    # 5. Map joint prim names -> DOF indices. Multi-axis joints can appear in
    #    Isaac's legacy wrapper as ``joint_name:0``, ``joint_name:1``, etc.
    #    Newton omits an excluded closure from its native articulation, but the
    #    legacy view may still expose all three authored spherical axes. Treat
    #    every such axis as belonging to the same sanctioned loop joint.
    name_to_dofs = {}  # type: dict
    for i, dof_name in enumerate(dof_names):
        text = str(dof_name)
        prim_name = text.rsplit(":", 1)[0] if text.rsplit(":", 1)[-1].isdigit() else text
        name_to_dofs.setdefault(prim_name, []).append(i)
    out_names = []  # type: List[str]
    for n in exclude_names:
        if n in name_to_dofs:
            out_idx.update(int(index) for index in name_to_dofs[n])
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
    """Compute the world-aligned AABB of a prim's renderable geometry.

    Runtime-control prims such as ``NewtonActuator`` can live below an asset
    root without being imageable geometry.  Asking ``BBoxCache`` to traverse
    the whole root makes some Kit/OpenUSD schema combinations try to query a
    nonexistent ``visibility`` attribute on those control prims.  Restricting
    the query to ``UsdGeomBoundable`` descendants is both semantically correct
    for this visual explosion canary and robust to provider-specific runtime
    schemas.
    """
    from pxr import Usd, UsdGeom

    if prim is None or not prim.IsValid():
        return BBoxSnapshot((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    min_point = None
    max_point = None
    for descendant in Usd.PrimRange(prim):
        if not descendant.IsA(UsdGeom.Boundable):
            continue
        aligned = bbox_cache.ComputeWorldBound(descendant).ComputeAlignedBox()
        descendant_min = aligned.GetMin()
        descendant_max = aligned.GetMax()
        if min_point is None:
            min_point = [float(descendant_min[i]) for i in range(3)]
            max_point = [float(descendant_max[i]) for i in range(3)]
            continue
        for i in range(3):
            min_point[i] = min(min_point[i], float(descendant_min[i]))
            max_point[i] = max(max_point[i], float(descendant_max[i]))

    if min_point is None:
        return BBoxSnapshot((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    return BBoxSnapshot(
        min_point=tuple(min_point),
        max_point=tuple(max_point),
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

    Discovery is intentionally OpenUSD-only. Importing Isaac Core's prim
    helpers before Newton first compiles the stage initializes a NumPy-backed
    simulation context; Isaac Sim 6.0 then switches the GPU pipeline to Torch
    and can fail while converting a CUDA tensor to NumPy. Traversing the
    composed USD hierarchy is sufficient, deterministic, and works before any
    runtime controller exists.

    Only return a prim that actually carries
    ``UsdPhysics.ArticulationRootAPI``. When no such prim exists, return None;
    ``setup_robot_test_scene`` turns that into an actionable precheck result.
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return None
    try:
        from pxr import UsdPhysics
    except Exception:
        return None

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
