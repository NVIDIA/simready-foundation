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

"""Effort observations distinguish unavailable evidence from genuine zeros."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases.robot_handle import RobotHandle


def _robot(native):
    robot = RobotHandle.__new__(RobotHandle)
    robot._articulation = native
    robot._newton_actuators = None
    return robot


@pytest.mark.parametrize("declared_none", [False, True])
def test_missing_native_effort_getter_returns_explicit_unavailable(declared_none):
    native = SimpleNamespace(dof_names=["a", "b"])
    if declared_none:
        native.get_applied_joint_efforts = None
    assert _robot(native).get_applied_joint_efforts() is None


@pytest.mark.parametrize(
    "values",
    [
        None,
        [False, True],
        [0, True],
        np.array([False, True]),
        ["0", "1"],
        np.array(["0", "1"]),
        [1j, 2j],
        np.array([1, 2], dtype=object),
        0.0,
        [],
        [0.0],
        [[0.0], [0.0]],
        [[0.0, 0.0], [0.0, 0.0]],
    ],
)
def test_missing_or_malformed_effort_result_does_not_become_valid_zero_evidence(values):
    robot = _robot(SimpleNamespace(dof_names=["a", "b"], get_applied_joint_efforts=lambda: values))
    result = robot.get_applied_joint_efforts()
    assert result.shape == (2,)
    assert np.isnan(result).all()


@pytest.mark.parametrize(
    "values",
    [[0, 0], [0.0, 0.0], np.zeros(2, dtype=np.float32), np.zeros((1, 2)), [1.25, -2.5]],
)
def test_real_numeric_efforts_preserve_values_and_single_row_shape(values):
    robot = _robot(SimpleNamespace(dof_names=["a", "b"], get_applied_joint_efforts=lambda: values))
    result = robot.get_applied_joint_efforts()
    assert result.shape == (2,)
    np.testing.assert_array_equal(result, np.asarray(values).reshape(2))


@pytest.mark.parametrize("native_bridge", [False, True])
@pytest.mark.parametrize("error_class", [RuntimeError, asyncio.CancelledError])
def test_native_effort_errors_and_cancellation_propagate_unchanged(native_bridge, error_class):
    error = error_class("native effort read failed")

    def failed_read():
        raise error

    robot = _robot(SimpleNamespace(dof_names=["a", "b"], get_applied_joint_efforts=failed_read))
    if native_bridge:
        robot._newton_actuators = SimpleNamespace(articulation=SimpleNamespace(get_dof_efforts=failed_read))
    with pytest.raises(error_class) as caught:
        robot.get_applied_joint_efforts()
    assert caught.value is error
