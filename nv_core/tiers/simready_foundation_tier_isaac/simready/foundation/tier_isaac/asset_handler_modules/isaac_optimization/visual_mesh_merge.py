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
"""Merge the visual meshes a rigid body owns.

usd-optimize 1.4 merges an explicit visual selection, preserving face materials.
Colliders remain separate because merging convex hulls can fill concavities.
The adapter preserves source paths, custom data and large-coordinate precision,
and stages every merge before updating the output.
"""

from __future__ import annotations

from typing import Any

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from . import _primvars

from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations._common import (
    is_rigid_body,
    mergeable_visual_meshes,
    rigid_body_owner,
)

ADAPTER_NAME = "rigid_body_visual_mesh_merge"
ADAPTER_VERSION = "1.0.3"

# Deactivate the sources rather than deleting them: they stay addressable.
_ORIGINAL_GEOM_DEACTIVATE = 2


def merge_groups(stage: Usd.Stage) -> list[tuple[str, list[str]]]:
    """Every (survivor, sources) a body's visual meshes make mergeable."""
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return []

    found = []
    for body in Usd.PrimRange(default_prim, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
        if not is_rigid_body(body):
            continue
        meshes = mergeable_visual_meshes(body)
        if len(meshes) < 2:
            continue
        # The largest keeps its path: it is the one most likely already addressed.
        ordered = sorted(
            meshes,
            key=lambda m: (-len(UsdGeom.Mesh(m).GetFaceVertexCountsAttr().Get() or []), str(m.GetPath())),
        )
        found.append((str(ordered[0].GetPath()), [str(m.GetPath()) for m in ordered[1:]]))
    return found


def _optimizer() -> tuple[Any, Any]:
    """Use usd-optimize >=1.4 with the host's compatible OpenUSD runtime."""
    from usd_optimize.core import ExecutionContext, UsdOptimizeCore

    return UsdOptimizeCore.getInstance(), ExecutionContext()


class MergeFailed(RuntimeError):
    """usd-optimize could not produce one unambiguous merged mesh."""


def _active_mesh_paths(stage: Usd.Stage) -> set[str]:
    return {
        str(prim.GetPath())
        for prim in stage.Traverse()
        if prim.IsActive() and prim.IsA(UsdGeom.Mesh)
    }


def _run_merge(scratch: Usd.Stage, survivor: str, sources: list[str]) -> str:
    core, context = _optimizer()
    context.set_stage(scratch)
    context.generateReport = 0
    context.captureStats = 0
    # Do not call context.remove_stage(): it evicts the stage from the
    # UsdStageCache and invalidates the object we still need to read from.
    before = _active_mesh_paths(scratch)
    ok, detail, created = core.executeOperation(
        "merge",
        context,
        {
            "meshPrimPaths": [survivor, *sources],
            # False allows different materials, preserved as face subsets.
            "considerMaterials": False,
            "originalGeomOption": _ORIGINAL_GEOM_DEACTIVATE,
            "allowSingleMeshes": False,
        },
    )
    if not ok:
        reason = str(detail).strip() if detail is not None else ""
        suffix = f": {reason}" if reason else ""
        raise MergeFailed(f"<{survivor}>: usd-optimize merge failed{suffix}")

    # Native operations may return a list or a path; require one active mesh.
    reported = list(created) if isinstance(created, (list, tuple)) else [created]
    reported = [str(path) for path in reported if path]
    valid_reported = [
        path
        for path in reported
        if (prim := scratch.GetPrimAtPath(Sdf.Path(path)))
        and prim.IsActive()
        and prim.IsA(UsdGeom.Mesh)
    ]
    if len(valid_reported) == 1:
        return str(valid_reported[0])
    if len(valid_reported) > 1:
        raise MergeFailed(
            f"<{survivor}>: usd-optimize reported multiple merged meshes: "
            f"{', '.join(sorted(valid_reported))}"
        )

    # Some merges report no path. The stage diff excludes unrelated/prior results.
    created_paths = sorted(_active_mesh_paths(scratch) - before)
    if len(created_paths) == 1:
        return created_paths[0]
    if not created_paths:
        raise MergeFailed(f"<{survivor}>: usd-optimize produced no merged mesh")
    raise MergeFailed(
        f"<{survivor}>: usd-optimize produced multiple candidate meshes: "
        f"{', '.join(created_paths)}"
    )


def _check_material_purposes(prim: Usd.Prim) -> None:
    for rel in prim.GetRelationships():
        parts = rel.GetName().split(":")
        if parts[:2] != ["material", "binding"] or len(parts) < 3:
            continue
        specific = len(parts) > (4 if parts[2] == "collection" else 2)
        if specific and rel.GetTargets():
            raise MergeFailed(f"<{rel.GetPath()}>: purpose-specific material bindings require a separate merge workflow")


def _preflight(stage: Usd.Stage, groups: list[tuple[str, list[str]]]) -> None:
    """The optimizer operates on static leaf geometry, not animated rigs."""
    for survivor, sources in groups:
        for path in [survivor, *sources]:
            prim = stage.GetPrimAtPath(path)
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                raise MergeFailed(f"<{path}>: a mesh that is itself a rigid body must retain its frame")
            if any(not child.IsA(UsdGeom.Subset) for child in prim.GetChildren()):
                raise MergeFailed(f"<{path}>: non-subset children must remain independently addressable")
            for child in prim.GetChildren():
                _check_material_purposes(child)
            for attr in prim.GetAttributes():
                if _is_geometry(attr.GetName()) and attr.GetNumTimeSamples():
                    raise MergeFailed(f"<{path}>: time-sampled {attr.GetName()} cannot be merged")
            ancestor = prim
            while ancestor and not ancestor.IsPseudoRoot():
                _check_material_purposes(ancestor)
                if 'SkelBindingAPI' in ancestor.GetAppliedSchemas() or ancestor.GetRelationship('skel:skeleton'):
                    raise MergeFailed(f"<{path}>: skinned geometry cannot be merged as static geometry")
                imageable = UsdGeom.Imageable(ancestor)
                if imageable and imageable.GetVisibilityAttr().GetNumTimeSamples():
                    raise MergeFailed(f"<{path}>: animated visibility cannot be merged")
                xform = UsdGeom.Xformable(ancestor)
                if xform and xform.TransformMightBeTimeVarying():
                    raise MergeFailed(f"<{path}>: animated transform cannot be merged")
                ancestor = ancestor.GetParent()


def _normalize_winding(mesh: UsdGeom.Mesh, mirrored: bool) -> None:
    """Keep front faces when native merge bakes a reflection into the points."""
    orientation = mesh.GetOrientationAttr().Get()
    if orientation not in ('leftHanded', 'rightHanded'):
        raise MergeFailed(f'<{mesh.GetPath()}>: invalid mesh orientation {orientation}')
    if (orientation == 'leftHanded') != mirrored:
        permutation = []
        offset = 0
        for count in mesh.GetFaceVertexCountsAttr().Get():
            permutation.extend(reversed(range(offset, offset + count)))
            offset += count
        attributes = [mesh.GetFaceVertexIndicesAttr()]
        if mesh.GetNormalsInterpolation() == 'faceVarying':
            attributes.append(mesh.GetNormalsAttr())
        for pv in UsdGeom.PrimvarsAPI(mesh).GetPrimvars():
            if pv.HasValue() and pv.GetInterpolation() == 'faceVarying':
                attributes.append(pv.GetIndicesAttr() if pv.IsIndexed() else pv.GetAttr())
        for attr in attributes:
            values = attr.Get()
            if values is None:
                continue
            if len(values) != len(permutation):
                raise MergeFailed(f'<{attr.GetPath()}>: values do not match face corners')
            attr.Set([values[index] for index in permutation])
    # Native merge keeps different orientations in separate groups.
    if orientation != 'rightHanded':
        mesh.CreateOrientationAttr().Set('rightHanded')


def _recenter_group(stage: Usd.Stage, survivor: str, sources: list[str]) -> Gf.Matrix4d:
    """Keep float mesh points near their body, including in large world scenes."""
    cache = UsdGeom.XformCache()
    body = rigid_body_owner(stage.GetPrimAtPath(survivor))
    origin = cache.GetLocalToWorldTransform(body).ExtractTranslation()
    offset = Gf.Matrix4d().SetTranslate(-origin)
    for path in [survivor, *sources]:
        prim = stage.GetPrimAtPath(path)
        parent = cache.GetLocalToWorldTransform(prim.GetParent())
        if abs(parent.GetDeterminant()) < 1e-12:
            raise MergeFailed(f"<{path}>: singular parent transform")
        world = cache.GetLocalToWorldTransform(prim)
        _normalize_winding(UsdGeom.Mesh(prim), world.GetDeterminant() < 0)
        local = world * offset * parent.GetInverse()
        xform = UsdGeom.Xformable(prim)
        xform.ClearXformOpOrder()
        xform.AddTransformOp(opSuffix='mergeOrigin').Set(local)
    return Gf.Matrix4d().SetTranslate(origin)


# What the merge itself authors on the survivor. Everything else the survivor
# carried is its own and survives, because Sdf.CopySpec replaces the whole spec
# and would otherwise drop it. Named explicitly rather than pattern-matched, so
# a property is only treated as geometry when we know it is.
_MERGE_AUTHORS = frozenset({
    "points", "faceVertexCounts", "faceVertexIndices", "normals", "extent",
    "velocities", "accelerations", "orientation", "doubleSided",
    "cornerIndices", "cornerSharpnesses", "creaseIndices", "creaseLengths",
    "creaseSharpnesses", "holeIndices", "subdivisionScheme",
    "interpolateBoundary", "faceVaryingLinearInterpolation",
    "triangleSubdivisionRule",
})
_MERGE_AUTHORS_PREFIXES = ("primvars:", "material:binding", "xformOp")


def _is_geometry(name: str) -> bool:
    return name in _MERGE_AUTHORS or name.startswith(_MERGE_AUTHORS_PREFIXES)


def _carried(
    prim: Usd.Prim, flattened_layer: Sdf.Layer
) -> dict[str, Any]:
    """The survivor's non-geometry property specs and prim metadata.

    Keep property specs rather than only resolved values. A value-only copy
    collapses time samples and loses relationships, connections, variability,
    and attribute metadata.
    """
    attribute_values: dict[str, object] = {}
    for attr in prim.GetAuthoredAttributes():
        if _is_geometry(attr.GetName()):
            continue
        attribute_values[attr.GetName()] = attr.Get()

    path = prim.GetPath()
    spec = flattened_layer.GetPrimAtPath(path)
    properties = [
        prop.name for prop in spec.properties if not _is_geometry(prop.name)
    ] if spec else []
    return {
        "layer": flattened_layer,
        "path": path,
        "properties": properties,
        "attribute_values": attribute_values,
        "custom_data": dict(prim.GetCustomData() or {}),
        "api_schemas": spec.GetInfo("apiSchemas")
        if spec and spec.HasInfo("apiSchemas")
        else None,
    }


def _conflicting(
    carried: dict[str, Any], sources: list[Usd.Prim]
) -> set[str]:
    """Drop conflicting survivor metadata that cannot describe all merged faces."""
    dropped: set[str] = set()
    for source in sources:
        if not source:
            continue
        for name, value in carried["attribute_values"].items():
            attr = source.GetAttribute(name)
            if attr and attr.HasAuthoredValue() and attr.Get() != value:
                dropped.add(name)
        source_data = dict(source.GetCustomData() or {})
        for key, value in carried["custom_data"].items():
            if key in source_data and source_data[key] != value:
                dropped.add(key)
    return dropped


def _restore(
    stage: Usd.Stage, path: str, carried: dict[str, Any], dropped: set[str]
) -> None:
    """Restore compatible survivor metadata after replacing its geometry.

    Clear optimizer-selected metadata first so conflicting source values cannot leak.
    """
    layer = stage.GetEditTarget().GetLayer()
    spec = layer.GetPrimAtPath(Sdf.Path(path))
    if spec:
        for name in [prop.name for prop in spec.properties]:
            if not _is_geometry(name):
                del spec.properties[name]
        if spec.HasInfo("customData"):
            spec.ClearInfo("customData")
        if spec.HasInfo("apiSchemas"):
            spec.ClearInfo("apiSchemas")

    target_path = Sdf.Path(path)
    for name in carried["properties"]:
        if name in dropped:
            continue
        Sdf.CopySpec(
            carried["layer"],
            carried["path"].AppendProperty(name),
            layer,
            target_path.AppendProperty(name),
        )

    data = {k: v for k, v in carried["custom_data"].items() if k not in dropped}
    if data:
        stage.GetPrimAtPath(target_path).SetCustomData(data)

    if carried["api_schemas"] is not None and spec:
        spec.SetInfo("apiSchemas", carried["api_schemas"])


def _mask_weaker_geometry(stage: Usd.Stage, path: str, merged: Sdf.PrimSpec) -> None:
    """Mask source geometry omitted by CopySpec in a stronger edit layer."""
    prim = stage.GetPrimAtPath(path)
    authored = {prop.name for prop in merged.properties}
    for attr in prim.GetAuthoredAttributes():
        name = attr.GetName()
        if _is_geometry(name) and not name.startswith("xformOp") and name not in authored:
            attr.Block()
    for rel in prim.GetRelationships():
        if rel.GetName().startswith("material:binding"):
            copied = stage.GetEditTarget().GetLayer().GetRelationshipAtPath(rel.GetPath())
            # Native merge authors additive list ops. Make the copied targets
            # explicit so an old material target cannot compose into the result.
            rel.SetTargets(list(copied.targetPathList.GetAppliedItems()) if copied else [])
    children = {child.name for child in merged.nameChildren}
    for child in prim.GetChildren():
        if child.GetName() not in children:
            child.SetActive(False)
    for child in merged.nameChildren:
        child_path = Sdf.Path(path).AppendChild(child.name)
        stage.OverridePrim(child_path).SetActive(child.active)
        _mask_weaker_geometry(stage, str(child_path), child)


def _partition_material_defaults(stage: Usd.Stage, paths: list[str]) -> None:
    """Keep unbound faces when native merge slices other meshes by material."""
    plans, has_subsets, has_unbound = [], False, False
    for path in paths:
        prim = stage.GetPrimAtPath(path)
        binding = UsdShade.MaterialBindingAPI(prim)
        material, _ = binding.ComputeBoundMaterial()
        count = len(UsdGeom.Mesh(prim).GetFaceVertexCountsAttr().Get())
        uncovered = set(range(count))
        subsets = binding.GetMaterialBindSubsets()
        has_subsets |= bool(subsets)
        resolved_subsets = []
        for subset in subsets:
            uncovered.difference_update(subset.GetIndicesAttr().Get())
            subset_material, _ = UsdShade.MaterialBindingAPI(subset.GetPrim()).ComputeBoundMaterial()
            has_unbound |= not subset_material and bool(subset.GetIndicesAttr().Get())
            resolved_subsets.append((subset, subset_material))
        has_unbound |= not material and bool(uncovered)
        plans.append((prim, material, sorted(uncovered), resolved_subsets))
    if not has_subsets or not has_unbound:
        return
    for prim, material, uncovered, subsets in plans:
        if not material:
            continue
        binding = UsdShade.MaterialBindingAPI.Apply(prim)
        for subset, subset_material in subsets:
            if subset_material:
                UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(subset_material)
        if uncovered:
            name = "mergeDefaultMaterial"
            while prim.GetChild(name):
                name += "_"
            subset = binding.CreateMaterialBindSubset(name, uncovered)
            UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(material)
        prim.RemoveProperty("material:binding")
        if binding.ComputeBoundMaterial()[0]:
            raise MergeFailed(f"<{prim.GetPath()}>: inherited or collection material binding cannot preserve unbound faces")


def cook_stage(input_stage: Usd.Stage, output_stage: Usd.Stage) -> int:
    """Apply the merge transactionally in the staged output's edit layer."""
    layer = output_stage.GetEditTarget().GetLayer()
    before = layer.ExportToString()
    try:
        return _cook_stage(input_stage, output_stage)
    except Exception:
        layer.ImportFromString(before)
        raise


def _cook_stage(input_stage: Usd.Stage, output_stage: Usd.Stage) -> int:
    """Merge every eligible visual-mesh group on ``output_stage``."""
    groups = merge_groups(input_stage)
    if not groups:
        return 0

    _preflight(input_stage, groups)
    preserved_layer = input_stage.Flatten()
    preserved_stage = Usd.Stage.Open(preserved_layer)
    scratch = Usd.Stage.Open(input_stage.Flatten())
    primvar_states = []
    for survivor, sources in groups:
        _partition_material_defaults(scratch, [survivor, *sources])
        try:
            # Materialize inherited values and carry unsupported primvar types.
            primvar_states.append(_primvars.prepare(scratch, [survivor, *sources]))
        except ValueError as error:
            raise MergeFailed(f'<{survivor}>: {error}') from error
    layer = output_stage.GetEditTarget().GetLayer()
    prepared = []
    for (survivor, sources), primvars in zip(groups, primvar_states):
        carried = _carried(
            preserved_stage.GetPrimAtPath(Sdf.Path(survivor)), preserved_layer
        )
        dropped = _conflicting(
            carried, [input_stage.GetPrimAtPath(Sdf.Path(p)) for p in sources]
        )
        origin = _recenter_group(scratch, survivor, sources)
        try:
            created = _run_merge(scratch, survivor, sources)
            _primvars.restore(scratch, created, primvars)
        except ValueError as error:
            raise MergeFailed(f'<{survivor}>: {error}') from error
        # The optimizer may place its output at the stage root or under a
        # different parent. CopySpec moves specs, not coordinate frames.
        world = UsdGeom.Xformable(scratch.GetPrimAtPath(created)).ComputeLocalToWorldTransform(Usd.TimeCode.Default()) * origin
        parent = output_stage.GetPrimAtPath(Sdf.Path(survivor).GetParentPath())
        parent_world = UsdGeom.XformCache().GetLocalToWorldTransform(parent)
        if abs(parent_world.GetDeterminant()) < 1e-12:
            raise MergeFailed(f"<{survivor}>: destination parent has a singular transform")
        prepared.append((survivor, sources, created, world * parent_world.GetInverse(), carried, dropped))

    # Finish every optimizer operation before mutating the destination.
    for survivor, sources, created, local, carried, dropped in prepared:
        Sdf.CreatePrimInLayer(layer, Sdf.Path(survivor))
        Sdf.CopySpec(scratch.GetRootLayer(), Sdf.Path(created), layer, Sdf.Path(survivor))
        layer.GetPrimAtPath(Sdf.Path(survivor)).active = True
        _mask_weaker_geometry(output_stage, survivor, scratch.GetRootLayer().GetPrimAtPath(created))
        xform = UsdGeom.Xformable(output_stage.GetPrimAtPath(survivor))
        xform.ClearXformOpOrder()
        xform.AddTransformOp(opSuffix="mergeFrame").Set(local)
        _restore(output_stage, survivor, carried, dropped)
        for path in sources:
            spec = Sdf.CreatePrimInLayer(layer, Sdf.Path(path))
            spec.specifier = Sdf.SpecifierOver
            spec.active = False
    return len(prepared)
