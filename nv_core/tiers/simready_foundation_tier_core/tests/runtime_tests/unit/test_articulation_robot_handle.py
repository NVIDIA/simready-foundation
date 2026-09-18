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
"""Tests for articulation_phases.robot_handle.

Uses a fake SingleArticulation stub to exercise RobotHandle's state API
without needing Kit. RobotHandle.initialize() is an integration concern
(covered by the manual Kit smoke run) and is NOT exercised here.
"""
import sys
import types

import numpy as np
from pxr import Sdf, Usd, UsdGeom
from simready_benchmark_kit_suite.articulation_phases.robot_handle import (
    RobotHandle,
    _discover_mjc_tendon_controls,
    _has_native_newton_actuators,
    _native_newton_actuator_target_names,
    _newton_actuator_prims,
    _tendon_position_to_ctrl,
    _to_dof_array,
)
from simready_benchmark_kit_suite.articulation_phases.robot_type import RobotType


class FakeArticulationAction:
    """Minimal ArticulationAction shim for unit tests."""

    def __init__(self, joint_positions=None, joint_velocities=None, joint_efforts=None, joint_indices=None):
        self.joint_positions = joint_positions
        self.joint_velocities = joint_velocities
        self.joint_efforts = joint_efforts
        self.joint_indices = joint_indices


def _install_isaacsim_articulation_action_stub():
    """Register a fake ``isaacsim.core.utils.types`` module so
    ``RobotHandle._apply_action`` can import ``ArticulationAction`` outside
    a Kit install. Safe to call multiple times.
    """
    if "isaacsim.core.utils.types" in sys.modules:
        return
    isaacsim_mod = sys.modules.setdefault("isaacsim", types.ModuleType("isaacsim"))
    core_mod = sys.modules.setdefault("isaacsim.core", types.ModuleType("isaacsim.core"))
    utils_mod = sys.modules.setdefault("isaacsim.core.utils", types.ModuleType("isaacsim.core.utils"))
    types_mod = types.ModuleType("isaacsim.core.utils.types")
    types_mod.ArticulationAction = FakeArticulationAction
    sys.modules["isaacsim.core.utils.types"] = types_mod
    # wire submodules together so `from isaacsim.core.utils.types import X` works
    core_mod.utils = utils_mod
    utils_mod.types = types_mod
    isaacsim_mod.core = core_mod


_install_isaacsim_articulation_action_stub()


class FakeArticulation:
    def __init__(self, dof_names, positions, velocities, efforts, lowers, uppers, vel_limits, eff_limits):
        self.dof_names = list(dof_names)
        self._positions = np.array(positions, dtype=np.float64)
        self._velocities = np.array(velocities, dtype=np.float64)
        self._efforts = np.array(efforts, dtype=np.float64)
        self._lowers = np.array(lowers, dtype=np.float64)
        self._uppers = np.array(uppers, dtype=np.float64)
        self._vel_limits = np.array(vel_limits, dtype=np.float64)
        self._eff_limits = np.array(eff_limits, dtype=np.float64)
        self._last_position_targets = None
        self._last_velocity_targets = None
        self._last_joint_indices = None

    def get_joint_positions(self):
        return self._positions.copy()

    def get_joint_velocities(self):
        return self._velocities.copy()

    def get_world_pose(self):
        return np.array([1.0, 2.0, 3.0]), np.array([1.0, 0.0, 0.0, 0.0])

    def get_applied_joint_efforts(self):
        return self._efforts.copy()

    def apply_action(self, action):
        """Capture position/velocity targets from ArticulationAction."""
        if getattr(action, "joint_positions", None) is not None:
            self._last_position_targets = np.array(action.joint_positions, dtype=np.float64)
        if getattr(action, "joint_velocities", None) is not None:
            self._last_velocity_targets = np.array(action.joint_velocities, dtype=np.float64)
        if getattr(action, "joint_indices", None) is not None:
            self._last_joint_indices = np.asarray(action.joint_indices)

    def set_joint_positions(self, positions):
        self._positions = np.array(positions, dtype=np.float64)

    def set_joint_velocities(self, velocities):
        self._velocities = np.array(velocities, dtype=np.float64)

    @property
    def dof_properties(self):
        rows = []
        for i in range(len(self.dof_names)):
            rows.append(
                {
                    "lower": float(self._lowers[i]),
                    "upper": float(self._uppers[i]),
                    "max_velocity": float(self._vel_limits[i]),
                    "max_effort": float(self._eff_limits[i]),
                }
            )
        return rows


