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
"""Author ``primvars:displayColor`` onto SimReady sample geometry.

Adds the ``FET_010_STANDARD`` contract to assets that carry a shaded
material but no display colour: a constant ``primvars:displayColor`` on every
renderable Gprim, derived from the material bound to that Gprim and held inside
the range DISP.002 defines.

The colour is derived, not invented. For each Gprim the script reads the bound
material's base colour, in this order:

1. OpenPBR ``base_color`` reached through ``outputs:mtlx:surface``
2. UsdPreviewSurface ``diffuseColor`` reached through ``outputs:surface``
3. MDL ``diffuse_color_constant`` / ``diffuse_texture`` (OmniPBR) or
   ``glass_color`` / ``glass_color_texture`` (OmniGlass), through
   ``outputs:mdl:surface``

Within each tier a texture beats a constant, because where a source drives base
colour from a map the constant beside it is usually the exporter's neutral
default rather than the colour the material shows.

A texture cannot go into a constant primvar, so it is reduced to one colour by
sampling it only where the geometry actually lands on it: the faces bound to
that material are triangulated, sampled at stratified points in UV space, and
averaged weighted by world-space triangle area. Sampling the whole image
instead would give the same answer for every material that shares an atlas,
which is the common case in this library.

Values are averaged in linear light. A diffuse map is sRGB-encoded, and
``displayColor`` resolves to linear Rec.709 unless a colour space says
otherwise, so each texel is decoded through the sRGB transfer function before
it enters the mean. sRGB and Rec.709 share primaries and a D65 white point, so
the transfer function is the whole conversion.

The script is safe to re-run. Every value is derived from scratch on each pass
and the derivation is deterministic, so a re-run leaves the same colour on the
same prim. A display colour it did not author itself is left alone and reported.

Usage::

    python author_display_color.py <path>... [--dry-run] [--no-textures] [--verify]

``<path>`` may be a USD file or a directory, which is searched for
``simready_usd`` assets. Run ``--verify`` on its own to report DISP.001, DISP.002
and DISP.003 conformance without editing anything; those checks are transcribed
from the capability validator, which a standalone run cannot import.

Exit codes::

    0  clean
    1  --verify found conformance problems
    2  bad arguments, or no USD assets under the given paths
    3  at least one asset could not be read or raised

A crash and a finding do not share a code, so a caller can tell them apart.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import traceback
from typing import Iterable, Optional

try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
except ImportError:  # pragma: no cover - environment guard
    sys.exit("USD Python is required. Install with: pip install usd-core")

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional
    np = None

try:
    from PIL import Image

    # These are large authoring textures, not untrusted uploads; the decompression
    # bomb guard exists for the latter and would refuse a legitimate 8K map.
    Image.MAX_IMAGE_PIXELS = None
except ImportError:  # pragma: no cover - optional
    Image = None


DISPLAY_COLOR = "displayColor"

# DISP.002 bounds. Every component of every element has to sit inside this.
COMPONENT_MIN, COMPONENT_MAX = 0.0, 1.0

# The OpenUSD default colour space for displayColor: Rec.709 primaries, D65
# white point, linear transfer function. DISP.002 makes authoring it optional
# because the default is well defined; it is authored here anyway, so the file
# records that these values were decoded out of sRGB rather than copied.
LINEAR_REC709 = "lin_rec709_scene"

# Where the derivation is recorded, so a re-run can tell its own work from a
# display colour someone authored by hand and leave the latter alone. Read back
# through the same key; USD nests it under "simready".
SOURCE_KEY = "simready:displayColorSource"

OPENPBR_SURFACE_ID = "ND_open_pbr_surface_surfaceshader"
PREVIEW_SURFACE_ID = "UsdPreviewSurface"

# Node ids that read an image in a MaterialX graph, and the input holding the file.
MTLX_IMAGE_IDS = ("ND_tiledimage_color3", "ND_image_color3", "ND_tiledimage_vector3")

# Texture formats that are linear by construction. Everything else in this
# library is an 8-bit PNG, which for a base colour map means sRGB-encoded.
FLOAT_FORMATS = (".exr", ".hdr")

# Colour space tokens that name an encoded (non-linear) source.
ENCODED_TOKENS = {"srgb", "srgb_texture", "sRGB", "auto"}
RAW_TOKENS = {"raw", "none", "linear", "lin_rec709_scene", "lin_srgb"}

# Sampling budget. Every triangle of a face group gets the same number of
# stratified samples, chosen so the group lands near this total. A fixed budget
# keeps the run deterministic, which is what makes a re-run idempotent.
TARGET_SAMPLES = 200_000
MAX_SAMPLES_PER_TRIANGLE = 64

# The two outcomes a texture-driven material can have when maps are not sampled.
# Named here because the closing summary counts them off the notes, and a summary
# that claims a fallback nobody used is worse than no summary at all.
FALLBACK_NOTE = "reader fallback beside"
UNSAMPLED_NOTE = "is texture-driven and could not be sampled"


# ----------------------------------------------------------------------------
# Colour
# ----------------------------------------------------------------------------


def srgb_to_linear_scalar(value: float) -> float:
    """The sRGB electro-optical transfer function, exact piecewise form."""
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _lut(encoded: bool):
    """A 256-entry lookup from 8-bit texel to linear float.

    Decoding through a table rather than per texel keeps the image in memory as
    bytes: a 2K map is 12 MB rather than 50 MB, and the decode is exact because
    an 8-bit source has only 256 possible values per channel.
    """
    table = [i / 255.0 for i in range(256)]
    if encoded:
        table = [srgb_to_linear_scalar(v) for v in table]
    return np.asarray(table, dtype=np.float32)


def clamp_component(value: float) -> float:
    return max(COMPONENT_MIN, min(COMPONENT_MAX, value))


def held(rgb) -> Optional[Gf.Vec3f]:
    """Hold a colour inside DISP.002's range, or reject it as unusable.

    Out of range is clamped, because a source value slightly outside [0,1] is
    usually an export artefact and the colour it names is still the right one.
    Non-finite is rejected: there is no defensible value to clamp NaN to, and
    substituting one would invent a colour rather than derive it.
    """
    try:
        components = [float(rgb[0]), float(rgb[1]), float(rgb[2])]
    except (TypeError, ValueError, IndexError):
        return None
    if not all(math.isfinite(c) for c in components):
        return None
    return Gf.Vec3f(*[clamp_component(c) for c in components])


# ----------------------------------------------------------------------------
# Material sources
# ----------------------------------------------------------------------------


class UvXform:
    """The UV transform a texture reader applies before it samples.

    ``st * scale`` rotated by ``rotation`` degrees, then offset by
    ``translation``, which is what ``UsdTransform2d`` specifies. The MaterialX
    and MDL forms carry no rotation, so they only fill scale and translation.
    """

    def __init__(self, scale=(1.0, 1.0), translation=(0.0, 0.0), rotation=0.0,
                 primvar="st"):
        self.scale = (float(scale[0]), float(scale[1]))
        self.translation = (float(translation[0]), float(translation[1]))
        self.rotation = float(rotation)
        self.primvar = primvar

    @property
    def identity(self) -> bool:
        return (self.scale == (1.0, 1.0) and self.translation == (0.0, 0.0)
                and self.rotation == 0.0)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        if self.identity:
            return f"uv={self.primvar}"
        return (f"uv={self.primvar} scale={self.scale} "
                f"offset={self.translation} rot={self.rotation}")


class TexRef:
    """A base colour texture: the file, how to read it, and what it claims."""

    def __init__(self, path: str, resolved: Optional[str], declared: Optional[str],
                 uv: UvXform, wrap_s: str = "repeat", wrap_t: str = "repeat",
                 scale=None, bias=None):
        self.path = path
        self.resolved = resolved
        # What the asset says the file's colour space is. Recorded so a
        # disagreement with the role rule can be reported rather than hidden.
        self.declared = declared
        self.uv = uv
        self.wrap_s = wrap_s
        self.wrap_t = wrap_t
        self.scale = scale
        self.bias = bias

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def encoded(self) -> bool:
        """Whether the file has to be decoded before it can be averaged.

        Decided by what the texture is for rather than by what the asset says.
        A base colour map in an integer format is sRGB-encoded; only a float
        format is linear by construction. Source metadata is unreliable here:
        the dishwand's OmniGlass shader labels the same PNG ``raw`` that its
        UsdPreviewSurface labels ``sRGB``, and following it would leave the
        clear plastic far too bright.
        """
        return not self.path.lower().endswith(FLOAT_FORMATS)

    @property
    def mislabelled(self) -> bool:
        """The asset declares a colour space that contradicts the role rule."""
        if self.declared is None:
            return False
        return self.encoded and self.declared.lower() in {t.lower() for t in RAW_TOKENS}


class Albedo:
    """What a material contributes to a display colour, and where it came from."""

    def __init__(self, origin: str, constant: Optional[Gf.Vec3f] = None,
                 texture: Optional[TexRef] = None, fallback: Optional[Gf.Vec3f] = None):
        self.origin = origin
        self.constant = constant
        self.texture = texture
        # The constant a texture reader falls back on when the map fails to
        # load. Only used when sampling is off or unavailable, because on a
        # migrated sample it is usually the OpenPBR nodedef default rather than
        # anything the material shows.
        self.fallback = fallback


def shader_id(shader) -> Optional[str]:
    if shader is None or not shader:
        return None
    attr = shader.GetIdAttr()
    return attr.Get() if attr else None


def connected_surface(material: UsdShade.Material, context: Optional[str]):
    """The shader a surface output resolves to, or None."""
    out = material.GetSurfaceOutput(context) if context else material.GetSurfaceOutput()
    if not out or not out.HasConnectedSource():
        return None
    source = out.GetConnectedSource()
    if not source:
        return None
    prim = source[0].GetPrim()
    if not prim or prim.GetTypeName() != "Shader":
        return None
    return UsdShade.Shader(prim)


def asset_path(value) -> Optional[str]:
    return getattr(value, "path", None) or None


def resolved_path(value, stage: Usd.Stage) -> Optional[str]:
    """Where an asset path lands on disk, or None when nothing is there."""
    path = asset_path(value)
    if not path:
        return None
    resolved = getattr(value, "resolvedPath", "") or ""
    if resolved and os.path.isfile(resolved):
        return resolved
    layer = stage.GetRootLayer()
    base = os.path.dirname(layer.realPath or layer.identifier)
    candidate = os.path.normpath(os.path.join(base, path))
    return candidate if os.path.isfile(candidate) else None


def input_value(shader, name):
    """An input's authored constant, or None when absent or connected."""
    if shader is None:
        return None
    shader_input = shader.GetInput(name)
    if not shader_input or shader_input.HasConnectedSource():
        return None
    return shader_input.Get()


