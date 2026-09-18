# Feature: `FET_004_ROBOT_PHYSX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_004_ROBOT_PHYSX` |
| Runtime                 | `ROBOT_PHYSX` |
| Proprietary Techs       | `PhysX` |
| Latest Version          | `0.4.0` |

## Description

The Robot PhysX Multi-Body Physics feature is the legacy robot-specific PhysX
multibody contract. It bundles rigid-body, joint, articulation, and PhysX
collider requirements in one feature and intentionally does not require
`RB.COL.001` because robot assets may use nested collision authoring patterns.

Newer profile versions should prefer `FET_004_PHYSX@0.4.0` plus the selected FET003
PhysX gate when the robot-specific collider exemption is not required.

## Dependency Graph

This feature has no JSON feature dependencies. It carries an explicit
robot-specific requirement list.

```{mermaid}
flowchart LR
    FET004RP["FET_004_ROBOT_PHYSX\n0.1.0, 2, 3, 4"]
    FET022P["FET_022_PHYSX\n0.1.0, 2"]

    FET022P --> FET004RP

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004RP current
    class FET022P other
```

## Use Cases

- Legacy Robot-Body-Runnable and Robot-Body-Isaac profiles that need the robot PhysX collider exemption.
- Robot assets with nested collision opinions that base `RB.COL.001` would reject.
- PhysX robot link and joint topology before driven-joint or articulation gates.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

None.

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Physics Rigid Bodies | `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.006`, `RB.007`, `RB.009`, `RB.010`, `RB.MB.001`, `RB.011`, `RB.012` |
| Physics Joints | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- **[Robot Body Runnable Profile](../profiles/robot-body-runnable.md)** (`v2.0.0`) - Legacy runnable robot PhysX multibody contract.
- **[Robot Body Isaac Profile](../profiles/robot-body-isaac.md)** (`v1.0.0`) - Legacy Isaac robot PhysX multibody contract.

#### Feature Dependencies

None.

#### Changes From Version 0.1.0

Version 0.2.0 removes `RB.COL.002` and adds `PHYSX.COL.001` and `PHYSX.COL.002`.

</details>

### Version 0.3.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

None.

#### Changes From Version 0.2.0

Version 0.3.0 removes `RB.006`.

</details>

### Version 0.4.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- **[Robot Body Profile](../profiles/profiles.md)** (`v3.0.0`) - Optional legacy robot PhysX multibody feature.

#### Feature Dependencies

None.

#### Changes From Version 0.3.0

Version 0.4.0 keeps the Version 0.3.0 requirement list and represents the latest legacy
Robot PhysX multibody contract.

</details>

## Pipelines

Source file type:

- `.urdf` / `.mjcf`
  - Via robot conversion workflows that preserve robot link structure.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET_004_ROBOT_PHYSX` manifest.
- SimReady Benchmark FET004 Multibody - verifies jointed robot behavior in a PhysX scene.

## Samples

- [sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Benchmarks

- Suite: [FET004 Multibody](../guides/benchmark/tests/fet004-multibody.md)
  - Tests:
    - [joint_movement](../guides/benchmark/tests/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_003_STANDARD@0.1.0` | `FET_004_ROBOT_PHYSX@0.2.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_physx` | Done | Computes mesh extents for the legacy robot PhysX path. |
