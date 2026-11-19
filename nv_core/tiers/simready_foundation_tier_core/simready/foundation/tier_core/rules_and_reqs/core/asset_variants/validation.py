# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Validation rules for the Asset Variants capability (AV.001-AV.010).

The asset-variation contract generalizes the physics-runtime variant pattern in
``runtime_variants`` to arbitrary variation categories
(``Representation``, ``MeshVariant``, ``Collision``, ``Appearance``) discoverable
under ``customLayerData.SimReady_Metadata.Variants.<Category>``. A variation
changes visual/collider content while holding the visual and collision envelopes
invariant, declares an honest impact class, and keeps every shared prim's type
and authored transform stable so an option only adds or removes geometry leaves
under a stable part prim.
"""

from typing import Dict, List, Optional, Tuple

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Usd, UsdGeom, UsdPhysics

from simready.foundation.tier_core import asset_variants as av


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _variation_sets_on(prim: Usd.Prim, categories) -> List[str]:
    """Authored variant-set names on ``prim`` that belong to a variation category."""
    out: List[str] = []
    for name in prim.GetVariantSets().GetNames():
        for category in categories:
            if name == av.master_set_name(category) or av.is_per_part_set(category, name):
                out.append(name)
                break
    return out


def _physics_fingerprint(stage: Usd.Stage) -> Dict[str, Dict[str, str]]:
    """Map prim path -> {property: value-repr} for physics/collider data under the root.

    Covers applied schemas and every ``physics:``/``physx``/``newton:``/``mjc:``
    property, so two compositions can be compared for simulation-relevant drift.
    """
    out: Dict[str, Dict[str, str]] = {}
    root = stage.GetDefaultPrim()
    if not root or not root.IsValid():
        return out
    for prim in Usd.PrimRange(root):
        entry: Dict[str, str] = {}
        schemas = [s for s in prim.GetAppliedSchemas() if _is_physics_schema(s)]
        if schemas:
            entry["__apiSchemas__"] = ",".join(sorted(schemas))
        for prop in prim.GetPropertyNames():
            if _is_physics_property(prop):
                attr = prim.GetAttribute(prop)
                entry[prop] = repr(attr.Get()) if attr and attr.HasValue() else "<unset>"
        if entry:
            out[str(prim.GetPath())] = entry
    return out


def _is_physics_schema(name: str) -> bool:
    return name.startswith(("Physics", "Physx", "Newton", "Mjc"))


def _is_physics_property(name: str) -> bool:
    return name.startswith(("physics:", "physx", "newton:", "mjc:"))


# Geometry-defining attributes that determine a collider's actual shape. Mesh
# topology/points plus the analytic-Gprim size attributes. The collision envelope
# (AV.006) only catches a bounding-box resize; a shape swap that keeps the same
# extent (a cube replaced by a same-extent octahedron) changes contact behavior
# while leaving the envelope and every physics property value untouched.
_COLLIDER_GEOMETRY_ATTRS = (
    "points",
    "faceVertexCounts",
    "faceVertexIndices",
    "size",
    "radius",
    "height",
    "axis",
    "extent",
)


def _collider_geometry_fingerprint(stage: Usd.Stage) -> Dict[str, Dict[str, str]]:
    """Map collider prim path -> {prim type + shape-defining attribute values}.

    Covers every prim carrying ``UsdPhysics.CollisionAPI`` under the default prim
    so two compositions can be compared for a collider shape or prim-type swap
    that holds the collision envelope and physics property values invariant.
    """
    out: Dict[str, Dict[str, str]] = {}
    root = stage.GetDefaultPrim()
    if not root or not root.IsValid():
        return out
    for prim in Usd.PrimRange(root):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        entry: Dict[str, str] = {"__type__": str(prim.GetTypeName())}
        for attr_name in _COLLIDER_GEOMETRY_ATTRS:
            attr = prim.GetAttribute(attr_name)
            if attr and attr.HasAuthoredValue():
                entry[attr_name] = repr(attr.Get())
        out[str(prim.GetPath())] = entry
    return out


def _mass_fingerprint(stage: Usd.Stage) -> Dict[str, dict]:
    return {str(p.GetPath()): av.authored_mass_properties(p) for p in av.iter_mass_bearing_prims(stage)}


def _stability_fingerprint(stage: Usd.Stage) -> Dict[str, Tuple[str, Optional[Gf.Matrix4d]]]:
    """Map prim path -> (typeName, composed local transform) under the default prim.

    Lets two compositions be compared for a prim that changes its type or its
    authored local transform across a variation set's options. A prim present in
    only some options is an added/removed geometry leaf, which is allowed.
    """
    out: Dict[str, Tuple[str, Optional[Gf.Matrix4d]]] = {}
    root = stage.GetDefaultPrim()
    if not root or not root.IsValid():
        return out
    for prim in Usd.PrimRange(root):
        xform: Optional[Gf.Matrix4d] = None
        xformable = UsdGeom.Xformable(prim)
        if xformable:
            try:
                xform = xformable.GetLocalTransformation(Usd.TimeCode.Default())
            except Exception:  # noqa: BLE001 - treat an unreadable xform as absent
                xform = None
        out[str(prim.GetPath())] = (str(prim.GetTypeName()), xform)
    return out


def _xforms_match(a: Optional[Gf.Matrix4d], b: Optional[Gf.Matrix4d], tol: float = 1e-6) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    for i in range(4):
        row_a, row_b = a.GetRow(i), b.GetRow(i)
        for j in range(4):
            if abs(row_a[j] - row_b[j]) > tol:
                return False
    return True


# --------------------------------------------------------------------------- #
# AV.001 - discovery metadata
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_001)
class VariationDiscoveryMetadataChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.001: Variants.<Category> entries resolve and tell the truth."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        categories = list(av.variation_metadata(stage).keys())

        # Every declared entry must be well-formed.
        for category, variant_set_name, entry in av.iter_variation_entries(stage):
            self._check_entry(stage, default_prim, category, variant_set_name, entry)

        # A variation set authored on the prim but absent from metadata fails.
        declared = {name for _, name, _ in av.iter_variation_entries(stage)}
        for name in _variation_sets_on(default_prim, av.KNOWN_CATEGORIES):
            if name not in declared:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Variant set '{name}' on <{default_prim.GetPath()}> is not declared under "
                        f"customLayerData.SimReady_Metadata.Variants."
                    ),
                    at=default_prim,
                )

    def _check_entry(self, stage, default_prim, category, variant_set_name, entry) -> None:
        if category == av.RESERVED_CATEGORY:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=f"'{av.RESERVED_CATEGORY}' is reserved for runtime_variants and must not be an asset variation.",
                at=stage,
            )
            return

        missing = [k for k in av.REQUIRED_ENTRY_KEYS if not entry.get(k)]
        if missing:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=f"Variants.{category}['{variant_set_name}'] is missing key(s): {', '.join(missing)}.",
                at=stage,
            )
            return

        if entry.get("variantSetName") != variant_set_name:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variants.{category}['{variant_set_name}'].variantSetName is "
                    f"'{entry.get('variantSetName')}', expected '{variant_set_name}'."
                ),
                at=stage,
            )
        if entry.get("category") != category:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variants.{category}['{variant_set_name}'].category is '{entry.get('category')}', "
                    f"expected '{category}'."
                ),
                at=stage,
            )
        if entry.get("impactClass") not in av.IMPACT_CLASSES:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variants.{category}['{variant_set_name}'].impactClass "
                    f"'{entry.get('impactClass')}' is not one of {av.IMPACT_CLASSES}."
                ),
                at=stage,
            )

        declared_prim = stage.GetPrimAtPath(entry.get("prim", ""))
        if not declared_prim or not declared_prim.IsValid():
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=f"Variants.{category}['{variant_set_name}'].prim '{entry.get('prim')}' does not resolve.",
                at=stage,
            )
            return
        if variant_set_name not in declared_prim.GetVariantSets().GetNames():
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variants.{category}['{variant_set_name}'].prim '{entry.get('prim')}' does not own a "
                    f"'{variant_set_name}' variant set."
                ),
                at=declared_prim,
            )
            return

        options = av.option_names(declared_prim, variant_set_name)
        if entry.get("default") not in options:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variants.{category}['{variant_set_name}'].default '{entry.get('default')}' is not a "
                    f"declared option ({options})."
                ),
                at=declared_prim,
            )


# --------------------------------------------------------------------------- #
# AV.002 - variant-set location and default
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_002)
class VariationVariantSetChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.002: variation sets live on the default prim with a valid authored default."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_002

    def CheckStage(self, stage: Usd.Stage) -> None:
        if not list(av.iter_variation_entries(stage)):
            return
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message="An asset declaring variations must have a valid defaultPrim to host the variant sets.",
                at=stage.GetPseudoRoot(),
            )
            return

        for category, variant_set_name, entry in av.iter_variation_entries(stage):
            owner_path = entry.get("prim")
            if owner_path and owner_path != str(default_prim.GetPath()):
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Variation set '{variant_set_name}' is hosted on '{owner_path}', but variation sets "
                        f"must live on the default prim <{default_prim.GetPath()}>."
                    ),
                    at=default_prim,
                )
                continue
            if variant_set_name not in default_prim.GetVariantSets().GetNames():
                continue  # AV.001 reports the missing set.

            options = av.option_names(default_prim, variant_set_name)
            if len(options) < 2:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=f"Variation set '{variant_set_name}' must declare at least two options, found {options}.",
                    at=default_prim,
                )
            selection = av.authored_default_selection(stage, default_prim, variant_set_name)
            if selection not in options:
                # A per-part set may inherit its default from a same-category master
                # that drives it: the master authors the per-part child selection
                # (AV.004), so the asset still composes to a known default state
                # without the per-part set authoring its own root selection. The
                # master's root default, validated below, supplies that state -- but
                # only when the master is ordered strongly enough to actually drive
                # the per-part set, so verify the drive composes, not just that a
                # master exists.
                if av.is_per_part_set(category, variant_set_name) and self._master_supplies_default(
                    stage, default_prim, category
                ):
                    if self._master_drives(stage, default_prim, category, variant_set_name):
                        continue
                    master = av.master_set_name(category)
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=(
                            f"Per-part set '{variant_set_name}' omits a root default and relies on the master "
                            f"set '{master}', but '{master}' does not drive it: the composed selection is the "
                            f"same for every '{master}' option. Order '{master}' before the per-part-bearing "
                            f"sets in the prim's variantSets so its child selections take effect, or author a "
                            f"root default on '{variant_set_name}'."
                        ),
                        at=default_prim,
                    )
                    continue
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Variation set '{variant_set_name}' must author a default selection naming one of "
                        f"{options}, found '{selection}'."
                    ),
                    at=default_prim,
                )

    @staticmethod
    def _master_supplies_default(stage, default_prim, category) -> bool:
        """True when a same-category master set on the default prim authors a valid
        default selection, so it drives the per-part sets' default state."""
        master = av.master_set_name(category)
        if master not in default_prim.GetVariantSets().GetNames():
            return False
        master_selection = av.authored_default_selection(stage, default_prim, master)
        return master_selection in av.option_names(default_prim, master)

    @staticmethod
    def _master_drives(stage, default_prim, category, per_part_name) -> bool:
        """True when the master set actually controls ``per_part_name``.

        Composes each master option and reads the per-part set's resulting
        selection; the master drives it only when that selection changes across
        the master's options. A master ordered more weakly than the per-part set's
        payload-surfaced default is inert and leaves the selection constant.
        """
        master = av.master_set_name(category)
        root_layer = stage.GetRootLayer()
        resolved = set()
        for option in av.option_names(default_prim, master):
            try:
                composed = av.compose_with_selection(root_layer, {master: option})
            except Exception:  # noqa: BLE001
                continue
            composed_prim = composed.GetDefaultPrim()
            if composed_prim and per_part_name in composed_prim.GetVariantSets().GetNames():
                resolved.add(composed_prim.GetVariantSet(per_part_name).GetVariantSelection())
        return len(resolved) > 1


