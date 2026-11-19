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
"""Reading which surfaces a material declares.

A SimReady material can put three surface outputs on one ``Material`` prim:

=========================  ==========================
``outputs:surface``        UsdPreviewSurface
``outputs:mdl:surface``    OmniPBR (MDL)
``outputs:mtlx:surface``   OpenPBR (MaterialX)
=========================  ==========================

This module only inspects. Which of them Kit evaluates is decided in
``_context``, by writing the render-context list rather than by editing the
material. Nothing here writes to the stage.

WHAT THIS IS AND IS NOT FOR
---------------------------
Reporting, the diagnosis attached to a failure, and one decision. The coverage
verdict comes from the probe renders, because a material declaring a surface
establishes nothing about whether that surface reached a pixel. The inventory
(``describe_surfaces``) is what makes a failure legible -- "the asset declares a
surface on mdl and universal" is the first thing a reader wants when coverage
came back short. ``declared_contexts`` decides whether an optional-context
coverage test runs at all: where no material a final render resolves declares a
surface for the context, Kit would render the universal surfaces in its place.

An earlier version of these tests resolved bindings down to the ``GeomSubset``
and attributed pixels to each one, so that a mesh partitioned between two
contexts was credited only with the faces each context shades. That machinery
is gone with the measurement it fed. The comparison is now over the whole
silhouette, and a partitioned mesh contributes to it wherever the surface under
test changes it.
"""

from pxr import Usd, UsdGeom, UsdShade

# Render context tokens, as used by UsdShadeMaterial.GetSurfaceOutput().
# "" is the universal context, which is where UsdPreviewSurface lives.
UNIVERSAL = ""
MDL = "mdl"
MTLX = "mtlx"
SURFACE_CONTEXTS = (UNIVERSAL, MDL, MTLX)

# Human-readable names, for messages and metrics.
CONTEXT_LABELS = {
    UNIVERSAL: "universal (UsdPreviewSurface)",
    MDL: "mdl (OmniPBR)",
    MTLX: "mtlx (OpenPBR)",
}


def label_for(context):
    """A readable name for a render context token."""
    return CONTEXT_LABELS.get(context, context or "universal")


def surface_output(material_prim, context):
    """The connected surface output for a context, or None."""
    material = UsdShade.Material(material_prim)
    output = material.GetSurfaceOutput(context) if context else material.GetSurfaceOutput()
    if output and output.HasConnectedSource():
        return output
    return None


def connected_contexts(material_prim):
    """The render contexts this material actually declares a surface for."""
    return [c for c in SURFACE_CONTEXTS if surface_output(material_prim, c) is not None]


def renderable_geometry(stage, root=None):
    """Every Gprim under ``root`` a renderer would actually draw.

    Filters on purpose and on resolved visibility. Purpose alone is not enough:
    a Gprim authored ``visibility="invisible"``, or sitting under an invisible
    ancestor, is not drawn, so counting it as renderable makes a test assert
    about geometry no frame contains.
    """
    start = stage.GetPrimAtPath(root) if root else None
    if start is None or not start.IsValid():
        start = stage.GetPseudoRoot()
    for prim in Usd.PrimRange(start, Usd.TraverseInstanceProxies()):
        if not UsdGeom.Gprim(prim):
            continue
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            continue
        if imageable.ComputePurpose() not in (
            UsdGeom.Tokens.default_,
            UsdGeom.Tokens.render,
        ):
            continue
        if imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
            continue
        yield prim


def bound_materials(stage, root=None):
    """Every distinct material actually bound to renderable geometry under ``root``.

    The materials in a /Looks scope are not the question: a surface on a
    material nothing binds never reaches a pixel. This resolves the computed
    binding for each Gprim a renderer would draw, so the set is what the frame
    is actually made of.

    A mesh's GeomSubsets are resolved too. Per-face-set binding is how a single
    mesh gets more than one material, and it is common in converted content:
    ``obs_workbench_tool_a01`` binds ``opaque__metal__blackshell`` on a subset
    only, and every material on ``ur10`` is bound that way with nothing on the
    meshes at all. Asking the Gprim alone reports that asset as having no
    materials.
    """
    seen, materials = set(), []

    def take(prim):
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        if not material:
            return
        path = material.GetPrim().GetPath()
        if path in seen:
            return
        seen.add(path)
        materials.append(material.GetPrim())

    for prim in renderable_geometry(stage, root):
        take(prim)
        for subset in UsdGeom.Subset.GetAllGeomSubsets(UsdGeom.Imageable(prim)):
            take(subset.GetPrim())
    return materials


def full_bound_materials(stage, root=None):
    """Every distinct material a final render resolves on renderable geometry under ``root``.

    Resolved at the ``full`` purpose, as the static gates resolve it (``VM.MAT.001``,
    ``VM.PS.002``, ``VM.MDL.003``, ``VM.PBR.001``). That purpose falls back to the
    all-purpose binding, so a material bound only through ``material:binding:full``
    counts, and one bound only through ``material:binding:preview`` does not.

    Each Gprim's ``materialBind`` subsets are resolved as well as the Gprim itself:
    faces outside every subset render with the Gprim's material. Materials are kept
    by path, so two that share a name in different scopes stay apart.
    """
    seen, materials = set(), []

    def take(prim):
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)
        if not material:
            return
        path = material.GetPrim().GetPath()
        if path in seen:
            return
        seen.add(path)
        materials.append(material.GetPrim())

    for prim in renderable_geometry(stage, root):
        take(prim)
        for subset in UsdShade.MaterialBindingAPI(prim).GetMaterialBindSubsets():
            take(subset.GetPrim())
    return materials


def published_materials(stage, root=None):
    """Every ``Material`` under ``root``, for an asset with no geometry of its own.

    A material asset publishes its materials for other assets to bind, so nothing
    under ``root`` resolves them and ``bound_materials`` finds none. The tests bind
    each of these to a test sphere instead (``_scene.add_test_spheres``). A
    material's own network is not searched for further materials.
    """
    start = stage.GetPrimAtPath(root) if root else None
    if start is None or not start.IsValid():
        start = stage.GetPseudoRoot()
    materials = []
    prims = iter(Usd.PrimRange(start, Usd.TraverseInstanceProxies()))
    for prim in prims:
        if prim.IsA(UsdShade.Material):
            materials.append(prim)
            prims.PruneChildren()
    return materials


def declared_contexts(stage, root=None):
    """The render contexts at least one material in ``full_bound_materials`` has a surface for."""
    return {context for prim in full_bound_materials(stage, root) for context in connected_contexts(prim)}


def describe_surfaces(stage, root=None):
    """Per-material context inventory of what the frame is made of.

    Bound materials rather than every Material under ``root``: a surface on a
    material nothing binds never reaches a pixel, and reporting it would tell a
    reader whose coverage came up short that the surface is there when no pixel
    resolves it.
    """
    return {prim.GetPath().name: connected_contexts(prim) for prim in bound_materials(stage, root)}
