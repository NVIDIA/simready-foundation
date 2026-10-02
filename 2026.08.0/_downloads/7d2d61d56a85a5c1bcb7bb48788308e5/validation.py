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
__all__ = [
    "SemanticLabelsCapabilityChecker",
    "SemanticLabelsMaterialChecker",
    "SemanticLabelsWikidataChecker",
]


import re
from functools import partial

import pxr
import simready.foundation.tier_core.requirements as cap
from pxr import Sdf, Usd, UsdGeom, UsdShade
from usd_validation_nvidia import (
    AtType,
    BaseRuleChecker,
    Suggestion,
    register_requirements,
)

_OMNI_PRIM_PATHS = {
    Sdf.Path("/OmniverseKit_Persp"),
    Sdf.Path("/OmniverseKit_Front"),
    Sdf.Path("/OmniverseKit_Top"),
    Sdf.Path("/OmniverseKit_Right"),
    Sdf.Path("/OmniKit_Viewport_LightRig"),
}
_OMNI_PRIM_NAMES = {"OmniverseKitViewportCameraMesh"}


def is_omni_path(path: Sdf.Path) -> bool:
    return path in _OMNI_PRIM_PATHS or path.name in _OMNI_PRIM_NAMES


class _SemanticLabelsMixin:
    """Shared, side-effect-free helpers for the semantic-label checkers.

    The requirements live in separate checker classes so that each checker's requirement set maps to
    a single feature (FET_011_STANDARD -> SL.001/SL.002/SL.003, FET_011_RTX -> SL.MAT.001/SL.TIME.001,
    FET_046_STANDARD -> SL.QCODE.001). This matches the one-feature-per-checker
    convention used across the repo (e.g. the gripper capability separates GR.001-004 from
    GR.ISA.001) and ensures taxonomy-specific rules cannot fire unless their feature is active.

    This is a plain mixin (not a ``BaseRuleChecker`` subclass) so it is never discovered/run as a
    checker on its own; the concrete classes inherit ``(_SemanticLabelsMixin, BaseRuleChecker)``.
    """

    QCODE_RE = re.compile(r"^Q[0-9]+$")

    # Instance name of the NVIDIA Wikidata Q-Code taxonomy. Q-code format (SL.QCODE.001) applies only
    # to this instance; existence (SL.001) is taxonomy-agnostic.
    SEMANTIC_INSTANCE_NAME = "wikidata_qcode"

    # SemanticsLabelsAPI instance used to label Material prims by material type (SL.MAT.001).
    MATERIAL_INSTANCE_NAME = "material"

    def __init__(self, verbose, consumerLevelChecks, assetLevelChecks):
        super().__init__(verbose, consumerLevelChecks, assetLevelChecks)
        # Keys of issues recorded while checking, used to avoid reporting the same finding twice.
        # Each key includes the requirement so two requirements with the same message/location are
        # not collapsed into one.
        self._semantic_parsing_issues: set[tuple] = set()

    def CheckStage(self, stage: Usd.Stage):
        # Clear per-stage dedup state up front so issues never leak across stages.
        self.ResetCaches()

    def ResetCaches(self):
        self._semantic_parsing_issues.clear()

    @staticmethod
    def _is_from_default_prim(prim: Usd.Prim) -> bool:
        # Semantic checks are scoped to the default-prim subtree: an asset's published content is
        # the defaultPrim and its descendants. A missing defaultPrim is not flagged here -- it is a
        # stage-metadata requirement enforced by the core profile (FET001).
        stage: Usd.Stage = prim.GetStage()
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return False
        return prim.GetPath().HasPrefix(default_prim.GetPath())

    @staticmethod
    def _is_render_or_default_gprim(prim: Usd.Prim) -> bool:
        """Returns True if the prim is a GPrim with default or renderable purpose."""
        if not (gprim := UsdGeom.Gprim(prim)):
            return False
        return gprim.ComputePurpose() in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)

    @staticmethod
    def _get_semantics_labels_api_instances(prim: Usd.Prim) -> list[str]:
        """Return the instance names of every applied ``SemanticsLabelsAPI:<instance>`` schema.

        Parsing the applied ``apiSchemas`` metadata keeps existence taxonomy-agnostic (any instance
        name counts) and avoids relying on schema-object truthiness -- which reflects prim validity,
        not whether the API is applied -- to detect application.
        """
        api_schemas: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        if not api_schemas:
            return []
        instances: list[str] = []
        for applied_schema in api_schemas.GetAddedOrExplicitItems():
            parts = applied_schema.split(":")
            if len(parts) == 2 and parts[0] == "SemanticsLabelsAPI" and parts[1].strip():
                instances.append(parts[1])
        return instances

    def _instance_present_value(self, prim: Usd.Prim, instance_name: str) -> tuple[bool, list[str]]:
        """Pure presence check for one ``SemanticsLabelsAPI:<instance>`` label (no issues emitted).

        Returns ``(present, values)`` where ``present`` is True when the label is structurally
        usable: authored, ``token[]``-typed, and either non-empty or time-sampled. Value-correctness
        (time samples, Q-code format) is judged separately by the NVIDIA checker.
        """
        attr = prim.GetAttribute(f"semantics:labels:{instance_name}")
        if not attr or not attr.HasAuthoredValue():
            return False, []
        if attr.GetTypeName() != Sdf.ValueTypeNames.TokenArray:
            return False, []
        values = attr.Get()
        # ``GetTypeName()`` reports the *schema's* declared type once the API is applied, so the
        # check above cannot see a layer that authored this as a scalar ``string`` -- which Sdf
        # permits and non-USD-aware exporters produce. A bare ``str`` is not a label array; treat
        # it as unusable rather than letting callers iterate its characters.
        if isinstance(values, str):
            return False, []
        if not values and attr.GetNumTimeSamples() == 0:
            return False, []
        return True, list(values) if values else []

    def _label_source_prims(self, prim: Usd.Prim) -> list[Usd.Prim]:
        """Ordered prims a label can be resolved from for SL.001: the prim and its ancestors, its
        computed bound full material and that material's ancestors, then its GeomSubset children."""
        sources: list[Usd.Prim] = []

        current = prim
        while current and not current.IsPseudoRoot():
            sources.append(current)
            current = current.GetParent()

        mtl, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)
        if mtl:
            current = mtl.GetPrim()
            while current and not current.IsPseudoRoot():
                sources.append(current)
                current = current.GetParent()

        for child in prim.GetChildren():
            if child.IsA(UsdGeom.Subset):
                sources.append(child)

        return sources

    def _AddFailedSemanticParsingCheck(
        self,
        message: str,
        at: AtType | None = None,
        suggestion: Suggestion | None = None,
        requirement=None,
    ) -> None:
        """Record a failed check once, deduped by (requirement, message, location)."""
        key = (requirement, message, self._at_key(at))
        if key not in self._semantic_parsing_issues:
            self._AddFailedCheck(requirement=requirement, message=message, at=at, suggestion=suggestion)
            self._semantic_parsing_issues.add(key)

    def _AddWarningSemanticParsingCheck(
        self,
        message: str,
        at: AtType | None = None,
        suggestion: Suggestion | None = None,
        requirement=None,
    ) -> None:
        """Record a warning once, deduped by (requirement, message, location)."""
        key = (requirement, message, self._at_key(at))
        if key not in self._semantic_parsing_issues:
            self._AddWarning(requirement=requirement, message=message, at=at, suggestion=suggestion)
            self._semantic_parsing_issues.add(key)

    @staticmethod
    def _at_key(at: AtType | None):
        """A hashable, requirement-independent key for the location an issue is attached to."""
        if at is None:
            return None
        get_path = getattr(at, "GetPath", None)
        if get_path is not None:
            return str(get_path())
        return repr(at)


