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
"""JIK phase: Jacobian-based Inverse Kinematics for any articulated robot.
V1 references:
  - shared_phases/jacobian_ik.py (orchestration, target generation,
    success-rate gating).
  - shared_phases/jik_execution.py (precompute, motion interpolation,
    teleport, hold).

This module merges both v1 files into one Framework 2.0 phase with the
simplified contract ``async def run_jacobian_ik(ctx, robot, scene_info,
config) -> None``. The viewport legend authoring (target spheres, on-
screen text), v1's split-OOR / inverted-mount workspace heuristics, and
the cascading-failure / dgv-aware error messages are intentionally
dropped (spec scope cuts).

The damped least-squares solver itself is shared with the IK phase and
lives in ``jik_solver.py``. v2's solver is sync; the phase below is
responsible for stepping physics around solve calls so USD xform caches
reflect current articulation state.
"""

import math

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.ee_discovery import (
    discover_end_effector_link,
)
from simready_benchmark_kit_suite.articulation_phases.error_utils import (
    asset_fix,
    engine_note,
)
from simready_benchmark_kit_suite.articulation_phases.ik_targets import (
    COLOR_TARGET_MOTION_FAILED,
    COLOR_TARGET_OOR_FALSE_POSITIVE,
    COLOR_TARGET_OUT_OF_REACH_OK,
    COLOR_TARGET_REACHED,
    COLOR_TARGET_SOLVE_FAILED,
    IKTarget,
    cleanup_target_spheres,
    create_target_spheres_from_targets,
    set_target_sphere_color,
)
from simready_benchmark_kit_suite.articulation_phases.jik_solver import (
    JacobianIKSolver,
)
from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
)

# ---------------------------------------------------------------------------
# Fix-message helpers (asset-author guidance)
#
# Library philosophy: when JIK cannot run on -- or fails on -- an asset, the
# message in result.json / HTML report is the ONLY signal the asset author
# gets back from CI. Each message below names the failure, prints what the
# test found vs. expected, points at the prim(s) that need editing, gives a
# paste-ready USDA snippet (or concrete edit instruction with example
# values), and ends with a REFERENCE block pointing to the spec docs and a
# working real-asset example.
# ---------------------------------------------------------------------------


_SPEC_REFERENCE_ARTICULATION = (
    "REFERENCE:\n"
    "  Spec:      nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_joints/requirements/articulation.md\n"
    "             nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_joints/requirements/joint-body-target-exists.md\n"
    "             nv_core/sr_specs/docs/capabilities/hierarchy/"
    "requirements/kinematic-chain-hierarchy.md\n"
    "  Example:   sample_content/common_assets/robots_general/"
    "Franka/Franka.usda\n"
    "             (search for: PhysicsArticulationRootAPI, "
    "PhysicsRevoluteJoint)"
)


def _fix_message_no_end_effector(search_root, robot_prim_path):
    # type: (str, str) -> str
    """Asset has no discoverable end-effector link in its kinematic chain."""
    return (
        "JIK: end-effector link could not be discovered on this asset.\n"
        "\n"
        "What the test found: could not identify a tip link from any spec-\n"
        "defined source under\n"
        "    {root}\n"
        "The discovery used SPEC sources only, in order:\n"
        "  1) the `isaac:physics:robotLinks` relationship (Isaac Robot schema,\n"
        "     ordered base -> tip, last entry = EE), searched on the robot /\n"
        "     default prim and its ancestors, and\n"
        "  2) the kinematic-chain tip from the articulation body order (last\n"
        "     non-gripper link), preferring a fixed tool-frame child\n"
        "     (flange / tool0 / tcp / ee_link) when present.\n"
        "Both returned None. The asset does not declare its end-effector in a\n"
        "way the tools can resolve unambiguously -- the tool frame is not\n"
        "discoverable from the robot schema or the articulation chain under the\n"
        "articulation root prim ({robot_root}). The discovery intentionally does\n"
        "NOT guess a link by name, so this needs an authoring fix.\n"
        "\n"
        "FIX (pick the option that matches your asset):\n"
        "\n"
        "  A) ADD a fixed tool-frame child to your last (tip) link, named one\n"
        "     of `tool0`, `ee_link`, `tcp`, or `flange`. Discovery returns this\n"
        "     fixed child as the tool output face. Easiest fix when the chain\n"
        "     hierarchy is already correct but the tip link has no explicit\n"
        "     tool frame. Author it at the tool-control-point offset/orientation:\n"
        "\n"
        '         over "<last_link>"\n'
        "         {{\n"
        '             def Xform "tool0"\n'
        "             {{\n"
        "                 # Fixed offset/orientation of the tool output face\n"
        "                 # relative to the last link.\n"
        "                 double3 xformOp:translate = (0, 0, 0)\n"
        '                 uniform token[] xformOpOrder = ["xformOp:translate"]\n'
        "             }}\n"
        "         }}\n"
        "\n"
        "  B) AUTHOR an `isaac:physics:robotLinks` relationship on the\n"
        "     articulation root listing the chain from base to tip. This\n"
        "     wins over name matching and works even when the tip link has\n"
        "     an asset-specific name.\n"
        "\n"
        '         over "{robot_root}" (\n'
        '             prepend apiSchemas = ["PhysicsArticulationRootAPI"]\n'
        "         )\n"
        "         {{\n"
        "             rel isaac:physics:robotLinks = [\n"
        "                 </path/to/base_link>,\n"
        "                 </path/to/link_1>,\n"
        "                 </path/to/link_2>,\n"
        "                 </path/to/link_3>,\n"
        "                 </path/to/wrist_link>,\n"
        "                 </path/to/tip_link>,   # EE -- must be last\n"
        "             ]\n"
        "         }}\n"
        "\n"
        "  C) FIX the kinematic-chain hierarchy. If the link prims live in\n"
        "     a sibling scope rather than nested under the articulation\n"
        "     root, the EE-discovery walk under {root} finds nothing.\n"
        "     Restructure so each link is an Xform descendant of the base,\n"
        "     parented along the kinematic chain (base -> shoulder -> ...\n"
        "     -> wrist -> tip).\n"
        "\n"
        "{ref}"
    ).format(
        root=search_root,
        robot_root=robot_prim_path,
        ref=_SPEC_REFERENCE_ARTICULATION,
    )


