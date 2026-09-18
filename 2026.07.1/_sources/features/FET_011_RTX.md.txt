# Feature: `FET_011_RTX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_011_RTX` |
| Runtime                 | `RTX` |
| Proprietary Techs       | `NVIDIA Omniverse, RTX` |
| Latest Version          | `0.1.0` |

## Description

This feature adds the NVIDIA RTX semantic-label conventions on top of the
Standard semantic-label contract. An asset that satisfies this feature carries a
non-empty `SemanticsLabelsAPI:material` label on every `UsdShade.Material` prim,
so RTX sensor and perception workflows can produce material-segmentation ground
truth in addition to object/class ground truth, and it keeps every semantic label
static.

Object labels describe what a thing is; the `material` taxonomy describes what it
is made of. Both coexist on the same asset through the `SemanticsLabelsAPI`
multiple-apply schema.

The RTX perception pipeline samples one constant label per object, so
time-sampled label values are a pipeline limitation rather than invalid USD.
Time-varying labels remain legal under the neutral
[`FET_011_STANDARD`](FET_011_STANDARD.md) contract; they only fail here.

## Dependency Graph

```{mermaid}
flowchart LR
    FET011RTX["FET_011_RTX\n0.1.0"]
    FET011STD["FET_011_STANDARD\n0.2.0"]

    FET011RTX --> FET011STD

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET011RTX current
    class FET011STD other
```

## Use Cases

Products or workflows that consume this feature:

- Isaac Sim RTX sensor workflows
- Material-segmentation ground truth for ML training
- NVIDIA Omniverse asset libraries

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop-Robotics-Physx](../profiles/prop-robotics-physx.md)** (`v2.3.0`) - Material-segmentation ground truth on prop materials.

#### Feature Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [`Semantic Labels`](FET_011_STANDARD.md) (`FET_011_STANDARD@0.2.0`) |

#### Requirement List

* Capability: [Semantic Labels](../capabilities/semantic_labels/capability-semantic_labels.md)
    * Requirements:
        * [Semantic Label Material](../capabilities/semantic_labels/requirements/semantic-label-material.md)
            * `SL.MAT.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)
        * [Semantic Label Time](../capabilities/semantic_labels/requirements/semantic-label-time.md)
            * `SL.TIME.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author `SemanticsLabelsAPI:material` and `semantics:labels:material` on each `UsdShade.Material` prim, with no time samples on any label attribute.

Validation or runtime pipeline:

- SimReady validation - verifies the `SL.MAT.001` material-label and `SL.TIME.001` static-label contract.
- Semantic Labels Check - confirms labels resolve to constant values at runtime.

## Samples

- None.

## Benchmarks

- Suite: [FET011 Semantic Labels](../guides/benchmark/tests/fet011-semantic-labels.md)
  - Tests:
    - [semantic_labels_seg](../guides/benchmark/tests/fet011/semantic-labels-seg.md)
      covers `SL.TIME.001` at runtime. `SL.MAT.001` is offline-validator-only.

## Adapters

None.
