# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Replace MaterialX render contexts with a portable preview on a staged copy.

Preserve existing preview and MDL networks. Unsupported connected graphs require
a baked preview and fail before the edit layer changes.
"""

from __future__ import annotations

from dataclasses import replace
import os

from pxr import Gf, Sdf, Usd, UsdShade

from ._materialx_values import Texture, resolve_input


def materialx_outputs(material: UsdShade.Material) -> list[UsdShade.Output]:
    """Return connected outputs in the case-insensitive MaterialX context."""
    return [output for output in material.GetOutputs()
            if len(output.GetBaseName().split(":")) == 2
            and output.GetBaseName().split(":")[0].lower() == "mtlx"
            and output.GetAttr().GetConnections()]


def _network(stage, paths):
    """Follow connection properties, including material interface chains."""
    seen, prims = set(), set()
    pending = list(paths)
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        attr = stage.GetAttributeAtPath(path)
        if not attr:
            raise ValueError(f"Unresolved material connection <{path}>")
        prim = attr.GetPrim()
        if UsdShade.Shader(prim) or (UsdShade.NodeGraph(prim) and not UsdShade.Material(prim)):
            prims.add(prim.GetPath())
        # An input interface forwards only its own connection. A shader output
        # depends on its inputs; a nodegraph output forwards its connection.
        if UsdShade.Shader(prim) and attr.GetName().startswith("outputs:"):
            pending.extend(p for a in prim.GetAttributes() for p in a.GetConnections())
        pending.extend(attr.GetConnections())
    return prims


def _preview(material):
    shader, _, _ = material.ComputeSurfaceSource()
    return shader if shader and shader.GetIdAttr().Get() == "UsdPreviewSurface" else None


def _fallback(material, outputs):
    surfaces = [o for o in outputs if o.GetBaseName().split(":")[-1] == "surface"]
    if len(surfaces) != 1:
        raise ValueError(f"<{material.GetPath()}> needs exactly one MaterialX surface to create its preview")
    context = surfaces[0].GetBaseName().split(":")[0]
    shader, _, _ = material.ComputeSurfaceSource(context)
    shader_id = shader.GetIdAttr().Get() if shader else None
    if shader_id == "ND_open_pbr_surface_surfaceshader":
        mapping = {
            "diffuseColor": ("base_color", Gf.Vec3f(0.8)),
            "metallic": ("base_metalness", 0.0),
            "roughness": ("specular_roughness", 0.3),
            "ior": ("specular_ior", 1.5),
            "opacity": ("geometry_opacity", 1.0),
            "clearcoat": ("coat_weight", 0.0),
            "clearcoatRoughness": ("coat_roughness", 0.0),
            "emissiveColor": ("emission_color", Gf.Vec3f(1.0)),
            "normal": ("geometry_normal", None),
        }
        emission_weight = resolve_input(shader.GetInput("emission_luminance"), 0.0)
    elif shader_id == "ND_standard_surface_surfaceshader":
        mapping = {
            "diffuseColor": ("base_color", Gf.Vec3f(0.8)),
            "metallic": ("metalness", 0.0),
            "roughness": ("specular_roughness", 0.2),
            "ior": ("specular_IOR", 1.5),
            "opacity": ("opacity", Gf.Vec3f(1.0)),
            "clearcoat": ("coat", 0.0),
            "clearcoatRoughness": ("coat_roughness", 0.1),
            "emissiveColor": ("emission_color", Gf.Vec3f(1.0)),
            "normal": ("normal", None),
        }
        emission_weight = resolve_input(shader.GetInput("emission"), 0.0)
    else:
        raise ValueError(f"<{material.GetPath()}> has unsupported MaterialX surface {shader_id!r}")
    values = {name: resolve_input(shader.GetInput(source), default)
              for name, (source, default) in mapping.items()}
    weight_name = "base_weight" if shader_id == "ND_open_pbr_surface_surfaceshader" else "base"
    weight = resolve_input(shader.GetInput(weight_name), 1.0)
    if isinstance(weight, Texture):
        raise ValueError(f"<{shader.GetPath()}> has textured base weight; bake a preview first")
    color = values["diffuseColor"]
    if isinstance(color, Texture):
        values["diffuseColor"] = replace(color,
            scale=tuple(float(weight) * x if i < 3 else x for i, x in enumerate(color.scale)),
            bias=tuple(float(weight) * x if i < 3 else x for i, x in enumerate(color.bias)))
    else:
        values["diffuseColor"] = Gf.Vec3f(*(float(weight) * v for v in color))
    # Preview emission is unitless. As in USD Exchange's preview fallback,
    # preserve emission color for an emitting surface, not physical luminance.
    if isinstance(emission_weight, Texture):
        raise ValueError(f"<{shader.GetPath()}> has textured emission strength; bake a preview first")
    if not emission_weight:
        values["emissiveColor"] = Gf.Vec3f(0)
    opacity = values["opacity"]
    if not isinstance(opacity, (int, float, Texture)):
        if not all(abs(float(v) - float(opacity[0])) < 1e-6 for v in opacity):
            raise ValueError(f"<{shader.GetPath()}> has colored opacity; author a scalar preview opacity")
        values["opacity"] = float(opacity[0])
    for name, value in values.items():
        if isinstance(value, Texture):
            expected_color = name in {"diffuseColor", "emissiveColor", "normal"}
            if expected_color != (value.channel == "rgb"):
                raise ValueError(f"<{shader.GetPath()}> has an incompatible texture channel for {name}; bake a preview first")
    return values


def _unique_path(stage, parent, name):
    path = parent.AppendChild(name)
    index = 1
    while stage.GetPrimAtPath(path):
        path = parent.AppendChild(f"{name}_{index}")
        index += 1
    return path


def _write_preview(material, values):
    stage = material.GetPrim().GetStage()
    shader = UsdShade.Shader.Define(stage, _unique_path(stage, material.GetPath(), "PreviewSurface"))
    shader.CreateIdAttr("UsdPreviewSurface")
    color_inputs = {"diffuseColor", "emissiveColor"}
    for name, value in values.items():
        if value is None:
            continue
        kind = Sdf.ValueTypeNames.Color3f if name in color_inputs else (
            Sdf.ValueTypeNames.Normal3f if name == "normal" else Sdf.ValueTypeNames.Float)
        target = shader.CreateInput(name, kind)
        if not isinstance(value, Texture):
            target.Set(value)
            continue
        tex = UsdShade.Shader.Define(stage, _unique_path(stage, material.GetPath(), f"Preview_{name}"))
        tex.CreateIdAttr("UsdUVTexture")
        texture_path = value.file
        target_path = stage.GetEditTarget().GetLayer().realPath
        if target_path and os.path.isabs(target_path) and os.path.isabs(texture_path.path):
            try:
                texture_path = Sdf.AssetPath(os.path.relpath(
                    texture_path.path, os.path.dirname(target_path)).replace("\\", "/"))
            except ValueError:
                pass  # Different Windows drives need the resolved absolute path.
        tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_path)
        tex.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(value.colorspace)
        tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set(value.wrap_s)
        tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set(value.wrap_t)
        tex.CreateInput("fallback", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*value.fallback))
        tex.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*value.scale))
        tex.CreateInput("bias", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(*value.bias))
        uv = UsdShade.Shader.Define(stage, _unique_path(stage, material.GetPath(), f"Preview_{name}_uv"))
        uv.CreateIdAttr("UsdPrimvarReader_float2")
        uv.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        coords = uv.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        if tuple(value.uvscale) != (1.0, 1.0) or tuple(value.uvoffset) != (0.0, 0.0):
            transform = UsdShade.Shader.Define(stage, _unique_path(stage, material.GetPath(), f"Preview_{name}_transform"))
            transform.CreateIdAttr("UsdTransform2d")
            transform.CreateInput("in", Sdf.ValueTypeNames.Float2).ConnectToSource(coords)
            transform.CreateInput("scale", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(*value.uvscale))
            transform.CreateInput("translation", Sdf.ValueTypeNames.Float2).Set(Gf.Vec2f(*value.uvoffset))
            coords = transform.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(coords)
        out_kind = Sdf.ValueTypeNames.Float3 if value.channel == "rgb" else Sdf.ValueTypeNames.Float
        target.ConnectToSource(tex.CreateOutput(value.channel, out_kind))
    material.CreateSurfaceOutput().ConnectToSource(shader.CreateOutput("surface", Sdf.ValueTypeNames.Token))


def cook_stage(stage: Usd.Stage) -> int:
    """Optimize MaterialX materials atomically in the current edit layer."""
    layer = stage.GetEditTarget().GetLayer()
    snapshot = layer.ExportToString()
    try:
        return _cook(stage)
    except Exception:
        layer.ImportFromString(snapshot)
        raise


def _cook(stage):
    plans, removals, context_paths = [], set(), set()
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        material = UsdShade.Material(prim)
        if not material:
            continue
        outputs = materialx_outputs(material)
        if not outputs:
            continue
        if prim.IsInstance() or prim.IsInstanceProxy():
            raise ValueError(f"<{prim.GetPath()}> is an instanced material; repair its source prototype")
        network = _network(stage, [p for o in outputs for p in o.GetAttr().GetConnections()])
        preview = _preview(material)
        universal = material.GetSurfaceOutput()
        if not preview and universal and universal.GetAttr().GetConnections():
            surface, _, _ = material.ComputeSurfaceSource()
            if not surface or surface.GetPath() not in network:
                raise ValueError(f"<{material.GetPath()}> has a different universal surface; preserve it and author an independent preview first")
            # The universal output selects the MaterialX surface being replaced.
            context_paths.add(universal.GetAttr().GetPath())
        values = None if preview else _fallback(material, outputs)
        # Include disconnected MaterialX nodes; shared users are checked below.
        for descendant in Usd.PrimRange(prim):
            shader = UsdShade.Shader(descendant)
            if shader and str(shader.GetIdAttr().Get()).startswith("ND_"):
                owner = descendant.GetParent()
                while owner and not UsdShade.Material(owner):
                    owner = owner.GetParent()
                if owner == prim:
                    network.add(descendant.GetPath())
        if any(not p.HasPrefix(prim.GetPath()) for p in network):
            raise ValueError(f"<{prim.GetPath()}> uses an external MaterialX graph; localize its shaders first")
        removals.update(network)
        context_paths.update(o.GetAttr().GetPath() for o in outputs)
        plans.append((material, outputs, values))

    if not plans:
        return 0
    # Keep dependencies used by surviving outputs, including inputs on other
    # materials. MaterialX shaders shared with those outputs cannot be removed.
    keep = set()
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        if prim.GetPath() in removals:
            continue
        for attr in prim.GetAttributes():
            if attr.GetPath() not in context_paths:
                references = [p for p in attr.GetConnections() if p.GetPrimPath() in removals]
                if references:
                    keep.update(_network(stage, references))
    for path in removals & keep:
        shader = UsdShade.Shader(stage.GetPrimAtPath(path))
        if shader and str(shader.GetIdAttr().Get()).startswith("ND_"):
            raise ValueError(f"<{path}> is shared with a surviving network; author an independent preview first")
    removals -= keep
    for path in removals:
        prim = stage.GetPrimAtPath(path)
        if prim.IsInstanceProxy() or prim.IsInstance():
            raise ValueError(f"<{path}> is an instanced shader; repair its source prototype")
        if any(child.GetPath() not in removals for child in Usd.PrimRange(prim) if child != prim):
            raise ValueError(f"<{path}> contains unrelated scene data; separate its MaterialX graph first")
    for material, outputs, values in plans:
        if values is not None:
            _write_preview(material, values)
        for output in outputs:
            prim, name = output.GetPrim(), output.GetFullName()
            prim.RemoveProperty(name)
            if prim.GetAttribute(name):
                # Block weaker referenced properties without editing their source.
                attr = prim.GetAttribute(name)
                attr.SetConnections([])
                attr.Block()
    for path in sorted(removals, key=lambda p: p.pathElementCount, reverse=True):
        stage.RemovePrim(path)
        if stage.GetPrimAtPath(path):
            stage.OverridePrim(path).SetActive(False)
    return len(plans)