def follow(shader, name):
    """The (prim, output name) an input connects to, or (None, None)."""
    if shader is None:
        return None, None
    shader_input = shader.GetInput(name)
    if not shader_input or not shader_input.HasConnectedSource():
        return None, None
    source = shader_input.GetConnectedSource()
    if not source:
        return None, None
    return source[0].GetPrim(), source[1]


def uv_chain(texture_shader) -> UvXform:
    """Read the UV set and 2D transform feeding a ``UsdUVTexture``.

    The chain is ``UsdPrimvarReader_float2 -> [UsdTransform2d] -> UsdUVTexture``.
    Both hops are optional; a texture with neither samples ``st`` untransformed.
    """
    xform = UvXform()
    prim, _out = follow(texture_shader, "st")
    for _hop in range(4):
        if prim is None or not prim:
            return xform
        shader = UsdShade.Shader(prim)
        sid = shader_id(shader)
        if sid == "UsdTransform2d":
            scale = input_value(shader, "scale") or Gf.Vec2f(1.0, 1.0)
            translation = input_value(shader, "translation") or Gf.Vec2f(0.0, 0.0)
            rotation = input_value(shader, "rotation")
            xform = UvXform(scale, translation, rotation or 0.0, xform.primvar)
            prim, _out = follow(shader, "in")
            continue
        if sid and sid.startswith("UsdPrimvarReader"):
            varname = input_value(shader, "varname")
            if varname:
                xform.primvar = str(varname)
            return xform
        return xform
    return xform


def preview_texture(stage, shader, name) -> Optional[TexRef]:
    """The ``UsdUVTexture`` feeding a UsdPreviewSurface input, if any."""
    prim, _out = follow(shader, name)
    for _hop in range(4):
        if prim is None or not prim:
            return None
        node = UsdShade.Shader(prim)
        file_input = node.GetInput("file")
        value = file_input.Get() if file_input else None
        if asset_path(value):
            declared = input_value(node, "sourceColorSpace")
            return TexRef(
                asset_path(value), resolved_path(value, stage),
                str(declared) if declared else None, uv_chain(node),
                str(input_value(node, "wrapS") or "repeat"),
                str(input_value(node, "wrapT") or "repeat"),
                input_value(node, "scale"), input_value(node, "bias"))
        prim, _out = follow(node, "in")
    return None


def interface_value(material_prim: Usd.Prim, shader, name):
    """Resolve an input that may be routed through the Material's interface.

    The OpenPBR migration exposes every parameter on the ``Material`` prim and
    has the shader read it back, so the constant is one hop away rather than on
    the shader itself.
    """
    direct = input_value(shader, name)
    if direct is not None:
        return direct
    prim, output = follow(shader, name)
    if prim and prim == material_prim:
        material_input = UsdShade.Material(material_prim).GetInput(str(output))
        if material_input and not material_input.HasConnectedSource():
            return material_input.Get()
    return None


def openpbr_albedo(stage, material_prim: Usd.Prim, shader) -> Optional[Albedo]:
    """``base_color`` off an OpenPBR surface, texture first."""
    prim, _out = follow(shader, "base_color")
    if prim:
        node = UsdShade.Shader(prim)
        if shader_id(node) in MTLX_IMAGE_IDS:
            file_input = node.GetInput("file")
            value = file_input.Get() if file_input else None
            declared = None
            if file_input and file_input.HasConnectedSource():
                # The reference topology puts the file, and its colour space,
                # on the Material's interface input rather than on the reader.
                source = file_input.GetConnectedSource()
                owner = UsdShade.Material(material_prim).GetInput(str(source[1]))
                if owner:
                    value = owner.Get()
                    declared = owner.GetAttr().GetColorSpace() or None
            if asset_path(value):
                uv = UvXform(
                    interface_value(material_prim, node, "uvtiling") or Gf.Vec2f(1.0, 1.0),
                    interface_value(material_prim, node, "uvoffset") or Gf.Vec2f(0.0, 0.0))
                texture = TexRef(asset_path(value), resolved_path(value, stage),
                                 str(declared) if declared else None, uv)
                default = interface_value(material_prim, node, "default")
                fallback = held(default) if default is not None else None
                return Albedo("OpenPBR base_color", texture=texture, fallback=fallback)
    value = interface_value(material_prim, shader, "base_color")
    constant = held(value) if value is not None else None
    if constant is not None:
        return Albedo("OpenPBR base_color", constant=constant)
    return None


