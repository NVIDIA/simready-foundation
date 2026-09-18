# Feature: `FET_004_ROBOT_NEWTON`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_004_ROBOT_NEWTON` |
| Runtime                 | `ROBOT_NEWTON` |
| Proprietary Techs       | `Newton` |
| Latest Version          | `0.1.0` |

## Description

The Robot Newton Multi-Body Physics feature is a robot-specific Newton
multibody contract. It mirrors the robot PhysX shape, replaces PhysX collider
requirements with Newton collider requirements, and intentionally does not
require `RB.COL.001` because robot assets may use nested collision authoring
patterns.

## Dependency Graph

This feature has no JSON feature dependencies. It carries an explicit
robot-specific requirement list.

```{mermaid}
flowchart LR
    FET004RN["FET_004_ROBOT_NEWTON\n0.1.0"]
    FET022N["FET_022_NEWTON\n0.1.0"]

    FET022N --> FET004RN

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004RN current
    class FET022N other
```

## Use Cases

- Future Newton robot profiles that need a robot-specific collider exemption.
- Newton robot link and joint topology before driven-joint or articulation gates.

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
| Physics Rigid Bodies | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `RB.MB.001`, `NEWTON.COL.001`, `NEWTON.COL.002`, `NEWTON.MAS.001`, `RB.011`, `RB.012` |
| Physics Materials | `NEWTON.MAT.001` |
| Physics Joints | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |

</details>

## Pipelines

Source file type:

- `.urdf` / `.mjcf`
  - Via robot conversion workflows that preserve robot link structure.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET_004_ROBOT_NEWTON` manifest.

## Samples

- None.

## Benchmarks

- [FET004 Multibody](../guides/benchmark/tests/fet004-multibody.md)
  - [joint_movement](../guides/benchmark/tests/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_003_STANDARD@0.1.0` | `FET_004_ROBOT_NEWTON@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_newton` | Done | Computes mesh extents and applies Newton mesh-collision schemas (`newton:contactGap`), and applies `NewtonMaterialAPI` with default friction tuning to bound physics materials. |
