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
"""
Validation rules for the Runtime Variants capability.

Enforces the per-runtime physics variant contract used by SimReady assets that
expose neutral + runtime-specialized physics through USD variant sets and
runtime payloads. Requirements are grouped by runtime so a feature can adopt
only the runtimes it targets:

- PhysX : RV.001 (variant set), RV.002 (payload), RV.003 (metadata)
- Newton: RV.004 (variant set), RV.005 (payload), RV.006 (metadata)
- MuJoCo: RV.007 (variant set), RV.008 (payload), RV.009 (metadata)

Two cross-runtime rules govern how the variants compose:

- RV.010: variant-section purity (Enabled composes only its payload arc,
  Disabled is empty).
- RV.011: runtime physics isolation (a selected runtime composes only its own
  + neutral physics, with no foreign schemas/attributes or conflicting
  ``physics:approximation`` values).

Each runtime uses a variant set named after the runtime (``PhysX``, ``Newton``,
``MuJoCo``) with ``Disabled``/``Enabled`` options (default ``Disabled``), whose
``Enabled`` option prepends an anchored payload
``runnables/physics/<stem>.usd(a)`` and is documented under
``customLayerData.SimReady_Metadata.Variants.Physics.<VariantSetName>``.
"""

from typing import List

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Usd

REQUIRED_OPTIONS = ("Disabled", "Enabled")
DEFAULT_OPTION = "Disabled"
ENABLED_OPTION = "Enabled"

# Location (relative to the asset root) that runtime payload layers must live in.
RUNTIME_PAYLOAD_DIR = "runnables/physics"

_ALLOWED_PAYLOAD_EXTS = ("usd", "usda", "usdc")


def _iter_payload_asset_paths(payload_list_op) -> List[str]:
    """Collect asset paths from every field of an Sdf payload list op."""
    asset_paths: List[str] = []
    if payload_list_op is None:
        return asset_paths
    for items in (
        payload_list_op.explicitItems,
        payload_list_op.prependedItems,
        payload_list_op.appendedItems,
        payload_list_op.addedItems,
        payload_list_op.orderedItems,
    ):
        for payload in items:
            asset_path = getattr(payload, "assetPath", "")
            if asset_path:
                asset_paths.append(asset_path)
    return asset_paths


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


class _RuntimeVariantSetCheckerBase(usd_validation_nvidia.BaseRuleChecker):
    """Base: default prim exposes ``VARIANT_SET_NAME`` with Disabled/Enabled, default Disabled.

    Concrete subclasses set ``VARIANT_SET_NAME`` and ``REQUIREMENT``.
    """

    VARIANT_SET_NAME: str = ""
    REQUIREMENT = None

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Stage has no valid default prim to host the '{self.VARIANT_SET_NAME}' "
                    f"physics runtime variant set."
                ),
                at=stage,
            )
            return

        variant_sets = default_prim.GetVariantSets()
        if self.VARIANT_SET_NAME not in set(variant_sets.GetNames()):
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Default prim <{default_prim.GetPath()}> must declare a "
                    f"'{self.VARIANT_SET_NAME}' physics runtime variant set."
                ),
                at=default_prim,
            )
            return

        options = set(variant_sets.GetVariantSet(self.VARIANT_SET_NAME).GetVariantNames())
        missing_options = [opt for opt in REQUIRED_OPTIONS if opt not in options]
        if missing_options:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variant set '{self.VARIANT_SET_NAME}' on <{default_prim.GetPath()}> is "
                    f"missing required option(s): {', '.join(missing_options)}."
                ),
                at=default_prim,
            )

        prim_spec = stage.GetRootLayer().GetPrimAtPath(default_prim.GetPath())
        authored_selections = dict(prim_spec.variantSelections) if prim_spec else {}
        selection = authored_selections.get(self.VARIANT_SET_NAME)
        if selection != DEFAULT_OPTION:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"Variant set '{self.VARIANT_SET_NAME}' must default to '{DEFAULT_OPTION}', "
                    f"but the authored default selection is '{selection}'."
                ),
                at=default_prim,
            )


