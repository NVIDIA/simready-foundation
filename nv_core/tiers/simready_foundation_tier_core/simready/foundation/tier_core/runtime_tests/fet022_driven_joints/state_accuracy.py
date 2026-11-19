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

"""FET022 State Accuracy: per-joint commanded-position + reporting sanity."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.articulation_phases import state_accuracy as sta_phase

# Metadata for the independently owned Core behavioral implementation.
STATE_ACCURACY_KWARGS = {
    "description": (
        "Commands eligible joints through configured waypoint sequences "
        "and compares sampled joint readback with legal waypoint goals using "
        "position_tolerance_deg, under zero gravity. Actual issued commands "
        "are recorded separately; each complete ramp issues its final goal "
        "before settling. Interrupted ramps retain only commands actually issued. "
        "This is command/readback response evidence, "
        "not an independent calibration of state reporting or a diagnosis "
        "of controller gains."
    ),
    "expected_video": (
        "Each tested joint visits the configured waypoints in sequence. "
        "Compare settling and tracking with the sampled waypoint errors. "
        "Drift, oscillation or failure to reach a goal may require investigation "
        "of test setup, importer/units, controller settings or the asset; "
        "the clip alone does not isolate inadequate stiffness or damping."
    ),
    "version": "1.2.9",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": sta_phase.get_defaults(),
    "max_duration": 600,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.PhysX.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.PhysX.0-2-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-1-0", "version": "*"},
        {"id": "FET022_DrivenJoints.Isaac.0-2-0", "version": "*"},
    ],
    name="state_accuracy",
    **STATE_ACCURACY_KWARGS,
)
async def test_state_accuracy(ctx):
    await run_state_accuracy(ctx)


async def run_state_accuracy(ctx):
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    # State accuracy measures drive command tracking, not gravity
    # compensation. Keep this gravity exception local to the state-accuracy
    # test instead of changing the other articulation and gripper tests.
    robot, scene_info = await setup_robot_test_scene(
        ctx,
        config_overrides={"gravity_magnitude": 0.0},
    )

    await sta_phase.run_state_accuracy(ctx, robot, scene_info, ctx.config)
