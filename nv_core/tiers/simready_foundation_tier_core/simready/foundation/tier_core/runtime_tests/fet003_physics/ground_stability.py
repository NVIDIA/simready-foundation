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

"""FET003 sampled ground stability following the qualified drop fixture.

Uses the same blue floor, impact placement, material, rates and allowances as
ground_drop. A rest window must consist entirely of post-proximity live AABB
observations. Within eight nominal seconds after proximity, both centre distance
and min/max corner variation must stay within 0.02 stage units for the configured
two-second sample window. At least two samples are required; midair stillness,
invalid bounds, an insufficient observation budget and overdue video-tail rest
cannot qualify. A sampled overlap breach or absent proximity fails prerequisites.

This is sampled geometric rest, not measured linear/angular velocity, continuous
stability proof or a mass/inertia diagnosis. Symmetric rotation can preserve an
AABB. Setup/readback/cleanup errors remain distinct from behavioral failures.
"""

from simready.evaluate.core.decorator import test

GROUND_STABILITY_KWARGS = {
    "description": (
        "Uses the ground-drop impact fixture and measures a fully post-proximity "
        "rest window: sampled bounding-box centre distance and min/max corner "
        "variation must remain within rest_tolerance (default 0.02 stage units) "
        "for rest_detection_hold_seconds (2 seconds), at or before the configured "
        "8-second post-proximity deadline. Requires valid proximity/allowed-overlap "
        "prerequisites; every rest-window sample must remain inside the configured "
        "floor-proximity/allowed-overlap band. This is not a velocity measurement, exact-contact check "
        "or proof of correct mass/inertia; symmetric rotation can preserve an AABB."
    ),
    "expected_video": (
        "The asset falls toward the flat blue floor, may rebound or tumble, then "
        "either satisfies the sampled rest window or reaches its deadline. The "
        "camera follows the object. A short video tail follows the frozen result; "
        "rest achieved after the deadline does not turn the result into PASS."
    ),
    "version": "3.0.2",
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
    "enabled": True,
}


@test(
    features=[
        {"id": "FET003_RigidBody.0-1-0", "version": "*"},
        {"id": "FET003_RigidBody.0-2-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-1-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-2-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-3-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-4-0", "version": "*"},
    ],
    name="ground_stability",
    **GROUND_STABILITY_KWARGS,
)
async def test_ground_stability(ctx):
    await run_ground_stability(ctx)


async def run_ground_stability(ctx):
    """Evaluate qualified sampled rest independently of the drop verdict."""
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()
    from simready.foundation.tier_core.runtime_tests.fet003_physics._ground_trial import (
        report_ground_stability,
        run_ground_trial,
    )

    result = await run_ground_trial(ctx, "ground_stability", stability=True)
    if result is not None:
        report_ground_stability(ctx, result)
