# Feature: `FET_028_MUJOCO`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_028_MUJOCO` |
| Runtime | `MUJOCO` |
| Proprietary Techs | `MuJoCo` |
| Latest Version | `1` |

## Description

Defines the MuJoCo gripper-site contract. It depends on the Standard gripper-site feature and MuJoCo driven-joint feature, then adds `MjcSiteAPI` on gripper site prims so MuJoCo tooling can treat them as runtime sites.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_022_MUJOCO_1["FET_022_MUJOCO\n1"]
    FET_028_STANDARD_1["FET_028_STANDARD\n1"]
    FET_028_MUJOCO_1["FET_028_MUJOCO\n1"]
    FET_028_MUJOCO_1 --> FET_028_STANDARD_1
    FET_028_MUJOCO_1 --> FET_022_MUJOCO_1

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

- SimReady validation verifies MuJoCo gripper-site schema authoring.
- MuJoCo gripper control workflows can locate gripper sites through `MjcSiteAPI`.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `FET_028_STANDARD@0.1.0` |
| Dependency | `FET_022_MUJOCO@0.1.0` |

#### Requirement List

* Capability: [Physics Bodies/Physics Grippers](../capabilities/physics_bodies/physics_grippers/capability-physics_grippers.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `MUJOCO.GR.001` | [MUJOCO.GR.001](../capabilities/physics_bodies/physics_grippers/requirements/mujoco-gripper-site-api.md) | [Implementation](../capabilities/physics_bodies/physics_grippers/validation.py) |

</details>

## Pipelines

Source file type:

- `.mjcf`, `.xml`, `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- SimReady validation verifies `FET_028_MUJOCO@0.1.0`.
- MuJoCo runtime validation should verify gripper site discovery and actuation.

## Samples

- [`Robotiq 2F-85` gripper](../../../../sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/2F-85.usda)

## Benchmarks

- None.

## Adapters

None.
