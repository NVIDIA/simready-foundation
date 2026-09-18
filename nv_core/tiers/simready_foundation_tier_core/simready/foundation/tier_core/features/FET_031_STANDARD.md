# Feature: `FET_031_STANDARD`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_031_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the Standard source-folder preflight contract. USD asset references under the source must resolve inside the source folder before wrapping.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- Package pre-validation verifies all asset references stay inside the package source.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Package-Candidate v1.0.0

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Core/Atomic Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `AA.001` | [AA.001](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md) | [Implementation](../capabilities/core/atomic_asset/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- Package pre-validation verifies all asset references stay inside the package source.

## Samples

- `sample_content/common_assets/props_general/apple_a01/simready_usd/` (source folder)

## Benchmarks

- None.

## Adapters

None.
