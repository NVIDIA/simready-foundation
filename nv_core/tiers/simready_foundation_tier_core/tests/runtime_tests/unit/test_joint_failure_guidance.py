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

"""Diagnostic-only regression coverage; no runtime controls are altered."""

import ast
from pathlib import Path

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    drive_gain_validation as dgv,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    effort_limit as eff,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    full_range_sweep as frs,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    gripper_close_lift as gcl,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    gripper_sites as sites,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach as ik,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    jacobian_ik as jik,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc,
)


@pytest.mark.parametrize(
    "message",
    [
        ik._fix_message_no_lula_descriptor("/Robot", "Manipulator"),
        ik._fix_message_no_ee_pose("UR10", "tool0", "/Robot"),
        ik._fix_message_no_targets(0.5, [0.0, 0.0, 0.0]),
        ik._fix_message_no_targets_reached(5, "tool0", "UR10"),
        ik._fix_message_low_success_rate(1, 5, 0.2, 0.5, list(range(10)), 0.03),
        jik._fix_message_no_end_effector("/Robot", "/Robot/root"),
        jik._fix_message_solver_construct(RuntimeError("missing runtime DOF mapping")),
        jik._fix_message_no_in_reach_targets(0.5, "/Robot"),
        jik._fix_message_pass_rate_below_min(0.2, 0.4, 1, 5, 2, 2, 0.1, 20, 0.05, 10, ["target_2"], "/Robot/tool0"),
        eff._no_testable_joints_message("/Robot", 1, 1),
        eff._no_child_body_message("slide", 1),
        eff._joint_broke_message("hinge", ["+x"], 2.5),
        eff._aggregate_failure_message(1, 2, ["hinge"], 10),
        dgv._fix_message_no_drivable_joints("/Robot", 2, 1, 1),
        dgv._fix_message_joint_step_response("slide", 60, 50, None, 5, 21, 20, 0.05, 0),
        dgv._fix_message_dgv_summary_failure(1, 2, ["slide"], 50, 5, 20),
    ],
)
def test_guidance_does_not_prescribe_force_pass_repairs(message):
    for unsafe in (
        "almost always",
        "stiffness = 400000",
        "damping   = 40000",
        "physics:lowerLimit = -2.8973",
        "prepend apiSchemas",
        "doubling stiffness",
        "raise by 10x",
        "Increase drive damping",
        "decrease stiffness by",
        "Bump maxForce",
        "escape hatches",
        "so PhysX sees",
        "usdGenSchema",
        "RENAME / RETAG",
    ):
        assert unsafe not in message
    assert "asset" in message.lower() or "runtime" in message.lower()


def test_full_range_guidance_distinguishes_authored_degrees_and_runtime_radians():
    from pxr import Sdf, Usd, UsdPhysics

    message = frs._fix_message_no_joints_with_limits(1, 2)
    assert "use degrees for revolute joints" in message
    assert "Runtime revolute readbacks use radians" in message
    assert "not suggested ratings" in message
    # Parse the emitted illustrative fragment using real USD, not a text-only
    # check: the authored angular values must be degrees, not runtime radians.
    lower = next(line.strip() for line in message.splitlines() if "float physics:lowerLimit" in line)
    upper = next(line.strip() for line in message.splitlines() if "float physics:upperLimit" in line)
    layer = Sdf.Layer.CreateAnonymous("frs_diagnostic.usda")
    assert layer.ImportFromString(
        '#usda 1.0\ndef PhysicsRevoluteJoint "illustrative" {\n' + lower + "\n" + upper + "\n}\n"
    )
    stage = Usd.Stage.Open(layer)
    joint = UsdPhysics.RevoluteJoint.Get(stage, "/illustrative")
    assert joint.GetLowerLimitAttr().Get() == -165.0
    assert joint.GetUpperLimitAttr().Get() == 165.0
    for guidance in (
        message,
        frs._fix_message_bbox_explode("hinge", "to_max", "grew 11x"),
        frs._fix_message_rest_violation("hinge", "to_min", 0.2, 3, 4),
        frs._fix_message_zero_return("hinge", 0.3, 0.2, 0.01),
        frs._fix_message_aggregate(1, 2, ["hinge"]),
    ):
        assert "radians for revolute" not in guidance
        assert "Bump" not in guidance
        assert "stiffness = 1000" not in guidance


