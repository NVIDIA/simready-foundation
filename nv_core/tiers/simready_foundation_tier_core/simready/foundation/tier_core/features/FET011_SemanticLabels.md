# Feature: `FET011_SemanticLabels`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET011_SemanticLabels` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-2-0` |

## Description

This feature defines the Standard OpenUSD semantic-label contract for assets
that need ground-truth object identity for perception, synthetic data
generation, or sensor validation workflows. An asset that satisfies this
feature has semantic labels authored with the modern `SemanticsLabelsAPI`
schema. The contract is taxonomy-agnostic: any `SemanticsLabelsAPI` instance
name may be used.

Static validation verifies that render/default geometry is semantically
labeled, that labels use the modern `SemanticsLabelsAPI` schema, and that any
deprecated `SemanticsAPI` labels have been migrated. Labels may be authored
directly on a renderable geometric prim, inherited from an ancestor, or provided
through a bound material.

OpenUSD permits time-varying labels, so this neutral feature allows them.
NVIDIA-specific rules are separate features: static labels and material labels
belong to [`FET011_SemanticLabels.RTX`](FET011_SemanticLabels.RTX.md), and Wikidata Q-code formatting to
[`CAP046_WikidataLabels`](../capabilities/CAP046_WikidataLabels.md).

## Dependency Graph

This feature has no dependencies. Taxonomy features such as
`CAP040_CocoLabels`–`CAP045_ImageNet1kLabels` and `CAP046_WikidataLabels` may depend on it.

## Use Cases

Products or workflows that consume this feature:

- NDAS SDG / Stargate
- MEGA
- Lightwheel SOW1
- Isaac Sim semantic-label runtime checks
- Synthetic data generation and ML ground-truth workflows

## Requirements

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Open-Taxonomy-ADE20K](../profiles/open-taxonomy-ade20k.md): required in `0.1.0`
- [Open-Taxonomy-COCO](../profiles/open-taxonomy-coco.md): required in `0.1.0`
- [Open-Taxonomy-Cityscapes](../profiles/open-taxonomy-cityscapes.md): required in `0.1.0`
- [Open-Taxonomy-ImageNet1K](../profiles/open-taxonomy-imagenet_1k.md): required in `0.1.0`
- [Open-Taxonomy-PascalVOC](../profiles/open-taxonomy-pascal_voc.md): required in `0.1.0`
- [Open-Taxonomy-SUNRGBD](../profiles/open-taxonomy-sunrgbd.md): required in `0.1.0`
- [Robotics-Prop](../profiles/robotics-prop.md): required in `3.2.0`, `3.3.0`, `4.0.0`

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Semantic Labels](../rules_and_reqs/semantic_labels/capability-semantic_labels.md)
    * Requirements:
        * [Semantic Label Capability](../rules_and_reqs/semantic_labels/requirements/semantic-label-capability.md)
            * `SL.001` | Version `0.1.0`
        * [Semantic Label Deprecated Schema](../rules_and_reqs/semantic_labels/requirements/semantic-label-deprecated-schema.md)
            * `SL.002` | Version `0.1.0`
        * [Semantic Label Schema](../rules_and_reqs/semantic_labels/requirements/semantic-label-schema.md)
            * `SL.003` | Version `0.1.0`

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author semantic labels with `SemanticsLabelsAPI:<instance>` and `semantics:labels:<instance>`.
- `.blend`
  - Via Blender SimReady Add-ons.
- `.mjcf`
  - Via Blender SimReady Add-ons and MJCF2USD tooling.
- `.step`
  - Via Blender SimReady Add-ons and CAD Converter tooling.

Validation or runtime pipeline:

- SimReady validation - verifies the `SL.001`, `SL.002`, and `SL.003` semantic-label contract.
- Semantic Labels Check - renders semantic-label validation evidence and highlights missing labels.

## Samples

- [`obs_orange_a02`](../../../../../../../sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd)
- [`obs_electricians_large_tool_box_a01`](../../../../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd)

## Evaluates

- Suite: [FET011 Semantic Labels](../runtime_tests/docs/fet011-semantic-labels.md)
  - Tests:
    - [semantic_labels_seg](../runtime_tests/docs/fet011/semantic-labels-seg.md)

## Adapters

None.
