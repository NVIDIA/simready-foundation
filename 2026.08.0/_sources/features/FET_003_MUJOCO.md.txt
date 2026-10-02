# Feature: `FET_003_MUJOCO`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_003_MUJOCO` |
| Runtime | `MUJOCO` |
| Proprietary Techs | `MuJoCo` |
| Latest Version | `0.1.0` |

## Description

Defines the MuJoCo rigid-body physics contract. This feature keeps the Standard USD rigid-body and collider requirements, then adds MuJoCo collision schema requirements from the official experimental `mjcPhysics` schema.

The MuJoCo runtime layer must use standard `UsdPhysics` rigid bodies, mass, collision, and mesh collision authoring. MuJoCo-specific runtime data is added through `MjcCollisionAPI` and `MjcMeshCollisionAPI`. A `UsdPhysics.Scene` with `MjcSceneAPI` is a scenario-level concern and is not required for a single asset.

## Dependency Graph

This feature has no JSON feature dependencies. It carries an explicit runtime-specific requirement list so the MuJoCo rigid-body contract can be validated directly.

```{mermaid}
flowchart LR
    FET003M["FET_003_MUJOCO\n0.1.0"]
    FET004M["FET_004_MUJOCO\n0.1.0"]

    FET004M --> FET003M

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET003M current
    class FET004M other
```

## Use Cases

- MuJoCo runtime rigid-body simulation for USD assets.
- MJCF-to-USD conversion workflows using the official MuJoCo USD schema.
- Runtime physics variants where MuJoCo is selectable alongside PhysX and Newton.

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
| Physics Rigid Bodies | `RB.COL.001`, `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `MUJOCO.COL.001`, `MUJOCO.COL.002` |

</details>

## Pipelines

Source file type:

- `.mjcf`, `.xml`, `.usd`, `.usda`, `.usdc`
  - Via MuJoCo MJCF authoring or MJCF-to-USD conversion workflows that emit `mjcPhysics` schemas.

Validation or runtime pipeline:

- SimReady validation verifies the selected `FET_003_MUJOCO` manifest.
- MuJoCo runtime validation should import the authored USD layer stack and confirm rigid-body collision behavior.

## Samples

- None.

## Benchmarks

- None.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_003_STANDARD@0.1.0` | `FET_003_MUJOCO@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_mujoco` | Done | Computes mesh extents and applies MuJoCo mesh-collision schemas (`convexHull`) for the prop MuJoCo rigid-body path. |
