# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regression scenes from adversarial review of collapse physics."""

import numpy as np
import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from conftest import _body, _collider, _fixed_joint, _new_stage
from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
    _massinfo, _massprops, fixed_joint_merge,
)


@pytest.mark.parametrize("nested", [False, True])
def test_mixed_direct_and_instanced_colliders_contribute_mass(tmp_path, nested):
    prototype = _new_stage(tmp_path / "prototype.usda")
    _collider(prototype, "/Asset/cube", size=1)
    prototype.GetRootLayer().Save()
    reference = "prototype.usda"
    if nested:
        wrapper = _new_stage(tmp_path / "wrapper.usda")
        inner = UsdGeom.Xform.Define(wrapper, "/Asset/inner").GetPrim()
        inner.GetReferences().AddReference(reference, "/Asset")
        inner.SetInstanceable(True)
        wrapper.GetRootLayer().Save()
        reference = "wrapper.usda"
    source = _new_stage(tmp_path / "source.usda")
    body = UsdGeom.Xform.Define(source, "/Asset/body").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    _collider(source, "/Asset/body/direct", size=1)
    for index in (1, 2):
        instance = UsdGeom.Xform.Define(source, f"/Asset/body/instance{index}")
        instance.GetPrim().GetReferences().AddReference(reference, "/Asset")
        instance.GetPrim().SetInstanceable(True)
        instance.AddTranslateOp().Set(Gf.Vec3d(2 * index, 0, 0))
        before = source.GetRootLayer().ExportToString()
        resolved = _massprops.resolve_body_mass(body)
        # Equal unit cubes at x=0,2[,4], default density 1000 kg/m^3.
        centers = np.arange(index + 1) * 2
        mass = 1000 * len(centers)
        diagonal = np.full(3, mass / 6)
        diagonal[1:] += 1000 * np.sum((centers - centers.mean()) ** 2)
        assert resolved.mass == pytest.approx(mass)
        np.testing.assert_allclose(resolved.center_of_mass, (centers.mean(), 0, 0), atol=1e-6)
        np.testing.assert_allclose(resolved.inertia, np.diag(diagonal), rtol=1e-6, atol=1e-5)
        assert source.GetRootLayer().ExportToString() == before
        assert instance.GetPrim().IsInstance()
    # A batch's next composition must neither reuse old geometry nor retain all
    # preceding asset stages through the scratch cache.
    other = _new_stage(tmp_path / "other.usda")
    other_body = UsdGeom.Xform.Define(other, "/Asset/body").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(other_body)
    other_instance = UsdGeom.Xform.Define(other, "/Asset/body/instance")
    other_instance.GetPrim().GetReferences().AddReference(reference, "/Asset")
    other_instance.GetPrim().SetInstanceable(True)
    other_instance.AddTranslateOp().Set(Gf.Vec3d(7, 0, 0))
    resolved = _massprops.resolve_body_mass(other_body)
    assert resolved.mass == pytest.approx(1000)
    np.testing.assert_allclose(resolved.center_of_mass, (7, 0, 0), atol=1e-6)
    assert len(_massinfo._DEINSTANCED) == 1
    assert next(iter(_massinfo._DEINSTANCED))[0] == other.GetRootLayer().identifier


@pytest.mark.parametrize("joint_type", ["revolute", "breakable_fixed"])
@pytest.mark.parametrize("state", ["enabled", "disabled", "animated"])
def test_surviving_joint_within_welded_group(tmp_path, joint_type, state):
    source = _new_stage(tmp_path / "source.usda")
    for name in ("a", "b"):
        _body(source, f"/Asset/{name}")
        _collider(source, f"/Asset/{name}/collider")
    _fixed_joint(source, "/Asset/weld", "/Asset/a", "/Asset/b")
    if joint_type == "revolute":
        extra = UsdPhysics.RevoluteJoint.Define(source, "/Asset/extra")
    else:
        extra = UsdPhysics.FixedJoint.Define(source, "/Asset/extra")
        extra.CreateBreakForceAttr(5)
    # Resolve descendant endpoints to their owning bodies before deciding.
    extra.CreateBody0Rel().SetTargets(["/Asset/a/collider"])
    extra.CreateBody1Rel().SetTargets(["/Asset/b/collider"])
    extra.CreateJointEnabledAttr(state == "enabled")
    if state == "animated":
        extra.GetJointEnabledAttr().Set(True, 1)
    output = Usd.Stage.Open(source.Flatten())
    before = output.GetRootLayer().ExportToString()
    if state != "disabled":
        with pytest.raises(fixed_joint_merge.MergeRefused, match="surviving joint.*same rigid body"):
            fixed_joint_merge.cook_stage(source, output)
        assert output.GetRootLayer().ExportToString() == before
    else:
        assert fixed_joint_merge.cook_stage(source, output) == 1
        assert UsdPhysics.Joint(output.GetPrimAtPath("/Asset/extra")).GetJointEnabledAttr().Get() is False


