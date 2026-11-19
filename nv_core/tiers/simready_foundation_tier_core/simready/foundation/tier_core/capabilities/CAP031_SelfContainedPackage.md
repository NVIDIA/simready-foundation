# Capability: `CAP031_SelfContainedPackage`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP031_SelfContainedPackage` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines the Standard source-folder preflight contract. USD asset references under the source must resolve inside the source folder before wrapping.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- Package pre-validation verifies all asset references stay inside the package source.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [AIF-Entity](../../../../../simready_foundation_tier_aif/simready/foundation/tier_aif/profiles/aif-entity.md): required in `0.2.0`
- [Package-Candidate](../../../../../../sr_specs/docs/shared/profiles/profiles.md): required in `1.0.0`, `1.1.0`, `1.2.0`, `1.3.0`
- [Robot-Body](../profiles/robot-body.md): required in `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): required in `2.1.0`, `2.2.0`, `3.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): required in `3.2.0`, `3.3.0`, `4.0.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Core/Atomic Asset](../rules_and_reqs/core/atomic_asset/capability-atomic_asset.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `AA.001` | [AA.001](../rules_and_reqs/core/atomic_asset/requirements/anchored-asset-paths.md) | Provided by `usd-validation-nvidia` |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- Package pre-validation verifies all asset references stay inside the package source.

## Samples

- `sample_content/common_assets/props_general/apple_a01/simready_usd/` (source folder)

## Evaluates

- None.

## Adapters

None.
