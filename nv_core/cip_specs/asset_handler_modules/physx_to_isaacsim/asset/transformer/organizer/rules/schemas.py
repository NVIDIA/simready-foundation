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
"""Schema routing rule for organizing USD applied API schemas into separate layers."""

from __future__ import annotations

import fnmatch
import os
from typing import List, Optional

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Sdf, Usd

from . import utils


def ensure_prim_spec_in_layer(layer: Sdf.Layer, path: Sdf.Path, *, specifier=Sdf.SpecifierOver):
    """Ensure a prim spec exists in a layer, creating it if necessary.

    Args:
        param layer: The layer to create the prim spec in.
        param path: Path to the prim.
        param specifier: Specifier type for the prim (default: Over).

    Returns:
        The existing or newly created prim spec.
    """
    prim_spec = layer.GetPrimAtPath(path)
    if prim_spec:
        return prim_spec
    prim_spec = Sdf.CreatePrimInLayer(layer, path)
    prim_spec.specifier = specifier
    return prim_spec


def get_schema_property_namespace(schema_token):
    """Get the property namespace prefix for an applied API schema.

    For single-apply schemas like 'PhysxJointAPI', returns 'physxJoint:'.
    For multi-apply schemas like 'PhysicsDriveAPI:angular', returns 'drive:angular:'.

    Args:
        param schema_token: The API schema token to query.

    Returns:
        The property namespace prefix, or None if not determinable.
    """
    schema_str = str(schema_token)

    # Try to get namespace from schema registry first
    reg = Usd.SchemaRegistry()
    prim_def = reg.FindAppliedAPIPrimDefinition(schema_token)
    if prim_def:
        prop_names = prim_def.GetPropertyNames()
        if prop_names:
            # Extract common prefix from property names
            first_prop = str(prop_names[0])
            if ":" in first_prop:
                # Return the namespace prefix (everything up to and including the last colon before the property name)
                parts = first_prop.rsplit(":", 1)
                if parts[0]:
                    return parts[0] + ":"

    # Fallback: derive namespace from schema name
    # Handle multi-apply schemas like "PhysicsDriveAPI:angular"
    if ":" in schema_str:
        base_schema, instance = schema_str.split(":", 1)
        # Remove "API" suffix and convert to namespace format
        if base_schema.endswith("API"):
            base_name = base_schema[:-3]
            # Convert CamelCase to namespace (e.g., PhysicsDrive -> drive)
            # For Physics schemas, the namespace is typically the last word lowercased
            if base_name.startswith("Physics"):
                namespace = base_name[7:].lower()  # Remove "Physics" prefix
            elif base_name.startswith("Physx"):
                namespace = "physx" + base_name[5:]
            else:
                namespace = base_name[0].lower() + base_name[1:]
            return f"{namespace}:{instance}:"
    else:
        # Single-apply schema like "PhysxJointAPI"
        if schema_str.endswith("API"):
            base_name = schema_str[:-3]
            if base_name.startswith("Physx"):
                # PhysxJointAPI -> physxJoint:
                return base_name[0].lower() + base_name[1:] + ":"
            elif base_name.startswith("Physics"):
                # PhysicsRigidBodyAPI -> physics:
                return "physics:"

    return None


def props_from_applied_api_token(schema_token):
    """Get property names defined by an applied API schema.

    Args:
        param schema_token: The API schema token to query.

    Returns:
        Set of property names defined by the schema, or empty set if not found.
    """
    reg = Usd.SchemaRegistry()
    primDef = reg.FindAppliedAPIPrimDefinition(schema_token)
    return set(primDef.GetPropertyNames()) if primDef else set()