def _make_handle_with_fake(articulation):
    # Bypass __init__'s stage/pxr requirements by setting private fields directly.
    handle = RobotHandle.__new__(RobotHandle)
    handle._stage = None
    handle._robot_prim_path = "/World/Robot"
    handle._asset_prim = None
    handle._root_prim = None
    handle._robot_type = RobotType.ARM
    handle._articulation = articulation
    handle._newton_actuators = None
    handle._initialized = True
    handle._name = "robot_test"
    return handle


def test_detects_native_newton_actuator_under_articulation():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World/Robot")
    stage.DefinePrim("/World/Robot/Actuators/finger", "NewtonActuator")

    assert _has_native_newton_actuators(stage, "/World/Robot")
    assert not _has_native_newton_actuators(stage, "/World/Missing")


def test_discovers_native_newton_actuators_across_merged_sibling_subtrees():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World/Carrier")
    UsdGeom.Xform.Define(stage, "/World/Asset")
    rail_joint = stage.DefinePrim("/World/Carrier/joint_z", "PhysicsPrismaticJoint")
    finger_joint = stage.DefinePrim("/World/Asset/finger_joint", "PhysicsRevoluteJoint")
    rail = stage.DefinePrim("/World/Carrier/joint_z_actuator", "NewtonActuator")
    finger = stage.DefinePrim("/World/Asset/finger_actuator", "NewtonActuator")
    rail.CreateRelationship("newton:targets").SetTargets([rail_joint.GetPath()])
    finger.CreateRelationship("newton:targets").SetTargets([finger_joint.GetPath()])

    roots = ["/World/Carrier", "/World/Asset"]
    assert [str(prim.GetPath()) for prim in _newton_actuator_prims(stage, roots)] == [
        "/World/Carrier/joint_z_actuator",
        "/World/Asset/finger_actuator",
    ]
    assert _native_newton_actuator_target_names(stage, roots) == {"joint_z", "finger_joint"}