@pytest.mark.parametrize(
    "name,kind,lower,upper",
    [
        ("slide", "prismatic", 0.000001, 0.085),
        ("hinge", "revolute", -0.7, 0.7),
        ("unresolved", None, -0.02, 0.02),
    ],
)
def test_mjc_reports_native_coordinates_without_guessing_angular_units(name, kind, lower, upper):
    joints = [{"name": name, "index": 2, "lower": lower, "upper": upper, "joint_type": kind}]
    message = mjc._format_joint_list(joints)
    assert f"limits [{lower:.6g}, {upper:.6g}]" in message
    assert "runtime joint coordinates" in message
    assert "motion metadata for units" in message
    assert " deg " not in message

    failure = mjc._build_fail_message_iterations(1, 3, [2], joints, 1.0, 8.0)
    assert "1/3" in failure and "failed iterations: 2" in failure
    assert "position_tolerance_deg=1.00" in failure
    assert "legacy configuration label is not a physical angle" in failure
    assert "does not isolate" in failure
    assert "stiffness = 1.0e6" not in failure
    skip = mjc._build_skip_message_no_movable_joints(3, 1)
    assert "Do not remove them from the articulation" in skip
    assert "not automatically meters" in skip


def test_mjc_iteration_warning_does_not_prescribe_tuning_or_weaker_policy():
    source = Path(mjc.__file__).read_text(encoding="utf-8")
    assert "Tune drive gains or relax target_margin_ratio." not in source
    assert "PD controller may need tuning per asset." not in source
    assert "Inspect actual commands, imported controls, coupling and unit basis; no cause is established." in source
    assert "Compare the selected variant, solver support and test setup before asset repair." in source


def test_gripper_open_diagnostic_respects_detected_mapping_and_authored_degree_units():
    from pxr import Sdf, Usd, UsdPhysics

    message = gcl._fix_message_open_mapping_wrong(
        joint_name="slide_or_hinge",
        actual_pos=0.2,
        expected_pos=0.7,
        error=0.5,
        tolerance=0.01,
        shape="sphere",
    )
    assert "Expected position:  0.7 selected open target" in message
    assert "Open is not universally the lower limit" in message
    assert "GR.003 is the tube axis" in message
    assert "not suggested travel ratings" in message
    assert "m for prismatic" not in message
    assert "stiffness = 1000" not in message
    # The illustrative authored limit fragment is syntactically valid USD and
    # uses degrees. Never paste a runtime-radian limit directly into USD.
    lower = next(line.strip() for line in message.splitlines() if "float physics:lowerLimit" in line)
    upper = next(line.strip() for line in message.splitlines() if "float physics:upperLimit" in line)
    layer = Sdf.Layer.CreateAnonymous("gripper_diagnostic.usda")
    assert layer.ImportFromString(
        '#usda 1.0\ndef PhysicsRevoluteJoint "illustrative" {\n' + lower + "\n" + upper + "\n}\n"
    )
    stage = Usd.Stage.Open(layer)
    joint = UsdPhysics.RevoluteJoint.Get(stage, "/illustrative")
    assert joint.GetLowerLimitAttr().Get() == 0.0
    assert joint.GetUpperLimitAttr().Get() == 40.0
    assert gcl._closed_fraction(0.5, 0.7, 0.0) == pytest.approx(2.0 / 7.0)


def test_gripper_mount_clearance_diagnostic_is_trial_setup_not_source_rest_pose():
    message = gcl._fix_message_grasp_below_object(0.02, 0.04)
    assert "0.0200 m" in message and "0.0400 m" in message
    assert "source asset need not be authored" in message
    assert "Do not rotate or translate the source asset" in message
    assert "test setup failure must be reported to the test owner" in message


def test_gripper_site_guidance_does_not_equate_grip_axis_width_to_jaw_opening():
    messages = [
        sites._fix_message_no_candidates("/Gripper"),
        sites._fix_message_incomplete_candidate(
            "/Gripper/site", "socketType", ["gripper_grip_line"], ["gripper_maxOpening"], 0
        ),
    ]
    for message in messages:
        assert "graspable-tube axis" in message
        assert "pad contact width" in message
        assert "not maxOpening" in message.replace("\n            # ", " ")
        assert "local stage coordinates" in message
        assert "pad-to-pad at max open" not in message
        assert "segment length should equal" not in message.lower()


