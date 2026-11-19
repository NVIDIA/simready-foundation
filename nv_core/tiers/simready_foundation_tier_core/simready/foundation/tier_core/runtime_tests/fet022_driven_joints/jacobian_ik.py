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

"""Core FET022 Jacobian search, dynamic playback and sampled end-effector checks."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.articulation_phases import jacobian_ik as jik_phase

# Metadata for the independently owned Core behavioral implementation.
JACOBIAN_IK_KWARGS = {
    "description": (
        "Attempts FK-sampled targets with an in-house damped-least-squares "
        "Jacobian IK solver and dynamic playback. A pass meets the configured "
        "sampled success fraction (default 40%), combining final live EE position "
        "error with solver orientation error. Final live orientation is not "
        "independently certified. Requires a discoverable EE link, but no Lula "
        "descriptor. Skips qualified standalone grippers; an arm with an "
        "attached gripper can remain applicable."
    ),
    "expected_video": (
        "The robot attempts FK-sampled targets and plays back accepted solutions. "
        "Review solver status and final position errors alongside joint traces. "
        "The default 40% minimum allows failed targets even in a passing run; "
        "a pass is neither an every-target nor a majority-success guarantee."
    ),
    "version": "1.4.12",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": jik_phase.get_defaults(),
    "max_duration": 2400,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.PhysX.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.PhysX.0-2-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-2-0", "version": "*"},
    ],
    name="jacobian_ik",
    **JACOBIAN_IK_KWARGS,
)
async def test_jacobian_ik(ctx):
    await run_jacobian_ik(ctx)


async def run_jacobian_ik(ctx):
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    jik_phase.validate_phase_config(ctx.config, "jacobian_ik")
    jik_phase.validate_search_budget(ctx.config)

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await jik_phase.run_jacobian_ik(ctx, robot, scene_info, ctx.config)
