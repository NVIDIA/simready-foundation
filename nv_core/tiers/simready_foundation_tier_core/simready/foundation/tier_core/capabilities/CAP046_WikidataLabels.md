# Capability: `CAP046_WikidataLabels`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP046_WikidataLabels` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

This capability validates labels authored on the
`SemanticsLabelsAPI:wikidata_qcode` instance. Every value must use the Wikidata
Q-code format: `Q` followed by one or more digits. It makes Wikidata an explicit
taxonomy choice, separate from the taxonomy-agnostic semantic-label contract in
[`FET011_SemanticLabels`](../features/FET011_SemanticLabels.md).

NVIDIA's Omniverse asset libraries use this taxonomy, so assets intended to ship
alongside them should select this capability in addition to `FET011_SemanticLabels`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET046STD["CAP046_WikidataLabels\n0-1-0"]
    FET011STD["FET011_SemanticLabels\n0-2-0"]

    FET046STD --> FET011STD

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET046STD current
    class FET011STD other
```

## Use Cases

Products or workflows that consume this capability:

- NVIDIA Omniverse asset libraries
- Synthetic data generation that keys ground truth on Wikidata Q-codes

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robotics-Prop](../profiles/robotics-prop.md): required in `3.2.0`, `3.3.0`, `4.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [`Semantic Labels`](../features/FET011_SemanticLabels.md) (`FET011_SemanticLabels.0-2-0`) |

#### Requirement List

* Capability: [Semantic Labels](../rules_and_reqs/semantic_labels/capability-semantic_labels.md)
    * Requirements:
        * [Semantic Label QCode Valid](../rules_and_reqs/semantic_labels/requirements/semantic-label-qcode-valid.md)
            * `SL.QCODE.001` | Version `0.1.0`

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

## Evaluates

- Suite: [FET011 Semantic Labels](../runtime_tests/docs/fet011-semantic-labels.md)
  - Tests:
    - [semantic_labels_seg](../runtime_tests/docs/fet011/semantic-labels-seg.md)

## Adapters

None.
