# Feature: `FET_004_PHYSX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_004_PHYSX` |
| Runtime                 | `PHYSX` |
| Proprietary Techs       | `PhysX` |
| Latest Version          | `0.4.0` |

## Description

The PhysX Multi-Body Physics feature defines the PhysX runtime contract for
assets with multiple intended rigid bodies, joints, and PhysX-compatible
multibody collision behavior.

Earlier versions add PhysX collider requirements on top of the Standard
multibody contract. Version 0.4.0 is the current PhysX multibody contract and
carries the joint, articulation, multibody, and nested-link requirements
directly.

## Dependency Graph

```{mermaid}
flowchart LR
    FET003P1["FET_003_PHYSX\n0.1.0"]
    FET003P4["FET_003_PHYSX\n0.4.0"]
    FET004S1["FET_004_STANDARD\n0.1.0"]
    FET004P1["FET_004_PHYSX\n0.1.0"]
    FET004P4["FET_004_PHYSX\n0.4.0"]

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

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- **[Prop Robotics PhysX Profile](../profiles/prop-robotics-physx.md)** (`v1.0.0`, `v2.0.0`, `v2.0.1`) - Original PhysX multibody prop contract.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.0.0`, `v1.0.1`) - Original Isaac composition with PhysX multibody contract.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET_003_PHYSX.md#version-010) (`FET_003_PHYSX@0.1.0`) |
| Dependency | [Multi-Body Physics Standard](FET_004_STANDARD.md#version-010) (`FET_004_STANDARD@0.1.0`) |

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Physics Colliders | `COL.001` |

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- None documented.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET_003_PHYSX.md#version-020) (`FET_003_PHYSX@0.2.0`) |
| Dependency | [Multi-Body Physics Standard](FET_004_STANDARD.md#version-010) (`FET_004_STANDARD@0.1.0`) |

#### Changes From Version 0.1.0

Version 0.2.0 replaces `COL.001` with `PHYSX.COL.001` and `PHYSX.COL.002`.

</details>

### Version 0.3.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- **[Prop Robotics PhysX Profile](../profiles/prop-robotics-physx.md)** (`v2.1.0`) - Updated PhysX multibody prop contract.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.1.0`) - Updated Isaac composition with PhysX multibody contract.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET_003_PHYSX.md#version-030) (`FET_003_PHYSX@0.3.0`) |
| Dependency | [Multi-Body Physics Standard](FET_004_STANDARD.md#version-020) (`FET_004_STANDARD@0.2.0`) |

#### Changes From Version 0.2.0

Version 0.3.0 keeps the PhysX collider requirements and updates dependencies to the
newer Standard and PhysX rigid-body contracts.

</details>

### Version 0.4.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- **[Robot Body Runnable Profile](../profiles/robot-body-runnable.md)** (`v2.1.0`) - PhysX multibody contract after FET003 PhysX `4`.
- **[Robot Body Isaac Profile](../profiles/robot-body-isaac.md)** (`v1.1.0`, `v1.2.0`) - PhysX multibody contract for Isaac robot workflows; also the dependency of `FET_101_ISAAC@0.1.0` robot composition at `v1.2.0`.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.2.0`) - PhysX multibody contract under the standalone-transformer Isaac composition path.
- **[Robotics Prop Profile](../profiles/profiles.md)** (`v3.0.0`) - Optional PhysX multibody feature.
- **[Robot Body Profile](../profiles/profiles.md)** (`v3.0.0`) - Optional PhysX multibody feature.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics PhysX](FET_003_PHYSX.md#version-040) (`FET_003_PHYSX@0.4.0`) |

#### Changes From Version 0.3.0

Version 0.4.0 replaces the dependency-on-Standard shape with an explicit PhysX
multibody requirement list:

| Change | Requirements |
|--------|--------------|
| Added | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004`, `RB.MB.001`, `RB.011`, `RB.012` |
| Removed | Direct `PHYSX.COL.001`, `PHYSX.COL.002`; collider conformance is provided by `FET_003_PHYSX@0.4.0` |

</details>

## Pipelines

Source file type:

- `.usd`
  - Via CIP conversion from Standard multibody assets.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET_004_PHYSX` manifest.
- SimReady Benchmark FET004 Multibody - verifies jointed multibody behavior in a PhysX scene.

## Samples

- `sample_content/common_assets/props_general/obs_workbench_tool_a01/simready_usd/sm_obs_workbench_tool_a01_01.usda` - select the `PhysX` variant.
- `sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd` - multibody prop (5 rigid bodies, 4 revolute joints); select the `PhysX` variant.
- `sample_content/common_assets/props_general/obs_joystick_a01/simready_usd/sm_obs_joystick_a01_01.usd` - select the `PhysX` variant.
- `sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usda` - select the `PhysX` variant.

## Benchmarks

- Suite: [FET004 Multibody](../guides/benchmark/tests/fet004-multibody.md)
  - Tests:
    - [joint_movement](../guides/benchmark/tests/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_004_STANDARD@0.1.0` | `FET_004_PHYSX@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_physx` | Done | Sets PhysX SDF collider approximation on existing collider prims. |