def preview_albedo(stage, shader) -> Optional[Albedo]:
    """``diffuseColor`` off a UsdPreviewSurface, texture first."""
    texture = preview_texture(stage, shader, "diffuseColor")
    if texture is not None:
        return Albedo("UsdPreviewSurface diffuseColor", texture=texture)
    value = input_value(shader, "diffuseColor")
    constant = held(value) if value is not None else None
    if constant is not None:
        return Albedo("UsdPreviewSurface diffuseColor", constant=constant)
    return None


def mdl_albedo(stage, shader) -> Optional[Albedo]:
    """Base colour off an MDL surface: OmniGlass names it differently.

    OmniGlass describes a transmissive material and calls its base colour
    ``glass_color``, so an OmniGlass source is read through those names rather
    than OmniPBR's.
    """
    attr = shader.GetPrim().GetAttribute("info:mdl:sourceAsset:subIdentifier")
    identifier = str(attr.Get() if attr else "").lower()
    if "glass" in identifier:
        pairs = [("glass_color_texture", "glass_color")]
        label = "OmniGlass glass_color"
    else:
        pairs = [("diffuse_texture", "diffuse_color_constant")]
        label = "OmniPBR diffuse_color"
    for texture_name, constant_name in pairs:
        value = input_value(shader, texture_name)
        if asset_path(value):
            shader_input = shader.GetInput(texture_name)
            declared = shader_input.GetAttr().GetColorSpace() or None
            uv = UvXform(input_value(shader, "texture_scale") or Gf.Vec2f(1.0, 1.0),
                         input_value(shader, "texture_translate") or Gf.Vec2f(0.0, 0.0),
                         input_value(shader, "texture_rotate") or 0.0)
            texture = TexRef(asset_path(value), resolved_path(value, stage),
                             str(declared) if declared else None, uv)
            return Albedo(f"{label} texture", texture=texture)
        raw = input_value(shader, constant_name)
        constant = held(raw) if raw is not None else None
        if constant is not None:
            return Albedo(f"{label} constant", constant=constant)
    return None


def material_albedo(stage: Usd.Stage, material_prim: Usd.Prim) -> Optional[Albedo]:
    """Resolve a material's base colour through the surface tiers in order.

    OpenPBR first: it is the final surface the material declares, so where one
    is authored it carries the intent. UsdPreviewSurface next, MDL last. The
    order is strict, so a hand-tuned OpenPBR constant wins over a legacy preview
    texture rather than being averaged with it.
    """
    material = UsdShade.Material(material_prim)

    openpbr = connected_surface(material, "mtlx")
    if shader_id(openpbr) == OPENPBR_SURFACE_ID:
        found = openpbr_albedo(stage, material_prim, openpbr)
        if found is not None:
            return found

    preview = connected_surface(material, None)
    if shader_id(preview) == PREVIEW_SURFACE_ID:
        found = preview_albedo(stage, preview)
        if found is not None:
            return found

    mdl = connected_surface(material, "mdl")
    if mdl is not None:
        found = mdl_albedo(stage, mdl)
        if found is not None:
            return found
    return None


# ----------------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------------


class FaceGroup:
    """The faces of one Gprim that share one bound material."""

    def __init__(self, material: Optional[Usd.Prim], faces: Optional[list]):
        self.material = material
        # None means every face of the prim: the direct binding with no subsets.
        self.faces = faces


def bound_material(prim: Usd.Prim) -> Optional[Usd.Prim]:
    material, _rel = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
    if not material:
        return None
    material_prim = material.GetPrim()
    return material_prim if material_prim and material_prim.IsValid() else None


def face_groups(prim: Usd.Prim) -> list:
    """Split a Gprim into the face sets its materials are bound to.

    A mesh can carry several materials through ``materialBind`` GeomSubsets.
    The toaster's body is one Mesh with 8,008 plastic faces and 12,356 metal
    ones, so reading only the direct binding would report the whole body as
    plastic.
    """
    binding = UsdShade.MaterialBindingAPI(prim)
    subsets = binding.GetMaterialBindSubsets()
    groups, covered = [], set()
    for subset in subsets:
        if subset.GetElementTypeAttr().Get() != UsdGeom.Tokens.face:
            continue
        indices = subset.GetIndicesAttr().Get()
        if indices is None or len(indices) == 0:
            continue
        material = bound_material(subset.GetPrim())
        faces = [int(i) for i in indices]
        covered.update(faces)
        groups.append(FaceGroup(material, faces))

    direct = bound_material(prim)
    mesh = UsdGeom.Mesh(prim)
    counts = mesh.GetFaceVertexCountsAttr().Get() if mesh else None
    total = len(counts) if counts else 0
    if not groups:
        groups.append(FaceGroup(direct, None))
    elif total and len(covered) < total:
        # Faces outside every subset still render, and they take the prim's own
        # binding. Leaving them out would weight the mean towards the subsets.
        remainder = [i for i in range(total) if i not in covered]
        if remainder and direct is not None:
            groups.append(FaceGroup(direct, remainder))
    return groups


def renderable_gprims(stage: Usd.Stage) -> Iterable[Usd.Prim]:
    """Every Gprim a renderer would draw.

    Purpose ``guide`` and ``proxy`` are out of scope for DISP.001, so a grasp
    guide curve is not given a display colour it would never show. The default
    traversal predicate is used rather than ``TraverseAll``, so class prims and
    deactivated prims are left out: neither renders, and a class prim cannot
    carry an authored opinion that means anything on its own.
    """
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        if not UsdGeom.Gprim(prim):
            continue
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            continue
        if imageable.ComputePurpose() not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
            continue
        yield prim


class Triangles:
    """A Gprim's triangulated surface, with world-space areas and UVs."""

    def __init__(self, face_index, corners, areas, uv):
        self.face_index = face_index  # source face per triangle
        self.corners = corners        # (n, 3) indices into the flattened corner list
        self.areas = areas            # (n,) world-space area
        self.uv = uv                  # (n, 3, 2) or None when the prim has no UVs


def triangulate(prim: Usd.Prim, primvar_name: str) -> Optional[Triangles]:
    """Fan-triangulate a mesh and gather what a texture sample needs.

    Areas are world-space so a face group's mean is weighted by the surface a
    viewer actually sees, not by how the prim happens to be scaled.
    """
    mesh = UsdGeom.Mesh(prim)
    if not mesh:
        return None
    counts = mesh.GetFaceVertexCountsAttr().Get()
    indices = mesh.GetFaceVertexIndicesAttr().Get()
    points = mesh.GetPointsAttr().Get()
    if not counts or not indices or not points:
        return None

    matrix = UsdGeom.Imageable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    world = np.asarray([matrix.Transform(p) for p in points], dtype=np.float64)

    counts = np.asarray(counts, dtype=np.int64)
    indices = np.asarray(indices, dtype=np.int64)
    offsets = np.concatenate(([0], np.cumsum(counts)[:-1]))

    face_index, corners = [], []
    for face, count in enumerate(counts):
        start = int(offsets[face])
        for i in range(1, int(count) - 1):
            face_index.append(face)
            corners.append((start, start + i, start + i + 1))
    if not corners:
        return None
    face_index = np.asarray(face_index, dtype=np.int64)
    corners = np.asarray(corners, dtype=np.int64)

    p = world[indices[corners]]  # (n, 3, 3)
    cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    areas = 0.5 * np.linalg.norm(cross, axis=1)

    uv = corner_uvs(prim, primvar_name, corners, indices, face_index, len(points))
    return Triangles(face_index, corners, areas, uv)


