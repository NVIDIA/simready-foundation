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
"""FET022 Velocity Limit: verify joints respect authored max velocities."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import velocity_limit as vel_phase


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="velocity_limit",
    description=(
        "Drives each non-passive, non-mimic-follower joint individually "
        "from rest to its commanded position; verifies measured velocity "
        "stays within the authored physxJoint:maxJointVelocity at every "
        "frame (with tolerance configurable as velocity_tolerance_percent, "
        "default 20%). Validates that the asset's velocity limits are "
        "actually enforced by the PhysX backend at runtime."
    ),
    expected_video=(
        "Each tested joint moves one at a time from rest, accelerating to "
        "its max velocity, briefly holding, then decelerating back. Only "
        "one joint moves per segment. The gripper or robot base stays "
        "fixed (carrier holds it). On a passing run, no joint visibly "
        "snaps or jumps — motion is smooth at every joint."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=vel_phase.get_defaults(),
    max_duration=300,
)
async def test_velocity_limit(ctx):
    """Drive each joint and assert measured velocities stay within limits."""
    # Lazy imports: Kit/USD modules are not available in pure-Python test env.
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await vel_phase.run_velocity_limit(ctx, robot, scene_info, ctx.config)
