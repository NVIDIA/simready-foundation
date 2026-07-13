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
"""Prim routing rule for organizing USD prims by type into separate layers."""

from __future__ import annotations

import fnmatch
import os
from typing import List, Optional, Set, Tuple

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Sdf, Usd

from . import utils


def merge_list_op(existing_list_op: Optional[Sdf.TokenListOp], new_items: list) -> Sdf.TokenListOp:
    """Merge new items into an existing list op by prepending.

    For non-delete operations, new items are prepended to existing items.
    For delete operations, both lists are combined.

    Args:
        param existing_list_op: Existing list op from destination layer (may be None).
        param new_items: New items from source prim to merge.

    Returns:
        Merged TokenListOp with new items prepended and deletes combined.
    """
    if (
        existing_list_op is None
        or existing_list_op.isExplicit is False
        and not any(
            [
                existing_list_op.prependedItems,
                existing_list_op.appendedItems,
                existing_list_op.deletedItems,
                existing_list_op.explicitItems,
            ]
        )
    ):
        # No existing data, create explicit list with new items
        return Sdf.TokenListOp.CreateExplicit(list(new_items))

    # Extract existing components
    existing_explicit = list(existing_list_op.explicitItems) if existing_list_op.isExplicit else []
    existing_prepended = list(existing_list_op.prependedItems) if existing_list_op.prependedItems else []
    existing_appended = list(existing_list_op.appendedItems) if existing_list_op.appendedItems else []
    existing_deleted = list(existing_list_op.deletedItems) if existing_list_op.deletedItems else []

    new_items_list = list(new_items)

    if existing_explicit:
        # Existing was explicit, prepend new items to it
        merged_explicit = new_items_list + [item for item in existing_explicit if item not in new_items_list]
        return Sdf.TokenListOp.CreateExplicit(merged_explicit)

    # Build merged list op with prepended items
    result = Sdf.TokenListOp()

    # Prepend: new items first, then existing prepended (avoiding duplicates)
    merged_prepended = new_items_list + [item for item in existing_prepended if item not in new_items_list]
    if merged_prepended:
        result.prependedItems = merged_prepended

    # Keep appended items as-is
    if existing_appended:
        result.appendedItems = existing_appended

    # Combine deleted items
    if existing_deleted:
        result.deletedItems = existing_deleted

    return result


def merge_path_list_op(existing_list: Sdf.PathListOp, new_paths: list) -> None:
    """Merge new paths into an existing path list op by prepending.

    Modifies the existing list in place. New paths are prepended, deletes are combined.

    Args:
        param existing_list: Existing path list op to modify in place.
        param new_paths: New paths from source to prepend.
    """
    # Get existing paths to avoid duplicates
    existing_paths = set()
    for path in existing_list.GetAddedOrExplicitItems():
        existing_paths.add(str(path))

    # Prepend new paths (in reverse order since Prepend adds to front)
    for path in reversed(new_paths):
        if str(path) not in existing_paths:
            existing_list.Prepend(path)


