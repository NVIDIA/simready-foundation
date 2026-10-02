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
"""Rewrite folder-variant physics runtimes into the neutral SimReady RV contract.

The Isaac composition pipeline (:class:`InterfaceConnectionRule` with
``generate_folder_variants``) emits, for every physics runtime, a
``payloads/<Folder>/enabled.usda`` overlay (referencing the runtime instance
prototypes) plus an empty ``payloads/<Folder>/disabled.usda``, and wires them as
folder variants with the runtime *Enabled* by default. That layout is what the
(now superseded) legacy Isaac prop profile validated, but it violates the
neutral SimReady runtime-variant contract required by ``FET_000_PHYSX`` /
``FET_000_NEWTON`` / ``FET_000_MUJOCO``:

* ``RV.002`` requires the ``Enabled`` option to compose a single anchored
  ``runnables/physics/<stem>.usd`` payload.
* ``RV.010`` requires the ``Disabled`` option to be empty (no composition arcs
  and no local opinions).
* ``RV.001`` requires the authored default selection to be ``Disabled``.

Consolidated ``Robotics-Prop`` 3.2.0 keeps the full 3.1.0 contract (including the
neutral ``FET_000_*`` runtime variants) *and* adds Isaac composition
(``FET_100_ISAAC`` / ``ISA.001``). Versions 3.3.0 and 4.0.0 keep that menu. The two
contracts target different parts of
the package -- ``ISA.001`` cares about ``kind = component``, the ``payloads/``
perf layers, and the ``./payloads/base.usda`` reference, while the RV contract
cares about the physics variant payloads under ``runnables/physics/`` -- so a
single asset can satisfy both.

This rule performs the reconciliation as the final step of the transform: it
relocates each ``enabled.usda`` overlay to ``runnables/physics/<stem>.usd``
(re-anchoring the overlay's relative references so they still resolve to the
``payloads/instances_<runtime>.usda`` prototypes), drops the ``disabled``
overlays, and re-authors the interface variant sets to the RV contract
(``Enabled`` -> the relocated payload, ``Disabled`` -> empty, default
``Disabled``). The Isaac ``payloads/`` perf layers, the component kind, the base
reference, and the ``customLayerData.SimReady_Metadata.Variants.Physics`` block
(``RV.003``) are all left untouched.
"""

from __future__ import annotations

import os
import shutil

from pxr import Sdf
from simready.asset_transformer import RuleConfigurationParam, RuleInterface

