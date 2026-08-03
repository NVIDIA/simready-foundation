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
"""FET022 Mimic Joint: PhysxMimicJointAPI follower-target tracking."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import mimic_joint as mim_phase


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="mimic_joint",
    description=(
        "For each PhysxMimicJointAPI pair on the asset, sweeps the "
        "reference (master) joint through its range and verifies the "
        "follower's motion magnitude matches |gear| × reference motion "
        "magnitude within gear_ratio_tolerance (default 0.10). "
        "Direction-agnostic — sign of gear and rest-pose offset are "
        "diagnostic warnings only. Validates that PhysX is enforcing the "
        "authored gear ratio, regardless of joint-frame conventions."
    ),
    expected_video=(
        "The asset's master joint sweeps slowly back and forth across its "
        "range; the follower joint(s) move synchronously with proportional "
        "magnitude. For a parallel-jaw gripper, the gripper visibly opens "
        "and closes through several cycles. A follower that doesn't move "
        "at all, or moves at a wildly different magnitude than the master, "
        "indicates a broken mimic constraint."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=mim_phase.get_defaults(),
    max_duration=300,
)
async def test_mimic_joint(ctx):
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await mim_phase.run_mimic_joint(ctx, robot, scene_info, ctx.config)