class _RuntimePayloadCheckerBase(usd_validation_nvidia.BaseRuleChecker):
    """Base: ``VARIANT_SET_NAME`` Enabled variant composes an anchored payload
    ``runnables/physics/<PAYLOAD_STEM>.usd(a)``.

    Concrete subclasses set ``VARIANT_SET_NAME``, ``PAYLOAD_STEM``, and ``REQUIREMENT``.
    """

    VARIANT_SET_NAME: str = ""
    PAYLOAD_STEM: str = ""
    REQUIREMENT = None

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            # The variant-set rule already reports the missing default prim.
            return

        prim_spec = stage.GetRootLayer().GetPrimAtPath(default_prim.GetPath())
        if prim_spec is None:
            return

        variant_set_spec = prim_spec.variantSets.get(self.VARIANT_SET_NAME)
        if variant_set_spec is None:
            # Missing variant set is reported by the variant-set rule.
            return

        variant_spec = variant_set_spec.variants.get(ENABLED_OPTION)
        if variant_spec is None:
            # Missing Enabled option is reported by the variant-set rule.
            return

        asset_paths = _iter_payload_asset_paths(variant_spec.primSpec.payloadList)
        if not asset_paths:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"'{self.VARIANT_SET_NAME}' variant '{ENABLED_OPTION}' must compose a runtime "
                    f"payload under '{RUNTIME_PAYLOAD_DIR}/', but no payload is authored."
                ),
                at=default_prim,
            )
            return

        for asset_path in asset_paths:
            normalized = _normalize(asset_path)

            if not (normalized.startswith("./") or normalized.startswith("../")):
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"'{self.VARIANT_SET_NAME}' Enabled payload '{asset_path}' must use an "
                        f"anchored relative path (starting with './' or '../')."
                    ),
                    at=default_prim,
                )

            if f"{RUNTIME_PAYLOAD_DIR}/" not in normalized:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"'{self.VARIANT_SET_NAME}' Enabled payload '{asset_path}' must resolve "
                        f"under '{RUNTIME_PAYLOAD_DIR}/'."
                    ),
                    at=default_prim,
                )

            file_name = normalized.rsplit("/", 1)[-1]
            stem, _, ext = file_name.partition(".")
            if stem != self.PAYLOAD_STEM or ext not in _ALLOWED_PAYLOAD_EXTS:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"'{self.VARIANT_SET_NAME}' Enabled payload should be named "
                        f"'{self.PAYLOAD_STEM}.usd' or '{self.PAYLOAD_STEM}.usda' under "
                        f"'{RUNTIME_PAYLOAD_DIR}/', found '{file_name}'."
                    ),
                    at=default_prim,
                )


class _RuntimeMetadataCheckerBase(usd_validation_nvidia.BaseRuleChecker):
    """Base: SimReady_Metadata.Variants.Physics.<VARIANT_SET_NAME> documents the variant set.

    Concrete subclasses set ``VARIANT_SET_NAME`` and ``REQUIREMENT``.
    """

    VARIANT_SET_NAME: str = ""
    REQUIREMENT = None
    _REQUIRED_ENTRY_KEYS = ("prim", "variantSetName", "activateOption")

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        # Only require metadata for a variant set that is actually authored; a
        # missing variant set itself is reported by the variant-set rule.
        if self.VARIANT_SET_NAME not in set(default_prim.GetVariantSets().GetNames()):
            return

        custom_layer_data = stage.GetRootLayer().customLayerData or {}
        sim_ready_metadata = custom_layer_data.get("SimReady_Metadata", {})
        variants = sim_ready_metadata.get("Variants", {}) if sim_ready_metadata else {}
        physics = variants.get("Physics", {}) if variants else {}

        entry = physics.get(self.VARIANT_SET_NAME) if physics else None
        if not entry:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"customLayerData.SimReady_Metadata.Variants.Physics is missing an entry for "
                    f"the '{self.VARIANT_SET_NAME}' runtime variant set."
                ),
                at=stage,
            )
            return

        missing_keys = [k for k in self._REQUIRED_ENTRY_KEYS if not entry.get(k)]
        if missing_keys:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"SimReady_Metadata.Variants.Physics['{self.VARIANT_SET_NAME}'] is missing "
                    f"required key(s): {', '.join(missing_keys)}."
                ),
                at=stage,
            )
            return

        if entry.get("variantSetName") != self.VARIANT_SET_NAME:
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"SimReady_Metadata.Variants.Physics['{self.VARIANT_SET_NAME}'].variantSetName "
                    f"is '{entry.get('variantSetName')}', expected '{self.VARIANT_SET_NAME}'."
                ),
                at=stage,
            )

        declared_prim_path = entry.get("prim")
        declared_prim = stage.GetPrimAtPath(declared_prim_path) if declared_prim_path else None
        if declared_prim is None or not declared_prim.IsValid():
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"SimReady_Metadata.Variants.Physics['{self.VARIANT_SET_NAME}'].prim "
                    f"'{declared_prim_path}' does not resolve to a valid prim."
                ),
                at=stage,
            )
        elif self.VARIANT_SET_NAME not in declared_prim.GetVariantSets().GetNames():
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"SimReady_Metadata.Variants.Physics['{self.VARIANT_SET_NAME}'].prim "
                    f"'{declared_prim_path}' does not own a '{self.VARIANT_SET_NAME}' variant set."
                ),
                at=stage,
            )


