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

"""Core FET022 Lula target solving with sampled live end-effector position checks."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach as ik_phase,
)

# Metadata for the independently owned Core behavioral implementation.
IK_TARGET_REACH_KWARGS = {
    "description": (
        "Attempts Fibonacci-sphere targets with Lula IK and dynamic playback "
        "(default 5 in-reach samples). A pass meets the configured sampled "
        "success fraction (default 50%) using final live EE position error "
        "(default tolerance 2 cm). Orientation tolerance is a solver input, "
        "not a final live orientation guarantee. Failed targets remain visible. "
        "Skips qualified standalone grippers. Missing a Lula descriptor or required "
        "robot-base/reach geometry leaves the test unassessed (NO VERDICT)."
    ),
    "expected_video": (
        "The robot attempts sampled targets and plays back accepted solutions. "
        "Compare per-target status, live EE position error and joint traces with "
        "video. A pass may contain failed targets and does not certify every "
        "target, full-workspace reachability or final live orientation."
    ),
    "version": "1.2.9",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": ik_phase.get_defaults(),
    "max_duration": 1200,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.PhysX.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.PhysX.0-2-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-2-0", "version": "*"},
    ],
    name="ik_target_reach",
    **IK_TARGET_REACH_KWARGS,
)
async def test_ik_target_reach(ctx):
    await run_ik_target_reach(ctx)


async def run_ik_target_reach(ctx):
    from simready.foundation.tier_core.runtime_tests.engine_guard import (
        require_physx_test_engine,
    )

    require_physx_test_engine()

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await ik_phase.run_ik_target_reach(ctx, robot, scene_info, ctx.config)