def test_discovers_native_mjc_fixed_tendon_actuator():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World/Robot")
    left = stage.DefinePrim("/World/Robot/Joints/left", "PhysicsRevoluteJoint")
    right = stage.DefinePrim("/World/Robot/Joints/right", "PhysicsRevoluteJoint")
    right.CreateRelationship("newton:mimicJoint").SetTargets([left.GetPath()])
    tendon = stage.DefinePrim("/World/Robot/Actuators/fingers", "MjcTendon")
    tendon.CreateRelationship("mjc:path").SetTargets([left.GetPath(), right.GetPath()])
    tendon.CreateAttribute("mjc:path:coef", Sdf.ValueTypeNames.DoubleArray).Set([0.485, 0.485])
    actuator = stage.DefinePrim("/World/Robot/Actuators/fingers_ctrl", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets([tendon.GetPath()])
    actuator.CreateAttribute("mjc:gainPrm", Sdf.ValueTypeNames.DoubleArray).Set([0.3137255])
    actuator.CreateAttribute("mjc:biasPrm", Sdf.ValueTypeNames.DoubleArray).Set([0.0, -100.0, -10.0])
    actuator.CreateAttribute("mjc:ctrlRange:min", Sdf.ValueTypeNames.Double).Set(0.0)
    actuator.CreateAttribute("mjc:ctrlRange:max", Sdf.ValueTypeNames.Double).Set(255.0)

    controls = _discover_mjc_tendon_controls(stage, "/World/Robot")

    assert _has_native_newton_actuators(stage, "/World/Robot")
    assert len(controls) == 1
    assert controls[0]["joint_names"] == ["left", "right"]
    assert controls[0]["control_joint_names"] == ["left"]
    assert controls[0]["coefficients"] == [0.485, 0.485]
    assert controls[0]["joint_target_offsets"] == [0.0, 0.0]
    assert controls[0]["joint_target_scales"] == [1.0, 1.0]


def test_initialize_newton_discovers_tendon_below_asset_when_carrier_is_articulation_root(monkeypatch):
    stage = Usd.Stage.CreateInMemory()
    carrier = UsdGeom.Xform.Define(stage, "/World/Carrier").GetPrim()
    asset = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    driver = stage.DefinePrim("/World/Asset/Joints/driver", "PhysicsRevoluteJoint")
    follower = stage.DefinePrim("/World/Asset/Joints/follower", "PhysicsRevoluteJoint")
    follower.CreateRelationship("newton:mimicJoint").SetTargets([driver.GetPath()])
    tendon = stage.DefinePrim("/World/Asset/Actuators/fingers", "MjcTendon")
    tendon.CreateRelationship("mjc:path").SetTargets([follower.GetPath(), driver.GetPath()])
    tendon.CreateAttribute("mjc:path:coef", Sdf.ValueTypeNames.DoubleArray).Set([0.5, 0.5])
    actuator = stage.DefinePrim("/World/Asset/Actuators/fingers_ctrl", "MjcActuator")
    actuator.CreateRelationship("mjc:target").SetTargets([tendon.GetPath()])
    actuator.CreateAttribute("mjc:gainPrm", Sdf.ValueTypeNames.DoubleArray).Set([1.0])
    actuator.CreateAttribute("mjc:biasPrm", Sdf.ValueTypeNames.DoubleArray).Set([0.0, -1.0, -0.1])

    assert _discover_mjc_tendon_controls(stage, str(carrier.GetPath())) == []
    controls = _discover_mjc_tendon_controls(stage, str(asset.GetPath()))
    assert controls[0]["control_joint_names"] == ["driver"]


def test_tendon_position_to_ctrl_uses_affine_equilibrium_and_clamps():
    actuator = {
        "coefficients": [0.485, 0.485],
        "gain": 0.3137255,
        "position_bias": -100.0,
        "ctrl_min": 0.0,
        "ctrl_max": 255.0,
    }

    assert _tendon_position_to_ctrl(actuator, 0.0) == 0.0
    assert np.isclose(_tendon_position_to_ctrl(actuator, 0.5), 154.59375, atol=1e-4)
    assert _tendon_position_to_ctrl(actuator, 0.9) == 255.0


def test_tendon_position_to_ctrl_accounts_for_opposed_mimic_coordinates():
    actuator = {
        "coefficients": [-0.485, 0.485],
        "joint_target_offsets": [0.0, 0.0],
        "joint_target_scales": [-1.0, 1.0],
        "gain": 0.3137255,
        "position_bias": -100.0,
        "ctrl_min": 0.0,
        "ctrl_max": 255.0,
    }

    assert _tendon_position_to_ctrl(actuator, 0.0) == 0.0
    assert np.isclose(_tendon_position_to_ctrl(actuator, 0.5), 154.59375, atol=1e-4)
    assert _tendon_position_to_ctrl(actuator, 0.9) == 255.0


def test_teardown_closes_native_newton_actuator_bridge():
    class Manager:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    handle = _make_handle_with_fake(FakeArticulation([], [], [], [], [], [], [], []))
    manager = Manager()
    handle._newton_actuators = manager

    handle.teardown()

    assert manager.closed
    assert handle._newton_actuators is None


def test_dof_count_and_names():
    art = FakeArticulation(
        dof_names=["a", "b", "c"],
        positions=[0.0, 0.0, 0.0],
        velocities=[0.0, 0.0, 0.0],
        efforts=[0.0, 0.0, 0.0],
        lowers=[-1.0, -2.0, -3.0],
        uppers=[1.0, 2.0, 3.0],
        vel_limits=[10.0, 20.0, 30.0],
        eff_limits=[100.0, 200.0, 300.0],
    )
    h = _make_handle_with_fake(art)
    assert h.dof_count == 3
    assert h.dof_names == ["a", "b", "c"]


def test_get_world_pose_copies_cuda_backed_values_to_host():
    art = FakeArticulation([], [], [], [], [], [], [], [])

    class DeviceBackedValues:
        def __init__(self, values):
            self.values = np.asarray(values)

        def __array__(self, dtype=None):
            raise TypeError("cannot convert cuda:0 device type tensor to numpy")

        def detach(self):
            return self

        def cpu(self):
            return self.values

    art.get_world_pose = lambda: (
        DeviceBackedValues([1.0, 2.0, 3.0]),
        DeviceBackedValues([1.0, 0.0, 0.0, 0.0]),
    )
    handle = _make_handle_with_fake(art)

    position, orientation = handle.get_world_pose()

    assert np.allclose(position, [1.0, 2.0, 3.0])
    assert np.allclose(orientation, [1.0, 0.0, 0.0, 0.0])


class _FakePhysicsView:
    def __init__(self, transforms):
        self.transforms = np.asarray(transforms, dtype=np.float64)

    def get_link_transforms(self):
        return self.transforms

    def apply_forces_and_torques_at_position(self, forces, torques, positions, indices, is_global=True):
        self.applied_forces = np.asarray(forces)
        self.applied_indices = np.asarray(indices)
        self.applied_is_global = is_global


class _CudaBackedPhysicsView(_FakePhysicsView):
    def get_link_transforms(self):
        values = self.transforms

        class DeviceBackedValues:
            def __array__(self, dtype=None):
                raise TypeError("cannot convert cuda:0 device type tensor to numpy")

            def detach(self):
                return self

            def cpu(self):
                return values

        return DeviceBackedValues()


def _handle_with_link_view(body_names, transforms, paths):
    art = FakeArticulation([], [], [], [], [], [], [], [])
    art._articulation_view = types.SimpleNamespace(
        body_names=body_names,
        _physics_view=_FakePhysicsView(transforms),
    )
    handle = _make_handle_with_fake(art)
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    for path in paths:
        UsdGeom.Xform.Define(stage, path)
    handle._stage = stage
    return handle


def test_link_transform_lookup_rejects_duplicate_physics_link_names():
    handle = _handle_with_link_view(
        ["tip", "tip"],
        [[[0, 0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 0, 1]]],
        ["/World/a/tip"],
    )

    assert handle.get_link_world_positions(["/World/a/tip"]) == {}
    assert "ambiguous physics link name" in handle._link_transform_resolve_detail


def test_link_transform_lookup_accepts_identical_closed_loop_alias_rows():
    handle = _handle_with_link_view(
        ["tip", "tip"],
        [[[1, 2, 3, 0, 0, 0, 1], [1, 2, 3, 0, 0, 0, 1]]],
        ["/World/a/tip"],
    )

    positions = handle.get_link_world_positions(["/World/a/tip"])

    assert np.allclose(positions["/World/a/tip"], [1, 2, 3])


def test_link_transform_lookup_rejects_non_finite_and_stale_rows():
    non_finite = _handle_with_link_view(
        ["tip"],
        [[[float("nan"), 0, 0, 0, 0, 0, 1]]],
        ["/World/a/tip"],
    )
    stale = _handle_with_link_view(
        ["tip", "other"],
        [[[0, 0, 0, 0, 0, 0, 1]]],
        ["/World/a/tip"],
    )

    assert non_finite.get_link_world_positions(["/World/a/tip"]) == {}
    assert "non-finite" in non_finite._link_transform_resolve_detail
    assert stale.get_link_world_positions(["/World/a/tip"]) == {}
    assert "stale physics link view" in stale._link_transform_resolve_detail


def test_link_transform_lookup_copies_cuda_backed_rows_to_host():
    handle = _handle_with_link_view(
        ["tip"],
        [[[1, 2, 3, 0, 0, 0, 1]]],
        ["/World/a/tip"],
    )
    handle._articulation._articulation_view._physics_view = _CudaBackedPhysicsView([[[1, 2, 3, 0, 0, 0, 1]]])

    transforms = handle.get_link_world_transforms(["/World/a/tip"])

    position, quaternion = transforms["/World/a/tip"]
    assert np.allclose(position, [1, 2, 3])
    assert np.allclose(quaternion, [0, 0, 0, 1])


def test_apply_external_force_targets_exact_articulation_link():
    handle = _handle_with_link_view(
        ["base", "tool"],
        [[[0, 0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 0, 1]]],
        ["/World/robot/tool"],
    )

    assert handle.apply_external_force("/World/robot/tool", (0.0, 2.0, 0.0), 5.0)
    physics_view = handle._articulation._articulation_view._physics_view
    assert physics_view.applied_forces.shape == (1, 2, 3)
    assert physics_view.applied_forces[0, 0].tolist() == [0.0, 0.0, 0.0]
    assert physics_view.applied_forces[0, 1].tolist() == [0.0, 10.0, 0.0]
    assert physics_view.applied_indices.tolist() == [0]
    assert physics_view.applied_is_global is True


def test_get_joint_positions_returns_copy():
    art = FakeArticulation(["a"], [0.5], [0.0], [0.0], [-1.0], [1.0], [10.0], [100.0])
    h = _make_handle_with_fake(art)
    out = h.get_joint_positions()
    out[0] = 99.0
    assert art.get_joint_positions()[0] == 0.5


def test_set_joint_position_targets_forwards_to_articulation():
    art = FakeArticulation(
        ["a", "b"], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [-1.0, -1.0], [1.0, 1.0], [10.0, 10.0], [100.0, 100.0]
    )
    h = _make_handle_with_fake(art)
    h.set_joint_position_targets(np.array([0.5, -0.5]))
    assert art._last_position_targets is not None
    assert list(art._last_position_targets) == [0.5, -0.5]


def test_set_joint_position_target_forwards_sparse_action():
    art = FakeArticulation(
        ["a", "b"], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [-1.0, -1.0], [1.0, 1.0], [10.0, 10.0], [100.0, 100.0]
    )
    h = _make_handle_with_fake(art)
    h.set_joint_position_target(1, -0.5)
    assert list(art._last_position_targets) == [-0.5]
    assert list(art._last_joint_indices) == [1]


def test_apply_action_preserves_integer_joint_indices_with_backend_conversion():
    class Backend:
        @staticmethod
        def convert(value, device=None, dtype="float32", indexed=None):
            numpy_dtype = np.int32 if dtype == "int32" else np.float32
            return np.asarray(value, dtype=numpy_dtype)

    art = FakeArticulation(
        ["a", "b"],
        [0.0, 0.0],
        [0.0, 0.0],
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0],
        [10.0, 10.0],
        [100.0, 100.0],
    )
    art._backend_utils = Backend()
    art._device = "cpu"
    handle = _make_handle_with_fake(art)

    handle._apply_action(joint_positions=np.array([0.5]), joint_indices=np.array([1], dtype=np.int32))

    assert art._last_joint_indices.dtype == np.int32
    assert art._last_joint_indices.tolist() == [1]