# --------------------------------------------------------------------------- #
# AV.003 - per-option composability
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_003)
class VariationOptionComposabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.003: every option recomposes to a valid, non-empty stage."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_003

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return
        root_layer = stage.GetRootLayer()

        for _category, variant_set_name, _entry in av.iter_variation_entries(stage):
            if variant_set_name not in default_prim.GetVariantSets().GetNames():
                continue
            for option in av.option_names(default_prim, variant_set_name):
                try:
                    composed = av.compose_with_selection(root_layer, {variant_set_name: option})
                except Exception as error:  # noqa: BLE001 - surface compose failure as a check
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=f"Option '{variant_set_name}={option}' failed to compose: {error}",
                        at=default_prim,
                    )
                    continue
                composed_root = composed.GetDefaultPrim()
                if not composed_root or not composed_root.IsValid():
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=f"Option '{variant_set_name}={option}' composes no valid default prim.",
                        at=default_prim,
                    )
                    continue
                if not any(True for _ in Usd.PrimRange(composed_root) if _ != composed_root):
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=f"Option '{variant_set_name}={option}' composes an empty asset (no content).",
                        at=default_prim,
                    )


# --------------------------------------------------------------------------- #
# AV.004 - section purity and per-selection isolation
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_004)
class VariationSectionPurityChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.004: per-part options carry only a payload arc; master options carry only selections."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_004

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return
        prim_spec = stage.GetRootLayer().GetPrimAtPath(default_prim.GetPath())
        if prim_spec is None:
            return

        categories = list(av.variation_metadata(stage).keys())
        for vs_name, variant_set_spec in prim_spec.variantSets.items():
            category = self._category_of(vs_name, categories)
            if category is None:
                continue
            is_master = vs_name == av.master_set_name(category)
            for opt_name, variant_spec in variant_set_spec.variants.items():
                self._check_option(default_prim, vs_name, opt_name, variant_spec.primSpec, is_master)

    @staticmethod
    def _category_of(vs_name, categories):
        for category in categories:
            if vs_name == av.master_set_name(category) or av.is_per_part_set(category, vs_name):
                return category
        return None

    def _check_option(self, at, vs_name, opt_name, variant_prim_spec, is_master) -> None:
        if variant_prim_spec is None:
            return
        children = len(variant_prim_spec.nameChildren)
        properties = len(variant_prim_spec.properties)
        nested_sets = len(variant_prim_spec.variantSets)
        payloads = self._listop_len(variant_prim_spec.payloadList)
        references = self._listop_len(variant_prim_spec.referenceList)
        inherits = self._listop_len(variant_prim_spec.inheritPathList)
        specializes = self._listop_len(variant_prim_spec.specializesList)
        selections = len(variant_prim_spec.variantSelections)

        if is_master:
            extras = []
            if children:
                extras.append(f"{children} inline child prim(s)")
            if properties:
                extras.append(f"{properties} inline property(ies)")
            if payloads:
                extras.append("payload arc(s)")
            if references:
                extras.append("reference arc(s)")
            if inherits or specializes:
                extras.append("inherit/specialize arc(s)")
            if extras:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Master option '{vs_name}={opt_name}' must author only child variant selections, "
                        f"but also authors: {', '.join(extras)}."
                    ),
                    at=at,
                )
            elif selections == 0 and nested_sets == 0:
                self._AddWarning(
                    requirement=self.REQUIREMENT,
                    message=f"Master option '{vs_name}={opt_name}' authors no child selections.",
                    at=at,
                )
        else:
            extras = []
            if children:
                extras.append(f"{children} inline child prim(s)")
            if properties:
                extras.append(f"{properties} inline property(ies)")
            if nested_sets:
                extras.append("nested variant set(s)")
            if references:
                extras.append("reference arc(s)")
            if inherits or specializes:
                extras.append("inherit/specialize arc(s)")
            if extras:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Per-part option '{vs_name}={opt_name}' must compose only through its payload arc, "
                        f"but also authors: {', '.join(extras)}. Move content into an isolated payload."
                    ),
                    at=at,
                )

    @staticmethod
    def _listop_len(list_op) -> int:
        if list_op is None:
            return 0
        total = 0
        for items in (
            list_op.explicitItems,
            list_op.prependedItems,
            list_op.appendedItems,
            list_op.addedItems,
            list_op.orderedItems,
        ):
            total += len(items)
        return total