@register_requirements(
    cap.SemanticLabelsRequirements.SL_001,
    cap.SemanticLabelsRequirements.SL_002,
    cap.SemanticLabelsRequirements.SL_003,
    override=True,
)
class SemanticLabelsCapabilityChecker(_SemanticLabelsMixin, BaseRuleChecker):
    """Validates the vendor-neutral semantic-label requirements (feature FET_011_STANDARD):

    - **SL.001**: every renderable gprim must be semantically labeled. Taxonomy-agnostic: the gprim
      is labeled when any applied ``SemanticsLabelsAPI:<instance>`` carries a structurally-present
      value (authored, ``token[]``-typed, non-empty) on the gprim, its ancestors, its computed
      bound full material, that material's ancestors, or its GeomSubsets.
    - **SL.002**: a deprecated ``SemanticsAPI`` label must be migrated to ``SemanticsLabelsAPI``.
    - **SL.003**: labels must use the modern ``SemanticsLabelsAPI`` schema.

    Material labeling (SL.MAT.001) and static labels (SL.TIME.001) live in
    :class:`SemanticLabelsMaterialChecker` (FET_011_RTX); Wikidata Q-code format (SL.QCODE.001 /
    FET_046_STANDARD) is handled by :class:`SemanticLabelsWikidataChecker`.
    """

    def CheckPrim(self, prim: Usd.Prim):
        if not self._is_from_default_prim(prim):
            return
        if is_omni_path(prim.GetPath()):
            return

        # SL.002 applies to any prim carrying a deprecated SemanticsAPI schema (the framework visits
        # every prim, so a per-prim check covers gprims, ancestors, materials, and subsets).
        self._check_deprecated_schema(prim)

        # SL.001 applies to renderable gprims only.
        if not self._is_render_or_default_gprim(prim):
            return

        labeled = False
        unusable: list[tuple[Usd.Prim, str]] = []
        for source in self._label_source_prims(prim):
            for instance in self._get_semantics_labels_api_instances(source):
                present, _ = self._instance_present_value(source, instance)
                if present:
                    labeled = True
                else:
                    unusable.append((source, instance))

        # SL.003: an applied SemanticsLabelsAPI carrying no usable value is a defect in its own
        # right, whether or not some other source resolves a label for this gprim. Reporting it
        # only when nothing resolves would let the common case through -- a labeled asset root
        # over a child whose own schema was applied and left empty -- which is the coverage the
        # deduped report below restores. ``at`` is the offending source, so a shared ancestor is
        # named once rather than once per descendant gprim.
        applied_but_unusable = bool(unusable)
        for source, instance in unusable:
            self._AddFailedSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_003,
                message=(
                    f"Unusable semantic label: 'SemanticsLabelsAPI:{instance}' is applied but "
                    f"'semantics:labels:{instance}' is missing, empty, or not a token[] array."
                ),
                at=source,
            )

        if labeled:
            return

        if applied_but_unusable:
            message = (
                "Unusable semantic label: a SemanticsLabelsAPI label attribute is applied but its "
                "value is missing, empty, or not a token[] array."
            )
        else:
            message = (
                "Unlabeled prim: no SemanticsLabelsAPI semantics found on the prim, its ancestors, "
                "its bound material, or its GeomSubsets."
            )
        self._AddFailedCheck(
            requirement=cap.SemanticLabelsRequirements.SL_001,
            message=message,
            at=prim,
        )

    def _check_deprecated_schema(self, prim: Usd.Prim) -> None:
        """SL.002: a deprecated SemanticsAPI label must have an equivalent SemanticsLabelsAPI label.

        (A) detect applied ``SemanticsAPI:<instance>`` schemas, (B) read their (taxonomy, value)
        labels, and (C) compare against this prim's modern ``SemanticsLabelsAPI`` values for the
        same taxonomy:

        - every deprecated value has a modern equivalent -> warning (pass): the deprecated schema is
          redundant and should be removed;
        - some deprecated value has no modern equivalent -> failure: migrate it.

        A prim with no deprecated schema is unaffected (silent pass).
        """
        instance_names = self._is_semantics_api_schema_applied(prim)
        if not instance_names:
            return

        deprecated_labels = self._parse_deprecated_labels(prim, instance_names)
        if not deprecated_labels:
            return

        modern_values_by_taxonomy: dict[str, list[str]] = {}
        for instance in self._get_semantics_labels_api_instances(prim):
            _, values = self._instance_present_value(prim, instance)
            if values:
                modern_values_by_taxonomy.setdefault(instance, []).extend(values)

        missing: list[str] = []
        for taxonomy, values in deprecated_labels.items():
            modern_values = set(modern_values_by_taxonomy.get(taxonomy, []))
            missing.extend(f"{taxonomy}={value}" for value in values if value not in modern_values)

        suggestion = Suggestion(
            message="Migrate the SemanticsAPI schema based semantics to SemanticsLabelsAPI schema based semantics.",
            callable=partial(
                self._migrate_to_semantics_labels_api,
                deprecated_labels=deprecated_labels,
                semantic_api_instance_names=instance_names,
            ),
            at=[prim],
        )

        if missing:
            self._AddFailedSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_002,
                message="Deprecated SemanticsAPI label not migrated: no equivalent SemanticsLabelsAPI label "
                f"found for {missing}. Migrate to the SemanticsLabelsAPI schema.",
                at=prim,
                suggestion=suggestion,
            )
        else:
            self._AddWarningSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_002,
                message="Deprecated SemanticsAPI schema found alongside an equivalent SemanticsLabelsAPI label; "
                "remove the redundant deprecated schema.",
                at=prim,
                suggestion=suggestion,
            )

    @staticmethod
    def _is_semantics_api_schema_applied(prim: Usd.Prim) -> list[str]:
        """Return the instance names of every applied deprecated ``SemanticsAPI:<instance>`` schema."""
        api_schemas: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        if not api_schemas:
            return []

        semantic_api_instance_names: list[str] = []
        for applied_schema in api_schemas.GetAddedOrExplicitItems():
            parts = applied_schema.split(":")
            if len(parts) != 2:
                continue
            schema_name, instance_name = parts[0], parts[1]
            if schema_name != "SemanticsAPI" or not instance_name.strip():
                continue
            semantic_api_instance_names.append(instance_name)
        return semantic_api_instance_names

    def _parse_deprecated_labels(self, prim: Usd.Prim, semantic_api_instance_names: list[str]) -> dict[str, list[str]]:
        """Parse deprecated SemanticsAPI labels, grouped by taxonomy (semanticType -> values).

        Taxonomy-agnostic: the SemanticsAPI ``semanticType`` maps to the target
        ``SemanticsLabelsAPI`` instance name and ``semanticData`` to the label value. Time-sampled
        or non-string ``semanticData`` is skipped. No Q-code format filtering is applied here --
        format is a modern-label (SL.QCODE.001) concern, not a migration concern.
        """
        labels: dict[str, list[str]] = {}
        for instance_name in semantic_api_instance_names:
            semantic_type = prim.GetAttribute(f"semantic:{instance_name}:params:semanticType")
            semantic_data = prim.GetAttribute(f"semantic:{instance_name}:params:semanticData")
            if not semantic_type or not semantic_data:
                continue
            if semantic_data.GetNumTimeSamples() > 0 or semantic_data.GetTypeName() != Sdf.ValueTypeNames.String:
                continue
            taxonomy = semantic_type.Get()
            value = semantic_data.Get()
            if not isinstance(taxonomy, str) or not taxonomy.strip():
                continue
            if not isinstance(value, str) or not value:
                continue
            labels.setdefault(taxonomy, []).append(value)
        return labels

    def _migrate_to_semantics_labels_api(
        self,
        _: Usd.Stage,
        prim: Usd.Prim,
        deprecated_labels: dict[str, list[str]],
        semantic_api_instance_names: list[str],
    ) -> None:
        """Migrate deprecated SemanticsAPI labels to SemanticsLabelsAPI schema based semantics."""
        for taxonomy, values in deprecated_labels.items():
            self._add_semantics_labels_api_schema_and_labels(prim, taxonomy, values)
        self._remove_semantics_api_schemas(prim, semantic_api_instance_names)

    def _add_semantics_labels_api_schema_and_labels(
        self, prim: Usd.Prim, instance_name: str, labels: list[str]
    ) -> None:
        """Adds the SemanticsLabelsAPI:<instance_name> schema to the prim and adds the semantic labels."""
        api_metadata: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        existing_apis = []
        if api_metadata:
            existing_apis = api_metadata.GetAddedOrExplicitItems()

        api_schema = f"SemanticsLabelsAPI:{instance_name}"
        if api_schema not in existing_apis:
            listop = Sdf.TokenListOp()
            if api_metadata and api_metadata.isExplicit:
                listop.explicitItems = [*existing_apis, api_schema]
            else:
                listop.addedItems = [*existing_apis, api_schema]
            prim.SetMetadata("apiSchemas", listop)

        # Add the semantic labels (merging with any existing values), always deduplicating while
        # preserving first-seen order so the migration is deterministic.
        attr = prim.CreateAttribute(f"semantics:labels:{instance_name}", Sdf.ValueTypeNames.TokenArray)
        labels = list(labels)
        current_labels = attr.Get()
        # ``CreateAttribute`` does not retype an existing scalar-string spec, so this can still
        # come back a bare ``str``. Splicing its characters in would write ["car", "c", "a", "r"]
        # into the user's asset -- this is the migration fix-up, so it edits the file.
        if isinstance(current_labels, str):
            current_labels = [current_labels]
        if current_labels:
            labels.extend(current_labels)
        labels = list(dict.fromkeys(labels))
        attr.Set(labels)

    def _remove_semantics_api_schemas(self, prim: Usd.Prim, semantic_api_instance_names: list[str]) -> None:
        """Removes the SemanticsAPI schema and its attributes from the prim."""
        api_metadata: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        if api_metadata and semantic_api_instance_names:
            apis_to_remove = [f"SemanticsAPI:{instance_name}" for instance_name in semantic_api_instance_names]
            existing_apis = api_metadata.GetAddedOrExplicitItems()
            new_apis = list(set(existing_apis) - set(apis_to_remove))
            listop = Sdf.TokenListOp()
            if api_metadata.isExplicit:
                listop.explicitItems = new_apis
            else:
                listop.addedItems = new_apis
            prim.SetMetadata("apiSchemas", listop)

        for instance_name in semantic_api_instance_names:
            prim.RemoveProperty(f"semantic:{instance_name}:params:semanticType")
            prim.RemoveProperty(f"semantic:{instance_name}:params:semanticData")


