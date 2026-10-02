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

"""What the FET006 surface tests decide, and what they decide it from.

Four things are worth pinning without a renderer: the probe material resolves
under every pin the family uses, a pin is only accepted when carb holds the
whole list, the comparison gate separates the runs measured on the rig, and so
does the default-material gate the universal context uses instead of it.

The two gates are different shapes because the contexts are. MDL and MaterialX
fall back to the universal context, so a missing surface produces the same
picture twice and has to be found by comparison. The universal context has
nothing beneath it, so a missing surface produces Kit's default material and
can be found in one frame.
"""

import pytest

pytest.importorskip("pxr")

from pxr import Usd, UsdShade  # noqa: E402

from simready_benchmark_kit_suite.fet006_materials import (  # noqa: E402
    _scene,
    _surface_test,
    preview_surface_renders,
    surfaces,
)

# Measured on Isaac Sim 6.0, inside the asset silhouette, under [""]: the share
# of the silhouette that is red-dominant, which is what Kit's default material
# renders as. Only the universal context is measured this way.
DEFAULT_MATERIAL_CONFORMANT = {
    "toaster, all three contexts": 0.00012,
    "toaster, UsdPreviewSurface alone": 0.00012,
    "workbench tool": 0.01840,
    # A red ball on a grey base, with its UsdPreviewSurface resolving
    # correctly. This is what stops the threshold being set anywhere near zero.
    "joystick": 0.28617,
}
DEFAULT_MATERIAL_NEGATIVE = {
    "toaster, outputs:surface stripped from every material": 0.99719,
}

# Measured on Isaac Sim 6.0, inside the asset silhouette, the context under
# test against its comparison. (changed fraction, mean-RGB delta).
POSITIVES = {
    "toaster, mtlx against universal": (0.150, 0.0534),
    "workbench tool, mtlx against universal": (0.278, 0.0333),
    "joystick, mtlx against universal": (0.219, 0.0686),
    # The delta collapses when the two surfaces share a mean colour, which mdl
    # against universal often does: a UsdPreviewSurface is usually baked down
    # from the MDL surface it stands in for. The fraction is what carries these.
    "toaster, mdl against universal": (0.092, 0.0045),
    "joystick, mdl against universal": (0.168, 0.0052),
    "workbench tool, mdl against universal": (0.277, 0.0325),
}
NEGATIVES = {
    "toaster with outputs:mtlx:surface stripped": (0.012, 0.0004),
    "toaster stripped to MDL alone": (0.013, 0.0004),
    # Two renders that should have been identical: same pin, same scene, and
    # the same pin run in a separate Kit process. The worst of each, which came
    # from the smallest sample.
    "same-pin repeat of the joystick": (0.042, 0.0011),
    "separate-process repeat of the joystick": (0.024, 0.0011),
}


def test_the_probe_resolves_under_every_pin_the_family_uses():
    """The silhouette is cut in both passes and the passes pin different lists.
    A probe carrying one surface would resolve under some and fall to Kit's
    default material under the rest, and the two silhouettes could not be
    intersected."""
    stage = Usd.Stage.CreateInMemory()
    material = _surface_test.build_probe(stage)

    for context in surfaces.SURFACE_CONTEXTS:
        assert surfaces.surface_output(material.GetPrim(), context) is not None, context


def test_the_probe_binds_stronger_than_anything_the_asset_authors():
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Asset", "Xform")
    stage.DefinePrim("/Asset/Geo/panel", "Mesh")

    assert _surface_test.paint(stage, "/Asset") is True
    api = UsdShade.MaterialBindingAPI(root)
    assert api.GetMaterialBindingStrength(api.GetDirectBindingRel()) == \
        UsdShade.Tokens.strongerThanDescendants

    panel = stage.GetPrimAtPath("/Asset/Geo/panel")
    bound, _rel = UsdShade.MaterialBindingAPI(panel).ComputeBoundMaterial(
        materialPurpose=UsdShade.Tokens.full
    )
    assert bound.GetPath().pathString.startswith(_surface_test.PROBE_SCOPE)

    _surface_test.clear(stage, "/Asset")
    bound, _rel = UsdShade.MaterialBindingAPI(panel).ComputeBoundMaterial(
        materialPurpose=UsdShade.Tokens.full
    )
    assert not bound


def test_a_pin_is_only_accepted_when_carb_holds_the_whole_list():
    """The fallback entries are as load-bearing as the first one. A list that
    was meant to be pinned to one context and came back with the shipped three
    behind it would measure whichever surface Kit reached first."""
    assert _surface_test.pin_took(["mtlx"], ["mtlx"]) is True
    assert _surface_test.pin_took([""], [""]) is True
    assert _surface_test.pin_took(["", "mtlx"], [""]) is False
    assert _surface_test.pin_took(["mdl", "mtlx", ""], ["mtlx"]) is False
    assert _surface_test.pin_took(None, ["mtlx"]) is False


