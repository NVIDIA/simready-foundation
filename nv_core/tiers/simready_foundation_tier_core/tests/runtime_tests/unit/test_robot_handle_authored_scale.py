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

"""Scale preservation is a setup invariant, not a grasp acceptance relaxation.

Host tests use real USD and a constructor-normalization double, not native
Isaac physics. Fresh branch-provider Evaluate trials remain necessary.
"""

import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_handle import (
    RobotHandle,
    _authored_articulation_local_scale,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.robot_type import RobotType


def _scaled_root(*, use_matrix=True, scale=(0.001, 0.001, 0.001), ancestor_scale=None):
    stage = Usd.Stage.CreateInMemory()
    parent = UsdGeom.Xform.Define(stage, "/Asset")
    if ancestor_scale is not None:
        parent.AddScaleOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Vec3d(*ancestor_scale))
    root = UsdGeom.Xform.Define(stage, "/Asset/Body")
    transform = Gf.Transform()
    transform.SetTranslation(Gf.Vec3d(1, 2, 3))
    transform.SetRotation(Gf.Rotation(Gf.Vec3d(0, 0, 1), 37))
    transform.SetScale(Gf.Vec3d(*scale))
    if use_matrix:
        root.AddTransformOp().Set(transform.GetMatrix())
    else:
        root.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(transform.GetTranslation())
        root.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(transform.GetRotation().GetQuat())
        root.AddScaleOp(UsdGeom.XformOp.PrecisionDouble).Set(transform.GetScale())
    collider = UsdGeom.Cube.Define(stage, "/Asset/Body/Collider")
    collider.CreateSizeAttr(62)
    return stage, root, parent, collider


def _bounds(collider):
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"]).ComputeWorldBound(collider.GetPrim())
    aligned = bounds.ComputeAlignedRange()
    return np.asarray(aligned.GetMin()), np.asarray(aligned.GetMax())


def _normalize_root_like_isaac(root, local_scale):
    """Model removal of authored matrix ops and public local-scale application.

    Rotation extraction below matches Gf's orthonormalization used by Isaac's
    USD pose reader for the supported, non-reflected orthogonal transform.
    This double does not qualify native solver, tensor, reset or camera behavior.
    """
    original = root.GetLocalTransformation()
    orthogonal = Gf.Matrix4d(original)
    assert orthogonal.Orthonormalize()
    orientation = orthogonal.ExtractRotationQuat()
    root.ClearXformOpOrder()
    for prop in list(root.GetPrim().GetProperties()):
        if prop.GetName().startswith("xformOp:"):
            root.GetPrim().RemoveProperty(prop.GetName())
    root.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(original.ExtractTranslation())
    root.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(orientation)
    root.AddScaleOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Vec3d(*local_scale))


