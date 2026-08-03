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
"""FET022 IK Target Reach: per-joint commanded-position + reporting sanity."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import ik_target_reach as ik_phase


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="ik_target_reach",
    description=(
        "Generates a Fibonacci-sphere distribution of end-effector target "
        "poses around home (default 5 in-reach targets); uses Lula's IK "
        "solver to compute joint configurations; commands the asset and "
        "verifies the EE reaches each target within position tolerance "
        "(default 5 cm) and orientation tolerance (default 10°). Skips "
        "cleanly when no Lula descriptor is available for the asset."
    ),
    expected_video=(
        "The robot's end-effector visits a sequence of target poses "
        "distributed around its home position — like points sampled on a "
        "sphere. At each target, the EE pauses briefly, then moves to the "
        "next. A pass shows the EE reaching every commanded target; "
        "missed targets, jittery motion, or stuck-at-home behavior all "
        "indicate IK or drive failure."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=ik_phase.get_defaults(),
    max_duration=600,
)
async def test_ik_target_reach(ctx):
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await ik_phase.run_ik_target_reach(ctx, robot, scene_info, ctx.config)
