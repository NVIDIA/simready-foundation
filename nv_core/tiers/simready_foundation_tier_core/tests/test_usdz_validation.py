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
"""Generated loose/USDZ parity coverage for package-aware validators."""

import zipfile
from pathlib import Path

import pytest
from pxr import Kind, Sdf, Usd, UsdUtils
from simready.foundation.tier_core.rules_and_reqs.core.naming_paths.validation import (
    AssetFolderStructureChecker,
    DirectoryStructureChecker,
    MetadataLocationChecker,
    PathLengthLimitsChecker,
    PathsExistChecker,
)
from simready.foundation.tier_core.rules_and_reqs.core.path_utils import (
    anchored_asset_identifier,
    delivered_asset_identifier,
    file_exists,
    package_member_names,
    sidecar_json_identifier,
    sidecar_json_identifiers,
    thumbnail_png_identifier,
)
from simready.foundation.tier_core.rules_and_reqs.isaac_sim.composition.validation import (
    IsaacCompositionCapabilityChecker,
)


def _make_layer(path: Path, references=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(path.as_posix())
    root = stage.DefinePrim("/Asset", "Xform")
    stage.SetDefaultPrim(root)
    for reference in references:
        root.GetReferences().AddReference(reference)
    stage.GetRootLayer().Save()


def _make_composition(tmp_path: Path, layout: str, base_arc: str = "payload") -> Path:
    payloads = tmp_path / "payloads"
    if layout == "legacy":
        roles = {
            "base": "chair_base.usdc",
            "meshes": "chair_meshes.usda",
            "physics": "chair_physics.usd",
        }
    else:
        roles = {
            "base": "base.usdc",
            "geometries": "geometries.usd",
            "instances": "instances.usda",
            "materials": "materials.usdc",
        }

    base_references = [f"./{filename}" for role, filename in roles.items() if role != "base"]
    for role, filename in roles.items():
        _make_layer(payloads / filename, base_references if role == "base" else ())

    root_path = tmp_path / "asset.usda"
    stage = Usd.Stage.CreateNew(root_path.as_posix())
    root = stage.DefinePrim("/Asset", "Xform")
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    if base_arc == "reference":
        root.GetReferences().AddReference(f"./payloads/{roles['base']}")
    else:
        root.GetPayloads().AddPayload(f"./payloads/{roles['base']}")
    stage.GetRootLayer().Save()
    return root_path


@pytest.mark.parametrize("layout", ["legacy", "performance"])
@pytest.mark.parametrize("base_arc", ["reference", "payload"])
def test_isa001_loose_and_usdz_have_validation_parity(tmp_path, layout, base_arc):
    root_path = _make_composition(tmp_path / layout / base_arc, layout, base_arc)
    package_path = tmp_path / f"{layout}-{base_arc}.usdz"
    assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(root_path.as_posix()), package_path.as_posix())

    issue_counts = []
    for identifier in (root_path.as_posix(), package_path.as_posix()):
        stage = Usd.Stage.Open(identifier, load=Usd.Stage.LoadNone)
        assert stage
        checker = IsaacCompositionCapabilityChecker()
        checker.CheckStage(stage)
        issue_counts.append(len(checker._issues))

    assert issue_counts == [0, 0]


def test_isa001_does_not_count_missing_authored_layers(tmp_path):
    root_path = tmp_path / "asset.usda"
    stage = Usd.Stage.CreateNew(root_path.as_posix())
    root = stage.DefinePrim("/Asset", "Xform")
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    for role in ("base", "geometries", "instances", "materials"):
        root.GetReferences().AddReference(f"./payloads/{role}.usd")
    stage.GetRootLayer().Save()

    checker = IsaacCompositionCapabilityChecker()
    checker.CheckStage(Usd.Stage.Open(root_path.as_posix(), load=Usd.Stage.LoadNone))

    assert checker._issues