# --------------------------------------------------------------------------- #
# PhysX (RV.001 / RV.002 / RV.003)
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_001)
class PhysXVariantSetChecker(_RuntimeVariantSetCheckerBase):
    """RV.001: default prim exposes the PhysX physics runtime variant set."""

    VARIANT_SET_NAME = "PhysX"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_001


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_002)
class PhysXRuntimePayloadChecker(_RuntimePayloadCheckerBase):
    """RV.002: PhysX Enabled variant composes an anchored runnables/physics/physx payload."""

    VARIANT_SET_NAME = "PhysX"
    PAYLOAD_STEM = "physx"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_002


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_003)
class PhysXVariantMetadataChecker(_RuntimeMetadataCheckerBase):
    """RV.003: SimReady_Metadata documents the PhysX variant set."""

    VARIANT_SET_NAME = "PhysX"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_003


# --------------------------------------------------------------------------- #
# Newton (RV.004 / RV.005 / RV.006)
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_004)
class NewtonVariantSetChecker(_RuntimeVariantSetCheckerBase):
    """RV.004: default prim exposes the Newton physics runtime variant set."""

    VARIANT_SET_NAME = "Newton"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_004


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_005)
class NewtonRuntimePayloadChecker(_RuntimePayloadCheckerBase):
    """RV.005: Newton Enabled variant composes an anchored runnables/physics/newton payload."""

    VARIANT_SET_NAME = "Newton"
    PAYLOAD_STEM = "newton"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_005


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_006)
class NewtonVariantMetadataChecker(_RuntimeMetadataCheckerBase):
    """RV.006: SimReady_Metadata documents the Newton variant set."""

    VARIANT_SET_NAME = "Newton"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_006


# --------------------------------------------------------------------------- #
# MuJoCo (RV.007 / RV.008 / RV.009)
# --------------------------------------------------------------------------- #
@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_007)
class MuJoCoVariantSetChecker(_RuntimeVariantSetCheckerBase):
    """RV.007: default prim exposes the MuJoCo physics runtime variant set."""

    VARIANT_SET_NAME = "MuJoCo"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_007


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_008)
class MuJoCoRuntimePayloadChecker(_RuntimePayloadCheckerBase):
    """RV.008: MuJoCo Enabled variant composes an anchored runnables/physics/mujoco payload."""

    VARIANT_SET_NAME = "MuJoCo"
    PAYLOAD_STEM = "mujoco"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_008


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_009)
class MuJoCoVariantMetadataChecker(_RuntimeMetadataCheckerBase):
    """RV.009: SimReady_Metadata documents the MuJoCo variant set."""

    VARIANT_SET_NAME = "MuJoCo"
    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_009


# --------------------------------------------------------------------------- #
# Cross-runtime composition rules (RV.010 / RV.011)
# --------------------------------------------------------------------------- #
PHYSICS_VARIANT_SETS = ("PhysX", "Newton", "MuJoCo")

# Map a physics variant-set name to its schema/attribute namespace bucket.
_BUCKET_BY_VARIANT_SET = {"PhysX": "physx", "Newton": "newton", "MuJoCo": "mujoco"}

# Human-readable runtime label per bucket, for messages.
_RUNTIME_LABEL = {
    "physx": "PhysX",
    "newton": "Newton",
    "mujoco": "MuJoCo",
    "neutral": "neutral base",
}

# Documented one-directional inheritance allowance: MjcCollisionAPI builds on
# NewtonCollisionAPI, so a MuJoCo composition may legitimately carry the
# inherited Newton collision base. Nothing else Newton is allowed under MuJoCo,
# and no MuJoCo data is ever allowed under Newton.
_NEWTON_UNDER_MUJOCO_SCHEMAS = {"NewtonCollisionAPI"}
_NEWTON_UNDER_MUJOCO_ATTRS = {"newton:contactGap", "newton:contactMargin"}

_APPROX_ATTR = "physics:approximation"


def _listop_items(list_op) -> list:
    """Return every item across all fields of an Sdf list op."""
    out: list = []
    if list_op is None:
        return out
    for items in (
        list_op.explicitItems,
        list_op.prependedItems,
        list_op.appendedItems,
        list_op.addedItems,
        list_op.orderedItems,
    ):
        out.extend(items)
    return out