def _fix_message_solver_construct(exc):
    # type: (Exception) -> str
    """Solver constructor raised -- typically a missing/invalid articulation."""
    return (
        "JIK: failed to construct the Jacobian IK solver on this asset.\n"
        "\n"
        "What the test found: building `JacobianIKSolver(robot, ee_link)`\n"
        "raised %s: %s.\n"
        "Common root causes (asset-side):\n"
        "  - The articulation has zero DOFs. The asset is missing\n"
        "    `PhysicsRevoluteJoint` / `PhysicsPrismaticJoint` prims, or\n"
        "    every joint is `PhysicsFixedJoint` so PhysX sees a rigid\n"
        "    body, not an articulated chain.\n"
        "  - `PhysicsArticulationRootAPI` is not applied (or is applied\n"
        "    to the wrong prim -- it must sit on the root body for a\n"
        "    free-floating robot, or on the root fixed-joint for a\n"
        "    base-bolted arm).\n"
        "  - The end-effector link path is not part of the articulation\n"
        "    body list (a joint between EE and the rest of the chain is\n"
        "    missing, or the EE prim is parented outside the articulation).\n"
        "\n"
        "FIX:\n"
        "  1. Open the asset in Kit and inspect the articulation in the\n"
        "     Physics Inspector. DOF count must be >= 1.\n"
        "  2. Verify exactly ONE prim along the chain carries\n"
        "     `PhysicsArticulationRootAPI` (see spec JT.ART.001).\n"
        "  3. Verify every moving joint is `PhysicsRevoluteJoint` or\n"
        "     `PhysicsPrismaticJoint` -- NOT `PhysicsFixedJoint`. Example:\n"
        "\n"
        '         def PhysicsRevoluteJoint "joint_1"\n'
        "         {\n"
        "             rel physics:body0 = </Robot/base_link>\n"
        "             rel physics:body1 = </Robot/link_1>\n"
        '             uniform token physics:axis = "Z"\n'
        "             float physics:lowerLimit = -180.0\n"
        "             float physics:upperLimit =  180.0\n"
        "         }\n"
        "\n"
        "  4. Verify each joint's `physics:body0` / `physics:body1`\n"
        "     relationships resolve to existing rigid-body prims (spec\n"
        "     JT.005, joint-body-target-exists).\n"
        "\n"
        "%s"
    ) % (type(exc).__name__, exc, _SPEC_REFERENCE_ARTICULATION)


def _fix_message_no_in_reach_targets(robot_reach, asset_prim_path):
    # type: (float, str) -> str
    """Target generator produced zero in-reach targets -- reach estimate is bogus."""
    return (
        "JIK: target generator produced no in-reach targets.\n"
        "\n"
        "What the test found: the bbox-based reach estimate for this asset\n"
        "came back at %.4f m, which is too small (or otherwise degenerate)\n"
        "to spawn any reachable IK targets after the radius factors\n"
        "(default 0.5, 0.7, 0.9) are applied. The estimate is half the\n"
        "diagonal of the world-aligned AABB of\n"
        "    %s\n"
        "and falls back to 0.5 m only when the bbox itself is degenerate.\n"
        "\n"
        "Most likely causes (asset-side):\n"
        "  - Asset is authored at the wrong scale (e.g. millimetres while\n"
        "    `metersPerUnit = 1.0`). SimReady requires meters per the\n"
        "    units spec; a 1500 mm arm authored in mm would compute a\n"
        "    1.5 m diagonal at the WRONG scale and trip lower thresholds.\n"
        "  - Articulation root prim has no visible link geometry under it\n"
        "    (link meshes are siblings rather than descendants), so the\n"
        "    AABB collapses to a single link.\n"
        '  - Geometry is hidden / `purpose = "guide"` so it does not\n'
        "    contribute to the bbox computation.\n"
        "\n"
        "FIX:\n"
        "  1. Verify `metersPerUnit = 1.0` on the root layer (spec UN.001).\n"
        "  2. Verify all link meshes are under the asset prim and have\n"
        '     `purpose = "default"` (not `guide` or `proxy`).\n'
        "  3. If the asset's reach really is well below 0.5 m (a small\n"
        "     gripper or finger-rig), override the JIK config with\n"
        "     explicit values, for example:\n"
        "\n"
        "         config = {\n"
        '             "target_radius_factors": (0.4, 0.6, 0.8),\n'
        '             "out_of_reach_factor": 1.5,\n'
        "         }\n"
        "\n"
        "%s"
    ) % (float(robot_reach), asset_prim_path, _SPEC_REFERENCE_ARTICULATION)


def _fix_message_pass_rate_below_min(
    pass_rate,
    min_pass_rate,
    in_reach_passed,
    in_reach_total,
    in_reach_solver_failed,
    in_reach_motion_failed,
    max_pos_err,
    max_orient_err_deg,
    pos_tol,
    orient_tol_deg,
    failure_names,
    ee_link_path,
):
    # type: (float, float, int, int, int, int, float, float, float, float, List[str], str) -> str
    """Pass rate below minimum: solver and/or motion drives are not tracking."""
    failed_list = ", ".join(failure_names) or "(none)"
    return (
        "JIK: in-reach pass rate %.2f below minimum %.2f -- the asset's\n"
        "articulation could not reach enough generated targets to pass.\n"
        "\n"
        "What the test found:\n"
        "  - %d / %d in-reach targets passed.\n"
        "  - %d failed because the DLS solver could not find a joint\n"
        "    solution (red sphere in the captured video).\n"
        "  - %d failed because the solver succeeded but the PD drives did\n"
        "    not track the precomputed solution to within tolerance\n"
        "    (orange sphere).\n"
        "  - Worst position error: %.4f m (tolerance %.3f m).\n"
        "  - Worst orientation error: %.2f deg (tolerance %.2f deg).\n"
        "  - End-effector under test: %s.\n"
        "  - Failed targets: %s.\n"
        "\n"
        "FIX -- triage in this order:\n"
        "\n"
        "  1) Open the captured video. Targets coloured RED never had a\n"
        "     joint solution. Targets coloured ORANGE had a solution but\n"
        "     the robot did not get there -- a drive-tuning problem.\n"
        "\n"
        "  2) For ORANGE (motion failed) on a `PhysicsRevoluteJoint`,\n"
        "     inspect drive stiffness / damping on each joint. Industrial\n"
        "     arms typically need:\n"
        "\n"
        '         def PhysicsRevoluteJoint "joint_3" (\n'
        '             prepend apiSchemas = ["PhysicsDriveAPI:angular"]\n'
        "         )\n"
        "         {\n"
        "             # Example values for a 25 kg-link arm; scale with\n"
        "             # link inertia. Stiffness too low -> drift; too\n"
        "             # high -> oscillation.\n"
        "             float drive:angular:physics:stiffness = 10000.0\n"
        "             float drive:angular:physics:damping   = 1000.0\n"
        "             float drive:angular:physics:maxForce  = 1000.0\n"
        "         }\n"
        "\n"
        "  3) For RED (solver failed), the Jacobian is singular or the\n"
        "     joint limits are too tight. Verify each joint declares\n"
        "     non-zero limits:\n"
        "\n"
        "         float physics:lowerLimit = -180.0\n"
        "         float physics:upperLimit =  180.0\n"
        "\n"
        "     and that the EE link (%s) is the LAST link in the chain --\n"
        "     a tip link with no preceding revolute joint cannot be\n"
        "     reached by a Jacobian solver.\n"
        "\n"
        "  4) %s\n"
        "\n"
        "  5) %s\n"
        "\n"
        "  6) TEST-CONFIG escape hatches (use only when the asset is\n"
        "     genuinely correct but the defaults are wrong for it):\n"
        "     - Reduce `target_radius_factors` (default (0.5, 0.7, 0.9))\n"
        "       when the bbox-based reach estimate overshoots the actual\n"
        "       workspace (common on non-extended / folded arms).\n"
        "     - Loosen `position_tolerance` / `orientation_tolerance_deg`\n"
        "       (defaults 0.05 m / 10 deg) when the asset's PD drive has\n"
        "       intentional steady-state error.\n"
        "     - Increase `max_solver_iterations` (default 50) when DLS\n"
        "       convergence is slow on long-armed or heavily damped\n"
        "       robots.\n"
        "\n"
        "%s"
    ) % (
        float(pass_rate),
        float(min_pass_rate),
        int(in_reach_passed),
        int(in_reach_total),
        int(in_reach_solver_failed),
        int(in_reach_motion_failed),
        float(max_pos_err),
        float(pos_tol),
        float(max_orient_err_deg),
        float(orient_tol_deg),
        ee_link_path,
        failed_list,
        ee_link_path,
        asset_fix(
            "Tune drive stiffness/damping so each joint can hold its\n"
            "     commanded position under JIK's smoothstep motion -- start\n"
            "     by doubling stiffness on the joint(s) showing the largest\n"
            "     tracking error in the video."
        ),
        engine_note(
            "JIK uses a damped least-squares Jacobian solver with USD\n"
            "     forward kinematics; ensure the asset's joints are exposed\n"
            "     in the SingleArticulation's `dof_names`."
        ),
        _SPEC_REFERENCE_ARTICULATION,
    )


