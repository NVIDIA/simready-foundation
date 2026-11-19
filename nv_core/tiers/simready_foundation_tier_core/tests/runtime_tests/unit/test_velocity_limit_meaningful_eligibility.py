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

import math
from importlib import import_module
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    motion_utils,
    velocity_limit,
)

_SENTINEL = float(np.finfo(np.float32).max)


def _robot(lower=-1.0, upper=1.0, velocity=1.0):
    return SimpleNamespace(
        dof_names=["joint"],
        dof_count=1,
        get_joint_position_limits=lambda: (np.array([lower]), np.array([upper])),
        get_joint_velocity_limits=lambda: np.array([velocity]),
    )


@pytest.mark.parametrize("value", [_SENTINEL, 3.402823e38, math.inf, math.nan, 0.0, -1.0])
def test_unlimited_or_absent_native_ceiling_does_not_qualify(value):
    assert velocity_limit.find_joints_with_velocity_limits(_robot(velocity=value)) == []


@pytest.mark.parametrize("value", [_SENTINEL, 3.402823e38])
def test_meaningful_authored_fallback_is_kept_without_unlimited_native_provenance(value):
    selected = velocity_limit.find_joints_with_velocity_limits(_robot(velocity=value), np.array([0.5]))
    assert selected[0]["max_velocity"] == 0.5
    assert selected[0]["max_velocity_source"] == "usd"


def test_meaningful_native_fallback_is_kept_without_unlimited_usd_provenance():
    selected = velocity_limit.find_joints_with_velocity_limits(_robot(), np.array([_SENTINEL]))
    assert selected[0]["max_velocity"] == 1.0
    assert selected[0]["max_velocity_source"] == "dof"


def test_large_finite_rating_not_near_sdk_sentinel_remains_meaningful():
    selected = velocity_limit.find_joints_with_velocity_limits(_robot(velocity=1e30))
    assert selected[0]["max_velocity"] == 1e30


def test_present_native_ceiling_getter_error_is_not_swallowed():
    robot = _robot()

    def failed_getter():
        raise RuntimeError("required native ceiling API failed")

    robot.get_joint_velocity_limits = failed_getter
    with pytest.raises(RuntimeError, match="native ceiling API failed"):
        velocity_limit.find_joints_with_velocity_limits(robot)


@pytest.mark.parametrize(
    "lo,hi",
    [
        (-_SENTINEL, _SENTINEL),
        (-3.402823e38, 3.402823e38),
        (-_SENTINEL, 1),
        (-1, _SENTINEL),
        (-math.inf, 1),
        (-1, math.inf),
        (1, -1),
        (1, 1),
        (-math.nan, 1),
        (-1e308, 1e308),
    ],
)
def test_unsafe_or_unbounded_travel_never_qualifies_or_generates_target(lo, hi):
    assert velocity_limit.find_joints_with_velocity_limits(_robot(lo, hi)) == []
    with pytest.raises(ValueError):
        velocity_limit.compute_velocity_test_target(0.0, lo, hi)


@pytest.mark.parametrize("current", [True, "0", math.inf, math.nan])
def test_target_requires_finite_real_current_state(current):
    with pytest.raises(ValueError):
        velocity_limit.compute_velocity_test_target(current, -1.0, 1.0)


@pytest.mark.parametrize("current,expected", [(-0.5, 0.9), (0.5, -0.9)])
def test_eligible_five_percent_target_policy_unchanged(current, expected):
    assert velocity_limit.compute_velocity_test_target(current, -1.0, 1.0) == pytest.approx(expected)


@pytest.fixture
def schema(monkeypatch):
    import pxr

    monkeypatch.setattr(
        pxr,
        "PhysxSchema",
        SimpleNamespace(
            PhysxJointAPI=SimpleNamespace(
                Get=lambda stage, path: SimpleNamespace(
                    GetMaxJointVelocityAttr=lambda: stage.GetPrimAtPath(path).GetAttribute(
                        "physxJoint:maxJointVelocity"
                    )
                )
            )
        ),
        raising=False,
    )


