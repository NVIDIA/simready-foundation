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
"""FET022 Jacobian IK: per-joint commanded-position + reporting sanity."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import jacobian_ik as jik_phase


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="jacobian_ik",
    description=(
        "Generates per-robot-type IK targets (Fibonacci sphere for arms; "
        "FK-reach single-radius ring for SCARA), then uses an in-house "
        "damped-least-squares Jacobian IK solver to compute joint "
        "configurations. Commands the asset and verifies the EE reaches "
        "each target within position + orientation tolerance. Independent "
        "of Lula descriptors — works on any asset with a discoverable "
        "end-effector link. Not applicable to gripper-type robots."
    ),
    expected_video=(
        "The robot's end-effector visits a sequence of generated targets "
        "around home — for arms a sphere of points, for SCARA a horizontal "
        "ring at home Z. At each target, the EE settles briefly. A pass "
        "shows the EE reaching the majority of in-reach targets; failure "
        "shows the EE drifting away or oscillating past targets without "
        "converging."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=jik_phase.get_defaults(),
    max_duration=600,
)
async def test_jacobian_ik(ctx):
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await jik_phase.run_jacobian_ik(ctx, robot, scene_info, ctx.config)
