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

"""Shared FET028 Gripper Close-Lift-Shake-Drop orchestration.

The sphere and cube registrations intentionally live in separate modules so
the planner, runner, and reporter retain two distinct result records. Both
tests bind to FET028_Gripper.Isaac.0-1-0; the framework's fail-dominates feature
aggregation therefore requires both shapes to pass.

Each runner exercises the same orchestration in
``articulation_phases.gripper_close_lift.run_gripper_close_lift``:
spawn the test object, open + close the gripper, lift it via a Z-axis
gantry attached by FixedJoint to the resolved physical articulation root, shake it to
perturb the grip, then open the gripper and evaluate the observed fall proxy.
"""

from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    gripper_close_lift as gcl_phase,
)


def _config_defaults_for_shape(shape):
    """Return registered defaults selecting one shape for this runner.

    Each runner re-uses the full default config from the articulation
    phase and selects one default ``config["shapes"]`` value. Explicit
    supported config overrides can select other configured trials.

    The cube runner uses the existing 85% of resolved payload and the sphere
    runner uses 50%, providing complementary configured contact geometries.
    Payload comes from gripper_maxPayload (legacy custom:maxPayload accepted)
    or the documented opening heuristic;
    that fallback is not a payload rating, and these proxies do not measure
    contact force or isolate material/drive causes.
    """
    cfg = gcl_phase.get_defaults()
    cfg["shapes"] = [shape]
    if shape == "sphere":
        cfg["payload_mass_fraction"] = 0.5
    return cfg


async def run(ctx):
    """Shared orchestration: scene setup, then the articulation-phase run.

    The shapes come from the effective ``ctx.config["shapes"]``; each
    registration defaults to one shape. ``run_gripper_close_lift`` performs its own
    gripper-site discovery and skips when the asset exposes no gripper
    site, so no separate phase-applicability gate is needed here (matching
    the current sibling-runner idiom, e.g. FET022).
    """
    from simready.foundation.tier_core.runtime_tests.engine_guard import require_physx_test_engine

    require_physx_test_engine()

    from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(
        ctx,
        config_overrides={
            # The phase presents the room floor itself. Avoid a second PhysX
            # ground plane in this PhysX-only procedure.
            "activate_ground_plane": False,
            "preorient_gripper_for_fet028": True,
        },
    )
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await gcl_phase.run_gripper_close_lift(ctx, robot, scene_info, ctx.config)


DESCRIPTION_TEMPLATE = (
    "By default, close + lift + shake + drop on a {shape} sized at 0.7 x "
    "declared maximum opening, with mass = {payload_pct}% of the resolved "
    "authored or heuristic maximum payload. Effective size, mass and hand "
    "controls are recorded in gripper_trial_controls. Evaluates configured "
    "retention, carrier-follow, shake and fall proxies, not measured contact "
    "force or a mechanical payload rating. Both sphere and cube bindings "
    "are required for FET028; a configured pass does not qualify an unrun shape."
)

EXPECTED_VIDEO_TEMPLATE = (
    "Default trial: {color} {shape} below the gripper. The gripper opens, "
    "gantry descends, closes on the {shape}, lifts 20cm, shakes ~2s, and "
    "opens again. Inspect observed carrier-follow and post-opening fall "
    "against the configured criteria. Overrides can change the trial; "
    "the clip may end at a failure and is not a native contact measurement."
)
