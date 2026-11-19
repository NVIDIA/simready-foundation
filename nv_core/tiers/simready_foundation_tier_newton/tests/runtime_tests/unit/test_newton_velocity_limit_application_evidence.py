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

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    motion_history,
    velocity_limit,
)


class _HostileAcknowledgement:
    def __bool__(self):
        raise AssertionError("A helper acknowledgement must not be coerced to bool")


class _Robot:
    dof_names = ["hinge"]
    dof_count = 1
    prim_path = "/Robot"

    def __init__(self, acknowledgement, velocities=None):
        self.acknowledgement = acknowledgement
        self.velocities = velocities
        self.velocity_reads = 0
        self.commands = []
        self.applied_limits = []

    def get_joint_position_limits(self):
        return np.array([-1.0]), np.array([1.0])

    def get_joint_velocity_limits(self):
        return np.array([1.0])

    def get_joint_positions(self):
        # A stationary joint may pass the sampled speed criterion. VEL is
        # deliberately not an arrival test.
        return np.array([0.0])

    def get_joint_velocities(self):
        value = self.velocities[self.velocity_reads] if self.velocities is not None else 0.2
        self.velocity_reads += 1
        return np.array([value])

    def apply_velocity_limits_to_tensor_view(self, values):
        self.applied_limits.append(values.copy())
        if isinstance(self.acknowledgement, Exception):
            raise self.acknowledgement
        return self.acknowledgement

    def set_joint_position_targets(self, values):
        self.commands.append(values.copy())


class _Context:
    def __init__(self):
        self.steps = 0
        self.metrics = {}
        self.warnings = []
        self.failures = []
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)

    async def step_one(self):
        self.steps += 1

    async def capture_frame(self, **kwargs):
        return None

    def add_metric(self, name, value):
        self.metrics[name] = value

    def step(self, message):
        pass

    log = step

    def warn(self, message):
        self.warnings.append(message)

    def fail(self, message):
        self.failures.append(message)

    def skip(self, message):
        raise AssertionError("Unexpected skip: " + message)


class _Motion:
    def __init__(self, metadata):
        self.metadata = metadata
        self.samples = []
        self.finish_reasons = []

    def sample(self, values, time_s, phase):
        self.samples.append((dict(values), time_s, phase))

    def finish(self, reason):
        self.finish_reasons.append(reason)


def _phase_setup(monkeypatch):
    observers = []

    def make_observer(ctx, scene, joint_name, name, channels, metadata=None, **kwargs):
        observer = _Motion(dict(metadata or {}))
        observers.append(observer)
        return observer

    monkeypatch.setattr(motion_history, "make_joint_observer", make_observer)
    monkeypatch.setattr(velocity_limit, "resolve_usd_max_velocities", lambda **kwargs: np.array([0.75]))
    monkeypatch.setattr(velocity_limit, "compute_world_aligned_bbox", lambda prim: SimpleNamespace(volume=1.0))
    monkeypatch.setattr(velocity_limit, "check_bbox_explode", lambda *args: None)
    return observers


_CONFIG = {"physics_fps": 4, "capture_fps": 4, "settle_seconds": 0, "test_duration_seconds": 5}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "acknowledgement, expected",
    [
        (True, "reported_success"),
        (False, "not_applied"),
        (None, "unknown"),
        (1, "unknown"),
        ("accepted", "unknown"),
        (np.bool_(True), "unknown"),
        (np.array([True, False]), "unknown"),
        (_HostileAcknowledgement(), "unknown"),
    ],
    ids=["true", "false", "none", "integer", "string", "numpy-bool", "array", "hostile-bool"],
)
async def test_application_acknowledgement_is_separate_from_observed_verdict(monkeypatch, acknowledgement, expected):
    observers = _phase_setup(monkeypatch)
    ctx, robot = _Context(), _Robot(acknowledgement)
    await velocity_limit.run_velocity_limit(ctx, robot, {}, dict(_CONFIG))

    assert ctx.metrics["vel_velocity_limit_application"] == expected
    assert ctx.metrics["vel_velocity_limit_enforcement"] == "not_verified"
    assert ctx.metrics["vel_joints_passed"] == 1
    assert ctx.metrics["vel_joints_failed"] == 0
    assert not ctx.failures
    assert len(ctx.warnings) == (0 if expected == "reported_success" else 1)
    assert ctx.steps == 20 and robot.velocity_reads == 20
    assert len(robot.commands) == 1
    assert robot.commands[0][0] == pytest.approx(0.9)
    assert robot.applied_limits[0][0] == pytest.approx(0.75)
    assert len(observers) == 1
    observer = observers[0]
    assert observer.metadata["vel_velocity_limit_application"] == expected
    assert observer.metadata["vel_velocity_limit_enforcement"] == "not_verified"
    assert observer.metadata["limit_source"] == "dof_or_usd_min"
    assert len(observer.samples) == 20
    assert all(sample[0]["speed_limit"] == 0.75 for sample in observer.samples)
    assert observer.finish_reasons == ["step_budget_exhausted"]