# ---------------------------------------------------------------------------
# Defaults (spec Section 4.1)
# ---------------------------------------------------------------------------


def get_defaults():
    # type: () -> Dict[str, Any]
    # Defaults tuned post-Fanuc smoke (2026-04-27):
    # - num_targets bumped back to 12 to match v1.6 coverage; PhysX teleport
    #   stability was actually fixed by zeroing velocities on every teleport
    #   (see jik_solver.compute_jacobian / solve), not by cutting target
    #   count.
    # - max_solver_iterations 50 (vs v1.6's 200) keeps wall time bounded;
    #   typical industrial-arm targets converge well under 50 with the
    #   loose 5 cm / 10 deg tolerances.
    # - capture_fps 15 (was 8 -- too low; matches FET003/FET004).
    # - interpolation_seconds 0.67 (~1.5x faster than 1.0; user request:
    #   "increase speed from 50% to 75%"). On a 1.0 s segment the PD
    #   drive struggles on long-stretch targets; 0.67 s is the
    #   "fast-but-trackable" sweet spot.
    return {
        "settle_seconds": 1.0,
        # 5 in-reach + 2 out-of-reach = 7 total. Pass = 2/5 = 40%.
        "num_targets": 5,
        "out_of_reach_count": 2,
        # Three radius shells matching v1.6 -- close (0.5*reach), mid
        # (0.7*reach), far (0.9*reach). With 5 reachable targets the
        # Fibonacci sphere points distribute 2/2/1 across the shells so
        # the captured video shows targets at varied workspace depths.
        "target_radius_factors": (0.5, 0.7, 0.9),
        "out_of_reach_factor": 1.5,
        "position_tolerance": 0.05,
        "orientation_tolerance_deg": 10.0,
        # 150 (was 50): on the old shell targets every failed solve hit the 50
        # cap without converging. FK-sampled targets are feasible, but big arms
        # (M-1000/R-2000, ~2-3 m reach) and the finite-difference Jacobian still
        # need headroom to converge from home. v1.6 used 200.
        "max_solver_iterations": 150,
        "damping_lambda": 0.05,
        "interpolation_seconds": 0.67,
        "hold_after_reach_seconds": 0.3,
        "interpolation_profile": "smoothstep",
        "physics_fps": 240.0,
        "capture_fps": 15,
        "min_pass_rate": 0.40,
        "bbox_explode_ratio": 10.0,
        "hemisphere_only": True,
        # Visual targets (ported from v1.6 target_generator viewport
        # legend). Disable via `show_target_spheres=False` if asset
        # authoring flags any conflict at /World/IK_Targets/.
        "show_target_spheres": True,
        "target_sphere_radius": 0.04,
        "target_sphere_scope": "/World/IK_Targets",
    }


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def smoothstep(t):
    # type: (float) -> float
    """Smoothstep ease at t in [0, 1]; returns 3t^2 - 2t^3."""
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def interpolate_profile(profile, t):
    # type: (str, float) -> float
    """Evaluate the named interpolation profile at t in [0, 1]."""
    name = str(profile).lower()
    if name == "smoothstep":
        return smoothstep(t)
    t = max(0.0, min(1.0, float(t)))
    if name == "smootherstep":
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    return t


def compute_pass_rate(passed, total):
    # type: (int, int) -> float
    """Return passed / total, or 0.0 when total <= 0."""
    if total <= 0:
        return 0.0
    return float(passed) / float(total)


def aggregate_jik_summary(per_target_results):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    """Roll up per-target results to phase-level metrics.

    Splits in-reach failures into two categories that match the target-
    sphere colors in the captured video:
    - solver_failed (red)  -- the IK solver could not find a joint solution.
    - motion_failed (orange/yellow) -- solver succeeded, but the PD drive
      did not track the precomputed solution to within tolerance.
    """
    in_reach_total = 0
    in_reach_passed = 0
    in_reach_solver_failed = 0
    in_reach_motion_failed = 0
    out_of_reach_total = 0
    out_of_reach_correct = 0
    out_of_reach_false_positive = 0
    max_pos_err = 0.0
    max_orient_err_deg = 0.0
    failure_names = []  # type: List[str]

    for r in per_target_results:
        pos_err = float(r.get("pos_err", 0.0) or 0.0)
        orient_err = float(r.get("orient_err_deg", 0.0) or 0.0)
        if pos_err > max_pos_err:
            max_pos_err = pos_err
        if orient_err > max_orient_err_deg:
            max_orient_err_deg = orient_err

        if r.get("is_reachable"):
            in_reach_total += 1
            if r.get("passed"):
                in_reach_passed += 1
            else:
                if r.get("solver_success"):
                    in_reach_motion_failed += 1
                else:
                    in_reach_solver_failed += 1
                failure_names.append(str(r.get("name", "target_?")))
        else:
            out_of_reach_total += 1
            # OOR target: "pass" means the solver correctly flagged it as
            # unreachable. If the solver claimed reachable it is a false
            # positive (solver bug or asset reach overestimate).
            if r.get("passed"):
                out_of_reach_correct += 1
            elif r.get("solver_success"):
                out_of_reach_false_positive += 1

    return {
        "targets_total": len(per_target_results),
        "in_reach_total": in_reach_total,
        "in_reach_passed": in_reach_passed,
        "in_reach_failed": in_reach_solver_failed + in_reach_motion_failed,
        "in_reach_solver_failed": in_reach_solver_failed,
        "in_reach_motion_failed": in_reach_motion_failed,
        "out_of_reach_total": out_of_reach_total,
        "out_of_reach_correct": out_of_reach_correct,
        "out_of_reach_false_positive": out_of_reach_false_positive,
        "max_position_error_m": float(max_pos_err),
        "max_orientation_error_deg": float(max_orient_err_deg),
        "pass_rate": compute_pass_rate(in_reach_passed, in_reach_total),
        "failure_names": failure_names,
    }


def get_robot_base_position(robot, scene_info):
    # type: (Any, Dict[str, Any]) -> np.ndarray
    """Return the robot's articulation root world position [x, y, z].

    Uses the ``robot_root_prim`` (or asset prim) recorded by the scene
    builder; falls back to origin when neither is valid. Lazy imports
    pxr so the helper stays import-clean outside Kit.
    """
    root_prim = scene_info.get("robot_root_prim") or scene_info.get("asset_prim")
    if root_prim is None:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)
    try:
        from pxr import Usd, UsdGeom

        if not root_prim.IsValid():
            return np.array([0.0, 0.0, 0.0], dtype=np.float64)
        xformable = UsdGeom.Xformable(root_prim)
        world_transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = world_transform.ExtractTranslation()
        return np.array(
            [
                float(translation[0]),
                float(translation[1]),
                float(translation[2]),
            ],
            dtype=np.float64,
        )
    except Exception:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)