# --------------------------------------------------------------------------- #
# Envelope-invariant base (AV.005 / AV.006)
# --------------------------------------------------------------------------- #
class _EnvelopeInvariantBase(usd_validation_nvidia.BaseRuleChecker):
    REQUIREMENT = None
    ENVELOPE_LABEL = ""

    def _envelope_size(self, stage):  # pragma: no cover - overridden
        raise NotImplementedError

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return
        root_layer = stage.GetRootLayer()
        baseline = self._envelope_size(stage)
        if baseline is None:
            return  # No relevant geometry (e.g. no colliders for AV.006).

        for _category, variant_set_name, _entry in av.iter_variation_entries(stage):
            if variant_set_name not in default_prim.GetVariantSets().GetNames():
                continue
            for option in av.option_names(default_prim, variant_set_name):
                try:
                    composed = av.compose_with_selection(root_layer, {variant_set_name: option})
                    size = self._envelope_size(composed)
                except Exception:  # noqa: BLE001
                    continue
                if size is None:
                    continue
                if not av.sizes_match(baseline, size):
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=(
                            f"Option '{variant_set_name}={option}' changes the {self.ENVELOPE_LABEL} envelope size "
                            f"from {tuple(round(v, 4) for v in baseline)} to {tuple(round(v, 4) for v in size)} "
                            f"(tolerance {av.ENVELOPE_TOLERANCE_M} m)."
                        ),
                        at=default_prim,
                    )