def corner_uvs(prim, primvar_name, corners, indices, face_index, point_count):
    """Gather each triangle corner's UV, whatever interpolation the mesh uses."""
    primvar = UsdGeom.PrimvarsAPI(prim).GetPrimvar(primvar_name)
    if not primvar or not primvar.HasAuthoredValue():
        for name in ("st", "st0", "uv", "UVMap"):
            candidate = UsdGeom.PrimvarsAPI(prim).GetPrimvar(name)
            if candidate and candidate.HasAuthoredValue():
                primvar = candidate
                break
        else:
            return None
    values = primvar.ComputeFlattened()
    if values is None or len(values) == 0:
        return None
    values = np.asarray(values, dtype=np.float64)
    interpolation = primvar.GetInterpolation()

    if interpolation == UsdGeom.Tokens.faceVarying and len(values) >= corners.max() + 1:
        return values[corners]
    if interpolation in (UsdGeom.Tokens.vertex, UsdGeom.Tokens.varying) \
            and len(values) >= point_count:
        return values[indices[corners]]
    if interpolation == UsdGeom.Tokens.uniform and len(values) > face_index.max():
        return np.repeat(values[face_index][:, None, :], 3, axis=1)
    if interpolation == UsdGeom.Tokens.constant:
        return np.broadcast_to(values[0], (len(corners), 3, 2)).copy()
    return None


# ----------------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------------


_IMAGE_CACHE: dict = {}


def load_image(path: str, encoded: bool):
    """An 8-bit RGB image plus the table that decodes it to linear."""
    key = (os.path.abspath(path), encoded)
    if key not in _IMAGE_CACHE:
        with Image.open(path) as image:
            pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
        _IMAGE_CACHE[key] = (pixels, _lut(encoded))
    return _IMAGE_CACHE[key]


def barycentric_samples(count: int):
    """Stratified barycentric coordinates, the same set on every run.

    A Hammersley set mapped onto the triangle. Deterministic, which is what
    lets a re-run produce the identical colour: a random sequence would move
    every value by a fraction each pass and rewrite every asset.
    """
    i = np.arange(count, dtype=np.float64)
    u = (i + 0.5) / count
    # Radical inverse in base 2.
    v = np.zeros(count, dtype=np.float64)
    bits = np.arange(count, dtype=np.uint64)
    denominator = 2.0
    while bits.any():
        v += (bits & np.uint64(1)).astype(np.float64) / denominator
        bits = bits >> np.uint64(1)
        denominator *= 2.0
    root = np.sqrt(u)
    return np.stack([1.0 - root, root * (1.0 - v), root * v], axis=1)


def apply_uv_xform(uv, xform: UvXform):
    if xform.identity:
        return uv
    scaled = uv * np.asarray(xform.scale)
    if xform.rotation:
        angle = math.radians(xform.rotation)
        cos, sin = math.cos(angle), math.sin(angle)
        scaled = np.stack([scaled[..., 0] * cos - scaled[..., 1] * sin,
                           scaled[..., 0] * sin + scaled[..., 1] * cos], axis=-1)
    return scaled + np.asarray(xform.translation)


def lookup(pixels, lut, uv, wrap_s: str, wrap_t: str):
    """Nearest-texel lookup, decoded to linear on the way out."""
    height, width = pixels.shape[0], pixels.shape[1]
    u, v = uv[..., 0], uv[..., 1]
    u = np.clip(u, 0.0, 1.0) if wrap_s == "clamp" else u - np.floor(u)
    v = np.clip(v, 0.0, 1.0) if wrap_t == "clamp" else v - np.floor(v)
    x = np.minimum((u * width).astype(np.int64), width - 1)
    # USD's ST origin is the bottom left of the image; row 0 is the top.
    y = np.minimum(((1.0 - v) * height).astype(np.int64), height - 1)
    return lut[pixels[y, x]]


def sample_texture(triangles: Triangles, faces: Optional[list], texture: TexRef):
    """Reduce a texture to one colour over the faces bound to it.

    The mean is over world-space surface area, sampled at stratified points in
    UV space, and taken in linear light. What it loses is stated in SKILL.md:
    one number cannot hold a label, a stripe or a second material.
    """
    if triangles.uv is None:
        return None, 0.0, "no UV primvar to sample with"
    if texture.resolved is None:
        return None, 0.0, f"{texture.name} does not resolve to a file on disk"

    if faces is None:
        selected = np.ones(len(triangles.areas), dtype=bool)
    else:
        wanted = np.zeros(int(triangles.face_index.max()) + 1, dtype=bool)
        inside = [f for f in faces if f < len(wanted)]
        wanted[inside] = True
        selected = wanted[triangles.face_index]
    areas = triangles.areas[selected]
    uvs = triangles.uv[selected]
    if len(areas) == 0 or float(areas.sum()) <= 0.0:
        return None, 0.0, "the bound faces have no surface area"

    pixels, lut = load_image(texture.resolved, texture.encoded)
    count = int(min(MAX_SAMPLES_PER_TRIANGLE,
                    max(1, math.ceil(TARGET_SAMPLES / len(areas)))))
    weights = barycentric_samples(count)

    total = np.zeros(3, dtype=np.float64)
    for weight in weights:
        uv = (uvs[:, 0] * weight[0] + uvs[:, 1] * weight[1] + uvs[:, 2] * weight[2])
        uv = apply_uv_xform(uv, texture.uv)
        rgb = lookup(pixels, lut, uv, texture.wrap_s, texture.wrap_t)
        total += (rgb * areas[:, None]).sum(axis=0)
    mean = total / (float(areas.sum()) * count)

    # UsdUVTexture applies scale and bias after the read, so a material that
    # tints or offsets its map is followed rather than ignored.
    if texture.scale is not None:
        mean = mean * np.asarray([float(texture.scale[i]) for i in range(3)])
    if texture.bias is not None:
        mean = mean + np.asarray([float(texture.bias[i]) for i in range(3)])
    return mean, float(areas.sum()), f"{texture.name} sampled over {len(areas)} triangle(s)"


def group_area(triangles: Optional[Triangles], faces: Optional[list]) -> float:
    """The world-space area a face group covers, used to weight constants."""
    if triangles is None:
        return 1.0
    if faces is None:
        return float(triangles.areas.sum())
    wanted = np.zeros(int(triangles.face_index.max()) + 1, dtype=bool)
    wanted[[f for f in faces if f < len(wanted)]] = True
    return float(triangles.areas[wanted[triangles.face_index]].sum())


# ----------------------------------------------------------------------------
# Derivation
# ----------------------------------------------------------------------------


class Contribution:
    def __init__(self, material, color, weight, detail):
        self.material = material
        self.color = color
        self.weight = weight
        self.detail = detail


