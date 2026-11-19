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
"""Articulation shape changes are not explosions; aborted observations are not convergence failures."""

from types import SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases import (
    multi_joint_coordination as mjc,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (
    BBoxSnapshot,
    check_bbox_explode,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.kinematic_bounds import (
    articulation_span_reference,
    check_articulation_span,
)


def test_public_discovery_imports_runtime_helpers_without_package_context():
    """Exercise the CLI's actual discovery gate, not only package imports."""
    import subprocess
    import sys
    from pathlib import Path

    suite_root = Path(mjc.__file__).resolve().parents[1]
    # Use a fresh interpreter: this test module already imports the provider,
    # whereas normal host planning discovers it before loading its helpers.
    command = (
        "import sys; from simready.evaluate.core.discovery import discover_tests; "
        "tests = discover_tests([sys.argv[1]]); "
        "assert any(test.name == 'multi_joint_coordination' for test in tests), "
        "'Core coordination test missing from the discovered inventory'"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command, str(suite_root)], capture_output=True, text=True, timeout=60, check=False
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _connected_robot(scale=1.0):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset")
    root.AddScaleOp().Set(Gf.Vec3f(scale))
    base = UsdGeom.Xform.Define(stage, "/Asset/base").GetPrim()
    tip = UsdGeom.Xform.Define(stage, "/Asset/tip")
    tip.AddTranslateOp().Set(Gf.Vec3d(0, 0, 2))
    for path in ("/Asset/base", "/Asset/tip"):
        UsdPhysics.RigidBodyAPI.Apply(stage.GetPrimAtPath(path))
        UsdGeom.Cube.Define(stage, path + "/visual").CreateSizeAttr(0.2)
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/joint")
    joint.CreateBody0Rel().SetTargets([base.GetPath()])
    joint.CreateBody1Rel().SetTargets([tip.GetPath()])
    joint.CreateLocalPos0Attr(Gf.Vec3f(0, 0, 1))
    joint.CreateLocalPos1Attr(Gf.Vec3f(0, 0, -1))
    return stage, root.GetPrim()


@pytest.mark.parametrize("scale", [0.001, 1.0, 1000.0])
def test_skinny_initial_pose_may_grow_in_volume_without_exceeding_kinematic_span(scale):
    stage, root = _connected_robot(scale)
    diameter = articulation_span_reference(root)
    assert diameter is not None
    baseline = BBoxSnapshot((0, 0, 0), tuple(scale * v for v in (0.191, 0.3867, 1.9477)))
    bent = BBoxSnapshot((0, 0, 0), tuple(scale * v for v in (1.1, 1.1, 1.221)))
    # The legacy volume guard misclassified normal articulation from a slender pose.
    if scale >= 1:
        assert check_bbox_explode(bent, baseline, 10) is not None
    assert check_articulation_span(bent, diameter, 10) is None
    runaway = BBoxSnapshot((0, 0, 0), (scale * 200, scale * 0.1, scale * 0.1))
    assert check_articulation_span(runaway, diameter, 10) is not None


def test_disconnected_body_does_not_produce_a_qualified_kinematic_bound():
    stage, root = _connected_robot()
    UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, "/Asset/loose").GetPrim())
    assert articulation_span_reference(root) is None


def _prismatic_robot(lower, upper):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    for path in ("/Asset/base", "/Asset/tip"):
        body = UsdGeom.Xform.Define(stage, path)
        body.AddScaleOp().Set(Gf.Vec3d(1, 1000, 1))
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        UsdGeom.Cube.Define(stage, path + "/mesh").CreateSizeAttr(0.01)
    joint = UsdPhysics.PrismaticJoint.Define(stage, "/Asset/slider")
    joint.CreateBody0Rel().SetTargets(["/Asset/base"])
    joint.CreateBody1Rel().SetTargets(["/Asset/tip"])
    joint.CreateAxisAttr("X")
    joint.CreateLowerLimitAttr(lower)
    joint.CreateUpperLimitAttr(upper)
    orientation = Gf.Quatf(Gf.Rotation(Gf.Vec3d(0, 0, 1), 90).GetQuat())
    joint.CreateLocalRot0Attr(orientation)
    joint.CreateLocalRot1Attr(orientation)
    return stage, root


