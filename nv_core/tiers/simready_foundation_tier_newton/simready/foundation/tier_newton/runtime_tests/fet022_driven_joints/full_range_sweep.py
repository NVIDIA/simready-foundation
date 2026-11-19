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

"""Newton FET022 sweep of eligible joints through legal inset targets and rest."""

import time

from simready.evaluate.core.decorator import test
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    full_range_sweep as frs_phase,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.sweep_timing import (
    MAX_DURATION_SECONDS,
)

# Newton-owned test policy and decorator metadata.
FULL_RANGE_SWEEP_KWARGS = {
    "description": (
        "Drives each non-passive, non-mimic-follower joint through its "
        "configured inset upper and lower targets, then its zero/rest target, "
        "one at a time. Targets use sweep_margin_ratio (default 10%) and "
        "ramp duration respects resolved native or qualified authored speed hints "
        "with bounded simulation/wall budgets. "
        "Targets may be capped by max_sweep_range within the imported legal interval; "
        "they are not exact authored "
        "endpoints. With default fatal rest checks, at least half of each "
        "hold's observations must be within target tolerance. The sampled "
        "world-aligned bounding box is checked against a frozen qualified "
        "kinematic span with bbox_explode_ratio volume margin (default 10). "
        "If span qualification is unavailable, an explicitly labelled initial "
        "volume proxy is used when nondegenerate; a degenerate fallback omits "
        "that canary. A guard trip is a required safety interruption, not an "
        "asset-cause verdict. "
        "A pass is evidence for these commands and hold windows, not "
        "continuous tracking or a diagnosis of a specific asset defect."
    ),
    "expected_video": (
        "Each tested joint moves one at a time, swinging slowly to its "
        "configured inset upper target, then its inset lower target, "
        "then its zero/rest target. The "
        "asset's overall silhouette grows and shrinks as joints move "
        "through that sweep. Compare the quantitative hold and bounding-box "
        "checks with the clip; apparent smoothness or an exact endpoint "
        "touch is not an additional pass criterion."
    ),
    "version": "1.5.7",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": frs_phase.get_defaults(),
    "max_duration": MAX_DURATION_SECONDS,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.Newton.0-1-0", "version": "*"},
    ],
    name="full_range_sweep_newton",
    **FULL_RANGE_SWEEP_KWARGS,
)
async def test_full_range_sweep_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_full_range_sweep(ctx)


async def run_full_range_sweep(ctx):
    """Sweep eligible joints through legal inset targets, holds and zero/rest."""
    # Lazy imports: Kit/USD modules are not available in pure-Python test env.
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_scene import (
        setup_gripper_inspection_camera,
        setup_robot_test_scene,
    )

    started_at = time.monotonic()
    robot, scene_info = await setup_robot_test_scene(ctx)
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    setup_gripper_inspection_camera(ctx, scene_info, ctx.config)

    await frs_phase.run_full_range_sweep(ctx, robot, scene_info, ctx.config, started_at=started_at)
