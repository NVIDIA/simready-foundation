# Capability: `CAP024_BaseArticulation`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP024_BaseArticulation` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines the Standard base-articulation contract: the articulated asset must have exactly one UsdPhysics.ArticulationRootAPI application for the mechanism.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- SimReady validation verifies CAP024_BaseArticulation articulation-root requirements.
- `simready-foundation-conform-fet-024-standard` repairs articulation-root placement on staged robot assets.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Physics Bodies/Base Articulation](../rules_and_reqs/physics_bodies/base_articulation/capability-base-articulation.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `BA.001` | [BA.001](../rules_and_reqs/physics_bodies/base_articulation/requirements/has-articulation-root.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies CAP024_BaseArticulation articulation-root requirements.
- `simready-foundation-conform-fet-024-standard` repairs articulation-root placement on staged robot assets.

## Samples

- [`ur10` PhysX robot demonstrating the Standard base-articulation contract](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Evaluates

- None.

## Adapters

None.