def copy_composed_prim_to_layer(src_prim: Usd.Prim, dst_layer: Sdf.Layer, dst_path: Sdf.Path) -> bool:
    """Copy a composed prim from a stage to a destination layer using composed values.

    This function reads the composed values from the stage (which automatically gives
    us the strongest opinions) and writes them to the destination layer. If the
    destination already has a spec at the target path, properties and metadata are
    merged with the following rules:
    - List metadata: new items are prepended, delete lists are combined
    - Non-list values: source prim wins conflicts

    Args:
        param src_prim: Source prim from the composed stage.
        param dst_layer: Destination layer to copy to.
        param dst_path: Destination path in the layer.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    if not src_prim.IsValid():
        return False

    # Check if destination already has a spec at this path
    existing_spec = dst_layer.GetPrimAtPath(dst_path)

    # Collect existing attributes and relationships before modification (for merge)
    existing_attrs = {}
    existing_rels = {}
    existing_variant_selections = {}

    if existing_spec:
        # Preserve existing attribute specs
        for attr_name in existing_spec.attributes.keys():
            attr_spec = existing_spec.attributes[attr_name]
            existing_attrs[attr_name] = {
                "type_name": attr_spec.typeName,
                "default": attr_spec.default if attr_spec.HasInfo("default") else None,
                "variability": attr_spec.variability,
                "connections": list(attr_spec.connectionPathList.GetAddedOrExplicitItems()),
            }
        # Preserve existing relationship specs
        for rel_name in existing_spec.relationships.keys():
            rel_spec = existing_spec.relationships[rel_name]
            existing_rels[rel_name] = list(rel_spec.targetPathList.GetAddedOrExplicitItems())
        # Preserve existing variant selections
        existing_variant_selections = dict(existing_spec.variantSelections)

    # Create or get the prim spec in destination layer
    prim_spec = Sdf.CreatePrimInLayer(dst_layer, dst_path)
    if not prim_spec:
        return False

    # Set basic prim metadata from composed stage (source wins for non-list)
    prim_spec.specifier = Sdf.SpecifierDef
    type_name = src_prim.GetTypeName()
    if type_name:
        prim_spec.typeName = type_name

    # Merge applied API schemas (list operation)
    applied_schemas = src_prim.GetAppliedSchemas()
    if applied_schemas:
        existing_api_schemas = None
        if existing_spec and existing_spec.HasInfo("apiSchemas"):
            existing_api_schemas = existing_spec.GetInfo("apiSchemas")
        merged_schemas = merge_list_op(existing_api_schemas, applied_schemas)
        prim_spec.SetInfo("apiSchemas", merged_schemas)

    # First, copy attribute specs from all layers in the prim stack
    # This ensures we get all authored opinions including those from sublayers
    for spec in src_prim.GetPrimStack():
        for attr_name in spec.attributes.keys():
            src_prop_path = spec.path.AppendProperty(attr_name)
            dst_prop_path = dst_path.AppendProperty(attr_name)
            # Only copy if not already in destination (strongest opinion wins)
            if not dst_layer.GetPropertyAtPath(dst_prop_path):
                Sdf.CopySpec(spec.layer, src_prop_path, dst_layer, dst_prop_path)

    # Now handle composed values for any remaining attributes
    for attr in src_prim.GetAttributes():
        attr_name = attr.GetName()

        # Skip if no authored value or connections
        is_output = attr_name.startswith("outputs:")
        if not attr.HasAuthoredValue() and not attr.GetConnections() and not is_output:
            continue

        try:
            # Get or create attribute spec
            attr_spec = prim_spec.attributes.get(attr_name)
            if not attr_spec:
                # Create if it doesn't exist (shouldn't happen often after CopySpec above)
                attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr.GetTypeName())
                if not attr_spec:
                    continue

                # Clear schema-level metadata that USD automatically adds
                for meta_key in ("doc", "displayName", "allowedTokens"):
                    if attr_spec.HasInfo(meta_key):
                        attr_spec.ClearInfo(meta_key)

            # Set composed value (source wins)
            value = attr.Get()
            if value is not None:
                attr_spec.default = value

            # Copy variability (source wins)
            if attr.GetVariability() == Sdf.VariabilityUniform:
                attr_spec.variability = Sdf.VariabilityUniform

            # Merge connections (prepend source connections)
            connections = attr.GetConnections()
            if connections:
                if attr_name in existing_attrs and existing_attrs[attr_name]["connections"]:
                    # Merge: prepend source connections to existing
                    existing_conns = set(str(c) for c in existing_attrs[attr_name]["connections"])
                    attr_spec.connectionPathList.ClearEditsAndMakeExplicit()
                    # Add source connections first
                    for conn in connections:
                        attr_spec.connectionPathList.Prepend(conn)
                    # Then add existing connections that weren't in source
                    for conn in existing_attrs[attr_name]["connections"]:
                        if str(conn) not in [str(c) for c in connections]:
                            attr_spec.connectionPathList.Prepend(conn)
                else:
                    attr_spec.connectionPathList.ClearEditsAndMakeExplicit()
                    for conn in connections:
                        attr_spec.connectionPathList.Prepend(conn)

        except Exception:
            pass

    # Restore existing attributes that weren't in source (merge: preserve destination-only attrs)
    for attr_name, attr_data in existing_attrs.items():
        if attr_name not in prim_spec.attributes:
            try:
                attr_spec = Sdf.AttributeSpec(prim_spec, attr_name, attr_data["type_name"])
                if attr_spec:
                    if attr_data["default"] is not None:
                        attr_spec.default = attr_data["default"]
                    attr_spec.variability = attr_data["variability"]
                    for conn in attr_data["connections"]:
                        attr_spec.connectionPathList.Prepend(conn)
            except Exception:
                pass

    # Copy relationships with their targets (merge with existing)
    for rel in src_prim.GetRelationships():
        if not rel.HasAuthoredTargets():
            continue

        try:
            rel_name = rel.GetName()
            rel_spec = prim_spec.relationships.get(rel_name)
            if not rel_spec:
                rel_spec = Sdf.RelationshipSpec(prim_spec, rel_name)

            if rel_spec:
                source_targets = rel.GetTargets()
                if rel_name in existing_rels and existing_rels[rel_name]:
                    # Merge: prepend source targets, keep existing unique targets
                    existing_target_strs = set(str(t) for t in existing_rels[rel_name])
                    source_target_strs = set(str(t) for t in source_targets)
                    rel_spec.targetPathList.ClearEditsAndMakeExplicit()
                    # Source targets first
                    for target in source_targets:
                        rel_spec.targetPathList.Prepend(target)
                    # Existing targets not in source
                    for target in existing_rels[rel_name]:
                        if str(target) not in source_target_strs:
                            rel_spec.targetPathList.Prepend(target)
                else:
                    for target in source_targets:
                        rel_spec.targetPathList.Prepend(target)
        except Exception:
            pass

    # Restore existing relationships that weren't in source
    for rel_name, targets in existing_rels.items():
        if rel_name not in prim_spec.relationships:
            try:
                rel_spec = Sdf.RelationshipSpec(prim_spec, rel_name)
                if rel_spec:
                    for target in targets:
                        rel_spec.targetPathList.Prepend(target)
            except Exception:
                pass

    # Copy important prim metadata (source wins for non-list)
    metadata_to_copy = ["kind", "instanceable", "active", "hidden"]
    for key in metadata_to_copy:
        if src_prim.HasMetadata(key):
            try:
                value = src_prim.GetMetadata(key)
                if value is not None:
                    prim_spec.SetInfo(key, value)
            except Exception:
                pass

    # Merge variant selections (source wins for conflicts, preserve existing unique keys)
    for vset_name, selection in existing_variant_selections.items():
        if vset_name not in prim_spec.variantSelections:
            prim_spec.variantSelections[vset_name] = selection

    variant_sets = src_prim.GetVariantSets()
    for vset_name in variant_sets.GetNames():
        vset = variant_sets.GetVariantSet(vset_name)
        if vset:
            selection = vset.GetVariantSelection()
            if selection:
                prim_spec.variantSelections[vset_name] = selection

    # Clean schema-level metadata from all attributes
    utils.clean_schema_metadata(prim_spec)

    # Recursively copy/merge children
    for child in src_prim.GetFilteredChildren(Usd.TraverseInstanceProxies()):
        child_name = child.GetName()
        child_dst_path = dst_path.AppendChild(child_name)
        copy_composed_prim_to_layer(child, dst_layer, child_dst_path)

    return True


def remove_prim_from_source_layers(prim: Usd.Prim, exclude_layer: Sdf.Layer) -> tuple:
    """Remove prim specs and all property specs from all layers in the prim stack except the excluded layer.

    This function ensures complete eradication of the prim by:
    1. Explicitly deleting all property specs (attributes and relationships) from each prim spec
    2. Clearing apiSchemas metadata from each prim spec
    3. Deleting the prim spec itself from the layer

    This is necessary because property specs can exist as overrides in layers (like robot_schema.usda)
    even when the prim is being moved elsewhere. Simply deleting the prim spec may leave orphaned
    property specs behind.

    Args:
        param prim: The prim whose specs should be removed.
        param exclude_layer: Layer to exclude from removal (typically the destination).

    Returns:
        Tuple of (removed_count, set of modified layers).
    """
    prim_path = prim.GetPath()
    removed_count = 0
    modified_layers = set()

    # Iterate through prim stack and remove specs
    for spec in prim.GetPrimStack():
        if spec.layer == exclude_layer:
            continue

        # Remove this prim spec from its layer
        try:
            layer = spec.layer

            # First, explicitly delete all property specs from this prim spec
            # This handles cases where properties were authored as overrides (e.g., from SchemaRoutingRule)
            for prop_name in list(spec.properties.keys()):
                del spec.properties[prop_name]

            # Then delete the prim spec itself (this also removes apiSchemas and other metadata)
            parent_spec = layer.GetPrimAtPath(prim_path.GetParentPath())
            if parent_spec and spec.name in parent_spec.nameChildren:
                del parent_spec.nameChildren[spec.name]
                removed_count += 1
                modified_layers.add(layer)
        except Exception:
            pass

    return removed_count, modified_layers


class PrimRoutingRule(RuleInterface):
    """Route prims matching type patterns to a separate layer.

    This rule identifies prims with types matching specified patterns (supporting wildcards),
    copies the complete composed prim definition to a dedicated layer, and removes the prim
    specs from all source layers. This allows organizing physics prims, render prims, or other
    typed prims into modular layers that can be selectively loaded.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters for prim type patterns and output file.
        """
        return [
            RuleConfigurationParam(
                name="prim_types",
                display_name="Prim Types",
                param_type=list,
                description="List of prim type patterns to route (supports wildcards like 'Physics*')",
                default_value=None,
            ),
            RuleConfigurationParam(
                name="stage_name",
                display_name="Stage Name",
                param_type=str,
                description="Name of the output USD file for the prims",
                default_value="prims.usda",
            ),
            RuleConfigurationParam(
                name="scope",
                display_name="Scope",
                param_type=str,
                description="Root path to search for matching prims (default: '/')",
                default_value="/",
            ),
        ]

    def process_rule(self) -> Optional[str]:
        """Move complete prim definitions to the destination layer.

        Expected args:
            - params.prim_types: List of prim type patterns to route (supports wildcards).
            - params.stage_name: Name of the destination USD file.
            - params.scope: Root path to search for prims (default: '/').
            - destination: Logical destination path.

        Returns:
            None (this rule does not change the working stage).
        """
        params = self.args.get("params", {}) or {}
        prim_types = params.get("prim_types") or []

        if not prim_types:
            self.log_operation("No prim types specified, skipping")
            return None

        destination_path = self.destination_path
        stage_name = params.get("stage_name") or "prims.usda"
        scope = params.get("scope") or "/"
        destination_label = os.path.join(destination_path, stage_name)

        self.log_operation(f"PrimRoutingRule start destination={destination_label}")
        self.log_operation(f"Prim type patterns: {', '.join(prim_types)}")
        self.log_operation(f"Search scope: {scope}")

        # Resolve output path relative to package root
        prims_output_path = os.path.join(self.package_root, destination_label)

        # Ensure output directories exist
        os.makedirs(os.path.dirname(prims_output_path), exist_ok=True)

        # Get the scope prim to search under
        scope_prim = self.source_stage.GetPrimAtPath(scope)
        if not scope_prim or not scope_prim.IsValid():
            self.log_operation(f"Invalid scope path: {scope}")
            return None

        # Collect all matching prims first (to avoid iterator invalidation when removing)
        matching_prims = []
        for prim in Usd.PrimRange(scope_prim):
            # Check if this prim's type matches any pattern
            prim_type = prim.GetTypeName()
            if not prim_type:
                continue

            matched = any(fnmatch.fnmatch(str(prim_type), pattern) for pattern in prim_types)
            if matched:
                matching_prims.append((prim.GetPath(), prim_type))

        if not matching_prims:
            self.log_operation("No matching prims found, skipping output file creation")
            return None

        # Open or create prims layer only if we have matches
        prims_layer = Sdf.Layer.FindOrOpen(prims_output_path)
        if not prims_layer:
            prims_layer = Sdf.Layer.CreateNew(prims_output_path)
            utils.copy_stage_metadata(self.source_stage, prims_layer)
            self.log_operation(f"Created new prims layer: {prims_output_path}")
        else:
            self.log_operation(f"Opened existing prims layer: {prims_output_path}")

        # Process collected prims
        prims_processed = 0
        prims_removed = 0
        all_modified_layers = set()

        for prim_path, prim_type in matching_prims:
            # Re-fetch the prim (in case stage has changed)
            prim = self.source_stage.GetPrimAtPath(prim_path)
            if not prim or not prim.IsValid():
                continue

            self.log_operation(f"Processing prim: {prim_path} (type: {prim_type})")

            # Copy the composed prim to destination layer
            success = copy_composed_prim_to_layer(prim, prims_layer, prim_path)
            if success:
                prims_processed += 1
                self.log_operation(f"Copied composed prim: {prim_path}")

                # Remove prim specs from source layers
                removed, modified_layers = remove_prim_from_source_layers(prim, prims_layer)
                prims_removed += removed
                all_modified_layers.update(modified_layers)
                if removed > 0:
                    self.log_operation(f"Removed {removed} prim spec(s) from source layers")
                else:
                    self.log_operation(
                        f"WARNING: Failed to remove prim specs for {prim_path} - may result in duplicates"
                    )
            else:
                self.log_operation(f"Failed to copy prim: {prim_path}")

        # Set default prim to match source layer
        source_default_prim = self.source_stage.GetRootLayer().defaultPrim
        if source_default_prim:
            prims_layer.defaultPrim = source_default_prim

        # Export the prims layer (Export does a clean serialization)
        prims_layer.Export(prims_layer.identifier)

        # Save all modified source layers (schemas layer, etc.)
        for layer in all_modified_layers:
            layer.Save()
            self.log_operation(f"Saved modified layer: {layer.identifier}")
        self.log_operation(f"Processed {prims_processed} prim(s), removed {prims_removed} prim spec(s) from source")

        self.add_affected_stage(destination_label)
        self.log_operation("PrimRoutingRule completed")

        return None
