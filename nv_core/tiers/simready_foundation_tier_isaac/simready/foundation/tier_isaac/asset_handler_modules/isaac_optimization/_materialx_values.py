# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Resolve the static texture patterns supported by the Preview Surface adapter.

This handles Material interfaces, MaterialX image nodes, and the normal-channel
controls used by NVIDIA's SimReady material library. Other graphs need baking.
"""
from dataclasses import dataclass, replace
import math

from pxr import Gf, Sdf, UsdShade


@dataclass(frozen=True)
class Texture:
    file: Sdf.AssetPath
    channel: str = "rgb"
    colorspace: str = "raw"
    uvscale: tuple = (1.0, 1.0)
    uvoffset: tuple = (0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0, 1.0)
    bias: tuple = (0.0, 0.0, 0.0, 0.0)
    fallback: tuple = (0.0, 0.0, 0.0, 1.0)
    wrap_s: str = "repeat"
    wrap_t: str = "repeat"


_UV = object()


def _constant(value, label):
    if isinstance(value, Texture) or value is _UV:
        raise ValueError(f"{label}: requires a static value")
    return value


def _vector(value, size, label):
    value = _constant(value, label)
    values = tuple(float(x) for x in value) if hasattr(value, "__len__") else (float(value),) * size
    if len(values) != size or not all(math.isfinite(x) for x in values):
        raise ValueError(f"{label}: invalid {size}-component value")
    return values


def _affine(value, scale, bias):
    """Fold normal decoding and channel flips into one UsdUVTexture operation."""
    if isinstance(value, Texture):
        return replace(value, scale=tuple(a * b for a, b in zip(value.scale, scale)),
                       bias=tuple(a * b + c for a, b, c in zip(value.bias, scale, bias)))
    return Gf.Vec3f(*(a * b + c for a, b, c in zip(_vector(value, 3, "normal"), scale, bias)))


def resolve_input(shader_input, default=None):
    """Return a constant or :class:`Texture`; refuse unsupported/animated graphs."""
    return _resolve(shader_input.GetAttr() if shader_input else None, default, frozenset())


def _resolve(attr, default, seen):
    if not attr:
        return default
    path = attr.GetPath()
    if path in seen:
        raise ValueError(f"{path}: cyclic material connection")
    if attr.GetNumTimeSamples():
        raise ValueError(f"{path}: animated material input requires baking")
    seen = seen | {path}
    connections = attr.GetConnections()
    if connections:
        if len(connections) != 1:
            raise ValueError(f"{path}: multiple material connections")
        source = attr.GetStage().GetAttributeAtPath(connections[0])
        if not source:
            raise ValueError(f"{path}: unresolved material connection {connections[0]}")
        return _resolve(source, default, seen)
    if attr.GetName().startswith("inputs:"):
        value = attr.Get()
        return default if value is None else value
    shader = UsdShade.Shader(attr.GetPrim())
    if not shader:
        raise ValueError(f"{path}: disconnected node graph output")
    shader_id = shader.GetIdAttr().Get()

    def read(name, fallback=None):
        item = shader.GetInput(name)
        return _resolve(item.GetAttr() if item else None, fallback, seen)

    if shader_id in {"ND_texcoord_vector2", "ND_geompropvalue_vector2"}:
        key = "index" if shader_id == "ND_texcoord_vector2" else "geomprop"
        value = _constant(read(key, 0 if key == "index" else "st"), str(path))
        if value not in (0, "st"):
            raise ValueError(f"{path}: only the st texture coordinate set is supported")
        return _UV
    if shader_id in {"ND_image_float", "ND_image_color3", "ND_image_vector3", "ND_image_color4",
                     "ND_tiledimage_float", "ND_tiledimage_color3", "ND_tiledimage_color4", "ND_tiledimage_vector3"}:
        return _image(shader, shader_id, read)
    if shader_id in {"ND_normalmap", "ND_normalmap_float"}:
        # A normalmap maps encoded RGB to a tangent-space normal. UPS performs
        # the tangent-frame transformation itself, so only decode and scale here.
        # MaterialX 1.38's ND_normalmap also supports object-space normals;
        # the newer ND_normalmap_float has no space input.
        if shader_id == "ND_normalmap" and _constant(read("space", "tangent"), str(path)) != "tangent":
            raise ValueError(f"{path}: object-space normal map requires baking to tangent space")
        for name in ("normal", "tangent", "bitangent"):
            item = shader.GetInput(name)
            if item and (item.HasConnectedSource() or item.GetAttr().HasAuthoredValueOpinion()):
                raise ValueError(f"{path}: custom normal frame requires baking")
        value = read("in", Gf.Vec3f(.5, .5, 1.0))
        strength = float(_constant(read("scale", 1.0), str(path)))
        if not math.isfinite(strength):
            raise ValueError(f"{path}: invalid normal scale")
        if isinstance(value, Texture):
            if value.channel != "rgb" or value.colorspace != "raw":
                raise ValueError(f"{path}: normal map requires raw RGB data")
        return _affine(value, (2 * strength, 2 * strength, 2, 1), (-strength, -strength, -1, 0))
    if shader_id == "ND_invert_vector3":
        amount = _vector(read("amount", Gf.Vec3f(1)), 3, str(path))
        return _affine(read("in", Gf.Vec3f(0)), (-1, -1, -1, 1), (*amount, 0))
    if shader_id in {"ND_separate3_vector3", "ND_separate3_color3", "ND_separate4_color4"}:
        channel = {"outx": "r", "outy": "g", "outz": "b", "outr": "r", "outg": "g", "outb": "b", "outa": "a"}.get(path.name.split(":")[-1])
        if channel is None:
            raise ValueError(f"{path}: unsupported image channel")
        value = read("in")
        if isinstance(value, Texture):
            return replace(value, channel=channel)
        return value["rgba".index(channel)]
    if shader_id == "ND_ifequal_floatB":
        first = _constant(read("value1", False), str(path))
        second = _constant(read("value2", False), str(path))
        return read("in1" if first == second else "in2", 0.0)
    if shader_id == "ND_combine3_vector3":
        values = [read(f"in{i}", 0.0) for i in range(1, 4)]
        if not any(isinstance(value, Texture) for value in values):
            return Gf.Vec3f(*values)
        if not all(isinstance(value, Texture) and value.channel == channel
                   for value, channel in zip(values, "rgb")):
            raise ValueError(f"{path}: normal channels require the same RGB image")
        first = values[0]
        identity = ("file", "colorspace", "uvscale", "uvoffset", "fallback", "wrap_s", "wrap_t")
        if any(any(getattr(value, key) != getattr(first, key) for key in identity) for value in values[1:]):
            raise ValueError(f"{path}: normal channels require the same RGB image")
        return replace(first, channel="rgb", scale=tuple(v.scale[i] for i, v in enumerate(values)) + (1,),
                       bias=tuple(v.bias[i] for i, v in enumerate(values)) + (0,))
    raise ValueError(f"{path}: unsupported MaterialX shader {shader_id!r}; bake it before optimization")


def _file_source(shader):
    """Follow interface inputs to retain the value's layer anchor and color space."""
    item = shader.GetInput("file")
    if not item:
        return None, ""
    attr = item.GetAttr()
    visited = set()
    colorspace = ""
    while attr and attr.GetPath() not in visited:
        visited.add(attr.GetPath())
        colorspace = colorspace or attr.GetMetadata("colorSpace") or ""
        connections = attr.GetConnections()
        if not connections:
            return attr, colorspace
        if len(connections) != 1:
            break
        attr = attr.GetStage().GetAttributeAtPath(connections[0])
    raise ValueError(f"{shader.GetPath()}: unsupported texture filename connection")


