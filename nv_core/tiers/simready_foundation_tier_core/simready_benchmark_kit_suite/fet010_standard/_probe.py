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
"""The probe materials the display colour benchmark swaps at the asset root.

Nothing here authors on the asset. The materials are defined on a scope of
their own, outside the asset root, and reach the geometry through a single
binding on the asset's root prim carrying
``bindMaterialAs = "strongerThanDescendants"``.

WHY A ROOT BINDING RATHER THAN EDITING THE ASSET
------------------------------------------------
UsdShade resolves a binding by walking up namespace, and a
``strongerThanDescendants`` binding wins over everything below it. Measured on
a stage carrying, all at once, a plain binding inside a prototype, a
``strongerThanDescendants`` binding inside that prototype, a ``GeomSubset``
binding, a collection binding on an intermediate ``Scope``, a
``strongerThanDescendants`` binding on an intermediate ``Xform``, and an
instance nested inside another prototype: one root binding took all ten
resolved prims. Nothing had to be de-instanced and no prim inside a prototype
was written to.

That matters beyond tidiness. The previous design made every instance under the
asset non-instanceable so it could author a primvar on the geometry, and on
assets with nested instancing -- ur10, Robotiq 2F-85 --
``SetInstanceable(False)`` raised part-way through. An instance proxy cannot be
authored on; the asset's own root prim never is one, because instance proxies
are by definition descendants of an instance, so a binding there is always
legal.

WHICH MATERIAL
--------------
The one DISP.001's Guidance nominates: an OpenPBR surface driven by MaterialX
primvar readers, ``ND_geompropvalue_color3`` on ``displayColor`` into
``base_color`` and ``ND_geompropvalue_float`` on ``displayOpacity`` into
``geometry_opacity``. Using it means the benchmark measures the material the
specification asks authors to produce rather than the internals of whichever
fallback a renderer happens to ship.

It also reaches ``displayOpacity``, which the previous design could not. That
design fell through to ``kit/mdl/rtx/Default.mdl``, which declares a surface
and no opacity term, so DISP.003 was out of reach by construction.

THE FALLBACK COLOUR IS THE MEASUREMENT
--------------------------------------
``ND_geompropvalue_color3`` returns ``inputs:default`` for geometry where the
named primvar does not resolve. DISP.001's Guidance suggests a plausible grey
there, which is right for an asset shipping the material. It is wrong for a
probe: a plausible grey is indistinguishable from a display colour that
resolved.

So the fallback is magenta, and the ``Removed`` material paints that same
magenta as a flat constant with no reader behind it. Geometry that resolves a
display colour renders its own colour under ``Read`` and magenta under
``Removed``, so it differs. Geometry that resolves none renders magenta under
both, so it does not. One comparison therefore answers both of the questions
this benchmark asks: which geometry reached the shader with a colour of its
own, and whether a primvar rather than a constant is what drove the pixels.

The probe used to carry a second reader differing only in a green fallback, and
coverage was measured as ``Read`` against that. ``Read`` against ``Removed``
subsumes it -- the same geometry moves in both -- and establishes causality at
the same time, so the green reader is gone.

What that costs is the one case the green reader could tell apart: geometry
whose authored display colour is itself the probe's magenta renders identically
under ``Read`` and ``Removed`` and is counted as unresponsive. That is a false
failure rather than a false pass, and the failure message names the constant.

``ND_geompropvalue_float`` defaults to ``0.0``, which is fully transparent, so
the opacity reader must set ``inputs:default = 1.0`` or an asset that omits
``displayOpacity`` -- which DISP.003 permits and calls the common case --
vanishes. That default is itself worth proving, which is what the opacity probe
material is for: it is the read material with the opacity fallback dropped to
``0.0``, so geometry relying on the default disappears and geometry authoring
its own opacity does not.

WHAT IS NOT SET
---------------
Everything else on the surface is left at the nodedef default, including
``specular_weight`` and ``specular_roughness``. Turning specular off would give
cleaner masks, and it would also mean the benchmark no longer renders the
material DISP.001 nominates. The masks are cut by chroma dominance with a
brightness floor instead, which tolerates a specular sheen; see
``_pixels.dominant_mask``.
"""

from pxr import Sdf, UsdGeom, UsdShade

# Outside the asset root on purpose. Prims added under the asset would show up
# in every traversal the rest of this suite scopes to it, and the asset's root
# prim may compose an instanceable opinion from the layer it references, which
# makes its children unauthorable.
PROBE_SCOPE = "/SimReadyDisplayColorProbe"

SURFACE_ID = "ND_open_pbr_surface_surfaceshader"
COLOR_READER_ID = "ND_geompropvalue_color3"
FLOAT_READER_ID = "ND_geompropvalue_float"

DISPLAY_COLOR = "displayColor"
DISPLAY_OPACITY = "displayOpacity"

# The colour a Gprim renders when it resolves no displayColor, and the constant
# the Removed material paints. One colour, used for both, so that geometry
# resolving nothing is identical between the two frames and geometry resolving
# something is not. Saturated, and far from anything an asset is likely to ship
# on every prim.
FALLBACK_COLOR = (1.0, 0.0, 1.0)

OPAQUE = 1.0
TRANSPARENT = 0.0

# Material names, and the frame labels that go with them.
READ = "Read"
READ_CONTROL = "ReadControl"
REMOVED = "Removed"
OPACITY = "Opacity"

DESCRIPTIONS = {
    READ: "displayColor -> base_color, missing values fall back to magenta",
    READ_CONTROL: "byte-for-byte what Read is, on a second prim",
    REMOVED: "no reader; base_color is a flat magenta constant",
    OPACITY: "as Read, with the displayOpacity fallback dropped to 0.0",
}


