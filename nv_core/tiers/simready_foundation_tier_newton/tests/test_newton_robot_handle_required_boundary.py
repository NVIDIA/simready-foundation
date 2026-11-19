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
"""Required evidence keeps invalid dtype and shape across the backend adapter."""

import warnings
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom
from simready.foundation.tier_newton.runtime_tests.articulation_phases import required_readback
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import RobotHandle


class _BackendValues:
    def __init__(self, values):
        self.values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.values


def _wrapped(values, wrapped):
    return _BackendValues(values) if wrapped else values


def _handle(values, native=False, count=2):
    names = [chr(ord("a") + index) for index in range(count)]
    robot = RobotHandle.__new__(RobotHandle)
    robot._articulation = SimpleNamespace(
        dof_names=names,
        get_joint_positions=lambda: values,
        get_joint_velocities=lambda: values,
    )
    robot._newton_actuators = (
        SimpleNamespace(
            articulation=SimpleNamespace(
                dof_paths=[["/Robot/" + name for name in reversed(names)]],
                get_dof_positions=lambda: values,
                get_dof_velocities=lambda: values,
            )
        )
        if native
        else None
    )
    return robot


INVALID_JOINT_SHAPES = [(2, 1), (2, 2), (1, 1, 2), (1, 2, 1)]


@pytest.mark.parametrize("shape", INVALID_JOINT_SHAPES)
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["required_positions", "required_velocities"])
def test_nonqualified_backend_joint_shapes_never_become_required_vectors(shape, wrapped, native, method):
    count = int(np.prod(shape))
    values = np.arange(1, count + 1, dtype=np.float64).reshape(shape)
    robot = _handle(_wrapped(values, wrapped), native, count)
    with pytest.raises(required_readback.RequiredReadbackError, match="criterion was not evaluated"):
        getattr(required_readback, method)(robot, "backend shape boundary")
    assert np.isnan(robot.get_joint_positions()).all()
    np.testing.assert_array_equal(values, np.arange(1, count + 1).reshape(shape))


def _with_position_targets(robot, values):
    robot._articulation.get_joint_position_targets = lambda: values
    if robot._newton_actuators is not None:
        robot._newton_actuators.articulation.get_dof_position_targets = lambda: values
    return robot


@pytest.mark.parametrize("shape", INVALID_JOINT_SHAPES)
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("native", [False, True])
def test_nonqualified_backend_target_shapes_remain_unavailable(shape, wrapped, native):
    count = int(np.prod(shape))
    values = _wrapped(np.arange(1, count + 1, dtype=np.float64).reshape(shape), wrapped)
    robot = _with_position_targets(_handle(values, native, count), values)
    assert np.isnan(robot.get_joint_position_targets()).all()


@pytest.mark.parametrize("shape", [(2,), (1, 2)])
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["required_positions", "required_velocities", "get_joint_position_targets"])
def test_qualified_vector_and_single_articulation_rows_preserve_values(shape, wrapped, native, method):
    values = _wrapped(np.array([1.0, 2.0]).reshape(shape), wrapped)
    robot = _with_position_targets(_handle(values, native), values)
    if method == "get_joint_position_targets":
        result = robot.get_joint_position_targets()
    else:
        result = getattr(required_readback, method)(robot, "backend shape boundary")
    np.testing.assert_array_equal(result, [2.0, 1.0] if native else [1.0, 2.0])
    assert result.shape == (2,)


INVALID_DTYPES = ["bool", "string", "object", "complex", "complex_imaginary_infinity"]


def _invalid(values, kind):
    if kind == "bool":
        return np.asarray(values, dtype=bool)
    if kind == "string":
        return np.asarray(values, dtype=str)
    if kind == "object":
        return np.asarray(values, dtype=object)
    imaginary = float("inf") if kind == "complex_imaginary_infinity" else 0.0
    return np.asarray([complex(value, imaginary) for value in values], dtype=complex)


