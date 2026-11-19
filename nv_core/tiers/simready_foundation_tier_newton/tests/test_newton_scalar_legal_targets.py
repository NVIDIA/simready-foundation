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
"""Official Newton scalar dispatch uses observed native stops, not relative USD endpoint deltas."""

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from test_newton_fet004_joint_movement import joint_movement as _joint_movement_fixture


@pytest.fixture
def joint_movement(monkeypatch):
    return _joint_movement_fixture.__wrapped__(monkeypatch)


def _native_interface(monkeypatch, module, positions, limits, writes, cleanup):
    sdk = ModuleType("isaacsim.core.prims")
    names = ["positive_hinge", "negative_hinge", "slider"][: len(positions)]
    articulation = SimpleNamespace(
        dof_names=names,
        initialize=lambda: None,
        get_joint_positions=lambda: np.array(positions),
        get_joint_limits=lambda: limits,
        apply_action=lambda action: writes.append(action.joint_positions.copy()),
    )
    sdk.SingleArticulation = lambda **kwargs: articulation
    monkeypatch.setitem(sys.modules, "isaacsim.core.prims", sdk)
    types = ModuleType("isaacsim.core.utils.types")
    types.ArticulationAction = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "isaacsim.core.utils.types", types)
    monkeypatch.setattr(module, "_articulation_roots", lambda *_: ["/Asset"])
    monkeypatch.setattr(module, "_reset_transforms", lambda *_: None)
    monkeypatch.setattr(module, "activate_newton_position_drives", lambda *args, **kwargs: {"snapshot": True})
    monkeypatch.setattr(module, "restore_newton_position_drives", lambda *args, **kwargs: cleanup.append(args[-1]))
    monkeypatch.setattr(
        module,
        "JointTracker",
        lambda *_: SimpleNamespace(
            update=lambda: None,
            finish=lambda *_: None,
            record_capture=lambda *_: None,
        ),
    )


def _scene():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/Asset")
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)
    joints = []
    for name, schema, limits in (
        ("positive_hinge", UsdPhysics.RevoluteJoint, (0.0, 90.0)),
        ("negative_hinge", UsdPhysics.RevoluteJoint, (-120.0, 0.0)),
        ("slider", UsdPhysics.PrismaticJoint, (0.0, 40.0)),
    ):
        prim = schema.Define(stage, "/Asset/" + name)
        prim.CreateLowerLimitAttr(limits[0])
        prim.CreateUpperLimitAttr(limits[1])
        joints.append(
            {
                "name": name,
                "prim_path": str(prim.GetPath()),
                "type_name": prim.GetPrim().GetTypeName(),
                "child_body_path": "/Asset/body",
            }
        )
    return stage, joints


def _context():
    async def step(*args, **kwargs):
        return None

    return SimpleNamespace(
        step=lambda *_: None,
        settle=step,
        physics_step=step,
        physics_advance=step,
        capture_frame=step,
        scene=SimpleNamespace(update_camera_follow=lambda: None),
    )


def _run(module, stage, joints, context):
    return asyncio.run(
        module._run_newton_drive_sim(
            context,
            stage,
            "/Asset",
            joints,
            {},
            SimpleNamespace(stop=lambda: None, play=lambda: None),
            {},
            4,
            100,
            False,
            0.0,
        )
    )


def test_mixed_nonzero_starts_finish_at_absolute_native_stops(joint_movement, monkeypatch):
    stage, joints = _scene()
    starts = [np.pi / 6, -0.4, 0.25]
    native_limits = np.array([[0, np.pi / 2], [-2.0, 0], [0, 0.4]])
    writes, cleanup = [], []
    for joint in joints:
        joint["_open_sign"], joint["_open_travel"] = joint_movement._open_direction(stage, joint)
    _native_interface(monkeypatch, joint_movement, starts, native_limits, writes, cleanup)
    _run(joint_movement, stage, joints, _context())
    assert len(writes) == 4
    assert all(np.all(row >= native_limits[:, 0]) and np.all(row <= native_limits[:, 1]) for row in writes)
    np.testing.assert_allclose(writes[-1], [np.pi / 2, -2.0, 0.4])
    assert cleanup == [{"snapshot": True}]


@pytest.mark.parametrize("start", [-0.01, np.pi / 6, np.pi / 2 + 0.01])
def test_every_scalar_setpoint_is_legal_even_if_live_start_is_outside_stop(joint_movement, monkeypatch, start):
    stage, joints = _scene()
    joints = joints[:1]
    joints[0]["_open_sign"] = 1.0
    limits = np.array([[0, np.pi / 2]])
    writes, cleanup = [], []
    _native_interface(monkeypatch, joint_movement, [start], limits, writes, cleanup)
    _run(joint_movement, stage, joints, _context())
    assert all(0 <= float(row[0]) <= np.pi / 2 for row in writes)
    assert writes[-1][0] == np.pi / 2


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        [[0]],
        [[0, 1], [0, 1]],
        [[False, 1]],
        [["0", "1"]],
        [[np.nan, 1]],
        [[0, np.inf]],
        [[2, 1]],
        [[0, 0]],
        np.array([[0, 1]], dtype=object),
    ],
)
def test_unqualified_native_stops_restore_controls_without_dispatch(joint_movement, monkeypatch, raw):
    stage, joints = _scene()
    writes, cleanup = [], []
    _native_interface(monkeypatch, joint_movement, [0.25], raw, writes, cleanup)
    with pytest.raises(RuntimeError, match="native joint-limit|bounded native stops"):
        _run(joint_movement, stage, joints[:1], _context())
    assert writes == []
    assert cleanup == [{"snapshot": True}]


@pytest.mark.parametrize("raw", [np.array([[0.0, 1.0]], dtype=np.float32), np.array([[[0.0, 1.0]]]), [[0, 1]]])
def test_complete_real_native_limit_rows_are_preserved(joint_movement, raw):
    actual = joint_movement._read_dof_limits(SimpleNamespace(get_joint_limits=lambda: raw), 1)
    np.testing.assert_array_equal(actual, [[0, 1]])


def test_cuda_like_native_stops_move_to_host_before_qualification(joint_movement):
    calls = []

    class Buffer:
        def detach(self):
            calls.append("detach")
            return self

        def cpu(self):
            calls.append("cpu")
            return np.array([[0, 1]], dtype=np.float32)

        def __array__(self, *args, **kwargs):
            raise AssertionError("read a device buffer before host transfer")

    assert joint_movement._read_dof_limits(SimpleNamespace(get_joint_limits=Buffer), 1).tolist() == [[0, 1]]
    assert calls == ["detach", "cpu"]


def test_present_native_limit_error_never_uses_dormant_property_fallback(joint_movement):
    def fail():
        raise RuntimeError("native view invalidated")

    props = np.array([(0.0, 1.0)], dtype=[("lower", "f8"), ("upper", "f8")])
    with pytest.raises(RuntimeError, match="required native joint-limit readback") as caught:
        joint_movement._read_dof_limits(SimpleNamespace(get_joint_limits=fail, dof_properties=props), 1)
    assert "native view invalidated" in str(caught.value.__cause__)
