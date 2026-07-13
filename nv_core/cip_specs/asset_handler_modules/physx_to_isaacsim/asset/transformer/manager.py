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

import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Type

from pxr import Sdf, Usd, UsdUtils

from .models import ExecutionReport, RuleExecutionResult, RuleProfile, RuleSpec
from .rule_interface import RuleInterface

_LOGGER = logging.getLogger(__name__)


def _collect_assets(layer: Sdf.Layer, package_root: str) -> None:
    """Copy external assets to package_root and update layer paths.

    Args:
        layer: The USD layer to process.
        package_root: Destination directory for collected assets.
    """
    layer_path = layer.realPath
    assets_dir = os.path.join(package_root, "source_assets")
    copied_assets: Dict[str, str] = {}

    # Compute all asset dependencies from this layer
    _, all_assets, _ = UsdUtils.ComputeAllDependencies(layer_path)

    for asset_path in all_assets:
        resolved = str(asset_path.GetResolvedPath()) if hasattr(asset_path, "GetResolvedPath") else str(asset_path)
        if not resolved or not os.path.isfile(resolved):
            continue

        # Determine local destination preserving filename
        filename = os.path.basename(resolved)
        local_path = os.path.join(assets_dir, filename)

        # Handle duplicate filenames by appending suffix
        if local_path in copied_assets.values() and copied_assets.get(resolved) != local_path:
            base, ext = os.path.splitext(filename)
            counter = 1
            while local_path in copied_assets.values():
                local_path = os.path.join(assets_dir, f"{base}_{counter}{ext}")
                counter += 1

        if resolved not in copied_assets:
            os.makedirs(assets_dir, exist_ok=True)
            shutil.copy2(resolved, local_path)
            copied_assets[resolved] = local_path

    layer_dir = os.path.dirname(layer_path)

    def remap_path(original_path: str) -> str:
        if not original_path:
            return original_path
        # Resolve relative paths against the layer directory
        if os.path.isabs(original_path):
            resolved = original_path
        else:
            resolved = os.path.normpath(os.path.join(layer_dir, original_path))
        if resolved in copied_assets:
            return os.path.relpath(copied_assets[resolved], layer_dir)
        return original_path

    UsdUtils.ModifyAssetPaths(layer, remap_path)
    layer.Save()


def Singleton(class_):
    """A singleton decorator"""
    instances = {}

    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]

    return getinstance


@Singleton
class RuleRegistry:
    """In-memory registry mapping fully qualified class names to implementation classes."""

    def __init__(self) -> None:
        self._type_to_cls: Dict[str, Type[RuleInterface]] = {}

    def register(self, rule_cls: Type[RuleInterface]) -> None:
        """Register a rule implementation class using its fully qualified name.

        Args:
            rule_cls: Concrete subclass of :class:`RuleInterface`. The registry
                key is computed as ``{rule_cls.__module__}.{rule_cls.__qualname__}``.

        Returns:
            None.
        """
        if not issubclass(rule_cls, RuleInterface):
            raise TypeError("rule_cls must subclass RuleInterface")
        fqcn = f"{rule_cls.__module__}.{rule_cls.__qualname__}"
        self._type_to_cls[fqcn] = rule_cls

    def get(self, rule_type: str) -> Optional[Type[RuleInterface]]:
        """Resolve a rule implementation class by fully qualified class name.

        Args:
            rule_type: Fully qualified class name stored in :class:`RuleSpec.type`.

        Returns:
            The registered class, or ``None`` if not found.
        """
        return self._type_to_cls.get(rule_type)

    def clear(self) -> None:
        """Clear all registered rule mappings."""
        self._type_to_cls.clear()


