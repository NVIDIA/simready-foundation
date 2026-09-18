# Feature: `FET_042_STANDARD`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_042_STANDARD` |
| Runtime                 | `STANDARD` |
| Proprietary Techs       | `None` |
| Latest Version          | `0.1.0` |

## Description

This feature validates that semantic labels authored on the
`SemanticsLabelsAPI:ade20k` instance are real members of the
**ADE20K (150 classes)** taxonomy. It is a closed-vocabulary check: values
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

- Indoor/outdoor scene-parsing synthetic data generation
- Example profile for authoring assets with a non-NVIDIA taxonomy

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Open-Taxonomy-ADE20K](../profiles/open-taxonomy-ade20k.md)** (`v0.1.0`) - Validates one closed-vocabulary taxonomy at a time.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Dataset Taxonomies](../capabilities/dataset_taxonomies/capability-dataset_taxonomies.md)
    * Requirements:
        * [ADE20K Labels](../capabilities/dataset_taxonomies/requirements/ade20k-labels.md)
            * `ADE.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/dataset_taxonomies/validation.py)

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author `SemanticsLabelsAPI:ade20k` and `semantics:labels:ade20k` with canonical ADE20K class names.

Validation or runtime pipeline:

- SimReady validation - verifies `ADE.001` taxonomy membership.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.
