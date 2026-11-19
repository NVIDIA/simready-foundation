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
"""Behaviour of the render/collision separation adapter."""

from __future__ import annotations

import shutil

import pytest
from conftest import _body, _collider, _mesh, _new_stage
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization import (
    render_collision_separation,
)
from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations._common import (
    COLLISION_SCHEMA_TOKENS,
    applied_schemas,
    inactive_render_collision_schemas,
    world_transform,
)


@pytest.fixture
def separated_stages(tmp_path):
    source_path = tmp_path / "render_collision.usda"
    stage = _new_stage(source_path)

    render = _mesh(stage, "/Asset/render")
    UsdGeom.Imageable(render).CreatePurposeAttr().Set(UsdGeom.Tokens.render)
    render.SetMetadata(
        "apiSchemas",
        Sdf.TokenListOp.CreateExplicit(
            [
                "PhysicsCollisionAPI",
                "PhysicsMeshCollisionAPI",
                "PhysxCollisionAPI",
                "MaterialBindingAPI",
            ]
        ),
    )
    render.CreateAttribute(
        "physics:collisionEnabled", Sdf.ValueTypeNames.Bool
    ).Set(False)

    _body(stage, "/Asset/body")
    active = _collider(stage, "/Asset/body/collider")
    UsdGeom.Xformable(active).AddTranslateOp().Set(Gf.Vec3d(1.0, 2.0, 3.0))
    material = UsdGeom.Scope.Define(stage, "/Asset/PhysicsMaterial").GetPrim()
    UsdPhysics.MaterialAPI.Apply(material)
    active.CreateRelationship("material:binding:physics").SetTargets(
        [material.GetPath()]
    )

    stage.GetRootLayer().Save()
    output_path = tmp_path / "render_collision_out.usda"
    shutil.copy2(source_path, output_path)
    return Usd.Stage.Open(str(source_path)), Usd.Stage.Open(str(output_path))


def _active_collider_snapshot(stage):
    prim = stage.GetPrimAtPath("/Asset/body/collider")
    owner = prim.GetParent()
    return (
        (str(prim.GetPath()), str(owner.GetPath())),
        world_transform(prim),
        tuple(applied_schemas(prim)),
        tuple(prim.GetRelationship("material:binding:physics").GetTargets()),
    )


def test_removes_only_the_inactive_collision_schema_stack(separated_stages):
    _input_stage, output_stage = separated_stages
    render = output_stage.GetPrimAtPath("/Asset/render")
    spec = output_stage.GetRootLayer().GetPrimAtPath(render.GetPath())
    authored_before = set(spec.GetInfo("apiSchemas").explicitItems)
    effective_before = set(applied_schemas(render))

    assert len(authored_before & COLLISION_SCHEMA_TOKENS) == 3
    assert len(effective_before & COLLISION_SCHEMA_TOKENS) == 3
    assert len(inactive_render_collision_schemas(render)) == 3
    assert render_collision_separation.cook_stage(output_stage) == 1

    render = output_stage.GetPrimAtPath("/Asset/render")
    spec = output_stage.GetRootLayer().GetPrimAtPath(render.GetPath())
    authored_after = set(spec.GetInfo("apiSchemas").explicitItems)
    effective_after = set(applied_schemas(render))

    assert len(authored_after & COLLISION_SCHEMA_TOKENS) == 0
    assert len(effective_after & COLLISION_SCHEMA_TOKENS) == 0
    assert inactive_render_collision_schemas(render) == []
    assert "MaterialBindingAPI" in effective_after


def test_preserves_active_collider_transform_and_material(separated_stages):
    input_stage, output_stage = separated_stages
    before = _active_collider_snapshot(input_stage)

    render_collision_separation.cook_stage(output_stage)

    assert _active_collider_snapshot(output_stage) == before


def test_is_idempotent(separated_stages):
    _input_stage, output_stage = separated_stages
    assert render_collision_separation.cook_stage(output_stage) == 1
    assert render_collision_separation.cook_stage(output_stage) == 0
