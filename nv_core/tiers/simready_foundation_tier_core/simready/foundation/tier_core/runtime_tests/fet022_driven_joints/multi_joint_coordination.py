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
"""FET022 Multi-Joint Coordination: sampled joint-space goal-band entries."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc_phase,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.coordination_timing import (
    CoordinationBudget,
    CoordinationTiming,
)

# Metadata for the independently owned Core behavioral implementation.
MULTI_JOINT_COORDINATION_KWARGS = {
    "description": (
        "Commands eligible joints together toward range-factor joint goals. "
        "Each joint must enter its goal tolerance band at least once within "
        "a shared velocity-aware ramp plus the configured post-ramp observation opportunity. The check remembers individual "
        "band entries; it does not require simultaneous final convergence "
        "or evaluate a Cartesian end-effector target or independent oscillation criterion."
    ),
    "expected_video": (
        "Eligible joints move together toward configured joint-space goals. "
        "Use the recorded goal-band entries and response traces to interpret "
        "the clip. A pass does not establish that all joints remain settled "
        "together or that an end-effector holds a particular Cartesian pose. "
        "Unexpected motion requires setup, controller/importer and asset triage."
    ),
    "version": "1.2.6",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": mjc_phase.get_defaults(),
    "max_duration": 3600,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.PhysX.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.PhysX.0-2-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-2-0", "version": "*"},
    ],
    name="multi_joint_coordination",
    **MULTI_JOINT_COORDINATION_KWARGS,
)
async def test_multi_joint_coordination(ctx):
    await run_multi_joint_coordination(ctx)


async def run_multi_joint_coordination(ctx):
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    import time

    started_at = time.monotonic()
    timing = CoordinationTiming(ctx.config)
    budget = CoordinationBudget(ctx.config, started_at=started_at)
    budget.reserve(timing.minimum_total_frames)

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await mjc_phase.run_multi_joint_coordination(ctx, robot, scene_info, ctx.config, budget=budget)
