# Capability: `CAP030_PackagingCore`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP030_PackagingCore` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines the Standard package contract for package identity, root metadata, hash object format, conformance metadata, and anchored internal asset references.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- Package validation verifies the selected package feature manifest.
- Package creation workflows use the package feature contracts for create and validation phases.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Package](../../../../../../sr_specs/docs/shared/profiles/profiles.md): required in `1.0.0`
- [Package-NoBOM](../../../../../../sr_specs/docs/shared/profiles/profiles.md): required in `1.0.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Packaging Core](../rules_and_reqs/packaging/packaging_core/capability-packaging_core.md), [Conformance Metadata](../rules_and_reqs/packaging/conformance_metadata/capability-conformance_metadata.md), [Atomic Asset](../rules_and_reqs/core/atomic_asset/capability-atomic_asset.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `PKG.DEF.001` | [PKG.DEF.001](../rules_and_reqs/packaging/packaging_core/requirements/package-definition.md) |
| `PKG.META.001` | [PKG.META.001](../rules_and_reqs/packaging/packaging_core/requirements/metadata-files.md) |
| `PKG.HASH.001` | [PKG.HASH.001](../rules_and_reqs/packaging/packaging_core/requirements/hash-object-format.md) |
| `PKG.CONF.001` | [PKG.CONF.001](../rules_and_reqs/packaging/conformance_metadata/requirements/conformance-metadata.md) |
| `AA.001` | [AA.001](../rules_and_reqs/core/atomic_asset/requirements/anchored-asset-paths.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- Package validation verifies the selected package feature manifest.
- Package creation workflows use package feature contracts for create and validation phases.

## Samples

- `sample_content/packaging/simple_packages/`

## Evaluates

- None.

## Adapters

None.
