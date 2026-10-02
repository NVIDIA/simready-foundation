# Feature: `FET_032_STANDARD`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_032_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the Standard package-introspection contract by adding a Bill of Materials file that exposes package contents without requiring full download.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_030_STANDARD_0_1_0["FET_030_STANDARD\n0.1.0"]
    FET_032_STANDARD_0_1_0["FET_032_STANDARD\n0.1.0"]
    FET_032_STANDARD_0_1_0 --> FET_030_STANDARD_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- Package validation verifies BOM structure, paths, sizes, and optional hash objects.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Package v1.0.0

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_030_STANDARD@0.1.0` |

#### Requirement List

* Capability: [Packaging/Packaging Introspection](../capabilities/packaging/packaging_introspection/capability-packaging_introspection.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `PKG.BOM.001` | [PKG.BOM.001](../capabilities/packaging/packaging_introspection/requirements/bom-structure.md) | [Implementation](../capabilities/packaging/packaging_introspection/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- Package validation verifies BOM structure, paths, sizes, and optional hash objects.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.