def test_the_config_drops_what_the_comparison_needed():
    """The two comparison gates and the silhouette-agreement floor have no
    meaning for a coverage measurement, and leaving them inert would read as
    though the test still consulted them."""
    config = preview_surface_renders.CONFIG

    for key in ("min_mean_rgb_delta", "min_changed_fraction",
                "min_silhouette_agreement", "pixel_change_threshold"):
        assert key not in config, key
    # Still needed: the silhouette is cut the same way in both shapes.
    for key in ("mask_dominance_ratio", "mask_dominance_floor",
                "min_silhouette_pixels"):
        assert key in config, key



def test_the_strict_query_is_what_makes_one_render_enough():
    """The load-bearing fact of the single-render design.

    ``GetSurfaceOutput(context)`` returns an invalid output when that context
    has no surface. ``ComputeSurfaceSource`` is documented to check the
    universal output instead, so it answers a different question and cannot be
    used to establish presence: on a material carrying only a preview surface
    it hands back the UsdPreviewSurface when asked for mdl.

    If USD ever made the strict accessor fall back, every surface test would
    silently start passing assets that do not carry the surface under test, so
    this is asserted rather than assumed.
    """
    from pxr import Sdf, Usd, UsdShade

    from simready_benchmark_kit_suite.fet006_materials import surfaces

    stage = Usd.Stage.CreateInMemory()
    material = UsdShade.Material.Define(stage, "/M")
    shader = UsdShade.Shader.Define(stage, "/M/Preview")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    prim = material.GetPrim()

    # Strict: present for universal, absent for the two it does not carry.
    assert surfaces.surface_output(prim, surfaces.UNIVERSAL) is not None
    assert surfaces.surface_output(prim, surfaces.MDL) is None
    assert surfaces.surface_output(prim, surfaces.MTLX) is None

    # Falls back, which is why presence is not asked this way.
    fell_back, _, _ = material.ComputeSurfaceSource(surfaces.MDL)
    assert UsdShade.Shader(fell_back).GetShaderId() == "UsdPreviewSurface"


def test_an_unbound_material_is_not_counted_as_present():
    """A surface on a material nothing binds never reaches a pixel, so the
    presence half resolves bindings rather than reading /Looks."""
    from pxr import Sdf, Usd, UsdGeom, UsdShade

    from simready_benchmark_kit_suite.fet006_materials import surfaces

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    sphere = UsdGeom.Sphere.Define(stage, "/World/Sphere")

    unbound = UsdShade.Material.Define(stage, "/Looks/Unbound")
    shader = UsdShade.Shader.Define(stage, "/Looks/Unbound/S")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    unbound.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    assert surfaces.bound_materials(stage, "/World") == []

    UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim())
    UsdShade.MaterialBindingAPI(sphere.GetPrim()).Bind(unbound)
    bound = surfaces.bound_materials(stage, "/World")
    assert [p.GetPath().pathString for p in bound] == ["/Looks/Unbound"]


def test_a_material_bound_on_a_geom_subset_is_counted():
    """Per-face-set binding is how one mesh gets more than one material, and
    converted content leans on it: every material on ``ur10`` is bound that way
    with nothing on the meshes at all. Asking the Gprim alone reports such an
    asset as having no materials."""
    from pxr import Sdf, Usd, UsdGeom, UsdShade

    from simready_benchmark_kit_suite.fet006_materials import surfaces

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    mesh = UsdGeom.Mesh.Define(stage, "/World/Mesh")

    material = UsdShade.Material.Define(stage, "/Looks/PerFace")
    shader = UsdShade.Shader.Define(stage, "/Looks/PerFace/S")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    assert surfaces.bound_materials(stage, "/World") == []

    subset = UsdGeom.Subset.CreateGeomSubset(mesh, "faceset", UsdGeom.Tokens.face, [0])
    UsdShade.MaterialBindingAPI.Apply(subset.GetPrim())
    UsdShade.MaterialBindingAPI(subset.GetPrim()).Bind(material)

    bound = surfaces.bound_materials(stage, "/World")
    assert [p.GetPath().pathString for p in bound] == ["/Looks/PerFace"]

def _coverage(silhouette, uncovered):
    """The arithmetic the body does, kept in step with it."""
    return max(0.0, 1.0 - (uncovered / float(silhouette)))


def _covered_enough(silhouette, uncovered, config=None):
    config = config or preview_surface_renders.CONFIG
    return _coverage(silhouette, uncovered) >= float(config["min_material_coverage"])


def test_coverage_is_the_share_of_the_silhouette_the_asset_shades():
    """Both numbers are counted the same way in two frames that differ only in
    the strength of one binding, so the arithmetic is a ratio and nothing else."""
    assert _coverage(1000, 0) == 1.0          # every pixel is the asset's own material
    assert _coverage(1000, 1000) == 0.0       # the control shows everywhere; nothing bound
    assert _coverage(1000, 250) == 0.75


