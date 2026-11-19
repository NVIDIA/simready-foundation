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

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.articulation_phases import effort_limit as eff_phase

# Core-owned PhysX test policy and decorator metadata.
EFFORT_LIMIT_KWARGS = {
    "description": (
        "For each non-passive, non-mimic-follower joint with position or "
        "effort limits, applies a configurable external force "
        "(default 10 N) at the live child-body center of mass in 12 "
        "world directions and records "
        "joint position over time. Checks for position-range overrun "
        "beyond the configured allowance or sampled bounding-box explosion. "
        "Missing/nonfinite live COM or position readbacks, ambiguous body "
        "mapping, or failed force submission "
        "are execution/setup errors, not asset-response failures. "
        "Motion inside the allowed range "
        "can pass; actuator effort, pose holding, and effort-limit "
        "enforcement are not measured by this probe."
    ),
    "expected_video": (
        "External world-frame forces probe each tested child's live body "
        "center of mass in "
        "12 directions; an optional arrow visualizes the issued force. "
        "Authored base constraints remain in effect; a qualified standalone "
        "gripper may have a temporary world pin. No carrier is attached and "
        "a fixed base is not guaranteed. Joint motion may remain "
        "inside the allowed position range and still pass. Review any "
        "large displacement or instability alongside measured positions; "
        "the video does not establish an actuator effort rating."
    ),
    "version": "1.2.0",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": eff_phase.get_defaults(),
    "max_duration": 1200,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.PhysX.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.PhysX.0-2-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-2-0", "version": "*"},
    ],
    name="effort_limit",
    **EFFORT_LIMIT_KWARGS,
)
async def test_effort_limit(ctx):
    await run_effort_limit(ctx)


async def run_effort_limit(ctx):
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await eff_phase.run_effort_limit(ctx, robot, scene_info, ctx.config)