def derive_gprim(stage: Usd.Stage, prim: Usd.Prim, sample: bool):
    """The display colour for one Gprim, and how each material contributed.

    A Gprim carrying several materials gets the area-weighted mean of their
    base colours, because a constant primvar holds one value. That mean matches
    no single material exactly, which is the cost of ``constant`` interpolation
    and is recorded rather than hidden.
    """
    groups = face_groups(prim)
    triangles = None
    if sample and np is not None:
        # Only meshes carry the topology a texture sample needs; a Sphere or a
        # Capsule has a material but nothing to walk, so it falls back to the
        # material's constant.
        triangles = triangulate(prim, "st")

    contributions, notes = [], []
    for group in groups:
        if group.material is None:
            notes.append("no material bound" if group.faces is None
                         else f"no material bound to {len(group.faces)} face(s)")
            continue
        albedo = material_albedo(stage, group.material)
        if albedo is None:
            notes.append(f"{group.material.GetName()}: no base colour on any surface")
            continue
        name = group.material.GetName()
        weight = group_area(triangles, group.faces) if triangles is not None else 1.0

        if albedo.texture is not None and sample and np is not None and Image is not None:
            mean, area, detail = sample_texture(triangles, group.faces, albedo.texture) \
                if triangles is not None else (None, 0.0, "prim carries no mesh topology")
            if mean is not None:
                color = held(mean)
                if color is not None:
                    flag = " [source says raw, read as sRGB]" if albedo.texture.mislabelled else ""
                    contributions.append(Contribution(
                        name, color, max(area, 1e-12),
                        f"{albedo.origin} <- {detail}{flag}"))
                    continue
                notes.append(f"{name}: sampled colour is not finite")
                continue
            notes.append(f"{name}: {detail}")

        constant = albedo.constant
        source = f"{albedo.origin} constant"
        if constant is None and albedo.texture is not None:
            constant = albedo.fallback
            source = f"{albedo.origin} {FALLBACK_NOTE} {albedo.texture.name}"
        if constant is None:
            notes.append(f"{name}: {albedo.origin} {UNSAMPLED_NOTE}")
            continue
        contributions.append(Contribution(name, constant, max(weight, 1e-12), source))

    if not contributions:
        return None, notes, contributions

    total = sum(c.weight for c in contributions)
    mixed = [sum(float(c.color[i]) * c.weight for c in contributions) / total for i in range(3)]
    return held(mixed), notes, contributions


# ----------------------------------------------------------------------------
# Authoring
# ----------------------------------------------------------------------------


def stamp_of(prim: Usd.Prim) -> Optional[str]:
    attr = prim.GetAttribute(f"primvars:{DISPLAY_COLOR}")
    if not attr:
        return None
    value = attr.GetCustomDataByKey(SOURCE_KEY)
    return str(value) if value is not None else None


def authored_here(prim: Usd.Prim) -> bool:
    attr = prim.GetAttribute(f"primvars:{DISPLAY_COLOR}")
    return bool(attr) and attr.HasAuthoredValue()


def inherited_from(prim: Usd.Prim) -> Optional[Usd.Prim]:
    """The ancestor a display colour resolves from, when the prim has none."""
    primvar = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance(DISPLAY_COLOR)
    if not primvar or not primvar.GetAttr().HasAuthoredValue():
        return None
    owner = primvar.GetAttr().GetPrim()
    return None if owner == prim else owner


def blocked_by(prim: Usd.Prim) -> Optional[str]:
    """Why this script must not author onto ``prim``, or None.

    Two ways a display colour already belongs to someone else: one authored on
    the Gprim without this script's stamp, or one inherited from an ancestor.
    Both are deliberate authoring, and overwriting either throws it away.
    """
    if authored_here(prim) and stamp_of(prim) is None:
        return "display colour already authored on the prim"
    ancestor = inherited_from(prim)
    if ancestor is not None:
        return f"display colour inherited from {ancestor.GetPath()}"
    return None


# Every purpose a direct binding can be authored under. UsdShade resolves a purpose-less
# binding as the fallback for all of them, so it is tried first.
BINDING_PURPOSES = (UsdShade.Tokens.allPurpose, UsdShade.Tokens.full, UsdShade.Tokens.preview)


def binding_opinion(prim: Usd.Prim):
    """The strongest authored spec of whichever binding relationship binds this prim.

    Read through ``UsdShade.MaterialBindingAPI`` rather than by fetching
    ``material:binding`` by name: a binding can be authored per purpose
    (``material:binding:full``, ``material:binding:preview``) or through a collection, and
    matching one literal name skips the rest. The colour derivation already resolves
    bindings properly through ``ComputeBoundMaterial``, so reading them differently here
    made the two halves disagree about what a binding is.

    Where the geometry carries no binding of its own, an ancestor's is used: a constant
    primvar inherits down namespace, so authoring beside the binding that covers this prim
    reaches it, which is what DISP.001's guidance describes.
    """
    walk = prim
    while walk and walk.GetPath() != walk.GetPath().GetParentPath():
        api = UsdShade.MaterialBindingAPI(walk)
        for purpose in BINDING_PURPOSES:
            relationship = api.GetDirectBindingRel(purpose)
            if not (relationship and relationship.IsValid()):
                continue
            stack = relationship.GetPropertyStack(Usd.TimeCode.Default())
            if stack:
                return stack[0]
        walk = walk.GetParent()
    return None


def binding_edit_target(prim: Usd.Prim):
    """The layer and path to author this Gprim's display colour into, or None.

    Display colour is an attribute, so it belongs where this asset's existing opinion
    about the prim's appearance is expressed, which is the layer holding the strongest
    ``material:binding``. That is not always where the prim is defined: a stronger layer
    often holds an ``over`` for a transform or visibility and says nothing about
    appearance.

    It also resolves instancing. A Gprim reached through an instance proxy cannot be
    authored at the path it appears on, and its prototype path is not persistent; the
    binding's property spec names both the layer and the path within it, which is where
    the opinion has to go for every instance to inherit it.

    Reading the property stack needs the prim inside the prototype -- through the proxy
    the stack reads empty, which looks like a material with no binding at all.
    """
    source = prim.GetPrimInPrototype() if prim.IsInstanceProxy() else prim
    if not source:
        return None
    strongest = binding_opinion(source)
    if strongest is None:
        # A binding through a collection is authored on the collection's owner rather than
        # on the geometry, so there is no per-Gprim opinion to sit beside. Reported by the
        # caller rather than guessed at.
        return None
    return strongest.layer, strongest.path.GetPrimPath()


def author(prim: Usd.Prim, color: Gf.Vec3f, source: str) -> None:
    """Write the primvar, its colour space and its derivation.

    ``constant`` interpolation with a single element: DISP.002 pairs that count
    with that interpolation, and a constant primvar is the only kind USD
    inherits down namespace, so the value stays usable if the asset is later
    restructured.
    """
    primvar = UsdGeom.Gprim(prim).CreateDisplayColorPrimvar(UsdGeom.Tokens.constant)
    primvar.Set(Vt.Vec3fArray([color]))
    if primvar.IsIndexed():
        # An indexed primvar carries its values through an index array, which
        # would leave the element count disagreeing with the interpolation.
        primvar.BlockIndices()
    attr = primvar.GetAttr()
    attr.SetColorSpace(LINEAR_REC709)
    attr.SetCustomDataByKey(SOURCE_KEY, source)


def format_color(color) -> str:
    return "(" + ", ".join(f"{float(c):.4f}" for c in color) + ")"


# ----------------------------------------------------------------------------
# Verification
#
# ``--verify`` must report what the shipped capability validator reports, and
# nothing else. That validator is
#
#     nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/
#         capabilities/visualization/display_color/validation.py
#
# and it cannot be imported from here: it depends on
# ``simready.foundation.tier_core.requirements`` and
# ``usd_validation_nvidia``, neither of which is available to a standalone run,
# which is the whole reason this preflight exists. So what follows is a
# transcription of it rather than a second opinion about DISP.001-003, and each
# function names the method it mirrors so a drift between the two is findable.
# Change one, change the other. Transcribed from d80bbe846.
#
# One difference remains and is deliberate: the validator is handed prims by the
# asset validator engine, while this walks ``Usd.Stage.Traverse()``. The two can
# disagree about instance prototypes and unloaded payloads.
# ----------------------------------------------------------------------------


