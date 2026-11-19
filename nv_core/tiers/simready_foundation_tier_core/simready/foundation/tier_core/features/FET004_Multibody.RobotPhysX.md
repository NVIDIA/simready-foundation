# Feature: `FET004_Multibody.RobotPhysX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET004_Multibody.RobotPhysX` |
| Runtime                 | `RobotPhysX` |
| Proprietary Techs       | `PhysX` |
| Versions                | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |

:::{warning}
`FET004_Multibody.RobotPhysX` is deprecated. It is retained only so existing profile
assets and external consumers can continue to resolve historical contracts. No
current in-repository profile selects it. Do not add this feature to new profile
versions. Use `FET003_RigidBody.PhysX.0-4-0` and
`FET004_Multibody.PhysX.0-4-0` instead.
:::

## Description

The Robot PhysX Multi-Body Physics feature is the legacy robot-specific PhysX
multibody contract. It bundles rigid-body, joint, articulation, and PhysX
collider requirements in one feature and intentionally does not require
`RB.COL.001` because robot assets may use nested collision authoring patterns.

New profile versions must use `FET004_Multibody.PhysX.0-4-0` plus
`FET003_RigidBody.PhysX.0-4-0`. The deprecated robot-specific feature is not eligible
for adoption by new profiles, even when preserving a legacy asset requires
compatibility validation against it.

## Dependency Graph

This feature has no JSON feature dependencies. It carries an explicit
robot-specific requirement list.

```{mermaid}
flowchart LR
    FET004RP["FET004_Multibody.RobotPhysX\n0-1-0, 0-2-0, 0-3-0, 0-4-0"]
    FET022P["FET022_DrivenJoints.PhysX\n0-1-0, 0-2-0"]

    FET022P --> FET004RP

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004RP current
    class FET022P other
```

## Use Cases

- Compatibility validation for assets or external profiles whose published
  contract already pins this feature.
- Existing assets whose validation metadata includes the legacy
  robot PhysX collider exemption.

This feature is not a valid selection for a new profile or profile version.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

None.

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Physics Rigid Bodies | `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `RB.MB.001`, `RB.011`, `RB.012` |
| Physics Joints | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

None.

#### Changes From Version 0-1-0

Version 0-2-0 removes `RB.COL.002` and adds `PHYSX.COL.001` and `PHYSX.COL.002`.

</details>

### Version 0-3-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

None.

#### Changes From Version 0-2-0

Version 0-3-0 removes `RB.006`.

</details>

### Version 0-4-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

None.

#### Changes From Version 0-3-0

Version 0-4-0 keeps the Version 0-3-0 requirement list and represents the latest legacy
Robot PhysX multibody contract.

</details>

## Pipelines

Source file type:

- `.urdf` / `.mjcf`
  - Via robot conversion workflows that preserve robot link structure.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET004_Multibody.RobotPhysX` manifest.
- SimReady Evaluate FET004 Multibody - verifies jointed robot behavior in a PhysX scene.

## Samples

- [sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Evaluates

- Suite: [FET004 Multibody](../runtime_tests/docs/fet004-multibody.md)
  - Tests:
    - [joint_movement](../runtime_tests/docs/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET003_RigidBody.0-1-0` | `FET004_Multibody.RobotPhysX.0-2-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | Done | Computes mesh extents for the legacy robot PhysX path. |
