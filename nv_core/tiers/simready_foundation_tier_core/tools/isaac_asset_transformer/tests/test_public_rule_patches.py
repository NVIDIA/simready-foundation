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
from __future__ import annotations

from pathlib import Path

import pytest
from isaacsim.asset.transformer import manager
from isaacsim.asset.transformer.rules.isaac_sim.joint_state_api import JointStateAPIRule
from isaacsim.asset.transformer.rules.isaac_sim.robot_schema import RobotSchemaRule
from isaacsim.asset.transformer.rules.perf.geometries import GeometriesRoutingRule
from isaacsim.asset.transformer.rules.perf.materials import MaterialsRoutingRule
from isaacsim.asset.transformer.rules.structure import variants
from isaacsim.asset.transformer.rules.structure.flatten import FlattenRule
from pxr import Sdf, Usd, UsdPhysics
from simready.asset_transformer.patches import PATCH_VERSION
from simready.asset_transformer.patches import apply as patch_module
from simready.asset_transformer.patches import apply_simready_rule_patches
from usd.schema.isaac import robot_schema


def test_public_robot_schema_is_available() -> None:
    assert robot_schema.__name__ == "usd.schema.isaac.robot_schema"
    assert RobotSchemaRule.__module__.startswith("isaacsim.asset.transformer.rules.")
    assert not hasattr(RobotSchemaRule, "__simready_patch_version__")


def test_patches_are_idempotent_and_limited_to_remaining_upstream_gaps() -> None:
    apply_simready_rule_patches()
    apply_simready_rule_patches()

    for target in (GeometriesRoutingRule, variants, manager):
        assert getattr(target, "__simready_patch_version__") == PATCH_VERSION
    assert GeometriesRoutingRule.__module__.startswith("isaacsim.asset.transformer.rules.")
    # The 6.0.1 material, flatten, and joint-state fixes are upstream in 6.2.
    for rule_class in (MaterialsRoutingRule, FlattenRule, JointStateAPIRule):
        assert not hasattr(rule_class, "__simready_patch_version__")


def test_upstream_joint_state_rule_authors_schema_without_registered_physx_schema(tmp_path) -> None:
    stage = Usd.Stage.CreateInMemory()
    joint = UsdPhysics.RevoluteJoint.Define(stage, "/joint").GetPrim()

    rule = JointStateAPIRule(stage, str(tmp_path), "", {"params": {}})
    assert rule.process_rule() is None
    assert "PhysicsJointStateAPI:angular" in joint.GetAppliedSchemas()


def test_upstream_materials_rule_transfers_local_udim_family(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "Textures"
    materials_dir = tmp_path / "payloads"
    source_dir.mkdir()
    output_dir.mkdir()
    materials_dir.mkdir()

    for tile in ("albedo.1001.png", "albedo.1002.png"):
        (source_dir / tile).write_bytes(b"tile")
    (source_dir / "normal.1001.png").write_bytes(b"unrelated")

    rule = MaterialsRoutingRule(Usd.Stage.CreateInMemory(), str(tmp_path), "payloads", {"params": {}})
    template = source_dir / "albedo.%3CUDIM%3E.png"
    mapping = rule._transfer_all_assets(
        [str(template)],
        str(output_dir),
        str(materials_dir),
        download_remote=False,
    )

    assert mapping[str(template)] == "../Textures/albedo.<UDIM>.png"
    assert sorted(path.name for path in output_dir.iterdir()) == ["albedo.1001.png", "albedo.1002.png"]


def test_publish_keeps_search_path_assets_bare(tmp_path: Path) -> None:
    """Built-in MDL identifiers such as ``OmniPBR.mdl`` are search paths, not
    package files. Publication must not anchor them as ``./OmniPBR.mdl``, while
    bare paths that name a generated package file are still anchored.
    """
    apply_simready_rule_patches()
    staging = tmp_path / "staging"
    output = tmp_path / "output"
    (staging / "payloads").mkdir(parents=True)
    output.mkdir()
    (staging / "payloads/sibling.usda").write_text("#usda 1.0\n", encoding="utf-8")

    layer = Sdf.Layer.CreateNew(str(staging / "payloads/materials.usda"))
    shader = Sdf.CreatePrimInLayer(layer, "/Materials/M/Shader")
    shader.specifier = Sdf.SpecifierDef
    builtin = Sdf.AttributeSpec(shader, "info:mdl:sourceAsset", Sdf.ValueTypeNames.Asset)
    builtin.default = Sdf.AssetPath("OmniPBR.mdl")
    sibling = Sdf.AttributeSpec(shader, "simready:test:sibling", Sdf.ValueTypeNames.Asset)
    sibling.default = Sdf.AssetPath("sibling.usda")
    layer.Save()
    layer = None

    manager._publish_staged_package(str(staging), str(output), None)

    published = Sdf.Layer.FindOrOpen(str(output / "payloads/materials.usda"))
    shader = published.GetPrimAtPath("/Materials/M/Shader")
    assert shader.attributes["info:mdl:sourceAsset"].default.path == "OmniPBR.mdl"
    assert shader.attributes["simready:test:sibling"].default.path == "./sibling.usda"


def test_version_guard_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(patch_module, "_installed_version", lambda: "6.2.0.2")
    with pytest.raises(RuntimeError, match="support.*6.2.0.1.*found 6.2.0.2"):
        patch_module._validate_target()


def test_signature_guard_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(variants, "copy_file_to_directory", lambda src_path, dest_dir: None)
    with pytest.raises(RuntimeError, match="changed upstream method signature"):
        patch_module._validate_target()