@pytest.mark.parametrize("use_matrix", [True, False])
@pytest.mark.parametrize("scale", [(0.001,) * 3, (1.0,) * 3, (2.0,) * 3, (2.0, 3.0, 4.0)])
def test_matrix_and_trs_preserve_dimensions_through_constructor_normalization(use_matrix, scale):
    stage, root, _, collider = _scaled_root(use_matrix=use_matrix, scale=scale)
    before = _bounds(collider)
    original = np.asarray(root.GetLocalTransformation()).copy()
    local_scale = _authored_articulation_local_scale(stage, str(root.GetPath()))
    np.testing.assert_allclose(local_scale, scale, rtol=1e-12, atol=1e-12)
    _normalize_root_like_isaac(root, local_scale)
    np.testing.assert_allclose(root.GetLocalTransformation(), original, rtol=1e-12, atol=1e-12)
    for actual, expected in zip(_bounds(collider), before, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(
        _authored_articulation_local_scale(stage, str(root.GetPath())), local_scale, rtol=1e-12, atol=1e-12
    )


@pytest.mark.parametrize("use_matrix", [True, False])
def test_even_signed_scale_keeps_proper_rotation_and_dimensions(use_matrix):
    stage, root, _, collider = _scaled_root(use_matrix=use_matrix, scale=(-2.0, -3.0, 4.0))
    before = _bounds(collider)
    original = np.asarray(root.GetLocalTransformation()).copy()
    local_scale = _authored_articulation_local_scale(stage, str(root.GetPath()))
    np.testing.assert_allclose(local_scale, (2.0, 3.0, 4.0), rtol=1e-12, atol=1e-12)
    _normalize_root_like_isaac(root, local_scale)
    np.testing.assert_allclose(root.GetLocalTransformation(), original, rtol=1e-12, atol=1e-12)
    for actual, expected in zip(_bounds(collider), before, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("use_matrix", [True, False])
@pytest.mark.parametrize("ancestor_scale", [(0.02,) * 3, (2.0,) * 3])
def test_scale_is_local_and_does_not_double_apply_ancestor_scale(use_matrix, ancestor_scale):
    stage, root, _, collider = _scaled_root(use_matrix=use_matrix, ancestor_scale=ancestor_scale)
    before = _bounds(collider)
    local_scale = _authored_articulation_local_scale(stage, str(root.GetPath()))
    np.testing.assert_allclose(local_scale, (0.001,) * 3, rtol=1e-12, atol=1e-12)
    _normalize_root_like_isaac(root, local_scale)
    for actual, expected in zip(_bounds(collider), before, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


def test_valid_fixed_joint_root_does_not_author_a_scale():
    stage = Usd.Stage.CreateInMemory()
    joint = UsdPhysics.FixedJoint.Define(stage, "/Pin")
    UsdPhysics.ArticulationRootAPI.Apply(joint.GetPrim())
    before = stage.GetRootLayer().ExportToString()
    assert _authored_articulation_local_scale(stage, "/Pin") is None
    assert stage.GetRootLayer().ExportToString() == before
    assert not joint.GetPrim().HasAttribute("xformOp:scale")


@pytest.mark.parametrize("use_matrix", [True, False])
@pytest.mark.parametrize("scale", [(-2.0, 3.0, 4.0), (-2.0, -3.0, -4.0), (0.0, 1.0, 1.0)])
def test_unrepresentable_reflection_or_degenerate_scale_is_a_setup_error(use_matrix, scale):
    stage, root, _, _ = _scaled_root(use_matrix=use_matrix, scale=scale)
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="(?i)scale|transform|reflection|singular|degenerate"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))
    assert stage.GetRootLayer().ExportToString() == before


def test_missing_root_is_not_silently_treated_as_unscaled():
    stage = Usd.Stage.CreateInMemory()
    with pytest.raises(RuntimeError, match="(?i)root|prim|invalid|missing"):
        _authored_articulation_local_scale(stage, "/Missing")


@pytest.mark.parametrize("use_matrix", [True, False])
@pytest.mark.parametrize("scale", [1e-46, 1e39])
def test_float64_scale_must_be_representable_by_native_float32_backend(use_matrix, scale):
    stage, root, _, _ = _scaled_root(use_matrix=use_matrix, scale=(scale,) * 3)
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="native float32 range"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))
    assert stage.GetRootLayer().ExportToString() == before


def test_sheared_matrix_is_a_setup_error_before_normalization():
    stage, root, _, _ = _scaled_root()
    sheared = Gf.Matrix4d(1)
    sheared.SetRow(0, Gf.Vec4d(1, 0.25, 0, 0))
    root.GetOrderedXformOps()[0].Set(sheared)
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="(?i)shear|transform|scale"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))
    assert stage.GetRootLayer().ExportToString() == before


def test_nonuniform_ancestor_induced_shear_is_a_setup_error():
    stage, root, _, _ = _scaled_root(ancestor_scale=(2.0, 3.0, 4.0))
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="(?i)shear|ancestor|transform|scale"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))
    assert stage.GetRootLayer().ExportToString() == before


def test_reset_transform_stack_is_not_silently_removed_by_constructor():
    stage, root, _, _ = _scaled_root(ancestor_scale=(2.0,) * 3)
    root.SetResetXformStack(True)
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="(?i)reset|transform|scale"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("reset_on_joint", [False, True])
def test_reset_stack_ancestor_is_rejected_even_for_fixed_joint_root(reset_on_joint):
    stage, root, parent, _ = _scaled_root(ancestor_scale=(2.0,) * 3)
    parent.SetResetXformStack(True)
    path = str(root.GetPath())
    if reset_on_joint:
        path = str(UsdPhysics.FixedJoint.Define(stage, "/Asset/Pin").GetPath())
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="reset transform stack"):
        _authored_articulation_local_scale(stage, path)
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("has_default", [False, True])
def test_time_sampled_root_transform_is_rejected_without_discarding_animation(has_default):
    stage, root, _, _ = _scaled_root()
    op = root.GetOrderedXformOps()[0]
    matrix = op.Get()
    if not has_default:
        op.GetAttr().Clear()
    op.Set(matrix, Usd.TimeCode(0))
    op.Set(Gf.Matrix4d(1), Usd.TimeCode(1))
    before = stage.GetRootLayer().ExportToString()
    with pytest.raises(RuntimeError, match="time-sampled"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))
    assert stage.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_nonfinite_matrix_is_not_passed_to_native_constructor(bad_value):
    stage, root, _, _ = _scaled_root()
    matrix = Gf.Matrix4d(1)
    matrix.SetRow(0, Gf.Vec4d(bad_value, 0, 0, 0))
    root.GetOrderedXformOps()[0].Set(matrix)
    with pytest.raises(RuntimeError, match="(?i)nonfinite|transform|scale"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))


