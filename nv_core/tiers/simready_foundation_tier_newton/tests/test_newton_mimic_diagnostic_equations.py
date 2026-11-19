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

"""Backend-aware mimic diagnostics without altered controls, verdicts or clocks."""

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    mimic_joint,
    motion_history,
)


class _History:
    def __init__(self, channels, metadata):
        self.channels = channels
        self.metadata = metadata
        self.samples = []
        self.reason = None

    def sample(self, time_s, values, **kwargs):
        self.samples.append((time_s, dict(values), kwargs))

    def finish(self, reason):
        self.reason = reason

    def mark_partial(self, reason):
        raise AssertionError("The complete mock readback should not become partial")


class _Robot:
    def __init__(self, multiplier, absolute_offset):
        self.dof_names = ["reference", "follower"]
        self.prim_path = "/Robot"
        self.multiplier = multiplier
        self.absolute_offset = absolute_offset
        self.positions = np.array([0.2, multiplier * 0.2 + absolute_offset])
        self.initial_positions = self.positions.copy()
        self.target = self.positions.copy()
        self.commands = []
        self.reads = 0

    def get_joint_positions(self):
        self.reads += 1
        return self.positions.copy()

    def get_joint_position_limits(self):
        return np.zeros(2), np.ones(2)

    def set_joint_position_targets(self, target):
        self.target = target.copy()
        self.commands.append(target.copy())

    def set_joint_position_targets_indexed(self, values, indices):
        assert list(indices) == [0]
        self.target[indices] = values
        self.commands.append(self.target.copy())

    def set_joint_positions_indexed(self, values, indices):
        self.positions[indices] = values

    def set_joint_velocities_indexed(self, values, indices):
        raise AssertionError("MIM does not write velocities")


class _Context:
    def __init__(self, robot, recording):
        self.robot = robot
        self.steps = 0
        self.histories = {}
        self.metrics = {}
        self.warnings = []
        self.failures = []
        self.scene = SimpleNamespace(update_camera_follow=lambda **kwargs: None)
        if not recording:
            self.begin_motion_history = None

    def begin_motion_history(self, name, channels, metadata=None):
        self.histories[name] = _History(channels, metadata)
        return self.histories[name]

    async def step_one(self):
        self.steps += 1
        self.robot.positions[0] = self.robot.target[0]
        self.robot.positions[1] = self.robot.multiplier * self.robot.target[0] + self.robot.absolute_offset

    async def physics_steps(self, count):
        for _ in range(count):
            await self.step_one()

    async def capture_frame(self, **kwargs):
        return None

    def add_metric(self, name, value):
        self.metrics[name] = value

    def warn(self, message):
        self.warnings.append(message)

    def fail(self, message):
        self.failures.append(message)

    def step(self, *args):
        pass

    def log(self, *args):
        pass