def test_newton_sparse_position_action_expands_from_current_state_when_targets_are_invalid():
    art = FakeArticulation(
        ["a", "b"],
        [0.25, -0.25],
        [0.0, 0.0],
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0],
        [10.0, 10.0],
        [100.0, 100.0],
    )
    handle = _make_handle_with_fake(art)
    handle._is_newton = True

    handle._apply_action(joint_positions=np.array([0.5]), joint_indices=np.array([1], dtype=np.int32))

    assert art._last_joint_indices is None
    assert art._last_position_targets.tolist() == [0.25, 0.5]


def test_public_apply_action_uses_backend_conversion():
    class Backend:
        dtypes = []

        @staticmethod
        def convert(value, device=None, dtype="float32", indexed=None):
            Backend.dtypes.append(dtype)
            numpy_dtype = np.int32 if dtype == "int32" else np.float32
            return np.asarray(value, dtype=numpy_dtype)

    class Action:
        joint_positions = np.array([0.25], dtype=np.float64)
        joint_velocities = None
        joint_efforts = None
        joint_indices = np.array([1], dtype=np.int64)

    art = FakeArticulation(
        ["a", "b"],
        [0.0, 0.0],
        [0.0, 0.0],
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0],
        [10.0, 10.0],
        [100.0, 100.0],
    )
    art._backend_utils = Backend()
    art._device = "cuda:0"
    handle = _make_handle_with_fake(art)

    handle.apply_action(Action())

    assert Backend.dtypes == ["float32", "int32"]
    assert art._last_position_targets.tolist() == [0.25]
    assert art._last_joint_indices.dtype == np.int32
    assert art._last_joint_indices.tolist() == [1]


