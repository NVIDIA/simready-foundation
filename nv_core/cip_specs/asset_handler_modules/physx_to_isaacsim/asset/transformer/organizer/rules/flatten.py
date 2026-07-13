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
"""Flatten rule for USD asset transformation."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from isaacsim.asset.transformer import RuleConfigurationParam, RuleInterface
from pxr import Sdf, Usd

# Default configuration values
_DEFAULT_OUTPUT_PATH: str = "base.usda"
_DEFAULT_CLEAR_VARIANTS: bool = True
_DEFAULT_SELECTED_VARIANTS: Dict[str, str] = {}


class FlattenRule(RuleInterface):
    """Flatten the original input stage into a single layer.

    Opens the original input asset (via input_stage_path from args), clears
    variant selections before flattening to ensure a neutral base representation,
    and exports the flattened result. Operating on the original preserves
    relative asset paths that would be broken after initial processing.
    """

    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters for output path, variant clearing, and variant selection.
        """
        return [
            RuleConfigurationParam(
                name="output_path",
                display_name="Output Path",
                param_type=str,
                description="Relative path within package root to export the flattened layer",
                default_value=_DEFAULT_OUTPUT_PATH,
            ),
            RuleConfigurationParam(
                name="clear_variants",
                display_name="Clear Variant Selections",
                param_type=bool,
                description="Clear all variant selections before flattening to produce a neutral base",
                default_value=_DEFAULT_CLEAR_VARIANTS,
            ),
            RuleConfigurationParam(
                name="selected_variants",
                display_name="Selected Variants",
                param_type=dict,
                description="Dictionary mapping variant set names to variant selections. "
                "Only applies to variant sets that exist on the asset default prim.",
                default_value=_DEFAULT_SELECTED_VARIANTS,
            ),
        ]

    def process_rule(self) -> Optional[str]:
        """Flatten the original input stage and export to the output path.

        Opens the original input stage (before any processing), applies variant
        selections if configured, clears remaining variant selections if configured,
        flattens it, and exports to the destination.
        This preserves relative paths that would be broken after initial processing.

        Returns:
            Path to the flattened stage for subsequent rules to use.
        """
        params = self.args.get("params", {}) or {}

        output_path = params.get("output_path") or _DEFAULT_OUTPUT_PATH
        clear_variants = params.get("clear_variants", _DEFAULT_CLEAR_VARIANTS)
        selected_variants = params.get("selected_variants") or _DEFAULT_SELECTED_VARIANTS

        # Get the original input stage path
        input_stage_path = self.args.get("input_stage_path")
        if not input_stage_path:
            self.log_operation("No input_stage_path provided, cannot flatten original source")
            return None

        self.log_operation(
            f"FlattenRule start input={input_stage_path} output={output_path} "
            f"clear_variants={clear_variants} selected_variants={selected_variants}"
        )

        # Open the original input stage
        input_stage = Usd.Stage.Open(input_stage_path)
        if not input_stage:
            self.log_operation(f"Failed to open input stage: {input_stage_path}")
            return None

        # Clear remaining variant selections before flattening
        if clear_variants:
            self._clear_all_variant_selections(input_stage)

        # Apply selected variant selections on the default prim
        if selected_variants:
            self._apply_variant_selections(input_stage, selected_variants)

        # Flatten the stage
        flattened_layer = input_stage.Flatten()
        if not flattened_layer:
            self.log_operation("Failed to flatten input stage")
            return None

        # Resolve output path
        output_abs_path = os.path.join(self.package_root, os.path.join(self.destination_path, output_path))
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        # Check if the layer is already cached by USD (e.g., opened by manager.py)
        cached_layer = Sdf.Layer.Find(output_abs_path)
        if cached_layer:
            # Transfer content to the cached layer and save to avoid cache conflicts
            self.log_operation(f"Layer cached in USD registry, transferring content: {output_abs_path}")
            cached_layer.TransferContent(flattened_layer)
            if not cached_layer.Save():
                self.log_operation(f"Failed to save cached layer: {output_abs_path}")
                return None
        else:
            # No cached layer, export directly
            if os.path.exists(output_abs_path):
                try:
                    os.remove(output_abs_path)
                    self.log_operation(f"Removed existing file: {output_abs_path}")
                except PermissionError:
                    # File may be locked by another process - export will overwrite
                    self.log_operation(f"Warning: Could not remove existing file: {output_abs_path}")
            if not flattened_layer.Export(output_abs_path):
                self.log_operation(f"Failed to export flattened layer to: {output_abs_path}")
                return None

        self.log_operation(f"Exported flattened layer to: {output_abs_path}")
        self.add_affected_stage(output_path)
        self.log_operation("FlattenRule completed")

        # Return the path so manager can switch to the flattened stage
        return output_abs_path

    def _apply_variant_selections(self, stage: Usd.Stage, selected_variants: Dict[str, str]) -> None:
        """Apply variant selections on the stage default prim.

        Sets variant selections for variant sets that exist on the default prim.
        Variant sets not present on the prim are skipped. If the requested variant
        does not exist within the variant set, the selection is set to empty string.

        Args:
            stage: The stage containing the default prim.
            selected_variants: Dictionary mapping variant set names to variant selections.
        """
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            self.log_operation("No valid default prim found, skipping variant selection")
            return

        variant_sets = default_prim.GetVariantSets()
        applied_count = 0

        for variant_set_name, variant_selection in selected_variants.items():
            if variant_sets.HasVariantSet(variant_set_name):
                variant_set = variant_sets.GetVariantSet(variant_set_name)
                available_variants = variant_set.GetVariantNames()
                if variant_selection in available_variants:
                    variant_set.SetVariantSelection(variant_selection)
                    self.log_operation(f"Set variant '{variant_set_name}' to '{variant_selection}'")
                else:
                    self.log_operation(
                        f"Variant '{variant_selection}' not found in '{variant_set_name}', keeping "
                        f"existing selection '{variant_set.GetVariantSelection()}'"
                    )
                applied_count += 1
            else:
                self.log_operation(f"Variant set '{variant_set_name}' not found on default prim, skipping")

        if applied_count > 0:
            self.log_operation(f"Applied {applied_count} variant selection(s)")
        else:
            self.log_operation("No variant selections applied")

    def _clear_all_variant_selections(self, stage: Usd.Stage) -> None:
        """Clear variant selections on all prims in the given stage.

        Iterates through the prim stack and clears the variantSelections metadata
        to ensure a neutral base before flattening.

        Args:
            stage: The stage to clear variant selections from.
        """
        cleared_count = 0
        root_layer = stage.GetRootLayer()

        for prim in Usd.PrimRange(stage.GetPseudoRoot()):
            if not prim.IsValid():
                continue

            prim_path = prim.GetPath()
            prim_spec = root_layer.GetPrimAtPath(prim_path)
            if not prim_spec:
                continue

            # Clear variant selections on this prim spec
            variant_selections = prim_spec.variantSelections
            if variant_selections:
                variant_set_names = list(variant_selections.keys())
                for variant_set_name in variant_set_names:
                    del variant_selections[variant_set_name]
                    cleared_count += 1

        if cleared_count > 0:
            self.log_operation(f"Cleared {cleared_count} variant selection(s)")
        else:
            self.log_operation("No variant selections to clear")
