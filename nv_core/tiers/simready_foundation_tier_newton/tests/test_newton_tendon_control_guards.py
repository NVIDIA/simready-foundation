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
"""Actual authored-data conversion and pre-native-write regression boundaries."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdGeom
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import (
    RobotHandle,
    _discover_mjc_tendon_controls,
    _tendon_position_to_ctrl,
)


def _control(**overrides):
    return dict(
        {
            "coefficients": [1.0],
            "gain": 1.0,
            "position_bias": -1.0,
            "ctrl_min": -np.inf,
            "ctrl_max": np.inf,
            "control_joint_names": ["driver"],
            "target_path": "/Robot/tendon",
            "actuator_path": "/Robot/control",
        },
        **overrides,
    )


@pytest.mark.parametrize(
    "override",
    [
        {"gain": float("nan")},
        {"gain": float("inf")},
        {"gain": 0.0},
        {"gain": True},
        {"position_bias": float("nan")},
        {"position_bias": -float("inf")},
        {"coefficients": [float("nan")]},
        {"coefficients": [True]},
        {"coefficients": ["1"]},
        {"joint_target_offsets": [float("inf")]},
        {"joint_target_scales": [float("nan")]},
        {"joint_target_scales": [1.0, 1.0]},
        {"ctrl_min": float("nan")},
        {"ctrl_min": float("inf")},
        {"ctrl_max": -float("inf")},
        {"ctrl_min": 2, "ctrl_max": 1},
    ],
)
def test_malformed_affine_parameters_never_produce_a_control(override):
    with pytest.raises(RuntimeError, match="Newton fixed-tendon"):
        _tendon_position_to_ctrl(_control(**override), 0.25)


@pytest.mark.parametrize("target", [float("nan"), float("inf"), True, "0.25"])
def test_malformed_target_is_not_coerced(target):
    with pytest.raises(RuntimeError, match="requested control"):
        _tendon_position_to_ctrl(_control(), target)


def test_valid_clamping_and_unbounded_sentinels_keep_their_existing_values():
    assert _tendon_position_to_ctrl(_control(), 0.25) == 0.25
    assert _tendon_position_to_ctrl(_control(ctrl_min=0, ctrl_max=0.1), 0.25) == 0.1
    assert _tendon_position_to_ctrl(_control(ctrl_min=0.1, ctrl_max=0.1), -0.25) == 0.1
    assert _tendon_position_to_ctrl(_control(ctrl_min=0, ctrl_max=np.inf), 1e6) == 1e6


@pytest.mark.parametrize("overrides,target", [({"coefficients": [1e308]}, 2.0), ({"gain": 1e-308}, 2.0)])
def test_finite_parameters_with_overflowing_derived_control_are_errors(overrides, target):
    with pytest.raises(RuntimeError, match="requested control"):
        _tendon_position_to_ctrl(_control(**overrides), target)


def _authored_control():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Robot")
    joint = stage.DefinePrim("/Robot/driver", "PhysicsRevoluteJoint")
    tendon = stage.DefinePrim("/Robot/tendon", "MjcTendon")
    tendon.CreateRelationship("mjc:path").SetTargets([joint.GetPath()])
    tendon.CreateAttribute("mjc:path:coef", Sdf.ValueTypeNames.DoubleArray).Set([1.0])
    actuator = stage.DefinePrim("/Robot/control", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets([tendon.GetPath()])
    actuator.CreateAttribute("mjc:gainPrm", Sdf.ValueTypeNames.DoubleArray).Set([1.0])
    actuator.CreateAttribute("mjc:biasPrm", Sdf.ValueTypeNames.DoubleArray).Set([0.0, -1.0])
    return stage, tendon, actuator


@pytest.mark.parametrize("field", ["gain", "bias", "coefficient", "lower", "upper"])
def test_actual_usd_discovery_rejects_nonfinite_authored_controls(field):
    stage, tendon, actuator = _authored_control()
    if field == "gain":
        actuator.GetAttribute("mjc:gainPrm").Set([float("nan")])
    elif field == "bias":
        actuator.GetAttribute("mjc:biasPrm").Set([0.0, float("nan")])
    elif field == "coefficient":
        tendon.GetAttribute("mjc:path:coef").Set([float("nan")])
    else:
        actuator.CreateAttribute(
            "mjc:ctrlRange:" + ("min" if field == "lower" else "max"), Sdf.ValueTypeNames.Double
        ).Set(float("nan"))
    with pytest.raises(RuntimeError, match="Newton fixed-tendon"):
        _discover_mjc_tendon_controls(stage, "/Robot")


def test_actual_usd_discovery_keeps_absent_unbounded_ranges():
    stage, _tendon, _actuator = _authored_control()
    controls = _discover_mjc_tendon_controls(stage, "/Robot")
    assert len(controls) == 1
    assert controls[0]["ctrl_min"] == -np.inf and controls[0]["ctrl_max"] == np.inf
    assert _tendon_position_to_ctrl(controls[0], 0.25) == 0.25


def test_actual_usd_discovery_does_not_coerce_malformed_boolean_range():
    stage, _tendon, actuator = _authored_control()
    actuator.CreateAttribute("mjc:ctrlRange:min", Sdf.ValueTypeNames.Bool).Set(True)
    with pytest.raises(RuntimeError, match="Newton fixed-tendon"):
        _discover_mjc_tendon_controls(stage, "/Robot")


@pytest.mark.parametrize("gain,bias", [(0.0, -1.0), (1.0, 0.0), (1.0, 1.0)])
def test_disabled_or_nonposition_actuators_keep_discovery_skip(gain, bias):
    stage, _tendon, actuator = _authored_control()
    actuator.GetAttribute("mjc:gainPrm").Set([gain])
    actuator.GetAttribute("mjc:biasPrm").Set([0.0, bias])
    assert _discover_mjc_tendon_controls(stage, "/Robot") == []


class _Buffer:
    dtype = np.float32
    device = "cpu"

    def __init__(self, values):
        self.values = np.asarray(values, dtype=np.float32)

    def numpy(self):
        return self.values  # Deliberately shared, so a missed copy would mutate native data.


def _native_handle(monkeypatch, controls):
    copies, targets = [], []
    native_buffer = _Buffer([0.0, 0.0])
    solver_buffer = _Buffer([[0.0, 0.0]])
    native_stage = SimpleNamespace(
        model=SimpleNamespace(mujoco=SimpleNamespace(actuator_target_label=["/Robot/tendon", "/Robot/other"])),
        control=SimpleNamespace(mujoco=SimpleNamespace(ctrl=native_buffer)),
        solver=SimpleNamespace(mjw_data=SimpleNamespace(ctrl=solver_buffer)),
    )
    backend = SimpleNamespace(model=native_stage.model, newton_stage=native_stage)
    articulation = SimpleNamespace(
        dof_paths=[["/Robot/driver"]],
        _physics_articulation_view=backend,
        set_dof_position_targets=lambda *args, **kwargs: targets.append(args),
    )
    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = SimpleNamespace(articulation=articulation)
    handle._articulation = SimpleNamespace(dof_names=["driver"])
    handle._mjc_tendon_controls = controls
    monkeypatch.setitem(sys.modules, "isaacsim.physics.newton", SimpleNamespace(acquire_stage=lambda: native_stage))
    monkeypatch.setitem(
        sys.modules,
        "warp",
        SimpleNamespace(
            array=lambda values, **kwargs: np.asarray(values).copy(),
            copy=lambda destination, values: (
                copies.append(destination),
                destination.values.__setitem__(slice(None), values),
            ),
        ),
    )
    return handle, native_buffer, solver_buffer, copies, targets


@pytest.mark.parametrize("invalid", ["nonfinite", "overflow", "native_precision", "unmapped", "target_precision"])
def test_bad_later_control_cannot_partially_write_any_native_buffer(monkeypatch, invalid):
    cases = {
        "nonfinite": _control(target_path="/Robot/other", gain=float("nan")),
        "overflow": _control(target_path="/Robot/other", gain=1e-308),
        "native_precision": _control(target_path="/Robot/other", gain=1e-40),
        "unmapped": _control(target_path="/Robot/uncompiled"),
        "target_precision": _control(target_path="/Robot/other", coefficients=[1e-100]),
    }
    bad = cases[invalid]
    handle, native, solver, copies, targets = _native_handle(monkeypatch, [_control(), bad])
    with pytest.raises(RuntimeError, match="Newton.*tendon"):
        handle._apply_native_newton_action(
            joint_positions=np.asarray([1e100 if invalid == "target_precision" else 2.0])
        )
    assert not copies and not targets
    np.testing.assert_array_equal(native.values, [0.0, 0.0])
    np.testing.assert_array_equal(solver.values, [[0.0, 0.0]])


def test_valid_control_updates_native_and_solver_buffers_consistently(monkeypatch):
    handle, native, solver, copies, _targets = _native_handle(monkeypatch, [_control()])
    handle._apply_mjc_tendon_position_targets(np.asarray([0.25]), np.asarray([0]))
    assert len(copies) == 2
    np.testing.assert_array_equal(native.values, [0.25, 0.0])
    np.testing.assert_array_equal(solver.values, [[0.25, 0.0]])


@pytest.mark.parametrize("shape", [(1,), (1, 1)])
def test_valid_whole_action_prepares_first_then_preserves_native_commit_order(monkeypatch, shape):
    handle, native, solver, copies, targets = _native_handle(monkeypatch, [_control()])
    handle._apply_native_newton_action(joint_positions=np.asarray([0.25]).reshape(shape))
    assert len(targets) == 1 and len(copies) == 2
    np.testing.assert_array_equal(targets[0][0], [0.25])
    np.testing.assert_array_equal(native.values, [0.25, 0.0])
    np.testing.assert_array_equal(solver.values, [[0.25, 0.0]])


@pytest.mark.parametrize("malformed", [[[True]], [["0.25"]], [[0.25], [0.5]]])
def test_single_row_target_compatibility_does_not_coerce_types_or_multiple_articulations(monkeypatch, malformed):
    handle, native, solver, copies, targets = _native_handle(monkeypatch, [_control()])
    with pytest.raises(RuntimeError, match="Newton fixed-tendon"):
        handle._apply_native_newton_action(joint_positions=malformed)
    assert not copies and not targets
    np.testing.assert_array_equal(native.values, [0.0, 0.0])
    np.testing.assert_array_equal(solver.values, [[0.0, 0.0]])


def test_failed_later_mapping_cannot_mutate_shared_numpy_control_view(monkeypatch):
    handle, native, solver, copies, _targets = _native_handle(
        monkeypatch, [_control(), _control(target_path="/Robot/uncompiled")]
    )
    with pytest.raises(RuntimeError, match="did not compile tendon target"):
        handle._apply_mjc_tendon_position_targets(np.asarray([0.25]), np.asarray([0]))
    assert not copies
    np.testing.assert_array_equal(native.values, [0.0, 0.0])
    np.testing.assert_array_equal(solver.values, [[0.0, 0.0]])