def move_applied_api_schemas(src_spec, dst_spec, schema_tokens):
    """Move multiple applied API schemas from source spec to destination spec.

    Removes the schemas from the source prim spec and adds them to the destination
    prim spec in a single operation. Removes from all lists in source and adds to
    prepended in destination. Preserves any other schemas that remain in the source.

    Args:
        param src_spec: Source prim spec containing the schemas.
        param dst_spec: Destination prim spec to receive the schemas.
        param schema_tokens: List of API schema tokens to move.
    """
    if not schema_tokens:
        return

    schemas_to_move = {str(t) for t in schema_tokens}

    # Get apiSchemas TokenListOp from source
    src_api_schemas = src_spec.GetInfo("apiSchemas")
    if not isinstance(src_api_schemas, Sdf.TokenListOp):
        return

    # Collect all items from source (convert to strings for consistent comparison)
    src_explicit = [str(t) for t in src_api_schemas.explicitItems]
    src_prepended = [str(t) for t in src_api_schemas.prependedItems]
    src_appended = [str(t) for t in src_api_schemas.appendedItems]

    # Find which schemas are actually present in source
    all_src_items = set(src_explicit + src_prepended + src_appended)
    matched_in_src = schemas_to_move & all_src_items
    if not matched_in_src:
        return

    # Get apiSchemas TokenListOp from destination (convert to strings)
    dst_api_schemas = dst_spec.GetInfo("apiSchemas")
    dst_explicit = (
        [str(t) for t in dst_api_schemas.explicitItems] if isinstance(dst_api_schemas, Sdf.TokenListOp) else []
    )
    dst_prepended = (
        [str(t) for t in dst_api_schemas.prependedItems] if isinstance(dst_api_schemas, Sdf.TokenListOp) else []
    )
    dst_appended = (
        [str(t) for t in dst_api_schemas.appendedItems] if isinstance(dst_api_schemas, Sdf.TokenListOp) else []
    )

    # Filter out schemas to move from source lists
    new_src_explicit = [s for s in src_explicit if s not in schemas_to_move]
    new_src_prepended = [s for s in src_prepended if s not in schemas_to_move]
    new_src_appended = [s for s in src_appended if s not in schemas_to_move]

    # Add matched schemas to destination (preserve order from source)
    schemas_to_add = [s for s in (src_explicit + src_prepended + src_appended) if s in matched_in_src]
    for schema_str in schemas_to_add:
        if schema_str not in dst_prepended:
            dst_prepended.append(schema_str)
    # Write destination using prepend
    dst_schemas = dst_prepended + dst_explicit + dst_appended
    if dst_schemas:
        new_dst = Sdf.TokenListOp.Create(prependedItems=dst_schemas)
        dst_spec.SetInfo("apiSchemas", new_dst)

    # Write back source using prepend
    remaining_schemas = new_src_explicit + new_src_prepended + new_src_appended
    if remaining_schemas:
        new_src = Sdf.TokenListOp.Create(prependedItems=remaining_schemas)
        src_spec.SetInfo("apiSchemas", new_src)
    else:
        src_spec.ClearInfo("apiSchemas")


def move_applied_apis_and_props(src_prim, api_schemas, src_layer, dst_layer):
    """Move applied API schemas and their properties from source prim to destination layer.

    Works with the resolved composition arc, moving matching API schemas and their
    associated properties from the source layer to the destination layer.

    Args:
        param src_prim: Source prim from the composed stage.
        param api_schemas: List of schema patterns to match (supports wildcards).
        param src_layer: Source layer containing the schema opinions.
        param dst_layer: Destination layer to receive the schemas.
    """
    prim_path = src_prim.GetPath()
    applied = src_prim.GetAppliedSchemas()

    # Find schemas matching the patterns (to be moved)
    matched = [t for t in applied if any(fnmatch.fnmatch(str(t), s) for s in api_schemas)]
    if not matched:
        return

    # Get source prim spec from source layer
    src_spec = src_layer.GetPrimAtPath(prim_path)
    if not src_spec:
        return

    # Ensure destination prim spec exists
    dst_prim_spec = ensure_prim_spec_in_layer(dst_layer, prim_path)

    # Move all matched schema tokens in a single operation
    move_applied_api_schemas(src_spec, dst_prim_spec, matched)

    # Collect property namespaces for matched schemas
    schema_namespaces = []
    for schema_token in matched:
        namespace = get_schema_property_namespace(schema_token)
        if namespace:
            schema_namespaces.append(namespace)
        # Also get properties from schema registry as fallback
        registry_props = props_from_applied_api_token(schema_token)
        for prop_name in registry_props:
            prop_path = prim_path.AppendProperty(prop_name)
            src_prop_spec = src_layer.GetPropertyAtPath(prop_path)
            if src_prop_spec:
                Sdf.CopySpec(src_layer, prop_path, dst_layer, prop_path)
                if prop_name in src_spec.properties:
                    del src_spec.properties[prop_name]

    # Also move properties by namespace matching (for schemas not in registry)
    if schema_namespaces:
        props_to_move = []
        for prop_name in src_spec.properties.keys():
            prop_str = str(prop_name)
            for namespace in schema_namespaces:
                if prop_str.startswith(namespace):
                    props_to_move.append(prop_str)
                    break

        for prop_name in props_to_move:
            prop_path = prim_path.AppendProperty(prop_name)
            src_prop_spec = src_layer.GetPropertyAtPath(prop_path)
            if src_prop_spec:
                Sdf.CopySpec(src_layer, prop_path, dst_layer, prop_path)
                if prop_name in src_spec.properties:
                    del src_spec.properties[prop_name]


