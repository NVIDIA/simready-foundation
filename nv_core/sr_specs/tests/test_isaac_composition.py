# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ISA.001 Isaac composition checker.

The checker must judge an asset from its composed stage rather than from the
surrounding directory listing, so that a `.usdz` package -- whose ``payloads/``
layers are archive members with no counterpart on disk -- validates the same way
as the equivalent unpacked directory tree.

The `.usdz` fixture is built at test time rather than committed: `*.usdz` is a
Git LFS pattern in this repository, and constructing the package here keeps the
required layout readable in review and the fixture in sync with these tests.

Run with:
    pytest nv_core/sr_specs/tests/test_isaac_composition.py
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from pxr import Kind, Sdf, Usd, UsdGeom, UsdUtils

import simready.validate as sv

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPABILITIES_PATH = REPO_ROOT / "nv_core" / "sr_specs" / "docs" / "capabilities"
FEATURES_PATH = REPO_ROOT / "nv_core" / "sr_specs" / "docs" / "features"
PROFILES_PATH = REPO_ROOT / "nv_core" / "sr_specs" / "docs" / "profiles"

ISA_001 = "com.nvidia.simready.ISA.001"

SAMPLE_PROP = (
    REPO_ROOT
    / "sample_content"
    / "common_assets"
    / "props_general"
    / "obs_workbench_tool_a01"
    / "isaacsim_usd"
    / "sm_obs_workbench_tool_a01_01.usd"
)


@pytest.fixture(scope="session")
def checker_class():
    """Load the validation implementation and return the ISA.001 checker class.

    ``sv.initialize`` generates the ``omni.capabilities`` requirement enums from
    the requirement docs and injects them, so the checker module cannot be
    imported before it runs.
    """
    sv.initialize(
        rules_and_requirements_paths=[CAPABILITIES_PATH],
        features_paths=[FEATURES_PATH],
        profiles_paths=[PROFILES_PATH],
    )
    module = importlib.import_module("capabilities.isaac_sim.composition.validation")
    yield module.IsaacCompositionCapabilityChecker
    sv.destroy()


def isa_001_failures(checker_class, stage: Usd.Stage) -> list[str]:
    """Run the checker over *stage* and return its ISA.001 failure messages."""
    checker = checker_class()
    checker.CheckStage(stage)
    return [
        str(getattr(issue, "message", issue))
        for issue in checker.GetIssues()
        if issue.requirement is not None and issue.requirement.code == ISA_001
    ]


def _define_default_prim(stage: Usd.Stage, path: str = "/MyAsset") -> Usd.Prim:
    xform = UsdGeom.Xform.Define(stage, path)
    stage.SetDefaultPrim(xform.GetPrim())
    return xform.GetPrim()


def build_isaac_asset(root: Path, meshes_visible: bool = False) -> Path:
    """Author a minimal, correctly composed Isaac asset tree under *root*.

    Layout matches the ISA.001 requirement doc:

        myasset.usda
        payloads/myasset_base.usd      <- referenced by the default prim
        payloads/myasset_meshes.usd    <- referenced by the base layer
        payloads/myasset_physics.usd   <- payloaded by the default prim
    """
    (root / "payloads").mkdir(parents=True, exist_ok=True)

    meshes = Usd.Stage.CreateNew(str(root / "payloads" / "myasset_meshes.usd"))
    _define_default_prim(meshes)
    for scope_name in ("Looks", "Meshes", "Visuals"):
        scope = UsdGeom.Scope.Define(meshes, f"/MyAsset/{scope_name}")
        if scope_name == "Looks":
            continue
        visibility = UsdGeom.Tokens.inherited if meshes_visible else UsdGeom.Tokens.invisible
        UsdGeom.Imageable(scope).CreateVisibilityAttr(visibility)
    UsdGeom.Mesh.Define(meshes, "/MyAsset/Meshes/mesh_obj_01")
    meshes.Save()

    base = Usd.Stage.CreateNew(str(root / "payloads" / "myasset_base.usd"))
    _define_default_prim(base).GetReferences().AddReference("./myasset_meshes.usd")
    base.Save()

    physics = Usd.Stage.CreateNew(str(root / "payloads" / "myasset_physics.usd"))
    _define_default_prim(physics)
    physics.Save()

    main_path = root / "myasset.usda"
    main = Usd.Stage.CreateNew(str(main_path))
    default_prim = _define_default_prim(main)
    Usd.ModelAPI(default_prim).SetKind(Kind.Tokens.component)
    default_prim.GetReferences().AddReference("./payloads/myasset_base.usd")
    default_prim.GetPayloads().AddPayload("./payloads/myasset_physics.usd")
    main.Save()

    return main_path


@pytest.fixture(scope="session")
def unpacked_asset(tmp_path_factory) -> Path:
    return build_isaac_asset(tmp_path_factory.mktemp("unpacked"))


@pytest.fixture(scope="session")
def usdz_asset(tmp_path_factory) -> Path:
    """Package the same asset into a single `.usdz` and return its path."""
    work_dir = tmp_path_factory.mktemp("packaged")
    main_path = build_isaac_asset(work_dir / "src")
    usdz_path = work_dir / "myasset.usdz"
    assert UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(main_path)), str(usdz_path))
    return usdz_path


