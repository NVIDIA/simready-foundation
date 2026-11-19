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


"""Newton flat-ground sampled stability, qualified after proximity and overlap.

Uses the same drop fixture and defaults as ground_drop_newton. A complete
post-proximity AABB center/corner hold must satisfy the existing tolerance
before its deadline. This is not an angular/linear-velocity measurement or a
claim of continuous stability; symmetric rotation may preserve the box.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_newton.runtime_tests.fet003_physics._ground_trial import (
    encode_ground_video,
    report_ground_result,
    run_ground_trial,
)

GROUND_STABILITY_KWARGS = {
    "description": (
        "Uses the qualified flat-ground drop fixture and requires a complete post-proximity sampled "
        "AABB center and min/max corner hold within rest_tolerance (default 0.02 stage units), "
        "for rest_detection_hold_seconds (2 seconds), before rest_detection_max_seconds "
        "(8 seconds after proximity). Missing proximity or excessive allowed-overlap breaches "
        "cannot certify stability. Every rest-window sample must remain inside the configured "
        "floor-proximity/allowed-overlap band. These are geometry proxies, not measured velocity or contact."
    ),
    "expected_video": (
        "The asset falls toward the flat blue floor, may bounce or tumble, and either satisfies "
        "the post-proximity sampled-rest hold or remains visibly moving through the deadline. "
        "The camera follows; stable sampled bounds do not prove zero angular velocity."
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
    features=[{"id": "FET003_RigidBody.Newton.0-1-0", "version": "*"}],
    name="ground_stability_newton",
    **GROUND_STABILITY_KWARGS,
)
async def test_ground_stability_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_ground_stability(ctx)


async def run_ground_stability(ctx):
    """Require a qualified complete rest hold after the ground-proximity event."""
    state = await run_ground_trial(ctx, label="ground_stability", require_rest=True)
    encode_ground_video(ctx, state, "ground_stability")
    report_ground_result(ctx, state, label="ground_stability", require_rest=True)
