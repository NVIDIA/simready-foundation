# Feature: `FET_030_STANDARD`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_030_STANDARD` |
| Runtime | `STANDARD` |
| Proprietary Techs | `None` |
| Latest Version | `0.1.0` |

## Description

Defines the Standard package contract for package identity, root metadata, hash object format, conformance metadata, and anchored internal asset references.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- Package validation verifies the selected package feature manifest.
- Package creation workflows use package profiles for preflight/create/validate phases.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- Package v1.0.0
- Package-No-BOM v1.0.0

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Packaging Core](../capabilities/packaging/packaging_core/capability-packaging_core.md), [Conformance Metadata](../capabilities/packaging/conformance_metadata/capability-conformance_metadata.md), [Atomic Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `PKG.DEF.001` | [PKG.DEF.001](../capabilities/packaging/packaging_core/requirements/package-definition.md) | [Implementation](../capabilities/packaging/packaging_core/validation.py) |
| `PKG.META.001` | [PKG.META.001](../capabilities/packaging/packaging_core/requirements/metadata-files.md) | [Implementation](../capabilities/packaging/packaging_core/validation.py) |
| `PKG.HASH.001` | [PKG.HASH.001](../capabilities/packaging/packaging_core/requirements/hash-object-format.md) | [Implementation](../capabilities/packaging/packaging_core/validation.py) |
| `PKG.CONF.001` | [PKG.CONF.001](../capabilities/packaging/conformance_metadata/requirements/conformance-metadata.md) | [Implementation](../capabilities/packaging/packaging_core/validation.py) |
| `AA.001` | [AA.001](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md) | [Implementation](../capabilities/packaging/packaging_core/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- Package validation verifies the selected package feature manifest.
- Package creation workflows use package profiles for preflight/create/validate phases.

## Samples

- `sample_content/packaging/simple_packages/`

## Benchmarks

- None.

## Adapters

None.