def estimate_robot_reach(asset_prim):
    # type: (Any) -> float
    """Estimate robot reach from the asset prim's world-aligned bbox.

    Uses the diagonal of the AABB as a coarse upper bound on reach; this
    matches v1's bbox-based reach estimate. Returns 0.5 m as a final
    fallback when the prim is unavailable or the bbox is degenerate.
    """
    if asset_prim is None:
        return 0.5
    try:
        bbox = compute_world_aligned_bbox(asset_prim)
        dx = bbox.max_point[0] - bbox.min_point[0]
        dy = bbox.max_point[1] - bbox.min_point[1]
        dz = bbox.max_point[2] - bbox.min_point[2]
        diag = math.sqrt(max(0.0, dx) ** 2 + max(0.0, dy) ** 2 + max(0.0, dz) ** 2)
        if diag <= 1e-3:
            return 0.5
        # Reach is roughly half the diagonal (one arm extending from base).
        return float(diag * 0.5)
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------
# Solver wrapping
# ---------------------------------------------------------------------------


def _capture_home_orientation(solver):
    # type: (JacobianIKSolver) -> Optional[np.ndarray]
    """Return the home end-effector quaternion or None when unavailable."""
    try:
        _, quat = solver.get_ee_pose()
        return np.asarray(quat, dtype=np.float64)
    except Exception:
        return None


async def _solve_target(
    ctx,
    solver,
    target,
    home_orientation,
    pos_tol,
    orient_tol_rad,
    max_iterations,
):
    # type: (Any, JacobianIKSolver, IKTarget, Optional[np.ndarray], float, float, int) -> Optional[JacobianIKResult]
    """Run the DLS solver against a single target.

    The solver is async and steps physics after every tensor-view write so
    PhysX propagates the new joint state into the USD xform cache before
    the next pose read.

    Wrapped in try/except so a runtime failure on a single target (PhysX
    instability under cumulative teleports, NaN limits, etc.) does NOT
    take the whole JIK test down. The caller treats a None return as a
    solver failure for that target and continues.
    """
    # Prefer the target's own orientation (FK-sampled targets carry a provably
    # feasible EE orientation). Fall back to the home orientation, then identity.
    target_orient = getattr(target, "orientation", None)
    if target_orient is None:
        target_orient = home_orientation
    if target_orient is None:
        target_orient = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    try:
        return await solver.solve(
            target_pos=np.asarray(target.position, dtype=np.float64),
            target_orient=target_orient,
            step_fn=ctx.step_one,
            max_iterations=max_iterations,
            pos_tol=pos_tol,
            orient_tol_rad=orient_tol_rad,
            heartbeat_fn=ctx.step,
        )
    except Exception as exc:
        ctx.warn(
            "JIK: solver raised %s for target_%d -- treating as solver "
            "failure for this target and continuing." % (type(exc).__name__, getattr(target, "index", -1))
        )
        return None


# ---------------------------------------------------------------------------
# Async runner (Kit-only)
# ---------------------------------------------------------------------------


async def _settle_and_snapshot(ctx, robot, settle_seconds, physics_fps):
    # type: (Any, Any, float, float) -> np.ndarray
    """Settle physics and snapshot the home joint configuration."""
    ctx.step("JIK: initial settle %.2fs (%d frames)" % (settle_seconds, int(settle_seconds * physics_fps)))
    await ctx.physics_steps(int(settle_seconds * physics_fps))
    return robot.get_joint_positions().copy()


async def _teleport_to_joints(ctx, robot, positions, settle_frames=3):
    # type: (Any, Any, np.ndarray, int) -> None
    """Teleport joints to *positions* (zero velocities) and step a few frames."""
    robot.set_joint_positions(np.array(positions, dtype=np.float64))
    try:
        robot.set_joint_velocities(np.zeros(robot.dof_count, dtype=np.float64))
    except Exception:
        pass
    for _ in range(max(1, int(settle_frames))):
        await ctx.step_one()


def _sample_joint_configs(home_joints, lowers, uppers, locked, count, seed=20260608):
    # type: (np.ndarray, Any, Any, set, int, int) -> List[np.ndarray]
    """Deterministically sample ``count`` in-limits joint configurations.

    Locked (closed-loop) DOFs are held at their home value -- they are governed
    by the loop constraint, not sampled. Finite-limit joints are sampled within
    a 15% margin off each limit to avoid near-singular limit poses; unbounded
    joints are sampled within +/- pi of home. Deterministic via a fixed seed so
    the same robot always yields the same targets.
    """
    rng = np.random.default_rng(seed)
    n = len(home_joints)
    configs = []  # type: List[np.ndarray]
    # Bound each joint's deviation from home to SPREAD * range and stay 15% off
    # the limits. Sampling the full range produces near-extension / near-limit
    # configurations whose EE poses sit at Cartesian singularities -- the DLS
    # solver then cannot reach them from home (position diverges, orientation
    # loses a controllable axis). A mid-workspace spread keeps every target
    # well-conditioned and representative while still exercising large motions.
    SPREAD = 0.35
    for _ in range(count):
        q = np.array(home_joints, dtype=np.float64).copy()
        for i in range(n):
            if i in locked:
                continue
            lo = float(lowers[i]) if i < len(lowers) else float("-inf")
            hi = float(uppers[i]) if i < len(uppers) else float("inf")
            if math.isfinite(lo) and math.isfinite(hi) and (hi - lo) > 1e-3:
                span = hi - lo
                margin = 0.15 * span
                offset = float(rng.uniform(-SPREAD, SPREAD)) * span
                q[i] = float(np.clip(home_joints[i] + offset, lo + margin, hi - margin))
            else:
                q[i] = float(home_joints[i]) + float(rng.uniform(-1.0, 1.0)) * SPREAD * math.pi
        configs.append(q)
    return configs


