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

"""VM.PS.002, VM.MDL.003 and VM.PBR.001: the surface a feature is named for is there.

A conformance requirement that inspects a surface only when it finds one is silent
on an asset that has none, so a feature built from those alone passes an asset that
does not have the thing the feature is named for. A consumer searching validation
metadata for the assets it can render cannot use such a feature to find them.

Requires an installed ``simready-foundation-tier-core`` wheel (with generated
requirements) plus ``usd-validation-nvidia`` and ``pxr``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("usd_validation_nvidia")
pytest.importorskip("pxr")
pytest.importorskip("simready.foundation.tier_core.requirements")

from pxr import Sdf, Usd, UsdGeom, UsdShade  # noqa: E402

from simready.foundation.tier_core.capabilities.visualization.materials import (  # noqa: E402
    validation as materials,
)

MATERIAL_PATH = "/World/Looks/Surface"
MESH_PATH = "/World/Geometry/Mesh"


def _stage(terminals: tuple[str, ...], *, bind: bool = True) -> Usd.Stage:
    """One renderable GPrim bound to a material connecting ``terminals``."""
    stage = Usd.Stage.CreateInMemory()
    mesh = UsdGeom.Mesh.Define(stage, MESH_PATH)
    material = UsdShade.Material.Define(stage, MATERIAL_PATH)

    for terminal in terminals:
        name = {"outputs:surface": "Preview",
                "outputs:mdl:surface": "Mdl",
                "outputs:mtlx:surface": "Mtlx"}[terminal]
        shader = UsdShade.Shader.Define(stage, f"{MATERIAL_PATH}/{name}")
        shader.CreateIdAttr({"Preview": "UsdPreviewSurface",
                             "Mdl": "mdl:OmniPBR",
                             "Mtlx": "ND_open_pbr_surface_surfaceshader"}[name])
        shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
        context = "" if terminal == "outputs:surface" else terminal.split(":")[1]
        output = (material.CreateSurfaceOutput(context) if context
                  else material.CreateSurfaceOutput())
        output.ConnectToSource(shader.ConnectableAPI(), "out")

    if bind:
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim())
        UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(material)
    return stage


def _issues(stage: Usd.Stage, code):
    checker = materials.VisualMaterialsCapabilityChecker()
    checker.CheckStage(stage)
    for prim in stage.Traverse():
        checker.CheckPrim(prim)
    return [i for i in checker.GetIssues() if i.requirement == code]


def _code(name):
    import simready.foundation.tier_core.requirements as cap
    return getattr(cap.MaterialsRequirements, name)


@pytest.mark.parametrize(
    "requirement,terminal",
    [("VM_PS_002", "outputs:surface"),
     ("VM_MDL_003", "outputs:mdl:surface"),
     ("VM_PBR_001", "outputs:mtlx:surface")],
)
def test_a_material_without_the_surface_fails(requirement, terminal):
    """The point of each requirement: a pass means the asset has that surface."""
    others = tuple(t for t in ("outputs:surface", "outputs:mdl:surface", "outputs:mtlx:surface")
                   if t != terminal)
    assert _issues(_stage(others), _code(requirement)), (
        f"a material connecting {others} and not {terminal} must fail {requirement}"
    )


@pytest.mark.parametrize(
    "requirement,terminal",
    [("VM_PS_002", "outputs:surface"),
     ("VM_MDL_003", "outputs:mdl:surface"),
     ("VM_PBR_001", "outputs:mtlx:surface")],
)
def test_a_material_with_the_surface_passes(requirement, terminal):
    assert not _issues(_stage((terminal,)), _code(requirement))


def test_an_mdl_surface_does_not_satisfy_openpbr():
    """The migration allowance VM.PBR.001 used to make.

    While `outputs:mdl:surface` counted as a physically based final surface, an
    MDL-only asset passed FET_006_OPENPBR with no OpenPBR in it, so the feature
    could not answer whether an asset has OpenPBR.
    """
    stage = _stage(("outputs:surface", "outputs:mdl:surface"))
    assert _issues(stage, _code("VM_PBR_001")), (
        "an MDL surface must not satisfy VM.PBR.001"
    )
    assert "outputs:mtlx:surface" in str(_issues(stage, _code("VM_PBR_001"))[0].message)


@pytest.mark.parametrize("requirement", ["VM_PS_002", "VM_MDL_003"])
def test_geometry_that_resolves_no_material_is_vm_mat_001s_to_report(requirement):
    """One defect, one finding. A GPrim with no material at all is reported by
    VM.MAT.001; repeating it here would report the same prim under two codes."""
    assert not _issues(_stage((), bind=False), _code(requirement))


@pytest.mark.parametrize("requirement", ["VM_PS_002", "VM_MDL_003"])
def test_a_material_nothing_binds_is_outside_the_question(requirement):
    """Driven from the geometry: an unused entry in /Looks renders nothing, so it
    is not asked for a surface."""
    assert not _issues(_stage(("outputs:mtlx:surface",), bind=False), _code(requirement))


def _material_only_stage(terminals: tuple[str, ...]) -> Usd.Stage:
    """A library asset: Material prims and no geometry to bind them to."""
    stage = Usd.Stage.CreateInMemory()
    material = UsdShade.Material.Define(stage, MATERIAL_PATH)
    for terminal in terminals:
        name = {"outputs:surface": "Preview",
                "outputs:mdl:surface": "Mdl",
                "outputs:mtlx:surface": "Mtlx"}[terminal]
        shader = UsdShade.Shader.Define(stage, f"{MATERIAL_PATH}/{name}")
        shader.CreateIdAttr({"Preview": "UsdPreviewSurface",
                             "Mdl": "mdl:OmniPBR",
                             "Mtlx": "ND_open_pbr_surface_surfaceshader"}[name])
        shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
        context = "" if terminal == "outputs:surface" else terminal.split(":")[1]
        output = (material.CreateSurfaceOutput(context) if context
                  else material.CreateSurfaceOutput())
        output.ConnectToSource(shader.ConnectableAPI(), "out")
    return stage


@pytest.mark.parametrize(
    "requirement,terminal",
    [("VM_PS_002", "outputs:surface"),
     ("VM_MDL_003", "outputs:mdl:surface"),
     ("VM_PBR_001", "outputs:mtlx:surface")],
)
def test_a_material_only_asset_is_judged_on_its_materials(requirement, terminal):
    """A material library declares materials and no geometry. A requirement written
    only against bound materials reports nothing about it, so the feature would state
    nothing a consumer can act on."""
    others = tuple(t for t in ("outputs:surface", "outputs:mdl:surface", "outputs:mtlx:surface")
                   if t != terminal)
    assert _issues(_material_only_stage(others), _code(requirement)), (
        f"a material-only asset with no {terminal} must fail {requirement}"
    )
    assert not _issues(_material_only_stage((terminal,)), _code(requirement))


def test_one_material_with_the_surface_is_enough_without_geometry():
    """An asset with no geometry cannot say which of its materials a consumer will
    use, so the stage-level branch asks for one rather than all."""
    stage = _material_only_stage(("outputs:surface",))
    bare = UsdShade.Material.Define(stage, "/World/Looks/NoSurface")
    assert bare
    assert not _issues(stage, _code("VM_PS_002"))


def test_proxy_only_geometry_is_read_as_having_no_renderable_geometry():
    """Proxy geometry is not drawn in a final render, so an asset whose only meshes
    are proxies is judged on its materials rather than on those bindings."""
    stage = _material_only_stage(("outputs:mtlx:surface",))
    proxy = UsdGeom.Mesh.Define(stage, "/World/Geometry/Proxy")
    UsdGeom.Imageable(proxy).CreatePurposeAttr(UsdGeom.Tokens.proxy)
    assert _issues(stage, _code("VM_PS_002")), (
        "the stage-level branch must still run when the only geometry is proxy purpose"
    )


def test_geometry_present_means_the_per_prim_rule_decides():
    """With renderable geometry the stage-level branch does not run, so an unused
    material with the surface cannot speak for a bound material without it."""
    stage = _stage(("outputs:mdl:surface",))
    unused = UsdShade.Material.Define(stage, "/World/Looks/UnusedButOpenPBR")
    shader = UsdShade.Shader.Define(stage, "/World/Looks/UnusedButOpenPBR/Mtlx")
    shader.CreateIdAttr("ND_open_pbr_surface_surfaceshader")
    shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
    unused.CreateSurfaceOutput("mtlx").ConnectToSource(shader.ConnectableAPI(), "out")

    assert _issues(stage, _code("VM_PBR_001")), (
        "an unused OpenPBR material must not rescue a bound material that has none"
    )