def test_apply_action_uses_native_newton_actuator_target_buffers():
    calls = []

    class NativeArticulation:
        dof_paths = [["/robot/joint_d", "/robot/joint_a", "/robot/joint_b", "/robot/joint_c"]]

        def set_dof_position_targets(self, values, **kwargs):
            calls.append(("position", values, kwargs))

        def set_dof_velocity_targets(self, values, **kwargs):
            calls.append(("velocity", values, kwargs))

        def set_dof_efforts(self, values, **kwargs):
            calls.append(("effort", values, kwargs))

    handle = RobotHandle.__new__(RobotHandle)
    stepped = []
    handle._newton_actuators = types.SimpleNamespace(
        articulation=NativeArticulation(),
        step_actuators=lambda step_dt: stepped.append(step_dt),
    )
    handle._physics_dt = 1.0 / 120.0
    handle._articulation = types.SimpleNamespace(
        dof_names=["joint_a", "joint_b", "joint_c", "joint_d"],
        apply_action=lambda _action: (_ for _ in ()).throw(
            AssertionError("legacy articulation received a native Newton action")
        ),
    )

    handle._apply_action(
        joint_positions=np.array([0.5]),
        joint_velocities=np.array([0.1]),
        joint_efforts=np.array([2.0]),
        joint_indices=np.array([3]),
    )

    assert [entry[0] for entry in calls] == ["position", "velocity", "effort"]
    # Targets are staged independently; the actuator manager's pre-physics
    # callback advances every controller once for the simulation frame.
    assert stepped == []
    for _kind, values, kwargs in calls:
        assert values.dtype == np.float32
        assert kwargs["dof_indices"].dtype == np.int32
        assert kwargs["dof_indices"].tolist() == [0]


