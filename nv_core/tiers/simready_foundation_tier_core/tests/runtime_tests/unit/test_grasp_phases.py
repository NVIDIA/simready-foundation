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
import pytest
from simready_benchmark_kit_suite.fet005_grasp.grasp_phases import GraspPhaseManager
from simready_benchmark_kit_suite.fet005_grasp.phase_dropping import DroppingPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_grasping import GraspingPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_opening import OpeningPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_shake import ShakePhase


@pytest.mark.parametrize(
    ("phase_index", "expected"),
    [
        (0, True),  # Stability
        (1, True),  # GripperPositioning
        (3, False),  # Lifting
        (4, False),  # HoldBeforeShake
        (8, False),  # Dropping
    ],
)
def test_grasp_line_tracking_stops_at_lift(phase_index, expected):
    manager = object.__new__(GraspPhaseManager)
    manager._current = phase_index

    assert manager.tracking_active is expected


def test_grasp_line_tracking_stops_after_expected_aperture_is_reached():
    grasping = object.__new__(GraspingPhase)
    grasping._contact_acquired = False
    manager = object.__new__(GraspPhaseManager)
    manager._current = manager._GRASPING_INDEX
    manager._grasping = grasping

    assert manager.tracking_active is True

    grasping._contact_acquired = True

    assert manager.tracking_active is False


def test_shake_fails_when_grasp_point_leaves_live_jaw_midpoint():
    class Robot:
        def get_joint_targets(self):
            return (0.0, 0.0, 0.0)

        def update_joint_target_positions(self, _x, _y, _z):
            pass

    class Scene:
        robot = Robot()

        def __init__(self):
            self._midpoints = iter(
                [
                    ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
                    ((0.0, 0.0, -0.1), (0.0, 0.0, 0.0)),
                ]
            )

        def get_grasp_and_gripper_midpoints(self):
            return next(self._midpoints)

    class Tracker:
        min_z_history = [1.0]

    phase = ShakePhase({"physics_fps": 60})
    result = phase.check_frame(0, 0.0, Scene(), Tracker())

    assert result["failed"] is True
    assert "object left the jaws" in result["message"]
    assert "grasp separation=0.1000m" in result["message"]


def test_opening_disables_fixture_collisions_once_after_opening_completes():
    class Robot:
        def __init__(self):
            self.close_targets = []
            self.open_calls = 0

        def get_gripper_joint_position(self):
            return -0.02

        def close(self, target):
            self.close_targets.append(target)

        def open(self):
            self.open_calls += 1

    class Scene:
        def __init__(self):
            self.robot = Robot()
            self.disable_calls = 0

        def disable_gripper_pad_collisions(self):
            self.disable_calls += 1

    class Tracker:
        center_history = [(0.0, 0.0, 1.0)]

    phase = OpeningPhase(
        {
            "physics_fps": 10,
            "open_duration": 0.2,
            "release_check_seconds": 1.0,
        }
    )
    scene = Scene()
    tracker = Tracker()

    phase.check_frame(0, 0.0, scene, tracker)
    phase.check_frame(1, 0.1, scene, tracker)
    phase.check_frame(2, 0.2, scene, tracker)
    phase.check_frame(3, 0.3, scene, tracker)

    assert scene.robot.open_calls == 1
    assert scene.disable_calls == 1
    assert scene.robot.close_targets == [-0.02, -0.01]


def test_drop_verdict_remains_strict_after_fixture_release():
    class Tracker:
        center_history = [(0.0, 0.0, 1.0)]

    phase = DroppingPhase(
        {
            "physics_fps": 10,
            "fall_min_delta_z": 0.05,
            "drop_check_seconds": 0.2,
        }
    )
    phase._compute_required_fall = lambda _scene: 0.05

    assert phase.check_frame(0, 0.0, object(), Tracker()) is None
    result = phase.check_frame(2, 0.2, object(), Tracker())

    assert result["failed"] is True
    assert result["drop_distance"] == 0.0
    assert "needed 0.0500m" in result["message"]