async def _generate_fk_targets(
    ctx,
    robot,
    solver,
    home_joints,
    base_pos,
    lowers,
    uppers,
    locked,
    num_reachable,
    num_out_of_reach,
    settle_frames=4,
):
    # type: (Any, Any, JacobianIKSolver, np.ndarray, np.ndarray, Any, Any, set, int, int, int) -> Tuple[List[IKTarget], float]
    """Generate IK targets by forward kinematics from sampled joint configs.

    Each reachable target is the EE pose (position AND orientation) the arm
    demonstrably held at a sampled, in-limits configuration, so the goal is a
    provably feasible 6-DOF pose. This replaces position-only shell targets,
    which demanded the fixed home orientation at every sampled point and were
    geometrically infeasible for most points on a real arm (the dominant cause
    of spurious red solver failures on conformant arms).

    Out-of-reach targets are placed beyond the farthest observed EE distance
    from the base (carrying the home orientation) so the solver is expected to
    fail them -- exercising correct rejection of unreachable goals.

    Returns ``(targets, max_observed_reach)``.
    """
    targets = []  # type: List[IKTarget]
    max_dist = 0.0

    # Capture the home EE orientation for the out-of-reach targets.
    await _teleport_to_joints(ctx, robot, home_joints, settle_frames)
    home_quat = None  # type: Optional[np.ndarray]
    try:
        _, home_quat = solver.get_ee_pose()
    except Exception:
        home_quat = None

    configs = _sample_joint_configs(home_joints, lowers, uppers, set(locked), num_reachable)
    idx = 0
    for q in configs:
        await _teleport_to_joints(ctx, robot, q, settle_frames)
        try:
            pos, quat = solver.get_ee_pose()
        except Exception:
            continue
        dist = float(np.linalg.norm(np.asarray(pos, dtype=np.float64) - np.asarray(base_pos, dtype=np.float64)))
        max_dist = max(max_dist, dist)
        targets.append(
            IKTarget(
                position=np.asarray(pos, dtype=np.float64),
                is_reachable=True,
                index=idx,
                orientation=np.asarray(quat, dtype=np.float64),
            )
        )
        idx += 1
        ctx.step("JIK: FK target %d/%d sampled (EE dist %.3f)" % (idx, num_reachable, dist))

    # Restore home before anything else reads state.
    await _teleport_to_joints(ctx, robot, home_joints, settle_frames)

    # Out-of-reach targets: beyond the farthest observed reach, home orientation.
    if num_out_of_reach > 0 and max_dist > 1e-3:
        rng = np.random.default_rng(20260609)
        for _ in range(num_out_of_reach):
            v = np.asarray(rng.normal(size=3), dtype=np.float64)
            nrm = float(np.linalg.norm(v))
            if nrm < 1e-6:
                v = np.array([1.0, 0.0, 0.0], dtype=np.float64)
                nrm = 1.0
            v = v / nrm
            v[2] = abs(v[2])  # upper hemisphere
            oor = np.asarray(base_pos, dtype=np.float64) + v * max_dist * 1.4
            targets.append(
                IKTarget(
                    position=oor,
                    is_reachable=False,
                    index=idx,
                    orientation=home_quat,
                )
            )
            idx += 1

    return targets, max_dist


async def _precompute_solutions(
    ctx,
    robot,
    solver,
    targets,
    home_joints,
    home_orientation,
    pos_tol,
    orient_tol_rad,
    max_iterations,
):
    # type: (Any, Any, JacobianIKSolver, List[IKTarget], np.ndarray, Optional[np.ndarray], float, float, int) -> List[Dict[str, Any]]
    """Solve every target up front; return per-target solution records.

    Each record carries ``target``, ``solution`` (joints or None),
    ``solver_success`` (the raw solver flag), ``iterations``,
    ``pos_err``, and ``orient_err_deg`` so the motion phase can dispatch
    without running the solver again.
    """
    # Heartbeat per target -- every solve can take seconds and the
    # session-inactivity watchdog kills Kit after ~60 s of silence on
    # stdout. Emit a ctx.step before each solve so the watchdog sees
    # progress even if a single target takes a long time to converge.
    solutions = []  # type: List[Dict[str, Any]]
    current_start = home_joints.copy()
    total_iterations = 0
    for i, target in enumerate(targets):
        target_name = "target_%d" % target.index
        # Each solve starts from the previous solution; mirror v1.
        await _teleport_to_joints(ctx, robot, current_start)
        # Heartbeat for every target -- keeps the runner watchdog happy
        # even if one solve runs to max_iterations.
        ctx.step("JIK precompute %d/%d: %s reachable=%s" % (i + 1, len(targets), target_name, target.is_reachable))
        result = await _solve_target(
            ctx=ctx,
            solver=solver,
            target=target,
            home_orientation=home_orientation,
            pos_tol=pos_tol,
            orient_tol_rad=orient_tol_rad,
            max_iterations=max_iterations,
        )
        if result is None:
            # Solver raised; treat as failure but keep going.
            solutions.append(
                {
                    "target": target,
                    "solution": None,
                    "solver_success": False,
                    "iterations": 0,
                    "pos_err": float("inf"),
                    "orient_err_deg": float("inf"),
                }
            )
            continue
        total_iterations += int(result.iterations)
        solver_success = bool(result.success)
        solution_joints = None  # type: Optional[np.ndarray]
        if result.converged_joints is not None and result.converged_joints.size:
            solution_joints = result.converged_joints.copy()
        if solver_success and solution_joints is not None:
            current_start = solution_joints.copy()
        solutions.append(
            {
                "target": target,
                "solution": solution_joints,
                "solver_success": solver_success,
                "iterations": int(result.iterations),
                "pos_err": float(result.final_pos_error),
                "orient_err_deg": float(result.final_orient_error_deg),
            }
        )
    # Restore the home configuration before motion playback begins.
    await _teleport_to_joints(ctx, robot, home_joints)
    ctx.add_metric("jik_total_iterations", total_iterations)
    return solutions


async def _interpolate_to_solution(
    ctx,
    robot,
    scene_info,
    start_joints,
    target_joints,
    interp_seconds,
    physics_fps,
    capture_interval,
    capture_frames,
    capture_label,
    profile,
    baseline_bbox,
    bbox_ratio_limit,
    target_name,
    locked_indices=None,
):
    # type: (Any, Any, Dict[str, Any], np.ndarray, np.ndarray, float, float, int, List[str], str, str, Optional[BBoxSnapshot], float, str, Any) -> List[str]
    """Smoothstep-interpolate joint targets and step physics frame-by-frame.

    Returns a list of bbox-explode error strings (empty when none).
    Captures into ``capture_frames`` at ``capture_interval`` cadence.
    """
    HB_EVERY = 40
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    bbox_errors = []  # type: List[str]

    motion_frames = max(1, int(interp_seconds * physics_fps))
    delta = np.array(target_joints, dtype=np.float64) - np.array(start_joints, dtype=np.float64)
    # Locked (closed-loop) DOFs must not be PD-driven: their motion is dictated
    # by the loop constraint, and commanding them to interpolated targets fights
    # the parallelogram and throws the EE far off (the "wrong direction" miss).
    # Hold their command at the live position each frame so the drive does not
    # push them away from where the constraint places them.
    locked = set(int(i) for i in (locked_indices or set()))
    for li in locked:
        if li < len(delta):
            delta[li] = 0.0
    for frame in range(motion_frames):
        t = (frame + 1) / float(motion_frames)
        eased = interpolate_profile(profile, t)
        command = np.array(start_joints, dtype=np.float64) + delta * eased
        if locked:
            live = np.asarray(robot.get_joint_positions(), dtype=np.float64)
            for li in locked:
                if li < len(command) and li < len(live):
                    command[li] = live[li]
        robot.set_joint_position_targets(command)
        await ctx.step_one()

        if frame % 20 == 0 and baseline_bbox is not None:
            current_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
            msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
            if msg:
                bbox_errors.append("JIK: %s: %s" % (target_name, msg))

        if frame % capture_interval == 0:
            fp = await ctx.capture_frame(
                label="%s_%04d" % (capture_label, frame),
                stabilize_frames=0,
            )
            if fp:
                capture_frames.append(fp)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)

        if frame % HB_EVERY == 0:
            ctx.step("JIK %s frame=%d/%d eased=%.3f" % (target_name, frame, motion_frames, eased))
    return bbox_errors


