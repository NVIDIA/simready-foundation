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

"""FET003 sampled ground drop, separate from the stability verdict.

The unchanged impact fixture places the asset above a collision-enabled blue
floor at two asset heights, preserving minimum free-fall clearance. PASS requires
an observed downward AABB proximity crossing and no sampled overlap beyond the
configured floor allowance. The previous rest/deadline/tail schedule is retained
to avoid shortening overlap coverage; settling is a diagnostic, not this verdict.
Ground stability is measured by the separate ground_stability procedure.

Lengths are stage units. AABB thresholds are not measured collider contacts or
penetration depths. Nominal observation time excludes rendering ticks; captures
are associations with observations, not exact frame timestamps. Setup, required
readback and cleanup errors are not completed asset behavioral failures.
"""

from simready.evaluate.core.decorator import test

GROUND_DROP_KWARGS = {
    "description": (
        "Drops the asset above a collision-enabled floor (default two asset heights). "
        "Requires a downward bounding-box proximity crossing and no sampled overlap "
        "below the configured floor allowance throughout the retained observation "
        "window. The rest/8-second post-proximity deadline and video tail retain the "
        "previous overlap coverage; rest is diagnostic only. Ground stability has "
        "its own verdict. Distances are stage units; no native contact depth, mass "
        "or inertia realism is established."
    ),
    "expected_video": (
        "The asset falls toward the flat blue floor and may rebound, tumble, slide "
        "or settle. The follow camera and clip end retain the former rest/deadline "
        "schedule. Continued motion alone does not fail ground drop; consult the "
        "separate ground stability result. Bounding-box overlap is not exact "
        "collider penetration, and follow-camera perspective can change apparent size."
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
    features=[
        {"id": "FET003_RigidBody.0-1-0", "version": "*"},
        {"id": "FET003_RigidBody.0-2-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-1-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-2-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-3-0", "version": "*"},
        {"id": "FET003_RigidBody.PhysX.0-4-0", "version": "*"},
    ],
    name="ground_drop",
    **GROUND_DROP_KWARGS,
)
async def test_ground_drop(ctx):
    await run_ground_drop(ctx)


async def run_ground_drop(ctx):
    """Evaluate proximity and allowed sampled overlap, not the rest criterion."""
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()
    from simready.foundation.tier_core.runtime_tests.fet003_physics._ground_trial import (
        report_ground_drop,
        run_ground_trial,
    )

    result = await run_ground_trial(ctx, "ground_drop")
    if result is not None:
        report_ground_drop(ctx, result)