@pytest.mark.parametrize("backend,gear,offset", [("newton", 2.0, 3.5), ("physx", -2.0, -3.5), ("physx", 2.0, 0.75)])
@pytest.mark.asyncio
async def test_mimic_nonzero_offset_evidence_preserves_240hz_controls_and_verdict(monkeypatch, backend, gear, offset):
    pair = SimpleNamespace(reference_dof_index=0, follower_dof_index=1, gear=gear, offset=offset, backend=backend)
    multiplier = gear if backend == "newton" else -gear
    absolute_offset = offset if backend == "newton" else -offset
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **kwargs: [pair])
    monkeypatch.setattr(mimic_joint, "compute_world_aligned_bbox", lambda prim: object())
    monkeypatch.setattr(mimic_joint, "check_bbox_explode", lambda *args: None)
    monkeypatch.setattr(
        motion_history,
        "joint_metadata",
        lambda stage, root, name, root_path=None: {"joint_name": name, "unit": "rad", "identity_resolved": True},
    )
    config = {"physics_fps": 240, "settle_seconds": 0, "sweep_seconds": 0.25, "capture_fps": 15}
    recorded_robot = _Robot(multiplier, absolute_offset)
    recorded = _Context(recorded_robot, recording=True)
    ordinary_robot = _Robot(multiplier, absolute_offset)
    ordinary = _Context(ordinary_robot, recording=False)
    await mimic_joint.run_mimic_joint(recorded, recorded_robot, {"stage": None}, config)
    await mimic_joint.run_mimic_joint(ordinary, ordinary_robot, {"stage": None}, config)

    assert recorded.steps == ordinary.steps == 60
    assert len(recorded_robot.commands) == len(ordinary_robot.commands) == 60
    np.testing.assert_array_equal(recorded_robot.commands, ordinary_robot.commands)
    assert recorded_robot.reads == ordinary_robot.reads == 8
    assert recorded.metrics == ordinary.metrics
    assert recorded.failures == ordinary.failures == []
    assert recorded.metrics["mim_pair_follower_motion_ratio"] == pytest.approx(abs(gear))
    assert recorded.metrics["mim_pair_follower_max_error_rad"] == pytest.approx(0, abs=1e-12)
    assert recorded.metrics["mim_pair_follower_abs_formula_max_error_rad"] == pytest.approx(0, abs=1e-12)
    assert recorded.metrics["mim_pair_follower_rest_residual_rad"] == pytest.approx(0, abs=1e-12)
    assert recorded.metrics["mim_pair_follower_dir_matches_gear"] == 1
    assert not recorded.warnings

    reference = recorded.histories["mim_reference_001"]
    follower = recorded.histories["mim_follower_001"]
    expected_times = [(frame + 1) / 240 for frame in range(0, 60, 10)]
    assert [row[0] for row in follower.samples] == pytest.approx(expected_times)
    assert follower.metadata["diagnostic_multiplier"] == multiplier
    assert follower.metadata["diagnostic_absolute_offset"] == absolute_offset
    assert follower.metadata["gearing"] == gear and follower.metadata["offset"] == offset
    assert "angular offset conversion not qualified" in follower.metadata["absolute_equation_unit_basis"]
    for reference_row, follower_row in zip(reference.samples, follower.samples):
        reference_values = reference_row[1]
        follower_values = follower_row[1]
        expected_delta = multiplier * (reference_values["position"] - recorded_robot.initial_positions[0])
        assert follower_values["expected_displacement"] == pytest.approx(expected_delta)
        assert follower_values["incremental_displacement"] == pytest.approx(expected_delta)
        assert follower_values["incremental_error"] == pytest.approx(0, abs=1e-12)
    assert reference.reason == follower.reason == "mimic_pair_sweep_completed"


def test_diagnostic_math_keeps_public_arithmetic_helper_and_raw_spec():
    pair = SimpleNamespace(gear=2.0, offset=3.0, backend="physx")
    assert mimic_joint._diagnostic_coefficients(pair) == (-2.0, -3.0)
    assert pair.gear == 2.0 and pair.offset == 3.0
    assert mimic_joint.compute_expected_follower(5.0, 2.0, 3.0) == 13.0


@pytest.mark.asyncio
async def test_mimic_failed_response_keeps_ratio_gate_without_identifying_asset_cause(monkeypatch):
    pair = SimpleNamespace(reference_dof_index=0, follower_dof_index=1, gear=2.0, offset=0.0, backend="newton")
    monkeypatch.setattr(mimic_joint, "detect_mimic_joints", lambda **kwargs: [pair])
    monkeypatch.setattr(mimic_joint, "compute_world_aligned_bbox", lambda prim: object())
    monkeypatch.setattr(mimic_joint, "check_bbox_explode", lambda *args: None)
    robot = _Robot(multiplier=0.0, absolute_offset=0.0)
    ctx = _Context(robot, recording=False)
    await mimic_joint.run_mimic_joint(
        ctx, robot, {"stage": None}, {"physics_fps": 240, "settle_seconds": 0, "sweep_seconds": 0.25}
    )
    assert ctx.steps == 60 and len(robot.commands) == 60 and robot.reads == 8
    assert ctx.metrics["mim_pair_follower_motion_ratio"] == 0
    assert ctx.metrics["mim_pair_follower_gear_ratio_error"] == 2
    assert ctx.metrics["mim_pairs_failed"] == 1
    assert len(ctx.failures) == 1
    assert "motion-magnitude check" in ctx.failures[0]
    assert "Legacy *_rad metric names" in ctx.failures[0]
    assert "angular offset conversion unqualified" in ctx.warnings[0]
    assert "Asset fix" not in ctx.failures[0]
    assert "magnitude is wrong" not in ctx.failures[0]


def test_mimic_instability_and_direction_do_not_prescribe_automatic_repairs():
    messages = [
        mimic_joint._msg_drift_fix_hint(),
        mimic_joint._msg_sweep_instability("follower", "reference", 2.0, 3.0, "bbox grew", 240),
        mimic_joint._msg_direction_mismatch("follower", "reference", 2.0, 2.0),
    ]
    for message in messages:
        assert "optional, cosmetic" not in message
        assert "try 25-50" not in message and "try 0.5-1.0" not in message
        assert "magnitude is wrong" not in message
        assert "Asset fix" not in message
    assert "lowering that rate increases" in messages[1]
    assert "not proof of an asset defect" in messages[2] or "before attributing an asset defect" in messages[2]


