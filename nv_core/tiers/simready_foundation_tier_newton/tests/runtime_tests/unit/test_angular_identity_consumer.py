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

"""Real USD identity through the original JIK gate and FK target preparation.

Native propagation/pose is a host adapter, not a solver or native acceptance test.
"""
import ast
import copy
import inspect
import math

import numpy as np
import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import jacobian_ik as phase


def consumer():
    """Execute the original contiguous applicability block and actual FK call."""
    tree = ast.parse(inspect.getsource(phase))
    run = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_run_jacobian_ik_impl")
    start = next(
        i
        for i, node in enumerate(run.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Tuple) and any(isinstance(x, ast.Name) and x.id == "lowers" for x in t.elts)
            for t in node.targets
        )
    )
    stop = next(
        i
        for i in range(start, len(run.body))
        if isinstance(run.body[i], ast.Try)
        and any(
            isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "JacobianIKSolver"
            for x in ast.walk(run.body[i])
        )
    )
    call = next(
        n
        for n in run.body
        if isinstance(n, ast.Assign)
        and any(
            isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "_generate_fk_targets"
            for x in ast.walk(n)
        )
    )
    wrapper = ast.parse(
        "async def consumer(ctx, robot, scene_info, home_joints, locked_indices, solver, base_pos, num_targets, out_of_reach_count):\n    pass\n"
    ).body[0]
    wrapper.body = copy.deepcopy(run.body[start:stop] + [call]) + [
        ast.Return(value=ast.Name(id="targets", ctx=ast.Load()))
    ]
    namespace = dict(vars(phase))
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), phase.__file__, "exec"),
        namespace,
    )
    return namespace["consumer"]


def articulation(stage, prefix, kind="revolute"):
    UsdGeom.Xform.Define(stage, prefix)
    for leaf in ("base", "tip"):
        prim = UsdGeom.Xform.Define(stage, prefix + "/" + leaf).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
    root = stage.GetPrimAtPath(prefix + "/base")
    UsdPhysics.ArticulationRootAPI.Apply(root)
    pin = UsdPhysics.FixedJoint.Define(stage, prefix + "/joints/world_pin")
    pin.GetBody1Rel().SetTargets([root.GetPath()])
    schema = UsdPhysics.RevoluteJoint if kind == "revolute" else UsdPhysics.PrismaticJoint
    joint = schema.Define(stage, prefix + "/joints/hinge")
    joint.GetBody0Rel().SetTargets([root.GetPath()])
    joint.GetBody1Rel().SetTargets([stage.GetPrimAtPath(prefix + "/tip").GetPath()])
    joint.GetAxisAttr().Set("Z")
    UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular" if kind == "revolute" else "linear")
    assert math.isinf(joint.GetLowerLimitAttr().Get()) and math.isinf(joint.GetUpperLimitAttr().Get())
    return root, joint.GetPrim()


def scene(case):
    stage = Usd.Stage.CreateInMemory()
    asset = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(asset)
    root, joint = articulation(stage, "/Asset/Selected", "prismatic" if case == "nonangular" else "revolute")
    if case == "foreign_duplicate":
        articulation(stage, "/Asset/Foreign")
    if case == "ambiguous_selected":
        tip2 = UsdGeom.Xform.Define(stage, "/Asset/Selected/tip2").GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(tip2)
        other = UsdPhysics.RevoluteJoint.Define(stage, "/Asset/Selected/other/hinge")
        other.GetBody0Rel().SetTargets([stage.GetPrimAtPath("/Asset/Selected/tip").GetPath()])
        other.GetBody1Rel().SetTargets([tip2.GetPath()])
    names = {"path": str(joint.GetPath()), "axis": "hinge:0", "path_axis": str(joint.GetPath()) + ":0"}
    name = names.get(case, "missing" if case == "missing" else "hinge")
    return stage, {"stage": stage, "asset_prim": asset, "robot_root_prim": root}, root, name


class HostRobot:
    """Explicit one-coordinate required-state adapter; no native simulator."""

    def __init__(self, root, name, asset):
        self.prim_path = str(root.GetPath())
        self.asset_prim = asset
        self.dof_names = [name]
        self.dof_count = 1
        self.q = np.zeros(1)
        self.writes = []

    def get_joint_position_limits(self):
        return np.array([-math.inf]), np.array([math.inf])

    def write(self, q, excluded):
        assert not excluded
        self.q = np.asarray(q).copy()
        self.writes.append(self.q.tolist())


class HostPose:
    """Planar rigid arm pose adapter, downstream of the real target sampler."""

    def __init__(self, robot):
        self.robot = robot

    def get_ee_pose(self):
        theta = float(self.robot.q[0])
        return np.array([math.cos(theta), math.sin(theta), 0.0]), np.array(
            [math.cos(theta / 2), 0.0, 0.0, math.sin(theta / 2)]
        )


class HostContext:
    def __init__(self):
        self.metrics, self.skips, self.warnings, self.steps = {}, [], [], 0

    def add_metric(self, name, value):
        self.metrics[name] = value

    def skip(self, text):
        self.skips.append(text)

    def warn(self, text):
        self.warnings.append(text)

    def step(self, text):
        pass

    async def step_one(self):
        self.steps += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    ["leaf", "path", "axis", "path_axis", "foreign_duplicate", "ambiguous_selected", "nonangular", "missing", "finite"],
)
async def test_selected_angular_identity_reaches_original_fk_preparation(monkeypatch, case):
    monkeypatch.setattr(phase, "write_probe_state", lambda robot, q, excluded: robot.write(q, excluded))
    run = consumer()

    async def prepare(label):
        stage, info, root, name = scene(label)
        robot, ctx = HostRobot(root, name, info["asset_prim"]), HostContext()
        if label == "finite":
            robot.get_joint_position_limits = lambda: (np.array([-1.0]), np.array([1.0]))
        targets = await run(ctx, robot, info, np.zeros(1), set(), HostPose(robot), np.zeros(3), 3, 0)
        return ctx, robot.writes, [target.position.tolist() for target in targets or []]

    baseline, baseline_writes, baseline_targets = await prepare("leaf")
    assert not baseline.skips and len(baseline_targets) == 3
    ctx, writes, targets = await prepare(case)
    if case in {"ambiguous_selected", "nonangular", "missing"}:
        assert ctx.skips and not targets and not writes
    elif case == "finite":
        assert not ctx.skips and len(targets) == 3
        assert all(-1.0 <= row[0] <= 1.0 for row in writes)
    else:
        assert not ctx.skips
        assert writes == baseline_writes
        assert targets == baseline_targets