def test_native_tendon_control_is_written_after_other_newton_actuators():
    order = []

    class NativeArticulation:
        dof_paths = [["/robot/driver"]]

        def set_dof_position_targets(self, values, **kwargs):
            order.append("position_target")

    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = types.SimpleNamespace(
        articulation=NativeArticulation(),
        step_actuators=lambda step_dt: order.append("actuator_step"),
    )
    handle._mjc_tendon_controls = [{"control_joint_names": ["driver"]}]
    handle._apply_mjc_tendon_position_targets = lambda values, indices: order.append("tendon_ctrl")
    handle._physics_dt = 1.0 / 240.0
    handle._articulation = types.SimpleNamespace(dof_names=["driver"])

    handle._apply_action(joint_positions=np.array([0.5]))

    assert order == ["position_target", "tendon_ctrl"]


def test_native_newton_bridge_omits_excluded_legacy_loop_closure_dofs():
    calls = []

    class NativeArticulation:
        dof_paths = [["/robot/driver", "/robot/follower"]]

        def set_dof_position_targets(self, values, **kwargs):
            calls.append((values, kwargs))

        def get_dof_positions(self):
            return np.array([0.25, -0.5], dtype=np.float32)

    handle = RobotHandle.__new__(RobotHandle)
    handle._newton_actuators = types.SimpleNamespace(
        articulation=NativeArticulation(),
        step_actuators=lambda step_dt: None,
    )
    handle._physics_dt = 1.0 / 240.0
    handle._articulation = types.SimpleNamespace(
        dof_names=["driver", "excluded_loop", "follower"],
    )

    handle._apply_action(joint_positions=np.array([0.1, 99.0, -0.2]))

    values, kwargs = calls[0]
    assert kwargs == {}
    assert np.allclose(values, [0.1, -0.2])
    positions = handle.get_joint_positions()
    assert np.isclose(positions[0], 0.25)
    assert np.isnan(positions[1])
    assert np.isclose(positions[2], -0.5)


def test_get_joint_position_limits_returns_tuple_of_arrays():
    art = FakeArticulation(
        ["a", "b"], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [-1.0, -2.0], [1.0, 2.0], [10.0, 20.0], [100.0, 200.0]
    )
    h = _make_handle_with_fake(art)
    lower, upper = h.get_joint_position_limits()
    assert list(lower) == [-1.0, -2.0]
    assert list(upper) == [1.0, 2.0]


