# Capability: `CAP040_CocoLabels`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP040_CocoLabels` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

This capability validates that semantic labels authored on the
`SemanticsLabelsAPI:coco` instance are real members of the
**COCO (instances, 80 classes)** taxonomy. It is a closed-vocabulary check:
values outside the taxonomy fail; values that match only after
case/spacing/alias normalization pass with a warning that suggests the canonical
class name.

It is one of several example taxonomy features that show SimReady labeling is
not tied to NVIDIA's Wikidata Q-code taxonomy. See
[Adding a custom taxonomy](../../../../../../sr_specs/docs/guides/adding_a_custom_taxonomy.md).

## Dependency Graph

This capability has no declared feature dependencies. It judges authored label
values only, so it pairs naturally with
[`FET011_SemanticLabels`](../features/FET011_SemanticLabels.md), which requires that geometry carry a
label at all.

## Use Cases

Products or workflows that consume this capability:

- Synthetic data generation against public COCO-trained models
- Example profile for authoring assets with a non-NVIDIA taxonomy

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Open-Taxonomy-COCO](../profiles/open-taxonomy-coco.md): required in `0.1.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Dataset Taxonomies](../rules_and_reqs/dataset_taxonomies/capability-dataset_taxonomies.md)
    * Requirements:
        * [COCO Labels](../rules_and_reqs/dataset_taxonomies/requirements/coco-labels.md)
            * `COCO.001` | Version `0.1.0`

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author `SemanticsLabelsAPI:coco` and `semantics:labels:coco` with canonical COCO class names.

Validation or runtime pipeline:

- SimReady validation - verifies `COCO.001` taxonomy membership.

## Samples

- None.

## Evaluates

- None.

## Adapters

None.
