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
"""FET022 Drive Gain Validation: step-response quality (overshoot/settle/oscillations)."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import (
    drive_gain_validation as dgv_phase,
)


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="drive_gain_validation",
    description=(
        "Step-response test: for each non-passive, non-mimic-follower "
        "joint, commands a 30° step (configurable) from current position "
        "and records position + velocity over 5 seconds. Asserts overshoot "
        "≤ 50% of step magnitude, settling time ≤ 5 s (within 5% of "
        "target sustained), and ≤ 20 velocity sign changes. Validates the "
        "drive's PD gains are tuned well enough to track commanded "
        "positions reliably, which is a precondition for state_accuracy "
        "and any trajectory test downstream."
    ),
    expected_video=(
        "Each tested joint executes a single discrete step — accelerates "
        "to the new target, may overshoot slightly, oscillates briefly "
        "around it (visible as small back-and-forth shaking), then "
        "settles. Stiff drives settle faster with less ringing; "
        "underdamped drives shake noticeably before settling. Excessive "
        "ringing or failure to settle inside the 5 s window is a fail."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dgv_phase.get_defaults(),
    max_duration=300,
)
async def test_drive_gain_validation(ctx):
    """Command step changes on each joint and assert step-response quality."""
    # Lazy imports: Kit/USD modules are not available in pure-Python test env.
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await dgv_phase.run_drive_gain_validation(ctx, robot, scene_info, ctx.config)