def _image(shader, shader_id, read):
    label = str(shader.GetPath())
    file = _constant(read("file", Sdf.AssetPath()), label)
    width = 4 if shader_id.endswith("_color4") else 3
    default = Gf.Vec4f(0) if width == 4 else Gf.Vec3f(0)
    fallback = _constant(read("default", 0.0 if shader_id.endswith("_float") else default), label)
    if not isinstance(file, Sdf.AssetPath):
        raise ValueError(f"{label}: texture filename must be an asset path")
    if not file.path:
        return fallback
    attr, colorspace = _file_source(shader)
    if file.resolvedPath:
        file = Sdf.AssetPath(file.resolvedPath)
    elif attr:
        for spec in attr.GetPropertyStack():
            if spec.HasDefaultValue():
                file = Sdf.AssetPath(Sdf.ComputeAssetPathRelativeToLayer(spec.layer, file.path))
                break
    aliases = {"": "raw", "raw": "raw", "data": "raw", "lin_rec709": "raw", "lin_rec709_scene": "raw",
               "linear": "raw", "sRGB": "sRGB", "srgb_texture": "sRGB", "srgb_rec709_scene": "sRGB"}
    if colorspace not in aliases:
        raise ValueError(f"{label}: unsupported texture color space {colorspace!r}")
    uv = read("texcoord", _UV)
    uvscale, uvoffset = (1.0, 1.0), (0.0, 0.0)
    if uv is not _UV:
        uvscale, uvoffset = (0.0, 0.0), _vector(uv, 2, label)
    if shader_id.startswith("ND_tiledimage"):
        tiling = _vector(read("uvtiling", Gf.Vec2f(1)), 2, label)
        offset = _vector(read("uvoffset", Gf.Vec2f(0)), 2, label)
        image_size = _vector(read("realworldimagesize", Gf.Vec2f(1)), 2, label)
        tile_size = _vector(read("realworldtilesize", Gf.Vec2f(1)), 2, label)
        if any(value <= 0 for value in image_size):
            raise ValueError(f"{label}: invalid image size")
        ratio = tuple(a / b for a, b in zip(tile_size, image_size))
        uvscale = tuple(a * b * c for a, b, c in zip(uvscale, tiling, ratio))
        # MaterialX tiledimage SUBTRACTS uvoffset; UsdTransform2d adds translation.
        uvoffset = tuple((a * b - c) * d for a, b, c, d in zip(uvoffset, tiling, offset, ratio))
    # MaterialX's constant border returns the authored default; UPS's black
    # border returns zero. Treating them as aliases changes texture edge colors.
    wraps = {"periodic": "repeat", "clamp": "clamp", "mirror": "mirror"}
    modes = (["periodic", "periodic"] if shader_id.startswith("ND_tiledimage") else
             [read(name, "periodic") for name in ("uaddressmode", "vaddressmode")])
    if any(mode not in wraps for mode in modes):
        raise ValueError(f"{label}: unsupported texture address mode")
    if read("filtertype", "linear") != "linear" or read("framerange", ""):
        raise ValueError(f"{label}: texture filtering or frame sequence requires baking")
    channel = "r" if shader_id.endswith("_float") else "rgb"
    values = _vector(fallback, width, label)
    return Texture(file=file, channel=channel, colorspace=aliases[colorspace], uvscale=uvscale, uvoffset=uvoffset,
                   fallback=values if len(values) == 4 else (*values, 1.0), wrap_s=wraps[modes[0]], wrap_t=wraps[modes[1]])
