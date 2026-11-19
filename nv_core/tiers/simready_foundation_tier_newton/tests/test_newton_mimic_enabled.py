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

"""Newton mimic detection follows the composed constraint's enable state."""

from types import SimpleNamespace

import pytest
from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_newton.runtime_tests.articulation_phases import mimic_joints
from simready.foundation.tier_newton.runtime_tests.articulation_phases.mimic_joints import (
    detect_mimic_joints,
)


def _mimic_stage(enable_state="missing", physx_compatibility=False):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.SetDefaultPrim(root)
    reference = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/reference")
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/follower").GetPrim()
    schemas = ["NewtonMimicAPI"]
    if physx_compatibility:
        schemas.append("PhysxMimicJointAPI:rotX")
        follower.CreateRelationship("physxMimicJoint:rotX:referenceJoint").SetTargets([reference.GetPath()])
        follower.CreateAttribute("physxMimicJoint:rotX:gearing", Sdf.ValueTypeNames.Float).Set(-1.0)
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(schemas))
    follower.CreateRelationship("newton:mimicJoint").SetTargets([reference.GetPath()])
    follower.CreateAttribute("newton:mimicCoef0", Sdf.ValueTypeNames.Float).Set(0.25)
    follower.CreateAttribute("newton:mimicCoef1", Sdf.ValueTypeNames.Float).Set(-2.0)
    if enable_state != "missing":
        attr = follower.CreateAttribute("newton:mimicEnabled", Sdf.ValueTypeNames.Bool)
        if enable_state != "unauthored":
            attr.Set(enable_state)
    return stage, root


@pytest.mark.parametrize("enable_state", ["missing", "unauthored", True])
def test_newton_mimic_missing_or_true_enable_state_detects_pair(enable_state):
    stage, root = _mimic_stage(enable_state)

    pairs = detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"])

    assert len(pairs) == 1
    assert pairs[0].backend == "newton"
    assert pairs[0].reference_joint_path == "/Robot/reference"
    assert pairs[0].reference_dof_index == 0
    assert pairs[0].follower_dof_index == 1
    assert pairs[0].gear == -2.0
    assert pairs[0].offset == 0.25


@pytest.mark.parametrize("physx_compatibility", [False, True])
def test_disabled_newton_mimic_is_not_detected_or_replaced_by_physx(physx_compatibility):
    stage, root = _mimic_stage(False, physx_compatibility)

    assert detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"]) == []


def test_enabled_newton_mimic_takes_precedence_over_physx_compatibility():
    stage, root = _mimic_stage(True, physx_compatibility=True)

    pairs = detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"])

    assert len(pairs) == 1
    assert pairs[0].backend == "newton"
    assert pairs[0].gear == -2.0


def test_physx_compatibility_mimic_is_discovered_with_standalone_schemas():
    try:
        from pxr import PhysxSchema
    except ImportError:
        from physx_usd_schemas import PhysxSchema

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Robot", "Xform")
    stage.SetDefaultPrim(root)
    reference = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/reference")
    follower = UsdPhysics.RevoluteJoint.Define(stage, "/Robot/follower")
    api = PhysxSchema.PhysxMimicJointAPI.Apply(follower.GetPrim(), "rotX")
    api.CreateReferenceJointRel().SetTargets([reference.GetPath()])
    api.CreateGearingAttr(-1.0)
    api.CreateOffsetAttr(0.0)

    pairs = detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"])

    assert len(pairs) == 1
    assert pairs[0].backend == "physx"
    assert pairs[0].reference_joint_path == "/Robot/reference"
    assert pairs[0].follower_joint_path == "/Robot/follower"
    assert pairs[0].gear == -1.0


@pytest.mark.parametrize("native_newton", [False, True])
@pytest.mark.parametrize("schema_accessor", ["type_info", "raw_metadata", "registered"])
def test_equality_api_overrides_native_and_physx_mimic(monkeypatch, native_newton, schema_accessor):
    stage, root = _mimic_stage(True, physx_compatibility=True)
    follower = stage.GetPrimAtPath("/Robot/follower")
    schemas = ["MjcEqualityJointAPI", "PhysxMimicJointAPI:rotX"]
    if native_newton:
        schemas.append("NewtonMimicAPI")
    follower.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(schemas))

    # Real USD authors the composed schemas and constraint fields. Adapters
    # select each discovery surface without requiring registered SDK plugins.
    class ApiSurface:
        def __getattr__(self, name):
            return getattr(follower, name)

        def HasAPI(self, schema):
            return schema_accessor == "registered" and schema in schemas

        def GetPrimTypeInfo(self):
            names = schemas if schema_accessor == "type_info" else []
            return SimpleNamespace(GetAppliedAPISchemas=lambda: names)

    from simready.foundation.tier_newton.runtime_tests.articulation_phases import joint_identity

    select_real_joints = joint_identity.selected_joint_prims

    def select_api_surfaces(*args, **kwargs):
        selected = select_real_joints(*args, **kwargs)
        return [ApiSurface() if prim.GetPath() == follower.GetPath() else prim for prim in selected]

    monkeypatch.setattr(joint_identity, "selected_joint_prims", select_api_surfaces)
    if schema_accessor != "raw_metadata":
        monkeypatch.setattr(mimic_joints, "_raw_applied_api_names", lambda prim: [])

    def unexpected_compatibility(*args):
        raise AssertionError("An equality-controlled joint fell back to a PhysX mimic constraint")

    import pxr

    monkeypatch.setattr(pxr, "PhysxSchema", SimpleNamespace(PhysxMimicJointAPI=unexpected_compatibility), raising=False)
    assert detect_mimic_joints(stage, root, "/Robot", ["reference", "follower"]) == []