DISPLAY_OPACITY = "displayOpacity"

# The types UsdGeomGprim declares for the two display primvars.
DISPLAY_COLOR_TYPE = Sdf.ValueTypeNames.Color3fArray
DISPLAY_OPACITY_TYPE = Sdf.ValueTypeNames.FloatArray


def authored_primvar(prim: Usd.Prim, name: str):
    """Mirrors ``DisplayColorCapabilityChecker._find_with_inheritance``.

    ``UsdGeomGprim`` declares both display primvars, so a primvar object exists
    whether or not anyone authored a value. The authored check is what separates
    the two, and it is what DISP.001 turns on.
    """
    primvar = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance(name)
    if not primvar or not primvar.GetAttr().HasAuthoredValue():
        return None
    return primvar


def resolved_values(primvar) -> tuple:
    """Mirrors ``._resolve``. Returns ``(values, time)``, or ``(None, None)``.

    The default time code is what a consumer reads for a static asset. Where a
    primvar carries only time samples nothing resolves there, and DISP.002 says
    conformance is then determined from the earliest authored sample, so that is
    what gets checked. Returning early instead would let such a primvar past the
    value rules entirely, and would contradict this script's own authoring path,
    which counts the same prim as already carrying a display colour.

    The time comes back with the values because the index array and the prim's
    topology have to be read at the same one. Comparing values from a sample
    against arrays resolved at the default time code compares arrays that never
    coexist.
    """
    time = Usd.TimeCode.Default()
    values = primvar.Get(time)
    if values is not None:
        return values, time
    if primvar.GetAttr().GetNumTimeSamples() == 0:
        return None, None
    time = Usd.TimeCode.EarliestTime()
    return primvar.Get(time), time


def authoring_path(primvar):
    """Mirrors ``._authoring_path``: the prim the value is authored on.

    Not always the prim being checked, because a constant primvar is inherited.
    """
    return primvar.GetAttr().GetPrim().GetPath()


def declared_type_problem(primvar, values, declared) -> Optional[str]:
    """Mirrors ``._check_value_type``. Returns the message, or None when the type is fine.

    Testing ``GetTypeName()`` for an array here would catch only half of what
    DISP.002 describes. On a Gprim the ``UsdGeomGprim`` schema declaration wins, so
    a scalar ``color3f primvars:displayColor`` authored straight onto a Mesh
    still reports ``color3f[]`` with ``isArray`` true while ``Get()`` hands back
    a ``Gf.Vec3f``. The resolved value is what a consumer sees, so the resolved
    value is what gets compared against the declared array type.
    """
    type_name = primvar.GetAttr().GetTypeName()
    array_class = type_name.arrayType.type.pythonClass if type_name else None
    if array_class is None:
        return None
    width = getattr(type_name.scalarType.type.pythonClass, "dimension", 1)
    expected_width = getattr(declared.scalarType.type.pythonClass, "dimension", 1)
    if isinstance(values, array_class) and width == expected_width:
        return None
    return (f"'{primvar.GetName()}' on '{authoring_path(primvar)}' resolves to "
            f"'{type(values).__name__}'; UsdGeomGprim declares it as '{declared}'")


def count_problems(prim: Usd.Prim, primvar, count: int, time, code: str) -> list:
    """Mirrors ``._check_element_count``.

    An indexed primvar holds one index per element the interpolation calls for,
    so the index array is what topology is compared against; its value array may
    be any length and only has to cover every index. Skipping indexed primvars
    outright, as an earlier version of this function did, dropped three of the
    conditions DISP.002 states: the constant count, the topology-implied count and
    the index range.

    ``time`` is the time code the values resolved at, and everything read here is
    read at the same one.
    """
    problems = []
    interpolation = primvar.GetInterpolation()
    authored_on = authoring_path(primvar)
    unit = "elements"

    # The indices attribute rather than ``GetIndices()``, which flattens "no
    # indices resolve here" and "an empty index array is authored here" into the
    # same empty array.
    indices = primvar.GetIndicesAttr().Get(time)
    if indices is not None:
        if any(index < 0 or index >= count for index in indices):
            problems.append(f"{prim.GetPath()}: '{primvar.GetName()}' on '{authored_on}' "
                            f"indexes outside its {count}-element value array ({code})")
        count = len(indices)
        unit = "indices"

    if interpolation == UsdGeom.Tokens.constant:
        if count != 1:
            problems.append(f"{prim.GetPath()}: '{primvar.GetName()}' on '{authored_on}' "
                            f"declares constant interpolation but authors {count} {unit}, "
                            f"expected 1 ({code})")
        return problems

    expected = expected_count(prim, interpolation, time)
    if expected is not None and count != expected:
        problems.append(f"{prim.GetPath()}: '{primvar.GetName()}' on '{authored_on}' declares "
                        f"{interpolation} interpolation and authors {count} {unit}, "
                        f"expected {expected} ({code})")
    return problems


def expected_count(prim: Usd.Prim, interpolation, time) -> Optional[int]:
    """Mirrors ``._expected_count``: the count the prim's topology implies, where knowable.

    ``vertex`` is one element per point on any point-based Gprim. ``uniform``,
    ``varying`` and ``faceVarying`` are read on meshes only: on
    ``UsdGeomBasisCurves`` they count curves and segment endpoints, which follow
    from the curve type, basis and wrap, so reading them as a mesh would report
    conforming curves as failures. Topology is read at ``time``, so a deforming
    mesh is compared against the points it carries alongside those values.
    """
    if interpolation == UsdGeom.Tokens.vertex:
        point_based = UsdGeom.PointBased(prim)
        if not point_based:
            return None
        points = point_based.GetPointsAttr().Get(time)
        return len(points) if points else None

    mesh = UsdGeom.Mesh(prim)
    if not mesh:
        return None
    if interpolation == UsdGeom.Tokens.uniform:
        counts = mesh.GetFaceVertexCountsAttr().Get(time)
        return len(counts) if counts else None
    if interpolation == UsdGeom.Tokens.varying:
        points = mesh.GetPointsAttr().Get(time)
        return len(points) if points else None
    if interpolation == UsdGeom.Tokens.faceVarying:
        indices = mesh.GetFaceVertexIndicesAttr().Get(time)
        return len(indices) if indices else None
    return None


def color_components(color) -> Optional[tuple]:
    """Mirrors ``._as_components``: the three components, or None if it is not a colour."""
    try:
        components = tuple(color)
    except TypeError:
        return None
    return components if len(components) == 3 else None


