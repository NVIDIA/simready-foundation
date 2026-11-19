# Feature: `FET004_Multibody.PhysX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET004_Multibody.PhysX` |
| Runtime                 | `PhysX` |
| Proprietary Techs       | `PhysX` |
| Versions                | `0-1-0`, `0-2-0`, `0-3-0`, `0-4-0` |

## Description

The PhysX Multi-Body Physics feature defines the PhysX runtime contract for
assets with multiple intended rigid bodies, joints, and PhysX-compatible
multibody collision behavior.

Earlier versions add PhysX collider requirements on top of the Standard
multibody contract. Version 0-4-0 is the current PhysX multibody contract and
carries the joint, articulation, multibody, and nested-link requirements
directly.

## Dependency Graph

```{mermaid}
flowchart LR
    FET003P1["FET003_RigidBody.PhysX\n0-1-0"]
    FET003P4["FET003_RigidBody.PhysX\n0-4-0"]
    FET004S1["FET004_Multibody\n0-1-0"]
    FET004P1["FET004_Multibody.PhysX\n0-1-0"]
    FET004P4["FET004_Multibody.PhysX\n0-4-0"]

    FET004P1 --> FET003P1
    FET004P1 --> FET004S1
    FET004P4 --> FET003P4

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004P1,FET004P4 current
    class FET003P1,FET003P4,FET004S1 other
```

## Use Cases

- PhysX multibody props and articulated mechanisms.
- Isaac Sim or PhysX runtime assets with multiple rigid bodies.
- Physics benchmarks that exercise jointed or linked bodies in a PhysX scene.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET003_RigidBody.PhysX.md#version-0-1-0) (`FET003_RigidBody.PhysX.0-1-0`) |
| Dependency | [Multi-Body Physics Standard](FET004_Multibody.md#version-0-1-0) (`FET004_Multibody.0-1-0`) |

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Physics Colliders | `COL.001` |

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET003_RigidBody.PhysX.md#version-0-2-0) (`FET003_RigidBody.PhysX.0-2-0`) |
| Dependency | [Multi-Body Physics Standard](FET004_Multibody.md#version-0-1-0) (`FET004_Multibody.0-1-0`) |

#### Changes From Version 0-1-0

Version 0-2-0 replaces `COL.001` with `PHYSX.COL.001` and `PHYSX.COL.002`.

</details>

### Version 0-3-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET003_RigidBody.PhysX.md#version-0-3-0) (`FET003_RigidBody.PhysX.0-3-0`) |
| Dependency | [Multi-Body Physics Standard](FET004_Multibody.md#version-0-2-0) (`FET004_Multibody.0-2-0`) |

#### Changes From Version 0-2-0

Version 0-3-0 keeps the PhysX collider requirements and updates dependencies to the
newer Standard and PhysX rigid-body contracts.

</details>

### Version 0-4-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): optional in `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET003_RigidBody.PhysX.md#version-0-4-0) (`FET003_RigidBody.PhysX.0-4-0`) |

#### Changes From Version 0-3-0

Version 0-4-0 replaces the dependency-on-Standard shape with an explicit PhysX
multibody requirement list:

| Change | Requirements |
|--------|--------------|
| Added | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |
| Removed | Direct `PHYSX.COL.001`, `PHYSX.COL.002`; collider conformance is provided by `FET003_RigidBody.PhysX.0-4-0` |

</details>

## Pipelines

Source file type:

- `.usd`
  - Via CIP conversion from Standard multibody assets.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET004_Multibody.PhysX` manifest.
- SimReady Evaluate FET004 Multibody - verifies jointed multibody behavior in a PhysX scene.

## Samples

- `sample_content/common_assets/props_general/obs_workbench_tool_a01/simready_usd/sm_obs_workbench_tool_a01_01.usda` - select the `PhysX` variant.
- `sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd` - multibody prop (5 rigid bodies, 4 revolute joints); select the `PhysX` variant.
- `sample_content/common_assets/props_general/obs_joystick_a01/simready_usd/sm_obs_joystick_a01_01.usd` - select the `PhysX` variant.
- `sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usda` - select the `PhysX` variant.

## Evaluates

- Suite: [FET004 Multibody](../runtime_tests/docs/fet004-multibody.md)
  - Tests:
    - [joint_movement](../runtime_tests/docs/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET004_Multibody.0-1-0` | `FET004_Multibody.PhysX.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | Done | Sets PhysX SDF collider approximation on existing collider prims. |
| `FET004_Multibody.0-2-0` | `FET004_Multibody.PhysX.0-4-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Validates neutral multibody topology and preserves extracted PhysX body/joint opinions in the isolated PhysX runnable payload. |