async def _hold_after_reach(
    ctx,
    robot,
    final_joints,
    hold_seconds,
    physics_fps,
    capture_interval,
    capture_frames,
    capture_label,
    locked_indices=None,
):
    # type: (Any, Any, np.ndarray, float, float, int, List[str], str, Any) -> None
    """Hold at the reached pose to stabilize captured frames."""
    HB_EVERY = 40
    hold_frames = max(1, int(hold_seconds * physics_fps))
    locked = set(int(i) for i in (locked_indices or set()))
    base_cmd = None
    if final_joints is not None:
        base_cmd = np.array(final_joints, dtype=np.float64)
        robot.set_joint_position_targets(base_cmd)
    for frame in range(hold_frames):
        # Keep locked (closed-loop) DOFs commanded to their live value so the
        # PD drive does not fight the loop constraint while holding.
        if base_cmd is not None and locked:
            live = np.asarray(robot.get_joint_positions(), dtype=np.float64)
            for li in locked:
                if li < len(base_cmd) and li < len(live):
                    base_cmd[li] = live[li]
            robot.set_joint_position_targets(base_cmd)
        await ctx.step_one()
        if frame % capture_interval == 0:
            fp = await ctx.capture_frame(
                label="%s_hold_%04d" % (capture_label, frame),
                stabilize_frames=0,
            )
            if fp:
                capture_frames.append(fp)
            ctx.scene.update_camera_follow(update_history=True)
        else:
            ctx.scene.update_camera_follow(update_history=False)
        if frame % HB_EVERY == 0:
            ctx.step("JIK hold %s frame=%d/%d" % (capture_label, frame, hold_frames))


def _evaluate_target(solver, target, pos_tol, orient_tol_deg):
    # type: (JacobianIKSolver, IKTarget, float, float) -> Tuple[float, float]
    """Read the EE pose and compute (pos_err_m, orient_err_deg) vs the target.

    Returns ``(inf, inf)`` when the EE pose cannot be read.
    """
    try:
        ee_pos, _ = solver.get_ee_pose()
    except Exception:
        return float("inf"), float("inf")
    pos_err = float(np.linalg.norm(np.asarray(ee_pos, dtype=np.float64) - target.position))
    # Orientation error tracking is optional in v2; the solver records
    # orient_err_deg in JacobianIKResult. The motion-phase value is
    # informational only -- the gate uses solver-recorded errors.
    return pos_err, 0.0


async def _run_motion_for_solutions(
    ctx,
    robot,
    solver,
    scene_info,
    solutions,
    home_joints,
    cfg,
    capture_frames,
    capture_interval,
    baseline_bbox,
    target_sphere_prims=None,
    locked_indices=None,
):
    # type: (Any, Any, JacobianIKSolver, Dict[str, Any], List[Dict[str, Any]], np.ndarray, Dict[str, Any], List[str], int, Optional[BBoxSnapshot], Optional[List[Any]]) -> List[Dict[str, Any]]
    """Drive motion to each precomputed solution; return per-target results.

    Per-target sphere color reflects the final outcome:
    - Green: in-reach target, robot reached it within tolerance.
    - Red: solver failed (no joint solution found).
    - Orange: solver succeeded but motion did not converge to within tolerance.
    - Magenta: out-of-reach target, solver correctly failed.
    """
    pos_tol = float(cfg["position_tolerance"])
    orient_tol_deg = float(cfg["orientation_tolerance_deg"])
    interp_seconds = float(cfg["interpolation_seconds"])
    hold_seconds = float(cfg["hold_after_reach_seconds"])
    physics_fps = float(cfg["physics_fps"])
    profile = str(cfg["interpolation_profile"])
    bbox_ratio_limit = float(cfg["bbox_explode_ratio"])

    per_target_results = []  # type: List[Dict[str, Any]]
    for solution in solutions:
        target = solution["target"]
        target_name = "target_%d" % target.index
        ctx.step("JIK motion for %s reachable=%s" % (target_name, target.is_reachable))

        # Each segment starts FROM the previous target's final pose (NOT
        # home). v1.6 chains the motion target-to-target so the robot
        # sweeps through the target field instead of darting back to
        # home between every reach. This also halves the cumulative
        # motion distance and keeps the captured video continuous.

        solver_success = bool(solution["solver_success"])
        solver_pos_err = float(solution["pos_err"])
        solver_orient_err_deg = float(solution["orient_err_deg"])
        target_joints = solution["solution"]
        bbox_errors = []  # type: List[str]
        actual_pos_err = float("inf")

        if target_joints is not None and solver_success:
            start_joints = robot.get_joint_positions().copy()
            bbox_errors = await _interpolate_to_solution(
                ctx=ctx,
                robot=robot,
                scene_info=scene_info,
                start_joints=start_joints,
                target_joints=target_joints,
                interp_seconds=interp_seconds,
                physics_fps=physics_fps,
                capture_interval=capture_interval,
                capture_frames=capture_frames,
                capture_label="jacobian_ik_%s" % target_name,
                profile=profile,
                baseline_bbox=baseline_bbox,
                bbox_ratio_limit=bbox_ratio_limit,
                target_name=target_name,
                locked_indices=locked_indices,
            )
            await _hold_after_reach(
                ctx=ctx,
                robot=robot,
                final_joints=target_joints,
                hold_seconds=hold_seconds,
                physics_fps=physics_fps,
                capture_interval=capture_interval,
                capture_frames=capture_frames,
                capture_label="jacobian_ik_%s" % target_name,
                locked_indices=locked_indices,
            )
            actual_pos_err, _ = _evaluate_target(solver, target, pos_tol, orient_tol_deg)

        if target.is_reachable:
            # Pass = solver succeeded AND end pose is within tolerance.
            motion_within_tol = actual_pos_err <= pos_tol and solver_orient_err_deg <= orient_tol_deg
            passed = bool(solver_success and motion_within_tol)
        else:
            # Out-of-reach target: solver SHOULD fail. We mirror v1.
            passed = not solver_success
            motion_within_tol = False

        # Update target sphere color to reflect the outcome. One color per
        # outcome so the video legend matches the metric breakdown 1:1.
        if target_sphere_prims is not None and target.index < len(target_sphere_prims):
            sphere_prim = target_sphere_prims[target.index]
            if sphere_prim is not None:
                if target.is_reachable and passed:
                    set_target_sphere_color(sphere_prim, COLOR_TARGET_REACHED)
                elif target.is_reachable and not solver_success:
                    set_target_sphere_color(sphere_prim, COLOR_TARGET_SOLVE_FAILED)
                elif target.is_reachable:
                    set_target_sphere_color(sphere_prim, COLOR_TARGET_MOTION_FAILED)
                elif not target.is_reachable and passed:
                    set_target_sphere_color(sphere_prim, COLOR_TARGET_OUT_OF_REACH_OK)
                else:
                    # OOR target but solver claimed reachable -- false positive.
                    set_target_sphere_color(sphere_prim, COLOR_TARGET_OOR_FALSE_POSITIVE)

        # Record per-target metrics with solver-side numbers; the
        # motion-phase pos error is informational and may be larger than
        # the precompute estimate when the PD drive has not fully
        # tracked the smoothstep target.
        record = {
            "index": target.index,
            "name": target_name,
            "is_reachable": bool(target.is_reachable),
            "passed": bool(passed),
            "solver_success": bool(solver_success),
            "pos_err": float(actual_pos_err if math.isfinite(actual_pos_err) else solver_pos_err),
            "orient_err_deg": float(solver_orient_err_deg),
            "iterations": int(solution["iterations"]),
        }
        per_target_results.append(record)

        if bbox_errors:
            for msg in bbox_errors:
                ctx.warn(msg)
        if not passed and target.is_reachable:
            ctx.warn(
                "JIK: %s failed (pos_err=%.4f m, orient_err=%.2f deg, iters=%d)"
                % (
                    target_name,
                    record["pos_err"],
                    record["orient_err_deg"],
                    record["iterations"],
                )
            )
        elif passed and target.is_reachable:
            ctx.log(
                "JIK: %s reached (pos_err=%.4f m, iters=%d)" % (target_name, record["pos_err"], record["iterations"])
            )
        elif not target.is_reachable and passed:
            ctx.log("JIK: %s out-of-reach correctly rejected (pos_err=%.4f m)" % (target_name, record["pos_err"]))
    return per_target_results


