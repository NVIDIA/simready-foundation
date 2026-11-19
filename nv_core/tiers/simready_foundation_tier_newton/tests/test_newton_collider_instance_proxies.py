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

"""nvBug 6976369: Newton collision checks must visit instance proxies."""

import pytest
from pxr import Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_newton.rules_and_reqs.physics_bodies.physics_rigid_bodies.validation import (
    NewtonColliderAPIChecker,
)


@pytest.mark.parametrize("instanceable", [False, True])
@pytest.mark.parametrize("representation", [None, "NewtonMeshCollisionAPI", "NewtonSDFCollisionAPI"])
@pytest.mark.parametrize("active", [False, True])
def test_newton_collider_schema(instanceable, representation, active):
    stage = Usd.Stage.CreateInMemory()
    stage.SetDefaultPrim(UsdGeom.Xform.Define(stage, "/World").GetPrim())
    source = stage.CreateClassPrim("/Source")
    collider = UsdGeom.Mesh.Define(stage, "/Source/Col").GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    UsdPhysics.MeshCollisionAPI.Apply(collider)
    if representation:
        collider.AddAppliedSchema("NewtonCollisionAPI")
        collider.AddAppliedSchema(representation)
    collider.SetActive(active)
    inst = UsdGeom.Xform.Define(stage, "/World/Inst").GetPrim()
    inst.GetReferences().AddInternalReference(source.GetPath())
    inst.SetInstanceable(instanceable)
    assert inst.IsInstance() == instanceable
    checker = NewtonColliderAPIChecker()
    checker.CheckStage(stage)
    issues = checker.GetIssues()
    assert len(issues) == (1 if active and representation is None else 0)
    if issues:
        assert "/World/Inst/Col" in issues[0].message
