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
"""Closed-vocabulary validators for open dataset taxonomies.

These checkers demonstrate that SimReady's semantic labeling is *not* tied to NVIDIA's Wikidata
Q-code taxonomy. Each one targets a public dataset taxonomy (COCO, Cityscapes, ADE20K, PASCAL VOC,
SUN RGB-D, ImageNet-1K) identified by its own ``SemanticsLabelsAPI`` instance name (the taxonomy
slug, e.g. ``SemanticsLabelsAPI:coco``) and verifies that every authored ``semantics:labels:<slug>``
value is a real member of that taxonomy's vocabulary.

This is layered on top of the vendor-neutral existence rule (SL.001 in the ``semantic_labels``
capability): SL.001 asks "is there *a* label?"; these rules ask "is the label a valid <taxonomy>
class?". A prim that does not carry the taxonomy's instance is left untouched here.

One checker per taxonomy -> one requirement -> one feature, mirroring the one-feature-per-checker
convention used elsewhere (e.g. the semantic_labels neutral/NV split), so a taxonomy's rule only runs
when its feature is enabled in the active profile.

To add your own taxonomy: drop a ``taxonomies/<slug>.json`` file next to this module, add a
``<SLUG>.001`` requirement, and subclass :class:`_TaxonomyMembershipChecker` with ``SLUG`` and
``REQUIREMENT`` set. See ``docs/guides/adding_a_custom_taxonomy.md``.

.. note::
   **This capability is a proof-of-concept**, not an authoritative implementation. It is meant to
   show the pattern -- non-NVIDIA taxonomies as toggleable features with closed-vocabulary
   validators -- and how a user would add their own. The SimReady team should harden the parts
   noted inline (e.g. scaffolding/non-content filtering) before treating these checks as canonical.
"""

__all__ = [
    "CocoLabelsChecker",
    "CityscapesLabelsChecker",
    "Ade20kLabelsChecker",
    "PascalVocLabelsChecker",
    "SunRgbdLabelsChecker",
    "ImageNet1kLabelsChecker",
]

import simready.foundation.tier_core.requirements as cap
from pxr import Sdf, Usd
from usd_validation_nvidia import BaseRuleChecker, register_requirements

from .taxonomy_data import load_taxonomy

# Editor scaffolding that should never be treated as asset content. NOTE (proof-of-concept): this is
# a hard-coded, Omniverse-specific deny-list carried over from the semantic_labels checkers. It is
# NOT the primary defense -- new/other-vendor cameras are already excluded generically by default-prim
# scoping (these prims are injected as stage-root siblings, outside the asset) and by the per-checker
# instance gate (scaffolding does not carry a taxonomy label). The robust, vendor-neutral signal for
# excluding non-content geometry is USD `purpose` (guide/proxy); a production implementation should
# lean on that rather than name/path matching. Left as-is here so this POC stays consistent with the
# existing semantic_labels checkers.
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


