# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Behaviour of the OPT.001, OPT.002, and OPT.003 checkers.

Every rule here is asserted to *fail* on a stage built to violate it, not only to
pass on a good one. A checker that raises inside ``CheckStage`` reports no issues
and therefore reads as a pass, so a suite that only tests the happy path cannot
tell a working rule from a broken one. That is not hypothetical: an OPT.002
revision shipped with an unimported name and passed every asset it was given.
"""

from __future__ import annotations

import pytest
from conftest import _body, _fixed_joint, _mesh, _new_stage
from pxr import Sdf, UsdGeom, UsdPhysics

from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations import validation


def issues(checker_class, stage):
    checker = checker_class()
    checker.CheckStage(stage)
    return list(checker.GetIssues())


def test_opt001_fails_on_welded_dynamic_pair(welded_pair):
    from pxr import Usd
    stage = Usd.Stage.Open(str(welded_pair))
    found = issues(validation.MergeableBodyPairChecker, stage)
    assert len(found) == 1
    assert "/Asset/Joints/weld" in str(found[0])


def test_opt001_ignores_breakable_joint(tmp_path):
    """A finite break force is authored behaviour, so the pair must stay."""
    stage = _new_stage(tmp_path / "breakable.usda")
    _body(stage, "/Asset/a")
    _body(stage, "/Asset/b", translate=(0.0, 0.0, 0.2))
    _fixed_joint(stage, "/Asset/weld", "/Asset/a", "/Asset/b", break_force=500.0)
    assert issues(validation.MergeableBodyPairChecker, stage) == []


def test_opt001_ignores_kinematic_body(tmp_path):
    stage = _new_stage(tmp_path / "kinematic.usda")
    _body(stage, "/Asset/a", dynamic=False)
    _body(stage, "/Asset/b", translate=(0.0, 0.0, 0.2))
    _fixed_joint(stage, "/Asset/weld", "/Asset/a", "/Asset/b")
    assert issues(validation.MergeableBodyPairChecker, stage) == []


def test_opt001_ignores_disabled_joint(tmp_path):
    """physics:jointEnabled=false welds nothing, which is what the merge authors."""
    stage = _new_stage(tmp_path / "disabled.usda")
    _body(stage, "/Asset/a")
    _body(stage, "/Asset/b", translate=(0.0, 0.0, 0.2))
    joint = _fixed_joint(stage, "/Asset/weld", "/Asset/a", "/Asset/b")
    UsdPhysics.Joint(joint).CreateJointEnabledAttr().Set(False)
    assert issues(validation.MergeableBodyPairChecker, stage) == []


def test_opt001_ignores_world_anchor(tmp_path):
    """One end naming a non-body is root fixation, a separate decision."""
    stage = _new_stage(tmp_path / "anchor.usda")
    _body(stage, "/Asset/b")
    UsdGeom.Xform.Define(stage, "/Asset/world")
    _fixed_joint(stage, "/Asset/weld", "/Asset/world", "/Asset/b")
    assert issues(validation.MergeableBodyPairChecker, stage) == []


def test_opt002_fails_on_two_visual_meshes(tmp_path):
    stage = _new_stage(tmp_path / "meshes.usda")
    _body(stage, "/Asset/body")
    _mesh(stage, "/Asset/body/one")
    _mesh(stage, "/Asset/body/two")
    found = issues(validation.MultipleVisualMeshesChecker, stage)
    assert len(found) == 1
    assert "/Asset/body" in str(found[0])


def test_opt002_passes_on_single_visual_mesh(tmp_path):
    stage = _new_stage(tmp_path / "one_mesh.usda")
    _body(stage, "/Asset/body")
    _mesh(stage, "/Asset/body/one")
    assert issues(validation.MultipleVisualMeshesChecker, stage) == []


def test_opt002_excludes_collision_meshes(tmp_path):
    """A mesh carrying CollisionAPI is not a visual mesh and must not be counted."""
    stage = _new_stage(tmp_path / "collision_meshes.usda")
    _body(stage, "/Asset/body")
    for name in ("one", "two"):
        mesh = _mesh(stage, f"/Asset/body/{name}")
        UsdPhysics.CollisionAPI.Apply(mesh)
    assert issues(validation.MultipleVisualMeshesChecker, stage) == []


def test_opt002_attributes_nested_body_meshes_to_the_nested_body(tmp_path):
    """Meshes under a nested body belong to it, not to the outer body."""
    stage = _new_stage(tmp_path / "nested.usda")
    _body(stage, "/Asset/outer")
    _mesh(stage, "/Asset/outer/own")
    _body(stage, "/Asset/outer/inner", translate=(0.0, 0.0, 0.1))
    _mesh(stage, "/Asset/outer/inner/a")
    _mesh(stage, "/Asset/outer/inner/b")
    found = issues(validation.MultipleVisualMeshesChecker, stage)
    assert len(found) == 1
    assert "/Asset/outer/inner" in str(found[0])


def _render_mesh(stage, path):
    prim = _mesh(stage, path)
    UsdGeom.Imageable(prim).CreatePurposeAttr().Set(UsdGeom.Tokens.render)
    return prim


def test_opt003_fails_on_disabled_collision_schema_stack(tmp_path):
    stage = _new_stage(tmp_path / "inactive_render_collision.usda")
    prim = _render_mesh(stage, "/Asset/render")
    collision = UsdPhysics.CollisionAPI.Apply(prim)
    collision.CreateCollisionEnabledAttr().Set(False)
    UsdPhysics.MeshCollisionAPI.Apply(prim)

    found = issues(validation.InactiveRenderCollisionSchemasChecker, stage)
    assert len(found) == 1
    assert "/Asset/render" in str(found[0])
    assert "PhysicsCollisionAPI" in str(found[0])


def test_opt003_fails_on_companion_schema_without_base_collision(tmp_path):
    stage = _new_stage(tmp_path / "orphaned_collision_schema.usda")
    prim = _render_mesh(stage, "/Asset/render")
    prim.SetMetadata(
        "apiSchemas",
        Sdf.TokenListOp.CreateExplicit(
            ["PhysicsMeshCollisionAPI", "PhysxCollisionAPI"]
        ),
    )

    found = issues(validation.InactiveRenderCollisionSchemasChecker, stage)
    assert len(found) == 1
    assert "PhysxCollisionAPI" in str(found[0])


def test_opt003_allows_enabled_collider_that_is_also_renderable(tmp_path):
    stage = _new_stage(tmp_path / "active_render_collision.usda")
    prim = _render_mesh(stage, "/Asset/render_and_collision")
    UsdPhysics.CollisionAPI.Apply(prim)
    assert issues(validation.InactiveRenderCollisionSchemasChecker, stage) == []


def test_opt003_ignores_non_render_purpose(tmp_path):
    stage = _new_stage(tmp_path / "proxy_collision.usda")
    prim = _mesh(stage, "/Asset/proxy")
    UsdGeom.Imageable(prim).CreatePurposeAttr().Set(UsdGeom.Tokens.proxy)
    collision = UsdPhysics.CollisionAPI.Apply(prim)
    collision.CreateCollisionEnabledAttr().Set(False)
    assert issues(validation.InactiveRenderCollisionSchemasChecker, stage) == []


@pytest.mark.parametrize(
    "checker",
    [
        validation.MergeableBodyPairChecker,
        validation.MultipleVisualMeshesChecker,
        validation.InactiveRenderCollisionSchemasChecker,
    ],
)
def test_checkers_report_missing_default_prim(tmp_path, checker):
    """No default prim is reported, not silently treated as conformant."""
    from pxr import Usd
    stage = Usd.Stage.CreateNew(str(tmp_path / f"nodefault_{checker.__name__}.usda"))
    UsdGeom.Xform.Define(stage, "/Asset")
    assert len(issues(checker, stage)) == 1


@pytest.mark.parametrize(
    "checker",
    [
        validation.MergeableBodyPairChecker,
        validation.MultipleVisualMeshesChecker,
        validation.InactiveRenderCollisionSchemasChecker,
    ],
)
def test_checkers_pass_without_applicable_physics(tmp_path, checker):
    stage = _new_stage(tmp_path / f"visual_only_{checker.__name__}.usda")
    _mesh(stage, "/Asset/visual")
    before = stage.GetRootLayer().ExportToString()

    assert issues(checker, stage) == []
    assert stage.GetRootLayer().ExportToString() == before