@pytest.mark.parametrize("joint_type", [UsdPhysics.RevoluteJoint, UsdPhysics.PrismaticJoint])
@pytest.mark.parametrize("attribute_name", ["physxJoint:maxJointVelocity", "envelope"])
@pytest.mark.parametrize("value", [_SENTINEL, 3.402823e38])
def test_raw_authored_unlimited_ceiling_is_rejected_before_unit_conversion(schema, joint_type, attribute_name, value):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    joint = joint_type.Define(stage, "/Robot/joint").GetPrim()
    if attribute_name == "envelope":
        axis = "angular" if joint_type is UsdPhysics.RevoluteJoint else "linear"
        attribute_name = "physxDrivePerformanceEnvelope:%s:maxActuatorVelocity" % axis
    joint.CreateAttribute(attribute_name, Sdf.ValueTypeNames.Float).Set(value)
    strict = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root, reject_unlimited=True)
    assert np.isnan(strict[0])
    # Other procedures retain the legacy default until their owner revises it.
    legacy = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root)
    assert math.isfinite(legacy[0]) and legacy[0] > 0


@pytest.mark.parametrize(
    "joint_type,mismatched_axis", [(UsdPhysics.RevoluteJoint, "linear"), (UsdPhysics.PrismaticJoint, "angular")]
)
def test_mismatched_envelope_axis_cannot_authorize_qualified_vel_input(schema, joint_type, mismatched_axis):
    stage = Usd.Stage.CreateInMemory()
    joint = joint_type.Define(stage, "/Robot/joint").GetPrim()
    joint.CreateAttribute(
        "physxDrivePerformanceEnvelope:%s:maxActuatorVelocity" % mismatched_axis, Sdf.ValueTypeNames.Float
    ).Set(30.0)
    assert motion_utils._read_joint_max_velocity(joint, reject_unlimited=True) is None
    assert motion_utils._read_joint_max_velocity(joint) is not None


@pytest.mark.parametrize("second_has_cap", [True, False])
def test_duplicate_joint_basename_does_not_borrow_other_joint_cap(schema, second_has_cap):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    first = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/joints/joint").GetPrim()
    first.CreateAttribute("physxJoint:maxJointVelocity", Sdf.ValueTypeNames.Float).Set(180.0)
    second = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/other/joint").GetPrim()
    if second_has_cap:
        second.CreateAttribute("physxJoint:maxJointVelocity", Sdf.ValueTypeNames.Float).Set(90.0)
    values = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root, reject_unlimited=True)
    assert np.isnan(values[0])
    assert velocity_limit.find_joints_with_velocity_limits(_robot(velocity=math.nan), values) == []


def test_joint_duplicates_inside_instance_proxies_cannot_authorize_vel_cap(schema):
    stage = Usd.Stage.CreateInMemory()
    prototype = stage.DefinePrim("/Prototype", "Xform")
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Prototype/joint").GetPrim()
    joint.CreateAttribute("physxJoint:maxJointVelocity", Sdf.ValueTypeNames.Float).Set(180.0)
    root = stage.DefinePrim("/Robot", "Xform")
    for name in ("first", "second"):
        instance = stage.DefinePrim("/Robot/" + name, "Xform")
        instance.GetReferences().AddInternalReference(prototype.GetPath())
        instance.SetInstanceable(True)
    values = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root, reject_unlimited=True)
    assert np.isnan(values[0])


@pytest.mark.parametrize(
    "joint_type,authored,expected",
    [
        (UsdPhysics.RevoluteJoint, 180.0, math.pi),
        (UsdPhysics.PrismaticJoint, 1.25, 1.25),
    ],
)
def test_qualified_authored_mapping_retains_existing_conversion(schema, joint_type, authored, expected):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    joint = joint_type.Define(stage, "/Robot/joint").GetPrim()
    joint.CreateAttribute("physxJoint:maxJointVelocity", Sdf.ValueTypeNames.Float).Set(authored)
    values = motion_utils.resolve_usd_max_velocities(stage, "/Robot", ["joint"], root, root, reject_unlimited=True)
    assert values[0] == pytest.approx(expected)