@pytest.mark.parametrize("motion", ["linear", "angular", "stationary"])
def test_local_space_velocity_convention_is_not_treated_as_world(tmp_path, motion):
    source = _new_stage(tmp_path / "source.usda")
    for name, rotation in (("a", 0), ("b", 90)):
        prim = _body(source, f"/Asset/{name}")
        UsdGeom.Xformable(prim).AddRotateZOp().Set(rotation)
        # OVPhysX documents this as customData, not a PhysxRigidBodyAPI attribute.
        prim.SetCustomDataByKey("physics:localSpaceVelocities", True)
        api = UsdPhysics.RigidBodyAPI(prim)
        if motion == "linear":
            api.CreateVelocityAttr(Gf.Vec3f(1, 0, 0))
        elif motion == "angular":
            api.CreateAngularVelocityAttr(Gf.Vec3f(90, 0, 0))
    _fixed_joint(source, "/Asset/weld", "/Asset/a", "/Asset/b")
    output = Usd.Stage.Open(source.Flatten())
    before = output.GetRootLayer().ExportToString()
    if motion == "stationary":
        assert fixed_joint_merge.cook_stage(source, output) == 1
        retained = output.GetPrimAtPath("/Asset/a")
        assert retained.GetCustomDataByKey("physics:localSpaceVelocities") is True
        assert UsdPhysics.RigidBodyAPI(retained).GetVelocityAttr().Get() == Gf.Vec3f(0)
        assert UsdPhysics.RigidBodyAPI(retained).GetAngularVelocityAttr().Get() == Gf.Vec3f(0)
    else:
        with pytest.raises(fixed_joint_merge.MergeRefused, match="local-space velocities"):
            fixed_joint_merge.cook_stage(source, output)
        assert output.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("angular", [False, True])
def test_zero_local_velocity_cannot_hide_nonzero_world_motion(tmp_path, angular):
    source = _new_stage(tmp_path / "source.usda")
    retained = _body(source, "/Asset/a")
    retained.SetCustomDataByKey("physics:localSpaceVelocities", True)
    other = _body(source, "/Asset/b")
    api = UsdPhysics.RigidBodyAPI(other)
    attr = api.CreateAngularVelocityAttr() if angular else api.CreateVelocityAttr()
    attr.Set(Gf.Vec3f(1, 0, 0))
    _fixed_joint(source, "/Asset/weld", "/Asset/a", "/Asset/b")
    output = Usd.Stage.Open(source.Flatten())
    before = output.GetRootLayer().ExportToString()
    with pytest.raises(fixed_joint_merge.MergeRefused, match="do not describe one rigid motion"):
        fixed_joint_merge.cook_stage(source, output)
    assert output.GetRootLayer().ExportToString() == before


@pytest.mark.parametrize("attribute,value", [("physics:jointEnabled", False), ("physics:breakForce", 5.)])
def test_animated_weld_is_not_frozen_into_a_compound_body(tmp_path, attribute, value):
    source = _new_stage(tmp_path / "source.usda")
    _body(source, "/Asset/a")
    _body(source, "/Asset/b")
    weld = _fixed_joint(source, "/Asset/weld", "/Asset/a", "/Asset/b")
    # The default pose is welded, but a later sample releases that constraint.
    weld.GetAttribute(attribute).Set(value, 1)
    output = Usd.Stage.Open(source.Flatten())
    before = output.GetRootLayer().ExportToString()
    with pytest.raises(fixed_joint_merge.MergeRefused, match="time-sampled physics:"):
        fixed_joint_merge.cook_stage(source, output)
    assert output.GetRootLayer().ExportToString() == before
