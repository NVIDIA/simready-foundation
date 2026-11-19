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
"""Rewrite generated folder variants into the neutral SimReady RV contract."""

from __future__ import annotations

import os
import shutil

from isaacsim.asset.transformer.rules import utils
from pxr import Sdf
from simready.asset_transformer import RuleConfigurationParam, RuleInterface

_DEFAULT_RUNTIMES: list[dict[str, str]] = [
    {"folder": "PhysX", "stem": "physx"},
    {"folder": "Newton", "stem": "newton"},
    {"folder": "MuJoCo", "stem": "mujoco"},
]
_DEFAULT_PAYLOADS_FOLDER = "payloads"
_DEFAULT_RUNNABLES_DIR = "runnables/physics"
_ENABLED_VARIANT = "Enabled"
_DISABLED_VARIANT = "Disabled"
_ENABLED_LAYER = "enabled.usda"


class NeutralRuntimeVariantRule(RuleInterface):
    """Convert Isaac folder variants into RV-conformant runtime payloads."""

    def get_configuration_parameters(self) -> list[RuleConfigurationParam]:
        return [
            RuleConfigurationParam(
                name="runtimes",
                display_name="Runtime Variant Mapping",
                param_type=list,
                description=(
                    "Physics runtimes to rewrite. Each entry maps a folder-variant "
                    "set name to its runnables/physics payload stem."
                ),
                default_value=[dict(entry) for entry in _DEFAULT_RUNTIMES],
            ),
            RuleConfigurationParam(
                name="payloads_folder",
                display_name="Payloads Folder",
                param_type=str,
                description="Folder holding generated per-runtime folder variants.",
                default_value=_DEFAULT_PAYLOADS_FOLDER,
            ),
            RuleConfigurationParam(
                name="runnables_dir",
                display_name="Runnables Physics Directory",
                param_type=str,
                description="Package-relative destination for runtime payloads.",
                default_value=_DEFAULT_RUNNABLES_DIR,
            ),
        ]

    @staticmethod
    def _rebase(asset_path: str, old_dir: str, new_dir: str) -> str:
        """Re-anchor a relative asset path after relocating its owning layer."""
        normalized = asset_path.replace("\\", "/")
        if not normalized or normalized.startswith("/") or normalized.startswith("@"):
            return asset_path
        if not normalized.startswith(("./", "../")):
            return asset_path
        absolute_target = os.path.normpath(os.path.join(old_dir, normalized))
        relative_target = os.path.relpath(absolute_target, new_dir).replace("\\", "/")
        if not relative_target.startswith(("./", "../")):
            relative_target = f"./{relative_target}"
        return relative_target

    @classmethod
    def _remap_arc_list(cls, arc_list, constructor, old_dir: str, new_dir: str) -> None:
        for attr in (
            "prependedItems",
            "appendedItems",
            "addedItems",
            "explicitItems",
            "orderedItems",
        ):
            items = list(getattr(arc_list, attr, []) or [])
            if not items:
                continue
            setattr(
                arc_list,
                attr,
                [
                    constructor(
                        cls._rebase(item.assetPath, old_dir, new_dir),
                        item.primPath,
                        item.layerOffset,
                    )
                    for item in items
                ],
            )

    @classmethod
    def _reanchor_layer(cls, layer: Sdf.Layer, old_dir: str, new_dir: str) -> None:
        layer.subLayerPaths = [cls._rebase(path, old_dir, new_dir) for path in layer.subLayerPaths]

        def walk(prim_spec: Sdf.PrimSpec) -> None:
            if prim_spec.hasReferences:
                cls._remap_arc_list(prim_spec.referenceList, Sdf.Reference, old_dir, new_dir)
            if prim_spec.hasPayloads:
                cls._remap_arc_list(prim_spec.payloadList, Sdf.Payload, old_dir, new_dir)
            for child in prim_spec.nameChildren.values():
                walk(child)

        for root_prim in layer.rootPrims:
            walk(root_prim)

    def _relocate_enabled_overlay(self, enabled_src: str, payload_dst: str) -> None:
        source_layer = Sdf.Layer.FindOrOpen(enabled_src)
        if source_layer is None:
            raise RuntimeError(f"Could not open runtime overlay: {enabled_src}")

        os.makedirs(os.path.dirname(payload_dst), exist_ok=True)
        destination_layer = Sdf.Layer.FindOrOpen(payload_dst)
        if destination_layer is None:
            destination_layer = Sdf.Layer.CreateNew(payload_dst)
        if destination_layer is None:
            raise RuntimeError(f"Could not create runtime payload: {payload_dst}")

        destination_layer.TransferContent(source_layer)
        self._reanchor_layer(
            destination_layer,
            os.path.dirname(os.path.abspath(enabled_src)),
            os.path.dirname(os.path.abspath(payload_dst)),
        )
        destination_layer.Save()

    @staticmethod
    def _empty_variant(variant_spec: Sdf.VariantSpec) -> None:
        prim_spec = variant_spec.primSpec
        if prim_spec is None:
            return
        utils.clear_composition_arcs(prim_spec)
        for child_name in list(prim_spec.nameChildren):
            del prim_spec.nameChildren[child_name]
        for property_spec in list(prim_spec.properties):
            del prim_spec.properties[property_spec.name]

    def _author_rv_variant_set(
        self,
        interface_layer: Sdf.Layer,
        prim_spec: Sdf.PrimSpec,
        variant_set_name: str,
        payload_path: str,
    ) -> None:
        variant_set = prim_spec.variantSets.get(variant_set_name)
        if variant_set is None:
            variant_set = Sdf.VariantSetSpec(prim_spec, variant_set_name)
            prim_spec.variantSetNameList.Append(variant_set_name)

        enabled = variant_set.variants.get(_ENABLED_VARIANT)
        if enabled is None:
            enabled = Sdf.VariantSpec(variant_set, _ENABLED_VARIANT)
        self._empty_variant(enabled)
        payload_rel = utils.get_relative_layer_path(interface_layer, os.path.abspath(payload_path))
        enabled.primSpec.payloadList.Prepend(Sdf.Payload(payload_rel))

        disabled = variant_set.variants.get(_DISABLED_VARIANT)
        if disabled is None:
            disabled = Sdf.VariantSpec(variant_set, _DISABLED_VARIANT)
        self._empty_variant(disabled)
        prim_spec.variantSelections[variant_set_name] = _DISABLED_VARIANT

    def process_rule(self) -> str | None:
        params = self.args.get("params", {}) or {}
        runtimes = params.get("runtimes") or [dict(entry) for entry in _DEFAULT_RUNTIMES]
        payloads_folder = params.get("payloads_folder") or _DEFAULT_PAYLOADS_FOLDER
        runnables_dir = params.get("runnables_dir") or _DEFAULT_RUNNABLES_DIR

        interface_layer = self.source_stage.GetRootLayer()
        default_prim_name = interface_layer.defaultPrim
        if not default_prim_name:
            raise RuntimeError("Interface layer has no default prim")
        prim_spec = interface_layer.GetPrimAtPath(Sdf.Path.absoluteRootPath.AppendChild(default_prim_name))
        if prim_spec is None:
            raise RuntimeError(f"Default prim /{default_prim_name} is not authored")

        rewritten = 0
        for runtime in runtimes:
            folder = runtime["folder"]
            stem = runtime["stem"]
            enabled_src = os.path.join(self.package_root, payloads_folder, folder, _ENABLED_LAYER)
            if not os.path.isfile(enabled_src):
                self.log_operation(f"No generated enabled overlay for '{folder}'; skipping")
                continue
            if folder not in prim_spec.variantSets:
                # A later rule (for example RemoveSchemaRule) can create
                # payloads/<folder>/enabled.usda for a source with no runtime
                # variants. Rewriting it would invent a variant whose payload has
                # no default prim, so drop the stray folder instead.
                shutil.rmtree(os.path.join(self.package_root, payloads_folder, folder), ignore_errors=True)
                self.log_operation(f"No '{folder}' variant set on the interface; removed stray overlay")
                continue

            payload_dst = os.path.join(self.package_root, runnables_dir, f"{stem}.usd")
            self._relocate_enabled_overlay(enabled_src, payload_dst)
            self._author_rv_variant_set(interface_layer, prim_spec, folder, payload_dst)
            shutil.rmtree(
                os.path.join(self.package_root, payloads_folder, folder),
                ignore_errors=True,
            )
            self.add_affected_stage(payload_dst)
            rewritten += 1

        interface_layer.Save()
        self.add_affected_stage(interface_layer.identifier)
        self.log_operation(f"NeutralRuntimeVariantRule rewrote {rewritten} runtime variant set(s)")
        return None