def _coefficient_scene(backend):
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics

    try:
        from pxr import PhysxSchema
    except ImportError:
        from physx_usd_schemas import PhysxSchema

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    for name in ("base", "left", "right"):
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Robot/" + name).GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/Robot/base"))
    for name, tip in (("reference", "left"), ("follower", "right")):
        joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/" + name)
        joint.CreateBody0Rel().SetTargets(["/Robot/base"])
        joint.CreateBody1Rel().SetTargets(["/Robot/" + tip])
    follower = stage.GetPrimAtPath("/Robot/follower")
    if backend == "physx":
        api = PhysxSchema.PhysxMimicJointAPI.Apply(follower, "Z")
        api.CreateReferenceJointRel().SetTargets(["/Robot/reference"])
        coefficients = {"gear": api.CreateGearingAttr(-2.0), "offset": api.CreateOffsetAttr(0.0)}
    else:
        follower.AddAppliedSchema("NewtonMimicAPI")
        follower.CreateRelationship("newton:mimicJoint").SetTargets(["/Robot/reference"])
        coefficients = {
            "gear": follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Double),
            "offset": follower.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Double),
        }
        coefficients["gear"].Set(2.0)
        coefficients["offset"].Set(0.0)
    return stage, root, coefficients


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["physx", "newton"])
@pytest.mark.parametrize("coefficient", ["gear", "offset"])
@pytest.mark.parametrize("fault", [False, True])
async def test_authored_coefficient_query_failure_never_becomes_default_or_pass(
    monkeypatch, backend, coefficient, fault
):
    from pxr import Usd
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import _independent_dofs

    stage, root, coefficients = _coefficient_scene(backend)
    robot = _Robot(1.0 if backend == "newton" else -1.0, 0.0)
    robot.asset_prim = root
    followers, _, loops, _ = _independent_dofs.control_ownership(stage, root, robot.prim_path, robot.dof_names)
    assert followers == {1}
    context = _Context(robot, recording=False)
    original_get = Usd.Attribute.Get
    primary = OSError("selected authored coefficient read unavailable")
    selected_path = coefficients[coefficient].GetPath()

    def read(attribute, *args, **kwargs):
        if fault and attribute.GetPath() == selected_path:
            raise primary
        return original_get(attribute, *args, **kwargs)

    monkeypatch.setattr(Usd.Attribute, "Get", read)
    monkeypatch.setattr(mimic_joint, "compute_world_aligned_bbox", lambda *args: object())
    monkeypatch.setattr(mimic_joint, "freeze_bbox_reference", lambda *args: None)
    monkeypatch.setattr(mimic_joint, "check_bbox_explode", lambda *args: None)
    run = mimic_joint.run_mimic_joint(
        context,
        robot,
        {"stage": stage, "asset_prim": root, "mimic_follower_indices": followers, "loop_joint_indices": loops},
        {"physics_fps": 240, "settle_seconds": 0, "sweep_seconds": 0.25, "capture_fps": 15},
    )
    if fault:
        with pytest.raises(OSError) as caught:
            await run
        assert caught.value is primary
        assert context.steps == 0 and robot.commands == []
        assert "mim_pairs_failed" not in context.metrics and not context.failures
    else:
        await run
        assert context.steps == 60 and context.metrics["mim_pairs_failed"] == 1
        assert len(context.failures) == 1  # Genuine finite |gear| mismatch is still measured FAIL.


@pytest.mark.parametrize("backend", ["physx", "newton"])
@pytest.mark.parametrize("coefficient", ["gear", "offset"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_authored_coefficient_is_not_a_qualified_pair(backend, coefficient, value):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import mimic_joints

    stage, root, coefficients = _coefficient_scene(backend)
    coefficients[coefficient].Set(value)
    with pytest.raises(RuntimeError, match="finite"):
        mimic_joints.detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"])


@pytest.mark.parametrize("backend", ["physx", "newton"])
@pytest.mark.parametrize("coefficient", ["gear", "offset"])
@pytest.mark.parametrize("absence", ["absent", "blocked"])
def test_genuine_absent_or_none_coefficient_retains_existing_default(backend, coefficient, absence):
    from simready.foundation.tier_newton.runtime_tests.articulation_phases import mimic_joints

    stage, root, coefficients = _coefficient_scene(backend)
    attribute = coefficients[coefficient]
    if absence == "absent":
        attribute.GetPrim().RemoveProperty(attribute.GetName())
    else:
        attribute.Block()
    pairs = mimic_joints.detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"])
    assert len(pairs) == 1
    assert getattr(pairs[0], coefficient) == (1.0 if coefficient == "gear" else 0.0)
