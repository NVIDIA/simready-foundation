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

"""Newton FET022 external-force range-overrun and bounding-box checks."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    effort_limit as eff_phase,
)

# Newton-owned test policy and decorator metadata.
EFFORT_LIMIT_KWARGS = {
    "description": (
        "For each non-passive, non-mimic-follower joint with position or "
        "effort limits, applies a configurable external force "
        "(default 10 N) at the joint's body in 12 directions and records "
        "joint position over time. Checks for position-range overrun "
        "beyond the configured allowance or sampled bounding-box explosion. "
        "Missing/nonfinite required readbacks or failed force submission "
        "are execution/setup errors, not asset-response failures. "
        "Motion inside the allowed range "
        "can pass; actuator effort, pose holding, and effort-limit "
        "enforcement are not measured by this probe."
    ),
    "expected_video": (
        "External world-frame forces probe each tested child body in "
        "12 directions; an optional arrow visualizes the issued force. "
        "Base behavior follows authored constraints or conditional gripper "
        "pinning; no carrier is added. Joint motion may remain "
        "inside the allowed position range and still pass. Review any "
        "large displacement or instability alongside measured positions; "
        "the video does not establish an actuator effort rating."
    ),
    "version": "1.1.10",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": eff_phase.get_defaults(),
    "max_duration": 1200,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.Newton.0-1-0", "version": "*"},
    ],
    name="effort_limit_newton",
    **EFFORT_LIMIT_KWARGS,
)
async def test_effort_limit_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_effort_limit(ctx)


async def run_effort_limit(ctx):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await eff_phase.run_effort_limit(ctx, robot, scene_info, ctx.config)