class SchemaRoutingRule(RuleInterface):
    """Route applied API schemas to a separate layer.

    This rule identifies prims with applied API schemas matching specified patterns,
    moves the schema opinions and their associated attributes to a dedicated layer,
    and removes them from the source layer using USD's list editing operations.
    This allows organizing physics schemas, rendering schemas, or other API schemas
    into modular layers that can be selectively loaded.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters for schema patterns and output file.
        """
        return [
            RuleConfigurationParam(
                name="schemas",
                display_name="Schemas",
                param_type=list,
                description="List of applied API schema patterns to route (supports wildcards like 'Physics*')",
                default_value=None,
            ),
            RuleConfigurationParam(
                name="stage_name",
                display_name="Stage Name",
                param_type=str,
                description="Name of the output USD file for the schemas",
                default_value="schemas.usda",
            ),
        ]

    def process_rule(self) -> Optional[str]:
        """Move applied schema opinions to the destination as overrides only.

        Expected args:
            - params.schemas: List of applied schema tokens to route (supports wildcards).
            - params.stage_name: Name of the destination USD file.
            - destination: Logical destination path.

        Returns:
            None (this rule does not change the working stage).
        """
        params = self.args.get("params", {}) or {}
        schemas = params.get("schemas") or []

        if not schemas:
            self.log_operation("No schemas specified, skipping")
            return None

        destination_path = self.destination_path
        stage_name = params.get("stage_name") or "schemas.usda"
        destination_label = os.path.join(destination_path, stage_name)

        self.log_operation(f"SchemaRoutingRule start destination={destination_label}")
        self.log_operation(f"Schema patterns: {', '.join(schemas)}")

        # Resolve output path relative to package root
        schemas_output_path = os.path.join(self.package_root, destination_label)

        # Ensure output directories exist
        os.makedirs(os.path.dirname(schemas_output_path), exist_ok=True)

        # First pass: collect all matching prims and schemas to determine if output file is needed
        root_prim = self.source_stage.GetPseudoRoot()
        matching_items = []  # List of (prim, matched_schemas)

        for prim in Usd.PrimRange(root_prim):
            applied = prim.GetAppliedSchemas()
            matched = [t for t in applied if any(fnmatch.fnmatch(str(t), s) for s in schemas)]
            if matched:
                matching_items.append((prim, matched))

        if not matching_items:
            self.log_operation("No matching schemas found, skipping output file creation")
            return None

        # Open or create schemas layer only if we have matches
        schemas_layer = Sdf.Layer.FindOrOpen(schemas_output_path)
        if not schemas_layer:
            schemas_layer = Sdf.Layer.CreateNew(schemas_output_path)
            utils.copy_stage_metadata(self.source_stage, schemas_layer)
            self.log_operation(f"Created new schemas layer: {schemas_output_path}")
        else:
            self.log_operation(f"Opened existing schemas layer: {schemas_output_path}")

        # Process collected prims
        prims_processed = 0
        schemas_moved = 0

        for prim, matched in matching_items:
            move_applied_apis_and_props(prim, schemas, self.source_stage.GetRootLayer(), schemas_layer)
            prims_processed += 1
            schemas_moved += len(matched)
            self.log_operation(
                f"Moved {len(matched)} schema(s) from {prim.GetPath()}: {', '.join(str(s) for s in matched)}"
            )

        # Set default prim to match source layer
        source_default_prim = self.source_stage.GetRootLayer().defaultPrim
        if source_default_prim:
            schemas_layer.defaultPrim = source_default_prim

        # Save the schemas layer
        schemas_layer.Save()
        self.log_operation(f"Processed {prims_processed} prim(s), moved {schemas_moved} schema instance(s)")

        self.add_affected_stage(destination_label)
        self.log_operation("SchemaRoutingRule completed")

        return None