def as_scalar(value) -> Optional[float]:
    """Mirrors ``._as_scalar``: a float for a scalar element, or None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_finite(value) -> bool:
    """Mirrors ``._is_finite``."""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def display_color_problems(prim: Usd.Prim, primvar) -> list:
    """Mirrors ``._check_dc_002_display_color_values``."""
    problems = []
    values, time = resolved_values(primvar)
    if values is None:
        # Authored, but resolving to nothing at the default time code or at any
        # authored sample: a blocked value, for example. Nothing to count or
        # range-check, and the validator reports nothing here either.
        return problems
    type_problem = declared_type_problem(primvar, values, DISPLAY_COLOR_TYPE)
    if type_problem is not None:
        return [f"{prim.GetPath()}: {type_problem} (DISP.002)"]

    authored_on = authoring_path(primvar)
    for index, color in enumerate(values):
        components = color_components(color)
        if components is None:
            problems.append(f"{prim.GetPath()}: 'primvars:{DISPLAY_COLOR}' element {index} on "
                            f"'{authored_on}' is not a three-component colour (DISP.002)")
            continue
        for channel, component in zip("rgb", components):
            if not is_finite(component):
                problems.append(f"{prim.GetPath()}: 'primvars:{DISPLAY_COLOR}' element {index} "
                                f"has a non-finite {channel} component on '{authored_on}' "
                                f"(DISP.002)")
            elif not COMPONENT_MIN <= component <= COMPONENT_MAX:
                problems.append(f"{prim.GetPath()}: 'primvars:{DISPLAY_COLOR}' element {index} "
                                f"has {channel}={component} outside [0, 1] on '{authored_on}' "
                                f"(DISP.002)")

    problems.extend(count_problems(prim, primvar, len(values), time, "DISP.002"))
    return problems


def display_opacity_problems(prim: Usd.Prim, primvar) -> list:
    """Mirrors ``._check_dc_003_display_opacity_values``.

    This script never authors display opacity, so DISP.003 is nothing it can
    repair. It is reported anyway, because a preflight that says ``ok`` on an
    asset the capability validator fails is worse than no preflight.
    """
    problems = []
    values, time = resolved_values(primvar)
    if values is None:
        return problems
    type_problem = declared_type_problem(primvar, values, DISPLAY_OPACITY_TYPE)
    if type_problem is not None:
        return [f"{prim.GetPath()}: {type_problem} (DISP.003)"]

    authored_on = authoring_path(primvar)
    for index, opacity in enumerate(values):
        value = as_scalar(opacity)
        if value is None:
            problems.append(f"{prim.GetPath()}: 'primvars:{DISPLAY_OPACITY}' element {index} on "
                            f"'{authored_on}' is not a single float (DISP.003)")
        elif not math.isfinite(value):
            problems.append(f"{prim.GetPath()}: 'primvars:{DISPLAY_OPACITY}' element {index} is "
                            f"non-finite on '{authored_on}' (DISP.003)")
        elif not COMPONENT_MIN <= value <= COMPONENT_MAX:
            problems.append(f"{prim.GetPath()}: 'primvars:{DISPLAY_OPACITY}' element {index} is "
                            f"{value}, outside [0, 1] on '{authored_on}' (DISP.003)")

    problems.extend(count_problems(prim, primvar, len(values), time, "DISP.003"))
    return problems


def verify(stage: Usd.Stage) -> list:
    """Report DISP.001, DISP.002 and DISP.003 on every renderable Gprim of a stage."""
    problems = []
    for prim in renderable_gprims(stage):
        color = authored_primvar(prim, DISPLAY_COLOR)
        if color is None:
            problems.append(f"{prim.GetPath()}: GPrim '{prim.GetPath()}' does not resolve a "
                            f"'primvars:{DISPLAY_COLOR}', authored on the prim or inherited "
                            f"from an ancestor (DISP.001)")
        else:
            problems.extend(display_color_problems(prim, color))

        opacity = authored_primvar(prim, DISPLAY_OPACITY)
        if opacity is not None:
            problems.extend(display_opacity_problems(prim, opacity))
    return problems


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------


# Exit codes. A caller has to be able to tell "the assets have problems" from
# "the run itself failed", so they do not share a code. 2 is what argparse
# already uses for a usage error, so a bad invocation keeps it.
EXIT_OK = 0
EXIT_PROBLEMS = 1   # --verify found DISP.001-003 problems
EXIT_USAGE = 2      # bad arguments, or nothing to look at
EXIT_ERROR = 3      # at least one asset could not be read or raised


def usd_files(paths: Iterable[str]) -> list:
    found = []
    for path in paths:
        if os.path.isfile(path):
            found.append(path)
            continue
        for root, _dirs, files in os.walk(path):
            walked = root.replace(os.sep, "/").replace("\\", "/")
            if walked.rsplit("/", 1)[-1] != "simready_usd":
                continue
            if "/textures/" in f"{walked}/":
                continue
            for name in files:
                if name.endswith((".usd", ".usda", ".usdc")):
                    found.append(os.path.join(root, name))
    return sorted(set(found))


def display_label(path: str) -> str:
    """A short path to print, falling back to the absolute one.

    ``os.path.relpath`` raises ``ValueError`` when the asset and the working
    directory sit on different mounts, which happens whenever the script is run
    from a Windows drive against a ``\\\\wsl.localhost`` path or the reverse.
    The label is display only, so an absolute path is a fine substitute for it
    and much better than losing the run.
    """
    try:
        return os.path.relpath(path)
    except ValueError:
        return os.path.abspath(path)


def flush_pending(pending: dict, dry_run: bool) -> list:
    """Write the colours grouped by layer, opening each layer as its own stage.

    Authoring cannot happen on the composed stage: the prims are inside prototypes,
    and the edit target for each is a layer reached through a reference. Opening the
    layer directly gives its own root namespace, which is the namespace the paths
    collected in :func:`author_stage` are expressed in.
    """
    notes = []
    for identifier, entries in sorted(pending.items()):
        if dry_run:
            notes.append(f"  {identifier.rsplit('/', 1)[-1]}: {len(entries)} colour(s) (dry run)")
            continue
        layer_stage = Usd.Stage.Open(identifier)
        if layer_stage is None:
            notes.append(f"  {identifier}: cannot open to author into")
            continue
        written = 0
        for layer_path, color, source in entries:
            prim = layer_stage.GetPrimAtPath(layer_path)
            if not prim:
                notes.append(f"  {identifier.rsplit('/', 1)[-1]}{layer_path}: not in this layer")
                continue
            author(prim, color, source)
            written += 1
        layer_stage.GetRootLayer().Save()
        notes.append(f"  {identifier.rsplit('/', 1)[-1]}: {written} colour(s) authored")
    return notes


def author_stage(stage: Usd.Stage, sample_textures: bool = True,
                 dry_run: bool = False, edit_target: str = "stage") -> tuple:
    """Author the display colour on every renderable Gprim of an open stage.

    This is the derivation itself, with none of the file handling ``process``
    does around it: nothing is opened here and nothing is saved. ``process``
    calls it for a command-line run, and the ``FET_010_STANDARD`` feature
    adapter in
    ``nv_core/cip_specs/asset_handler_modules/neutral_to_display_color`` calls
    it for a run inside the SimReady adapter framework, so both paths author
    exactly the same value from the same derivation.

    Returns ``(authored, skipped, conflicts, per_material, notes)``.

    ``per_material`` maps a material name to the unnormalised accumulator
    ``[gprim_count, accumulated_weight, accumulated_colour]``, where
    ``accumulated_colour`` is each contributing colour multiplied by that
    contribution's world-space area and summed. It is not a colour: divide it
    by ``accumulated_weight`` to get the area-weighted colour, as ``main``
    does. It stays unnormalised so a caller running several assets can sum the
    entries across all of them and divide once at the end.
    """
    authored, skipped, conflicts, notes = 0, 0, 0, []
    per_material: dict = {}
    pending: dict = {}
    for prim in list(renderable_gprims(stage)):
        blocker = blocked_by(prim)
        if blocker is not None:
            conflicts += 1
            notes.append(f"  {prim.GetPath()}: CONFLICT, {blocker}, left alone")
            continue
        color, problems, contributions = derive_gprim(stage, prim, sample_textures)
        if color is None:
            skipped += 1
            reason = "; ".join(problems) or "no material to derive from"
            notes.append(f"  {prim.GetPath()}: SKIPPED, {reason}")
            continue
        source = "; ".join(f"{c.material}: {c.detail}" for c in contributions)
        if edit_target == "binding":
            target = binding_edit_target(prim)
            if target is None:
                skipped += 1
                notes.append(f"  {prim.GetPath()}: SKIPPED, no material:binding to place "
                             f"the display colour beside")
                continue
            layer, layer_path = target
            pending.setdefault(layer.identifier, []).append((layer_path, color, source))
            notes.append(f"  {prim.GetPath()}: {format_color(color)} "
                         f"-> {layer.identifier.rsplit('/', 1)[-1]}{layer_path}")
        else:
            if not dry_run:
                author(prim, color, source)
            notes.append(f"  {prim.GetPath()}: {format_color(color)}")
        authored += 1
        for contribution in contributions:
            notes.append(f"      {contribution.material} -> "
                         f"{format_color(contribution.color)}  {contribution.detail}")
            entry = per_material.setdefault(contribution.material, [0, 0.0, [0.0, 0.0, 0.0]])
            entry[0] += 1
            entry[1] += contribution.weight
            for i in range(3):
                entry[2][i] += float(contribution.color[i]) * contribution.weight
        for problem in problems:
            notes.append(f"      note: {problem}")

    if pending:
        notes.extend(flush_pending(pending, dry_run))

    return authored, skipped, conflicts, per_material, notes


def process(path: str, args) -> tuple:
    stage = Usd.Stage.Open(path)
    if stage is None:
        # Raised rather than returned as a note: an unreadable file is a failed
        # run, not a conformance finding, and the two must not share an exit code.
        raise RuntimeError("cannot open as a USD stage")

    if args.verify:
        return 0, 0, 0, {}, verify(stage)

    result = author_stage(stage, sample_textures=args.textures, dry_run=args.dry_run,
                          edit_target=getattr(args, "edit_target", "stage"))
    if result[0] and not args.dry_run:
        stage.GetRootLayer().Save()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="+", help="USD file(s) or directories to search")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--textures", dest="textures", action="store_true", default=True,
                        help="sample base colour maps over the bound faces (default)")
    parser.add_argument("--no-textures", dest="textures", action="store_false",
                        help="derive from material constants only, never sample a map")
    parser.add_argument(
        "--edit-target", choices=["stage", "binding"], default="stage",
        help="where to author the primvar: on the composed stage (default), or in the "
             "layer holding each Gprim's material:binding, which is what reaches geometry "
             "inside an instance",
    )
    parser.add_argument("--verify", action="store_true",
                        help="report DISP.001, DISP.002 and DISP.003, change nothing")
    args = parser.parse_args()

    # --verify never writes, so --dry-run cannot guard anything on top of it.
    # Accepting the pair silently would let a run look guarded when the guard was
    # doing nothing, so say which flag to drop instead of picking one.
    if args.verify and args.dry_run:
        parser.error("--dry-run has no meaning with --verify, which already changes nothing. "
                     "Use --verify to report conformance, or --dry-run to preview authoring.")

    if args.textures and not args.verify and (np is None or Image is None):
        missing = ", ".join(n for n, m in (("numpy", np), ("Pillow", Image)) if m is None)
        print(f"WARNING: {missing} not available, so base colour maps cannot be sampled. "
              f"A texture-driven material then contributes only the constant authored beside "
              f"its texture, which is usually the exporter's neutral default rather than the "
              f"colour the map shows. Where the material authors no such constant nothing can "
              f"be derived at all and the Gprim is skipped, so an asset whose materials are "
              f"all texture-driven gains no display colour. Install with: pip install numpy "
              f"pillow")
        args.textures = False

    targets = usd_files(args.paths)
    if not targets:
        print("No USD assets found.")
        return EXIT_USAGE

    total_authored, total_skipped, total_conflicts, total_problems = 0, 0, 0, 0
    fallbacks, unsampled, errors = 0, 0, 0
    materials: dict = {}
    for path in targets:
        label = display_label(path)
        try:
            authored, skipped, conflicts, per_material, notes = process(path, args)
        except Exception:  # noqa: BLE001 - one unreadable asset must not end the walk
            errors += 1
            print(f"ERROR {label}: could not be processed, traceback on stderr")
            print(f"--- {label}", file=sys.stderr)
            traceback.print_exc()
            continue
        if args.verify:
            if notes:
                total_problems += len(notes)
                print(f"FAIL {label}")
                for note in notes:
                    print(f"  {note}")
            else:
                print(f"ok   {label}")
            continue
        total_authored += authored
        total_skipped += skipped
        total_conflicts += conflicts
        # Counted off the notes the derivation emits, using the same two phrases
        # it writes them with, so the closing summary cannot claim a fallback
        # that never happened.
        fallbacks += sum(note.count(FALLBACK_NOTE) for note in notes)
        unsampled += sum(note.count(UNSAMPLED_NOTE) for note in notes)
        print(f"{label}: {authored} authored, {skipped} skipped"
              f"{f', {conflicts} conflict(s)' if conflicts else ''}"
              f"{' (dry run)' if args.dry_run else ''}")
        for note in notes:
            print(note)
        # Material names repeat across assets, so the rollup is keyed by the
        # asset folder as well: props_general/<asset>/simready_usd/<file>.usd.
        asset = os.path.basename(os.path.dirname(os.path.dirname(path))) or "."
        for name, (count, weight, accumulated) in per_material.items():
            entry = materials.setdefault(f"{asset}/{name}", [0, 0.0, [0.0, 0.0, 0.0]])
            entry[0] += count
            entry[1] += weight
            for i in range(3):
                entry[2][i] += accumulated[i]

    if args.verify:
        checked = len(targets) - errors
        print(f"\n{total_problems} problem(s) across {checked} asset(s) checked"
              f"{f', {errors} could not be read' if errors else ''}")
        if errors:
            return EXIT_ERROR
        return EXIT_PROBLEMS if total_problems else EXIT_OK

    if materials:
        print("\nPer-material area-weighted colour:")
        for name in sorted(materials):
            count, weight, accumulated = materials[name]
            mean = [component / weight for component in accumulated] if weight else [0, 0, 0]
            print(f"  {name}: {format_color(mean)} across {count} Gprim(s)")

    print(f"\n{total_authored} Gprim(s) given a display colour across {len(targets)} asset(s)")
    if total_skipped:
        print(f"{total_skipped} renderable Gprim(s) skipped: nothing to derive a colour from. "
              f"They are listed as SKIPPED above and still fail DISP.001. No colour was "
              f"invented for them.")
    if total_conflicts:
        print(f"{total_conflicts} Gprim(s) left alone: they already resolve a display colour "
              f"this script did not author, listed as CONFLICT above.")
    if not args.textures:
        print("Base colour maps were not sampled.")
        if fallbacks:
            print(f"  {fallbacks} texture-driven material contribution(s) used the constant "
                  f"authored beside the texture, which is usually the exporter's neutral "
                  f"default rather than the colour the map shows.")
        if unsampled:
            print(f"  {unsampled} texture-driven material contribution(s) had no constant "
                  f"beside the texture, so nothing could be derived from them. The Gprims "
                  f"they cover are listed as SKIPPED above and still fail DISP.001.")
        print("  Re-run without --no-textures to sample the maps.")
    if errors:
        print(f"\n{errors} asset(s) could not be processed, listed as ERROR above.")
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
