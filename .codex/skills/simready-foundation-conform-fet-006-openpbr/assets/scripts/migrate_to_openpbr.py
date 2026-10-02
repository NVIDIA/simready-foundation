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
"""Author an OpenPBR surface onto SimReady sample materials.

Adds the ``FET_006_OPENPBR`` contract to assets that currently carry only a
UsdPreviewSurface preview and an OmniPBR (MDL) final surface: an OpenPBR
surface connected to ``outputs:mtlx:surface``, with parameters derived from the
existing material and held inside the ranges VM.PBR.002 defines.

Textures are carried across, not flattened. Where the source drives a channel
from a texture, the migration authors the MaterialX reader nodes that sample it
and wires them into the OpenPBR surface. The topology follows NVIDIA's
PhysicalAI SimReady materials library (``open_pbr_uber_base_class.usda``):
``ND_tiledimage_*`` readers fed by a shared ``ND_texcoord_vector2``, packed
textures split with ``ND_separate3_vector3``, normal maps decoded through
``ND_normalmap``.

Every parameter is exposed as an interface input on the ``Material`` prim and
read by the shader through that input, so a consumer can retune a material
without reaching into its shader network. Unlike the reference library, the
materials this script writes are self-contained: it authors no ``inherits`` or
``specializes`` arc, so each material carries its own network.

The script is safe to re-run. It owns one prim per material, ``OpenPBR_Shader``,
plus the reader nodes named ``OpenPBR_Shader_*`` beside it, and rewrites all of
them from scratch on every pass: whatever the previous run left is removed
before the fresh derivation is authored, so a re-run leaves exactly what the
current derivation produces and never duplicates a texture node. An asset can
therefore be re-migrated after someone else has edited it.

A material that already carries an OpenPBR surface under a different prim name
was authored by hand, so the script leaves that material alone rather than
adding a second, competing surface. Those materials are reported at the end of
the run.

Usage::

    python migrate_to_openpbr.py <path>... [--dry-run] [--no-textures] [--verify]

``<path>`` may be a USD file or a directory, which is searched for
``simready_usd`` assets. Run ``--verify`` on its own to report conformance
without editing anything.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import sys
from typing import Iterable, Optional

try:
    from pxr import Gf, Sdf, Usd, UsdShade
except ImportError:  # pragma: no cover - environment guard
    sys.exit("USD Python is required. Install with: pip install usd-core")

# The OpenPBR surface nodedef. VM.PBR.001 requires this on outputs:mtlx:surface.
OPENPBR_SURFACE_ID = "ND_open_pbr_surface_surfaceshader"
# The single output that nodedef declares: <output name="out" type="surfaceshader"/>.
# This is the name to author: all 904 OpenPBR materials in NVIDIA's shipped library
# use it. The name is not load-bearing at render time, though. Hydra derives the
# MaterialX terminal from the nodedef's type rather than the USD property name
# (HdMtlxGetMxTerminalName in hdMtlx.cpp), and USD's own usdMtlx reader normalises
# the other way, writing outputs:surface, which is what Blender's exporter produces.
# Both names render. Do not add a gate that rejects one of them.
OPENPBR_SURFACE_OUTPUT = "out"

# MaterialX stdlib nodes used to sample and unpack textures. These are the nodes
# NVIDIA's own OpenPBR materials use, so a runtime that resolves theirs resolves ours.
TEXCOORD_ID = "ND_texcoord_vector2"
TILEDIMAGE_IDS = {
    "color3": "ND_tiledimage_color3",
    "float": "ND_tiledimage_float",
    "vector3": "ND_tiledimage_vector3",
    "vector4": "ND_tiledimage_vector4",
}
SEPARATE_IDS = {"vector3": "ND_separate3_vector3", "vector4": "ND_separate4_vector4"}
# The reference library writes "ND_normalmap", which is the MaterialX 1.38 name. 1.39
# split that nodedef by the type of its scale input, and the plain name resolves in
# neither the 1.39 stdlib nor the library Kit ships. Our scale is a float, so this is
# the 1.39 id for the same node; writing the old name would leave the normal
# unresolvable, which renders as a flat surface rather than failing loudly.
NORMALMAP_ID = "ND_normalmap_float"

# Prim name for the surface this script authors. Fixed, so re-runs update in place
# and an OpenPBR surface under any other name is recognised as someone else's work.
OPENPBR_PRIM = "OpenPBR_Shader"
# Every node this script adds beside the surface is named OpenPBR_Shader_<something>,
# which is how a re-run tells its own nodes apart from anything else under the material.
NODE_PREFIX = f"{OPENPBR_PRIM}_"

# VM.PBR.002 bounds.
IOR_MIN, IOR_MAX = 1.0, 3.0

# Inputs this script authors, and how each is bounded. Names match the OpenPBR
# surface nodedef; the bounds match the requirement page.
UNIT_FLOATS = {"base_metalness", "specular_roughness", "geometry_opacity", "transmission_weight",
               "coat_weight", "coat_roughness", "coat_darkening"}
IOR_FLOATS = {"specular_ior", "coat_ior"}
NON_NEGATIVE_FLOATS = {"emission_luminance"}
UNIT_COLORS = {"base_color", "emission_color", "coat_color", "transmission_color"}

# Every input name this script is allowed to author, and so the only names a
# re-run is allowed to remove. An input outside this set came from somewhere else
# and is left where it is.
# geometry_thin_walled is a boolean, so it has no range to hold it inside; it is listed
# separately so a re-run still knows the input is one this script owns.
BOOLEANS = {"geometry_thin_walled"}

AUTHORED_INPUTS = UNIT_FLOATS | IOR_FLOATS | NON_NEGATIVE_FLOATS | UNIT_COLORS | BOOLEANS

# geometry_normal only ever arrives as a texture, so it carries no constant and is
# not bounded, but it is still an input this script owns.
NORMAL_INPUT = "geometry_normal"
TEXTURE_TARGETS = AUTHORED_INPUTS | {NORMAL_INPUT}

# Interface inputs on the Material prim that hold the texture wiring itself rather
# than a shader parameter. Owned by this script, so cleared on a re-run.
UV_INPUTS = {"uvtiling", "uvoffset"}
NORMAL_SCALE_INPUT = "geometry_normal_scale"

# The OpenPBR nodedef defaults. Used when the source material drives an input from a
# texture and offers no constant, so the interface input the consumer sees still holds
# a sensible value and the reader node has something to fall back on.
OPENPBR_DEFAULTS = {
    "base_color": Gf.Vec3f(0.8, 0.8, 0.8),
    "base_metalness": 0.0,
    "specular_roughness": 0.3,
    "specular_ior": 1.5,
    "geometry_opacity": 1.0,
    "emission_color": Gf.Vec3f(1.0, 1.0, 1.0),
    "emission_luminance": 0.0,
    "transmission_weight": 0.0,
    "transmission_color": Gf.Vec3f(1.0, 1.0, 1.0),
    "coat_weight": 0.0,
    "coat_roughness": 0.1,
    "coat_color": Gf.Vec3f(1.0, 1.0, 1.0),
    "coat_ior": 1.6,
}

# Colour space per texture role, following the reference library: only the colour
# channels are sRGB, and every data channel (roughness, metalness, normal, opacity)
# is raw. Source assets sometimes mislabel an ORM or normal map as sRGB; decoding
# those as colour would skew the values, so the role decides rather than the source.
SRGB_TARGETS = UNIT_COLORS
COLORSPACE_SRGB = "srgb_texture"
COLORSPACE_RAW = "none"

# Channel name on a UsdUVTexture output -> index into the sampled vector.
CHANNEL_INDEX = {"r": 0, "g": 1, "b": 2, "a": 3}
SEPARATE_OUTPUTS = ("outx", "outy", "outz", "outw")


class TexRef:
    """A texture feeding one OpenPBR input: the file, and which channel to read."""

    def __init__(self, path: str, channel: str = "rgb"):
        self.path = path
        # "rgb" means take the whole colour; "r"/"g"/"b"/"a" means unpack one channel.
        self.channel = channel

    @property
    def packed(self) -> bool:
        return self.channel in CHANNEL_INDEX

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{os.path.basename(self.path)}[{self.channel}]"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def as_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_rgb(value) -> Optional[tuple]:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError, IndexError):
        return None


def bound(name: str, value):
    """Hold a value inside the range VM.PBR.002 defines for that input."""
    if name in UNIT_FLOATS:
        number = as_float(value)
        return None if number is None else clamp(number, 0.0, 1.0)
    if name in IOR_FLOATS:
        number = as_float(value)
        return None if number is None else clamp(number, IOR_MIN, IOR_MAX)
    if name in NON_NEGATIVE_FLOATS:
        number = as_float(value)
        return None if number is None else max(0.0, number)
    if name in UNIT_COLORS:
        rgb = as_rgb(value)
        return None if rgb is None else Gf.Vec3f(*[clamp(c, 0.0, 1.0) for c in rgb])
    return value


def slug(text: str) -> str:
    """A prim-name-safe token derived from a texture file name."""
    stem = os.path.basename(text).rsplit(".", 1)[0]
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", stem).strip("_")
    return cleaned or "texture"


def find_shader(material: Usd.Prim, predicate) -> Optional[UsdShade.Shader]:
    for child in material.GetChildren():
        if child.GetTypeName() != "Shader":
            continue
        shader = UsdShade.Shader(child)
        if predicate(child, shader):
            return shader
    return None


def preview_shader(material: Usd.Prim) -> Optional[UsdShade.Shader]:
    return find_shader(
        material,
        lambda prim, sh: (sh.GetIdAttr().Get() if sh.GetIdAttr() else None) == "UsdPreviewSurface",
    )


def omnipbr_shader(material: Usd.Prim) -> Optional[UsdShade.Shader]:
    def is_omnipbr(prim, shader):
        if prim.GetName() == OPENPBR_PRIM:
            return False
        attr = prim.GetAttribute("info:mdl:sourceAsset:subIdentifier")
        return bool(attr and attr.Get())

    return find_shader(material, is_omnipbr)


def mdl_model(shader: Optional[UsdShade.Shader]) -> Optional[str]:
    """Which MDL model a shader is built on, or None if this script does not know it.

    Keyed on ``info:mdl:sourceAsset:subIdentifier`` so the answer comes from what the
    shader declares rather than from the module path, which varies by deployment.
    """
    if shader is None or not shader:
        return None
    attr = shader.GetPrim().GetAttribute("info:mdl:sourceAsset:subIdentifier")
    name = str(attr.Get() if attr else "").strip().lower()
    return MDL_MODELS.get(name)


def unknown_mdl_model(material: Usd.Prim) -> Optional[str]:
    """The subIdentifier of an MDL shader this script cannot read, or None.

    None covers both a material with no MDL shader, which migrates from its
    UsdPreviewSurface alone, and one whose model is in :data:`MDL_MODELS`.
    """
    shader = omnipbr_shader(material)
    if shader is None or mdl_model(shader) is not None:
        return None
    attr = shader.GetPrim().GetAttribute("info:mdl:sourceAsset:subIdentifier")
    return str(attr.Get() if attr else "") or "<unnamed>"


def shader_id(shader: Optional[UsdShade.Shader]) -> Optional[str]:
    if shader is None or not shader:
        return None
    id_attr = shader.GetIdAttr()
    return id_attr.Get() if id_attr else None


def owned_openpbr(material: Usd.Prim) -> Optional[UsdShade.Shader]:
    """Return the OpenPBR surface this script authored, if it is already there.

    Matched on the fixed prim name as well as the nodedef, so the only surface a
    re-run ever rewrites is the one it created itself.
    """
    child = material.GetChild(OPENPBR_PRIM)
    if not child or child.GetTypeName() != "Shader":
        return None
    shader = UsdShade.Shader(child)
    return shader if shader_id(shader) == OPENPBR_SURFACE_ID else None


def foreign_openpbr(material: Usd.Prim) -> Optional[UsdShade.Shader]:
    """Return an OpenPBR surface authored under a name this script does not own.

    Someone put it there by hand, so the material it belongs to is left alone
    rather than given a second, competing surface.
    """
    for child in material.GetChildren():
        if child.GetTypeName() != "Shader" or child.GetName() == OPENPBR_PRIM:
            continue
        shader = UsdShade.Shader(child)
        if shader_id(shader) == OPENPBR_SURFACE_ID:
            return shader
    return None


def connected_mtlx_surface(material: UsdShade.Material) -> tuple:
    """Return the shader and output name ``outputs:mtlx:surface`` resolves to.

    Only the shader half decides conformance. The output name is returned for
    diagnostics; it is not checked, because either spelling renders.
    """
    out = material.GetSurfaceOutput("mtlx")
    if not out or not out.HasConnectedSource():
        return None, None
    source = out.GetConnectedSource()
    if not source:
        return None, None
    source_prim = source[0].GetPrim()
    if not source_prim or source_prim.GetTypeName() != "Shader":
        return None, None
    return UsdShade.Shader(source_prim), source[1]


def constant_input(shader: Optional[UsdShade.Shader], name: str):
    """Return an input's authored constant, or None when absent or connected."""
    if shader is None:
        return None
    shader_input = shader.GetInput(name)
    if not shader_input or shader_input.HasConnectedSource():
        return None
    return shader_input.Get()


