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
"""Property routing rule for organizing USD properties by name pattern into separate layers."""

from __future__ import annotations

import os
import re
from typing import List, Optional, Set, Tuple

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Sdf, Usd

from . import utils


def ensure_prim_spec_in_layer(layer: Sdf.Layer, path: Sdf.Path, *, specifier=Sdf.SpecifierOver) -> Sdf.PrimSpec:
    """Ensure a prim spec exists in a layer, creating it if necessary.

    Args:
        layer: The layer to create the prim spec in.
        path: Path to the prim.
        specifier: Specifier type for the prim (default: Over).

    Returns:
        The existing or newly created prim spec.
    """
    prim_spec = layer.GetPrimAtPath(path)
    if prim_spec:
        return prim_spec
    prim_spec = Sdf.CreatePrimInLayer(layer, path)
    prim_spec.specifier = specifier
    return prim_spec


def copy_property_to_layer(
    src_prim: Usd.Prim,
    prop_name: str,
    dst_layer: Sdf.Layer,
) -> bool:
    """Copy a property spec from source prim to destination layer as an override.

    Copies the property from the strongest opinion in the prim stack to the
    destination layer. The destination prim is created as an over if it doesn't exist.

    Args:
        src_prim: Source prim from the composed stage.
        prop_name: Name of the property to copy.
        dst_layer: Destination layer to copy to.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    prim_path = src_prim.GetPath()
    prop_path = prim_path.AppendProperty(prop_name)

    # Ensure destination prim spec exists as an over
    dst_prim_spec = ensure_prim_spec_in_layer(dst_layer, prim_path)
    if not dst_prim_spec:
        return False

    # Skip if property already exists in destination
    if dst_layer.GetPropertyAtPath(prop_path):
        return True

    # Find the strongest opinion for this property in the prim stack
    for spec in src_prim.GetPrimStack():
        if spec.layer == dst_layer:
            continue

        src_prop_spec = spec.layer.GetPropertyAtPath(prop_path)
        if src_prop_spec:
            # Copy the spec to destination (strongest opinion)
            Sdf.CopySpec(spec.layer, prop_path, dst_layer, prop_path)
            return True

    return False


def remove_property_from_source_layers(
    prim: Usd.Prim,
    prop_name: str,
    exclude_layer: Sdf.Layer,
) -> Tuple[int, Set[Sdf.Layer]]:
    """Remove property specs from all layers in the prim stack except the excluded layer.

    Args:
        prim: The prim whose property specs should be removed.
        prop_name: Name of the property to remove.
        exclude_layer: Layer to exclude from removal (typically the destination).

    Returns:
        Tuple of (removed_count, set of modified layers).
    """
    prim_path = prim.GetPath()
    prop_path = prim_path.AppendProperty(prop_name)
    removed_count = 0
    modified_layers = set()

    for spec in prim.GetPrimStack():
        if spec.layer == exclude_layer:
            continue

        try:
            if prop_name in spec.properties:
                del spec.properties[prop_name]
                removed_count += 1
                modified_layers.add(spec.layer)
        except Exception:
            pass

    return removed_count, modified_layers


class PropertyRoutingRule(RuleInterface):
    """Route properties matching name patterns to a separate layer.

    This rule identifies properties with names matching specified regex patterns,
    copies the property specs to a dedicated layer as overrides, and removes the
    property specs from all source layers. This allows organizing specific properties
    (e.g., physics properties, custom attributes) into modular layers.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters for property patterns and output file.
        """
        return [
            RuleConfigurationParam(
                name="properties",
                display_name="Property Patterns",
                param_type=list,
                description="List of regex patterns to match property names (e.g., 'physics:.*', 'custom:.*')",
                default_value=None,
            ),
            RuleConfigurationParam(
                name="stage_name",
                display_name="Stage Name",
                param_type=str,
                description="Name of the output USD file for the properties",
                default_value="properties.usda",
            ),
            RuleConfigurationParam(
                name="scope",
                display_name="Scope",
                param_type=str,
                description="Root path to search for matching properties (default: '/')",
                default_value="/",
            ),
        ]

    def process_rule(self) -> Optional[str]:
        """Move property specs matching patterns to the destination layer as overrides.

        Expected args:
            - params.property_patterns: List of regex patterns to match property names.
            - params.stage_name: Name of the destination USD file.
            - params.scope: Root path to search for properties (default: '/').
            - destination: Logical destination path.

        Returns:
            None (this rule does not change the working stage).
        """
        params = self.args.get("params", {}) or {}
        property_patterns = params.get("properties") or []

        if not property_patterns:
            self.log_operation("No property patterns specified, skipping")
            return None

        # Compile regex patterns
        compiled_patterns = []
        for pattern in property_patterns:
            try:
                compiled_patterns.append(re.compile(pattern))
            except re.error as e:
                self.log_operation(f"Invalid regex pattern '{pattern}': {e}, skipping")

        if not compiled_patterns:
            self.log_operation("No valid property patterns after compilation, skipping")
            return None

        destination_path = self.destination_path
        stage_name = params.get("stage_name") or "properties.usda"
        scope = params.get("scope") or "/"
        destination_label = os.path.join(destination_path, stage_name)

        self.log_operation(f"PropertyRoutingRule start destination={destination_label}")
        self.log_operation(f"Property patterns: {', '.join(property_patterns)}")
        self.log_operation(f"Search scope: {scope}")

        # Resolve output path relative to package root
        properties_output_path = os.path.join(self.package_root, destination_label)

        # Ensure output directories exist
        os.makedirs(os.path.dirname(properties_output_path), exist_ok=True)

        # Get the scope prim to search under
        scope_prim = self.source_stage.GetPrimAtPath(scope)
        if not scope_prim or not scope_prim.IsValid():
            self.log_operation(f"Invalid scope path: {scope}")
            return None

        # First pass: collect all matching properties to determine if output file is needed
        matching_items: List[Tuple[Usd.Prim, str]] = []

        for prim in Usd.PrimRange(scope_prim):
            if not prim.IsValid():
                continue

            for attr in prim.GetAttributes():
                attr_name = attr.GetName()
                if any(pattern.match(attr_name) for pattern in compiled_patterns):
                    if attr.HasAuthoredValue() or attr.GetConnections():
                        matching_items.append((prim, attr_name))

            for rel in prim.GetRelationships():
                rel_name = rel.GetName()
                if any(pattern.match(rel_name) for pattern in compiled_patterns):
                    if rel.HasAuthoredTargets():
                        matching_items.append((prim, rel_name))

        if not matching_items:
            self.log_operation("No matching properties found, skipping output file creation")
            return None

        # Open or create properties layer only if we have matches
        properties_layer = Sdf.Layer.FindOrOpen(properties_output_path)
        if not properties_layer:
            properties_layer = Sdf.Layer.CreateNew(properties_output_path)
            utils.copy_stage_metadata(self.source_stage, properties_layer)
            self.log_operation(f"Created new properties layer: {properties_output_path}")
        else:
            self.log_operation(f"Opened existing properties layer: {properties_output_path}")

        # Process collected matching properties
        properties_processed = 0
        properties_removed = 0
        all_modified_layers: Set[Sdf.Layer] = set()

        # Group by prim for logging
        from collections import defaultdict

        prim_props = defaultdict(list)
        for prim, prop_name in matching_items:
            prim_props[prim.GetPath()].append((prim, prop_name))

        for prim_path, props in prim_props.items():
            self.log_operation(f"Processing prim: {prim_path} ({len(props)} matching properties)")

            for prim, prop_name in props:
                # Copy property to destination layer
                success = copy_property_to_layer(prim, prop_name, properties_layer)
                if success:
                    properties_processed += 1

                    # Remove property specs from source layers
                    removed, modified_layers = remove_property_from_source_layers(prim, prop_name, properties_layer)
                    properties_removed += removed
                    all_modified_layers.update(modified_layers)

                    if removed > 0:
                        self.log_operation(f"  Moved property: {prop_name} (removed from {removed} source layer(s))")
                    else:
                        self.log_operation(f"  Copied property: {prop_name} (no source removal needed)")
                else:
                    self.log_operation(f"  Failed to copy property: {prop_name}")

        # Set default prim to match source layer
        source_default_prim = self.source_stage.GetRootLayer().defaultPrim
        if source_default_prim:
            properties_layer.defaultPrim = source_default_prim

        # Export the properties layer
        properties_layer.Export(properties_layer.identifier)

        # Save all modified source layers
        for layer in all_modified_layers:
            layer.Save()
            self.log_operation(f"Saved modified layer: {layer.identifier}")

        self.log_operation(
            f"Processed {properties_processed} property(s), removed {properties_removed} property spec(s) from source"
        )

        self.add_affected_stage(destination_label)
        self.log_operation("PropertyRoutingRule completed")

        return None
