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

"""FET022 Velocity Limit: compare the evaluated response with resolved ceilings."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    velocity_limit as vel_phase,
)

# Newton-owned test policy and decorator metadata.
VELOCITY_LIMIT_KWARGS = {
    "description": (
        "Drives each non-passive, non-mimic-follower joint individually "
        "from rest to its commanded position; verifies measured velocity "
        "stays within the resolved runtime/USD comparison ceiling in the "
        "evaluated window (tolerance_percent, default 5%). The criterion "
        "excludes the first five observations when more than ten are "
        "collected; the window can end on consecutive near-zero velocities. "
        "A pass describes this response, not universal hard-cap enforcement "
        "under other commands, loads, or excluded startup steps."
    ),
    "expected_video": (
        "Each tested joint moves one at a time from rest toward an "
        "opposite-range target. One independent joint receives a new "
        "target per segment; other measured coordinates need not be motionless. "
        "Base behavior depends on authored constraints or conditional "
        "gripper pinning, not a carrier fixture. Use measured velocities and the resolved "
        "ceiling to judge the criterion; visual smoothness alone does not "
        "prove the ceiling is enforced."
    ),
    "version": "1.1.12",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": vel_phase.get_defaults(),
    "max_duration": 600,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.Newton.0-1-0", "version": "*"},
    ],
    name="velocity_limit_newton",
    **VELOCITY_LIMIT_KWARGS,
)
async def test_velocity_limit_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_velocity_limit(ctx)


async def run_velocity_limit(ctx):
    """Drive each eligible joint and compare its evaluated velocity window."""
    # Lazy imports: Kit/USD modules are not available in pure-Python test env.
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await vel_phase.run_velocity_limit(ctx, robot, scene_info, ctx.config)
