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

"""Core STA/VEL diagnostic guidance must not prescribe force-pass repairs."""

import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import state_accuracy as sta
from simready.foundation.tier_core.runtime_tests.articulation_phases import velocity_limit as vel


@pytest.mark.parametrize(
    "message",
    [
        sta._fix_message_no_testable_joints(1, ["passive"], 1, ["follower"]),
        sta._fix_message_joint_position_error("slide", 12.5, 5.0, "target was not reached"),
        sta._fix_message_phase_failure(1, 2, ["slide"]),
        vel._fix_message_no_velocity_limits(),
        vel._fix_message_violations(1, 2, "slide", "slide: peak=0.5, limit=0.4"),
    ],
)
def test_guidance_keeps_cause_open_without_generic_repairs(message):
    for unsafe in (
        "prepend apiSchemas",
        "stiffness = 100000",
        "damping   = 10000",
        "physics:lowerLimit = -3.14159",
        "raise by 10x",
        "New value >= observed peak",
        "float physxJoint:maxJointVelocity = 120",
        "physxRigidBody:mass",
        "physxRigidBody:diagonalInertia",
        "Loosen `position_tolerance_deg`",
    ):
        assert unsafe not in message
    assert "selected variant" in message.lower()
    assert "original" in message.lower() or "before changing" in message.lower()


def test_sta_prerequisites_distinguish_authored_and_runtime_units():
    message = sta._fix_message_no_testable_joints(1, ["caster"], 1, ["finger"])
    assert "Passive joints: 1 (caster)" in message
    assert "Mimic followers: 1 (finger)" in message
    assert "targetPosition use\ndegrees" in message
    assert "runtime revolute coordinates use radians" in message
    assert "stage-distance units, not necessarily meters" in message
    assert "runtime linear scaling remains\nunqualified" in message
    assert "not an automatic asset failure" in message


def test_sta_legacy_summary_is_not_claimed_as_a_linear_joint_angle():
    message = sta._fix_message_joint_position_error("slide", 12.5, 5.0, "actual command mismatch")
    assert "12.50" in message and "5.00" in message and "actual command mismatch" in message
    assert "linear joints it is not a physical angle" in message
    assert "cause is not\nestablished" in message
    assert sta.get_defaults()["position_tolerance_deg"] == 5.0
    assert sta.get_defaults()["max_step_deg"] == 15.0


def test_velocity_guidance_keeps_linear_units_and_failure_guard_distinct():
    message = vel._fix_message_violations(1, 2, "slide", "slide: peak=0.5, limit=0.4")
    assert "1/2" in message and "peak=0.5, limit=0.4" in message
    assert "Angular comparisons use radians/s" in message
    assert "linear comparisons retain runtime native units/s (scale unqualified)" in message
    assert "first five startup observations" in message
    assert "consecutive near-zero observations" in message
    assert "speed exceedance from a bounding-box" in message
    assert "does not establish a cause" in message
    assert vel.get_defaults()["tolerance_percent"] == 0.05
    assert vel.get_defaults()["capture_fps"] == 15