def _phase_fixture(monkeypatch, *, ineligible=0, all_ineligible=False):
    names = ["good"] + ["free_%d" % i for i in range(ineligible)]
    count = len(names)
    commands, applied, skipped, failures, warnings, steps = [], [], [], [], [], []
    metrics = {}
    velocity = _SENTINEL if all_ineligible else 1.0
    robot = SimpleNamespace(
        dof_names=names,
        dof_count=count,
        prim_path="/Robot",
        get_joint_position_limits=lambda: (
            np.array([-1.0] + [-_SENTINEL] * ineligible),
            np.array([1.0] + [_SENTINEL] * ineligible),
        ),
        get_joint_velocity_limits=lambda: np.array([velocity] + [1.0] * ineligible),
        get_joint_positions=lambda: np.zeros(count, dtype=int),
        get_joint_velocities=lambda: np.full(count, 0.2),
        set_joint_position_targets=lambda values: commands.append(values.copy()),
        apply_velocity_limits_to_tensor_view=lambda values: applied.append(values.copy()) or True,
    )

    async def step_one():
        steps.append(1)

    async def capture_frame(**kwargs):
        return None

    ctx = SimpleNamespace(
        step_one=step_one,
        capture_frame=capture_frame,
        add_metric=lambda key, value: metrics.update({key: value}),
        warn=warnings.append,
        fail=failures.append,
        skip=skipped.append,
        step=lambda message: None,
        log=lambda message: None,
        scene=SimpleNamespace(update_camera_follow=lambda **kwargs: None),
    )
    monkeypatch.setattr(velocity_limit, "resolve_usd_max_velocities", lambda **kwargs: np.full(count, np.nan))
    monkeypatch.setattr(velocity_limit, "compute_world_aligned_bbox", lambda prim: None)
    monkeypatch.setattr(velocity_limit, "check_bbox_explode", lambda *args: None)
    return ctx, robot, commands, applied, skipped, failures, warnings, steps, metrics


@pytest.mark.asyncio
async def test_no_meaningful_ceiling_is_execution_gap_before_application_commands_or_ticks(monkeypatch):
    ctx, robot, commands, applied, skipped, failures, warnings, steps, metrics = _phase_fixture(
        monkeypatch, all_ineligible=True
    )
    with pytest.raises(RuntimeError, match="bounded travel"):
        await velocity_limit.run_velocity_limit(ctx, robot, {}, {"settle_seconds": 0})
    assert not skipped
    assert not commands and not applied and not steps and not failures
    assert metrics["vel_joints_with_limits"] == 0 and metrics["vel_joints_not_evaluated"] == 1
    assert "vel_joints_passed" not in metrics
    assert "only 0 eligible joint" in warnings[0]


@pytest.mark.asyncio
async def test_partial_joint_coverage_is_visible_bounded_and_preserves_real_float_target(monkeypatch):
    ctx, robot, commands, applied, skipped, failures, warnings, steps, metrics = _phase_fixture(
        monkeypatch, ineligible=70
    )
    await velocity_limit.run_velocity_limit(
        ctx, robot, {}, {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 5}
    )
    assert not skipped and not failures
    assert len(commands) == 1 and commands[0][0] == pytest.approx(0.9)
    assert np.all(commands[0][1:] == 0) and len(steps) == 20
    assert len(applied) == 1 and np.all(np.isnan(applied[0][1:]))
    assert metrics["vel_joints_passed"] == 1 and metrics["vel_joints_with_limits"] == 1
    assert metrics["vel_joints_not_evaluated"] == 70
    assert len(metrics["vel_joint_eligibility_omissions"]) == 64
    assert metrics["vel_joint_eligibility_omissions_truncated"] == 6
    assert len(warnings) == 1 and "only 1 eligible joint" in warnings[0]


def test_registration_reports_eligibility_fix_procedure_version():
    registration = import_module("simready.foundation.tier_core.runtime_tests.fet022_driven_joints.velocity_limit")
    assert registration.VELOCITY_LIMIT_KWARGS["version"] == "1.1.11"
