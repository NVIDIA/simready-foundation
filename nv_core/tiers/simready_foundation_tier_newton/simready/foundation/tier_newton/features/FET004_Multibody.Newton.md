# Feature: `FET004_Multibody.Newton`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET004_Multibody.Newton` |
| Runtime                 | `Newton` |
| Proprietary Techs       | `Newton` |
| Versions                | `0-1-0` |

## Description

The Newton Multi-Body Physics feature defines the Newton runtime contract for
assets with multiple intended rigid bodies connected by joints and
articulations. It is the Newton expansion of
[Simulate Multi-Body Physics](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/features/FET004_Multibody.md): the multibody joint and
articulation requirements are the same, while the Newton-specific rigid-body and
collision behavior is provided by its `FET003_RigidBody.Newton.0-1-0` dependency.

### Newton Authoring Notes

Editorial guidance (does not change the requirement IDs below):

- This feature covers the multibody topology (joints, articulation, link masses). Newton
  collision schemas come from `FET003_RigidBody.Newton.0-1-0`.
- Newton joint tuning (`NewtonJointAPI` / `newton:armature` …), driven-joint actuation
  (`PhysicsDriveAPI` or `NewtonActuator`), and articulation-root self-collision
  (`NewtonArticulationRootAPI` / `newton:selfCollisionEnabled`) are the domain of the Newton
  driven-joint feature [`FET022_DrivenJoints.Newton`](FET022_DrivenJoints.Newton.md) and base-articulation feature
  [`CAP024_BaseArticulation.Newton`](../capabilities/CAP024_BaseArticulation.Newton.md); author them there when a robot/gripper profile pins
  those features.

## Dependency Graph

```{mermaid}
flowchart LR
    FET003N["FET003_RigidBody.Newton\n0-1-0"]
    FET004N1["FET004_Multibody.Newton\n0-1-0"]

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

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-body.md): optional in `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`; required in `4.0.0`
- [Robot-Gripper](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robot-gripper.md): optional in `2.1.0`, `2.2.0`, `3.0.0`; required in `4.0.0`
- [Robotics-Prop](../../../../../simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md): optional in `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics Newton](FET003_RigidBody.Newton.md#version-0-1-0) (`FET003_RigidBody.Newton.0-1-0`) |

The Newton collider requirements (`NEWTON.COL.001`, `NEWTON.COL.002`) and the
Newton rigid-body base are provided by the `FET003_RigidBody.Newton.0-1-0` dependency, so they
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

- SimReady validation - verifies the `FET004_Multibody.Newton.0-1-0` manifest.

## Samples

- [sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd) - multibody prop (5 rigid bodies, 4 revolute joints); select the `Newton` variant.

## Evaluates

 - [Newton multibody observations](../runtime_tests/docs/runtime-tests.md#qualified-joint-movement-observations)
   - `joint_movement_newton` (independently owned Newton procedure).

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET004_Multibody.0-1-0` | `FET004_Multibody.Newton.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_newton` | Done | Applies Newton mesh-collision schemas (`newton:contactGap`) on existing collider prims. |
| `FET004_Multibody.0-2-0` | `FET004_Multibody.Newton.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Validates the neutral multibody topology used by Newton; no joints or runtime intent are invented. |
