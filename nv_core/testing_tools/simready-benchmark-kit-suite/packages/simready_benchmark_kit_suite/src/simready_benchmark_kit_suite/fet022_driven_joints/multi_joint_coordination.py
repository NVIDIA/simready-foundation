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
"""FET022 Multi-Joint Coordination: simultaneous convergence to targets."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import (
    multi_joint_coordination as mjc_phase,
)


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="multi_joint_coordination",
    description=(
        "Commands all non-passive joints simultaneously to a target "
        "configuration computed to place the end-effector at a chosen "
        "workspace point; verifies every joint reaches its commanded "
        "position within tolerance and within max_settling_seconds. "
        "Validates that the drive controllers don't fight each other "
        "during simultaneous motion and that the asset can execute "
        "coordinated trajectories without joint-by-joint stalling."
    ),
    expected_video=(
        "All robot joints move simultaneously, in coordination, toward a "
        "single end-effector target pose. The motion looks fluid — "
        "joints accelerate and decelerate in concert rather than one at "
        "a time. The end-effector smoothly reaches its target and holds. "
        "Joints stalling, jittering, or arriving at wildly different "
        "times indicates inadequate drive coordination."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=mjc_phase.get_defaults(),
    max_duration=300,
)
async def test_multi_joint_coordination(ctx):
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await mjc_phase.run_multi_joint_coordination(ctx, robot, scene_info, ctx.config)
