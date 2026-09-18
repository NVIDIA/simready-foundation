# Feature: `FET_004_NEWTON`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_004_NEWTON` |
| Runtime                 | `NEWTON` |
| Proprietary Techs       | `Newton` |
| Latest Version          | `0.1.0` |

## Description

The Newton Multi-Body Physics feature defines the Newton runtime contract for
assets with multiple intended rigid bodies connected by joints and
articulations. It is the Newton expansion of
[Simulate Multi-Body Physics](FET_004_STANDARD.md): the multibody joint and
articulation requirements are the same, while the Newton-specific rigid-body and
collision behavior is provided by its `FET_003_NEWTON@0.1.0` dependency.

### Newton Authoring Notes

Editorial guidance (does not change the requirement IDs below):

- This feature covers the multibody topology (joints, articulation, link masses). Newton
  collision schemas come from `FET_003_NEWTON@0.1.0`.
- Newton joint tuning (`NewtonJointAPI` / `newton:armature` …), driven-joint actuation
  (`PhysicsDriveAPI` or `NewtonActuator`), and articulation-root self-collision
  (`NewtonArticulationRootAPI` / `newton:selfCollisionEnabled`) are the domain of the Newton
  driven-joint feature [`FET_022_NEWTON`](FET_022_NEWTON.md) and base-articulation feature
  [`FET_024_NEWTON`](FET_024_NEWTON.md); author them there when a robot/gripper profile pins
  those features.

## Dependency Graph

```{mermaid}
flowchart LR
    FET003N["FET_003_NEWTON\n0.1.0"]
    FET004N1["FET_004_NEWTON\n0.1.0"]

    FET004N1 --> FET003N

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004N1 current
    class FET003N other
```

## Use Cases

- Newton runtime multibody simulation for props and robot-adjacent assets.
- Nested link structures joined by Newton-compatible joints and articulations.
- Runtime payload variants where Newton is selectable alongside PhysX.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- `Robotics-Prop` (optional).

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics Newton](FET_003_NEWTON.md#version-010) (`FET_003_NEWTON@0.1.0`) |

The Newton collider requirements (`NEWTON.COL.001`, `NEWTON.COL.002`) and the
Newton rigid-body base are provided by the `FET_003_NEWTON@0.1.0` dependency, so they
are not re-listed here.

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Joints | `JT.001`, `JT.002`, `JT.003` |
| Joints (Articulation) | `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |
| Physics Rigid Bodies | `RB.MB.001`, `RB.011`, `RB.012` |

</details>

## Pipelines

Source file type:

- `.usd` / `.usda`
  - Via USD authoring tools that emit Newton runtime physics payload layers.

Validation or runtime pipeline:

- SimReady validation - verifies the `FET_004_NEWTON@0.1.0` manifest.

## Samples

- [sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd) - multibody prop (5 rigid bodies, 4 revolute joints); select the `Newton` variant.

## Benchmarks

- [FET004 Multibody](../guides/benchmark/tests/fet004-multibody.md)
  - [joint_movement](../guides/benchmark/tests/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_004_STANDARD@0.1.0` | `FET_004_NEWTON@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_newton` | Done | Applies Newton mesh-collision schemas (`newton:contactGap`) on existing collider prims. |