from .. import utils

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
    """Convert Isaac folder variants into neutral ``RV.*``-conformant variants."""

    def get_configuration_parameters(self) -> list[RuleConfigurationParam]:
        return [
            RuleConfigurationParam(
                name="runtimes",
                display_name="Runtime Variant Mapping",
                param_type=list,
                description=(
                    "Physics runtimes to rewrite. Each entry maps a folder-variant "
                    "set name to the runnables/physics payload stem (physx/newton/mujoco)."
                ),
                default_value=[dict(entry) for entry in _DEFAULT_RUNTIMES],
            ),
            RuleConfigurationParam(
                name="payloads_folder",
                display_name="Payloads Folder",
                param_type=str,
                description="Folder holding the generated per-runtime folder variants.",
                default_value=_DEFAULT_PAYLOADS_FOLDER,
            ),
            RuleConfigurationParam(
                name="runnables_dir",
                display_name="Runnables Physics Directory",
                param_type=str,
                description="Destination directory (relative to the package root) for the RV payloads.",
                default_value=_DEFAULT_RUNNABLES_DIR,
            ),
        ]

    @staticmethod
    def _rebase(asset_path: str, old_dir: str, new_dir: str) -> str:
        """Re-anchor a relative asset path from ``old_dir`` to ``new_dir``.

        Absolute paths and empty paths are returned unchanged.
        """
        if not asset_path:
            return asset_path
        normalized = asset_path.replace("\\", "/")
        # Leave absolute paths and asset-relative search-path identifiers alone.
        if normalized.startswith("/") or normalized.startswith("@"):
            return asset_path
        if not (normalized.startswith("./") or normalized.startswith("../")):
            # Bare identifiers (search paths / package-relative) are not our concern.
            return asset_path
        abs_target = os.path.normpath(os.path.join(old_dir, normalized))
        return utils.make_explicit_relative(os.path.relpath(abs_target, new_dir))

    @classmethod
    def _remap_arc_list(cls, arc_list, ctor, old_dir: str, new_dir: str) -> None:
        """Re-anchor every item in a reference/payload list op in place."""
        for attr in ("prependedItems", "appendedItems", "explicitItems", "orderedItems"):
            items = list(getattr(arc_list, attr, []) or [])
            if not items:
                continue
            rebased = [
                ctor(
                    cls._rebase(item.assetPath, old_dir, new_dir),
                    item.primPath,
                    item.layerOffset,
                )
                for item in items
            ]
            setattr(arc_list, attr, rebased)

    @classmethod
    def _reanchor_layer(cls, layer: Sdf.Layer, old_dir: str, new_dir: str) -> None:
        """Re-anchor sublayers, references, and payloads of ``layer`` in place."""
        if layer.subLayerPaths:
            layer.subLayerPaths = [cls._rebase(sp, old_dir, new_dir) for sp in layer.subLayerPaths]

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
        """Copy ``enabled.usda`` to ``runnables/physics/<stem>.usd`` and re-anchor it."""
        src_layer = Sdf.Layer.FindOrOpen(enabled_src)
        if src_layer is None:
            raise RuntimeError(f"Could not open runtime overlay: {enabled_src}")

        os.makedirs(os.path.dirname(payload_dst), exist_ok=True)
        dst_layer = Sdf.Layer.FindOrOpen(payload_dst) or Sdf.Layer.CreateNew(payload_dst)
        if dst_layer is None:
            raise RuntimeError(f"Could not create runtime payload layer: {payload_dst}")
        dst_layer.TransferContent(src_layer)

        old_dir = os.path.dirname(os.path.abspath(enabled_src))
        new_dir = os.path.dirname(os.path.abspath(payload_dst))
        self._reanchor_layer(dst_layer, old_dir, new_dir)
        dst_layer.Save()

    @staticmethod
    def _empty_variant(variant_spec: Sdf.VariantSpec) -> None:
        """Strip a variant's prim spec so the option composes nothing (``RV.010``)."""
        prim_spec = variant_spec.primSpec
        if prim_spec is None:
            return
        utils.clear_composition_arcs(prim_spec)
        for child_name in list(prim_spec.nameChildren.keys()):
            del prim_spec.nameChildren[child_name]
        for prop_name in [prop.name for prop in prim_spec.properties]:
            del prim_spec.properties[prop_name]

    def _author_rv_variant_set(
        self,
        interface_layer: Sdf.Layer,
        prim_spec: Sdf.PrimSpec,
        folder: str,
        payload_dst: str,
    ) -> None:
        """Re-point the ``Enabled`` option and empty the ``Disabled`` option."""
        variant_set_spec = prim_spec.variantSets.get(folder)
        if variant_set_spec is None:
            variant_set_spec = Sdf.VariantSetSpec(prim_spec, folder)
            if folder not in prim_spec.variantSetNameList.GetAddedOrExplicitItems():
                prim_spec.variantSetNameList.Append(folder)

        enabled_variant = variant_set_spec.variants.get(_ENABLED_VARIANT)
        if enabled_variant is None:
            enabled_variant = Sdf.VariantSpec(variant_set_spec, _ENABLED_VARIANT)
        enabled_prim = enabled_variant.primSpec
        enabled_prim.payloadList.ClearEdits()
        enabled_prim.referenceList.ClearEdits()
        payload_rel = utils.get_relative_layer_path(interface_layer, os.path.abspath(payload_dst))
        enabled_prim.payloadList.Prepend(Sdf.Payload(payload_rel))

        disabled_variant = variant_set_spec.variants.get(_DISABLED_VARIANT)
        if disabled_variant is None:
            disabled_variant = Sdf.VariantSpec(variant_set_spec, _DISABLED_VARIANT)
        self._empty_variant(disabled_variant)

        prim_spec.variantSelections[folder] = _DISABLED_VARIANT

    def process_rule(self) -> str | None:
        params = self.args.get("params", {}) or {}
        runtimes = params.get("runtimes") or [dict(entry) for entry in _DEFAULT_RUNTIMES]
        payloads_folder = params.get("payloads_folder") or _DEFAULT_PAYLOADS_FOLDER
        runnables_dir = params.get("runnables_dir") or _DEFAULT_RUNNABLES_DIR

        interface_layer = self.source_stage.GetRootLayer()
        default_prim_name = interface_layer.defaultPrim
        if not default_prim_name:
            self.log_operation("No default prim on interface; skipping neutral runtime variant rewrite")
            return None
        prim_spec = interface_layer.GetPrimAtPath(Sdf.Path.absoluteRootPath.AppendChild(default_prim_name))
        if prim_spec is None:
            self.log_operation(f"Default prim spec /{default_prim_name} not found; skipping rewrite")
            return None

        rewritten = 0
        for runtime in runtimes:
            folder = runtime["folder"]
            stem = runtime["stem"]
            enabled_src = os.path.join(self.package_root, payloads_folder, folder, _ENABLED_LAYER)
            if not os.path.isfile(enabled_src):
                self.log_operation(f"No enabled overlay for '{folder}'; skipping ({enabled_src})")
                continue

            payload_dst = os.path.join(self.package_root, runnables_dir, f"{stem}.usd")
            self._relocate_enabled_overlay(enabled_src, payload_dst)
            self._author_rv_variant_set(interface_layer, prim_spec, folder, payload_dst)

            folder_dir = os.path.join(self.package_root, payloads_folder, folder)
            shutil.rmtree(folder_dir, ignore_errors=True)

            self.add_affected_stage(payload_dst)
            rewritten += 1
            self.log_operation(
                f"Rewrote '{folder}' folder variant into neutral RV payload runnables/physics/{stem}.usd"
            )

        interface_layer.Save()
        self.add_affected_stage(interface_layer.identifier)
        self.log_operation(f"NeutralRuntimeVariantRule rewrote {rewritten} runtime variant set(s)")
        return None