def test_ik_keeps_observations_without_guaranteeing_workspace_or_orientation():
    message = ik._fix_message_low_success_rate(1, 5, 0.2, 0.5, list(range(10)), 0.03)
    assert "1 / 5" in message and "20.0%" in message and "50%" in message
    assert "0, 1, 2, 3, 4, 5, 6, 7 ..." in message
    assert "0.0300 m" in message
    assert "Authored USD angular limits use" in message
    assert "runtime angular coordinates use radians" in message
    assert "sampled position-success fraction" in message
    assert "not certify all targets" in message


def test_jik_distinguishes_solver_orientation_from_live_position():
    message = jik._fix_message_pass_rate_below_min(
        0.2, 0.4, 1, 5, 2, 2, 0.1, 20, 0.05, 10, ["target_2"], "/Robot/tool0"
    )
    assert "Targets passed: 1 / 5" in message
    assert "Solver failures (red targets): 2" in message
    assert "Playback failures after a solution (orange targets): 2" in message
    assert "Worst recorded position residual (solver or playback): 0.1000 m" in message
    assert "Worst solver orientation error: 20.00 deg" in message
    assert "not independently certify the final live orientation" in message
    assert "target_2" in message and "/Robot/tool0" in message


def test_effort_reports_criterion_not_physical_break_or_direct_torque():
    message = eff._joint_broke_message("hinge", ["+x", "-x"], 2.5)
    assert "+x, -x" in message
    assert "2.5 N" in message and "not measured break force" in message
    assert "execution errors" in message and "bounding-box" in message
    assert "Minimum failure threshold: unavailable" in message
    assert "Commanded external body force at failure" in message
    assert "not prove physical joint" in message
    assert "cannot be compared directly" in message and "N*m" in message
    missing = eff._no_child_body_message("slide", 1)
    assert "World/root" in missing and "legitimately leave one USD body target unset" in missing
    assert "unexecuted joint supplies no" in missing
    assert "required probe could not execute" in missing


def test_dgv_reports_warning_policy_without_gain_prescription():
    assert dgv.get_defaults()["step_fatal"] is False
    message = dgv._fix_message_joint_step_response("slide", 60, 50, None, 5, 21, 20, 0.05, 0)
    assert "runtime joint coordinates" in message
    assert "No evidence here establishes a cause or a safe gain change" in message
    assert "WARNING by default" in message and "step_fatal: true" in message


def _registration_strings(phase, name):
    path = Path(phase.__file__).resolve().parents[1] / "fet022_driven_joints" / (name + ".py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    kwargs = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and (
            isinstance(node.value, ast.Dict)
            or (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "dict"
            )
        )
    )
    if isinstance(kwargs, ast.Dict):
        return {
            ast.literal_eval(key): ast.literal_eval(value)
            for key, value in zip(kwargs.keys, kwargs.values, strict=True)
            if key is not None and ast.literal_eval(key) in ("description", "expected_video", "version")
        }
    return {
        keyword.arg: ast.literal_eval(keyword.value)
        for keyword in kwargs.keywords
        if keyword.arg in ("description", "expected_video", "version")
    }


def test_ik_registration_matches_sampled_position_criterion_and_default():
    text = _registration_strings(ik, "ik_target_reach")
    assert text["version"] == "1.2.9"
    assert ik.get_defaults()["min_success_rate"] == 0.5
    assert ik.get_defaults()["position_tolerance"] == 0.02
    assert "50%" in text["description"] and "2 cm" in text["description"]
    assert "solver input" in text["description"]
    assert "pass may contain failed targets" in text["expected_video"]
    assert "reaching every" not in text["expected_video"]


def test_jik_registration_matches_fraction_not_majority_and_solver_orientation():
    text = _registration_strings(jik, "jacobian_ik")
    assert text["version"] == "1.4.12"
    assert jik.get_defaults()["min_pass_rate"] == 0.4
    assert "40%" in text["description"] and "solver orientation error" in text["description"]
    assert "neither an every-target nor a majority-success guarantee" in text["expected_video"]
