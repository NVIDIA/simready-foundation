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
"""Tests for ik_target_reach pure helpers.

The full Kit-side phase needs a stage + articulation + Lula descriptor and
is exercised only by the manual smoke run. These unit tests cover the pure
module-level helpers that ship with the phase: defaults, aggregate
summary, Lula robot-name lookup, EE-candidate lookup.
"""

import math
from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    ik_target_reach,
    required_readback,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.ik_target_reach import (
    _precompute_ik_solutions,
    _teleport_to_joints,
    aggregate_ik_summary,
    default_ee_candidates,
    expand_ik_action,
    get_defaults,
    run_ik_target_reach,
    select_lula_robot_name,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import RobotType


class _HostBoundaryTensor:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def detach(self):
        self.calls.append("detach")
        return self

    def cpu(self):
        self.calls.append("cpu")
        return self

    def numpy(self):
        self.calls.append("numpy")
        return self.values


def _make_host_boundary_articulation(joints, position):
    calls = {"fk": [], "ik": []}

    def forward(frame, values, **kwargs):
        calls["fk"].append(values.copy())
        return position, np.array([1.0, 0.0, 0.0, 0.0])

    def inverse(frame, target, orientation, warm_start, position_tolerance, orientation_tolerance):
        calls["ik"].append(warm_start.copy())
        return np.array([0.1, 0.2, 0.3]), True

    subset = SimpleNamespace(
        get_joint_positions=lambda: joints,
        make_articulation_action=lambda values, velocities: SimpleNamespace(joint_positions=values),
    )
    kinematics = SimpleNamespace(compute_forward_kinematics=forward, compute_inverse_kinematics=inverse)
    articulation = SimpleNamespace(
        get_joints_subset=lambda: subset,
        get_kinematics_solver=lambda: kinematics,
        get_end_effector_frame=lambda: "tip",
    )
    return articulation, calls


@pytest.mark.parametrize(
    "values",
    [
        np.array([True, False, True]),
        np.array(["0", "1", "2"]),
        np.array([0, 1, 2], dtype=object),
        np.array([complex(0, 1), 0, 0]),
        np.array([complex(0, math.inf), 0, 0]),
    ],
)
@pytest.mark.parametrize("boundary", ["fk_joints", "fk_position", "ik_warm_start"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_lula_host_boundary_rejects_malformed_dtype_before_numeric_conversion(values, boundary, wrapped):
    backend = _HostBoundaryTensor(values) if wrapped else values
    joints = backend if boundary != "fk_position" else np.array([0.0, 0.1, 0.2])
    position = backend if boundary == "fk_position" else np.array([1.0, 2.0, 3.0])
    articulation, calls = _make_host_boundary_articulation(joints, position)
    with pytest.raises(required_readback.RequiredReadbackError):
        if boundary == "ik_warm_start":
            ik_target_reach._compute_inverse_kinematics_host(articulation, np.zeros(3), 0.01, 0.1)
        else:
            ik_target_reach._compute_end_effector_pose_host(articulation)
    assert len(calls["fk"]) == (1 if boundary == "fk_position" else 0)
    assert calls["ik"] == []
    if wrapped:
        assert backend.calls == ["detach", "cpu", "numpy"]


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.uint32])
@pytest.mark.parametrize("wrapped", [False, True])
def test_lula_host_boundary_keeps_backend_copy_and_qualified_numeric_float64_contract(dtype, wrapped):
    values = np.array([0, 1, 2], dtype=dtype)
    backend = _HostBoundaryTensor(values) if wrapped else values
    host = ik_target_reach._host_array(backend)
    assert host is values and host.dtype == values.dtype
    if wrapped:
        assert backend.calls == ["detach", "cpu", "numpy"]
        backend.calls.clear()
    articulation, calls = _make_host_boundary_articulation(backend, backend)
    position, _ = ik_target_reach._compute_end_effector_pose_host(articulation)
    action, success = ik_target_reach._compute_inverse_kinematics_host(articulation, np.zeros(3), 0.01, 0.1)
    assert success and action.joint_positions.shape == (3,)
    np.testing.assert_array_equal(position, values)
    assert position.dtype == np.float64
    assert calls["fk"][0].dtype == np.float64 and calls["ik"][0].dtype == np.float64
    np.testing.assert_array_equal(calls["fk"][0], values)
    np.testing.assert_array_equal(calls["ik"][0], values)
    np.testing.assert_array_equal(values, [0, 1, 2])
    if wrapped:
        assert backend.calls == ["detach", "cpu", "numpy"] * 3


@pytest.mark.parametrize(
    "asset,expected",
    [
        ("factory_ur3e.usd", "UR3e"),
        ("robot_ur5e", "UR5e"),
        ("robot_ur10e", "UR10e"),
        ("robot_fr3", "FR3"),
        ("robot_panda", "Franka"),
        ("UR300", None),
        ("frankalog", None),
    ],
)
def test_model_names_match_tokens_not_prefixes(asset, expected):
    assert select_lula_robot_name(None, asset, None) == expected


def test_expand_indexed_action_preserves_non_commanded_dofs():
    current = np.array([0.1, 0.2, 0.3])
    action = SimpleNamespace(joint_positions=[0.7, 0.9], joint_indices=np.array([2, 0], dtype=np.int32))
    assert np.allclose(expand_ik_action(action, current), [0.9, 0.2, 0.7])
    assert np.allclose(current, [0.1, 0.2, 0.3])


@pytest.mark.parametrize("indices", [[True, False], [False, 1], [0.0, 1.0], [0, 0], [-1, 1], [0, 3], [[0, 1]]])
def test_expand_action_rejects_invalid_indices(indices):
    with pytest.raises(RuntimeError, match="indices"):
        expand_ik_action(SimpleNamespace(joint_positions=[0.2, 0.3], joint_indices=indices), [0, 0, 0])


@pytest.mark.parametrize("current,positions", [([0, float("nan")], [0.2]), ([0, 0], [float("inf")]), ([[0, 0]], [0.2])])
def test_expand_action_requires_finite_full_current_and_solver_vectors(current, positions):
    with pytest.raises(RuntimeError, match="runtime error"):
        expand_ik_action(SimpleNamespace(joint_positions=positions, joint_indices=[0]), current)


def test_full_action_requires_all_dofs():
    with pytest.raises(RuntimeError, match="DOF count"):
        expand_ik_action(SimpleNamespace(joint_positions=[0.2], joint_indices=None), [0, 0])


@pytest.mark.asyncio
async def test_teleport_synchronizes_target_and_velocity_before_stepping():
    calls = []

    async def step():
        calls.append("step")

    robot = SimpleNamespace(
        dof_names=["a", "b"],
        set_joint_positions=lambda value: calls.append(("positions", value.copy())),
        set_joint_position_targets=lambda value: calls.append(("targets", value.copy())),
        set_joint_velocities=lambda value: calls.append(("velocities", value.copy())),
    )
    await _teleport_to_joints(robot, [0.2, 0.3], SimpleNamespace(step_one=step), 1)
    assert [item[0] if isinstance(item, tuple) else item for item in calls] == [
        "positions",
        "targets",
        "velocities",
        "step",
    ]
    assert np.array_equal(calls[0][1], calls[1][1]) and np.array_equal(calls[2][1], [0, 0])


@pytest.mark.asyncio
async def test_precompute_restores_reference_after_required_state_failure(monkeypatch):
    from simready.foundation.tier_core.runtime_tests.articulation_phases import (
        ik_target_reach as phase,
    )

    writes = []

    async def fail(*args):
        raise RuntimeError("original solver state failure")

    async def step():
        pass

    robot = SimpleNamespace(
        dof_names=["joint"],
        set_joint_positions=lambda value: writes.append(value.copy()),
        set_joint_position_targets=lambda value: None,
        set_joint_velocities=lambda value: None,
    )
    monkeypatch.setattr(phase, "_precompute_ik_solutions_impl", fail)
    with pytest.raises(RuntimeError, match="original solver state failure"):
        await _precompute_ik_solutions(SimpleNamespace(step_one=step), robot, None, [], 0.01, 0.01, np.array([0.4]))
    assert np.array_equal(writes[-1], [0.4])


@pytest.mark.asyncio
async def test_ik_skips_validated_driven_joint_gripper_contract_before_lula_setup():
    ctx = SimpleNamespace(
        asset_validated_features=["FET022_DrivenJoints.PhysX.0-2-0", "FET028_Gripper.Isaac.0-1-0"],
        skip_message=None,
        add_metric=lambda name, value: None,
    )
    ctx.skip = lambda message: setattr(ctx, "skip_message", message)
    robot = SimpleNamespace(dof_count=1)

    await run_ik_target_reach(
        ctx,
        robot,
        scene_info={"robot_type": RobotType.ARM, "has_gripper_signals": False},
        config={},
    )

    assert "not applicable to standalone grippers" in ctx.skip_message


# --- get_defaults shape ---


def test_get_defaults_shape():
    """All required defaults are present and well-typed."""
    d = get_defaults()
    # JIK-mirroring keys
    assert d["num_reachable_targets"] == 5
    assert d["num_out_of_reach_targets"] == 2
    assert d["radius_factors"] == [0.5, 0.7, 0.9]
    assert d["out_of_reach_factor"] == 1.3
    assert d["hemisphere_only"] is True
    assert d["position_tolerance"] == 0.02
    assert d["orientation_tolerance"] == 0.25
    assert d["min_success_rate"] == 0.5
    assert d["physics_fps"] == 240.0
    assert d["capture_fps"] == 8
    # Lula-specific overrides default to None.
    assert d["lula_robot_name"] is None
    assert d["lula_yaml_path"] is None
    assert d["lula_urdf_path"] is None


def test_get_defaults_returns_fresh_dict():
    """Defaults are not memoized: callers get an independent dict."""
    a = get_defaults()
    a["physics_fps"] = 60.0
    b = get_defaults()
    assert b["physics_fps"] == 240.0


# --- aggregate_ik_summary ---


def test_aggregate_ik_summary_all_pass():
    per_target = [
        {"index": 0, "ok": True, "reachable": True, "pos_error": 0.005},
        {"index": 1, "ok": True, "reachable": True, "pos_error": 0.012},
        {"index": 2, "ok": True, "reachable": True, "pos_error": 0.008},
    ]
    s = aggregate_ik_summary(per_target)
    assert s["targets_total"] == 3
    assert s["targets_reachable"] == 3
    assert s["targets_out_of_reach"] == 0
    assert s["targets_passed"] == 3
    assert s["targets_failed"] == 0
    assert s["in_reach_passed"] == 3
    assert s["in_reach_failed"] == 0
    assert s["failed_indices"] == []
    assert s["pass_rate"] == 1.0
    assert abs(s["max_position_error_m"] - 0.012) < 1e-9


def test_aggregate_ik_summary_mixed():
    """Partial failures + out-of-reach targets contribute correctly."""
    per_target = [
        {"index": 0, "ok": True, "reachable": True, "pos_error": 0.01},
        {"index": 1, "ok": False, "reachable": True, "pos_error": 0.5},
        {"index": 2, "ok": True, "reachable": False, "pos_error": float("inf")},
        {"index": 3, "ok": False, "reachable": False, "pos_error": float("inf")},
        {"index": 4, "ok": True, "reachable": True, "pos_error": 0.015},
    ]
    s = aggregate_ik_summary(per_target)
    assert s["targets_total"] == 5
    assert s["targets_reachable"] == 3
    assert s["targets_out_of_reach"] == 2
    assert s["targets_passed"] == 3
    assert s["targets_failed"] == 2
    assert s["in_reach_passed"] == 2
    assert s["in_reach_failed"] == 1
    assert s["failed_indices"] == [1, 3]
    # max_position_error_m ignores +inf entries.
    assert abs(s["max_position_error_m"] - 0.5) < 1e-9
    # 2 of 3 reachable passed.
    assert abs(s["pass_rate"] - (2.0 / 3.0)) < 1e-9


def test_aggregate_ik_summary_empty():
    s = aggregate_ik_summary([])
    assert s["targets_total"] == 0
    assert s["targets_reachable"] == 0
    assert s["targets_out_of_reach"] == 0
    assert s["targets_passed"] == 0
    assert s["targets_failed"] == 0
    assert s["pass_rate"] == 0.0
    assert s["max_position_error_m"] == 0.0
    assert s["failed_indices"] == []


def test_aggregate_ik_summary_all_unreachable():
    """Out-of-reach-only batch yields 0.0 pass_rate (no in-reach denominator)."""
    per_target = [
        {"index": 0, "ok": True, "reachable": False, "pos_error": float("inf")},
        {"index": 1, "ok": False, "reachable": False, "pos_error": float("inf")},
    ]
    s = aggregate_ik_summary(per_target)
    assert s["targets_reachable"] == 0
    assert s["pass_rate"] == 0.0
    assert s["targets_passed"] == 1
    assert s["targets_failed"] == 1
    # No finite errors -> 0.0
    assert s["max_position_error_m"] == 0.0


def test_aggregate_ik_summary_handles_bad_pos_error():
    """Non-numeric / NaN pos_error values do not crash the helper."""
    per_target = [
        {"index": 0, "ok": True, "reachable": True, "pos_error": float("nan")},
        {"index": 1, "ok": False, "reachable": True, "pos_error": "not-a-number"},
        {"index": 2, "ok": True, "reachable": True, "pos_error": 0.02},
    ]
    s = aggregate_ik_summary(per_target)
    # Only the 0.02 entry is finite -> max_err is 0.02.
    assert math.isfinite(s["max_position_error_m"])
    assert abs(s["max_position_error_m"] - 0.02) < 1e-9


# --- select_lula_robot_name ---


def test_select_lula_robot_name_known_via_asset_name():
    # Asset path containing "Franka" matches the canonical "Franka" entry.
    assert (
        select_lula_robot_name(
            robot_type_name="ARM",
            asset_name="/assets/robots/Franka_Panda/franka.usd",
            override=None,
        )
        == "Franka"
    )


def test_select_lula_robot_name_known_via_robot_type():
    # No asset hit, but the robot type name contains "UR10".
    assert (
        select_lula_robot_name(
            robot_type_name="UR10_arm",
            asset_name="/assets/robots/generic.usd",
            override=None,
        )
        == "UR10"
    )


def test_select_lula_robot_name_override_wins():
    """An explicit override bypasses the lookup table even on a known asset."""
    assert (
        select_lula_robot_name(
            robot_type_name="ARM",
            asset_name="/assets/robots/Franka_Panda/franka.usd",
            override="CustomRobot",
        )
        == "CustomRobot"
    )


def test_select_lula_robot_name_unknown_returns_none():
    assert (
        select_lula_robot_name(
            robot_type_name="SCARA",
            asset_name="/assets/robots/sr12ia.usd",
            override=None,
        )
        is None
    )


def test_select_lula_robot_name_empty_inputs():
    """Empty strings and Nones are tolerated."""
    assert select_lula_robot_name(None, None, None) is None
    assert select_lula_robot_name("", "", "") is None


def test_select_lula_robot_name_case_insensitive():
    """Lowercase asset names still match the canonical capitalized entry."""
    assert (
        select_lula_robot_name(
            robot_type_name=None,
            asset_name="/assets/franka_panda.usd",  # lowercase
            override=None,
        )
        == "Franka"
    )


# --- default_ee_candidates ---


def test_default_ee_candidates():
    """Returns the canonical generic list (same for every robot)."""
    candidates = default_ee_candidates("Franka")
    assert isinstance(candidates, list)
    # Known v1 candidates must be present.
    assert "ee_link" in candidates
    assert "tool0" in candidates
    assert "tcp" in candidates
    assert "flange" in candidates
    assert "panda_hand" in candidates
    # Unknown robots get the same list.
    assert default_ee_candidates("Mystery_Robot_9000") == candidates
    # And a None robot_name still works.
    assert default_ee_candidates(None) == candidates


def test_default_ee_candidates_returns_fresh_list():
    """Caller can mutate the returned list without affecting subsequent calls."""
    a = default_ee_candidates("Franka")
    a.append("custom_ee")
    b = default_ee_candidates("Franka")
    assert "custom_ee" not in b
