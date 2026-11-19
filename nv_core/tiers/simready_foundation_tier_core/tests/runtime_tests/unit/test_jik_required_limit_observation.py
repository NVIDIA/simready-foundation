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
"""Required JIK stop observations cannot become unlimited fallback probes."""

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases.jik_solver import JacobianIKSolver
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)


@pytest.mark.parametrize("properties", [None, [{"lower": -1.0, "upper": 1.0}]])
def test_present_native_limit_failure_propagates_before_any_probe(properties):
    calls, writes = [], []

    class Robot:
        dof_names = ["joint"]
        dof_properties = properties

        def get_joint_position_limits(self):
            calls.append("limits")
            raise RuntimeError("native joint-limit view is unavailable")

        def set_joint_positions(self, value):
            writes.append(value)

    with pytest.raises(RequiredReadbackError, match="required joint-limit readback") as caught:
        JacobianIKSolver(Robot(), "/tool")
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert calls == ["limits"] and writes == []


def test_transient_limit_view_failure_is_not_hidden_by_an_earlier_success():
    calls = []

    def limits():
        calls.append("limits")
        if len(calls) == 1:
            return np.array([-1.0]), np.array([1.0])
        raise RuntimeError("native view was invalidated after applicability")

    robot = SimpleNamespace(dof_names=["joint"], get_joint_position_limits=limits)
    robot.get_joint_position_limits()  # Same earlier read made by the phase.
    with pytest.raises(RequiredReadbackError, match="required joint-limit readback"):
        JacobianIKSolver(robot, "/tool")
    assert calls == ["limits", "limits"]


@pytest.mark.parametrize(
    "limits",
    [
        (None, None),
        ([], []),
        ([False], [1.0]),
        (["-1"], [1.0]),
        ([np.nan], [1.0]),
        ([-1.0], [np.nan]),
        ([2.0], [1.0]),
        ([np.inf], [np.inf]),
        ([-np.inf], [-np.inf]),
        ([-1.0, -1.0], [1.0, 1.0]),
        (np.array([-1.0], dtype=object), [1.0]),
    ],
)
def test_malformed_active_limits_are_required_errors(limits):
    robot = SimpleNamespace(dof_names=["joint"], get_joint_position_limits=lambda: limits)
    with pytest.raises(RequiredReadbackError, match="required joint-limit readback"):
        JacobianIKSolver(robot, "/tool")


def test_missing_accessor_requires_observed_property_limits():
    with pytest.raises(RequiredReadbackError, match="required joint-limit readback"):
        JacobianIKSolver(SimpleNamespace(dof_names=["joint"]), "/tool")
    robot = SimpleNamespace(dof_names=["joint"], dof_properties=[{"lower": -2.0, "upper": 3.0}])
    solver = JacobianIKSolver(robot, "/tool")
    assert solver._lower_limits.tolist() == [-2.0]
    assert solver._upper_limits.tolist() == [3.0]


@pytest.mark.parametrize("bad", [True, "1", np.bool_(False), np.nan])
def test_mapping_property_stops_are_not_float_coerced_into_real_evidence(bad):
    robot = SimpleNamespace(dof_names=["joint"], dof_properties=[{"lower": bad, "upper": 3.0}])
    with pytest.raises(RequiredReadbackError, match="required joint-limit readback"):
        JacobianIKSolver(robot, "/tool")


@pytest.mark.parametrize("limits", [([-np.inf], [np.inf]), ([0.25], [0.25]), ([-1.0], [1.0])])
def test_explicit_signed_unlimited_or_locked_limits_remain_valid(limits):
    solver = JacobianIKSolver(SimpleNamespace(dof_names=["joint"], get_joint_position_limits=lambda: limits), "/tool")
    np.testing.assert_array_equal(solver._lower_limits, limits[0])
    np.testing.assert_array_equal(solver._upper_limits, limits[1])