@pytest.mark.asyncio
async def test_reported_success_cannot_override_observed_speed_violation(monkeypatch):
    observers = _phase_setup(monkeypatch)
    ctx, robot = _Context(), _Robot(True, velocities=[1.0] * 20)
    await velocity_limit.run_velocity_limit(ctx, robot, {}, dict(_CONFIG))

    assert ctx.metrics["vel_velocity_limit_application"] == "reported_success"
    assert ctx.metrics["vel_velocity_limit_enforcement"] == "not_verified"
    assert ctx.metrics["vel_joints_passed"] == 0
    assert ctx.metrics["vel_joints_failed"] == 1
    assert len(ctx.failures) == 1
    assert observers[0].metadata["vel_velocity_limit_enforcement"] == "not_verified"


@pytest.mark.asyncio
async def test_application_error_propagates_before_motion_or_verdict(monkeypatch):
    observers = _phase_setup(monkeypatch)
    ctx, robot = _Context(), _Robot(RuntimeError("application view unavailable"))
    config = dict(_CONFIG, settle_seconds=1)
    with pytest.raises(RuntimeError, match="application view unavailable"):
        await velocity_limit.run_velocity_limit(ctx, robot, {}, config)

    assert ctx.steps == 0
    assert not robot.commands and not observers
    assert not ctx.failures and not ctx.warnings
    assert "vel_joints_passed" not in ctx.metrics
    assert "vel_velocity_limit_application" not in ctx.metrics
    assert "vel_velocity_limit_enforcement" not in ctx.metrics


@pytest.mark.asyncio
async def test_unapplied_limit_preserves_existing_startup_exclusion(monkeypatch):
    _phase_setup(monkeypatch)
    ctx, robot = _Context(), _Robot(False, velocities=[10.0] * 5 + [0.2] * 15)
    await velocity_limit.run_velocity_limit(ctx, robot, {}, dict(_CONFIG))

    assert ctx.metrics["vel_joints_passed"] == 1 and not ctx.failures
    assert ctx.metrics["vel_velocity_limit_application"] == "not_applied"
    assert len(ctx.warnings) == 1
    assert "physical hard-cap enforcement is not verified" in ctx.warnings[0]


@pytest.mark.parametrize("readback", [[1.0], [1.0, np.nan], [[1.0, 1.0], [1.0, 1.0]]])
def test_real_handle_acknowledgement_requires_complete_requested_readback(readback):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )

    robot = RobotHandle(None, "/Robot", None, None)
    robot._articulation = SimpleNamespace(
        dof_names=["a", "b"],
        set_max_joint_velocities=lambda values: None,
        get_max_joint_velocities=lambda: np.asarray(readback),
    )
    assert robot.apply_velocity_limits_to_tensor_view(np.array([1.0, 1.0])) is False


@pytest.mark.asyncio
async def test_real_handle_readback_error_reaches_velocity_consumer_before_verdict(monkeypatch):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import (
        RobotHandle,
    )

    _phase_setup(monkeypatch)
    primary = OSError("native readback unavailable")

    def readback():
        raise primary

    robot = _Robot(True)
    robot._articulation = SimpleNamespace(
        set_max_joint_velocities=lambda values: None, get_max_joint_velocities=readback
    )
    robot.apply_velocity_limits_to_tensor_view = lambda values: RobotHandle.apply_velocity_limits_to_tensor_view(
        robot, values
    )
    ctx = _Context()
    with pytest.raises(OSError) as caught:
        await velocity_limit.run_velocity_limit(ctx, robot, {}, dict(_CONFIG))
    assert caught.value is primary
    assert ctx.steps == 0 and not robot.commands and not ctx.failures
    assert "vel_joints_passed" not in ctx.metrics


@pytest.mark.parametrize("forwarding", [False, True])
def test_independent_newton_control_ownership_keeps_qualified_loop_axes(forwarding):
    from pxr import Usd, UsdGeom, UsdPhysics
    from simready.foundation.tier_newton.runtime_tests.articulation_phases._independent_dofs import (
        control_ownership,
    )

    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    for name in ("base", "a", "b"):
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Asset/" + name).GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Asset/base"))
    for name, a, b in (("driver", "base", "a"), ("passive", "a", "b"), ("closure", "base", "b")):
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Joints/" + name)
        for index, body in enumerate((a, b)):
            path = "/Asset/" + body
            if forwarding:
                relation = asset.CreateRelationship("to_" + name + str(index))
                relation.SetTargets([path])
                path = relation.GetPath()
            joint.GetPrim().CreateRelationship("physics:body" + str(index)).SetTargets([path])
        if name == "driver":
            UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular").CreateStiffnessAttr(100)
        if name == "closure":
            joint.CreateExcludeFromArticulationAttr(True)
    names = ["/Asset/Joints/driver:0", "/Asset/Joints/passive:0", "/Asset/Joints/passive:1"]
    assert control_ownership(stage, asset, "/Asset/base", names)[2] == {1, 2}
