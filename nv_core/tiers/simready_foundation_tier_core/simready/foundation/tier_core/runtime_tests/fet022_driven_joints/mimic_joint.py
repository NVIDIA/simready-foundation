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
"""FET022 Mimic Joint: PhysX follower-target tracking."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.articulation_phases import mimic_joint as mim_phase

# Metadata for the independently owned Core behavioral implementation.
MIMIC_JOINT_KWARGS = {
    "description": (
        "For each detected mimic pair in the selected runtime variant, sweeps the "
        "reference (master) joint through its range and verifies the "
        "follower's motion magnitude matches |gear| × reference motion "
        "magnitude within gear_ratio_tolerance (default 0.10). "
        "The sampled magnitude ratio determines the verdict; backend-normalized "
        "direction and rest-pose residuals are diagnostics only. A failure does not "
        "by itself establish whether the cause is asset, importer, solver or test setup."
    ),
    "expected_video": (
        "The asset's master joint sweeps slowly back and forth across its "
        "range; the follower joint(s) move synchronously with proportional "
        "magnitude. For a parallel-jaw gripper, the gripper visibly opens "
        "and closes during the outbound/return sweep. A follower that doesn't move "
        "at all, or moves at a wildly different magnitude than the master, "
        "requires investigation of the composed coupling, runtime support and test setup."
    ),
    "version": "1.1.11",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": mim_phase.get_defaults(),
    "max_duration": 600,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.PhysX.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.PhysX.0-2-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-2-0", "version": "*"},
    ],
    name="mimic_joint",
    **MIMIC_JOINT_KWARGS,
)
async def test_mimic_joint(ctx):
    await run_mimic_joint(ctx)


async def run_mimic_joint(ctx):
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)

    await mim_phase.run_mimic_joint(ctx, robot, scene_info, ctx.config)
