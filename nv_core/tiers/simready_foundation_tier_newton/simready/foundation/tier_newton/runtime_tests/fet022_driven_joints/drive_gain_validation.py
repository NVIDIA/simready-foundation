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

"""FET022 Drive Gain Validation: step-response quality (overshoot/settle/oscillations)."""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    drive_gain_validation as dgv_phase,
)

# Newton-owned test policy and decorator metadata.
DRIVE_GAIN_VALIDATION_KWARGS = {
    "description": (
        "Commands configurable joint steps and samples the existing position "
        "and velocity response over the observation window. Reports overshoot, "
        "settling and velocity-sign-change criteria. With default step_fatal=False, "
        "finite response criterion failures are warnings and may accompany PASS; "
        "step_fatal=True makes them fail. Required unavailable/nonfinite views "
        "are execution errors. These observations do not isolate a PD-gain cause."
    ),
    "expected_video": (
        "Each tested joint executes a discrete step and may overshoot or "
        "oscillate before settling. Compare the clip with sampled response "
        "metrics and the configured step_fatal policy; visible ringing or "
        "failure to settle is not automatically an overall FAIL under defaults. "
        "Investigate setup, importer/units, controller and asset causes separately."
    ),
    "version": "1.1.10",
    "engine": {"tags": ["kit"], "version": ">=2024.2.0"},
    "config_defaults": dgv_phase.get_defaults(),
    "max_duration": 600,
}


@test(
    features=[
        {"id": "FET022_DrivenJoints.Newton.0-1-0", "version": "*"},
    ],
    name="drive_gain_validation_newton",
    **DRIVE_GAIN_VALIDATION_KWARGS,
)
async def test_drive_gain_validation_newton(ctx):
    from simready.foundation.tier_newton.runtime_tests.runtime_guard import require_newton_backend

    require_newton_backend()
    await run_drive_gain_validation(ctx)


async def run_drive_gain_validation(ctx):
    """Measure eligible joints' step responses under the configured step_fatal policy."""
    # Lazy imports: Kit/USD modules are not available in pure-Python test env.
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(ctx)
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await dgv_phase.run_drive_gain_validation(ctx, robot, scene_info, ctx.config)