def _record_phase_metrics(ctx, summary, ee_link_path):
    # type: (Any, Dict[str, Any], str) -> None
    """Write the metric set used by report.html.

    The first three metrics give the at-a-glance "generated vs reached"
    summary the user wants in the report:
    - jik_targets_generated: total targets created (in-reach + out-of-reach).
    - jik_targets_reached: in-reach targets the robot successfully reached.
    - jik_targets_total_passed: total passing targets including out-of-reach
      that correctly failed (the headline pass count).
    """
    targets_total = int(summary["targets_total"])
    in_reach_total = int(summary["in_reach_total"])
    in_reach_passed = int(summary["in_reach_passed"])
    in_reach_solver_failed = int(summary["in_reach_solver_failed"])
    in_reach_motion_failed = int(summary["in_reach_motion_failed"])
    out_of_reach_total = int(summary["out_of_reach_total"])
    out_of_reach_correct = int(summary["out_of_reach_correct"])
    out_of_reach_false_positive = int(summary["out_of_reach_false_positive"])

    # Headline metrics.
    ctx.add_metric("jik_targets_generated", targets_total)
    ctx.add_metric("jik_targets_reached", in_reach_passed)
    ctx.add_metric("jik_targets_total_passed", in_reach_passed + out_of_reach_correct)

    # Reach-class totals.
    ctx.add_metric("jik_targets_in_reach", in_reach_total)
    ctx.add_metric("jik_targets_out_of_reach", out_of_reach_total)
    ctx.add_metric("jik_in_reach_failed", summary["in_reach_failed"])

    # Per-outcome counts. The COLOR is embedded in the metric name so the
    # report row reads "what happened + what color" in one line, and the
    # alphabetic sort groups in-reach-* and out-of-reach-* together.
    ctx.add_metric("jik_in_reach_passed_green", in_reach_passed)
    ctx.add_metric("jik_in_reach_solver_failed_red", in_reach_solver_failed)
    ctx.add_metric("jik_in_reach_motion_failed_orange", in_reach_motion_failed)
    ctx.add_metric("jik_out_of_reach_correctly_failed_magenta", out_of_reach_correct)
    ctx.add_metric("jik_out_of_reach_false_positive_yellow", out_of_reach_false_positive)

    ctx.add_metric(
        "jik_max_position_error_m",
        round(summary["max_position_error_m"], 6),
    )
    ctx.add_metric(
        "jik_max_orientation_error_deg",
        round(summary["max_orientation_error_deg"], 4),
    )
    ctx.add_metric("jik_pass_rate", round(summary["pass_rate"], 4))
    ctx.add_metric("jik_ee_link", ee_link_path)


