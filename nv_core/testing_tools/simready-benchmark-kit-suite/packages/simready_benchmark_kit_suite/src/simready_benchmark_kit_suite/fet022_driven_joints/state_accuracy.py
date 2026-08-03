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
"""FET022 State Accuracy: per-joint commanded-position + reporting sanity."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import state_accuracy as sta_phase


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="state_accuracy",
    description=(
        "Commands each non-passive, non-mimic-follower joint through a "
        "5-waypoint sequence around home (center, +step, center, -step, "
        "center) with step = min(15°, 10% of joint range). At each "
        "waypoint, measures actual position vs. commanded; verifies error "
        "stays within position_tolerance_deg (default 5°). Validates that "
        "the joint's drive can hold the commanded position accurately and "
        "that joint-state reporting is consistent."
    ),
    expected_video=(
        "Each tested joint visits 5 waypoints in sequence — small "
        "step out, back to center, small step the other way, back to "
        "center. Joints settle visibly at each waypoint before moving on. "
        "Drift past the commanded position, oscillation around it, or "
        "failure to reach it indicates inadequate drive stiffness/damping."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=sta_phase.get_defaults(),
    max_duration=300,
)
async def test_state_accuracy(ctx):
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await sta_phase.run_state_accuracy(ctx, robot, scene_info, ctx.config)
