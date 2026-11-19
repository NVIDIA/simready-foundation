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
"""Composed Mimic forwarding: real USD discovery, topology and MIM prerequisites."""

import asyncio
from types import SimpleNamespace

import pytest

try:
    from pxr import PhysxSchema
except ImportError:
    from physx_usd_schemas import PhysxSchema

from pxr import Sdf, Tf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    mimic_joint,
    mimic_joints,
    robot_type,
)

_BACKENDS = ("physx", "newton")
_INVALID = ("empty", "dangling", "cycle", "multiple", "attribute", "non_joint", "outside", "self")


def _pair(backend, depth=0, joint_type=UsdPhysics.PrismaticJoint, invalid=None, axis=None):
    stage = Usd.Stage.CreateInMemory()
    world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    stage.SetDefaultPrim(world)
    root = UsdGeom.Xform.Define(stage, "/World/Asset").GetPrim()
    for name in ("base", "left", "right"):
        UsdPhysics.RigidBodyAPI.Apply(UsdGeom.Xform.Define(stage, str(root.GetPath()) + "/" + name).GetPrim())
    leader = joint_type.Define(stage, "/World/Asset/leader")
    follower = joint_type.Define(stage, "/World/Asset/follower")
    for joint, body in ((leader, "left"), (follower, "right")):
        joint.CreateBody0Rel().SetTargets(["/World/Asset/base"])
        joint.CreateBody1Rel().SetTargets(["/World/Asset/" + body])
        joint.CreateLowerLimitAttr(0.0)
        joint.CreateUpperLimitAttr(0.025)
    if backend == "physx":
        axis = axis or ("transX" if joint_type == UsdPhysics.PrismaticJoint else "rotX")
        mimic = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), axis)
        relationship = mimic.CreateReferenceJointRel()
        mimic.CreateGearingAttr(-1.0)
        mimic.CreateOffsetAttr(0.0)
        mimic.CreateNaturalFrequencyAttr(-1.0)
        mimic.CreateDampingRatioAttr(-1.0)
    else:
        follower.GetPrim().SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["NewtonMimicAPI"]))
        relationship = follower.GetPrim().CreateRelationship("newton:mimicJoint")
        follower.GetPrim().CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Float).Set(0.0)
        follower.GetPrim().CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(1.0)
    target = leader.GetPath()
    for index in range(depth):
        alias = root.CreateRelationship("leader_" + str(index))
        alias.SetTargets([target])
        target = alias.GetPath()
    if invalid is not None:
        alias = root.CreateRelationship("badAlias")
        if invalid == "dangling":
            alias.SetTargets(["/World/Asset.missing"])
        elif invalid == "cycle":
            other = root.CreateRelationship("cycle")
            other.SetTargets([alias.GetPath()])
            alias.SetTargets([other.GetPath()])
        elif invalid == "multiple":
            alias.SetTargets([leader.GetPath(), follower.GetPath()])
        elif invalid == "attribute":
            attr = root.CreateAttribute("notARelationship", Sdf.ValueTypeNames.Float)
            attr.Set(1.0)
            alias.SetTargets([attr.GetPath()])
        elif invalid == "non_joint":
            alias.SetTargets(["/World/Asset/base"])
        elif invalid == "outside":
            # Same DOF basename cannot substitute for a joint in this asset.
            alias.SetTargets([joint_type.Define(stage, "/World/Other/leader").GetPath()])
        elif invalid == "self":
            alias.SetTargets([follower.GetPath()])
        target = alias.GetPath()
    relationship.SetTargets([target])
    return stage, root, relationship


@pytest.mark.parametrize("axis", ["X", "Y", "Z", "rotX", "rotY", "rotZ", "transX", "transY", "transZ"])
@pytest.mark.parametrize("depth", [0, 3])
def test_physx_compatibility_axis_values_preserve_authored_namespace(axis, depth):
    stage, root, relationship = _pair("physx", depth, axis=axis)
    pairs = mimic_joints.detect_mimic_joints(stage, root, str(root.GetPath()), ["leader", "follower"])
    assert relationship.GetName() == "physxMimicJoint:" + axis + ":referenceJoint"
    assert len(pairs) == 1
    assert pairs[0] == mimic_joints.MimicJointSpec(
        follower_joint_path="/World/Asset/follower",
        reference_joint_path="/World/Asset/leader",
        gear=-1.0,
        offset=0.0,
        follower_dof_index=1,
        reference_dof_index=0,
    )


@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
@pytest.mark.parametrize("invalid", _INVALID)
def test_short_physx_compatibility_axis_cannot_resolve_invalid_reference(axis, invalid):
    stage, root, _ = _pair("physx", invalid=invalid, axis=axis)
    assert mimic_joints.detect_mimic_joints(stage, root, str(root.GetPath()), ["leader", "follower"]) == []


@pytest.mark.parametrize("axis", ["x", "z", "axis", "futureAxis"])
def test_non_axis_python_token_names_cannot_establish_physx_compatibility_mimic(axis):
    stage, root, _ = _pair("physx", axis=axis)
    assert mimic_joints.detect_mimic_joints(stage, root, str(root.GetPath()), ["leader", "follower"]) == []


