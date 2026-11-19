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

"""Regression coverage for Newton author-facing units and qualified triage."""

import inspect

from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    drive_gain_validation as dgv,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import effort_limit as eff
from simready.foundation.tier_newton.runtime_tests.articulation_phases import full_range_sweep as frs
from simready.foundation.tier_newton.runtime_tests.articulation_phases import jacobian_ik as jik
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases import state_accuracy as sta


def test_newton_limit_repair_uses_authored_degrees_not_runtime_radians():
    message = frs._fix_message_no_joints_with_limits(2, 4)
    assert "degrees for revolute" in message
    assert "physics:lowerLimit = -165.0" in message
    assert "-2.8973" not in message
    assert "prepend apiSchemas" not in message


def test_newton_tracking_failure_does_not_prescribe_gain_multiplication():
    message = sta._fix_message_joint_position_error("slide", 8.0, 5.0, "tracking")
    assert "linear" in message and "not a physical angle" in message
    assert "No evidence here establishes a cause" in message
    assert "raise by 10x" not in message
    assert "physxRigidBody:mass" not in message


def test_newton_mimic_filter_explains_native_or_compatibility_prerequisites():
    message = sta._fix_message_no_testable_joints(1, ["passive"], 1, ["follower"])
    assert "native Newton or supported compatibility mimic" in message
    assert "insufficient evidence" in message
    assert "no PhysxMimicJointAPI" not in message


def test_newton_dgv_prerequisites_do_not_infer_physx_authoring_or_remove_coupling():
    message = dgv._fix_message_no_drivable_joints("/Robot", 2, 1, 1)
    assert "enabled native Newton or supported compatibility mimic" in message
    assert "insufficient test evidence" in message
    assert "driven by PhysxMimicJointAPI" not in message
    assert "leave drive stiffness/damping at 0.0" not in message
    assert "stiffness = 1000" not in message


def test_newton_dgv_response_is_observation_not_tuning_prescription():
    message = dgv._fix_message_joint_step_response("slide", 25, 20, None, 4, 5, 4, 0.05, 0.0)
    summary = dgv._fix_message_dgv_summary_failure(1, 2, ["slide"], 20, 4, 4)
    assert "runtime joint coordinates" in message
    assert "No evidence here establishes a cause or a safe gain change" in message
    for text in (message, summary):
        assert "raise stiffness" not in text
        assert "RAISE" not in text
        assert "LOWER" not in text
        assert "repair or tuning is external" in text


def test_newton_mjc_failure_has_no_canned_gains_or_policy_relaxation():
    joints = [{"name": "slide", "index": 0, "lower": 0.0, "upper": 0.05}]
    message = mjc._build_fail_message_iterations(1, 3, [0], joints, 1.0, 8.0)
    assert "limits [0, 0.05] runtime joint coordinates" in message
    assert "does not isolate" in message
    assert "legacy configuration label is not a physical angle" in message
    assert "stiffness = 1.0e6" not in message
    assert "Increase" not in message
    assert "Loosen" not in message
    assert "remove them from" not in message


def test_newton_effort_usd_limit_examples_are_degrees_and_stage_units():
    message = eff._no_testable_joints_message("/Robot", 1, 1)
    assert "angular limits use degrees" in message
    assert "limits use stage units" in message
    assert "insufficient test evidence" in message
    assert "PhysxJointAPI" not in message
    assert "physics:lowerLimit = -166.0" not in message
    assert "physics:lowerLimit = -2.8973" not in message
    assert "meters for prismatic" not in message


def test_newton_jik_framework_errors_route_to_local_owner():
    source = inspect.getsource(jik._run_jacobian_ik_impl)
    assert "_run_jacobian_ik_impl" in inspect.getsource(jik.run_jacobian_ik)
    assert "File against the Newton tier's articulation runtime-test implementation" in source
    assert "against the Newton tier's runtime-test implementation if the defaults are in use." in source
    assert "core tier's" not in source
