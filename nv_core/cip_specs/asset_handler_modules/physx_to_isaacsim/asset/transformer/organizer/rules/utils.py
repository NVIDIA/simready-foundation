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
"""Common utility functions for asset transformer rules."""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Tuple

from pxr import Sdf, Usd

# Schema metadata keys to remove from copied attributes
SCHEMA_METADATA_TO_REMOVE: Tuple[str, ...] = ("allowedTokens", "doc", "displayName")


def clear_composition_arcs(prim_spec: Sdf.PrimSpec, make_explicit: bool = False) -> None:
    """Clear all composition arcs from a prim spec.

    Args:
        prim_spec: The prim spec to clear arcs from.
        make_explicit: If True, use ClearEditsAndMakeExplicit to override sublayer arcs.
    """
    arc_lists = [
        prim_spec.referenceList,
        prim_spec.payloadList,
        prim_spec.inheritPathList,
        prim_spec.specializesList,
    ]
    for arc_list in arc_lists:
        if make_explicit:
            arc_list.ClearEditsAndMakeExplicit()
        else:
            arc_list.ClearEdits()


def create_prim_spec(
    layer: Sdf.Layer,
    path: str,
    specifier: Sdf.Specifier = Sdf.SpecifierDef,
    type_name: str = "",
    instanceable: bool = False,
) -> Optional[Sdf.PrimSpec]:
    """Create a prim spec with common settings.

    Args:
        layer: The layer to create the prim in.
        path: The prim path.
        specifier: The specifier (Def, Over, Class).
        type_name: The prim type name.
        instanceable: Whether the prim should be instanceable.

    Returns:
        The created prim spec or None if creation failed.
    """
    prim_spec = Sdf.CreatePrimInLayer(layer, path)
    if prim_spec:
        prim_spec.specifier = specifier
        if type_name:
            prim_spec.typeName = type_name
        if instanceable:
            prim_spec.instanceable = True
    return prim_spec


def get_relative_layer_path(from_layer: Sdf.Layer, to_layer_path: str) -> str:
    """Compute relative path from one layer to another.

    Args:
        from_layer: The layer to compute the path from.
        to_layer_path: Absolute path to the target layer.

    Returns:
        Relative path string.
    """
    from_dir = os.path.dirname(from_layer.identifier)
    return os.path.relpath(to_layer_path, from_dir)


def clear_instanceable_recursive(prim_spec: Sdf.PrimSpec) -> None:
    """Recursively clear the instanceable flag on a prim spec and all its children.

    Args:
        prim_spec: The prim spec to clear instanceable on.
    """
    if prim_spec.instanceable:
        prim_spec.instanceable = False
    for child_spec in prim_spec.nameChildren:
        clear_instanceable_recursive(child_spec)


def clean_schema_metadata(prim_spec: Sdf.PrimSpec) -> None:
    """Clean up schema-level metadata from attributes.

    These are copied by CopySpec but shouldn't be authored on instances.

    Args:
        prim_spec: The prim spec to clean metadata from.
    """
    for attr_name in list(prim_spec.attributes.keys()):
        attr_spec = prim_spec.attributes[attr_name]
        for meta_key in SCHEMA_METADATA_TO_REMOVE:
            if attr_spec.HasInfo(meta_key):
                attr_spec.ClearInfo(meta_key)


def find_ancestor_matching(
    prim: Usd.Prim,
    predicate: Callable[[Usd.Prim], bool],
) -> Optional[Usd.Prim]:
    """Find the first ancestor prim matching a predicate.

    Args:
        prim: The prim to start from (not included in search).
        predicate: Callable that takes a prim and returns True if it matches.

    Returns:
        The first matching ancestor prim, or None if not found.
    """
    ancestor = prim.GetParent()
    while ancestor and ancestor.IsValid():
        if predicate(ancestor):
            return ancestor
        ancestor = ancestor.GetParent()
    return None