def test_coverage_is_clamped_at_zero():
    """The two passes frame on separate stages, so an asset that binds nothing
    anywhere can report marginally more uncovered pixels than the silhouette it
    is divided by. Measured on TEST/minimal.usd, three Gprims with no material
    bound anywhere: 406,675 uncovered against a 406,604 pixel silhouette."""
    assert _coverage(406604, 406675) == 0.0


def test_the_coverage_gate_rejects_a_largely_unshaded_asset():
    """The floor is 0.98. Measured on Isaac Sim 6.0.1 across all three surface
    tests, the 19 sample assets with geometry to measure came back at 1.0 with
    no uncovered pixel at all, two equal cubes with one of them unbound came
    back between 0.424 and 0.432, and an asset binding nothing anywhere came
    back at 0."""
    assert _covered_enough(1000, 0)
    assert _covered_enough(1000, 20)          # 98%, exactly the floor
    assert not _covered_enough(1000, 21)      # just under it
    assert not _covered_enough(338019, 191995)  # the two-cube fixture, 0.432


def test_no_gate_depends_on_a_colour_the_renderer_chose():
    """Why the red-dominance gate was dropped rather than retuned.

    The joystick is a shipping sample whose UsdPreviewSurface resolves
    correctly, and 28.6% of its silhouette measured red-dominant on the rig --
    because the asset is a red ball. Any gate keyed on Kit's default material
    being red has to sit above that, which is most of an asset. The same defect
    applies one colour over to the neutral grey Kit paints for a material with
    no surface outputs, and grey is commoner in content than red.

    The control's magenta is authored by the suite instead, so nothing in the
    gate is a colour the renderer picked. That is also what lets a non-Kit
    runtime mimic these tests.
    """
    assert "max_default_material_fraction" not in preview_surface_renders.CONFIG
    assert "min_material_coverage" in preview_surface_renders.CONFIG
    assert _surface_test.MAGENTA_CHANNELS == (0, 2)
    assert not hasattr(_surface_test, "RED_CHANNELS")
    assert not hasattr(_surface_test, "DEFAULT_MATERIAL_RGB")


def test_the_materialx_log_names_only_the_asset_and_only_failures():
    """Coverage cannot see a material that is bound and does not evaluate, so
    the MaterialX validation log is what reports it. The control this family
    binds is itself an OpenPBR network and the room has its own material, so a
    failure in either is a fault in the rig rather than in the content and is
    scoped out by prim path."""
    from simready_benchmark_kit_suite.fet006_materials import _logs

    entries = [
        {"level": "error", "channel": "rtx.materialx.plugin",
         "message": "Unable to create document for material: "
                    "'/World/AssetRoot/Asset/Looks/Chrome'"},
        {"level": "error", "channel": "rtx.materialx.plugin",
         "message": "Unable to create document for material: "
                    "'/SimReadySurfaceProbe/Flat'"},
        {"level": "warning", "channel": "rtx.materialx.plugin",
         "message": "Unable to create document for material: "
                    "'/World/AssetRoot/Asset/Looks/OnlyAWarning'"},
        {"level": "error", "channel": "omni.usd",
         "message": "Unable to create document for material: "
                    "'/World/AssetRoot/Asset/Looks/WrongChannel'"},
        {"level": "error", "channel": "rtx.materialx.plugin",
         "message": "Something else entirely"},
    ]
    found = _logs.unresolved_materials("/World/AssetRoot/Asset", entries=entries)
    assert found == ["/World/AssetRoot/Asset/Looks/Chrome"]

    unscoped = _logs.unresolved_materials(None, entries=entries)
    assert unscoped == ["/World/AssetRoot/Asset/Looks/Chrome",
                        "/SimReadySurfaceProbe/Flat"]


def test_a_prefix_match_does_not_pull_in_a_sibling_asset():
    """`/World/AssetRoot/Asset2` is not under `/World/AssetRoot/Asset`."""
    from simready_benchmark_kit_suite.fet006_materials import _logs

    entries = [{"level": "error", "channel": "rtx.materialx.plugin",
                "message": "Unable to create document for material: "
                           "'/World/AssetRoot/Asset2/Looks/Chrome'"}]
    assert _logs.unresolved_materials("/World/AssetRoot/Asset", entries=entries) == []


def test_only_openpbr_reads_the_materialx_log():
    """MaterialX is the one context Kit reports evaluation for; MDL and
    UsdPreviewSurface have no equivalent switch, so a check there would report
    a clean result it never established."""
    import inspect

    from simready_benchmark_kit_suite.fet006_materials import (
        mdl_renders, openpbr_renders, preview_surface_renders)

    assert "read_materialx_log=True" in inspect.getsource(openpbr_renders)
    assert "read_materialx_log" not in inspect.getsource(mdl_renders)
    assert "read_materialx_log" not in inspect.getsource(preview_surface_renders)