@pytest.mark.parametrize("kind", INVALID_DTYPES)
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["required_positions", "required_velocities"])
def test_malformed_backend_joint_reads_never_become_finite_required_evidence(kind, wrapped, native, method):
    values = _invalid([1.0, 2.0], kind)
    original = values.copy()
    robot = _handle(_wrapped(values, wrapped), native)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(required_readback.RequiredReadbackError, match="criterion was not evaluated"):
            getattr(required_readback, method)(robot, "backend boundary")
    assert not caught
    np.testing.assert_array_equal(values, original)
    assert np.isnan(robot.get_joint_positions()).all()


@pytest.mark.parametrize("dtype", [np.int32, np.uint32, np.float16, np.float32, np.float64])
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["required_positions", "required_velocities"])
def test_valid_numeric_backend_joint_reads_keep_values_and_native_order(dtype, wrapped, native, method):
    values = np.array([1.0, 2.0], dtype=dtype)
    robot = _handle(_wrapped(values, wrapped), native)
    result = getattr(required_readback, method)(robot, "backend boundary")
    np.testing.assert_array_equal(result, [2.0, 1.0] if native else [1.0, 2.0])
    assert result.dtype == np.float64
    np.testing.assert_array_equal(values, [1.0, 2.0])


def _pose_handle(values):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Robot/tip")
    robot = _handle(np.zeros(2))
    robot._stage = stage
    robot._articulation.body_names = ["tip"]
    robot._articulation._physics_view = SimpleNamespace(get_link_transforms=lambda: values)
    return robot


@pytest.mark.parametrize("kind", INVALID_DTYPES)
@pytest.mark.parametrize("wrapped", [False, True])
def test_malformed_backend_pose_rows_never_become_finite_required_evidence(kind, wrapped):
    values = _invalid([1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0], kind).reshape(1, 1, 7)
    robot = _pose_handle(_wrapped(values, wrapped))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(required_readback.RequiredReadbackError, match="criterion was not evaluated"):
            required_readback.required_link_pose(robot, "/Robot/tip", "backend boundary")
    assert not caught
    assert robot.get_link_world_transforms(["/Robot/tip"]) == {}


@pytest.mark.parametrize("dtype", [np.int32, np.uint32, np.float16, np.float32, np.float64])
@pytest.mark.parametrize("wrapped", [False, True])
def test_valid_numeric_backend_pose_rows_remain_usable(dtype, wrapped):
    values = np.array([[[1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0]]], dtype=dtype)
    robot = _pose_handle(_wrapped(values, wrapped))
    position, quaternion = required_readback.required_link_pose(robot, "/Robot/tip", "backend boundary")
    np.testing.assert_array_equal(position, [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(quaternion, [0.0, 0.0, 0.0, 1.0])


@pytest.mark.parametrize("kind", INVALID_DTYPES)
@pytest.mark.parametrize("wrapped", [False, True])
def test_malformed_applied_action_indices_are_not_treated_as_an_absent_index_vector(kind, wrapped):
    robot = _handle(np.zeros(2))
    robot._articulation.get_applied_action = lambda: SimpleNamespace(
        joint_positions=np.array([0.25, 0.75]),
        joint_indices=_wrapped(_invalid([0.0, 1.0], kind), wrapped),
    )
    assert np.isnan(robot.get_joint_position_targets()).all()


@pytest.mark.parametrize("wrapped", [False, True])
def test_applied_action_target_fallback_reorders_valid_full_permutation_indices(wrapped):
    robot = _handle(np.zeros(2))
    robot._articulation.get_applied_action = lambda: SimpleNamespace(
        joint_positions=_wrapped(np.array([0.75, 0.25]), wrapped),
        joint_indices=_wrapped(np.array([1, 0], dtype=np.int32), wrapped),
    )
    np.testing.assert_allclose(robot.get_joint_position_targets(), [0.25, 0.75])
