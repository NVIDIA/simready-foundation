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
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    drive_gain_validation as dgv,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    effort_limit as eff,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    ik_target_reach as ik,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    jacobian_ik as jik,
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
    assert "were not played back" in message
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
    assert text["version"] == "1.2.10"
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