def test_scaled_prismatic_bound_covers_rotated_joint_frame_axis():
    _stage, root = _prismatic_robot(0, 1)
    diameter = articulation_span_reference(root)
    assert diameter is not None
    assert diameter >= 1000
    # The body-local X axis is rotated onto the Y-scaled body direction.
    # This is a mathematical reach bound, not native importer qualification.
    extent = BBoxSnapshot((0, 0, 0), (0.01, 1000.01, 0.01))
    assert check_articulation_span(extent, diameter, 10) is None
    runaway = BBoxSnapshot((0, 0, 0), (0.01, 20000, 0.01))
    assert check_articulation_span(runaway, diameter, 10) is not None


@pytest.mark.parametrize("coordinate", [0.0, 0.5, -0.5])
def test_locked_finite_prismatic_coordinate_still_has_known_reach(coordinate):
    _stage, root = _prismatic_robot(coordinate, coordinate)
    diameter = articulation_span_reference(root)
    assert diameter is not None
    assert diameter >= abs(coordinate) * 1000


@pytest.mark.parametrize(
    ("lower", "upper"),
    [(1, 0), (-float("inf"), float("inf")), (float.fromhex("0x1.fffffep+127"),) * 2],
)
def test_unqualified_prismatic_limits_are_not_a_known_reach(lower, upper):
    _stage, root = _prismatic_robot(lower, upper)
    assert articulation_span_reference(root) is None


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_nonfinite_live_axis_cannot_be_hidden_by_maximum_reduction(axis):
    upper = [1.0, 1.0, 1.0]
    upper[axis] = float("nan")
    with pytest.raises(RuntimeError, match="finite live bounds"):
        check_articulation_span(BBoxSnapshot((0, 0, 0), tuple(upper)), 3, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize("reporting_fails", [False, True])
async def test_guard_abort_retains_completed_ticks_without_reporting_nonconvergence(monkeypatch, reporting_fails):
    metrics = {}

    async def tick():
        return None

    robot = SimpleNamespace(
        dof_count=1, get_joint_positions=lambda: np.array([0.0]), set_joint_position_targets=lambda *_: None
    )

    def record(key, value):
        if reporting_fails:
            raise OSError("diagnostic write failed")
        metrics[key] = value

    ctx = SimpleNamespace(step_one=tick, add_metric=record)
    monkeypatch.setattr(mjc, "compute_world_aligned_bbox", lambda *_: BBoxSnapshot((0, 0, 0), (200, 1, 1)))
    with pytest.raises(RuntimeError, match="observation interrupted.*not a measured non-convergence") as raised:
        await mjc._run_iteration(
            ctx,
            robot,
            {},
            [{"index": 0, "name": "joint", "lower": -1.0, "upper": 1.0}],
            factor=1.0,
            iteration_idx=0,
            pos_tol_rad=0.01,
            max_frames=5,
            capture_interval=1,
            capture_frames=[],
            baseline_bbox=None,
            bbox_ratio_limit=10.0,
            margin_ratio=0.0,
            physics_fps=240.0,
            motion_frames=5,
            kinematic_span=3.0,
        )
    if reporting_fails:
        assert "1/5 planned ticks" in str(raised.value)
        assert any("diagnostic write failed" in note for note in raised.value.__notes__)
    else:
        assert metrics["mjc_guard_abort"]["completed_ticks"] == 1
        assert metrics["mjc_guard_abort"]["planned_ticks"] == 5
        assert metrics["mjc_guard_abort"]["basis"] == "kinematic_span"


def test_reference_diagnostic_failure_does_not_disable_the_guard():
    def fail(*_):
        raise OSError("diagnostic output unavailable")

    mjc._record_guard_metric(SimpleNamespace(add_metric=fail, warn=fail), "mjc_guard_reference", {"qualified": True})
