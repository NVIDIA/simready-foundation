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
"""EFF phase: external-force break detection across 12 directions.
V1 reference: shared_phases/effort_limit.py.
"""

import math

from simready.evaluate.core.output_layout import UnsafeEvidencePathError
from simready.foundation.tier_core.runtime_tests.articulation_phases.config_validation import (
    finite_number,
    validate_phase_config,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.force_utils import (
    apply_external_force,
    clear_external_force,
    clear_force_visualization,
    generate_12_force_directions,
    visualize_force_arrow,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    check_bbox_explode,
    compute_world_aligned_bbox,
    freeze_bbox_reference,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    require_vector,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_state import (
    reset_to_default,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.settling import (
    nominal_settle_steps,
    settle_nominal,
)

_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Feature:   nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/"
    "FET022_DrivenJoints.PhysX.md\n"
    "  Drive:     nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_driven_joints/requirements/\n"
    "             physics-drive-and-joint-state.md (DJ.001 -- maxForce > 0)\n"
    "             drive-joint-value-reasonable.md  (DJ.006 -- stiffness/"
    "damping ranges)\n"
    "  Joints:    nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/"
    "physics_joints/requirements/\n"
    "             joint-body-target-exists.md\n"
    "  Example:   sample_content/common_assets/robots_general/ur10/"
    "simready_usd/payloads/Physics/physics.usda\n"
    "             (search for: drive:angular:physics:maxForce)"
)


def _no_testable_joints_message(asset_path, passive_count, follower_count):
    # type: (str, int, int) -> str
    return (
        "EFF: no joints with a finite runtime range or positive effort-limit\n"
        "readback remain for external-force testing.\n"
        f"  Asset: {asset_path}\n"
        f"  Passive joints excluded: {passive_count}\n"
        f"  Mimic-follower joints excluded: {follower_count}\n\n"
        "Inspect the selected variant, imported controls/limits, unit basis and\n"
        "candidate filters. Passive, coupled or continuous joints may legitimately\n"
        "provide no candidate. This is insufficient test evidence, not proof of\n"
        "missing authoring. Authored USD angular limits use degrees and linear\n"
        "limits use stage units; qualify runtime coordinates separately.\n"
        "Do not invent limits, add a solver-specific schema or raise effort ratings\n"
        "merely to run EFF. External body force in N is not joint actuator torque.\n\n"
        f"{_SPEC_REFERENCE}"
    )


def _no_child_body_message(joint_name, joint_index):
    # type: (str, int) -> str
    return (
        f"EFF: joint '{joint_name}' (DOF index {joint_index}) has no resolvable downstream\n"
        "child-body mapping; the required probe could not execute.\n\n"
        "EFF needs an imported body to receive its external force. Inspect the\n"
        "composed joint targets, runtime DOF/body mapping, fixed-body merging and\n"
        "selected variant before classifying this as an asset defect. World/root\n"
        "joint conventions may legitimately leave one USD body target unset;\n"
        "do not invent a parent body or add physics APIs merely to satisfy mapping.\n"
        "An unexecuted joint supplies no force-response evidence.\n\n"
        f"{_SPEC_REFERENCE}"
    )


def _joint_broke_message(joint_name, broke_directions, commanded_force):
    # type: (str, list, Optional[float]) -> str
    force_str = "unavailable" if commanded_force is None else ("%.1f N" % commanded_force)
    return (
        "EFF: joint '{name}' failed the evaluated external-force response criterion.\n"
        "  Failing directions: {dirs}\n"
        "  Commanded external body force at failure: {force}\n"
        "  Minimum failure threshold: unavailable (not measured break force)\n\n"
        "The criterion can fail on finite runtime range overrun or bounding-box\n"
        "growth. Missing/nonfinite required readings are execution errors, not\n"
        "observed force-response failures. This does not prove physical joint\n"
        "breakage, insufficient actuator rating or incorrect source limits.\n"
        "Inspect the required readings and force application, leverage, imported\n"
        "limits/controls, unit basis, base/gravity setup and solver behavior.\n"
        "The issued world-frame body force is in N; it cannot be compared directly\n"
        "with an angular actuator torque in N*m or interpreted as measured contact\n"
        "force. Authored USD angular limits use degrees; runtime angles use radians.\n"
        "Do not raise ratings, widen limits or change gains/load/tolerances merely\n"
        "to obtain a pass. Preserve the original plan, asset and observed trajectory;\n"
        "any evidence-backed repair or tuning is external to Evaluate.\n\n"
        "{ref}"
    ).format(name=joint_name, dirs=", ".join(broke_directions) or "(none)", force=force_str, ref=_SPEC_REFERENCE)


def _aggregate_failure_message(failed, tested, failure_names, force_magnitude):
    # type: (int, int, list, float) -> str
    return (
        "EFF: {failed}/{tested} joints failed the evaluated response criterion\n"
        "under {force:.0f} N commanded external body force.\n"
        "  Failing joints: {names}\n\n"
        "Review per-joint directions and required readings to distinguish range\n"
        "overrun and bounding-box growth. Missing/nonfinite required readings are\n"
        "execution errors, not observed response failures. Compare the selected\n"
        "variant, force/body mapping, controls/limits, unit basis, base/gravity setup\n"
        "and importer/solver support before attributing an asset defect.\n"
        "This is not a direct actuator-effort or physical-breakage measurement.\n"
        "Do not infer a safe gain/rating change or reduce the tested load merely\n"
        "from the number of failures. Preserve the plan and evidence for triage.\n\n"
        "{ref}"
    ).format(failed=failed, tested=tested, force=force_magnitude, names=", ".join(failure_names), ref=_SPEC_REFERENCE)


def get_defaults():
    # type: () -> dict[str, Any]
    # v1.6 parity (shared_phases.effort_limit): test_duration_seconds is the
    # TOTAL budget across all 12 directions, NOT per-direction. v1 computes:
    #   total_test_frames    = test_duration * fps
    #   frames_per_direction = total_test_frames // len(FORCE_DIRECTIONS)
    # so 2 s / 12 dirs = ~0.17 s per direction. Earlier ports of this file
    # ran the full test_duration per direction, which made EFF 12x slower
    # than v1 and pushed wall time past 6 min on a 6-DOF arm.
    return {
        "settle_seconds": 0.3,
        "force_magnitude_newtons": 10.0,
        "test_duration_seconds": 2.0,
        "break_tolerance": 0.1,
        "bbox_explode_ratio": 10.0,
        # Retained configuration keys for compatibility; no refinement probe is
        # implemented. They cannot establish a measured threshold/lower bound.
        "bisection_enabled": True,
        "bisection_min_newtons": 1.0,
        "bisection_max_iterations": 6,
        "physics_fps": 240.0,
        "capture_fps": 8,
        "stop_on_first_break": True,
    }


def detect_break_from_positions(positions, authored_lo, authored_hi, break_tolerance, bbox_msgs):
    # type: (list[float], float, float, float, list[str]) -> tuple[bool, str]
    """Return (broke, reason). Break = position excursion past (lo, hi) by > tolerance*range OR bbox explode."""
    break_tolerance = finite_number(break_tolerance, "break_tolerance")
    if bbox_msgs:
        return True, "bbox explode: %s" % bbox_msgs[0]
    if not positions:
        return False, ""
    rng = authored_hi - authored_lo
    if rng <= 0:
        return False, ""
    overshoot = break_tolerance * rng
    if math.isfinite(rng) and not math.isfinite(overshoot):
        raise ValueError("Break tolerance produces a nonfinite allowed excursion")
    max_p = max(positions)
    min_p = min(positions)
    if max_p > authored_hi + overshoot:
        return True, "exceeded upper limit (%.3f > %.3f + tol %.3f)" % (max_p, authored_hi, overshoot)
    if min_p < authored_lo - overshoot:
        return True, "exceeded lower limit (%.3f < %.3f - tol %.3f)" % (min_p, authored_lo, overshoot)
    return False, ""


def aggregate_eff_summary(per_joint_results):
    # type: (list[dict[str, Any]]) -> dict[str, Any]
    total = len(per_joint_results)
    passed = sum(1 for r in per_joint_results if r["ok"])
    return {
        "joints_tested": total,
        "joints_passed": passed,
        "joints_failed": total - passed,
        "failure_names": [r["name"] for r in per_joint_results if not r["ok"]],
    }


async def run_effort_limit(ctx, robot, scene_info, config):
    # type: (Any, Any, dict[str, Any], dict[str, Any]) -> None
    stage = scene_info.get("stage")
    asset_prim = scene_info.get("asset_prim")
    robot_root_prim = scene_info.get("robot_root_prim")
    default_state = scene_info.get("default_state")

    validate_phase_config(config, "effort_limit")
    nominal_settle_steps(config.get("settle_seconds", 0.3), config.get("physics_fps", 240.0))
    physics_fps = float(config.get("physics_fps", 240.0))
    capture_fps = int(config.get("capture_fps", 8))
    settle_seconds = float(config.get("settle_seconds", 0.3))
    force_mag = float(config.get("force_magnitude_newtons", 10.0))
    test_duration = float(config.get("test_duration_seconds", 2.0))
    break_tol = float(config.get("break_tolerance", 0.1))
    bbox_ratio_limit = float(config.get("bbox_explode_ratio", 10.0))
    bisection_enabled = bool(config.get("bisection_enabled", True))
    stop_on_first_break = bool(config.get("stop_on_first_break", True))

    HB_EVERY = 40

    # Exclude passive joints (no drive — applying external force tests the
    # joint's break threshold under no-drive holding torque, which is
    # meaningless) and mimic-followers (their effort response is dominated by
    # the mimic constraint, not their own drive). Both sets come from
    # scene_info; for arms with no mimic, the follower set is empty.
    ctx.step("Scanning joints for EFF candidates (excluding passive + mimic followers)")
    passive_indices = {int(i) for i in scene_info.get("passive_joint_indices") or []}
    follower_indices = {int(i) for i in scene_info.get("mimic_follower_indices") or []}
    loop_indices = {int(i) for i in scene_info.get("loop_joint_indices") or []}
    excluded = passive_indices | follower_indices | loop_indices

    dof_names = list(robot.dof_names)
    lowers, uppers = robot.get_joint_position_limits()
    effort_limits = robot.get_joint_effort_limits()
    joints = []
    for i, name in enumerate(dof_names):
        if i in excluded:
            continue
        lo = float(lowers[i]) if i < len(lowers) else float("nan")
        hi = float(uppers[i]) if i < len(uppers) else float("nan")
        el = float(effort_limits[i]) if effort_limits is not None and i < len(effort_limits) else float("nan")
        has_pos = math.isfinite(lo) and math.isfinite(hi) and (hi - lo) > 1e-6
        has_eff = math.isfinite(el) and el > 0.0
        if has_pos or has_eff:
            joints.append({"index": i, "name": str(name), "lower": lo, "upper": hi})

    ctx.add_metric("eff_joints_with_candidates", len(joints))
    ctx.add_metric("eff_joints_skipped_passive", len(passive_indices))
    ctx.add_metric("eff_joints_skipped_mimic_follower", len(follower_indices))
    if not joints:
        ctx.skip(
            _no_testable_joints_message(
                asset_path=str(asset_prim.GetPath()) if asset_prim is not None else "<unknown asset>",
                passive_count=len(passive_indices),
                follower_count=len(follower_indices),
            )
        )
        return

    # Probe IPhysxSimulation availability. apply_force_at_pos lives on this
    # interface in Kit 110+ (it was removed from the PhysX C++ class returned
    # by get_physx_interface() that v1.6 used). When the interface is absent
    # (e.g., pure-Python test env), report a setup error rather than silently
    # omitting an applicable force-response test.
    try:
        from omni.physx import get_physx_simulation_interface

        if get_physx_simulation_interface() is None:
            raise RuntimeError("get_physx_simulation_interface returned None")
    except Exception as exc:
        raise RuntimeError(
            "EFF setup error: the required omni.physx simulation interface is"
            " not available in this process (%s: %s). The asset was not evaluated." % (type(exc).__name__, exc)
        ) from exc

    ctx.step("Settling robot before EFF")
    await settle_nominal(ctx, settle_seconds, physics_fps, phase="EFF")
    baseline_bbox = freeze_bbox_reference(
        compute_world_aligned_bbox(asset_prim or robot_root_prim), asset_prim or robot_root_prim, ctx, "eff"
    )

    force_vectors = generate_12_force_directions()
    capture_frames = []
    capture_interval = max(1, int(physics_fps / max(1, capture_fps)))
    per_joint_results = []

    active_primary = None

    def preserve_completed_results():
        summary = aggregate_eff_summary(per_joint_results)
        for name, value in (
            ("eff_joints_tested", summary["joints_tested"]),
            ("eff_joints_passed", summary["joints_passed"]),
            ("eff_joints_failed", summary["joints_failed"]),
            ("eff_joint_results", per_joint_results),
        ):
            optional(lambda name=name, value=value: ctx.add_metric(name, value))

    def optional(operation):
        try:
            return operation()
        except BaseException as error:
            if active_primary is None and (
                not isinstance(error, Exception) or isinstance(error, UnsafeEvidencePathError)
            ):
                raise
            if active_primary is not None:
                note_secondary_error(
                    active_primary, lambda error=error: f"EFF optional delivery also failed: {error!r}"
                )
            return None

    for jnum, jinfo in enumerate(joints, start=1):
        body_path, motion, arrow_path, fvec = None, None, None, None
        broke_directions, broke_reasons = [], {}
        interruption = "required_probe_interrupted"
        try:
            ctx.step("EFF joint %d/%d: %s" % (jnum, len(joints), jinfo["name"]))
            broke_directions = []
            broke_reasons = {}
            commanded_force_at_failure = None
            body_path = robot.get_child_body_path(jinfo["index"]) if hasattr(robot, "get_child_body_path") else None
            if not body_path:
                msg = _no_child_body_message(jinfo["name"], jinfo["index"])
                detail = getattr(robot, "_child_body_resolve_detail", "")
                if detail:
                    msg = msg + "\nResolver detail: " + detail + "\n"
                # This candidate is applicable but cannot be exercised. Preserve
                # any earlier joint evidence without counting the unexecuted one
                # as tested/passed or attributing a source-asset defect.
                preserve_completed_results()
                raise RuntimeError("EFF setup error: required child-body mapping is unresolved.\n" + msg)

            from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_history import (
                make_joint_observer,
            )

            motion = optional(
                lambda jinfo=jinfo, jnum=jnum, body_path=body_path: make_joint_observer(
                    ctx,
                    scene_info,
                    jinfo["name"],
                    "eff_joint_%03d" % jnum,
                    {
                        "position": {"unit": "{joint}", "source": "RobotHandle articulation position readback"},
                        "external_force_x": {"unit": "N", "source": "world-frame external force command on child body"},
                        "external_force_y": {"unit": "N", "source": "world-frame external force command on child body"},
                        "external_force_z": {"unit": "N", "source": "world-frame external force command on child body"},
                        "force_point_x": {"unit": "native_world", "source": "observed live child-body COM world x"},
                        "force_point_y": {"unit": "native_world", "source": "observed live child-body COM world y"},
                        "force_point_z": {"unit": "native_world", "source": "observed live child-body COM world z"},
                    },
                    metadata={
                        "physics_fps": physics_fps,
                        "clock_basis": "cumulative force-probe step count / configured physics fps; reset and capture ticks excluded",
                        "force_basis": "issued external world force in N; not measured actuator torque or force",
                        "force_point_basis": "live child-body center of mass",
                        "force_point_unit": "native articulation world coordinates; stage-to-meter conversion unqualified",
                        "body_path": str(body_path),
                        "runtime_lower": jinfo["lower"] if math.isfinite(jinfo["lower"]) else None,
                        "runtime_upper": jinfo["upper"] if math.isfinite(jinfo["upper"]) else None,
                        "runtime_limit_source": "RobotHandle.get_joint_position_limits(); native articulation limit readback, not raw USD authored limits",
                        "break_tolerance": break_tol,
                    },
                )
            )
            motion_steps = 0

            def record_force_point(point, direction, jinfo=jinfo, body_path=body_path):
                try:
                    ctx.add_metric(
                        "eff_force_point_observation",
                        {
                            "basis": "live child-body center of mass",
                            "unit": "native articulation world coordinates",
                            "joint": jinfo["name"],
                            "body_path": str(body_path),
                            "direction": direction,
                            "world_com": list(point) if point is not None else None,
                        },
                    )
                except UnsafeEvidencePathError:
                    raise
                except Exception:
                    pass  # Diagnostics are optional; a required COM read remains authoritative.

            # v1.6 parity: test_duration is the TOTAL budget per joint across
            # all 12 directions, not per-direction. With test_duration=2.0s and
            # 12 directions, each direction gets ~0.17s of physics + capture.
            total_test_frames = max(60, int(test_duration * physics_fps))
            frames_per_direction = max(1, total_test_frames // len(force_vectors))

            for fvec in force_vectors:
                arrow_path = "/World/_effort_viz/j%d_%s" % (
                    jnum,
                    fvec.label.replace("+", "p").replace("-", "n"),
                )
                positions_buf = []
                bbox_msgs = []
                for frame in range(frames_per_direction):
                    # apply_force_at_pos is single-shot per physics tick;
                    # re-apply every frame so the force persists across the
                    # whole test window. Matches v1.6 behaviour.
                    interruption = "required_com_unavailable"
                    try:
                        world_com = tuple(
                            float(value)
                            for value in require_vector(
                                robot.get_child_body_world_com(body_path), "EFF", "live child-body COM", 3
                            )
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            f"EFF runtime error: required live child-body COM is unavailable for {body_path}; "
                            f"the current joint's response criterion was not evaluated. {exc}"
                        ) from exc
                    interruption = "required_probe_interrupted"
                    record_force_point(world_com, fvec.label)
                    if frame == 0:
                        try:
                            visualize_force_arrow(
                                stage, body_path, fvec.direction, force_mag, arrow_path, origin=world_com
                            )
                        except UnsafeEvidencePathError:
                            raise
                        except Exception:
                            optional(lambda motion=motion: motion._warn())
                    interruption = "force_application_unavailable"
                    submitted = apply_external_force(stage, body_path, fvec.direction, force_mag, world_com)
                    if not submitted:
                        raise RuntimeError(
                            "EFF setup error: required external force could not be submitted "
                            f"to PhysX child body {body_path}. The current joint's response criterion was not evaluated."
                        )
                    interruption = "required_probe_interrupted"
                    await ctx.step_one()
                    motion_steps += 1
                    idx = jinfo["index"]
                    interruption = "required_position_unavailable"
                    try:
                        positions = robot.get_joint_positions()
                        pos = float(positions[idx])
                    except Exception as exc:
                        raise RuntimeError(
                            "EFF runtime error: required position readback is unavailable "
                            f"for joint {jinfo['name']}; its force-response criterion was not evaluated."
                        ) from exc
                    if not math.isfinite(pos):
                        interruption = "required_position_nonfinite"
                        raise RuntimeError(
                            f"EFF runtime error: required position readback is nonfinite for joint {jinfo['name']}; "
                            "its force-response criterion was not evaluated."
                        )
                    interruption = "required_probe_interrupted"
                    positions_buf.append(pos)
                    try:
                        motion.sample(
                            {
                                "position": pos,
                                "external_force_x": float(fvec.direction[0]) * force_mag,
                                "external_force_y": float(fvec.direction[1]) * force_mag,
                                "external_force_z": float(fvec.direction[2]) * force_mag,
                                "force_point_x": world_com[0],
                                "force_point_y": world_com[1],
                                "force_point_z": world_com[2],
                            },
                            motion_steps / physics_fps,
                            "force_" + fvec.label,
                        )
                    except UnsafeEvidencePathError:
                        raise
                    except Exception:
                        try:
                            motion._warn()
                        except UnsafeEvidencePathError:
                            raise
                        except Exception:
                            pass
                    if frame % 20 == 0:
                        current_bbox = compute_world_aligned_bbox(asset_prim or robot_root_prim)
                        msg = check_bbox_explode(current_bbox, baseline_bbox, bbox_ratio_limit)
                        if msg:
                            bbox_msgs.append(msg)

                    if frame % capture_interval == 0:
                        frame_path = await ctx.capture_frame(
                            label="eff_%03d_%s_%04d" % (jnum, fvec.label, frame),
                            stabilize_frames=0,
                        )
                        if frame_path:
                            capture_frames.append(frame_path)
                            optional(lambda motion=motion, frame_path=frame_path: motion.record_capture(frame_path))
                        optional(lambda: ctx.scene.update_camera_follow(update_history=True))
                    if frame % HB_EVERY == 0:
                        ctx.step(
                            "EFF j=%s dir=%s frame=%d/%d" % (jinfo["name"], fvec.label, frame, frames_per_direction)
                        )
                    if bbox_msgs:
                        break

                clear_external_force(stage, body_path)
                optional(lambda arrow_path=arrow_path: clear_force_visualization(stage, arrow_path))

                broke, reason = detect_break_from_positions(
                    positions_buf,
                    jinfo["lower"],
                    jinfo["upper"],
                    break_tol,
                    bbox_msgs,
                )
                if broke:
                    broke_directions.append(fvec.label)
                    broke_reasons[fvec.label] = reason
                    if commanded_force_at_failure is None:
                        commanded_force_at_failure = force_mag
                        if bisection_enabled:
                            optional(
                                lambda: ctx.warn(
                                    "EFF: bisection refinement was requested but is not implemented; "
                                    "the minimum failure threshold remains unknown. Configured bisection "
                                    "bounds are not observations; no additional force probes were run."
                                )
                            )

                if default_state is not None:
                    await reset_to_default(ctx, robot, default_state, settle_seconds=0.2)

                # v1 parity: stop testing remaining directions once a break is
                # detected -- there is no value in confirming the joint is broken
                # in 11 more directions, and on a 6-DOF arm this saves up to ~90%
                # of the per-joint wall time on broken joints.
                if broke and stop_on_first_break:
                    ctx.step(
                        "EFF j=%s broke at dir=%s -- skipping remaining %d directions"
                        % (jinfo["name"], fvec.label, len(force_vectors) - len(broke_directions))
                    )
                    break

            optional(
                lambda motion=motion, broke_directions=broke_directions: motion.finish(
                    "first_break_detected" if broke_directions and stop_on_first_break else "force_directions_completed"
                )
            )

            ok = not broke_directions
            record = {
                "name": jinfo["name"],
                "broke_directions": broke_directions,
                "broke_reasons": broke_reasons,
                # Compatibility field remains unknown: no threshold search ran.
                "min_break_force_newtons": None,
                "commanded_force_at_failure_newtons": commanded_force_at_failure,
                "bisection_refinement_requested": bisection_enabled,
                "bisection_refinement_available": False,
                "ok": ok,
            }
            if not ok:
                optional(
                    lambda jinfo=jinfo, broke_directions=broke_directions, commanded_force_at_failure=commanded_force_at_failure: ctx.warn(
                        _joint_broke_message(jinfo["name"], broke_directions, commanded_force_at_failure)
                    )
                )
            else:
                optional(lambda jinfo=jinfo: ctx.log("EFF: Joint '%s' held across all 12 directions" % jinfo["name"]))
            per_joint_results.append(record)

        except BaseException as primary:
            active_primary = primary
            preserve_completed_results()
            optional(
                lambda jinfo=jinfo, fvec=fvec, interruption=interruption, broke_directions=broke_directions, broke_reasons=broke_reasons: ctx.add_metric(
                    "eff_incomplete_joint_evidence",
                    {
                        "name": jinfo["name"],
                        "status": "incomplete",
                        "interrupted_direction": fvec.label if fvec is not None else None,
                        "interruption": interruption,
                        "broke_directions": list(broke_directions),
                        "broke_reasons": dict(broke_reasons),
                    },
                )
            )
            if interruption == "required_com_unavailable":
                optional(lambda fvec=fvec: record_force_point(None, fvec.label if fvec is not None else None))
            if motion is not None:
                optional(lambda motion=motion: motion._warn())
                optional(lambda motion=motion, interruption=interruption: motion.finish(interruption))
            if body_path is not None:
                optional(lambda body_path=body_path: clear_external_force(stage, body_path))
            if arrow_path is not None:
                optional(lambda arrow_path=arrow_path: clear_force_visualization(stage, arrow_path))
            raise

    preserve_completed_results()
    if capture_frames:
        ctx.encode_video(capture_frames, fps=capture_fps, label="effort_limit", role="summary")

    summary = aggregate_eff_summary(per_joint_results)
    preserve_completed_results()

    if summary["joints_failed"] > 0:
        ctx.fail(
            _aggregate_failure_message(
                failed=summary["joints_failed"],
                tested=summary["joints_tested"],
                failure_names=summary["failure_names"],
                force_magnitude=float(config.get("force_magnitude_newtons", 10.0)),
            )
        )