@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_005)
class VisualEnvelopeInvariantChecker(_EnvelopeInvariantBase):
    """AV.005: every option holds the visual envelope size invariant."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_005
    ENVELOPE_LABEL = "visual"

    def _envelope_size(self, stage):
        return av.envelope_size(av.visual_envelope(stage))


@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_006)
class CollisionEnvelopeInvariantChecker(_EnvelopeInvariantBase):
    """AV.006: every option that carries colliders holds the collision envelope invariant."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_006
    ENVELOPE_LABEL = "collision"

    def _envelope_size(self, stage):
        return av.envelope_size(av.collision_envelope(stage))


# --------------------------------------------------------------------------- #
# AV.007 - impact-class honesty
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_007)
class ImpactClassHonestyChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.007: the declared impact class matches what the options actually change."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_007

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return
        root_layer = stage.GetRootLayer()
        baseline_physics = _physics_fingerprint(stage)
        baseline_collider_geometry = _collider_geometry_fingerprint(stage)
        baseline_collision = av.envelope_size(av.collision_envelope(stage))

        for category, variant_set_name, entry in av.iter_variation_entries(stage):
            if variant_set_name not in default_prim.GetVariantSets().GetNames():
                continue
            impact = entry.get("impactClass")
            # The Collision category's declared impact class is simulation-affecting
            # (FET015_CollisionVariant): a Collision variation changes collider data
            # by definition, so declaring it visual-only is inherently dishonest.
            if impact == av.IMPACT_VISUAL_ONLY and category == av.CATEGORY_COLLISION:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Variant set '{variant_set_name}' is in the Collision category, which is "
                        f"simulation-affecting, but declares impactClass 'visual-only'. A Collision "
                        f"variation changes collider data; declare it 'simulation-affecting'."
                    ),
                    at=default_prim,
                )
            for option in av.option_names(default_prim, variant_set_name):
                try:
                    composed = av.compose_with_selection(root_layer, {variant_set_name: option})
                except Exception:  # noqa: BLE001
                    continue
                if impact == av.IMPACT_VISUAL_ONLY:
                    self._check_visual_only(
                        default_prim,
                        variant_set_name,
                        option,
                        composed,
                        baseline_physics,
                        baseline_collider_geometry,
                        baseline_collision,
                    )
                elif impact == av.IMPACT_SIMULATION_AFFECTING:
                    self._check_simulation_affecting(default_prim, variant_set_name, option, composed, baseline_collision)

    def _check_visual_only(
        self, at, vs_name, option, composed, baseline_physics, baseline_collider_geometry, baseline_collision
    ) -> None:
        if _physics_fingerprint(composed) != baseline_physics:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"'{vs_name}' is declared visual-only, but option '{option}' changes physics/collider data."
                ),
                at=at,
            )
        if _collider_geometry_fingerprint(composed) != baseline_collider_geometry:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"'{vs_name}' is declared visual-only, but option '{option}' changes collider geometry "
                    f"(collider shape, topology, or prim type). Only visual geometry/material/encoding may differ."
                ),
                at=at,
            )
        size = av.envelope_size(av.collision_envelope(composed))
        if not av.sizes_match(baseline_collision, size):
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=f"'{vs_name}' is declared visual-only, but option '{option}' changes the collision envelope.",
                at=at,
            )

    def _check_simulation_affecting(self, at, vs_name, option, composed, baseline_collision) -> None:
        # The only simulation-affecting category in 0.1.0 is Collision, whose
        # declared domain is collision-contact behavior: the collision envelope
        # and authored mass must stay invariant (AV.006/AV.009 enforce those);
        # only collider fidelity may differ. Flag an envelope change here too so
        # a dishonest "simulation-affecting" that resizes contact is caught.
        size = av.envelope_size(av.collision_envelope(composed))
        if not av.sizes_match(baseline_collision, size):
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"'{vs_name}' is simulation-affecting (Collision), but option '{option}' resizes the collision "
                    f"envelope; fidelity may change, footprint may not."
                ),
                at=at,
            )


