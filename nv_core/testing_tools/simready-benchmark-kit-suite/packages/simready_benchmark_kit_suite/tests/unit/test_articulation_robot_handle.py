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
from simready_benchmark_kit_suite.articulation_phases.robot_handle import (
    RobotHandle,
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

    def get_joint_positions(self):
        return self._positions.copy()

    def get_joint_velocities(self):
        return self._velocities.copy()

    def get_applied_joint_efforts(self):
        return self._efforts.copy()

    def apply_action(self, action):
        """Capture position/velocity targets from ArticulationAction."""
        if getattr(action, "joint_positions", None) is not None:
            self._last_position_targets = np.array(action.joint_positions, dtype=np.float64)
        if getattr(action, "joint_velocities", None) is not None:
            self._last_velocity_targets = np.array(action.joint_velocities, dtype=np.float64)

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
    handle._initialized = True
    handle._name = "robot_test"
    return handle


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