@register_requirements(
    cap.SemanticLabelsRequirements.SL_MAT_001,
    cap.SemanticLabelsRequirements.SL_TIME_001,
    override=True,
)
class SemanticLabelsMaterialChecker(_SemanticLabelsMixin, BaseRuleChecker):
    """Validates the NVIDIA-specific semantic-label requirements for FET_011_RTX:

    - **SL.MAT.001**: Material prims must carry a non-empty ``SemanticsLabelsAPI:material`` label.
    - **SL.TIME.001**: semantic label attributes must not contain time samples (any instance).

    Registered separately from the STANDARD checker so material labeling and the static-label rule
    are inactive when only FET_011_STANDARD is being validated.
    """

    def CheckPrim(self, prim: Usd.Prim):
        if not self._is_from_default_prim(prim):
            return
        if is_omni_path(prim.GetPath()):
            return

        # SL.TIME.001 on every label instance authored on this prim, regardless of prim type.
        for instance in self._get_semantics_labels_api_instances(prim):
            self._check_static_label_rule(prim, instance)

        # SL.MAT.001: every Material prim must carry a non-empty SemanticsLabelsAPI:material label.
        if prim.IsA(UsdShade.Material):
            self._check_material_label(prim)

    def _check_static_label_rule(self, prim: Usd.Prim, instance_name: str) -> None:
        """SL.TIME.001: semantic label attributes must not have time samples."""
        attr = prim.GetAttribute(f"semantics:labels:{instance_name}")
        if not attr or not attr.HasAuthoredValue() or attr.GetTypeName() != Sdf.ValueTypeNames.TokenArray:
            return
        if attr.GetNumTimeSamples() == 0:
            return

        self._AddFailedSemanticParsingCheck(
            requirement=cap.SemanticLabelsRequirements.SL_TIME_001,
            message="Incorrect attribute sampling: the attribute cannot have time samples.",
            at=attr,
        )

    def _check_material_label(self, prim: Usd.Prim) -> None:
        """SL.MAT.001: a Material prim must have ``SemanticsLabelsAPI:material`` applied with a value.

        The spec requires the schema *applied* with at least one authored value, so the ``material``
        instance must appear in the applied ``apiSchemas`` before the attribute is accepted -- an
        authored ``semantics:labels:material`` attribute without the schema applied does not satisfy
        the requirement. (Time samples on the attribute are flagged separately by SL.TIME.001.)
        """
        present = False
        if self.MATERIAL_INSTANCE_NAME in self._get_semantics_labels_api_instances(prim):
            present, _ = self._instance_present_value(prim, self.MATERIAL_INSTANCE_NAME)
        if not present:
            self._AddFailedCheck(
                requirement=cap.SemanticLabelsRequirements.SL_MAT_001,
                message=f"Unlabeled material: a Material prim must have 'SemanticsLabelsAPI:"
                f"{self.MATERIAL_INSTANCE_NAME}' applied with a non-empty "
                f"'semantics:labels:{self.MATERIAL_INSTANCE_NAME}' value.",
                at=prim,
            )