def _color_reader(stage, path, fallback):
    """A ``ND_geompropvalue_color3`` reading ``displayColor``."""
    shader = UsdShade.Shader.Define(stage, path)
    shader.CreateIdAttr(COLOR_READER_ID)
    shader.CreateInput("geomprop", Sdf.ValueTypeNames.String).Set(DISPLAY_COLOR)
    shader.CreateInput("default", Sdf.ValueTypeNames.Color3f).Set(fallback)
    return shader.CreateOutput("out", Sdf.ValueTypeNames.Color3f)


def _opacity_reader(stage, path, fallback):
    """A ``ND_geompropvalue_float`` reading ``displayOpacity``."""
    shader = UsdShade.Shader.Define(stage, path)
    shader.CreateIdAttr(FLOAT_READER_ID)
    shader.CreateInput("geomprop", Sdf.ValueTypeNames.String).Set(DISPLAY_OPACITY)
    shader.CreateInput("default", Sdf.ValueTypeNames.Float).Set(float(fallback))
    return shader.CreateOutput("out", Sdf.ValueTypeNames.Float)


def _material(stage, name, color_fallback, opacity_fallback, flat_color=None):
    """One probe material.

    ``flat_color`` replaces the colour reader with a constant, which is what
    makes the removed frame a render of the same surface with the primvar taken
    out of it rather than a render of some other material.
    """
    path = "%s/%s" % (PROBE_SCOPE, name)
    material = UsdShade.Material.Define(stage, path)

    surface = UsdShade.Shader.Define(stage, path + "/Surface")
    surface.CreateIdAttr(SURFACE_ID)

    base_color = surface.CreateInput("base_color", Sdf.ValueTypeNames.Color3f)
    if flat_color is None:
        base_color.ConnectToSource(_color_reader(stage, path + "/ColorReader", color_fallback))
    else:
        base_color.Set(flat_color)

    surface.CreateInput("geometry_opacity", Sdf.ValueTypeNames.Float).ConnectToSource(
        _opacity_reader(stage, path + "/OpacityReader", opacity_fallback)
    )

    # The nodedef declares one output named "out". DISP.001's Guidance connects
    # outputs:mtlx:surface to it, and so does this.
    material.CreateSurfaceOutput("mtlx").ConnectToSource(
        surface.CreateOutput("out", Sdf.ValueTypeNames.Token)
    )
    return material


def build(stage):
    """Define every probe material and return them by name.

    The scope is a sibling of the asset, so hiding or showing the asset does
    not touch it and nothing under it is reachable by a traversal scoped to the
    asset root.
    """
    UsdGeom.Scope.Define(stage, PROBE_SCOPE)
    return {
        READ: _material(stage, READ, FALLBACK_COLOR, OPAQUE),
        # A duplicate of Read, and the whole point of it is that it is a
        # duplicate. Every comparison this benchmark makes is between two
        # frames taken either side of a material swap, and a swap costs the
        # path tracer its accumulated history: it re-shades from scratch and
        # lands on a different noise realisation. Capturing the control without
        # a swap in between measured that noise at 0.0% and the real
        # swap-to-swap floor at 4.0%, so the control was understating the floor
        # by the entire floor. Binding a second identical material makes the
        # control the same kind of comparison as the measurements.
        READ_CONTROL: _material(stage, READ_CONTROL, FALLBACK_COLOR, OPAQUE),
        REMOVED: _material(stage, REMOVED, None, OPAQUE, flat_color=FALLBACK_COLOR),
        OPACITY: _material(stage, OPACITY, FALLBACK_COLOR, TRANSPARENT),
    }


def bind(stage, root_path, material):
    """Bind one probe material over the whole asset.

    ``strongerThanDescendants`` is what makes this a swap rather than an
    addition: it beats every binding the asset authors below the root,
    including ones inside prototypes reached through instance proxies, without
    any of them being edited. Re-calling this with a different material
    retargets the same relationship.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        raise RuntimeError("The asset root %s is not on the stage." % root_path)
    api = UsdShade.MaterialBindingAPI.Apply(root)
    api.Bind(material, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
    return root


def unbind(stage, root_path):
    """Take the probe binding back off the asset root.

    The stage is the one the framework composed for this run and is never
    written to disk, so this is housekeeping rather than a correctness
    requirement. It is here so the frames a later step captures are of the
    asset as it shipped.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return False
    UsdShade.MaterialBindingAPI(root).UnbindAllBindings()
    return True


def bound_probe(prim):
    """The probe material name resolved on ``prim``, or None.

    Used to confirm the swap reached the geometry before any pixel is read. A
    Gprim that does not resolve the probe is one the render cannot say anything
    about, and saying so by name beats reporting it later as an unexplained
    absence of response.
    """
    material, _rel = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(
        materialPurpose=UsdShade.Tokens.full
    )
    if not material:
        return None
    path = material.GetPrim().GetPath()
    if path.GetParentPath().pathString != PROBE_SCOPE:
        return None
    return path.name


def resolves_display_opacity(prim):
    """Whether ``primvars:displayOpacity`` resolves on this Gprim.

    Follows inheritance, on the same terms DISP.001 sets for ``displayColor``.
    This predicts what the opacity probe frame should show -- geometry that
    resolves nothing takes the reader's fallback and disappears when that
    fallback is dropped to zero -- and the frame then either bears the
    prediction out or does not. It gates nothing.
    """
    primvar = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance(DISPLAY_OPACITY)
    if not primvar:
        return False
    values = primvar.Get()
    return values is not None and len(values) > 0