class AssetStructureManager:
    """Coordinates execution of a :class:`RuleProfile` over USD stages.

    The manager creates a flattened and collected copy of the input stage at
    ``{package_root}/base.usda``. External assets are copied to
    ``{package_root}/assets/`` with paths updated to local references. All
    rules execute against this self-contained working copy.
    """

    def __init__(self, registry: RuleRegistry | None = None) -> None:
        self._registry = RuleRegistry()

    @property
    def registry(self) -> RuleRegistry:
        return self._registry

    def run(
        self,
        input_stage_path: str,
        profile: RuleProfile,
        package_root: Optional[str] = None,
    ) -> ExecutionReport:
        """Execute a profile from an input stage path and return an execution report.

        Args:
            input_stage_path: Path to the source USD stage or layer.
            profile: Rule profile specifying ordered rules to run.
            package_root: Destination root directory for outputs.

        Returns:
            Execution report including per-rule logs and status.
        """
        package_root_final = package_root or profile.output_package_root or ""
        report = ExecutionReport(
            profile=profile,
            input_stage_path=input_stage_path,
            package_root=package_root_final,
        )

        source_stage = Usd.Stage.Open(input_stage_path)
        if source_stage is None:
            report.close()
            raise RuntimeError(f"Failed to open source stage: {input_stage_path}")
        base_name = profile.base_name or "base.usd"
        # Create flattened copy at destination as base.usda
        base_usda_path = os.path.join(package_root_final, "payloads", base_name)
        os.makedirs(package_root_final, exist_ok=True)
        if profile.flatten_source:
            flattened_layer = source_stage.Flatten()
            if not flattened_layer.Export(base_usda_path):
                report.close()
                raise RuntimeError(f"Failed to export flattened stage to: {base_usda_path}")
        else:
            source_stage.GetRootLayer().Export(base_usda_path)

        # Collect external assets and update paths in base.usda
        base_layer = Sdf.Layer.FindOrOpen(base_usda_path)
        if base_layer:
            _collect_assets(base_layer, package_root_final)

        working_stage = Usd.Stage.Open(base_usda_path)
        if working_stage is None:
            report.close()
            raise RuntimeError(f"Failed to open flattened stage: {base_usda_path}")

        for spec in profile.rules:
            if not spec.enabled:
                _LOGGER.info("Skipping disabled rule: %s", spec.name)
                continue

            result = RuleExecutionResult(rule=spec, success=False)
            report.results.append(result)

            try:
                impl_cls = self._registry.get(spec.type)
                if impl_cls is None:
                    raise KeyError(f"No rule implementation registered for type '{spec.type}'")

                destination_path = spec.destination or ""
                rule: RuleInterface = impl_cls(
                    working_stage,
                    package_root_final,
                    destination_path,
                    {
                        "params": spec.params,
                        "interface_asset_name": profile.interface_asset_name,
                        "input_stage_path": input_stage_path,
                    },
                )

                returned_stage_path = rule.process_rule()

                # Update working stage if the rule returned a different stage path
                if returned_stage_path is not None:
                    current_path = working_stage.GetRootLayer().realPath
                    if returned_stage_path != current_path:
                        # Release the old stage before opening the new one
                        # The rule is responsible for saving its changes before returning a new path
                        del working_stage

                        # Open the new stage
                        new_stage = Usd.Stage.Open(returned_stage_path)
                        if new_stage is not None:
                            working_stage = new_stage
                            _LOGGER.info("Switched working stage to: %s", returned_stage_path)
                        else:
                            _LOGGER.warning("Failed to open returned stage: %s", returned_stage_path)
                            # Re-open the original if we can't open the new one
                            working_stage = Usd.Stage.Open(current_path)

                # Collect logs and affected stages from the rule.
                for entry in rule.get_operation_log():
                    result.log.append({"message": entry})
                result.affected_stages = rule.get_affected_stages()
                result.success = True

            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception("Rule '%s' failed", spec.name)
                result.error = str(exc)
                result.success = False
            finally:
                result.close()

        # Save the working stage's root layer if it has unsaved changes
        root_layer = working_stage.GetRootLayer()
        if root_layer and root_layer.dirty:
            root_layer.Save()

        report.close()
        return report
