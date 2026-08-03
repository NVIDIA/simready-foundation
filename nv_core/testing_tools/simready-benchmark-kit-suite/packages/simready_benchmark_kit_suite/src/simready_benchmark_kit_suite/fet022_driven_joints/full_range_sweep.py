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
"""FET022 Full Range Sweep: drive every joint through max -> min -> zero."""
from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.articulation_phases import (
    full_range_sweep as frs_phase,
)


@test(
    features=[
        {"id": "FET022_DRIVEN_JOINTS_PHYSX", "version": ">=0.1.0"},
        {"id": "FET022_DRIVEN_JOINTS_ISAAC", "version": ">=0.1.0"},
    ],
    name="full_range_sweep",
    description=(
        "Drives each non-passive, non-mimic-follower joint through its "
        "full authored position range (lower → upper → home) one at a "
        "time. Verifies the joint reaches both commanded extremes within "
        "tolerance and that the asset's world-aligned bounding box does "
        "not explode (≤ bbox_explode_ratio × baseline, default 10×). "
        "Catches mis-authored joint limits, missing collision shapes, and "
        "drive failures that prevent the joint from completing the sweep."
    ),
    expected_video=(
        "Each tested joint moves one at a time, swinging slowly to its "
        "upper limit, then to its lower limit, then back to home. The "
        "asset's overall silhouette grows and shrinks as joints move "
        "through their range. A joint that doesn't move, an explosion of "
        "the silhouette (limbs flying apart due to broken collision), or "
        "stuck-at-mid-range behavior all indicate failure."
    ),
    version="1.0.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=frs_phase.get_defaults(),
    max_duration=600,
)
async def test_full_range_sweep(ctx):
    """Sweep every joint through max -> min -> zero and assert completion."""
    # Lazy imports: Kit/USD modules are not available in pure-Python test env.
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await frs_phase.run_full_range_sweep(ctx, robot, scene_info, ctx.config)