def test_non_affine_matrix_cannot_be_preserved_by_local_scale():
    stage, root, _, _ = _scaled_root()
    matrix = Gf.Matrix4d(1)
    matrix.SetRow(0, Gf.Vec4d(1, 0, 0, 0.1))
    root.GetOrderedXformOps()[0].Set(matrix)
    with pytest.raises(RuntimeError, match="(?i)affine|transform|scale"):
        _authored_articulation_local_scale(stage, str(root.GetPath()))


def _fake_isaac(monkeypatch, stage):
    calls = []

    def single_articulation(**kwargs):
        calls.append(("construct", kwargs))
        root = UsdGeom.Xformable(stage.GetPrimAtPath(kwargs["prim_path"]))
        if root:
            _normalize_root_like_isaac(root, kwargs["scale"])
        return SimpleNamespace(dof_names=[])

    class World:
        @staticmethod
        def clear_instance():
            calls.append(("clear",))

        def __init__(self, **kwargs):
            calls.append(("world", kwargs))
            self.scene = SimpleNamespace(
                add=lambda articulation: calls.append(("add", articulation)),
                remove_object=lambda name, **kwargs: calls.append(("remove", name, kwargs)),
            )

        async def initialize_simulation_context_async(self):
            calls.append(("initialize_context",))

        async def reset_async(self):
            calls.append(("reset",))

    for name in ("isaacsim", "isaacsim.core", "isaacsim.core.api", "isaacsim.core.prims"):
        module = ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules["isaacsim.core.api"].World = World
    sys.modules["isaacsim.core.prims"].SingleArticulation = single_articulation
    return calls, World


@pytest.mark.asyncio
@pytest.mark.parametrize("use_matrix", [True, False])
async def test_initialize_and_reinitialize_pass_public_local_scale_to_constructor(monkeypatch, use_matrix):
    stage, root, parent, collider = _scaled_root(use_matrix=use_matrix)
    calls, _ = _fake_isaac(monkeypatch, stage)
    robot = RobotHandle(stage, root.GetPath(), parent.GetPrim(), RobotType.ARM)
    ctx = SimpleNamespace(step=lambda message: None, warn=lambda message: None)
    before = _bounds(collider)
    await robot.initialize(ctx)
    await robot.reinitialize_articulation(ctx)
    construction = [call[1] for call in calls if call[0] == "construct"]
    assert len(construction) == 2
    for kwargs in construction:
        assert kwargs["prim_path"] == str(root.GetPath())
        assert kwargs["name"] == robot._name
        np.testing.assert_allclose(kwargs["scale"], (0.001,) * 3, rtol=1e-12, atol=1e-12)
    removals = [call for call in calls if call[0] == "remove"]
    assert removals == [("remove", robot._name, {"registry_only": True})]
    for actual, expected in zip(_bounds(collider), before, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["initialize", "reinitialize_articulation"])
async def test_unsupported_transform_fails_before_world_or_registration_mutation(monkeypatch, operation):
    stage, root, parent, _ = _scaled_root()
    root.SetResetXformStack(True)
    calls, world_type = _fake_isaac(monkeypatch, stage)
    robot = RobotHandle(stage, root.GetPath(), parent.GetPrim(), RobotType.ARM)
    if operation == "reinitialize_articulation":
        robot._world = world_type()
    previous = SimpleNamespace(dof_names=["preserved"])
    robot._articulation = previous
    calls.clear()
    ctx = SimpleNamespace(step=lambda message: None, warn=lambda message: None)
    with pytest.raises(RuntimeError, match="(?i)reset|transform|scale"):
        await getattr(robot, operation)(ctx)
    assert calls == []
    assert robot._articulation is previous


@pytest.mark.asyncio
async def test_initialize_registration_failure_stops_before_reset_or_publication(monkeypatch):
    stage, root, parent, _ = _scaled_root()
    calls, world_type = _fake_isaac(monkeypatch, stage)
    error = RuntimeError("controlled registration failure")
    original_init = world_type.__init__

    def initialize_with_registration_failure(self, **kwargs):
        original_init(self, **kwargs)

        def fail_add(articulation):
            calls.append(("add_failed", articulation))
            raise error

        self.scene.add = fail_add

    monkeypatch.setattr(world_type, "__init__", initialize_with_registration_failure)
    robot = RobotHandle(stage, root.GetPath(), parent.GetPrim(), RobotType.ARM)
    ctx = SimpleNamespace(step=lambda message: None, warn=lambda message: None)
    with pytest.raises(RuntimeError, match="registering the articulation view failed") as raised:
        await robot.initialize(ctx)
    assert raised.value.__cause__ is error
    assert any(call[0] == "add_failed" for call in calls)
    assert not any(call[0] == "reset" for call in calls)
    assert robot._articulation is None