# --------------------------------------------------------------------------- #
# AV.008 - conditional presence
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_008)
class ConditionalPresenceChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.008: a variant set exists iff its scope offers two or more options."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_008

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        categories = list(av.variation_metadata(stage).keys())
        for vs_name in _variation_sets_on(default_prim, categories or av.KNOWN_CATEGORIES):
            options = av.option_names(default_prim, vs_name)
            if len(options) < 2:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Variant set '{vs_name}' offers {len(options)} option(s); a variation set must exist only "
                        f"when its scope offers two or more. Remove the single-option set."
                    ),
                    at=default_prim,
                )


# --------------------------------------------------------------------------- #
# AV.009 - authored, not derived, physical properties
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_009)
class AuthoredPhysicalPropertiesChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.009: a Collision variation requires authored, invariant mass/COM/inertia."""

    REQUIREMENT = cap.AssetVariantsRequirements.AV_009

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        collision_sets = [
            name
            for _c, name, entry in av.iter_variation_entries(stage)
            if entry.get("category") == av.CATEGORY_COLLISION and name in default_prim.GetVariantSets().GetNames()
        ]
        if not collision_sets:
            return

        mass_prims = list(av.iter_mass_bearing_prims(stage))
        if not mass_prims:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    "A Collision variation requires a rigid body with explicitly authored UsdPhysics.MassAPI "
                    "mass/centerOfMass/inertia, but no mass-bearing prim was found."
                ),
                at=default_prim,
            )
            return

        for prim in mass_prims:
            props = av.authored_mass_properties(prim)
            missing = [k for k in ("mass", "centerOfMass", "diagonalInertia") if k not in props]
            if missing:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"<{prim.GetPath()}> carries a Collision variation but does not explicitly author: "
                        f"{', '.join(missing)}."
                    ),
                    at=prim,
                )
            mass = props.get("mass")
            if mass is not None and not (mass > 0):
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=f"<{prim.GetPath()}> authors non-positive physics:mass {mass}.",
                    at=prim,
                )

        # Mass properties must be invariant across the Collision options.
        root_layer = stage.GetRootLayer()
        baseline = _mass_fingerprint(stage)
        for vs_name in collision_sets:
            for option in av.option_names(default_prim, vs_name):
                try:
                    composed = av.compose_with_selection(root_layer, {vs_name: option})
                except Exception:  # noqa: BLE001
                    continue
                if _mass_fingerprint(composed) != baseline:
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=(
                            f"Collision option '{vs_name}={option}' changes authored mass properties; mass, center "
                            f"of mass, and inertia must be identical across collider options."
                        ),
                        at=default_prim,
                    )


# --------------------------------------------------------------------------- #
# AV.010 - variation stability (stable part, swappable child)
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("AssetVariants")
@usd_validation_nvidia.register_requirements(cap.AssetVariantsRequirements.AV_010)
class VariationStabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """AV.010: no shared prim changes type or authored transform across a set's options.

    A variation swaps a geometry child of a stable part prim; it may only add or
    remove geometry leaves. Any prim present in two or more options of one set
    must keep its prim type and composed local transform, so an authored or
    interactive pose (an opened lid) survives a selection change and a render
    mesh never mutates its type in place into a splat (a renderer-ghost hazard).
    """

    REQUIREMENT = cap.AssetVariantsRequirements.AV_010

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return
        root_layer = stage.GetRootLayer()

        for _category, variant_set_name, _entry in av.iter_variation_entries(stage):
            if variant_set_name not in default_prim.GetVariantSets().GetNames():
                continue
            fingerprints: Dict[str, Dict[str, Tuple[str, Optional[Gf.Matrix4d]]]] = {}
            for option in av.option_names(default_prim, variant_set_name):
                try:
                    composed = av.compose_with_selection(root_layer, {variant_set_name: option})
                except Exception:  # noqa: BLE001 - AV.003 reports a compose failure
                    continue
                fingerprints[option] = _stability_fingerprint(composed)
            self._compare_options(default_prim, variant_set_name, fingerprints)

    def _compare_options(self, at, vs_name, fingerprints) -> None:
        options = list(fingerprints)
        if len(options) < 2:
            return
        baseline_option = options[0]
        baseline = fingerprints[baseline_option]
        for option in options[1:]:
            current = fingerprints[option]
            for path in sorted(set(baseline) & set(current)):
                base_type, base_xf = baseline[path]
                cur_type, cur_xf = current[path]
                if base_type != cur_type:
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=(
                            f"Prim <{path}> changes type from '{base_type}' to '{cur_type}' between options "
                            f"'{vs_name}={baseline_option}' and '{vs_name}={option}'. A variation must add or remove "
                            f"a geometry child of a stable part prim, not redefine a shared prim's type (give each "
                            f"type its own child name, e.g. Geo_mesh / Geo_splat)."
                        ),
                        at=at,
                    )
                elif not _xforms_match(base_xf, cur_xf):
                    self._AddFailedCheck(
                        requirement=self.REQUIREMENT,
                        message=(
                            f"Prim <{path}> changes its authored local transform between options "
                            f"'{vs_name}={baseline_option}' and '{vs_name}={option}'. The part prim's transform "
                            f"(pose and pivot) must live on a stable prim outside every variant section so an "
                            f"interactive or authored pose survives a selection change."
                        ),
                        at=at,
                    )