class _TaxonomyMembershipChecker(BaseRuleChecker):
    """Shared logic for the per-taxonomy closed-vocabulary checkers.

    Concrete subclasses set ``SLUG`` (the ``SemanticsLabelsAPI`` instance name / data-file slug) and
    ``REQUIREMENT`` (the requirement this checker reports against), and apply ``@register_requirements``.
    """

    # Overridden by subclasses.
    SLUG: str = ""
    REQUIREMENT = None

    @staticmethod
    def _is_from_default_prim(prim: Usd.Prim) -> bool:
        # Scoped to the default-prim subtree -- an asset's published content. A missing defaultPrim is
        # a stage-metadata concern enforced by the core profile, not flagged here.
        default_prim = prim.GetStage().GetDefaultPrim()
        if not default_prim:
            return False
        return prim.GetPath().HasPrefix(default_prim.GetPath())

    @staticmethod
    def _get_semantics_labels_api_instances(prim: Usd.Prim) -> list[str]:
        """Return the instance names of every applied ``SemanticsLabelsAPI:<instance>`` schema."""
        api_schemas: Sdf.TokenListOp = prim.GetMetadata("apiSchemas")
        if not api_schemas:
            return []
        instances: list[str] = []
        for applied_schema in api_schemas.GetAddedOrExplicitItems():
            parts = applied_schema.split(":")
            if len(parts) == 2 and parts[0] == "SemanticsLabelsAPI" and parts[1].strip():
                instances.append(parts[1])
        return instances

    def CheckPrim(self, prim: Usd.Prim):
        if not self._is_from_default_prim(prim):
            return
        if is_omni_path(prim.GetPath()):
            return

        # Only validate prims that opt into this taxonomy by applying its instance.
        if self.SLUG not in self._get_semantics_labels_api_instances(prim):
            return

        attr = prim.GetAttribute(f"semantics:labels:{self.SLUG}")
        # Structural problems (unauthored, wrong type, empty) are the vendor-neutral existence rule's
        # (SL.001) concern; this membership rule only judges authored token[] values.
        if not attr or not attr.HasAuthoredValue() or attr.GetTypeName() != Sdf.ValueTypeNames.TokenArray:
            return
        values = attr.Get()
        if not values:
            return
        # ``GetTypeName()`` above reports the schema's token[] even when the layer authored a
        # scalar ``string``, so a bare ``str`` still arrives here. Resolve it as the one label it
        # is; per-character lookups would report N nonsense "not a member" failures for one value.
        if isinstance(values, str):
            values = [values]

        taxonomy = load_taxonomy(self.SLUG)
        for value in values:
            if not isinstance(value, str):
                value = str(value)
            status, canonical = taxonomy.resolve(value)
            if status == "exact":
                continue
            if status == "alias":
                self._AddWarning(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Non-canonical {taxonomy.name} label: '{value}' is not the canonical spelling. "
                        f"Use '{canonical}'."
                    ),
                    at=attr,
                )
            else:
                self._AddFailedCheck(
                    requirement=self.REQUIREMENT,
                    message=(
                        f"Unknown {taxonomy.name} label: '{value}' is not a member of the " f"'{self.SLUG}' taxonomy."
                    ),
                    at=attr,
                )


@register_requirements(cap.DatasetTaxonomiesRequirements.COCO_001, override=True)
class CocoLabelsChecker(_TaxonomyMembershipChecker):
    """COCO.001: ``SemanticsLabelsAPI:coco`` values must be COCO (instances) classes."""

    SLUG = "coco"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.COCO_001


@register_requirements(cap.DatasetTaxonomiesRequirements.CITY_001, override=True)
class CityscapesLabelsChecker(_TaxonomyMembershipChecker):
    """CITY.001: ``SemanticsLabelsAPI:cityscapes`` values must be Cityscapes classes."""

    SLUG = "cityscapes"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.CITY_001


@register_requirements(cap.DatasetTaxonomiesRequirements.ADE_001, override=True)
class Ade20kLabelsChecker(_TaxonomyMembershipChecker):
    """ADE.001: ``SemanticsLabelsAPI:ade20k`` values must be ADE20K classes."""

    SLUG = "ade20k"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.ADE_001


@register_requirements(cap.DatasetTaxonomiesRequirements.VOC_001, override=True)
class PascalVocLabelsChecker(_TaxonomyMembershipChecker):
    """VOC.001: ``SemanticsLabelsAPI:pascal_voc`` values must be PASCAL VOC classes."""

    SLUG = "pascal_voc"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.VOC_001


@register_requirements(cap.DatasetTaxonomiesRequirements.SUN_001, override=True)
class SunRgbdLabelsChecker(_TaxonomyMembershipChecker):
    """SUN.001: ``SemanticsLabelsAPI:sunrgbd`` values must be SUN RGB-D classes."""

    SLUG = "sunrgbd"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.SUN_001


@register_requirements(cap.DatasetTaxonomiesRequirements.IN1K_001, override=True)
class ImageNet1kLabelsChecker(_TaxonomyMembershipChecker):
    """IN1K.001: ``SemanticsLabelsAPI:imagenet_1k`` values must be ImageNet-1K classes."""

    SLUG = "imagenet_1k"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.IN1K_001
