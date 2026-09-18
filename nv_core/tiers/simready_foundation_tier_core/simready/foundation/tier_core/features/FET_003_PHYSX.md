# Feature: `FET_003_PHYSX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_003_PHYSX` |
| Runtime                 | `PHYSX` |
| Proprietary Techs       | `PhysX` |
| Latest Version          | `0.4.0` |

## Description

The PhysX Rigid Body Physics feature defines the PhysX runtime contract for
assets that can be simulated as dynamic rigid bodies with PhysX-compatible
colliders.

An asset that satisfies this feature carries the rigid-body requirements needed
for stable dynamics and the PhysX collider rules that allow valid PhysX mesh
collision, including merged mesh collider patterns that the Standard OpenUSD
rules do not allow.

## Dependency Graph

Version 0.1.0 depends on `FET_003_STANDARD@0.1.0`. Versions 2 through 4 carry explicit
runtime-specific requirement lists so PhysX collider requirements can replace
the Standard collider placement rules.

```{mermaid}
flowchart LR
    FET003S1["FET_003_STANDARD\n0.1.0"]
    FET003P1["FET_003_PHYSX\n0.1.0"]
    FET003P4["FET_003_PHYSX\n0.4.0"]
    FET004P["FET_004_PHYSX\n0.4.0"]
    FET100["FET_100_ISAAC\n0.1.0, 2, 3, 4"]

    FET003P1 --> FET003S1
    FET004P --> FET003P4
    FET100 --> FET003P4

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET003P1,FET003P4 current
    class FET003S1,FET004P,FET100 other
```

## Use Cases

- PhysX rigid-body simulation for props and robot bodies.
- Isaac Sim and PhysX runtime tests that require collider behavior beyond the
  Standard OpenUSD collider placement rules.
- Physics benchmark runs that drop, collide, settle, and slide assets in a
  PhysX scene.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics PhysX Profile](../profiles/prop-robotics-physx.md)** (`v1.0.0`, `v2.0.0`, `v2.0.1`) - Provides the original PhysX rigid-body gate for prop assets.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.0.0`, `v1.0.1`) - Provides the original PhysX rigid-body gate under Isaac composition.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics Standard](FET_003_STANDARD.md#version-010) (`FET_003_STANDARD@0.1.0`) |

#### Requirement List

* Capability: [Physics Bodies/Colliders](../capabilities/physics_bodies/physics_colliders/requirements.md)
    * Requirements:
        * [Collider-Approximation-SDF](../capabilities/physics_bodies/physics_colliders/requirements/collider-approximation-sdf.md)
            * `COL.001` | Version `0.1.0`

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Robot Body Runnable Profile](../profiles/robot-body-runnable.md)** (`v2.0.0`) - Provides the explicit PhysX rigid-body gate for runnable robot bodies.

#### Feature Dependencies

None.

#### Changes From Version 0.1.0

Version 0.2.0 replaces the Version 0.1.0 dependency-plus-`COL.001` contract with an
explicit PhysX rigid-body requirement list:

| Change | Requirement | Reason |
|--------|-------------|--------|
| Removed | `FET_003_STANDARD@0.1.0` dependency | The PhysX variant now carries the full list so runtime-specific collider rules can replace Standard collider rules. |
| Removed | `COL.001` | Replaced by PhysX collider requirements. |
| Added | `RB.COL.003` | Keeps collider mesh validation. |
| Added | `RB.COL.004` | Keeps collider scale validation. |
| Added | `RB.001` | Requires at least one rigid body. |
| Added | `RB.003` | Requires valid rigid-body API placement. |
| Added | `RB.005` | Rejects invalid rigid-body instancing. |
| Added | `RB.006` | Keeps the original nested rigid-body check for this version. |
| Added | `RB.007` | Requires mass authoring. |
| Added | `RB.009` | Rejects skewed rigid-body transforms. |
| Added | `RB.010` | Requires collision-only invisible meshes to use guide purpose. |
| Added | `PHYSX.COL.001` | Allows Gprim colliders and valid PhysX mesh-merge Xform colliders. |
| Added | `PHYSX.COL.002` | Allows mesh collision on meshes or valid PhysX mesh-merge prims. |

</details>

### Version 0.3.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics PhysX Profile](../profiles/prop-robotics-physx.md)** (`v2.1.0`) - Uses the PhysX rigid-body contract after `RB.006` was removed.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.1.0`) - Uses the PhysX rigid-body contract after `RB.006` was removed.

#### Feature Dependencies

None.

#### Changes From Version 0.2.0

Version 0.3.0 keeps all Version 0.2.0 requirements except:

| Change | Requirement | Reason |
|--------|-------------|--------|
| Removed | `RB.006` | Nested rigid-body behavior moved toward multibody and robot-specific validation instead of the base rigid-body gate. |

</details>

### Version 0.4.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Robot Body Runnable Profile](../profiles/robot-body-runnable.md)** (`v2.1.0`) - Uses the latest PhysX rigid-body gate before PhysX multibody validation.
- **[Robot Body Isaac Profile](../profiles/robot-body-isaac.md)** (`v1.1.0`) - Uses the latest PhysX rigid-body gate before Isaac robot composition.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.2.0`) - Uses the latest PhysX rigid-body gate under the standalone-transformer Isaac composition path.
- **[Robot Body Profile](../profiles/profiles.md)** (`v3.0.0`) - Used through optional `FET_004_PHYSX@0.4.0` and Isaac composition dependencies.

#### Feature Dependencies

None.

#### Changes From Version 0.3.0

Version 0.4.0 keeps the Version 0.3.0 requirement list and clarifies that this is the
latest unibody PhysX rigid-body contract. Multibody joint and articulation work
belongs to FET004 runtime variants.

</details>

## Pipelines

Source file type:

- `.blend`
  - Via Blender SimReady Add-ons
- `.mjcf`
  - Via Blender SimReady Add-ons and MJCF2USD Tool
- `.step`
  - Via Blender SimReady Add-ons and CAD Converter

Validation or runtime pipeline:

- SimReady validation - verifies the PhysX Rigid Body Physics requirement IDs
  listed in the selected `FET_003_PHYSX` manifest.
- SimReady Benchmark FET003 Physics - verifies rigid-body drop, collision, and
  settling behavior in a PhysX runtime scene.

## Samples

- `sample_content/common_assets/props_general/obs_small_sledge_hammer_a01/simready_usd/sm_obs_small_sledge_hammer_a01_01.usd`
- `sample_content/common_assets/props_general/alcohol_a01/simready_usd/sm_alcohol_a01_01.usd`
- `sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd`
- `sample_content/common_assets/props_general/obs_orange_a01/simready_usd/sm_obs_orange_a01_01.usd`
- `sample_content/common_assets/props_general/coffee_cup_grasp_a01/simready_usd/sm_coffee_cup_grasp_a01_01.usd`

## Benchmarks

- Suite: [FET003 Physics](../guides/benchmark/tests/fet003-physics.md)
  - Tests:
    - [ground_drop](../guides/benchmark/tests/fet003/ground-drop.md)
    - [slope_drop](../guides/benchmark/tests/fet003/slope-drop.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET_003_STANDARD@0.1.0` | `FET_003_PHYSX@0.1.0` | `nv_core/cip_specs/asset_handler_modules/neutral_to_physx` | Done | Computes mesh extents for the original prop PhysX rigid-body path. |