async def run_jacobian_ik(ctx, robot, scene_info, config):
    # type: (Any, Any, Dict[str, Any], Dict[str, Any]) -> None
    """Run the JIK phase. Mutates ctx via skip / add_metric / warn / fail."""
    # ---- Resolve config ------------------------------------------------
    cfg = dict(get_defaults())
    if config:
        cfg.update(config)

    settle_seconds = float(cfg["settle_seconds"])
    num_targets = int(cfg["num_targets"])
    out_of_reach_count = int(cfg["out_of_reach_count"])
    # Accept either a tuple of factors (v1.6 multi-shell pattern) or a
    # single float (legacy callers / overrides).
    rf_cfg = cfg.get("target_radius_factors") or cfg.get("target_radius_factor")
    if isinstance(rf_cfg, (int, float)):
        target_radius_factors = (float(rf_cfg),)
    elif isinstance(rf_cfg, (list, tuple)) and rf_cfg:
        target_radius_factors = tuple(float(f) for f in rf_cfg)
    else:
        target_radius_factors = (0.5, 0.7, 0.9)
    # TODO: out_of_reach_factor is read but not applied; _generate_fk_targets()
    # hard-codes the out-of-reach multiplier (1.4) instead (latent bug).
    out_of_reach_factor = float(cfg["out_of_reach_factor"])  # noqa: F841
    pos_tol = float(cfg["position_tolerance"])
    orient_tol_deg = float(cfg["orientation_tolerance_deg"])
    orient_tol_rad = math.radians(orient_tol_deg)
    max_solver_iterations = int(cfg["max_solver_iterations"])
    damping_lambda = float(cfg["damping_lambda"])
    physics_fps = float(cfg["physics_fps"])
    capture_fps = int(cfg["capture_fps"])
    min_pass_rate = float(cfg["min_pass_rate"])
    # TODO: hemisphere_only is read but not applied; OOR target generation always
    # forces the upper hemisphere (v[2] = abs(v[2])) regardless of this flag (latent bug).
    hemisphere_only = bool(cfg["hemisphere_only"])  # noqa: F841

    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))

    # ---- Discover end-effector ----------------------------------------
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    if stage is None:
        # scene_info["stage"] is wired by the runner; missing it is a
        # framework setup bug, not an asset-authoring issue. Tag clearly so
        # the asset author does not chase a phantom asset fix.
        ctx.skip(
            "INTERNAL: JIK scene_info has no USD stage -- runner did not "
            "populate scene_info['stage'] before invoking the phase. This "
            "is a framework bug; the asset under test is not at fault. "
            "File against simready-benchmark-kit-suite (articulation runner / "
            "scene builder) with the asset path and the runner log."
        )
        return

    # v1.6 parity: pass the ASSET root prim (e.g. /World/AssetRoot/Asset),
    # NOT the articulation root (e.g. /robot/Geometry/world). Many robots
    # (Fanuc CR/CRX) author the articulation root in a sibling scope to the
    # link prims; walking under the articulation root finds zero links.
    asset_prim = scene_info.get("asset_prim")
    if asset_prim is not None and asset_prim.IsValid():
        search_root = str(asset_prim.GetPath())
    else:
        search_root = robot.prim_path
    ctx.step("JIK: discovering end-effector under %s" % search_root)
    ee_link_path = discover_end_effector_link(stage=stage, robot=robot, robot_root_path=search_root)
    if ee_link_path is None:
        ctx.skip(
            _fix_message_no_end_effector(
                search_root=search_root,
                robot_prim_path=str(robot.prim_path),
            )
        )
        return
    ctx.log("JIK: end-effector link: %s" % ee_link_path)

    # ---- Settle + snapshot home configuration -------------------------
    home_joints = await _settle_and_snapshot(ctx, robot, settle_seconds, physics_fps)

    # ---- Build solver --------------------------------------------------
    # Closed-loop / parallel-linkage joints (e.g. the M-2000 counterbalance
    # P2/P2_01) cannot be driven as free DOFs: the loop constraint fights the
    # finite-difference perturbation and corrupts their Jacobian columns. Lock
    # them so the DLS solve runs over the main open chain only and the loop
    # joints passively follow their constraint. Empty on open-chain robots.
    locked_indices = set(int(i) for i in scene_info.get("loop_joint_indices") or [])
    loop_joint_names = scene_info.get("loop_joint_names") or []
    if locked_indices:
        ctx.step(
            "JIK: locking %d closed-loop / parallel-linkage joint(s) (%s); "
            "solving IK over the main open chain only. Refer to DJ.011."
            % (len(locked_indices), ", ".join(loop_joint_names))
        )
        ctx.add_metric("jik_loop_joints_locked", len(locked_indices))
    try:
        solver = JacobianIKSolver(
            robot=robot,
            ee_link_path=ee_link_path,
            damping_lambda=damping_lambda,
            locked_indices=locked_indices,
        )
    except Exception as exc:
        ctx.skip(_fix_message_solver_construct(exc))
        return

    home_orientation = _capture_home_orientation(solver)

    # ---- Reach + base position -----------------------------------------
    base_pos = get_robot_base_position(robot, scene_info)
    robot_reach = estimate_robot_reach(asset_prim or robot_root_prim)
    # Use the largest factor as the headline radius for metrics.
    max_radius_factor = max(target_radius_factors)
    target_radius = max(0.05, robot_reach * max_radius_factor)
    ctx.add_metric("jik_robot_reach", round(robot_reach, 4))
    ctx.add_metric("jik_target_radius", round(target_radius, 4))
    ctx.add_metric("jik_base_position_x", round(float(base_pos[0]), 4))
    ctx.add_metric("jik_base_position_y", round(float(base_pos[1]), 4))
    ctx.add_metric("jik_base_position_z", round(float(base_pos[2]), 4))

    # ---- Generate targets (forward-kinematics sampled) ----------------
    # Targets are EE poses the arm demonstrably holds at sampled in-limits
    # configurations, so every in-reach target is a provably feasible 6-DOF
    # pose (position + orientation). This replaces position-only shell targets,
    # which fixed the home orientation at every sampled point and were
    # infeasible for most points on a real arm -- the cause of spurious red
    # solver failures on conformant arms. Loop-locked DOFs are not sampled.
    lowers, uppers = robot.get_joint_position_limits()
    targets, max_observed_reach = await _generate_fk_targets(
        ctx=ctx,
        robot=robot,
        solver=solver,
        home_joints=home_joints,
        base_pos=base_pos,
        lowers=lowers,
        uppers=uppers,
        locked=locked_indices,
        num_reachable=num_targets,
        num_out_of_reach=out_of_reach_count,
    )
    ctx.add_metric("jik_max_observed_reach", round(float(max_observed_reach), 4))
    if not targets:
        # The target generator should always return at least one target as
        # long as num_reachable + num_out_of_reach > 0 and a radius factor
        # is set -- all of which are guaranteed by get_defaults(). An empty
        # list here means the generator itself failed or the caller
        # overrode config with zero counts.
        ctx.skip(
            "INTERNAL: JIK target generator returned zero targets despite "
            "num_targets=%d, out_of_reach_count=%d, radius_factors=%s. "
            "This is a framework / test-config bug (not an asset issue). "
            "Verify the JIK config override on this profile and file "
            "against simready-benchmark-kit-suite if the defaults are in use."
            % (num_targets, out_of_reach_count, str(target_radius_factors))
        )
        return
    ctx.log("JIK: generated %d targets" % len(targets))

    # ---- Target sphere visualization (gray = pending) -----------------
    show_spheres = bool(cfg.get("show_target_spheres", True))
    sphere_scope = str(cfg.get("target_sphere_scope", "/World/IK_Targets"))
    sphere_radius = float(cfg.get("target_sphere_radius", 0.04))
    target_sphere_prims = []  # type: List[Any]
    if show_spheres:
        target_sphere_prims = create_target_spheres_from_targets(
            stage=stage,
            parent_path=sphere_scope,
            targets=targets,
            radius=sphere_radius,
        )

    # ---- Baseline bbox (explode canary) -------------------------------
    baseline_bbox = None  # type: Optional[BBoxSnapshot]
    if asset_prim is not None or robot_root_prim is not None:
        baseline_bbox = compute_world_aligned_bbox(robot_root_prim or asset_prim)
        ctx.add_metric("jik_bbox_baseline_volume", round(baseline_bbox.volume, 6))

    # ---- Precompute solver solutions ----------------------------------
    ctx.step("JIK: precompute phase begin (%d targets)" % len(targets))
    solutions = await _precompute_solutions(
        ctx=ctx,
        robot=robot,
        solver=solver,
        targets=targets,
        home_joints=home_joints,
        home_orientation=home_orientation,
        pos_tol=pos_tol,
        orient_tol_rad=orient_tol_rad,
        max_iterations=max_solver_iterations,
    )

    # ---- Motion playback for each solution ----------------------------
    capture_frames = []  # type: List[str]
    ctx.step("JIK: motion phase begin (%d solutions)" % len(solutions))
    per_target_results = await _run_motion_for_solutions(
        ctx=ctx,
        robot=robot,
        solver=solver,
        scene_info=scene_info,
        solutions=solutions,
        home_joints=home_joints,
        cfg=cfg,
        capture_frames=capture_frames,
        capture_interval=capture_interval,
        baseline_bbox=baseline_bbox,
        target_sphere_prims=target_sphere_prims,
        locked_indices=locked_indices,
    )

    # Sphere cleanup -- so the asset stage stays clean between tests.
    if show_spheres:
        cleanup_target_spheres(stage, sphere_scope)

    # ---- Encode video --------------------------------------------------
    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="jacobian_ik", role="summary")

    # ---- Aggregate + gate ---------------------------------------------
    summary = aggregate_jik_summary(per_target_results)
    _record_phase_metrics(ctx, summary, ee_link_path)

    if summary["in_reach_total"] <= 0:
        # No in-reach targets means the bbox-based reach estimate is
        # degenerate -- typically an asset-authoring problem (wrong scale,
        # missing geometry under the articulation root) rather than a
        # framework bug. Treat as skip to mirror v1's defensive path.
        asset_path = (
            str(asset_prim.GetPath()) if asset_prim is not None and asset_prim.IsValid() else str(robot.prim_path)
        )
        ctx.skip(
            _fix_message_no_in_reach_targets(
                robot_reach=robot_reach,
                asset_prim_path=asset_path,
            )
        )
        return

    if summary["pass_rate"] < min_pass_rate:
        ctx.fail(
            _fix_message_pass_rate_below_min(
                pass_rate=summary["pass_rate"],
                min_pass_rate=min_pass_rate,
                in_reach_passed=summary["in_reach_passed"],
                in_reach_total=summary["in_reach_total"],
                in_reach_solver_failed=summary["in_reach_solver_failed"],
                in_reach_motion_failed=summary["in_reach_motion_failed"],
                max_pos_err=summary["max_position_error_m"],
                max_orient_err_deg=summary["max_orientation_error_deg"],
                pos_tol=pos_tol,
                orient_tol_deg=orient_tol_deg,
                failure_names=summary["failure_names"],
                ee_link_path=ee_link_path,
            )
        )
