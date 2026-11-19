# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Reject staged geometry or physics mutations.

Metadata conformance is only allowed to touch provenance, authored asset paths,
and a thumbnail file. Digesting every protected opinion before and after the run
turns that promise into something checkable, so a bug that silently rewrites a
mesh or a rigid body is caught before the staged package is promoted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pxr import Sdf

USD_LAYER_SUFFIXES = frozenset({".usd", ".usda", ".usdc"})
GEOMETRY_TYPES = frozenset(
    {
        "BasisCurves",
        "Capsule",
        "Cone",
        "Cube",
        "Cylinder",
        "HermiteCurves",
        "Mesh",
        "NurbsCurves",
        "NurbsPatch",
        "Plane",
        "PointInstancer",
        "Points",
        "Sphere",
    }
)
GEOMETRY_PROPERTIES = frozenset(
    {
        "accelerations",
        "angularVelocities",
        "axis",
        "cornerIndices",
        "cornerSharpnesses",
        "curveVertexCounts",
        "doubleSided",
        "extent",
        "faceVaryingLinearInterpolation",
        "faceVertexCounts",
        "faceVertexIndices",
        "height",
        "holeIndices",
        "interpolateBoundary",
        "normals",
        "orientation",
        "points",
        "primvars:displayColor",
        "primvars:displayOpacity",
        "protoIndices",
        "positions",
        "radius",
        "size",
        "subdivisionScheme",
        "velocities",
        "widths",
    }
)
PHYSICS_SCHEMA_MARKERS = ("Physics", "Physx")


def _walk_prim_specs(prim_spec: Sdf.PrimSpec):
    yield prim_spec
    for child in prim_spec.nameChildren:
        yield from _walk_prim_specs(child)
    for variant_set in prim_spec.variantSets.values():
        for variant in variant_set.variants.values():
            yield from _walk_prim_specs(variant.primSpec)


def _stable_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "explicitItems") or type(value).__name__.endswith("ListOp"):
        return {
            field: [
                _stable_value(item) for item in list(getattr(value, field, ()) or ())
            ]
            for field in (
                "explicitItems",
                "prependedItems",
                "appendedItems",
                "addedItems",
                "deletedItems",
                "orderedItems",
            )
        }
    if isinstance(value, Path):
        return str(value)
    identifier = getattr(value, "pathString", None) or getattr(value, "path", None)
    if isinstance(identifier, str):
        return identifier
    if hasattr(value, "__iter__") and not isinstance(value, (bytes, dict)):
        try:
            return [_stable_value(item) for item in list(value)]
        except TypeError:
            return str(value)
    return str(value)


def _serialized_info(spec: Sdf.Spec) -> dict[str, Any]:
    return {
        key: _stable_value(spec.GetInfo(key))
        for key in sorted(spec.ListInfoKeys())
        if key not in {"customData", "documentation", "displayGroup", "displayName"}
    }


def _api_schemas(prim_spec: Sdf.PrimSpec) -> tuple[str, ...]:
    if not prim_spec.HasInfo("apiSchemas"):
        return ()
    schemas = prim_spec.GetInfo("apiSchemas")
    values: list[str] = []
    for field in (
        "explicitItems",
        "prependedItems",
        "appendedItems",
        "addedItems",
        "deletedItems",
        "orderedItems",
    ):
        values.extend(str(item) for item in getattr(schemas, field, ()))
    return tuple(sorted(values))


def _is_physics_name(name: str) -> bool:
    return name.startswith("physics:") or name.startswith("physx")


def _is_physics_type(type_name: str) -> bool:
    return any(marker in type_name for marker in PHYSICS_SCHEMA_MARKERS)


def _is_physics_schema(schema: str) -> bool:
    return any(marker in schema for marker in PHYSICS_SCHEMA_MARKERS)


def _protected_layer_opinions(
    layer_path: Path, package_root: Path
) -> list[dict[str, Any]]:
    layer = Sdf.Layer.FindOrOpen(str(layer_path))
    if layer is None:
        raise ValueError(f"Failed to open USD layer: {layer_path}")
    opinions: list[dict[str, Any]] = []
    for root_prim in layer.rootPrims:
        for prim_spec in _walk_prim_specs(root_prim):
            type_name = prim_spec.typeName
            api_schemas = _api_schemas(prim_spec)
            protected_properties = {}
            for prop_spec in prim_spec.properties:
                name = prop_spec.name
                if not (_is_physics_name(name) or name in GEOMETRY_PROPERTIES):
                    continue
                protected_properties[name] = _serialized_info(prop_spec)
            protected_type = type_name in GEOMETRY_TYPES or _is_physics_type(type_name)
            protected_schemas = tuple(
                schema for schema in api_schemas if _is_physics_schema(schema)
            )
            if not (protected_type or protected_schemas or protected_properties):
                continue
            opinions.append(
                {
                    "layer": layer_path.relative_to(package_root).as_posix(),
                    "path": str(prim_spec.path),
                    "type": type_name if protected_type else "",
                    "schemas": protected_schemas,
                    "properties": protected_properties,
                }
            )
    return opinions


def protected_stage_digest(
    asset_path: Path, package_root: Path | None = None
) -> str:
    """Digest every authored geometry and physics opinion in the package."""
    asset = Path(asset_path).resolve()
    package = Path(package_root).resolve() if package_root else asset.parent.parent
    opinions: list[dict[str, Any]] = []
    for layer_path in sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and path.suffix.lower() in USD_LAYER_SUFFIXES
    ):
        opinions.extend(_protected_layer_opinions(layer_path.resolve(), package))
    encoded = json.dumps(opinions, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit_mutation(
    before_digest: str, asset_path: Path, package_root: Path | None = None
) -> dict[str, Any]:
    after = protected_stage_digest(asset_path, package_root)
    return {
        "passed": before_digest == after,
        "before_digest": before_digest,
        "after_digest": after,
        "policy": "authored package-local geometry and physics are immutable",
    }