@register_requirements(cap.SemanticLabelsRequirements.SL_QCODE_001, override=True)
class SemanticLabelsWikidataChecker(_SemanticLabelsMixin, BaseRuleChecker):
    """Validates the Wikidata Q-code requirement for FET_046_STANDARD.

    SL.QCODE.001 applies only to the ``SemanticsLabelsAPI:wikidata_qcode`` instance.
    """

    def CheckPrim(self, prim: Usd.Prim):
        if not self._is_from_default_prim(prim) or is_omni_path(prim.GetPath()):
            return
        if self.SEMANTIC_INSTANCE_NAME not in self._get_semantics_labels_api_instances(prim):
            return

        attr = prim.GetAttribute(f"semantics:labels:{self.SEMANTIC_INSTANCE_NAME}")
        if not attr or not attr.HasAuthoredValue() or attr.GetTypeName() != Sdf.ValueTypeNames.TokenArray:
            return
        values = attr.Get()
        if not values:
            return
        # A layer may author this as a scalar ``string`` despite the schema declaring token[]
        # (see ``_instance_present_value``). Judge it as the one label it is; reporting each
        # character separately would bury the real finding. The mistyping itself is SL.003's.
        if isinstance(values, str):
            values = [values]
        for value in values:
            if not isinstance(value, str) or self.QCODE_RE.match(value) is None:
                self._AddFailedSemanticParsingCheck(
                    requirement=cap.SemanticLabelsRequirements.SL_QCODE_001,
                    message="Incorrect semantic label format: the label must be a string starting with "
                    f"letter 'Q' followed by one or more numbers. Found: {value!s}",
                    at=attr,
                )