def test_get_joint_velocity_limits():
    art = FakeArticulation(
        ["a", "b"], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [-1.0, -1.0], [1.0, 1.0], [10.0, 20.0], [100.0, 200.0]
    )
    h = _make_handle_with_fake(art)
    out = h.get_joint_velocity_limits()
    assert list(out) == [10.0, 20.0]


def test_robot_type_property():
    art = FakeArticulation(["a"], [0.0], [0.0], [0.0], [-1.0], [1.0], [10.0], [100.0])
    h = _make_handle_with_fake(art)
    assert h.robot_type == RobotType.ARM


def test_articulation_escape_hatch():
    art = FakeArticulation(["a"], [0.0], [0.0], [0.0], [-1.0], [1.0], [10.0], [100.0])
    h = _make_handle_with_fake(art)
    assert h.articulation is art


# -----------------------------------------------------------------------------
# _to_dof_array — defensive coercion of (possibly broken) tensor reads.
# Protects callers from IndexError when the physics view is invalidated
# mid-test and Articulation.get_joint_positions() returns None.
# -----------------------------------------------------------------------------


def test_to_dof_array_none_returns_nan_filled():
    """None (invalidated view) → NaN-filled 1-D array of shape (dof_count,)."""
    out = _to_dof_array(None, 6)
    assert out.shape == (6,)
    assert np.isnan(out).all()


def test_to_dof_array_zero_d_returns_nan_filled():
    """0-D array (np.array(None) coercion) → NaN-filled."""
    raw = np.array(None)  # shape ()
    assert raw.ndim == 0
    out = _to_dof_array(raw, 4)
    assert out.shape == (4,)
    assert np.isnan(out).all()


def test_to_dof_array_well_formed_passes_through():
    raw = np.array([0.1, 0.2, 0.3, 0.4])
    out = _to_dof_array(raw, 4)
    assert out.shape == (4,)
    assert np.allclose(out, [0.1, 0.2, 0.3, 0.4])


def test_to_dof_array_wrong_length_returns_nan():
    raw = np.array([0.1, 0.2])  # only 2 of 5
    out = _to_dof_array(raw, 5)
    assert out.shape == (5,)
    assert np.isnan(out).all()


def test_to_dof_array_2d_is_flattened_when_size_matches():
    raw = np.array([[0.1, 0.2, 0.3]])  # shape (1, 3)
    out = _to_dof_array(raw, 3)
    assert out.shape == (3,)
    assert np.allclose(out, [0.1, 0.2, 0.3])


def test_to_dof_array_reads_device_backed_values_elementwise():
    class DeviceBackedValues:
        def __init__(self, values):
            self._values = values

        def __array__(self, dtype=None):
            raise TypeError("cannot convert CUDA tensor to numpy")

        def detach(self):
            return self

        def cpu(self):
            return np.asarray(self._values)

    out = _to_dof_array(DeviceBackedValues([0.25, -0.5, 1.0]), 3)

    assert out.shape == (3,)
    assert np.allclose(out, [0.25, -0.5, 1.0])


def test_limits_fall_back_to_cuda_backed_articulation_view():
    class DeviceBackedValues:
        def __init__(self, values):
            self._values = values

        def detach(self):
            return self

        def cpu(self):
            return np.asarray(self._values)

    class NewtonArticulation(FakeArticulation):
        @property
        def dof_properties(self):
            raise TypeError("cannot convert cuda:0 device type tensor to numpy")

    art = NewtonArticulation(
        ["a", "b"], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [-1.0, -2.0], [1.0, 2.0], [10.0, 20.0], [100.0, 200.0]
    )
    art._articulation_view = types.SimpleNamespace(
        get_dof_limits=lambda: DeviceBackedValues([[[-1.0, 1.0], [-2.0, 2.0]]]),
        get_joint_max_velocities=lambda: DeviceBackedValues([[10.0, 20.0]]),
        get_max_efforts=lambda: DeviceBackedValues([[100.0, 200.0]]),
    )
    handle = _make_handle_with_fake(art)

    lower, upper = handle.get_joint_position_limits()
    assert np.allclose(lower, [-1.0, -2.0])
    assert np.allclose(upper, [1.0, 2.0])
    assert np.allclose(handle.get_joint_velocity_limits(), [10.0, 20.0])
    assert np.allclose(handle.get_joint_effort_limits(), [100.0, 200.0])