def test_usdz_payload_layers_are_package_relative(usdz_asset):
    """Guards the premise of the fix: usdz payloads exist only inside the archive."""
    assert not (usdz_asset.parent / "payloads").exists()

    stage = Usd.Stage.Open(str(usdz_asset))
    packaged = [layer.identifier for layer in stage.GetUsedLayers() if ".usdz[" in layer.identifier]
    assert any("payloads/myasset_base.usd]" in identifier for identifier in packaged)
    assert any("payloads/myasset_meshes.usd]" in identifier for identifier in packaged)
    assert any("payloads/myasset_physics.usd]" in identifier for identifier in packaged)


def test_packaged_asset_passes(checker_class, usdz_asset):
    """A correctly composed asset delivered as `.usdz` must pass ISA.001."""
    stage = Usd.Stage.Open(str(usdz_asset))
    assert isa_001_failures(checker_class, stage) == []


def test_unpacked_asset_passes(checker_class, unpacked_asset):
    """The same asset as a directory tree must pass identically."""
    stage = Usd.Stage.Open(str(unpacked_asset))
    assert isa_001_failures(checker_class, stage) == []


def test_packaged_and_unpacked_agree(checker_class, usdz_asset, unpacked_asset):
    """Packaging must not change the verdict."""
    packaged = isa_001_failures(checker_class, Usd.Stage.Open(str(usdz_asset)))
    unpacked = isa_001_failures(checker_class, Usd.Stage.Open(str(unpacked_asset)))
    assert packaged == unpacked


def test_flat_asset_still_fails(checker_class, tmp_path):
    """An asset with no payload structure at all must still fail."""
    stage = Usd.Stage.CreateNew(str(tmp_path / "flat.usda"))
    default_prim = _define_default_prim(stage)
    Usd.ModelAPI(default_prim).SetKind(Kind.Tokens.component)
    UsdGeom.Mesh.Define(stage, "/MyAsset/mesh_01")
    stage.Save()

    failures = isa_001_failures(checker_class, stage)
    assert failures, "a flat asset must not pass ISA.001"
    assert any("No recognized Isaac Sim payload structure" in message for message in failures)


def build_robot_asset(root: Path, omit: str | None = None) -> Path:
    """Author the RC.001 robot payload layout, optionally omitting one layer.

    ``Robot-Body-Isaac`` includes ISA.001, so this layout must satisfy the
    requirement too: ``payloads/base.usda`` referencing ``geometries.usd``,
    ``instances.usda`` and ``materials.usda``.
    """
    (root / "payloads").mkdir(parents=True, exist_ok=True)

    leaf_layers = [name for name in ("geometries.usd", "instances.usda", "materials.usda") if name != omit]
    for layer_name in leaf_layers:
        layer = Usd.Stage.CreateNew(str(root / "payloads" / layer_name))
        _define_default_prim(layer)
        layer.Save()

    base = Usd.Stage.CreateNew(str(root / "payloads" / "base.usda"))
    base_prim = _define_default_prim(base)
    for layer_name in leaf_layers:
        base_prim.GetReferences().AddReference(f"./{layer_name}", Sdf.Path("/MyAsset"))
    base.Save()

    main_path = root / "robot.usda"
    main = Usd.Stage.CreateNew(str(main_path))
    default_prim = _define_default_prim(main)
    Usd.ModelAPI(default_prim).SetKind(Kind.Tokens.component)
    default_prim.GetReferences().AddReference("./payloads/base.usda")
    main.Save()

    return main_path


def test_robot_payload_layout_passes(checker_class, tmp_path):
    """The robot layout is the other structure ISA.001 accepts."""
    stage = Usd.Stage.Open(str(build_robot_asset(tmp_path / "robot")))
    assert isa_001_failures(checker_class, stage) == []


def test_partial_robot_layout_fails(checker_class, tmp_path):
    """A layout that only partly matches is reported against the closest layout."""
    stage = Usd.Stage.Open(str(build_robot_asset(tmp_path / "partial", omit="materials.usda")))

    failures = isa_001_failures(checker_class, stage)
    assert failures
    assert any("robot" in message and "materials" in message for message in failures)


def test_missing_component_kind_fails(checker_class, tmp_path):
    """Default prim kind is still enforced alongside the payload structure."""
    main_path = build_isaac_asset(tmp_path / "nokind")
    stage = Usd.Stage.Open(str(main_path))
    Usd.ModelAPI(stage.GetDefaultPrim()).SetKind(Kind.Tokens.assembly)

    failures = isa_001_failures(checker_class, stage)
    assert any("component" in message for message in failures)


def test_visible_meshes_scope_fails(checker_class, tmp_path):
    """A visible Meshes/Visuals scope is still reported."""
    main_path = build_isaac_asset(tmp_path / "visible", meshes_visible=True)
    stage = Usd.Stage.Open(str(main_path))

    failures = isa_001_failures(checker_class, stage)
    assert any("invisible" in message for message in failures)


@pytest.mark.skipif(not SAMPLE_PROP.exists(), reason="sample_content not fetched (Git LFS)")
def test_sample_content_prop_passes(checker_class):
    """The repository's own Isaac-composed sample prop must pass ISA.001.

    This asset uses ``payloads/obs_workbench_tool_01_{base,meshes,physics}.usd``:
    note the payload stem does not match the main asset file name, which is why
    the layers are matched by role suffix rather than by exact file name.
    """
    stage = Usd.Stage.Open(str(SAMPLE_PROP))
    assert isa_001_failures(checker_class, stage) == []
