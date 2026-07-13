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
from __future__ import annotations

import os
from typing import List, Optional, Tuple, Union

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Sdf, Usd

from . import utils

# Default configuration
_DEFAULT_DESTINATION: str = "payloads"


class VariantRoutingRule(RuleInterface):
    """Route variant set contents to separate layer files.

    This rule extracts each variant from the default prim's variant sets into
    individual USDA files organized by variant set folder. If a variant contains
    prepended payloads or references, the contents of those referenced assets
    are inlined (flattened) into the output layer. The variant's own deltas
    (attributes, relationships, child prims) are then applied on top.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters.
        """
        return [
            RuleConfigurationParam(
                name="variant_sets",
                display_name="Variant Sets",
                param_type=list,
                description="Optional list of variant set names to process. If empty, all variant sets are processed.",
                default_value=[],
            ),
        ]

    def _get_prepended_arcs(self, variant_spec: Sdf.VariantSpec) -> Tuple[List[Sdf.Payload], List[Sdf.Reference]]:
        """Extract prepended payloads and references from a variant spec.

        Args:
            variant_spec: The variant spec to inspect.

        Returns:
            Tuple of (prepended_payloads, prepended_references).
        """
        prepended_payloads: List[Sdf.Payload] = []
        prepended_references: List[Sdf.Reference] = []

        prim_spec = variant_spec.primSpec
        if not prim_spec:
            return prepended_payloads, prepended_references

        # Check for prepended payloads
        if prim_spec.hasPayloads:
            payload_list = prim_spec.payloadList
            prepended_payloads = list(payload_list.prependedItems)

        # Check for prepended references
        if prim_spec.hasReferences:
            ref_list = prim_spec.referenceList
            prepended_references = list(ref_list.prependedItems)

        return prepended_payloads, prepended_references

    def _apply_prim_spec_deltas(
        self,
        src_spec: Sdf.PrimSpec,
        dest_layer: Sdf.Layer,
        dest_path: str,
        skip_composition_arcs: bool = True,
    ) -> None:
        """Apply prim spec deltas on top of existing content in destination layer.

        This merges the source spec's opinions into the destination, creating
        or updating prims, attributes, and relationships.

        Args:
            src_spec: The source prim spec with deltas to apply.
            dest_layer: The destination layer.
            dest_path: The destination prim path.
            skip_composition_arcs: If True, skip copying payloads/references from the spec.
        """
        dest_prim_spec = dest_layer.GetPrimAtPath(dest_path)
        if not dest_prim_spec:
            dest_prim_spec = Sdf.CreatePrimInLayer(dest_layer, dest_path)
            if not dest_prim_spec:
                return
            dest_prim_spec.specifier = Sdf.SpecifierDef

        # Update type if authored
        if src_spec.typeName:
            dest_prim_spec.typeName = src_spec.typeName

        # Merge applied API schemas
        if src_spec.HasInfo("apiSchemas"):
            src_schemas = src_spec.GetInfo("apiSchemas")
            if dest_prim_spec.HasInfo("apiSchemas"):
                existing = set(dest_prim_spec.GetInfo("apiSchemas").GetAddedOrExplicitItems())
                new_schemas = list(existing.union(set(src_schemas.GetAddedOrExplicitItems())))
                dest_prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(new_schemas))
            else:
                dest_prim_spec.SetInfo("apiSchemas", src_schemas)

        # Copy metadata (excluding composition-related)
        skip_keys = {
            "specifier",
            "typeName",
            "apiSchemas",
            "references",
            "payloads",
            "inherits",
            "specializes",
            "variantSets",
            "variantSelection",
        }
        for key in src_spec.ListInfoKeys():
            if key in skip_keys:
                continue
            try:
                value = src_spec.GetInfo(key)
                if value is not None:
                    dest_prim_spec.SetInfo(key, value)
            except Exception:
                pass

        # Apply attribute deltas
        for attr_name in src_spec.attributes.keys():
            attr_spec = src_spec.attributes[attr_name]
            dest_attr = dest_prim_spec.attributes.get(attr_name)
            if not dest_attr:
                try:
                    dest_attr = Sdf.AttributeSpec(dest_prim_spec, attr_name, attr_spec.typeName)
                except Exception:
                    continue

            if dest_attr:
                if attr_spec.HasDefaultValue():
                    dest_attr.default = attr_spec.default
                if attr_spec.variability != Sdf.VariabilityVarying:
                    dest_attr.variability = attr_spec.variability

                if attr_spec.connectionPathList.GetAddedOrExplicitItems():
                    for conn in attr_spec.connectionPathList.GetAddedOrExplicitItems():
                        dest_attr.connectionPathList.Prepend(conn)

        # Apply relationship deltas
        for rel_name in src_spec.relationships.keys():
            rel_spec = src_spec.relationships[rel_name]
            dest_rel = dest_prim_spec.relationships.get(rel_name)
            if not dest_rel:
                try:
                    dest_rel = Sdf.RelationshipSpec(dest_prim_spec, rel_name)
                except Exception:
                    continue

            if dest_rel:
                for target in rel_spec.targetPathList.GetAddedOrExplicitItems():
                    dest_rel.targetPathList.Prepend(target)

        # Copy composition arcs if not skipping (for child prims)
        if not skip_composition_arcs:
            if src_spec.hasReferences:
                for ref in src_spec.referenceList.prependedItems:
                    dest_prim_spec.referenceList.Prepend(ref)
                for ref in src_spec.referenceList.appendedItems:
                    dest_prim_spec.referenceList.Append(ref)

            if src_spec.hasPayloads:
                for payload in src_spec.payloadList.prependedItems:
                    dest_prim_spec.payloadList.Prepend(payload)
                for payload in src_spec.payloadList.appendedItems:
                    dest_prim_spec.payloadList.Append(payload)

        # Recursively apply child prim deltas (children don't skip composition arcs)
        for child_name in src_spec.nameChildren.keys():
            child_spec = src_spec.nameChildren[child_name]
            child_dest_path = f"{dest_path}/{child_name}"
            self._apply_prim_spec_deltas(child_spec, dest_layer, child_dest_path, skip_composition_arcs=False)

    def _resolve_asset_path(self, arc_asset_path: str) -> str:
        """Resolve an asset path, trying multiple base directories.

        Asset paths may be relative to either the working stage (after remapping
        by _collect_assets) or the original source file. This method tries both.

        Args:
            arc_asset_path: The asset path from a composition arc.

        Returns:
            Resolved absolute path or empty string if not resolvable.
        """
        if not arc_asset_path:
            return ""

        # If already absolute, check if it exists
        if os.path.isabs(arc_asset_path):
            if os.path.isfile(arc_asset_path):
                self.log_operation(f"Resolved absolute path: {arc_asset_path}")
                return arc_asset_path
            return ""

        # Try 1: Resolve relative to working stage root layer (paths may be remapped)
        layer_dir = os.path.dirname(self.source_stage.GetRootLayer().realPath)
        resolved = os.path.normpath(os.path.join(layer_dir, arc_asset_path))
        if os.path.isfile(resolved):
            self.log_operation(f"Resolved relative to working stage: {arc_asset_path} -> {resolved}")
            return resolved

        # Try 2: Resolve relative to original input stage path
        input_stage_path = self.args.get("input_stage_path", "")
        if input_stage_path:
            input_dir = os.path.dirname(input_stage_path)
            resolved = os.path.normpath(os.path.join(input_dir, arc_asset_path))
            if os.path.isfile(resolved):
                self.log_operation(f"Resolved relative to original source: {arc_asset_path} -> {resolved}")
                return resolved

        self.log_operation(
            f"Failed to resolve path '{arc_asset_path}' from layer_dir={layer_dir} or input_dir={input_stage_path}"
        )
        return ""

    def _clear_inlined_composition_arcs(
        self,
        dest_layer: Sdf.Layer,
        dest_prim_path: str,
        inlined_payloads: List[Sdf.Payload],
        inlined_references: List[Sdf.Reference],
    ) -> None:
        """Clear prepended payloads/references that were inlined from the destination prim.

        After inlining content from prepended arcs, those arcs should be removed from
        the destination since their content is now directly present.

        Args:
            dest_layer: The destination layer.
            dest_prim_path: Path to the destination prim.
            inlined_payloads: List of payloads whose content was inlined.
            inlined_references: List of references whose content was inlined.
        """
        if not inlined_payloads and not inlined_references:
            return

        dest_prim_spec = dest_layer.GetPrimAtPath(dest_prim_path)
        if not dest_prim_spec:
            return

        # Build sets of asset paths that were inlined
        inlined_payload_paths = {p.assetPath for p in inlined_payloads if p.assetPath}
        inlined_ref_paths = {r.assetPath for r in inlined_references if r.assetPath}

        # Clear prepended payloads that match inlined paths
        if inlined_payload_paths and dest_prim_spec.hasPayloads:
            payload_list = dest_prim_spec.payloadList
            current_prepended = list(payload_list.prependedItems)
            current_appended = list(payload_list.appendedItems)

            # Filter out payloads whose asset paths were inlined
            new_prepended = [p for p in current_prepended if p.assetPath not in inlined_payload_paths]

            if len(new_prepended) < len(current_prepended):
                payload_list.ClearEdits()
                for p in new_prepended:
                    payload_list.Prepend(p)
                for p in current_appended:
                    payload_list.Append(p)
                removed_count = len(current_prepended) - len(new_prepended)
                self.log_operation(f"Cleared {removed_count} inlined payloads from destination")

        # Clear prepended references that match inlined paths
        if inlined_ref_paths and dest_prim_spec.hasReferences:
            ref_list = dest_prim_spec.referenceList
            current_prepended = list(ref_list.prependedItems)
            current_appended = list(ref_list.appendedItems)

            # Filter out references whose asset paths were inlined
            new_prepended = [r for r in current_prepended if r.assetPath not in inlined_ref_paths]

            if len(new_prepended) < len(current_prepended):
                ref_list.ClearEdits()
                for r in new_prepended:
                    ref_list.Prepend(r)
                for r in current_appended:
                    ref_list.Append(r)
                removed_count = len(current_prepended) - len(new_prepended)
                self.log_operation(f"Cleared {removed_count} inlined references from destination")

    def _process_variant(
        self,
        variant_set_spec: Sdf.VariantSetSpec,
        variant_name: str,
        variant_set_output_dir: str,
        source_layer: Sdf.Layer,
        default_prim_path: str,
    ) -> Optional[str]:
        """Process a single variant and write it to a USDA file.

        If the variant has prepended payloads or references, the contents of those
        referenced assets are inlined (copied) into the output layer. Then the
        remaining deltas from the variant spec are applied on top. The prepended
        arcs themselves are NOT added to the output.

        Args:
            variant_set_spec: The variant set spec containing the variant.
            variant_name: Name of the variant to process.
            variant_set_output_dir: Output directory for this variant set.
            source_layer: The source layer containing the variant.
            default_prim_path: Path to the default prim.

        Returns:
            Path to the created variant layer file, or None if processing failed.
        """
        variant_spec = variant_set_spec.variants.get(variant_name)
        if not variant_spec:
            self.log_operation(f"Variant '{variant_name}' not found in variant set")
            return None

        # Create output file path
        sanitized_name = utils.sanitize_prim_name(variant_name)
        variant_file_path = os.path.join(variant_set_output_dir, f"{sanitized_name}.usda")

        self.log_operation(f"Processing variant '{variant_name}' -> {variant_file_path}")

        # Get prepended arcs
        prepended_payloads, prepended_references = self._get_prepended_arcs(variant_spec)
        self.log_operation(
            f"Found {len(prepended_payloads)} prepended payloads, {len(prepended_references)} prepended references"
        )
        for p in prepended_payloads:
            self.log_operation(f"  Payload: assetPath={p.assetPath}, primPath={p.primPath}")
        for r in prepended_references:
            self.log_operation(f"  Reference: assetPath={r.assetPath}, primPath={r.primPath}")

        # Create the variant layer
        os.makedirs(os.path.dirname(variant_file_path), exist_ok=True)
        variant_layer = Sdf.Layer.CreateNew(variant_file_path)
        if not variant_layer:
            self.log_operation(f"Failed to create layer: {variant_file_path}")
            return None

        # Copy stage metadata from source
        utils.copy_stage_metadata(self.source_stage, variant_layer)

        # Determine destination prim path - use the default prim name
        default_prim_name = Sdf.Path(default_prim_path).name
        dest_prim_path = f"/{default_prim_name}"

        # Step 1: Inline contents from prepended payloads and references
        for payload in prepended_payloads:
            if payload.assetPath:
                resolved = self._resolve_asset_path(payload.assetPath)
                if resolved:
                    self._inline_asset_contents(resolved, payload.primPath, variant_layer, dest_prim_path)
                    self.log_operation(f"Inlined payload contents from: {payload.assetPath}")
                else:
                    self.log_operation(f"Failed to resolve asset path: {payload.assetPath}")

        for ref in prepended_references:
            if ref.assetPath:
                resolved = self._resolve_asset_path(ref.assetPath)
                if resolved:
                    self._inline_asset_contents(resolved, ref.primPath, variant_layer, dest_prim_path)
                    self.log_operation(f"Inlined reference contents from: {ref.assetPath}")
                else:
                    self.log_operation(f"Failed to resolve prepended reference asset path: {ref.assetPath}")

        # Step 2: Apply the variant's own deltas on top (skipping the prepended arcs)
        prim_spec = variant_spec.primSpec
        if prim_spec:
            self._apply_prim_spec_deltas(prim_spec, variant_layer, dest_prim_path, skip_composition_arcs=True)
            self.log_operation(f"Applied variant deltas")
        else:
            self.log_operation(f"Failed to get prim spec for variant: {variant_name}")

        # Step 3: Clear the inlined prepended payloads/references from the destination
        self._clear_inlined_composition_arcs(variant_layer, dest_prim_path, prepended_payloads, prepended_references)

        # Set default prim
        variant_layer.defaultPrim = default_prim_name

        # Save the layer
        variant_layer.Save()
        self.log_operation(f"Created variant layer: {variant_file_path}")

        return variant_file_path

    def _inline_asset_contents(
        self,
        asset_path: str,
        prim_path: Optional[Sdf.Path],
        dest_layer: Sdf.Layer,
        dest_prim_path: str,
    ) -> bool:
        """Inline the raw layer contents of a referenced asset into the destination layer.

        Opens the referenced asset as a layer (not a composed stage) and copies
        the prim specs directly without composition/flattening.

        Args:
            asset_path: Absolute path to the asset file.
            prim_path: Optional prim path within the asset (if None, uses default prim).
            dest_layer: The destination layer.
            dest_prim_path: The destination prim path.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Open the asset as a layer (not a composed stage)
            src_layer = Sdf.Layer.FindOrOpen(asset_path)
            if not src_layer:
                self.log_operation(f"Failed to open layer: {asset_path}")
                return False

            # Determine which prim to copy
            if prim_path and str(prim_path) and str(prim_path) != "/":
                src_prim_path = str(prim_path)
            else:
                # Use default prim if set
                default_prim_name = src_layer.defaultPrim
                if default_prim_name:
                    src_prim_path = f"/{default_prim_name}"
                else:
                    # Fall back to first root prim
                    root_prims = src_layer.rootPrims
                    if root_prims:
                        src_prim_path = f"/{root_prims[0].name}"
                    else:
                        self.log_operation(f"No prims found in layer: {asset_path}")
                        return False

            src_prim_spec = src_layer.GetPrimAtPath(src_prim_path)
            if not src_prim_spec:
                self.log_operation(f"Prim spec not found at '{src_prim_path}' in layer: {asset_path}")
                return False

            self.log_operation(
                f"Inlining prim spec '{src_prim_path}' (type={src_prim_spec.typeName}) from {asset_path}"
            )

            # Copy the prim spec directly (raw layer content, not composed)
            result = self._copy_prim_spec_to_layer(src_prim_spec, src_layer, dest_layer, dest_prim_path)
            self.log_operation(f"Copy prim spec result: {result}")
            return result

        except Exception as e:
            self.log_operation(f"Error inlining asset {asset_path}: {e}")
            return False

    def _copy_prim_spec_to_layer(
        self,
        src_spec: Sdf.PrimSpec,
        src_layer: Sdf.Layer,
        dest_layer: Sdf.Layer,
        dest_path: str,
    ) -> bool:
        """Copy a prim spec and its children from one layer to another.

        Copies raw layer content without composition. Asset paths in composition
        arcs are remapped to be relative to the destination layer.

        Args:
            src_spec: The source prim spec.
            src_layer: The source layer (for resolving relative paths).
            dest_layer: The destination layer.
            dest_path: The destination prim path.

        Returns:
            True if successful, False otherwise.
        """
        dest_prim_spec = Sdf.CreatePrimInLayer(dest_layer, dest_path)
        if not dest_prim_spec:
            return False

        dest_prim_spec.specifier = src_spec.specifier
        if src_spec.typeName:
            dest_prim_spec.typeName = src_spec.typeName

        # Copy applied API schemas
        if src_spec.HasInfo("apiSchemas"):
            dest_prim_spec.SetInfo("apiSchemas", src_spec.GetInfo("apiSchemas"))

        # Copy metadata (excluding composition-related keys handled separately)
        skip_keys = {
            "specifier",
            "typeName",
            "apiSchemas",
            "references",
            "payloads",
            "inherits",
            "specializes",
            "variantSets",
            "variantSelection",
        }
        for key in src_spec.ListInfoKeys():
            if key in skip_keys:
                continue
            try:
                value = src_spec.GetInfo(key)
                if value is not None:
                    dest_prim_spec.SetInfo(key, value)
            except Exception:
                pass

        # Copy attributes
        for attr_name in src_spec.attributes.keys():
            attr_spec = src_spec.attributes[attr_name]
            try:
                new_attr = Sdf.AttributeSpec(dest_prim_spec, attr_name, attr_spec.typeName)
                if new_attr:
                    if attr_spec.HasDefaultValue():
                        new_attr.default = attr_spec.default
                    if attr_spec.variability != Sdf.VariabilityVarying:
                        new_attr.variability = attr_spec.variability

                    if attr_spec.connectionPathList.GetAddedOrExplicitItems():
                        for conn in attr_spec.connectionPathList.GetAddedOrExplicitItems():
                            new_attr.connectionPathList.Prepend(conn)

                    # Copy attribute metadata
                    for key in attr_spec.ListInfoKeys():
                        if key in ("typeName", "default", "variability", "connectionPaths"):
                            continue
                        try:
                            new_attr.SetInfo(key, attr_spec.GetInfo(key))
                        except Exception:
                            pass
            except Exception:
                pass

        # Copy relationships
        for rel_name in src_spec.relationships.keys():
            rel_spec = src_spec.relationships[rel_name]
            try:
                new_rel = Sdf.RelationshipSpec(dest_prim_spec, rel_name)
                if new_rel:
                    for target in rel_spec.targetPathList.GetAddedOrExplicitItems():
                        new_rel.targetPathList.Prepend(target)
            except Exception:
                pass

        # Copy composition arcs with path remapping
        src_layer_dir = os.path.dirname(src_layer.realPath)
        dest_layer_dir = os.path.dirname(dest_layer.realPath)

        def remap_asset_path(asset_path: str) -> str:
            """Remap an asset path from source layer to destination layer."""
            if not asset_path:
                return asset_path
            if os.path.isabs(asset_path):
                return os.path.relpath(asset_path, dest_layer_dir)
            # Resolve relative to source, then make relative to dest
            abs_path = os.path.normpath(os.path.join(src_layer_dir, asset_path))
            return os.path.relpath(abs_path, dest_layer_dir)

        if src_spec.hasReferences:
            for ref in src_spec.referenceList.prependedItems:
                new_path = remap_asset_path(ref.assetPath) if ref.assetPath else ref.assetPath
                new_ref = Sdf.Reference(new_path, ref.primPath, ref.layerOffset)
                dest_prim_spec.referenceList.Prepend(new_ref)
            for ref in src_spec.referenceList.appendedItems:
                new_path = remap_asset_path(ref.assetPath) if ref.assetPath else ref.assetPath
                new_ref = Sdf.Reference(new_path, ref.primPath, ref.layerOffset)
                dest_prim_spec.referenceList.Append(new_ref)

        if src_spec.hasPayloads:
            for payload in src_spec.payloadList.prependedItems:
                new_path = remap_asset_path(payload.assetPath) if payload.assetPath else payload.assetPath
                new_payload = Sdf.Payload(new_path, payload.primPath, payload.layerOffset)
                dest_prim_spec.payloadList.Prepend(new_payload)
            for payload in src_spec.payloadList.appendedItems:
                new_path = remap_asset_path(payload.assetPath) if payload.assetPath else payload.assetPath
                new_payload = Sdf.Payload(new_path, payload.primPath, payload.layerOffset)
                dest_prim_spec.payloadList.Append(new_payload)

        if src_spec.hasInheritPaths:
            for path in src_spec.inheritPathList.GetAddedOrExplicitItems():
                dest_prim_spec.inheritPathList.Prepend(path)

        if src_spec.hasSpecializes:
            for path in src_spec.specializesList.GetAddedOrExplicitItems():
                dest_prim_spec.specializesList.Prepend(path)

        # Recursively copy children
        for child_name in src_spec.nameChildren.keys():
            child_spec = src_spec.nameChildren[child_name]
            child_dest_path = f"{dest_path}/{child_name}"
            self._copy_prim_spec_to_layer(child_spec, src_layer, dest_layer, child_dest_path)

        return True

    def process_rule(self) -> Optional[str]:
        """Process variant sets and extract each variant to separate layer files.

        For each variant set on the default prim, creates a folder and extracts
        each variant to a USDA file. Contents of prepended payloads and references
        are inlined into the output, and variant deltas are applied on top.

        Returns:
            None (this rule does not change the working stage).
        """
        params = self.args.get("params", {}) or {}
        variant_sets_filter: List[str] = params.get("variant_sets") or []
        destination = self.destination_path

        self.log_operation(f"VariantRoutingRule start destination={destination}")

        # Get the default prim
        default_prim = self.source_stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            self.log_operation("No valid default prim found, skipping")
            return None

        default_prim_path = default_prim.GetPath().pathString
        self.log_operation(f"Processing default prim: {default_prim_path}")

        # Get variant sets from the default prim
        variant_sets = default_prim.GetVariantSets()
        variant_set_names = variant_sets.GetNames() if variant_sets else []

        if not variant_set_names:
            self.log_operation("No variant sets found on default prim")
            return None

        self.log_operation(f"Found variant sets: {variant_set_names}")

        # Filter variant sets if specified
        if variant_sets_filter:
            variant_set_names = [name for name in variant_set_names if name in variant_sets_filter]
            self.log_operation(f"Filtered to variant sets: {variant_set_names}")

        # Get the source layer for resolving asset paths
        source_layer = self.source_stage.GetRootLayer()

        # Process each variant set
        output_base = os.path.join(self.package_root, destination)

        for vs_name in variant_set_names:
            variant_set = variant_sets.GetVariantSet(vs_name)
            if not variant_set:
                continue

            # Create output directory for this variant set
            sanitized_vs_name = utils.sanitize_prim_name(vs_name)
            variant_set_output_dir = os.path.join(output_base, sanitized_vs_name)
            os.makedirs(variant_set_output_dir, exist_ok=True)

            self.log_operation(f"Processing variant set '{vs_name}' -> {variant_set_output_dir}")

            # Get all variant names
            variant_names = variant_set.GetVariantNames()

            # Get the variant set spec from the layer to access variant contents
            prim_spec = source_layer.GetPrimAtPath(default_prim_path)
            if not prim_spec:
                self.log_operation(f"Could not find prim spec for {default_prim_path}")
                continue

            variant_set_spec = prim_spec.variantSets.get(vs_name)
            if not variant_set_spec:
                self.log_operation(f"Could not find variant set spec for {vs_name}")
                continue

            # Process each variant
            for variant_name in variant_names:
                output_path = self._process_variant(
                    variant_set_spec,
                    variant_name,
                    variant_set_output_dir,
                    source_layer,
                    default_prim_path,
                )

                if output_path:
                    self.add_affected_stage(output_path)

        self.log_operation("VariantRoutingRule completed")

        return None
