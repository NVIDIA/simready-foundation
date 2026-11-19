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
"""Raw sequence promotion cannot invent valid joint observations or commands."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach,
    required_readback,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import RobotHandle


class _BackendValues:
    def __init__(self, values):
        self.values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.values


@pytest.mark.parametrize("boolean", [True, False, np.bool_(True), np.bool_(False)])
@pytest.mark.parametrize("container", [list, tuple])
def test_mixed_raw_boolean_vector_is_not_required_evidence(boolean, container):
    values = container([0.25, boolean])
    with pytest.raises(required_readback.RequiredReadbackError) as error:
        required_readback.require_vector(values, "IK", "joint position", 2)
    assert isinstance(error.value.__cause__, ValueError)
    assert "boolean coordinates" in str(error.value.__cause__)


@pytest.mark.parametrize("boolean", [True, np.bool_(False)])
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("batched", [False, True])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["required_positions", "required_velocities", "get_joint_position_targets"])
def test_mixed_raw_or_backend_wrapped_joint_rows_stay_unavailable(boolean, wrapped, batched, native, method):
    values = [[0.25, boolean]] if batched else [0.25, boolean]
    backend = _BackendValues(values) if wrapped else values
    robot = RobotHandle.__new__(RobotHandle)
    robot._articulation = SimpleNamespace(
        dof_names=["a", "b"],
        get_joint_positions=lambda: backend,
        get_joint_velocities=lambda: backend,
        get_joint_position_targets=lambda: backend,
    )
    robot._newton_actuators = (
        SimpleNamespace(
            articulation=SimpleNamespace(
                dof_paths=[["/Robot/b", "/Robot/a"]],
                get_dof_positions=lambda: backend,
                get_dof_velocities=lambda: backend,
                get_dof_position_targets=lambda: backend,
            )
        )
        if native
        else None
    )
    if method == "get_joint_position_targets":
        assert np.isnan(robot.get_joint_position_targets()).all()
    else:
        with pytest.raises(required_readback.RequiredReadbackError):
            getattr(required_readback, method)(robot, "raw adapter")
    assert (values[-1][-1] if batched else values[-1]) is boolean


@pytest.mark.parametrize("boolean", [True, np.bool_(False)])
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("boundary", ["fk_joints", "fk_position", "warm_start"])
def test_lula_host_copy_rejects_mixed_raw_booleans_before_kinematics(boolean, wrapped, boundary):
    values = [0.25, boolean, 0.5]
    backend = _BackendValues(values) if wrapped else values
    calls = []

    def forward(frame, joints, **kwargs):
        calls.append("fk")
        return backend if boundary == "fk_position" else np.zeros(3), np.array([1, 0, 0, 0])

    def inverse(*args):
        calls.append("ik")
        return np.zeros(3), True

    articulation = SimpleNamespace(
        get_joints_subset=lambda: SimpleNamespace(
            get_joint_positions=lambda: backend if boundary != "fk_position" else np.zeros(3),
            make_articulation_action=lambda positions, velocities: SimpleNamespace(joint_positions=positions),
        ),
        get_kinematics_solver=lambda: SimpleNamespace(
            compute_forward_kinematics=forward, compute_inverse_kinematics=inverse
        ),
        get_end_effector_frame=lambda: "tip",
    )
    with pytest.raises(required_readback.RequiredReadbackError):
        if boundary == "warm_start":
            ik_target_reach._compute_inverse_kinematics_host(articulation, np.zeros(3), 0.01, 0.1)
        else:
            ik_target_reach._compute_end_effector_pose_host(articulation)
    assert calls == (["fk"] if boundary == "fk_position" else [])


@pytest.mark.parametrize(
    "values",
    [
        [np.array([True, False]), np.array([0.25, 0.5])],
        [np.array([0.25, 0.5]), np.array([True, False])],
    ],
)
def test_nested_boolean_typed_rows_cannot_promote_to_real_backend_arrays(values):
    with pytest.raises(ValueError):
        required_readback.as_real_array(values)
    assert required_readback.as_real_array([[0.25, 0.5]]).shape == (1, 2)


@pytest.mark.parametrize("dtype", [np.int32, np.uint32, np.float32, np.float64])
def test_typed_numeric_arrays_and_raw_numeric_lists_keep_their_contract(dtype):
    values = np.array([1, 2], dtype=dtype)
    assert required_readback.as_real_array(values) is values
    assert required_readback.require_vector(values, "IK", "joint position", 2) is values
    np.testing.assert_array_equal(required_readback.require_vector([1, 0.25], "IK", "joint position", 2), [1, 0.25])


def test_aliased_numeric_rows_remain_valid_and_cyclic_sequences_do_not_loop():
    row = [0.25, 0.5]
    np.testing.assert_array_equal(required_readback.as_real_array([row, row]), [row, row])
    cycle = [0.25]
    cycle.append(cycle)
    with pytest.raises(required_readback.RequiredReadbackError):
        required_readback.require_vector(cycle, "IK", "joint position", 2)


@pytest.mark.parametrize("boolean", [True, np.bool_(False)])
@pytest.mark.parametrize("wrapped", [False, True])
def test_mixed_live_link_pose_cannot_become_a_numeric_observation(boolean, wrapped):
    values = [[[0.25, boolean, 0.5, 0, 0, 0, 1]]]
    backend = _BackendValues(values) if wrapped else values
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Robot/tip")
    robot = RobotHandle.__new__(RobotHandle)
    robot._stage = stage
    robot._newton_actuators = None
    robot._articulation = SimpleNamespace(
        body_names=["tip"], _physics_view=SimpleNamespace(get_link_transforms=lambda: backend)
    )
    with pytest.raises(required_readback.RequiredReadbackError):
        required_readback.required_link_pose(robot, "/Robot/tip", "IK")


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_indexed_precompute_restores_after_error_or_cancellation(monkeypatch, error_type):
    reference = np.array([0.1, 0.2, 0.3])
    writes = []
    original = error_type("original failure")

    async def failed(*args):
        writes.append(np.array([0.5, 0.6, 0.7]))
        raise original

    async def step():
        pass

    robot = SimpleNamespace(
        dof_names=["a", "b", "c"],
        dof_count=3,
        get_joint_positions=lambda: reference.copy(),
        set_joint_positions=lambda value: writes.append(value.copy()),
        set_joint_position_targets=lambda value: None,
        set_joint_velocities=lambda value: None,
    )
    monkeypatch.setattr(ik_target_reach, "_precompute_ik_solutions_impl", failed)
    with pytest.raises(error_type) as caught:
        await ik_target_reach._precompute_ik_solutions(
            SimpleNamespace(step_one=step), robot, None, [], 0.01, 0.1, reference
        )
    assert caught.value is original
    np.testing.assert_array_equal(writes[-1], reference)


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_failed_precompute_restoration_retains_the_original_error(monkeypatch, error_type):
    original = error_type("original failure")

    async def failed(*args):
        raise original

    async def failed_restore(*args, **kwargs):
        raise RuntimeError("restoration failed")

    monkeypatch.setattr(ik_target_reach, "_precompute_ik_solutions_impl", failed)
    monkeypatch.setattr(ik_target_reach, "_teleport_to_joints", failed_restore)
    with pytest.raises(error_type) as caught:
        await ik_target_reach._precompute_ik_solutions(None, None, None, [], 0.01, 0.1, np.array([0.1]))
    assert caught.value is original
    assert "restoration failed" in "; ".join(original.__notes__)


@pytest.mark.asyncio
@pytest.mark.parametrize("boolean", [True, np.bool_(False)])
async def test_indexed_lula_precompute_never_dispatches_a_mixed_boolean_solution(boolean):
    reference = np.array([0.1, 0.2, 0.3])
    writes = []
    ticks = []

    async def step():
        ticks.append(None)

    robot = SimpleNamespace(
        dof_names=["a", "finger", "b"],
        dof_count=3,
        get_joint_positions=lambda: reference.copy(),
        set_joint_positions=lambda positions: writes.append(("positions", positions.copy())),
        set_joint_position_targets=lambda positions: writes.append(("targets", positions.copy())),
        set_joint_velocities=lambda positions: writes.append(("velocities", positions.copy())),
    )
    subset = SimpleNamespace(
        get_joint_positions=lambda: reference.copy(),
        make_articulation_action=lambda positions, velocities: SimpleNamespace(
            joint_positions=positions, joint_indices=[2, 0]
        ),
    )
    articulation = SimpleNamespace(
        get_joints_subset=lambda: subset,
        get_kinematics_solver=lambda: SimpleNamespace(
            compute_inverse_kinematics=lambda *args: ([boolean, 0.9], True),
        ),
        get_end_effector_frame=lambda: "tip",
    )
    context = SimpleNamespace(step_one=step, step=lambda message: None, warn=lambda message: None)
    target = SimpleNamespace(index=0, position=np.zeros(3), is_reachable=True)
    with pytest.raises(required_readback.RequiredReadbackError):
        await ik_target_reach._precompute_ik_solutions(context, robot, articulation, [target], 0.01, 0.1, reference)
    # Existing initial/reference restoration runs; no solution command executes.
    assert len(ticks) == 6
    for operation, positions in writes:
        np.testing.assert_array_equal(positions, np.zeros(3) if operation == "velocities" else reference)
    np.testing.assert_array_equal(reference, [0.1, 0.2, 0.3])


@pytest.mark.asyncio
async def test_real_indexed_lula_precompute_preserves_uncommanded_state_and_restores_reference():
    reference = np.array([0.1, 0.2, 0.3])
    writes = []
    written_indices = []

    def indexed_positions(values, indices):
        written_indices.append(list(indices))
        full = reference.copy()
        full[indices] = values
        writes.append(full)

    async def step():
        pass

    robot = SimpleNamespace(
        dof_names=["a", "finger", "b"],
        dof_count=3,
        get_joint_positions=lambda: reference.copy(),
        set_joint_positions=lambda positions: writes.append(positions.copy()),
        set_joint_position_targets=lambda positions: None,
        set_joint_velocities=lambda velocities: None,
        set_joint_positions_indexed=indexed_positions,
        set_joint_position_targets_indexed=lambda values, indices: None,
        set_joint_velocities_indexed=lambda values, indices: None,
    )
    subset = SimpleNamespace(
        get_joint_positions=lambda: reference.copy(),
        get_joint_subset_indices=lambda: [2, 0],
        make_articulation_action=lambda positions, velocities: SimpleNamespace(
            joint_positions=positions, joint_indices=[2, 0]
        ),
    )
    articulation = SimpleNamespace(
        get_joints_subset=lambda: subset,
        get_kinematics_solver=lambda: SimpleNamespace(
            compute_inverse_kinematics=lambda *args: ([0.7, 0.9], True),
            compute_forward_kinematics=lambda *args, **kwargs: (np.zeros(3), np.array([1, 0, 0, 0])),
        ),
        get_end_effector_frame=lambda: "tip",
    )
    context = SimpleNamespace(
        step_one=step, step=lambda message: None, warn=lambda message: None, log=lambda message: None
    )
    target = SimpleNamespace(index=0, position=np.zeros(3), is_reachable=True)
    robot = ik_target_reach._lula_controlled_robot(robot, articulation, {})
    solutions, metrics = await ik_target_reach._precompute_ik_solutions(
        context, robot, articulation, [target], 0.01, 0.1, reference
    )
    assert metrics["precompute_success"] == 1 and len(solutions) == 1
    np.testing.assert_array_equal(writes[1], [0.9, 0.2, 0.7])
    np.testing.assert_array_equal(writes[-1], reference)
    assert all(indices == [0, 2] for indices in written_indices)
    assert solutions[0].command_indices == [2, 0]