def asset_path(value) -> Optional[str]:
    """The path out of an Sdf.AssetPath, or None when it is empty."""
    path = getattr(value, "path", None)
    return path or None


def texture_for(shader: Optional[UsdShade.Shader], name: str) -> Optional[TexRef]:
    """Return the texture feeding an input through a UsdUVTexture, if any.

    The output name the connection arrives through carries which channel the
    source reads: ``outputs:rgb`` for a colour, ``outputs:g`` for the roughness
    channel of a packed ORM map. Dropping that name is what flattened packed
    textures on earlier runs, so it is kept.
    """
    if shader is None:
        return None
    shader_input = shader.GetInput(name)
    if not shader_input or not shader_input.HasConnectedSource():
        return None
    source = shader_input.GetConnectedSource()
    if not source:
        return None
    source_prim, output_name = source[0].GetPrim(), source[1]
    # Walk through any pass-through node that does not itself hold the file, so a
    # texture reached via a placement node is still found.
    for _hop in range(4):
        if source_prim is None or not source_prim:
            return None
        file_attr = source_prim.GetAttribute("inputs:file")
        if file_attr and asset_path(file_attr.Get()):
            return TexRef(asset_path(file_attr.Get()), str(output_name))
        upstream = UsdShade.Shader(source_prim).GetInput("in")
        if not upstream or not upstream.HasConnectedSource():
            return None
        hop = upstream.GetConnectedSource()
        if not hop:
            return None
        source_prim = hop[0].GetPrim()
    return None


# OmniPBR and OmniGlass spell two of the same maps differently. A shader authors one
# name out of each pair and never both, so trying both is unambiguous, and it is what
# keeps an OmniGlass source from losing its albedo and normal maps.
# Every MDL model this script knows how to read, keyed by
# ``info:mdl:sourceAsset:subIdentifier`` in lower case.
#
# Migration matches source inputs by name, and different models spell the same name
# with different meaning. SimPBR authors ``emissive_color`` and ``emissive_intensity``
# on every material and gates them behind ``enable_emission``; OmniPBR has no such
# gate and authors them only where the material emits. Read one model through
# another's table and the result is a surface that looks right and is not, so a model
# that is not named here is left alone rather than migrated on a name collision.
MDL_OMNIPBR = "omnipbr"
MDL_OMNIGLASS = "omniglass"
MDL_SIMPBR = "simpbr"
MDL_SIMPBR_TRANSLUCENT = "simpbr_translucent"

MDL_MODELS = {
    "omnipbr": MDL_OMNIPBR,
    "omniglass": MDL_OMNIGLASS,
    "simpbr": MDL_SIMPBR,
    "simpbr_translucent": MDL_SIMPBR_TRANSLUCENT,
}

# (OpenPBR input, UsdPreviewSurface input, MDL input) for each model. A None in the
# preview column means the channel has no UsdPreviewSurface equivalent to fall back on.
MDL_MAPPINGS = {
    MDL_OMNIPBR: [
        ("base_color", "diffuseColor", "diffuse_color_constant"),
        ("base_metalness", "metallic", "metallic_constant"),
        ("specular_roughness", "roughness", "reflection_roughness_constant"),
        ("specular_ior", "ior", None),
        ("geometry_opacity", "opacity", "opacity_constant"),
        ("emission_color", "emissiveColor", "emissive_color"),
    ],
    MDL_OMNIGLASS: [
        ("base_color", "diffuseColor", "glass_color"),
        ("specular_roughness", "roughness", "frosting_roughness"),
        ("specular_ior", "ior", "glass_ior"),
        ("geometry_opacity", "opacity", "cutout_opacity"),
    ],
    # SimPBR spells albedo, metalness and roughness as OmniPBR does. It has no plain
    # index of refraction -- ``clearcoat_ior`` describes the coat, not the base -- so
    # specular_ior takes the UsdPreviewSurface value or the nodedef default.
    MDL_SIMPBR: [
        ("base_color", "diffuseColor", "diffuse_color_constant"),
        ("base_metalness", "metallic", "metallic_constant"),
        ("specular_roughness", "roughness", "reflection_roughness_constant"),
        ("specular_ior", "ior", None),
        ("geometry_opacity", "opacity", "alpha_constant"),
        ("emission_color", "emissiveColor", "emissive_color"),
        ("coat_weight", None, "clearcoat_weight"),
        ("coat_roughness", None, "clearcoat_reflection_roughness"),
        ("coat_color", None, "clearcoat_tint"),
        ("coat_ior", None, "clearcoat_ior"),
    ],
    # SimPBR_Translucent describes transmission instead of an albedo, so it maps no
    # base_color: ``transmittance_color`` is what light picks up passing through, not
    # what the surface reflects.
    MDL_SIMPBR_TRANSLUCENT: [
        ("specular_roughness", "roughness", "reflection_roughness_constant"),
        ("specular_ior", "ior", "ior_constant"),
        ("emission_color", "emissiveColor", "emissive_color"),
        # What light picks up passing through. Without it a red glass migrates clear:
        # transmission_weight alone says light gets through, not what colour it comes out.
        ("transmission_color", None, "transmittance_color"),
        ("geometry_thin_walled", None, "enable_thin_walled"),
    ],
}