def test_package_helpers_keep_outer_and_inner_identifiers_distinct(tmp_path):
    root_path = _make_composition(tmp_path / "asset", "performance")
    package_path = tmp_path / "robot.usdz"
    assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(root_path.as_posix()), package_path.as_posix())

    stage = Usd.Stage.Open(package_path.as_posix(), load=Usd.Stage.LoadNone)
    root_layer = stage.GetRootLayer()
    base_identifier = anchored_asset_identifier(root_layer, "./payloads/base.usdc")

    assert delivered_asset_identifier(root_layer) == package_path.as_posix()
    assert base_identifier.endswith(".usdz[payloads/base.usdc]")
    assert file_exists(base_identifier)
    assert "payloads/base.usdc" in package_member_names(package_path.as_posix())
    assert sidecar_json_identifier(root_layer) == (tmp_path / "robot.json").as_posix()
    assert thumbnail_png_identifier(root_layer) == (tmp_path / ".thumbs" / "256x256" / "robot.usdz.png").as_posix()


def test_delivered_identifier_uses_resolved_path_for_relative_stage(tmp_path, monkeypatch):
    asset_dir = tmp_path / "manufacturer" / "robot"
    asset = asset_dir / "robot.usda"
    _make_layer(asset)
    monkeypatch.chdir(asset_dir)

    stage = Usd.Stage.Open("robot.usda")

    assert delivered_asset_identifier(stage.GetRootLayer()) == asset.as_posix()


def test_embedded_json_is_not_an_external_sidecar(tmp_path):
    package = tmp_path / "asset.usdz"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("root.usda", "#usda 1.0\n")
        archive.writestr("asset.json", "{}")

    assert sidecar_json_identifiers(f"{package.as_posix()}[root.usda]") == ()


def test_naming_path_validators_have_loose_and_usdz_parity(tmp_path):
    identifiers = []
    for encoding in ("loose", "package"):
        asset_dir = tmp_path / encoding / "chair" / "payload"
        root_path = _make_composition(asset_dir, "legacy")
        stage = Usd.Stage.Open(root_path.as_posix())
        stage.GetRootLayer().customLayerData = {"SimReady_Metadata": {"asset_name": "chair"}}
        stage.GetRootLayer().Save()

        if encoding == "package":
            package_path = asset_dir / "chair.usdz"
            assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(root_path.as_posix()), package_path.as_posix())
            root_path.unlink()
            identifiers.append(package_path.as_posix())
        else:
            loose_path = asset_dir / "chair.usdc"
            assert stage.GetRootLayer().Export(loose_path.as_posix())
            root_path.unlink()
            identifiers.append(loose_path.as_posix())

    checker_types = (
        DirectoryStructureChecker,
        PathLengthLimitsChecker,
        AssetFolderStructureChecker,
        MetadataLocationChecker,
        PathsExistChecker,
    )
    results = []
    for identifier in identifiers:
        stage = Usd.Stage.Open(identifier)
        issue_counts = []
        for checker_type in checker_types:
            checker = checker_type()
            checker.CheckStage(stage)
            issue_counts.append(len(checker._issues))
        results.append(issue_counts)

    assert results[0] == results[1] == [0, 0, 0, 0, 0]


def _make_mdl_material(path: Path, source_asset: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(path.as_posix())
    root = stage.DefinePrim("/Asset", "Xform")
    stage.SetDefaultPrim(root)
    shader = stage.DefinePrim("/Asset/Looks/Material/Shader", "Shader")
    shader.CreateAttribute("info:implementationSource", Sdf.ValueTypeNames.Token, variability=Sdf.VariabilityUniform).Set(
        "sourceAsset"
    )
    shader.CreateAttribute("info:mdl:sourceAsset", Sdf.ValueTypeNames.Asset, variability=Sdf.VariabilityUniform).Set(
        Sdf.AssetPath(source_asset)
    )
    stage.GetRootLayer().Save()


@pytest.mark.parametrize(
    "source_asset, reported",
    [
        # The runtime resolves these from its own MDL search path; VM.MDL.001 exempts them.
        ("OmniPBR.mdl", False),
        ("OmniPBR_Opacity.mdl", False),
        ("nvidia/core_definitions.mdl", False),
        # These name a location or a module the runtime does not ship, so the file must exist.
        ("./OmniPBR.mdl", True),
        ("materials/OmniPBR.mdl", True),
        ("Custom.mdl", True),
    ],
)
def test_np008_does_not_look_for_runtime_shipped_mdl_modules(tmp_path, source_asset, reported):
    root_path = tmp_path / "asset" / "root.usda"
    _make_mdl_material(root_path, source_asset)

    checker = PathsExistChecker()
    checker.CheckStage(Usd.Stage.Open(root_path.as_posix()))

    assert bool(checker._issues) is reported, [str(issue) for issue in checker._issues]
