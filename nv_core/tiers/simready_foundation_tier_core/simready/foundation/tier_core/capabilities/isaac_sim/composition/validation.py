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
import os
from collections import deque

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Kind, Sdf, Usd, UsdGeom

from ...core.path_utils import anchored_asset_identifier, split_package_identifier


_USD_EXTENSIONS = (".usd", ".usda", ".usdc")


def _list_op_items(list_op) -> list:
    if not list_op:
        return []
    items = []
    for name in ("explicitItems", "prependedItems", "addedItems", "appendedItems"):
        items.extend(getattr(list_op, name, ()))
    return items


def _iter_prim_specs(prim_specs):
    for prim_spec in prim_specs:
        yield prim_spec
        yield from _iter_prim_specs(prim_spec.nameChildren.values())


def _layer_basename(identifier: str) -> str:
    outer, inner = split_package_identifier(identifier)
    return os.path.basename(inner or outer).lower()


@usd_validation_nvidia.register_rule("IsaacComposition")
@usd_validation_nvidia.register_requirements(cap.CompositionRequirements.ISA_001, override=True)
class IsaacCompositionCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    ISAAC_COMPOSITION_REQUIREMENT = cap.CompositionRequirements.ISA_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                "Stage has no default prim. Unable to validate.",
                at=stage,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        # Check if default prim has kind = "component"
        model_api = Usd.ModelAPI(default_prim)
        if not model_api.GetKind() == Kind.Tokens.component:
            self._AddFailedCheck(
                "Default prim must have kind='component' for proper Isaac Sim composition.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

        # Check the complete package layout without forcing payload loading.
        self._check_layer_structure(stage, default_prim)

        # Check for proper hierarchy organization
        self._check_hierarchy_organization(stage, default_prim)

    def _check_layer_structure(self, stage: Usd.Stage, default_prim: Usd.Prim) -> None:
        """Validate either supported composition layout using authored layer arcs."""
        root_layer = stage.GetRootLayer()
        prim_spec = root_layer.GetPrimAtPath(default_prim.GetPath())
        if not prim_spec:
            self._AddFailedCheck(
                "Could not resolve prim spec for default prim.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        root_arcs = _list_op_items(prim_spec.referenceList) + _list_op_items(prim_spec.payloadList)
        root_arc_basenames = set()
        for item in root_arcs:
            if not item.assetPath:
                continue
            identifier = anchored_asset_identifier(root_layer, item.assetPath)
            try:
                referenced_layer = Sdf.Layer.FindOrOpen(identifier) if identifier else None
            except Exception:
                referenced_layer = None
            if referenced_layer:
                root_arc_basenames.add(_layer_basename(referenced_layer.identifier))

        layers = self._collect_authored_layers(stage)
        basenames = {_layer_basename(layer.identifier) for layer in layers}

        perf_required = {"base", "geometries", "instances", "materials"}
        perf_found = {
            stem
            for stem in perf_required
            if any(name == f"{stem}{ext}" for ext in _USD_EXTENSIONS for name in basenames)
        }

        legacy_stems = {
            name[: -len(suffix)]
            for name in basenames
            for ext in _USD_EXTENSIONS
            for suffix in (f"_base{ext}", f"_meshes{ext}", f"_physics{ext}")
            if name.endswith(suffix) and name[: -len(suffix)]
        }
        legacy_matches = {
            stem: {
                role
                for role in ("base", "meshes", "physics")
                if any(f"{stem}_{role}{ext}" in basenames for ext in _USD_EXTENSIONS)
            }
            for stem in legacy_stems
        }
        best_legacy_stem, best_legacy_found = max(
            legacy_matches.items(), key=lambda item: len(item[1]), default=("", set())
        )

        perf_complete = perf_found == perf_required
        legacy_required = {"base", "meshes", "physics"}
        legacy_complete = best_legacy_found == legacy_required
        if not perf_complete and not legacy_complete:
            if len(perf_found) >= len(best_legacy_found):
                missing = sorted(perf_required - perf_found)
                detail = f"performance robot layout; missing layers: {', '.join(missing)}"
            elif best_legacy_stem:
                missing = sorted(legacy_required - best_legacy_found)
                detail = (
                    f"legacy prop layout with shared stem '{best_legacy_stem}'; "
                    f"missing layers: {', '.join(missing)}"
                )
            else:
                detail = (
                    "no recognizable layout layers found; expected base/geometries/instances/materials "
                    "or <asset>_base/<asset>_meshes/<asset>_physics"
                )
            self._AddFailedCheck(
                f"Incomplete Isaac Sim composition: {detail}.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

        if perf_complete:
            valid_base_names = {f"base{ext}" for ext in _USD_EXTENSIONS}
        elif best_legacy_stem:
            valid_base_names = {f"{best_legacy_stem}_base{ext}" for ext in _USD_EXTENSIONS}
        else:
            valid_base_names = set()
        if valid_base_names and not root_arc_basenames.intersection(valid_base_names):
            self._AddFailedCheck(
                "Default prim must author a reference or payload arc to the layout's base layer.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

    def _collect_authored_layers(self, stage: Usd.Stage) -> list:
        """Collect composed layers and recursively reachable authored layer arcs."""
        layers = []
        pending = deque(stage.GetUsedLayers())
        seen = set()
        while pending:
            layer = pending.popleft()
            if not layer or layer.identifier in seen:
                continue
            seen.add(layer.identifier)
            layers.append(layer)

            authored_paths = list(layer.subLayerPaths)
            for prim_spec in _iter_prim_specs(layer.rootPrims):
                authored_paths.extend(
                    item.assetPath
                    for item in _list_op_items(prim_spec.referenceList) + _list_op_items(prim_spec.payloadList)
                    if item.assetPath
                )

            for authored_path in authored_paths:
                identifier = anchored_asset_identifier(layer, authored_path)
                if not identifier or identifier in seen:
                    continue
                try:
                    referenced_layer = Sdf.Layer.FindOrOpen(identifier)
                except Exception:
                    referenced_layer = None
                if referenced_layer:
                    pending.append(referenced_layer)
        return layers

    def _check_hierarchy_organization(self, stage: Usd.Stage, default_prim: Usd.Prim):
        """Check for proper Isaac Sim hierarchy organization"""
        # Look for common Isaac Sim structure indicators
        found_looks = False
        found_meshes = False
        found_visuals = False

        # Check entire stage for expected scopes
        for prim in Usd.PrimRange(stage.GetPseudoRoot()):
            if prim.GetName() == "Looks" and prim.GetTypeName() == "Scope":
                found_looks = True
            elif prim.GetName() == "Meshes" and prim.GetTypeName() == "Scope":
                found_meshes = True
                # Check if Meshes scope is invisible
                imageable = UsdGeom.Imageable(prim)
                if imageable.GetVisibilityAttr():
                    visibility = imageable.GetVisibilityAttr().Get()
                    if visibility != UsdGeom.Tokens.invisible:
                        self._AddFailedCheck(
                            "Meshes scope should be invisible for proper Isaac Sim composition.",
                            at=prim,
                            requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
                        )
            elif prim.GetName() == "Visuals" and prim.GetTypeName() == "Scope":
                found_visuals = True
                # Check if Visuals scope is invisible
                imageable = UsdGeom.Imageable(prim)
                if imageable.GetVisibilityAttr():
                    visibility = imageable.GetVisibilityAttr().Get()
                    if visibility != UsdGeom.Tokens.invisible:
                        self._AddFailedCheck(
                            "Visuals scope should be invisible for proper Isaac Sim composition.",
                            at=prim,
                            requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
                        )

        # Warning if expected scopes are not found (may be in payloads)
        if not (found_looks or found_meshes or found_visuals):
            # This is a soft warning since these might be in payload files
            pass  # Could add informational message if needed
