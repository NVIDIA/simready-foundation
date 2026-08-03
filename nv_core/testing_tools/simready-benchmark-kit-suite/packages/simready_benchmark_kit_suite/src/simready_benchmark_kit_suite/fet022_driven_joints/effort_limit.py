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
"""FET022 Effort Limit: external-force break detection across 12 directions."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import effort_limit as eff_phase


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="effort_limit",
    description=(
        "For each non-passive, non-mimic-follower joint with position or "
        "effort limits, applies a configurable external force "
        "(default 10 N) at the joint's body in 12 directions and records "
        "joint position over time. Verifies the drive can either hold the "
        "joint within its commanded position under the applied force OR "
        "the joint breaks predictably toward a limit. Validates that the "
        "authored joint:maxEffort is enforced and the drive can resist "
        "realistic operating-range forces."
    ),
    expected_video=(
        "Each tested joint sees a sequence of arrows applied at its body "
        "from 12 directions. The joint either resists motion (holds its "
        "commanded position despite the visible force) or visibly breaks "
        "toward one of its limits. The robot/gripper base stays fixed "
        "(carrier pin). Spurious physics explosions or NaN-y motions "
        "indicate the test was applied to a broken joint configuration."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=eff_phase.get_defaults(),
    max_duration=600,
)
async def test_effort_limit(ctx):
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await eff_phase.run_effort_limit(ctx, robot, scene_info, ctx.config)