def _schema_bucket(schema_name: str) -> str:
    """Classify an API schema name into a runtime namespace bucket."""
    if schema_name.startswith("Physx"):
        return "physx"
    if schema_name.startswith("Newton"):
        return "newton"
    if schema_name.startswith("Mjc"):
        return "mujoco"
    return "neutral"


def _attr_bucket(attr_name: str):
    """Classify a property name into a physics namespace bucket, or None."""
    if attr_name.startswith("physics:"):
        return "neutral"
    if attr_name.startswith("physx"):
        return "physx"
    if attr_name.startswith("newton:"):
        return "newton"
    if attr_name.startswith("mjc:"):
        return "mujoco"
    return None


def _applied_api_schema_names(prim: Usd.Prim) -> List[str]:
    """Applied API schema names, including schemas unknown to this USD build.

    Reads the composed ``apiSchemas`` list op so foreign-runtime schemas are
    detected even when their plugin is not registered locally.
    """
    names = list(prim.GetAppliedSchemas())
    api_schemas = prim.GetMetadata("apiSchemas")
    if api_schemas is not None:
        for item in _listop_items(api_schemas):
            base = str(item).split(":", 1)[0]
            if base not in names:
                names.append(base)
    return names


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_010)
class RuntimeVariantSectionPurityChecker(usd_validation_nvidia.BaseRuleChecker):
    """RV.010: physics variant sections carry only the payload arc.

    ``Enabled`` may compose the runtime only through its ``prepend payload``
    arc (no inline child prims, properties, or other arcs). ``Disabled`` must
    be empty. Inline variant opinions outrank payloads in USD strength
    ordering and would leak across runtime selections.
    """

    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_010

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        prim_spec = stage.GetRootLayer().GetPrimAtPath(default_prim.GetPath())
        if prim_spec is None:
            return

        for vs_name in PHYSICS_VARIANT_SETS:
            variant_set_spec = prim_spec.variantSets.get(vs_name)
            if variant_set_spec is None:
                continue

            for opt_name, variant_spec in variant_set_spec.variants.items():
                self._check_option(default_prim, vs_name, opt_name, variant_spec.primSpec)

    def _check_option(self, at, vs_name, opt_name, variant_prim_spec) -> None:
        if variant_prim_spec is None:
            return

        has_children = len(variant_prim_spec.nameChildren) > 0
        has_properties = len(variant_prim_spec.properties) > 0
        has_nested_variant_sets = len(variant_prim_spec.variantSets) > 0
        payloads = _listop_items(variant_prim_spec.payloadList)
        references = _listop_items(variant_prim_spec.referenceList)
        inherits = _listop_items(variant_prim_spec.inheritPathList)
        specializes = _listop_items(variant_prim_spec.specializesList)

        extras: List[str] = []
        if has_children:
            extras.append(f"{len(variant_prim_spec.nameChildren)} inline child prim(s)")
        if has_properties:
            extras.append(f"{len(variant_prim_spec.properties)} inline property(ies)")
        if has_nested_variant_sets:
            extras.append("nested variant set(s)")
        if references:
            extras.append("reference arc(s)")
        if inherits:
            extras.append("inherit arc(s)")
        if specializes:
            extras.append("specialize arc(s)")

        if opt_name == ENABLED_OPTION:
            if extras:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"'{vs_name}' variant '{ENABLED_OPTION}' must compose the runtime only "
                        f"through its payload arc, but it also authors: {', '.join(extras)}. "
                        f"Move runtime data into the runnables/physics payload."
                    ),
                    at=at,
                )
        elif opt_name == DEFAULT_OPTION:
            if payloads:
                extras.insert(0, "a payload arc")
            if extras:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"'{vs_name}' variant '{DEFAULT_OPTION}' must be empty, but it authors: "
                        f"{', '.join(extras)}."
                    ),
                    at=at,
                )


