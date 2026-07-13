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

__all__ = ["SemanticLabelsCapabilityChecker"]


import re
from dataclasses import dataclass
from functools import partial

import omni.capabilities as cap
import pxr
from omni.asset_validator import (
    AtType,
    BaseRuleChecker,
    Issue,
    IssueSeverity,
    Suggestion,
    register_requirements,
)
from pxr import Sdf, Usd, UsdGeom, UsdShade


# Backward compatible

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


@dataclass
class QCodeLabel:
    code: str


@register_requirements(
    cap.SemanticLabelsRequirements.SL_001,
    cap.SemanticLabelsRequirements.SL_003,
    cap.SemanticLabelsRequirements.SL_NV_002,
    cap.SemanticLabelsRequirements.SL_QCODE_001,
)
class SemanticLabelsCapabilityChecker(BaseRuleChecker):
    """
    Validates the following semantic labels requirements:

    - **SL.001**: All geometry prims must be semantically labeled
    - **SL.003**: Semantic labels must use the SemanticsLabelsAPI schema
    - **SL.NV.002**: Semantic label attributes must not contain time samples
    - **SL.QCODE.001**: If the Wikidata ontology is used, Q-Codes must be valid, properly formatted, and retrievable from wikidata.org

    The sum of all semantic labels based on SemanticsLabelsAPI schema instances named "wikidata_qcode" that are
    directly authored on the prim, inherited from ancestor prims or from materials with purpose full bound to the prim,
    must be greater than zero.

    The "wikidata_qcode" attribute must not be time-varying.

    The "wikidata_qcode" attribute's value must start with a capital Q followed by one or more numbers [0-9].
    """

    QCODE_RE = re.compile(r"^Q[0-9]+$")

    SEMANTIC_INSTANCE_NAME = "wikidata_qcode"

    def __init__(self, verbose, consumerLevelChecks, assetLevelChecks):
        super().__init__(verbose, consumerLevelChecks, assetLevelChecks)
        # Set of issues found during parsing prim hierarchy for semantic schemas.
        # Helps to avoid reporting issues more than once.
        self._semantic_parsing_issues: set[Issue] = set()

    def CheckStage(self, stage: Usd.Stage):
        # Validate that the stage has a valid default prim
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck(
                message="Stage has no default prim.",
                at=stage,
            )
            return False

        self.ResetCaches()

    def CheckPrim(self, prim: Usd.Prim):
        if not self._is_from_default_prim(prim):
            return

        if is_omni_path(prim.GetPath()):
            return

        if not self._is_render_or_default_gprim(prim):
            return

        # Collect semantics from the GPrim
        gprim_semantics: list[QCodeLabel] = self._parse_semantics(prim)

        # Collect semantics from the GPrim's bound materials
        material_semantics: list[QCodeLabel] = self._collect_semantics_from_materials(prim)
        gprim_semantics.extend(material_semantics)

        # Collect the semantics from the GPrim's ancestors
        ancestor_semantics = []
        parent_prim = prim.GetParent()
        while parent_prim and not parent_prim.IsPseudoRoot():
            semantics: list[QCodeLabel] = self._parse_semantics(parent_prim)
            ancestor_semantics.extend(semantics)
            parent_prim = parent_prim.GetParent()

        gprim_semantics.extend(ancestor_semantics)

        # Check if there are semantic labels attributed to the GPrim
        if not gprim_semantics:
            self._AddFailedCheck(
                requirement=cap.SemanticLabelsRequirements.SL_001,
                message=f"Unlabeled prim: No {self.SEMANTIC_INSTANCE_NAME} semantics found on prim, its ancestors or its bound materials.",
                at=prim,
            )

    def _collect_semantics_from_materials(self, prim: Usd.Prim) -> list[QCodeLabel]:
        """Collects the semantic labels from the bound materials of a GPrim.
        Args:
            prim (Usd.Prim): The GPrim to collect semantic labels from its bound materials.
        Returns:
            list[QCodeLabel]: A list of qcode labels.
        """
        # Material binding can be specified through collectios, in which case the prim
        # will have a MaterialBindingAPI. Therefore, not checking for the MaterialBindingAPI
        # on the prim directly.
        # Look for materials with 'full' or 'allPurpose' purpose
        mtl, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose=UsdShade.Tokens.full)

        semantics: list[QCodeLabel] = self._parse_semantics(mtl.GetPrim()) if mtl else []

        return semantics

    def _is_semantics_labels_api_schema_applied(self, prim: Usd.Prim) -> bool:
        """Checks if the SemanticsLabelsAPI schema is applied to the prim.
        Args:
            prim (Usd.Prim): The prim to check.
        Returns:
            bool: True if the SemanticsLabelsAPI schema is applied, False otherwise.
        """
        if hasattr(pxr, "UsdSemantics"):
            from pxr import UsdSemantics

            if UsdSemantics.LabelsAPI(prim, self.SEMANTIC_INSTANCE_NAME):
                return True
            return False
        api_schemas: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        if not api_schemas:
            return False
        applied_schemas = api_schemas.GetAddedOrExplicitItems()
        if f"SemanticsLabelsAPI:{self.SEMANTIC_INSTANCE_NAME}" in applied_schemas:
            return True
        return False

    def _is_semantics_api_schema_applied(self, prim: Usd.Prim) -> list[str]:
        """Checks if the SemanticsAPI schema is applied to the prim.
        Args:
            prim (Usd.Prim): The prim to check.
        Returns:
            List[str]: A list of instance names of the SemanticsAPI schema applied to the prim.
        """
        api_schemas: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        if not api_schemas:
            return []
        applied_schemas = api_schemas.GetAddedOrExplicitItems()

        semantic_api_instance_names: list[str] = []
        for applied_schema in applied_schemas:
            parts = applied_schema.split(":")
            if len(parts) != 2:
                continue
            schema_name, instance_name = parts[0], parts[1]
            if schema_name != "SemanticsAPI" or not instance_name.strip():
                continue

            # The instance name of the SemanticsAPI schema can be anything
            # as long as its unique within the prim's applied schemas
            # Later we'll check if the semanticType is the same as the SEMANTIC_INSTANCE_NAME.
            semantic_api_instance_names.append(instance_name)

        return semantic_api_instance_names

    @staticmethod
    def _is_from_default_prim(prim: Usd.Prim):
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
        purpose = gprim.ComputePurpose()
        return purpose in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)

    def _parse_labels_from_semantics_labels_api_schema(self, prim: Usd.Prim) -> list[QCodeLabel]:
        """Parse the semantic labels from the SemanticsLabelsAPI schema.
        Args:
            prim (Usd.Prim): The prim to parse.
        Returns:
            list[QCodeLabel]: A list of qcode labels.
        """
        qcode_attr = prim.GetAttribute(f"semantics:labels:{self.SEMANTIC_INSTANCE_NAME}")
        if not qcode_attr or not qcode_attr.HasAuthoredValue():
            self._AddFailedSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_003,
                message=f"Missing schema attribute: 'semantics:label:{self.SEMANTIC_INSTANCE_NAME}' is not authored.",
                at=prim,
            )
            return []

        # Validate attribute metadata
        failed_checks = False
        if qcode_attr.GetTypeName() != Sdf.ValueTypeNames.TokenArray:
            self._AddFailedSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_QCODE_001,
                message=f"Incorrect attribute type: actual type {qcode_attr.GetTypeName()} different than expected type {Sdf.ValueTypeNames.TokenArray}.",
                at=qcode_attr,
            )
            failed_checks = True

        if qcode_attr.GetNumTimeSamples() > 0:
            self._AddFailedSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_NV_002,
                message="Incorrect attribute sampling: the attribute cannot have time samples.",
                at=qcode_attr,
            )
            failed_checks = True

        # Validate attribute values
        qcode_value_list = qcode_attr.Get()
        if qcode_value_list is None or not qcode_value_list:
            self._AddFailedSemanticParsingCheck(
                requirement=cap.SemanticLabelsRequirements.SL_QCODE_001,
                message="Missing attribute value.",
                at=qcode_attr,
            )
            failed_checks = True

        if failed_checks:
            return []

        valid_qcodes = []
        for qcode_value in qcode_value_list:
            if not isinstance(qcode_value, str) or self.QCODE_RE.match(qcode_value) is None:
                self._AddFailedSemanticParsingCheck(
                    requirement=cap.SemanticLabelsRequirements.SL_QCODE_001,
                    message="Incorrect semantic label format: the label must be a string starting with letter 'Q' followed "
                    f"by one or more numbers. Found: {qcode_value!s}",
                    at=qcode_attr,
                )
            else:
                valid_qcodes.append(QCodeLabel(qcode_value))

        return valid_qcodes

    def _parse_labels_from_semantics_api_schema(
        self, prim: Usd.Prim, semantic_api_instance_names: list[str]
    ) -> list[QCodeLabel]:
        """Parse the semantic labels from the SemanticsAPI schema.
        Args:
            prim (Usd.Prim): The prim to parse.
            semantic_api_instance_names (list[str]): A list of instance names of the SemanticsAPI schema applied to the prim.
        Returns:
            List[QCodeLabel]: A list of qcode labels.
        """
        semantic_labels: list[QCodeLabel] = []
        for instance_name in semantic_api_instance_names:
            # Look for the semanticType that are the same as the SEMANTIC_INSTANCE_NAME
            semantic_type = prim.GetAttribute(f"semantic:{instance_name}:params:semanticType")
            if not semantic_type or semantic_type.Get() != self.SEMANTIC_INSTANCE_NAME:
                continue
            # SemanticsAPI instance is of type SEMANTIC_INSTANCE_NAME, check paramData value
            semantic_data = prim.GetAttribute(f"semantic:{instance_name}:params:semanticData")
            if (
                not semantic_data
                or semantic_data.GetNumTimeSamples() > 0
                or semantic_data.GetTypeName() != Sdf.ValueTypeNames.String
            ):
                continue
            qcode_value = semantic_data.Get()
            if not isinstance(qcode_value, str) or self.QCODE_RE.match(qcode_value) is None:
                continue
            semantic_labels.append(QCodeLabel(qcode_value))

        return semantic_labels

    def _parse_semantics(self, prim: Usd.Prim) -> list[QCodeLabel]:
        """Return all the semantics data associated with a prim.
        Args:
            prim (Usd.Prim): The prim to parse.
        Returns:
            List[QCodeLabel]: A list of qcode labels.
        """
        semantic_labels: list[QCodeLabel] = []
        if prim and self._is_semantics_labels_api_schema_applied(prim):
            semantic_labels.extend(self._parse_labels_from_semantics_labels_api_schema(prim))

        # Check for labels from SemanticsAPI (legacy) schema and offer migration to SemanticsLabelsAPI schema
        if (semantic_api_instance_names := self._is_semantics_api_schema_applied(prim)) is not None:
            new_semantic_labels = self._parse_labels_from_semantics_api_schema(prim, semantic_api_instance_names)
            if new_semantic_labels:
                self._AddWarningSemanticParsingCheck(
                    requirement=cap.SemanticLabelsRequirements.SL_003,
                    message="Deprecated SemanticsAPI schema based wikidata_qcode semantics found.",
                    at=prim,
                    suggestion=Suggestion(
                        message="Migrate the SemanticsAPI schema based wikidata_qcode semantics to SemanticsLabelsAPI schema based semantics.",
                        callable=partial(
                            self._migrate_to_semantics_labels_api,
                            semantic_labels=new_semantic_labels,
                            semantic_api_instance_names=semantic_api_instance_names,
                        ),
                        at=[prim],
                    ),
                )

        return semantic_labels

    def _migrate_to_semantics_labels_api(
        self,
        _: Usd.Stage,
        prim: Usd.Prim,
        semantic_labels: list[QCodeLabel],
        semantic_api_instance_names: list[str],
    ) -> None:
        """
        Migrate the SemanticsAPI schema based semantics to SemanticsLabelsAPI schema based semantics.
        Args:
            _: Usd.Stage: The stage.
            prim: Usd.Prim: The prim.
            semantic_labels: list[QCodeLabel]: The semantic labels to be added to the prim.
            semantic_api_instance_names: list[str]: The semantic API instance names to be removed from the prim.
        """
        # If the SemanticsLabelsAPI schema is not applied, apply it
        self._add_semantics_labels_api_schema_and_labels(prim, [label.code for label in semantic_labels])
        self._remove_semantics_api_schemas(prim, semantic_api_instance_names)

    def _add_semantics_labels_api_schema_and_labels(self, prim: Usd.Prim, labels: list[str]) -> None:
        """Adds the SemanticsLabelsAPI schema to the prim and adds the semantic labels."""
        # Get the existing api schemas
        api_metadata: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        existing_apis = []
        if api_metadata:
            existing_apis = api_metadata.GetAddedOrExplicitItems()

        # Add the SemanticsLabelsAPI schema to the prim if it is not already applied
        api_schema = f"SemanticsLabelsAPI:{self.SEMANTIC_INSTANCE_NAME}"
        if api_schema not in existing_apis:
            listop = Sdf.TokenListOp()
            if api_metadata and api_metadata.isExplicit:
                listop.explicitItems = [*existing_apis, api_schema]
            else:
                listop.addedItems = [*existing_apis, api_schema]
            prim.SetMetadata("apiSchemas", listop)

        # Add the semantic labels to the prim
        attr = prim.CreateAttribute(f"semantics:labels:{self.SEMANTIC_INSTANCE_NAME}", Sdf.ValueTypeNames.TokenArray)
        current_labels = attr.Get()
        if current_labels:
            labels.extend(current_labels)
            labels = list(set(labels))  # make labels unique
        attr.Set(labels)

    def _remove_semantics_api_schemas(self, prim: Usd.Prim, semantic_api_instance_names: list[str]) -> None:
        """Removes the SemanticsAPI schema and its attributes from the prim.
        Args:
            prim: Usd.Prim: The prim.
            semantic_api_instance_names: list[str]: The semantic API instance names to be removed from the prim.
        """
        # Remove the SemanticsAPI schemas from the prim
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

        # Remove the attributes from the prim
        for instance_name in semantic_api_instance_names:
            prim.RemoveProperty(f"semantic:{instance_name}:params:semanticType")
            prim.RemoveProperty(f"semantic:{instance_name}:params:semanticData")

    def _AddFailedSemanticParsingCheck(
        self,
        message: str,
        at: AtType | None = None,
        suggestion: Suggestion | None = None,
        requirement: cap.SemanticLabelsRequirements | None = None,
    ) -> None:
        """Helper method to record a failed semantic parsing check."""
        issue = Issue(message=message, severity=IssueSeverity.FAILURE, rule=self.__class__, at=at)
        if issue not in self._semantic_parsing_issues:
            self._AddFailedCheck(requirement=requirement, message=message, at=at, suggestion=suggestion)
            self._semantic_parsing_issues.add(issue)

    def _AddWarningSemanticParsingCheck(
        self,
        message: str,
        at: AtType | None = None,
        suggestion: Suggestion | None = None,
        requirement: cap.SemanticLabelsRequirements | None = None,
    ) -> None:
        """Helper method to record a failed semantic parsing check."""
        issue = Issue(message=message, severity=IssueSeverity.WARNING, rule=self.__class__, at=at)
        if issue not in self._semantic_parsing_issues:
            self._AddWarning(requirement=requirement, message=message, at=at, suggestion=suggestion)
            self._semantic_parsing_issues.add(issue)

    def ResetCaches(self):
        self._semantic_parsing_issues.clear()
