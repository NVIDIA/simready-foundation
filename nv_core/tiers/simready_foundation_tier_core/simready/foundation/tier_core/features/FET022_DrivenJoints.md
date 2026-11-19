# Feature: `FET022_DrivenJoints`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET022_DrivenJoints` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

Defines the Standard OpenUSD driven-joint contract for articulated robot mechanisms using joint drive/state APIs, consistent joint transforms and states, and loop-free articulation graphs.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_004_STANDARD_0_1_0["FET004_Multibody\n0-1-0"]
    FET_004_STANDARD_0_2_0["FET004_Multibody\n0-2-0"]
    FET_022_STANDARD_0_1_0["FET022_DrivenJoints\n0-1-0"]
    FET_022_STANDARD_0_2_0["FET022_DrivenJoints\n0-2-0"]
    FET_022_STANDARD_0_1_0 --> FET_004_STANDARD_0_1_0
    FET_022_STANDARD_0_2_0 --> FET_004_STANDARD_0_2_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies the selected FET022_DrivenJoints manifest.
- Runtime-specific FET022 features extend this authoring for engine execution.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET004_Multibody.0-1-0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Driven Joints](../rules_and_reqs/physics_bodies/physics_driven_joints/capability-physics_driven_joints.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `DJ.001` | [DJ.001](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/physics-drive-and-joint-state.md) |
| `DJ.002` | [DJ.002](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/joint-has-joint-state-api.md) |
| `DJ.003` | [DJ.003](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/joint-has-correct-transform-and-state.md) |
| `DJ.011` | [DJ.011](../rules_and_reqs/physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md) |

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET004_Multibody.0-2-0` |

#### Changes From Version 0-1-0

Keeps Version 0-1-0 requirements and updates the dependency to FET004_Multibody.0-2-0.

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies the selected FET022_DrivenJoints manifest.
- Runtime-specific FET022 features extend this authoring for engine execution.

## Samples

- [`ur10` PhysX robot demonstrating the Standard driven-joint contract](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Evaluates

- None. The bundled driven-joint tests register against the PhysX and Isaac
  runtime variants, not the Standard authoring feature.

## Adapters

None.
