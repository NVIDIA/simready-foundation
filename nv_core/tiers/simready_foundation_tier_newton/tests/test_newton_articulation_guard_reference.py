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
"""Exercise frozen safety references through each production phase's setup and guard."""

import ast
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import joint_utils
from simready.foundation.tier_newton.runtime_tests.articulation_phases._kinematic_bounds import (
    SpatialGuardInterruption,
    freeze_bbox_reference,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    RequiredReadbackError,
)

PHASES = [
    "full_range_sweep",
    "velocity_limit",
    "effort_limit",
    "state_accuracy",
    "drive_gain_validation",
    "mimic_joint",
    "ik_target_reach",
    "jacobian_ik",
    "multi_joint_coordination",
]


def _robot():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Robot").GetPrim()
    for name, z in (("base", 0), ("tip", 2)):
        body = UsdGeom.Xform.Define(stage, "/Robot/" + name)
        body.AddTranslateOp().Set(Gf.Vec3d(0, 0, z))
        body.AddOrientOp().Set(Gf.Quatf(1))
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        geometry = UsdGeom.Cube.Define(stage, "/Robot/" + name + "/visual")
        geometry.AddScaleOp().Set(Gf.Vec3f(0.1, 0.1, 2))
        geometry.CreateSizeAttr(1)
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/hinge")
    joint.CreateBody0Rel().SetTargets(["/Robot/base"])
    joint.CreateBody1Rel().SetTargets(["/Robot/tip"])
    joint.CreateLocalPos0Attr(Gf.Vec3f(0, 0, 1))
    joint.CreateLocalPos1Attr(Gf.Vec3f(0, 0, -1))
    return stage, root


def _bounds(root):
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    bounds = cache.ComputeWorldBound(root).ComputeAlignedRange()
    return joint_utils.BBoxSnapshot(tuple(bounds.GetMin()), tuple(bounds.GetMax()))


def _context(fail_metrics=False):
    metrics = {}

    def metric(name, value):
        if fail_metrics:
            raise OSError("guard diagnostics unavailable")
        metrics[name] = value

    return SimpleNamespace(add_metric=metric, warn=lambda *_: None, metrics=metrics)


def _production_reference(phase, root, ctx):
    # Evaluate the actual setup expression, not a copied reference algorithm.
    # Physical observations below are in-memory USD geometry, not native QA.
    tree = ast.parse(Path(phase.__file__).read_text(encoding="utf-8"))
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "baseline_bbox" for target in node.targets)
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "freeze_bbox_reference"
            for child in ast.walk(node.value)
        )
    ]
    assert len(assignments) == 1
    expression = ast.Expression(body=assignments[0].value)
    return eval(
        compile(ast.fix_missing_locations(expression), phase.__file__, "eval"),
        {
            "compute_world_aligned_bbox": _bounds,
            "freeze_bbox_reference": phase.freeze_bbox_reference,
            "asset_prim": root,
            "robot_root_prim": None,
            "ctx": ctx,
        },
    )


@pytest.mark.parametrize("name", PHASES)
def test_production_phase_does_not_call_connected_bending_an_explosion(name):
    phase = importlib.import_module("simready.foundation.tier_newton.runtime_tests.articulation_phases." + name)
    stage, root = _robot()
    ctx = _context()
    reference = _production_reference(phase, root, ctx)
    assert reference.kinematic_span is not None
    rotation = Gf.Rotation(Gf.Vec3d(0, 0, 1), Gf.Vec3d(1, 1, 1).GetNormalized())
    tip = UsdGeom.Xformable(stage.GetPrimAtPath("/Robot/tip"))
    translation, orientation = tip.GetOrderedXformOps()
    orientation.Set(Gf.Quatf(rotation.GetQuat()))
    translation.Set(Gf.Vec3d(0, 0, 1) + rotation.TransformDir(Gf.Vec3d(0, 0, 1)))
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    # Joint anchors stay coincident: the changed AABB is ordinary rigid motion.
    pivot = cache.GetLocalToWorldTransform(stage.GetPrimAtPath("/Robot/tip")).Transform(Gf.Vec3d(0, 0, -1))
    assert (pivot - Gf.Vec3d(0, 0, 1)).GetLength() < 1e-6
    bent = _bounds(root)
    assert bent.volume > reference.volume * 10
    assert phase.check_bbox_explode(bent, reference.snapshot, 10) is not None
    assert phase.check_bbox_explode(bent, reference, 10) is None
    assert ctx.metrics[reference.phase + "_guard_reference"]["qualified"]


@pytest.mark.parametrize("name", PHASES)
@pytest.mark.parametrize("fail_metrics", [False, True])
def test_each_phase_interrupts_actual_separation_without_a_response_verdict(name, fail_metrics):
    phase = importlib.import_module("simready.foundation.tier_newton.runtime_tests.articulation_phases." + name)
    stage, root = _robot()
    ctx = _context(fail_metrics)
    reference = _production_reference(phase, root, ctx)
    tip = UsdGeom.Xformable(stage.GetPrimAtPath("/Robot/tip"))
    tip.GetOrderedXformOps()[0].Set(Gf.Vec3d(200, 200, 200))
    with pytest.raises(SpatialGuardInterruption, match="not a completed asset-response failure") as caught:
        phase.check_bbox_explode(_bounds(root), reference, 10)
    assert isinstance(caught.value, RequiredReadbackError)
    if not fail_metrics:
        assert ctx.metrics[reference.phase + "_guard_abort"]["basis"] == "kinematic_span"


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf")])
def test_invalid_required_live_observation_is_not_an_optional_diagnostic(bad):
    _stage, root = _robot()
    reference = freeze_bbox_reference(_bounds(root), root, _context(), "probe")
    current = None if bad is None else joint_utils.BBoxSnapshot((0, 0, 0), (bad, 1, 1))
    with pytest.raises(RequiredReadbackError):
        joint_utils.check_bbox_explode(current, reference, 10)


def test_unqualified_topology_uses_honest_fallback_and_still_interrupts():
    stage, root = _robot()
    loose = UsdGeom.Xform.Define(stage, "/Robot/loose").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(loose)
    UsdGeom.Cube.Define(stage, "/Robot/loose/visual").CreateSizeAttr(0.05)
    ctx = _context()
    reference = freeze_bbox_reference(_bounds(root), root, ctx, "probe")
    assert reference.kinematic_span is None
    assert ctx.metrics["probe_guard_reference"]["basis"] == "unqualified_initial_volume_proxy"
    current = joint_utils.BBoxSnapshot((0, 0, 0), (100, 100, 100))
    with pytest.raises(SpatialGuardInterruption, match="unqualified_initial_volume_proxy"):
        joint_utils.check_bbox_explode(current, reference, 10)