# SimPBR authors these whether or not the material uses them and gates each behind a
# boolean. Where the gate is authored false the value beside it is inert, and carrying
# it across turns a matte surface emissive or a solid one cut out.
MDL_GATES = {
    MDL_SIMPBR: {
        "emission_color": "enable_emission",
        "emission_luminance": "enable_emission",
        "geometry_opacity": "enable_opacity",
        "coat_weight": "enable_clearcoat",
        "coat_roughness": "enable_clearcoat",
        "coat_color": "enable_clearcoat",
        "coat_ior": "enable_clearcoat",
    },
    MDL_SIMPBR_TRANSLUCENT: {
        "emission_color": "enable_emission",
        "emission_luminance": "enable_emission",
    },
}

# Models whose surface transmits. OpenPBR renders opaque without this whatever else
# it carries, so the migrated material would not read as glass.
MDL_TRANSMISSIVE = frozenset({MDL_OMNIGLASS, MDL_SIMPBR_TRANSLUCENT})

BASE_COLOR_TEXTURES = ("diffuse_texture", "glass_color_texture")
NORMAL_TEXTURES = ("normalmap_texture", "normal_map_texture")
# The packed map is spelled the same on both, so it needs no pair.
ORM_TEXTURE = "ORM_texture"


def omni_texture(shader: Optional[UsdShade.Shader], names,
                 channel: str = "rgb") -> Optional[TexRef]:
    """Return an MDL shader's texture-valued input as a TexRef.

    ``names`` is one input name or several alternatives, which is how the OmniPBR
    and OmniGlass spellings of the same map are both found.
    """
    for name in (names,) if isinstance(names, str) else names:
        path = asset_path(constant_input(shader, name))
        if path:
            return TexRef(path, channel)
    return None


def derive(material: Usd.Prim, wire_textures: bool = True) -> tuple[dict, dict, list]:
    """Map the existing material onto OpenPBR inputs.

    Returns the constant values to author, the textures that fed the source, and
    notes describing anything that could not be carried across.

    ``wire_textures`` decides what a texture-driven channel becomes. Wired, the
    texture is the value and no constant is derived for it, because the reader
    node carries one as its fallback. Flattened, there is no reader to hold that
    fallback, so the constant has to be derived here instead: the channel takes
    whatever constant the source carries beside the map, and the OpenPBR nodedef
    default when it carries none. Deriving nothing left the input unauthored,
    which is not what ``--no-textures`` says it does.
    """
    preview = preview_shader(material)
    omni = omnipbr_shader(material)
    values, textures, notes = {}, {}, []

    # Each MDL model spells its inputs differently and describes a different surface,
    # so the mapping is chosen by model. A material with no MDL shader at all migrates
    # from its UsdPreviewSurface alone, which is what the OmniPBR table describes.
    model = mdl_model(omni)
    if omni is not None and model is None:
        return {}, {}, notes
    mapping = MDL_MAPPINGS[model or MDL_OMNIPBR]
    gates = MDL_GATES.get(model, {})

    def gated_out(target: str) -> bool:
        """True where the source authors this input but its model gates it off."""
        gate = gates.get(target)
        if gate is None:
            return False
        return constant_input(omni, gate) is False

    for target, preview_name, omni_name in mapping:
        # A texture wins over a constant of the same name, so it is resolved first.
        # Where one shader carries both, the constant is the neutral default the
        # exporter wrote beside the map it actually sampled: OmniPBR declares
        # diffuse_color_constant ("Albedo Color") beside diffuse_texture ("Albedo
        # Map"), and its metallic_texture_influence / reflection_roughness_texture_influence
        # inputs exist to blend one against the other. Reading the constant first
        # flattened the map and reported nothing, so the order below is load-bearing.
        if gated_out(target):
            notes.append(f"{target} not migrated: {gates[target]} is false on the source")
            continue
        texture = texture_for(preview, preview_name) if preview_name else None
        if texture is None and omni is not None:
            texture = omni_source_texture(omni, target)
        if texture is not None:
            textures[target] = texture
            notes.append(f"{target} <- {texture.path.rsplit('/', 1)[-1]} ({texture.channel})")
            if wire_textures:
                continue
            # Flattening: fall through to the constant, which is the whole point of
            # --no-textures. Skipping to the next channel here left the input on
            # neither the shader nor the Material, so the flag dropped the channel
            # rather than holding it at a value.
        # Neither source drives this channel from a texture, so take a constant.
        if model in MDL_TRANSMISSIVE and omni_name:
            # The transmissive shader holds the authored intent; the preview surface
            # usually holds a generic default such as ior 1.5.
            value = constant_input(omni, omni_name)
            if value is None and preview_name:
                value = constant_input(preview, preview_name)
        else:
            value = constant_input(preview, preview_name) if preview_name else None
            if value is None and omni_name:
                value = constant_input(omni, omni_name)
        if value is None and target in textures:
            # Only reachable when flattening, since the wired path never gets here
            # with a texture recorded. The source drives this channel from a map and
            # carries no constant beside it, so the nodedef default is the only value
            # left. Authoring it keeps the channel retunable on the Material prim
            # instead of absent, and it is what the surface would have rendered anyway.
            value = OPENPBR_DEFAULTS.get(target)
        if value is not None:
            held = bound(target, value)
            if held is not None:
                values[target] = held

    # The normal map is texture-only: there is no constant that stands in for it,
    # and it appears in neither mapping list, so it is resolved on its own here.
    # Routed through omni_source_texture so the MDL name table has one home.
    normal = texture_for(preview, "normal")
    if normal is None and omni is not None:
        normal = omni_source_texture(omni, NORMAL_INPUT)
    if normal:
        textures[NORMAL_INPUT] = normal
        notes.append(f"{NORMAL_INPUT} <- {normal.path.rsplit('/', 1)[-1]} ({normal.channel})")

    # SimPBR multiplies the albedo by a tint before it reaches the surface:
    #   base_color = multiply_colors(diffuse_color, diffuse_tint, 1.0).tint
    # in SimPBR_Model.mdl. Carrying the albedo across without it authors a material as
    # bright as the tint is dark -- a 0.5 tint arrives twice as light as it renders.
    if model in (MDL_SIMPBR, MDL_SIMPBR_TRANSLUCENT):
        tint = as_rgb(constant_input(omni, "diffuse_tint"))
        if tint is not None and any(abs(c - 1.0) > 1e-6 for c in tint):
            if "base_color" in values:
                base = as_rgb(values["base_color"])
                if base is not None:
                    held = bound("base_color", Gf.Vec3f(*[b * t for b, t in zip(base, tint)]))
                    if held is not None:
                        values["base_color"] = held
                        notes.append(f"base_color multiplied by diffuse_tint "
                                     f"({', '.join(f'{c:.3f}' for c in tint)})")
            elif "base_color" in textures:
                # The albedo comes from a map, so the tint would need a multiply node
                # between the reader and the surface. Naming it beats dropping it quietly.
                notes.append("diffuse_tint not applied: base_color is texture-driven and "
                             "the tint would need a multiply node")

    # OpenPBR darkens what sits under a coat, modelling the light that reflects back
    # internally: coat_darkening defaults to 1.0. SimPBR's coat does not -- it is a
    # fresnel_layer over a base that is only tinted, and with a white clearcoat_tint the
    # base is untouched (SimPBR_Model.mdl, opt_omni_PBR_coated_bsdf). Carrying the coat
    # across without saying so renders the base darker than the source does, which is
    # most visible on a dark metallic under a full-weight coat.
    if values.get("coat_weight"):
        held = bound("coat_darkening", 0.0)
        if held is not None:
            values["coat_darkening"] = held
            notes.append("coat_darkening set to 0: SimPBR's coat does not darken its base")

    if model in MDL_TRANSMISSIVE:
        # A transmissive material lets light through. Without this the OpenPBR surface
        # is opaque whatever else it holds, so the migrated asset would not read as glass.
        values["transmission_weight"] = 1.0
        values.setdefault("base_metalness", 0.0)
        notes.append(f"{model} source: transmission_weight set to 1.0")

    # Emission intensity is spelled the same across these models, and gated on SimPBR.
    if not gated_out("emission_luminance"):
        intensity = constant_input(omni, "emissive_intensity")
        number = as_float(intensity)
        if number is not None and number > 0:
            held = bound("emission_luminance", number)
            if held is not None:
                values["emission_luminance"] = held

    return values, textures, notes