class _PhysicsBoundary(RuntimeError):
    pass


class _Context:
    def __init__(self):
        self.metrics = {}
        self.skipped = False
        self.failed = False

    def step(self, message):
        pass

    def add_metric(self, name, value):
        self.metrics[name] = value

    def warn(self, message):
        pass

    def skip(self, message):
        self.skipped = True

    def fail(self, message):
        self.failed = True

    async def step_one(self):
        # Reaching real MIM's settle boundary proves resolution, not a native
        # response PASS. No solver, fake motion or persisted verdict is used.
        raise _PhysicsBoundary("native simulation deliberately unavailable")


def _run(stage, root, names=("leader", "follower")):
    ctx = _Context()

    def unused_write(*_args):
        raise AssertionError("The fixture stops at the first native tick, before any command")

    robot = SimpleNamespace(
        prim_path=str(root.GetPath()),
        dof_names=list(names),
        set_joint_position_targets_indexed=unused_write,
        set_joint_positions_indexed=unused_write,
        set_joint_velocities_indexed=unused_write,
    )
    return ctx, mimic_joint.run_mimic_joint(ctx, robot, {"stage": stage, "asset_prim": root}, {})


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("depth", [0, 1, 3])
@pytest.mark.parametrize("joint_type", [UsdPhysics.PrismaticJoint, UsdPhysics.RevoluteJoint])
def test_direct_and_forwarded_mimic_resolve_one_joint_and_qualify_topology(backend, depth, joint_type):
    stage, root, relationship = _pair(backend, depth, joint_type)
    pairs = mimic_joints.detect_mimic_joints(stage, root, str(root.GetPath()), ["leader", "follower"])
    assert relationship.GetForwardedTargets() == [Sdf.Path("/World/Asset/leader")]
    assert len(pairs) == 1
    assert pairs[0].reference_joint_path == "/World/Asset/leader"
    assert pairs[0].reference_dof_index == 0
    assert pairs[0].follower_dof_index == 1
    assert pairs[0].backend == backend
    assert robot_type.has_standalone_gripper_topology(stage, root)


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("invalid", _INVALID)
def test_invalid_forwarding_cannot_resolve_by_basename_or_qualify_topology(backend, invalid):
    stage, root, _ = _pair(backend, invalid=invalid)
    assert mimic_joints.detect_mimic_joints(stage, root, str(root.GetPath()), ["leader", "follower"]) == []
    assert not robot_type.has_standalone_gripper_topology(stage, root)


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("depth", [0, 1, 3])
def test_real_mim_entry_exercises_resolved_forwarding_instead_of_skipping(backend, depth):
    stage, root, _ = _pair(backend, depth)
    ctx, run = _run(stage, root)
    with pytest.raises(_PhysicsBoundary):
        asyncio.run(run)
    assert ctx.metrics == {"mim_mimic_pairs_detected": 1, "mim_skipped_pairs": 0}
    assert not ctx.skipped and not ctx.failed


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("invalid", _INVALID)
def test_real_mim_entry_unresolved_authored_reference_is_execution_limitation_not_no_mimic(backend, invalid):
    stage, root, _ = _pair(backend, invalid=invalid)
    ctx, run = _run(stage, root)
    with pytest.raises(RuntimeError, match="authored mimic followers exist"):
        asyncio.run(run)
    assert ctx.metrics["mim_mimic_pairs_detected"] == 0
    assert not ctx.skipped and not ctx.failed


@pytest.mark.parametrize("backend", _BACKENDS)
def test_resolved_forwarding_without_runtime_dof_mapping_is_execution_gap(backend):
    stage, root, _ = _pair(backend, depth=3)
    ctx, run = _run(stage, root, names=("leader",))
    with pytest.raises(RuntimeError, match="NONE of them resolve to a live articulation DOF"):
        asyncio.run(run)
    assert ctx.metrics == {"mim_mimic_pairs_detected": 1, "mim_skipped_pairs": 1}
    assert not ctx.skipped and not ctx.failed


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("native_error", [False, True])
def test_only_native_forwarding_resolution_errors_are_handled(monkeypatch, backend, native_error):
    stage, root, _ = _pair(backend, depth=3)
    error = (
        Tf.ErrorException("native forwarding unavailable") if native_error else RuntimeError("unexpected helper bug")
    )

    original_forwarding = Usd.Relationship.GetForwardedTargets

    def unavailable(relationship):
        # This regression injects mimic-reference resolution failure, while the
        # physical body relationships remain usable for required ownership.
        if "mimic" in str(relationship.GetName()).lower():
            raise error
        return original_forwarding(relationship)

    monkeypatch.setattr(Usd.Relationship, "GetForwardedTargets", unavailable)
    ctx, run = _run(stage, root)
    if native_error:
        with pytest.raises(RuntimeError, match="authored mimic followers exist"):
            asyncio.run(run)
        assert not ctx.skipped and not ctx.failed
        assert not robot_type.has_standalone_gripper_topology(stage, root)
    else:
        with pytest.raises(RuntimeError, match="unexpected helper bug"):
            asyncio.run(run)
        assert not ctx.skipped and not ctx.failed
