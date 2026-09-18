# Feature: `FET_045_STANDARD`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_045_STANDARD` |
| Runtime                 | `STANDARD` |
| Proprietary Techs       | `None` |
| Latest Version          | `0.1.0` |

## Description

This feature validates that semantic labels authored on the
`SemanticsLabelsAPI:imagenet_1k` instance are real members of the
**ImageNet-1K (1000 classes)** taxonomy. It is a closed-vocabulary check: values
outside the taxonomy fail; values that match only after case/spacing/alias
normalization pass with a warning that suggests the canonical class name.

It is one of several example taxonomy features that show SimReady labeling is
not tied to NVIDIA's Wikidata Q-code taxonomy. See
[Adding a custom taxonomy](../guides/adding_a_custom_taxonomy.md).

## Dependency Graph

This feature has no declared feature dependencies. It judges authored label
values only, so it pairs naturally with
[`FET_011_STANDARD`](FET_011_STANDARD.md), which requires that geometry carry a
label at all.

## Use Cases

Products or workflows that consume this feature:

- Classification-oriented synthetic data generation
- Example profile for authoring assets with a non-NVIDIA taxonomy

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Open-Taxonomy-ImageNet1K](../profiles/open-taxonomy-imagenet_1k.md)** (`v0.1.0`) - Validates one closed-vocabulary taxonomy at a time.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Dataset Taxonomies](../capabilities/dataset_taxonomies/capability-dataset_taxonomies.md)
    * Requirements:
        * [ImageNet-1K Labels](../capabilities/dataset_taxonomies/requirements/imagenet-labels.md)
            * `IN1K.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/dataset_taxonomies/validation.py)

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author `SemanticsLabelsAPI:imagenet_1k` and `semantics:labels:imagenet_1k` with canonical ImageNet-1K class names.

Validation or runtime pipeline:

- SimReady validation - verifies `IN1K.001` taxonomy membership.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.
