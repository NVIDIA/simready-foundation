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

"""Exercise the real cap adapter against its active frontend's tensor contract.

The external tensor boundary is a host double; no solver or native acceptance
claim is made. In Isaac's Torch frontend, move_data calls data.to(device=...).
"""

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import RobotHandle


class _Tensor:
    def __init__(self, values, device, dtype):
        self.values = np.asarray(values, dtype=dtype).copy()
        self.device = device

    def to(self, *, device):
        return _Tensor(self.values, device, self.values.dtype)

    def detach(self):
        return self

    def cpu(self):
        return self.values.copy()


class _Backend:
    def __init__(self, failing_dtype=None, error=None):
        self.failing_dtype = failing_dtype
        self.error = error

    def convert(self, values, device=None, dtype="float32"):
        if dtype == self.failing_dtype:
            raise self.error
        return _Tensor(values, device, dtype)


class _PhysicsView:
    def __init__(self):
        self.caps = np.array([[8.0, 9.0]], dtype=np.float32)
        self.writes = []

    def _values(self, values):
        # This operation reproduces the installed Torch move_data boundary.
        host = values.to(device="cpu").values
        assert values.device == "cuda:0"
        assert host.dtype == np.float32 and host.shape == (1, 2)
        return host

    def set_max_joint_velocities(self, values):
        self.caps = self._values(values).copy()
        self.writes.append("public")

    def set_dof_max_velocities(self, values, indices):
        host = self._values(values)
        host_indices = indices.to(device="cpu").values
        assert indices.device == "cuda:0" and host_indices.dtype == np.int32
        np.testing.assert_array_equal(host_indices, [0])
        self.caps = host.copy()
        self.writes.append("tensor")

    def get_dof_max_velocities(self):
        return _Tensor(self.caps, "cuda:0", "float32")


def _handle(path, backend):
    physics = _PhysicsView()
    view = SimpleNamespace(_physics_view=physics)
    art = SimpleNamespace(dof_names=["a", "b"], _articulation_view=view, _backend_utils=backend, _device="cuda:0")
    if path != "tensor":
        owner = art if path == "articulation" else view
        owner.set_max_joint_velocities = physics.set_max_joint_velocities
        owner.get_joint_max_velocities = physics.get_dof_max_velocities
    robot = RobotHandle(None, "/Robot", None, None)
    robot._articulation = art
    return robot, physics


@pytest.mark.parametrize("path", ["articulation", "view", "tensor"])
@pytest.mark.parametrize("unauthored", [False, True])
def test_real_handle_converts_caps_for_active_frontend_without_changing_requested_slots(path, unauthored):
    # Removing frontend conversion must fail before an external cap write.
    robot, physics = _handle(path, _Backend())
    limits = np.array([1.25, np.nan if unauthored else 2.5], dtype=np.float64)

    assert robot.apply_velocity_limits_to_tensor_view(limits) is True

    np.testing.assert_array_equal(physics.caps, [[1.25, 9.0 if unauthored else 2.5]])
    np.testing.assert_array_equal(limits, [1.25, np.nan if unauthored else 2.5])
    assert physics.writes == (["tensor"] if path == "tensor" else ["public"])


@pytest.mark.parametrize("failing_dtype", ["float32", "int32"])
def test_real_handle_propagates_frontend_conversion_failure_before_any_write(failing_dtype):
    primary = RuntimeError("frontend conversion unavailable")
    robot, physics = _handle("tensor", _Backend(failing_dtype, primary))

    with pytest.raises(RuntimeError) as caught:
        robot.apply_velocity_limits_to_tensor_view(np.array([1.25, 2.5]))

    assert caught.value is primary
    assert physics.writes == []
    np.testing.assert_array_equal(physics.caps, [[8.0, 9.0]])


def test_real_handle_keeps_first_public_failure_when_fallback_conversion_also_fails():
    primary = OSError("public setter unavailable")
    secondary = RuntimeError("fallback index conversion unavailable")
    robot, physics = _handle("view", _Backend("int32", secondary))

    def reject(values):
        raise primary

    robot._articulation._articulation_view.set_max_joint_velocities = reject

    with pytest.raises(OSError) as caught:
        robot.apply_velocity_limits_to_tensor_view(np.array([1.25, 2.5]))

    assert caught.value is primary
    assert physics.writes == []
    np.testing.assert_array_equal(physics.caps, [[8.0, 9.0]])


def test_real_handle_retains_numpy_tensor_fallback_without_backend_utilities():
    caps = np.array([[8.0, 9.0]], dtype=np.float32)

    def write(values, indices):
        assert values.dtype == np.float32 and values.shape == (1, 2)
        assert indices.dtype == np.int32
        np.testing.assert_array_equal(indices, [0])
        caps[:] = values

    physics = SimpleNamespace(set_dof_max_velocities=write, get_dof_max_velocities=lambda: caps.copy())
    robot = RobotHandle(None, "/Robot", None, None)
    robot._articulation = SimpleNamespace(dof_names=["a", "b"], _physics_view=physics)

    assert robot.apply_velocity_limits_to_tensor_view(np.array([1.25, 2.5])) is True
    np.testing.assert_array_equal(caps, [[1.25, 2.5]])
