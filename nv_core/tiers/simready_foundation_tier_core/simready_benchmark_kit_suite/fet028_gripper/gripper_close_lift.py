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
tests bind to FET_028_ISAAC; the framework's fail-dominates feature
aggregation therefore requires both shapes to pass.

Each runner exercises the same orchestration in
``articulation_phases.gripper_close_lift.run_gripper_close_lift``:
spawn the test object, open + close the gripper, lift it via a Z-axis
gantry attached by FixedJoint to the gripper base, shake the gantry to
perturb the grip, then open the gripper to verify release.
"""
from simready_benchmark_kit_suite.articulation_phases import (
    gripper_close_lift as gcl_phase,
)


def _config_defaults_for_shape(shape):
    """Return a config dict with ``shapes`` overridden to a single shape.

    Each runner re-uses the full default config from the articulation
    phase but pins ``config["shapes"]`` so
    ``run_gripper_close_lift``'s per-shape loop iterates exactly once.

    The cube runner uses the default 85% of rated payload (the
    standard FET028 stress test). The sphere runner uses 50%: a
    sphere only contacts the finger pads at a single point each
    (or a tiny area for soft pads), so its grip is friction-limited
    by a much smaller normal-force lever arm than a flat-faced cube
    of the same mass. Rated maxPayload is implicitly defined for
    flat / well-conforming geometry; testing a sphere at the same
    fraction would penalize geometrically-fine grippers for a
    contact-area limitation that isn't really about grip strength.
    """
    cfg = gcl_phase.get_defaults()
    cfg["shapes"] = [shape]
    if shape == "sphere":
        cfg["payload_mass_fraction"] = 0.5
    return cfg


async def run(ctx):
    """Shared orchestration: scene setup, then the articulation-phase run.

    The shape comes from ``ctx.config["shapes"]`` which each runner has
    pinned to a single value. ``run_gripper_close_lift`` performs its own
    gripper-site discovery and skips when the asset exposes no gripper
    site, so no separate phase-applicability gate is needed here (matching
    the current sibling-runner idiom, e.g. FET022).
    """
    from simready_benchmark_kit_suite.articulation_phases.robot_scene import (
        setup_robot_test_scene,
    )

    robot, scene_info = await setup_robot_test_scene(
        ctx,
        config_overrides={
            # The phase presents the room floor itself. Avoid a second PhysX
            # ground plane; Newton still receives its native builder ground
            # because prebuild_fet028_test_object is enabled below.
            "activate_ground_plane": False,
            "preorient_gripper_for_fet028": True,
            "prebuild_gripper_carrier": True,
            "prebuild_fet028_test_object": True,
        },
    )
    if robot is None:
        # setup_robot_test_scene already called ctx.precheck_failure.
        return

    await gcl_phase.run_gripper_close_lift(ctx, robot, scene_info, ctx.config)


DESCRIPTION_TEMPLATE = (
    "Close + lift + shake + drop on a {shape} sized at 0.7 x "
    "maxOpening, mass = {payload_pct}% x maxPayload. Both the sphere "
    "and cube tests must pass FET028."
)

EXPECTED_VIDEO_TEMPLATE = (
    "{color} {shape} on the floor below the gripper. Gripper opens, "
    "gantry descends, closes on the {shape}, lifts 20cm, shakes ~2s, "
    "drops. Pass: held through lift + shake, released on drop."
)
