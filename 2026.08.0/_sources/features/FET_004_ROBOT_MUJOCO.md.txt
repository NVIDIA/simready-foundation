# Feature: `FET_004_ROBOT_MUJOCO`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_004_ROBOT_MUJOCO` |
| Runtime | `ROBOT_MUJOCO` |
| Proprietary Techs | `MuJoCo` |
| Latest Version | `0.1.0` |

## Description

Defines the robot-specific MuJoCo multibody contract. It mirrors the robot PhysX/Newton multibody shape by bundling robot rigid-body, joint, articulation, and runtime collider requirements in one feature.

This feature intentionally omits `RB.COL.001` and `RB.COL.002` because robot assets may use nested collision authoring patterns, and MuJoCo collider rules replace the Standard collider placement checks for this runtime.

## Dependency Graph

This feature has no JSON feature dependencies. It carries an explicit robot-specific requirement list.

```{mermaid}
flowchart LR
    FET004RM["FET_004_ROBOT_MUJOCO\n0.1.0"]
    FET022M["FET_022_MUJOCO\n0.1.0"]

    FET022M --> FET004RM

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004RM current
    class FET022M other
```

## Use Cases

- MuJoCo robot profiles that need a robot-specific collider exemption.
- MuJoCo robot link and joint topology before driven-joint, gripper, or articulation gates.
- MJCF-to-USD robot conversion workflows using official `mjcPhysics` schemas.

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
| Physics Rigid Bodies | `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `RB.MB.001`, `MUJOCO.COL.001`, `MUJOCO.COL.002`, `RB.011`, `RB.012` |
| Physics Joints | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |

</details>

## Pipelines

Source file type:

- `.mjcf`, `.xml`, `.urdf`, `.usd`, `.usda`, `.usdc`
  - Via robot conversion workflows that preserve robot link structure.

Validation or runtime pipeline:

- SimReady validation verifies the selected `FET_004_ROBOT_MUJOCO` manifest.
- MuJoCo runtime validation should import the robot layer stack and confirm linked-body simulation.

## Samples

- None.

## Benchmarks

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_003_STANDARD@0.1.0` | `FET_004_ROBOT_MUJOCO@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_mujoco` | Done | Computes mesh extents and applies MuJoCo mesh-collision schemas (`convexHull`) for the robot MuJoCo path. |
