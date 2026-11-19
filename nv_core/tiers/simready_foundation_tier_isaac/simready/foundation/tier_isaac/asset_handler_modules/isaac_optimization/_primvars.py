# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Preserve opaque primvar values through the native mesh merger.

The optimizer slices float primvars but drops several other USD types.
Exact float labels carry opaque values through its own topology/interpolation mapping;
decoding restores their original types without guessing vertex correspondence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pxr import Sdf, Usd, UsdGeom


_NATIVE_TYPES = frozenset({'float',
                           'GfVec2f', 'GfVec2d', 'GfVec3f', 'GfVec3d'})
_VALUE_METADATA = frozenset({'default', 'timeSamples', 'typeName', 'interpolation',
                             'elementSize', 'variability', 'custom'})


@dataclass
class EncodedPrimvar:
    name: str
    type_name: Any
    values: list[list[Any]]
    metadata: dict[str, Any]
    element_size: int


@dataclass
class PrimvarState:
    names: set[str]
    encoded: list[EncodedPrimvar]


def prepare(stage: Usd.Stage, paths: list[str]) -> PrimvarState:
    """Bake inherited values and encode types the native merger cannot carry."""
    layer = stage.GetRootLayer()
    sources = []
    for path in paths:
        prim = stage.GetPrimAtPath(path)
        mapping = {}
        for pv in UsdGeom.PrimvarsAPI(prim).FindPrimvarsWithInheritance():
            if not pv.HasValue():
                continue
            name = str(pv.GetPrimvarName())
            indices = pv.GetIndicesAttr()
            if pv.GetAttr().GetNumTimeSamples() or (indices and indices.GetNumTimeSamples()):
                raise ValueError(f'primvars:{name}: animated values cannot be merged as static geometry')
            if pv.GetAttr().GetPrim() != prim:
                # Inheritance can differ between the source meshes' parents.
                Sdf.CopySpec(layer, pv.GetAttr().GetPath(), layer,
                             prim.GetPath().AppendProperty(pv.GetAttr().GetName()))
                if pv.IsIndexed():
                    indices = pv.GetIndicesAttr()
                    Sdf.CopySpec(layer, indices.GetPath(), layer,
                                 prim.GetPath().AppendProperty(indices.GetName()))
                pv = UsdGeom.PrimvarsAPI(prim).GetPrimvar(name)
            mapping[name] = pv
        sources.append(mapping)

    names = set().union(*(source.keys() for source in sources))
    encoded = []
    for name in sorted(names):
        present = [source[name] for source in sources if name in source]
        type_name = present[0].GetTypeName()
        element_size = present[0].GetElementSize()
        if any(pv.GetTypeName() != type_name or pv.GetElementSize() != element_size for pv in present):
            raise ValueError(f'primvars:{name}: incompatible types or element sizes')
        if type_name.scalarType.type.typeName in _NATIVE_TYPES and element_size == 1:
            continue
        if type_name.role in {'Point', 'Normal', 'Vector'}:
            raise ValueError(f'primvars:{name}: unsupported geometric type {type_name}')
        if len(present) != len(sources):
            raise ValueError(f'primvars:{name}: opaque values must be defined on every merged mesh')
        if any(pv.GetUnauthoredValuesIndex() >= 0 for pv in present):
            raise ValueError(f'primvars:{name}: unauthored indexed values cannot be preserved safely')
        metadata = [{k: v for k, v in pv.GetAttr().GetAllAuthoredMetadata().items()
                     if k not in _VALUE_METADATA} for pv in present]
        if any(item != metadata[0] for item in metadata[1:]):
            raise ValueError(f'primvars:{name}: incompatible attribute metadata')
        values = []
        for pv in present:
            value = pv.Get()
            items = list(value) if type_name.isArray else [value]
            if not items or element_size < 1 or len(items) % element_size:
                raise ValueError(f'primvars:{name}: invalid or empty element blocks')
            blocks = [items[i:i + element_size] for i in range(0, len(items), element_size)]
            if len(values) + len(blocks) > 2**24:
                raise ValueError(f'primvars:{name}: too many values for exact float label transport')
            labels = list(range(len(values), len(values) + len(blocks)))
            values.extend(blocks)
            pv.GetAttr().SetTypeName(Sdf.ValueTypeNames.FloatArray)
            pv.SetElementSize(1)
            pv.Set(labels)
        encoded.append(EncodedPrimvar(name, type_name, values, metadata[0], element_size))
    return PrimvarState(names, encoded)


def restore(stage: Usd.Stage, path: str, state: PrimvarState) -> None:
    """Decode native topology mappings and reject any silently dropped primvar."""
    prim = stage.GetPrimAtPath(path)
    api = UsdGeom.PrimvarsAPI(prim)
    for item in state.encoded:
        pv = api.GetPrimvar(item.name)
        if not pv or not pv.HasValue():
            raise ValueError(f'<{path}>: optimizer dropped primvars:{item.name}')
        labels = pv.ComputeFlattened()
        labels = list(labels) if pv.GetTypeName().isArray else [labels]
        if any(int(label) != label or label < 0 or label >= len(item.values) for label in labels):
            raise ValueError(f'<{path}>: invalid mapping for primvars:{item.name}')
        if pv.GetElementSize() != 1:
            raise ValueError(f'<{path}>: optimizer changed primvars:{item.name} element size')
        values = [value for label in labels for value in item.values[int(label)]]
        scalar = not item.type_name.isArray and pv.GetInterpolation() == 'constant' and len(values) == 1
        pv.GetAttr().SetTypeName(item.type_name if item.type_name.isArray or scalar else item.type_name.arrayType)
        prim.RemoveProperty(pv.GetName() + ':indices')
        pv.SetElementSize(item.element_size)
        pv.Set(values[0] if scalar else values)
        for key, value in item.metadata.items():
            pv.GetAttr().SetMetadata(key, value)
    for name in state.names:
        pv = api.GetPrimvar(name)
        if not pv or not pv.HasValue():
            raise ValueError(f'<{path}>: optimizer dropped primvars:{name}')