def omni_source_texture(omni: UsdShade.Shader, target: str) -> Optional[TexRef]:
    """Find an MDL texture for an OpenPBR input.

    The one place that knows how the MDL surfaces name their maps, so the two
    callers in :func:`derive` cannot drift apart. OmniPBR packs occlusion,
    roughness and metalness into one ORM map and reads the green and blue
    channels, which is the convention this unpacks. OmniGlass packs its ORM the
    same way but spells the albedo and normal maps differently.
    """
    if target == "base_color":
        return omni_texture(omni, BASE_COLOR_TEXTURES)
    if target == NORMAL_INPUT:
        return omni_texture(omni, NORMAL_TEXTURES)
    if target in ("specular_roughness", "base_metalness"):
        enabled = constant_input(omni, "enable_ORM_texture")
        if not enabled:
            return None
        channel = "g" if target == "specular_roughness" else "b"
        return omni_texture(omni, ORM_TEXTURE, channel)
    return None


def colorspace_for(target: str) -> str:
    return COLORSPACE_SRGB if target in SRGB_TARGETS else COLORSPACE_RAW


def _same_value(a, b, tol: float = 1e-6) -> bool:
    """Compare two authored values, tolerating float round-trip through the crate."""
    fa, fb = as_float(a), as_float(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= tol
    ra, rb = as_rgb(a), as_rgb(b)
    if ra is not None and rb is not None:
        return all(abs(x - y) <= tol for x, y in zip(ra, rb))
    return a == b


def already_authored(material_prim: Usd.Prim, values: dict, textures: dict,
                     wire_textures: bool) -> bool:
    """True where the surface on this material is already what this run would author.

    Re-running is semantically idempotent -- the same derivation produces the same
    surface -- but it rewrites the layer either way, and on a shared material library
    that means touching files that did not change. Comparing first keeps a re-run
    silent on everything it has already done.

    Read from the shader rather than the Material: a constant reaches the shader
    through the Material's interface input, and a texture reaches it through a reader
    node, so which of the two a channel uses is only visible by following the
    connection back to its source.
    """
    shader = owned_openpbr(material_prim)
    if shader is None:
        return False

    have_constant, have_connected = {}, set()
    for shader_input in shader.GetInputs():
        name = shader_input.GetBaseName()
        source = shader_input.GetConnectedSource()
        if source is None:
            current = shader_input.Get()
            if current is not None:
                have_constant[name] = current
            continue
        source_prim = source[0].GetPrim()
        if source_prim == material_prim:
            # Routed through the Material's interface input, which holds the constant.
            interface = UsdShade.Material(material_prim).GetInput(name)
            current = interface.Get() if interface else None
            if current is not None:
                have_constant[name] = current
        else:
            have_connected.add(name)

    if have_connected != (set(textures) if wire_textures else set()):
        return False
    if set(have_constant) != set(values):
        return False
    return all(_same_value(have_constant[name], value) for name, value in values.items())


# The MDL inputs the derivation reads, strongest-opinion-first, used to find the layer
# this material's own values are authored in.
OPINION_INPUTS = (
    "diffuse_color_constant", "metallic_constant", "reflection_roughness_constant",
    "emissive_color", "transmittance_color", "clearcoat_weight", "diffuse_tint",
)


def material_source_prim(material_prim: Usd.Prim):
    return material_prim.GetPrimInPrototype() if material_prim.IsInstanceProxy() else material_prim


def opinion_target(material_prim: Usd.Prim):
    """The layer and material path holding this material's own input values.

    Not the weakest ``def``. A material that specialises a shared library base has its
    own values in a stronger layer, and the weakest def is the base itself -- shared with
    every other material that specialises from it. Writing there stamps one material's
    derived surface onto all of them: the Audi's WheelRim reads 0.15 through a variant and
    the base it specialises reads 0.5, and targeting the base gave every rim the dark
    variant's colour.

    So the target is the strongest authored opinion on the inputs the derivation actually
    read. That is the layer this material's identity lives in.
    """
    source = material_source_prim(material_prim)
    if not source:
        return None
    shader = None
    for child in source.GetChildren():
        attr = child.GetAttribute("info:mdl:sourceAsset:subIdentifier")
        if attr and attr.Get():
            shader = child
            break
    if shader is not None:
        for name in OPINION_INPUTS:
            attr = shader.GetAttribute(f"inputs:{name}")
            if not (attr and attr.IsValid()):
                continue
            stack = attr.GetPropertyStack(Usd.TimeCode.Default())
            if not stack:
                continue
            spec = stack[0]
            # .../Looks/<Material>/<Shader>.inputs:<name> -> the Material prim path,
            # with any variant selectors stripped so the path is addressable on a stage.
            # .../Looks/<Material>/<Shader>.inputs:<name> -> the Material prim path. The
            # path keeps its variant selectors: a material that is specialised inside a
            # variant has its values there, and authoring outside the variant would give
            # every other variant this one's surface.
            material_path = spec.path.GetPrimPath().GetParentPath()
            return spec.layer, material_path
    # No MDL inputs to go on, so fall back to where the material is defined.
    defs = [spec for spec in source.GetPrimStack() if spec.specifier == Sdf.SpecifierDef]
    stack = defs or source.GetPrimStack()
    if not stack:
        return None
    return stack[0].layer, stack[0].path.StripAllVariantSelections()


def defining_layer(material_prim: Usd.Prim):
    """The layer this material's own values are authored in."""
    target = opinion_target(material_prim)
    return target[0] if target else None


def is_outside_asset(material_prim: Usd.Prim, asset_dir: str) -> Optional[str]:
    """The defining layer's name where the material lives outside this asset, else None.

    Containment is by directory rather than by layer stack: an asset's own parts arrive
    through references too, so a layer-stack test would call the doors and wheels
    external. A shared material library sits in a different tree, which is the
    distinction that matters.
    """
    layer = defining_layer(material_prim)
    if layer is None or not asset_dir:
        return None
    path = os.path.abspath(layer.realPath or layer.identifier)
    if path.startswith(asset_dir):
        return None
    return layer.identifier


def dropped_inputs(material_prim: Usd.Prim, values: dict, textures: dict,
                   wire_textures: bool) -> list:
    """Name the inputs a previous run left that this derivation no longer produces.

    Reporting only, so ``--dry-run`` and a real run say the same thing. The
    removal itself happens in :func:`author`.
    """
    shader = owned_openpbr(material_prim)
    if shader is None:
        return []
    keep = set(values) | (set(textures) if wire_textures else set())
    return sorted(
        name for name in (i.GetBaseName() for i in shader.GetInputs())
        if name in TEXTURE_TARGETS and name not in keep
    )


def blocked_by(material: Usd.Prim) -> Optional[str]:
    """Explain why this script must not author onto ``material``, or return None.

    Two ways the material can already belong to someone else: an OpenPBR surface
    authored under a name this script does not own, or a prim sitting on the name
    it writes to that is not the surface it left there. Overwriting either throws
    away hand-authored work, so both are reported and skipped.
    """
    foreign = foreign_openpbr(material)
    if foreign is not None:
        return f"OpenPBR surface already authored at {foreign.GetPrim().GetName()}"
    child = material.GetChild(OPENPBR_PRIM)
    if child and owned_openpbr(material) is None:
        found = shader_id(UsdShade.Shader(child)) or "no info:id"
        return f"{OPENPBR_PRIM} is already a {child.GetTypeName() or 'prim'} ({found})"
    return None


def owns_material_input(name: str) -> bool:
    """Whether an interface input on the Material prim was authored by this script.

    Anything ending ``_texture_file`` counts, because a packed map is exposed under
    the map's own name rather than a parameter name, and those names vary per asset.
    A material that already carried inputs like these was hand-authored, and
    :func:`blocked_by` keeps this script away from it.
    """
    if name.endswith("_texture_file"):
        return True
    return name in TEXTURE_TARGETS or name in UV_INPUTS or name == NORMAL_SCALE_INPUT


def reset_authored(shader: UsdShade.Shader) -> None:
    """Strip what the last run of this script left on its own OpenPBR prim.

    Every value is re-derived on each pass, so anything the previous pass wrote
    has to go first. Without this an input that used to be a constant, or a
    texture connection that outlived the texture, survives into a derivation
    that no longer produces it and the material carries a stale value.

    Only the input names in ``TEXTURE_TARGETS`` are removed, and only on the prim
    this script owns. Any other input on it is left where it is.
    """
    prim = shader.GetPrim()
    for shader_input in shader.GetInputs():
        if shader_input.GetBaseName() in TEXTURE_TARGETS:
            prim.RemoveProperty(shader_input.GetFullName())
    # The nodedef declares one output. Anything else here is from an older run of
    # this script, which wrote outputs:surface; leaving it behind would keep a
    # second, unconnected output beside the live one. Tidiness rather than
    # correctness: either name resolves at render time.
    for shader_output in shader.GetOutputs():
        if shader_output.GetBaseName() != OPENPBR_SURFACE_OUTPUT:
            prim.RemoveProperty(shader_output.GetFullName())


def reset_owned_nodes(stage: Usd.Stage, material_prim: Usd.Prim) -> None:
    """Drop the reader nodes and interface inputs a previous run added.

    They are rebuilt below from the current derivation, so nothing survives
    pointing at a texture the material no longer uses, and re-running never
    leaves a second copy of a node beside the first.
    """
    for child in list(material_prim.GetChildren()):
        if child.GetName().startswith(NODE_PREFIX):
            stage.RemovePrim(child.GetPath())
    material = UsdShade.Material(material_prim)
    for material_input in material.GetInputs():
        if owns_material_input(material_input.GetBaseName()):
            material_prim.RemoveProperty(material_input.GetFullName())


def value_type(target: str, value=None):
    if target in UNIT_COLORS:
        return Sdf.ValueTypeNames.Color3f
    if isinstance(value, Gf.Vec3f):
        return Sdf.ValueTypeNames.Color3f
    return Sdf.ValueTypeNames.Float


def expose(material: UsdShade.Material, name: str, type_name, value=None,
           uniform: bool = False):
    """Author a parameter as an interface input on the Material prim.

    Everything the shader reads goes through one of these, so a consumer can
    retune a material without opening its shader network.

    ``uniform`` matters for the file paths. MaterialX declares ``file`` on its image
    nodes as uniform, and a renderer checks that the input driving it is uniform too.
    Exposing the path as the varying default and connecting it produced "Input storage
    type (uniform/varying) does not match input 'file'" in Houdini and no surface.
    """
    if uniform:
        attr = material.GetPrim().CreateAttribute(
            f"inputs:{name}", type_name, custom=False, variability=Sdf.VariabilityUniform
        )
        if value is not None:
            attr.Set(value)
        return UsdShade.Input(attr)
    material_input = material.CreateInput(name, type_name)
    if value is not None:
        material_input.Set(value)
    return material_input


def author_texcoord(stage: Usd.Stage, material_prim: Usd.Prim) -> UsdShade.Output:
    """The single UV source every reader node under this material shares."""
    path = material_prim.GetPath().AppendChild(f"{NODE_PREFIX}texcoord")
    node = UsdShade.Shader.Define(stage, path)
    node.CreateIdAttr(TEXCOORD_ID)
    node.CreateInput("index", Sdf.ValueTypeNames.Int).Set(0)
    return node.CreateOutput("out", Sdf.ValueTypeNames.Float2)


def author_reader(stage: Usd.Stage, material_prim: Usd.Prim, name: str, kind: str,
                  path: str, colorspace: str, texcoord: UsdShade.Output,
                  uvtiling: UsdShade.Input, uvoffset: UsdShade.Input,
                  file_input: UsdShade.Input, default=None) -> UsdShade.Output:
    """Author one ND_tiledimage_* reader, wired the way the reference library wires them."""
    out_type = {
        "color3": Sdf.ValueTypeNames.Color3f,
        "float": Sdf.ValueTypeNames.Float,
        "vector3": Sdf.ValueTypeNames.Float3,
        "vector4": Sdf.ValueTypeNames.Float4,
    }[kind]
    node = UsdShade.Shader.Define(stage, material_prim.GetPath().AppendChild(name))
    node.CreateIdAttr(TILEDIMAGE_IDS[kind])
    # The file comes from the Material's interface input, so the texture can be
    # swapped there rather than inside the network.
    # Uniform on both ends: the nodedef declares file uniform, and a varying input
    # driving it is the storage-type mismatch a renderer rejects the network for.
    file_attr = node.GetPrim().CreateAttribute(
        "inputs:file", Sdf.ValueTypeNames.Asset, custom=False,
        variability=Sdf.VariabilityUniform,
    )
    UsdShade.Input(file_attr).ConnectToSource(file_input)
    if default is not None:
        if isinstance(default, UsdShade.Input):
            node.CreateInput("default", out_type).ConnectToSource(default)
        else:
            node.CreateInput("default", out_type).Set(default)
    node.CreateInput("texcoord", Sdf.ValueTypeNames.Float2).ConnectToSource(texcoord)
    node.CreateInput("uvtiling", Sdf.ValueTypeNames.Float2).ConnectToSource(uvtiling)
    node.CreateInput("uvoffset", Sdf.ValueTypeNames.Float2).ConnectToSource(uvoffset)
    # Colour space rides on the Material's asset input, matching the reference library.
    file_input.GetAttr().SetColorSpace(colorspace)
    return node.CreateOutput("out", out_type)


def author_packed(stage: Usd.Stage, material_prim: Usd.Prim, shader: UsdShade.Shader,
                  path: str, channels: list, texcoord: UsdShade.Output,
                  uvtiling: UsdShade.Input, uvoffset: UsdShade.Input) -> None:
    """Sample one packed map and unpack the channels the source reads out of it.

    An ORM map feeding both roughness and metalness is read once and split once,
    rather than sampled separately per channel. The file is exposed on the Material
    under the map's own name, because the channels sharing it do not share a
    parameter name to hang it on.
    """
    material = UsdShade.Material(material_prim)
    token = slug(path)
    indices = [CHANNEL_INDEX[channel] for _target, channel in channels]
    kind = "vector4" if max(indices) == 3 else "vector3"
    # The reader's fallback holds each channel's own OpenPBR default, so a map that
    # fails to load leaves every channel at a sensible value rather than zero.
    size = 4 if kind == "vector4" else 3
    fallback = [1.0, 0.3, 0.0, 1.0][:size]
    for target, channel in channels:
        default = OPENPBR_DEFAULTS.get(target)
        if isinstance(default, float):
            fallback[CHANNEL_INDEX[channel]] = default
    default_value = Gf.Vec4f(*fallback) if kind == "vector4" else Gf.Vec3f(*fallback)

    file_input = expose(material, f"{token}_texture_file", Sdf.ValueTypeNames.Asset,
                        Sdf.AssetPath(path), uniform=True)
    sampled = author_reader(
        stage, material_prim, f"{NODE_PREFIX}tiledimage_{token}", kind, path,
        COLORSPACE_RAW, texcoord, uvtiling, uvoffset, file_input, default=default_value)
    split = UsdShade.Shader.Define(
        stage, material_prim.GetPath().AppendChild(f"{NODE_PREFIX}separate_{token}"))
    split.CreateIdAttr(SEPARATE_IDS[kind])
    in_type = Sdf.ValueTypeNames.Float4 if kind == "vector4" else Sdf.ValueTypeNames.Float3
    split.CreateInput("in", in_type).ConnectToSource(sampled)
    for target, channel in channels:
        out = split.CreateOutput(SEPARATE_OUTPUTS[CHANNEL_INDEX[channel]],
                                 Sdf.ValueTypeNames.Float)
        shader.CreateInput(target, Sdf.ValueTypeNames.Float).ConnectToSource(out)


def author_textures(stage: Usd.Stage, material_prim: Usd.Prim, shader: UsdShade.Shader,
                    textures: dict, constants: dict) -> None:
    """Author the reader network and wire it into the OpenPBR surface.

    Packed maps are read once per file and unpacked with a separate node, so an
    ORM map feeding both roughness and metalness is sampled once, not twice.
    """
    material = UsdShade.Material(material_prim)
    texcoord = author_texcoord(stage, material_prim)
    uvtiling = expose(material, "uvtiling", Sdf.ValueTypeNames.Float2, Gf.Vec2f(1.0, 1.0))
    uvoffset = expose(material, "uvoffset", Sdf.ValueTypeNames.Float2, Gf.Vec2f(0.0, 0.0))

    # Group the channels that share one packed file, so it is read and split once.
    packed: dict = {}
    for target in sorted(textures):
        texture = textures[target]
        if target != NORMAL_INPUT and texture.packed:
            packed.setdefault(texture.path, []).append((target, texture.channel))
    for path, channels in sorted(packed.items()):
        author_packed(stage, material_prim, shader, path, channels, texcoord,
                      uvtiling, uvoffset)

    for target in sorted(textures):
        texture = textures[target]
        if target != NORMAL_INPUT and texture.packed:
            continue
        file_input = expose(material, f"{target}_texture_file", Sdf.ValueTypeNames.Asset,
                            Sdf.AssetPath(texture.path), uniform=True)
        if target == NORMAL_INPUT:
            # ND_normalmap expects the encoded tangent-space normal straight off the
            # texture and does the range decode itself, so no scale/bias node is needed.
            sampled = author_reader(
                stage, material_prim, f"{NODE_PREFIX}tiledimage_{NORMAL_INPUT}", "vector3",
                texture.path, COLORSPACE_RAW, texcoord, uvtiling, uvoffset,
                file_input, default=Gf.Vec3f(0.5, 0.5, 1.0))
            scale = expose(material, NORMAL_SCALE_INPUT, Sdf.ValueTypeNames.Float, 1.0)
            node = UsdShade.Shader.Define(
                stage,
                material_prim.GetPath().AppendChild(f"{NODE_PREFIX}normalmap_{NORMAL_INPUT}"))
            node.CreateIdAttr(NORMALMAP_ID)
            node.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(sampled)
            node.CreateInput("scale", Sdf.ValueTypeNames.Float).ConnectToSource(scale)
            out = node.CreateOutput("out", Sdf.ValueTypeNames.Float3)
            shader.CreateInput(NORMAL_INPUT, Sdf.ValueTypeNames.Float3).ConnectToSource(out)
            continue

        is_color = target in UNIT_COLORS
        # The interface constant doubles as the reader's fallback, so the material
        # still holds a usable value if the texture ever fails to load, and the
        # consumer has one place to retune the channel.
        fallback = constants.get(target, OPENPBR_DEFAULTS.get(target))
        exposed = expose(material, target, value_type(target, fallback), fallback)
        kind = "color3" if is_color else "float"
        out = author_reader(
            stage, material_prim, f"{NODE_PREFIX}tiledimage_{target}", kind, texture.path,
            colorspace_for(target), texcoord, uvtiling, uvoffset, file_input,
            default=exposed)
        out_type = Sdf.ValueTypeNames.Color3f if is_color else Sdf.ValueTypeNames.Float
        shader.CreateInput(target, out_type).ConnectToSource(out)


def author(stage: Usd.Stage, material_prim: Usd.Prim, values: dict, textures: dict,
           wire_textures: bool) -> UsdShade.Shader:
    material = UsdShade.Material(material_prim)
    shader = owned_openpbr(material_prim)
    if shader is None:
        shader = UsdShade.Shader.Define(stage, material_prim.GetPath().AppendChild(OPENPBR_PRIM))
    else:
        reset_authored(shader)
    reset_owned_nodes(stage, material_prim)
    shader.CreateIdAttr(OPENPBR_SURFACE_ID)

    # Constants are exposed on the Material and read back through that input, so
    # every parameter the shader uses is retunable from the Material prim.
    for name, value in sorted(values.items()):
        type_name = value_type(name, value)
        exposed = expose(material, name, type_name,
                         value if isinstance(value, Gf.Vec3f) else float(value))
        shader.CreateInput(name, type_name).ConnectToSource(exposed)

    if wire_textures and textures:
        author_textures(stage, material_prim, shader, textures, values)

    surface_out = shader.CreateOutput(OPENPBR_SURFACE_OUTPUT, Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput("mtlx").ConnectToSource(surface_out)
    return shader


def resolve_texture(attr: Usd.Attribute) -> tuple:
    """Return (authored path, resolved path or None) for an asset-valued attribute."""
    value = attr.Get()
    path = asset_path(value)
    if not path:
        return None, None
    resolved = getattr(value, "resolvedPath", "") or ""
    if resolved and os.path.isfile(resolved):
        return path, resolved
    # usd-core leaves resolvedPath empty for a path it cannot find, so fall back to
    # resolving against the layer that authored it before calling the texture missing.
    layer = attr.GetPrim().GetStage().GetRootLayer()
    base = os.path.dirname(layer.realPath or layer.identifier)
    candidate = os.path.normpath(os.path.join(base, path))
    return path, candidate if os.path.isfile(candidate) else None


def texture_problems(material_prim: Usd.Prim) -> list:
    """Report textures this material names that do not resolve to a file on disk.

    A migration that writes a reader node pointing at a texture nobody can open
    produces a material that looks right in the file and renders untextured, which
    is the failure this gate exists to catch.

    Every asset-valued shader input counts, whatever it is named. Matching the two
    names this script authors, ``inputs:file`` on a UsdUVTexture and ``*_texture_file``
    on the Material, left every MDL-named map unchecked: OmniPBR and OmniGlass spell
    theirs ``inputs:diffuse_texture``, ``inputs:ORM_texture``, ``inputs:normalmap_texture``
    and so on, a migrated material keeps its MDL surface, and an unmigrated one has
    nothing else. Across the 14 samples that was 56 of 197 asset inputs invisible.

    The filter is ``inputs:`` rather than every asset-valued attribute, so
    ``info:mdl:sourceAsset``, which names a ``.mdl`` module the runtime resolves
    through its own search paths rather than beside the layer, is not reported as a
    missing texture.
    """
    problems, seen = [], set()
    for prim in Usd.PrimRange(material_prim):
        for attr in prim.GetAttributes():
            name = attr.GetName()
            if not name.startswith("inputs:"):
                continue
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            path, resolved = resolve_texture(attr)
            if path is None or (prim.GetPath(), path) in seen:
                continue
            seen.add((prim.GetPath(), path))
            if resolved is None:
                problems.append(
                    f"{material_prim.GetPath()}: {name} = {path} does not resolve to a "
                    f"file on disk (VM.TEX.001)")
    return problems


def verify(stage: Usd.Stage) -> list:
    """Report the VM.PBR conditions this script is responsible for."""
    problems = []
    for prim in stage.TraverseAll():
        if prim.GetTypeName() != "Material":
            continue
        if "PhysicsMaterials" in str(prim.GetPath()):
            continue
        material = UsdShade.Material(prim)
        # Texture resolution does not depend on the surface contract, so it is
        # checked on every material. Reporting it only after VM.PBR.001 passed
        # meant an unmigrated material, which is the state the workflow runs
        # --verify on first, was told about its missing surface and nothing else.
        problems.extend(texture_problems(prim))
        # Follow the connection rather than searching the material for any OpenPBR
        # shader: an orphaned OpenPBR prim next to an mtlx output wired to something
        # else is exactly the state this gate exists to catch.
        shader, _output_name = connected_mtlx_surface(material)
        sid = shader_id(shader)
        if shader is None:
            problems.append(f"{prim.GetPath()}: no outputs:mtlx:surface (VM.PBR.001)")
        elif sid != OPENPBR_SURFACE_ID:
            problems.append(
                f"{prim.GetPath()}: outputs:mtlx:surface resolves to "
                f"{shader.GetPrim().GetName()} ({sid or 'no info:id'}), "
                f"not an OpenPBR nodedef (VM.PBR.001)")
        else:
            for shader_input in shader.GetInputs():
                if shader_input.HasConnectedSource():
                    continue
                name, value = shader_input.GetBaseName(), shader_input.Get()
                if value is None:
                    continue
                held = bound(name, value)
                if held is None:
                    continue
                if isinstance(held, Gf.Vec3f):
                    if as_rgb(value) != tuple(held):
                        problems.append(
                            f"{prim.GetPath()}.{name}: {value} out of range (VM.PBR.002)")
                elif as_float(value) is not None and abs(as_float(value) - float(held)) > 1e-6:
                    problems.append(
                        f"{prim.GetPath()}.{name}: {value} out of range (VM.PBR.002)")
        # The parameters the shader reads through the Material also have to stay in
        # range, since that is now where the authored values live. Checked whatever
        # the surface contract said, so a material migrated by an older version of
        # this script still has its values reported. A material that was never
        # migrated carries none of these names and produces nothing here.
        for material_input in material.GetInputs():
            name = material_input.GetBaseName()
            if name not in AUTHORED_INPUTS or material_input.HasConnectedSource():
                continue
            value = material_input.Get()
            if value is None:
                continue
            held = bound(name, value)
            if held is None:
                continue
            if isinstance(held, Gf.Vec3f):
                if as_rgb(value) != tuple(held):
                    problems.append(f"{prim.GetPath()}.inputs:{name}: {value} out of range "
                                    f"(VM.PBR.002)")
            elif as_float(value) is not None and abs(as_float(value) - float(held)) > 1e-6:
                problems.append(f"{prim.GetPath()}.inputs:{name}: {value} out of range "
                                f"(VM.PBR.002)")
    return problems


def usd_files(paths: Iterable[str]) -> list:
    found = []
    for path in paths:
        if os.path.isfile(path):
            found.append(path)
            continue
        for root, _dirs, files in os.walk(path):
            # One separator convention for every test below, so the same walk
            # behaves the same on Windows and POSIX.
            walked = root.replace(os.sep, "/").replace("\\", "/")
            if walked.rsplit("/", 1)[-1] != "simready_usd":
                continue
            if "/textures/" in f"{walked}/":
                continue
            for name in files:
                if name.endswith((".usd", ".usda", ".usdc")):
                    found.append(os.path.join(root, name))
    return sorted(set(found))


def variant_contexts(stage: Usd.Stage, path):
    """Edit contexts that point authoring at the variants named in ``path``.

    A path such as ``/wheel{paint_color=Metallic_Black_Rim}Looks/WheelRim`` cannot be
    handed to ``GetPrimAtPath``: variant selectors are part of the layer's namespace, not
    the composed stage's. Walking the selectors outward and entering each variant's edit
    context puts authoring inside that variant, which is where the values were read from
    and the only place they belong -- author outside it and every sibling variant
    inherits this one's surface.

    Returns ``(contexts, prim_path)``, or ``(None, None)`` where a selection does not
    resolve. ``contexts`` is empty for an ordinary path, which then authors as before.
    """
    selections = []
    walk = path
    while walk != walk.GetParentPath():
        if walk.IsPrimVariantSelectionPath():
            variant_set, variant = walk.GetVariantSelection()
            selections.append((walk.GetPrimPath(), variant_set, variant))
        walk = walk.GetParentPath()
    prim_path = path.StripAllVariantSelections()
    if not selections:
        return [], prim_path

    contexts = []
    for owner_path, variant_set, variant in reversed(selections):
        owner = stage.GetPrimAtPath(owner_path.StripAllVariantSelections())
        if not owner:
            return None, None
        variant_sets = owner.GetVariantSets()
        if variant_set not in variant_sets.GetNames():
            return None, None
        selection = variant_sets.GetVariantSet(variant_set)
        if variant not in selection.GetVariantNames():
            return None, None
        selection.SetVariantSelection(variant)
        contexts.append(selection.GetVariantEditContext())
    return contexts, prim_path


def variant_sets_on(stage: Usd.Stage):
    """Every variant set on the stage, as (prim path, set name, [variant names]).

    Read from the prim inside the prototype where the prim is an instance proxy, because a
    proxy has no variant sets of its own. Selecting on the prototype moves every instance
    that shares it, which is what makes one pass per variant cover the whole asset.
    """
    found, seen = [], set()
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        source = prim.GetPrimInPrototype() if prim.IsInstanceProxy() else prim
        if not source:
            continue
        variant_sets = source.GetVariantSets()
        for name in variant_sets.GetNames():
            key = (str(source.GetPath()), name)
            if key in seen:
                continue
            seen.add(key)
            found.append((source.GetPath(), name, variant_sets.GetVariantSet(name).GetVariantNames()))
    return found


def each_variant(stage: Usd.Stage):
    """Select each variant of each set in turn, restoring the original selection after.

    One pass per variant rather than per combination: a material is specialised inside one
    variant of one set, so visiting every variant of every set reaches all of them without
    the combinatorial blowup of every product. Ten paint colours and seven rim finishes on
    the Audi A6 are 17 passes, not 70.

    Materials already migrated on an earlier pass are reported unchanged, so a material
    shared across variants is authored once.
    """
    for prim_path, set_name, variants in variant_sets_on(stage):
        owner = stage.GetPrimAtPath(prim_path)
        if not owner:
            continue
        variant_set = owner.GetVariantSets().GetVariantSet(set_name)
        original = variant_set.GetVariantSelection()
        for variant in variants:
            if variant == original:
                continue  # already covered by the pass over the asset as it ships
            variant_set.SetVariantSelection(variant)
            yield f"{set_name}={variant}"
        variant_set.SetVariantSelection(original)


def migrate_stage(stage: Usd.Stage, wire_textures: bool = True,
                  dry_run: bool = False, shared_materials: str = "skip") -> tuple:
    """Author the OpenPBR surface on every material of an already-open stage.

    This is the migration itself, with none of the file handling ``process``
    does around it: nothing is opened here and nothing is saved. ``process``
    calls it for a command-line run, and the ``FET_006_OPENPBR`` feature
    adapter in ``nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr``
    calls it for a run inside the SimReady adapter framework, so both paths
    author exactly the same thing from the same derivation.

    Returns ``(migrated, skipped, conflicts, wired, flattened, notes)``.
    """
    migrated, skipped, conflicts, wired, flattened, notes = 0, 0, 0, 0, 0, []
    pending: dict = {}
    # Materials outside this directory belong to something else -- a shared library
    # referenced by many assets. Migrating them from inside one asset's run changes
    # how every other asset renders, so it takes asking for.
    root_layer = stage.GetRootLayer()
    asset_dir = os.path.dirname(os.path.abspath(root_layer.realPath or root_layer.identifier))
    asset_dir = asset_dir + os.sep if asset_dir else ""
    # Collect paths rather than prim handles: authoring removes the reader nodes a
    # previous run left, and a handle to a removed prim expires. Re-fetching by path
    # keeps a re-run from tripping over the nodes it is replacing.
    # Instance proxies are included on purpose. A material inside an instance is not
    # visible to TraverseAll, and on the vehicle sample that hid 61 of 80 materials --
    # the run reported success having never seen most of the asset. Authoring still
    # happens in the material's own defining layer, which is where an instanced
    # material can be written at all.
    material_paths = [prim.GetPath() for prim in stage.Traverse(Usd.TraverseInstanceProxies())
                      if prim.GetTypeName() == "Material"]
    for path in material_paths:
        prim = stage.GetPrimAtPath(path)
        if not prim or prim.GetTypeName() != "Material":
            continue
        if "PhysicsMaterials" in str(prim.GetPath()):
            skipped += 1
            continue
        # Only ever rewrite a surface this script created. Anything else under the
        # material was authored by hand, and overwriting it would throw that away.
        blocker = blocked_by(prim)
        if blocker is not None:
            conflicts += 1
            notes.append(f"  {prim.GetPath()}: CONFLICT, {blocker}, left alone")
            continue
        if shared_materials == "skip":
            outside = is_outside_asset(prim, asset_dir)
            if outside is not None:
                skipped += 1
                notes.append(
                    f"  {prim.GetPath()}: defined in {outside.rsplit('/', 1)[-1]}, outside this "
                    f"asset. Re-run with --shared-materials migrate to include it"
                )
                continue
        unknown = unknown_mdl_model(prim)
        if unknown is not None:
            skipped += 1
            notes.append(
                f"  {prim.GetPath()}: MDL model '{unknown}' is not one this script reads, "
                f"left alone"
            )
            continue
        values, textures, prim_notes = derive(prim, wire_textures)
        if not values and not textures:
            skipped += 1
            notes.append(f"  {prim.GetPath()}: no source parameters found, left alone")
            continue
        if already_authored(prim, values, textures, wire_textures):
            skipped += 1
            notes.append(f"  {prim.GetPath()}: already migrated, unchanged")
            continue
        # Read before authoring: this is what a previous run left that the current
        # derivation does not produce, and the run is about to drop it.
        dropped = dropped_inputs(prim, values, textures, wire_textures)
        if not dry_run:
            if prim.IsInstanceProxy():
                # A material inside an instance cannot be authored where it appears:
                # USD refuses to create a prim under an instance proxy. Its defining
                # layer is where the material actually lives, so the work is collected
                # here and written once per layer below.
                target = opinion_target(prim)
                if target is None:
                    skipped += 1
                    notes.append(f"  {prim.GetPath()}: no layer holds this material's own "
                                 f"values, left alone")
                    continue
                target_layer, layer_path = target
                pending.setdefault(target_layer.identifier, []).append(
                    (layer_path, values, textures)
                )
            else:
                author(stage, prim, values, textures, wire_textures)
        migrated += 1
        if wire_textures:
            wired += len(textures)
        else:
            flattened += len(textures)
        summary = ", ".join(f"{k}={v}" for k, v in sorted(values.items()))
        notes.append(f"  {prim.GetPath()}: {summary or '(no constants)'}")
        if dropped:
            notes.append(f"      dropped stale input(s) from an earlier run: {', '.join(dropped)}")
        for note in prim_notes:
            if "<-" in note:
                marker = "texture" if wire_textures else "FLAT"
                notes.append(f"      {marker}: {note}")
            else:
                notes.append(f"      note: {note}")

    if pending:
        # A material authored on a prototype's own layer is saved alongside the layer
        # opinion_target chose, since the two are not always the same file.
        extra_saves = set()
        for identifier, entries in sorted(pending.items()):
            layer_stage = Usd.Stage.Open(identifier)
            if layer_stage is None:
                notes.append(f"  {identifier}: cannot open to author into")
                continue
            written = 0
            for layer_path, layer_values, layer_textures in entries:
                # A path carrying variant selectors is not addressable on a stage, so the
                # selections are re-entered as edit contexts: each one points authoring at
                # that variant's own spec, which is where the values came from.
                contexts, prim_path = variant_contexts(layer_stage, layer_path)
                if contexts is None:
                    notes.append(f"  {identifier.rsplit('/', 1)[-1]}{layer_path}: "
                                 f"variant selections do not resolve in this layer")
                    continue
                with contextlib.ExitStack() as stack:
                    for context in contexts:
                        stack.enter_context(context)
                    write_stage, layer_prim = authorable_prim(layer_stage, prim_path)
                    if not layer_prim:
                        notes.append(f"  {identifier.rsplit('/', 1)[-1]}{layer_path}: "
                                     f"not in this layer, or no layer defines it outside "
                                     f"an instance")
                        continue
                    author(write_stage, layer_prim, layer_values, layer_textures, wire_textures)
                    if write_stage is not layer_stage:
                        extra_saves.add(write_stage)
                written += 1
            layer_stage.GetRootLayer().Save()
            for extra in extra_saves:
                extra.GetRootLayer().Save()
            extra_saves.clear()
            notes.append(f"  {identifier.rsplit('/', 1)[-1]}: {written} material(s) authored")

    return migrated, skipped, conflicts, wired, flattened, notes


def authorable_prim(layer_stage: Usd.Stage, prim_path):
    """The material as a prim that can be authored, and the stage holding it.

    ``opinion_target`` picks the layer holding a material's own values. USD refuses to
    create a prim in two cases that layer can present, and both appear in Isaac-composed
    samples, where a mesh is instanced from ``instances.usda`` and each material is in
    turn instanced from ``materials.usda``:

    * the material is an **instance proxy**, because an ancestor is instanceable, so its
      real prims live in a prototype;
    * the material is **itself instanceable**, so its own children live in a prototype
      and ``OpenPBR_Shader`` cannot be created under it.

    Either way the prims exist for real in the layer the instance references, so
    authoring moves there. Returns ``(stage, prim)``, or ``(None, None)`` when no layer
    holds the material outside an instance.
    """
    prim = layer_stage.GetPrimAtPath(prim_path)
    if not prim:
        return None, None
    if not prim.IsInstanceProxy() and not prim.IsInstanceable():
        return layer_stage, prim

    for identifier, path in _reference_sources(prim):
        source_stage = Usd.Stage.Open(identifier)
        if source_stage is None:
            continue
        source_prim = source_stage.GetPrimAtPath(path)
        if source_prim and not source_prim.IsInstanceProxy() and not source_prim.IsInstanceable():
            return source_stage, source_prim
    return None, None


def _reference_sources(prim: Usd.Prim):
    """Every (layer identifier, prim path) this prim references, strongest first.

    An instance's own children are unreachable, so the referenced prims are where the
    material actually is. The prototype is consulted first when the prim is a proxy,
    since then the reference lives on an ancestor rather than on the prim.
    """
    candidates = []
    source = prim.GetPrimInPrototype() if prim.IsInstanceProxy() else prim
    if source:
        for spec in source.GetPrimStack():
            candidates.append((spec.layer.identifier, spec.path))

    query = Usd.PrimCompositionQuery(prim)
    for arc in query.GetCompositionArcs():
        layer = arc.GetTargetLayer()
        path = arc.GetTargetPrimPath()
        if layer is not None and path:
            candidates.append((layer.identifier, path))

    seen, ordered = set(), []
    for identifier, path in candidates:
        key = (identifier, str(path))
        if key in seen:
            continue
        seen.add(key)
        ordered.append((identifier, path))
    return ordered


def process(path: str, args) -> tuple:
    stage = Usd.Stage.Open(path)
    if stage is None:
        return 0, 0, 0, 0, 0, [f"{path}: cannot open"]

    if args.verify:
        return 0, 0, 0, 0, 0, verify(stage)

    def run():
        return migrate_stage(stage, wire_textures=args.textures, dry_run=args.dry_run,
                             shared_materials=getattr(args, "shared_materials", "skip"))

    migrated, skipped, conflicts, wired, flattened, notes = run()

    if getattr(args, "variants", "selected") == "all":
        # A material specialised inside a variant is only on the stage while that variant
        # is selected, so a single pass sees one variant's worth. The rest are invisible,
        # not absent: the Audi A6 ships with Midnight_Black and Metallic_Black_Rim chosen,
        # and every other paint and rim finish migrates as nothing at all.
        for selection in each_variant(stage):
            extra = run()
            if extra[0]:
                notes.append(f"  variant {selection}: {extra[0]} material(s)")
            migrated += extra[0]
            skipped += extra[1]
            conflicts += extra[2]
            wired += extra[3]
            flattened += extra[4]
            notes.extend(extra[5])

    if migrated and not args.dry_run:
        stage.GetRootLayer().Save()
    return migrated, skipped, conflicts, wired, flattened, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="+", help="USD file(s) or directories to search")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    # Textures are carried across by default. --textures is kept so the older
    # documented invocation still works, and now says what already happens.
    parser.add_argument("--textures", dest="textures", action="store_true", default=True,
                        help="wire MaterialX reader nodes for texture-driven inputs (default)")
    parser.add_argument("--no-textures", dest="textures", action="store_false",
                        help="flatten texture-driven inputs to constants instead of wiring them")
    parser.add_argument(
        "--variants", choices=["selected", "all"], default="selected",
        help="which variants to migrate: only the ones the asset ships selected (default), "
             "or every variant of every variant set, which is what an asset whose "
             "materials are specialised per variant needs",
    )
    parser.add_argument(
        "--shared-materials", choices=["skip", "migrate"], default="skip",
        help="what to do with materials defined outside this asset's directory, which is "
             "where a shared material library lives: skip them and say so (default), or "
             "migrate them, which changes every asset that references them",
    )
    parser.add_argument("--verify", action="store_true",
                        help="report VM.PBR.001/002 and texture resolution, change nothing")
    args = parser.parse_args()

    targets = usd_files(args.paths)
    if not targets:
        print("No USD assets found.")
        return 1

    total_migrated, total_problems, total_conflicts = 0, 0, 0
    total_wired, total_flat = 0, 0
    for path in targets:
        migrated, skipped, conflicts, wired, flat, notes = process(path, args)
        label = os.path.relpath(path)
        if args.verify:
            if notes:
                total_problems += len(notes)
                print(f"FAIL {label}")
                for note in notes:
                    print(f"  {note}")
            else:
                print(f"ok   {label}")
            continue
        total_migrated += migrated
        total_conflicts += conflicts
        total_wired += wired
        total_flat += flat
        print(f"{label}: {migrated} migrated, {skipped} skipped"
              f"{f', {conflicts} conflict(s)' if conflicts else ''}"
              f"{' (dry run)' if args.dry_run else ''}")
        for note in notes:
            print(note)

    if args.verify:
        print(f"\n{total_problems} problem(s) across {len(targets)} asset(s)")
        return 1 if total_problems else 0
    print(f"\n{total_migrated} material(s) migrated across {len(targets)} asset(s)")
    if total_wired:
        print(f"{total_wired} channel(s) carried across as textures.")
    if total_conflicts:
        print(f"{total_conflicts} material(s) left alone: they already carry a shader this "
              "script does not own, listed as CONFLICT above. Review those by hand; the "
              "script will not overwrite them or author a second surface beside them.")
    if total_flat:
        print(f"{total_flat} channel(s) marked FLAT were texture-driven in the source and are "
              "held at a constant here, because --no-textures was given: the constant the "
              "source carries beside the map, or the OpenPBR default where it carries none. "
              "geometry_normal is the exception, having no constant form, and is left "
              "unauthored. Re-run without --no-textures to wire them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