def copy_prim_from_composed_stage(
    src_prim: Usd.Prim,
    dst_layer: Sdf.Layer,
    dst_path: str,
    remap_connections_from: Optional[str] = None,
    remap_connections_to: Optional[str] = None,
) -> bool:
    """Copy prim content from composed stage to a layer, handling instance proxies.

    This function reads from the composed stage which can traverse instance proxies,
    unlike Sdf.CopySpec which only works with layer specs. It manually creates
    all prim specs, attributes, relationships, and children.

    Args:
        src_prim: The source prim from the composed stage.
        dst_layer: The destination layer to copy to.
        dst_path: The destination path in the layer.
        remap_connections_from: Optional path prefix to remap connections from.
        remap_connections_to: Optional path prefix to remap connections to.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    if not src_prim.IsValid():
        return False

    # Create the prim spec
    prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
    if not prim_spec:
        return False

    prim_spec.specifier = Sdf.SpecifierDef
    prim_spec.typeName = src_prim.GetTypeName()

    # Copy applied API schemas
    applied_schemas = src_prim.GetAppliedSchemas()
    if applied_schemas:
        prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(applied_schemas)))

    # Copy all authored attributes
    for attr in src_prim.GetAttributes():
        attr_name = attr.GetName()
        # Include attributes that have authored values, connections, or are output ports
        is_output = attr_name.startswith("outputs:")
        if not attr.HasAuthoredValue() and not attr.GetConnections() and not is_output:
            continue

        try:
            attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr.GetTypeName())
            if not attr_spec:
                continue

            # Copy value
            if attr.HasAuthoredValue():
                value = attr.Get()
                if value is not None:
                    attr_spec.default = value

            # Copy variability
            if attr.GetVariability() == Sdf.VariabilityUniform:
                attr_spec.variability = Sdf.VariabilityUniform

            # Copy connections with optional path remapping
            connections = attr.GetConnections()
            if connections:
                for conn in connections:
                    conn_path = conn.pathString
                    if remap_connections_from and remap_connections_to:
                        if conn_path.startswith(remap_connections_from):
                            conn_path = conn_path.replace(remap_connections_from, remap_connections_to, 1)
                    attr_spec.connectionPathList.Prepend(Sdf.Path(conn_path))

            # Copy relevant metadata (skip schema-level metadata)
            for key in attr.GetAllMetadata():
                if key in ("typeName", "default", "variability", "connectionPaths"):
                    continue
                if key in SCHEMA_METADATA_TO_REMOVE:
                    continue
                try:
                    metadata_value = attr.GetMetadata(key)
                    if metadata_value is not None:
                        attr_spec.SetInfo(key, metadata_value)
                except Exception:
                    pass

        except Exception:
            pass

    # Copy relationships
    for rel in src_prim.GetRelationships():
        if not rel.HasAuthoredTargets():
            continue

        try:
            rel_spec = Sdf.RelationshipSpec(prim_spec, rel.GetName())
            if rel_spec:
                for target in rel.GetTargets():
                    target_path = target.pathString
                    if remap_connections_from and remap_connections_to:
                        if target_path.startswith(remap_connections_from):
                            target_path = target_path.replace(remap_connections_from, remap_connections_to, 1)
                    rel_spec.targetPathList.Prepend(Sdf.Path(target_path))
        except Exception:
            pass

    # Recursively copy children (using TraverseInstanceProxies to access instance proxy children)
    for child in src_prim.GetFilteredChildren(Usd.TraverseInstanceProxies()):
        child_name = child.GetName()
        child_dst_path = f"{dst_path}/{child_name}"
        copy_prim_from_composed_stage(child, dst_layer, child_dst_path, remap_connections_from, remap_connections_to)

    return True


def ensure_prim_hierarchy(
    layer: Sdf.Layer,
    prim_path: str,
    default_type: str = "Scope",
) -> None:
    """Ensure the parent hierarchy exists for a given prim path.

    Args:
        layer: The layer to create the hierarchy in.
        prim_path: The full prim path whose parents need to exist.
        default_type: The type to use for created parent prims.
    """
    path = Sdf.Path(prim_path)
    parent_path = path.GetParentPath()

    if parent_path != Sdf.Path.absoluteRootPath:
        parent_spec = layer.GetPrimAtPath(parent_path)
        if not parent_spec:
            ensure_prim_hierarchy(layer, parent_path.pathString, default_type)
            create_prim_spec(layer, parent_path.pathString, type_name=default_type)


def files_are_identical(path1: str, path2: str) -> bool:
    """Check if two files have identical content.

    Args:
        path1: Path to first file.
        path2: Path to second file.

    Returns:
        True if files are identical, False otherwise.
    """
    try:
        if os.path.getsize(path1) != os.path.getsize(path2):
            return False
        with open(path1, "rb") as f1, open(path2, "rb") as f2:
            while True:
                chunk1 = f1.read(8192)
                chunk2 = f2.read(8192)
                if chunk1 != chunk2:
                    return False
                if not chunk1:
                    return True
    except Exception:
        return False


def sanitize_prim_name(name: str, prefix: str = "prim_") -> str:
    """Sanitize a name for use as a USD prim name.

    Args:
        name: The name to sanitize.
        prefix: Prefix to use if name starts with a digit.

    Returns:
        A sanitized name suitable for USD prim paths.
    """
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if not sanitized or sanitized[0].isdigit():
        sanitized = prefix + sanitized
    return sanitized


def copy_stage_metadata(source_stage: Usd.Stage, target_layer: Sdf.Layer) -> None:
    """Copy stage-level metadata from source stage to target layer.

    Copies all layer-level metadata (metersPerUnit, upAxis, timeCodesPerSecond, etc.)
    from the source stage root layer to the target layer.

    Args:
        source_stage: The source stage to copy metadata from.
        target_layer: The layer to copy metadata to.
    """
    source_layer = source_stage.GetRootLayer()
    source_pseudo_root = source_layer.pseudoRoot
    target_pseudo_root = target_layer.pseudoRoot

    # Keys to skip (handled separately or should not be copied)
    skip_keys = frozenset(("defaultPrim", "subLayers", "primChildren"))

    # Copy all metadata from source to target
    for key in source_pseudo_root.ListInfoKeys():
        if key in skip_keys:
            continue
        try:
            value = source_pseudo_root.GetInfo(key)
            if value is not None:
                target_pseudo_root.SetInfo(key, value)
        except Exception:
            pass