@usd_validation_nvidia.register_rule("RuntimeVariants")
@usd_validation_nvidia.register_requirements(cap.RuntimeVariantsRequirements.RV_011)
class RuntimePhysicsIsolationChecker(usd_validation_nvidia.BaseRuleChecker):
    """RV.011: a selected runtime composes only its own + neutral physics.

    For each declared physics variant (and the neutral base) the stage is
    recomposed with that runtime Enabled and every other physics runtime
    Disabled, then every prim under the default prim is inspected for
    foreign-runtime schemas/attributes and for conflicting
    ``physics:approximation`` values.
    """

    REQUIREMENT = cap.RuntimeVariantsRequirements.RV_011

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        declared = [vs for vs in PHYSICS_VARIANT_SETS if vs in set(default_prim.GetVariantSets().GetNames())]
        if not declared:
            # No physics runtime variants: nothing cross-runtime to isolate.
            return

        root_layer = stage.GetRootLayer()

        # Neutral base (all runtimes Disabled) is validated like "Standard".
        self._check_selection(root_layer, target_set=None, target_bucket="neutral")

        for vs_name in declared:
            self._check_selection(
                root_layer,
                target_set=vs_name,
                target_bucket=_BUCKET_BY_VARIANT_SET[vs_name],
            )

    def _compose(self, root_layer, target_set):
        composed = Usd.Stage.Open(root_layer)
        default_prim = composed.GetDefaultPrim()
        present = set(default_prim.GetVariantSets().GetNames())
        with Usd.EditContext(composed, composed.GetSessionLayer()):
            for vs_name in PHYSICS_VARIANT_SETS:
                if vs_name not in present:
                    continue
                selection = ENABLED_OPTION if vs_name == target_set else DEFAULT_OPTION
                default_prim.GetVariantSet(vs_name).SetVariantSelection(selection)
        return composed

    def _check_selection(self, root_layer, target_set, target_bucket) -> None:
        composed = self._compose(root_layer, target_set)
        default_prim = composed.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            return

        label = _RUNTIME_LABEL.get(target_bucket, target_bucket)
        allowed = {"neutral", target_bucket}

        for prim in Usd.PrimRange(default_prim):
            self._check_schemas(prim, target_bucket, allowed, label)
            self._check_attributes(prim, target_bucket, allowed, label)
            self._check_approximation(prim, target_bucket, label)

    def _check_schemas(self, prim, target_bucket, allowed, label) -> None:
        for schema_name in _applied_api_schema_names(prim):
            bucket = _schema_bucket(schema_name)
            if bucket in allowed:
                continue
            if target_bucket == "mujoco" and bucket == "newton" and schema_name in _NEWTON_UNDER_MUJOCO_SCHEMAS:
                continue
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"{label} selection composes foreign-runtime schema "
                    f"'{schema_name}' ({_RUNTIME_LABEL.get(bucket, bucket)}) on "
                    f"<{prim.GetPath()}>. A {label} composition must carry only neutral "
                    f"and {label} physics schemas."
                ),
                at=prim,
            )

    def _check_attributes(self, prim, target_bucket, allowed, label) -> None:
        for prop_name in prim.GetPropertyNames():
            bucket = _attr_bucket(prop_name)
            if bucket is None or bucket in allowed:
                continue
            if target_bucket == "mujoco" and bucket == "newton" and prop_name in _NEWTON_UNDER_MUJOCO_ATTRS:
                continue
            self._AddFailedCheck(
                requirement=self.REQUIREMENT,
                message=(
                    f"{label} selection composes foreign-runtime attribute "
                    f"'{prop_name}' ({_RUNTIME_LABEL.get(bucket, bucket)}) on "
                    f"<{prim.GetPath()}>."
                ),
                at=prim,
            )

    def _check_approximation(self, prim, target_bucket, label) -> None:
        attr = prim.GetAttribute(_APPROX_ATTR)
        if not attr or not attr.IsValid() or not attr.HasAuthoredValue():
            return
        value = attr.Get()
        if value is None:
            return
        value = str(value)

        if target_bucket == "newton":
            if value == "sdf":
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Newton selection composes {_APPROX_ATTR} = 'sdf' on "
                        f"<{prim.GetPath()}>. 'sdf' is a PhysX approximation and conflicts "
                        f"with Newton collision; remove it from the Newton composition."
                    ),
                    at=prim,
                )
            else:
                self._AddWarning(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Newton selection composes {_APPROX_ATTR} = '{value}' on "
                        f"<{prim.GetPath()}>. Newton does not consume this attribute; it is "
                        f"an inert leak that should be dropped from the Newton composition."
                    ),
                    at=prim,
                )
        elif target_bucket == "mujoco":
            has_mjc_collision = "MjcCollisionAPI" in _applied_api_schema_names(prim)
            if has_mjc_collision and value != "convexHull":
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"MuJoCo selection composes {_APPROX_ATTR} = '{value}' on a "
                        f"MjcCollisionAPI mesh <{prim.GetPath()}>; MuJoCo requires "
                        f"'convexHull' (see MUJOCO.COL.002)."
                    ),
                    at=prim,
                )
        elif target_bucket == "neutral":
            if value == "sdf":
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Neutral base composes {_APPROX_ATTR} = 'sdf' on <{prim.GetPath()}>. "
                        f"'sdf' is PhysX-specific and must not appear on the runtime-neutral base."
                    ),
                    at=prim,
                )
