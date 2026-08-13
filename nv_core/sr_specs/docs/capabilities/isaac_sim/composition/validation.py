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
import re

import omni.capabilities as cap
import usd_validation_nvidia
from pxr import Kind, Usd, UsdGeom

# Payload layers are identified by *role* rather than by an exact filename, and the
# roles are grouped into the two payload layouts that ISA.001 governs:
#
#   "prop"  - SimReady prop content, per this requirement's "How to comply" section:
#             payloads/{asset_name}_base.usd + _meshes.usd + _physics.usd
#             (packaged assets conventionally prefix the stem with an underscore)
#   "robot" - the robot layout shared with RC.001, used by Robot-Body-Isaac:
#             payloads/base.usda + geometries.usd + instances.usda + materials.usda
#
# An asset satisfies the payload-structure check when it completely matches either
# layout. The two are disjoint: the prop patterns require an underscore before the
# role word, so "payloads/base.usda" never matches the prop "base" role.
#
# The trailing ``(\]|$)`` makes every pattern match BOTH forms of layer identifier:
#   on disk   ".../payloads/myasset_base.usd"
#   in a usdz ".../myasset.usdz[payloads/myasset_base.usd]"
_SUFFIX = r"\.usd[ac]?(\]|$)"

_LAYOUTS = {
    "prop": {
        role: re.compile(rf"payloads/[^/]*_{role}{_SUFFIX}", re.IGNORECASE)
        for role in ("base", "meshes", "physics")
    },
    "robot": {
        role: re.compile(rf"payloads/{role}{_SUFFIX}", re.IGNORECASE)
        for role in ("base", "geometries", "instances", "materials")
    },
}

_LAYOUT_DESCRIPTIONS = {
    "prop": "payloads/{asset_name}_base.usd + _meshes.usd + _physics.usd",
    "robot": "payloads/base.usda + geometries.usd + instances.usda + materials.usda",
}

# Either layout's base layer is an acceptable target for the default prim's arc.
_BASE_PATTERNS = (_LAYOUTS["prop"]["base"], _LAYOUTS["robot"]["base"])


def _normalize(identifier: str) -> str:
    """Normalize a layer identifier or asset path for role matching.

    On-disk identifiers may use OS-native separators; usdz-internal layers are
    always reported with forward slashes inside square brackets. Normalizing to
    forward slashes lets one pattern match both.
    """
    return identifier.replace("\\", "/")


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

        # Check for payload structure
        self._check_payload_structure(stage, default_prim)

        # Check for proper reference structure
        self._check_reference_structure(default_prim)

        # Check for proper hierarchy organization
        self._check_hierarchy_organization(stage, default_prim)

    @staticmethod
    def _root_arc_asset_paths(default_prim: Usd.Prim) -> list:
        """Asset paths of the reference and payload arcs authored on the default prim.

        Read from the root layer's prim spec, so this reflects what the asset
        itself declares rather than what composition happened to resolve.
        """
        root_layer = default_prim.GetStage().GetRootLayer()
        prim_spec = root_layer.GetPrimAtPath(default_prim.GetPath())
        if not prim_spec:
            return []

        arcs = prim_spec.referenceList.GetAddedOrExplicitItems()
        arcs += prim_spec.payloadList.GetAddedOrExplicitItems()
        return [_normalize(str(arc.assetPath)) for arc in arcs]

    def _check_payload_structure(self, stage: Usd.Stage, default_prim: Usd.Prim):
        """Check if the asset has proper payload structure.

        Driven by the composed layer stack rather than the OS filesystem, so a
        `.usdz` package -- whose ``payloads/`` layers live inside the archive and
        therefore have no sibling directory on disk -- is validated the same way
        as an unpacked asset.
        """
        # Union the composed layer stack with the arcs authored on the default
        # prim. GetUsedLayers() alone would miss an unloaded payload when the
        # stage was opened with a load rule other than LoadAll.
        candidates = [_normalize(layer.identifier) for layer in stage.GetUsedLayers()]
        candidates += self._root_arc_asset_paths(default_prim)

        missing_by_layout = {
            layout: [
                role
                for role, pattern in roles.items()
                if not any(pattern.search(candidate) for candidate in candidates)
            ]
            for layout, roles in _LAYOUTS.items()
        }

        # The asset passes if it completely matches either recognized layout.
        if any(not missing for missing in missing_by_layout.values()):
            return

        # Otherwise report against the closest layout, so a nearly-complete asset
        # gets told which layer it is actually missing rather than a generic error.
        closest = min(missing_by_layout, key=lambda layout: len(missing_by_layout[layout]))
        missing = missing_by_layout[closest]

        if len(missing) == len(_LAYOUTS[closest]):
            accepted = " or ".join(
                f"{layout} ({_LAYOUT_DESCRIPTIONS[layout]})" for layout in _LAYOUTS
            )
            self._AddFailedCheck(
                f"No recognized Isaac Sim payload structure found. Expected {accepted}.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        for role in missing:
            self._AddFailedCheck(
                f"Incomplete {closest} Isaac Sim payload structure: no '{role}' layer is "
                f"composed into the stage. Expected {_LAYOUT_DESCRIPTIONS[closest]}.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

    def _check_reference_structure(self, default_prim: Usd.Prim):
        """Check if default prim has proper references and payloads."""
        root_layer = default_prim.GetStage().GetRootLayer()
        if not root_layer.GetPrimAtPath(default_prim.GetPath()):
            self._AddFailedCheck(
                "Could not resolve prim spec for default prim.",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )
            return

        arc_paths = self._root_arc_asset_paths(default_prim)
        if not any(pattern.search(path) for pattern in _BASE_PATTERNS for path in arc_paths):
            self._AddFailedCheck(
                "Default prim must reference or payload the base layer "
                "(payloads/{asset_name}_base.usd or payloads/base.usda).",
                at=default_prim,
                requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
            )

    def _check_hierarchy_organization(self, stage: Usd.Stage, default_prim: Usd.Prim):
        """Check for proper Isaac Sim hierarchy organization."""
        # The "Looks", "Meshes" and "Visuals" scopes may legitimately live inside a
        # payload, so their absence is not an error here; only assert invisibility
        # on the scopes that are actually present in the composed stage.
        for prim in Usd.PrimRange(stage.GetPseudoRoot()):
            if prim.GetName() not in ("Meshes", "Visuals") or prim.GetTypeName() != "Scope":
                continue

            visibility_attr = UsdGeom.Imageable(prim).GetVisibilityAttr()
            if not visibility_attr:
                continue

            visibility = visibility_attr.Get()
            # An unauthored visibility attribute resolves to None; treat only an
            # explicitly visible scope as a failure.
            if visibility is not None and visibility != UsdGeom.Tokens.invisible:
                self._AddFailedCheck(
                    f"{prim.GetName()} scope should be invisible for proper Isaac Sim composition.",
                    at=prim,
                    requirement=self.ISAAC_COMPOSITION_REQUIREMENT,
                )
