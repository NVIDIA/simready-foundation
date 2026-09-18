# Feature: `FET_046_STANDARD`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_046_STANDARD` |
| Runtime                 | `STANDARD` |
| Proprietary Techs       | `None` |
| Latest Version          | `0.1.0` |

## Description

This feature validates labels authored on the
`SemanticsLabelsAPI:wikidata_qcode` instance. Every value must use the Wikidata
Q-code format: `Q` followed by one or more digits. It makes Wikidata an explicit
taxonomy choice, separate from the taxonomy-agnostic semantic-label contract in
[`FET_011_STANDARD`](FET_011_STANDARD.md).

NVIDIA's Omniverse asset libraries use this taxonomy, so assets intended to ship
alongside them should select this feature in addition to `FET_011_STANDARD`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET046STD["FET_046_STANDARD\n0.1.0"]
    FET011STD["FET_011_STANDARD\n0.2.0"]

    FET046STD --> FET011STD

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET046STD current
    class FET011STD other
```

## Use Cases

Products or workflows that consume this feature:

- NVIDIA Omniverse asset libraries
- Synthetic data generation that keys ground truth on Wikidata Q-codes

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop-Robotics-Physx](../profiles/prop-robotics-physx.md)** (`v2.3.0`) - Wikidata Q-code label values for NVIDIA asset libraries.

#### Feature Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [`Semantic Labels`](FET_011_STANDARD.md) (`FET_011_STANDARD@0.2.0`) |

#### Requirement List

* Capability: [Semantic Labels](../capabilities/semantic_labels/capability-semantic_labels.md)
    * Requirements:
        * [Semantic Label QCode Valid](../capabilities/semantic_labels/requirements/semantic-label-qcode-valid.md)
            * `SL.QCODE.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author `SemanticsLabelsAPI:wikidata_qcode` and `semantics:labels:wikidata_qcode` with `Q<digits>` values.

Validation or runtime pipeline:

- SimReady validation - verifies the `SL.QCODE.001` Q-code format contract.
- Semantic Labels Check - exercises the Q-code rule at runtime where the
  `wikidata_qcode` taxonomy is used.

## Samples

- None.

## Benchmarks

- Suite: [FET011 Semantic Labels](../guides/benchmark/tests/fet011-semantic-labels.md)
  - Tests:
    - [semantic_labels_seg](../guides/benchmark/tests/fet011/semantic-labels-seg.md)

## Adapters

None.
