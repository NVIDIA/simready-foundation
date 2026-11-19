# Feature: `FET004_Multibody`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET004_Multibody` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

The Standard Multi-Body Physics feature defines the OpenUSD contract for assets
that intentionally contain more than one rigid body connected by joints or
articulation structure.

An asset that satisfies this feature has multiple intended rigid bodies, valid
joint relationships, a valid articulation-root arrangement, and no static or
kinematic articulation-root body violations.

## Dependency Graph

```{mermaid}
flowchart LR
    FET003S1["FET003_RigidBody\n0-1-0"]
    FET003S2["FET003_RigidBody\n0-2-0"]
    FET004S1["FET004_Multibody\n0-1-0"]
    FET004S2["FET004_Multibody\n0-2-0"]
    FET022S["FET022_DrivenJoints\n0-2-0"]

    FET004S1 --> FET003S1
    FET004S2 --> FET003S2
    FET022S --> FET004S2

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET004S1,FET004S2 current
    class FET003S1,FET003S2,FET022S other
```

## Use Cases

- Standard OpenUSD multibody props and robot link structures.
- Baseline multibody validation before runtime-specific PhysX or Newton
  variants.
- Assets with existing rigid-body parts, joints, or articulation intent.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics Standard](FET003_RigidBody.md#version-0-1-0) (`FET003_RigidBody.0-1-0`) |

#### Requirement List

| Capability | Requirements |
|------------|--------------|
| Physics Joints | `JT.001`, `JT.002`, `JT.003`, `JT.ART.002`, `JT.ART.003`, `JT.ART.004` |
| Physics Rigid Bodies | `RB.MB.001` |

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): optional in `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Rigid Body Physics Standard](FET003_RigidBody.md#version-0-2-0) (`FET003_RigidBody.0-2-0`) |

#### Changes From Version 0-1-0

Version 0-2-0 keeps the Version 0-1-0 requirement list and updates the dependency to
`FET003_RigidBody.0-2-0`.

</details>

## Pipelines

Source file type:

- `.blend`
  - Via Blender SimReady Add-ons.
- `.mjcf`
  - Via Blender SimReady Add-ons and MJCF2USD Tool.
- `.step`
  - Via Blender SimReady Add-ons and CAD Converter.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET004_Multibody` manifest.

## Samples

- [sample_content/common_assets/props_general/obs_workbench_tool_a01/simready_usd/sm_obs_workbench_tool_a01_01.usda](../../../../../../../sample_content/common_assets/props_general/obs_workbench_tool_a01/simready_usd/sm_obs_workbench_tool_a01_01.usda)
- [sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd)
- [sample_content/common_assets/props_general/obs_joystick_a01/simready_usd/sm_obs_joystick_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/obs_joystick_a01/simready_usd/sm_obs_joystick_a01_01.usd)
- [sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usda](../../../../../../../sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usda)

## Evaluates

- [FET004 Multibody](../runtime_tests/docs/fet004-multibody.md)
  - [joint_movement](../runtime_tests/docs/fet004/joint-movement.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET004_Multibody.PhysX.0-1-0` | `FET004_Multibody.0-2-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Extracts PhysX joint/body opinions to the PhysX runnable while preserving and validating neutral joint/articulation topology. |
| `FET004_Multibody.0-1-0` | `FET004_Multibody.PhysX.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | Done | Sets PhysX SDF collider approximation on existing collider prims. |
| `FET004_Multibody.0-1-0` | `FET004_Multibody.Newton.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_newton` | Done | Applies Newton mesh-collision schemas (`newton:contactGap`) on existing collider prims. |
| `FET004_Multibody.0-1-0` | `CAP004_Multibody.MuJoCo.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_mujoco` | Done | Applies MuJoCo mesh-collision schemas (`convexHull`) on existing collider prims. |
| `FET004_Multibody.0-2-0` | `FET004_Multibody.PhysX.0-4-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Validates neutral multibody topology and preserved PhysX opinions without inventing joints or drives. |
| `FET004_Multibody.0-2-0` | `FET004_Multibody.Newton.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Validate-only runtime edge; Newton uses the neutral joint/articulation topology. |
| `FET004_Multibody.0-2-0` | `CAP004_Multibody.MuJoCo.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Validate-only runtime edge; MuJoCo uses the neutral joint/articulation topology. |
