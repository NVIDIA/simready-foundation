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


"""Newton flat-ground drop: qualified proximity and allowed AABB overlap.

Sampled rest controls the established observation schedule but not this verdict.
The independently required ground_stability_newton procedure evaluates settling.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_newton.runtime_tests.fet003_physics._ground_trial import (
    encode_ground_video,
    report_ground_result,
    run_ground_trial,
)

GROUND_DROP_KWARGS = {
    "description": (
        "Drops the asset above a collision-enabled ground plane and requires its live bounding-box "
        "lowest point to cross the proximity threshold while observed floor overlap stays within "
        "the configured allowance. The existing rest/deadline schedule bounds the observation; "
        "settling is assessed separately by ground_stability_newton. Distances are stage units. "
        "These proxies do not measure collision contact points or prove mass/inertia realism."
    ),
    "expected_video": (
        "The asset starts above a flat blue floor and falls under gravity. It may bounce, tumble "
        "or continue moving until the observation deadline. The follow camera and sampled AABB "
        "overlap allowance help interpretation; a drop PASS does not certify settling."
    ),
    "version": "4.0.2",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "max_duration": 600,
    "config_defaults": {
        "simulation_seconds": 10.0,
        "physics_fps": 240,
        "capture_fps": 15,
        "settle_frames": 5,
        "asset_load_timeout": 30,
        "drop_height_factor": 2.0,
        "minimum_drop_distance": 0.1,
        "floor_level": 0.0,
        "floor_margin": 0.1,
        "penetration_check_seconds": 1.0,
        "rest_tolerance": 0.02,
        "rest_detection_hold_seconds": 2.0,
        "rest_detection_max_seconds": 8.0,
        "simulate_after_result_seconds": 0.5,
    },
}


@test(
    features=[{"id": "FET003_RigidBody.Newton.0-1-0", "version": "*"}],
    name="ground_drop_newton",
    **GROUND_DROP_KWARGS,
)
async def test_ground_drop_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_ground_drop(ctx)


async def run_ground_drop(ctx):
    """Run the Newton-local fixture without requiring a rest outcome."""
    state = await run_ground_trial(ctx, label="ground_drop", require_rest=False)
    encode_ground_video(ctx, state, "ground_drop")
    report_ground_result(ctx, state, label="ground_drop", require_rest=False)
