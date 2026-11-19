# Feature: `FET003_RigidBody`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET003_RigidBody` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

The Standard Rigid Body Physics feature defines the OpenUSD contract for assets
that can be simulated as dynamic rigid bodies using standard `UsdPhysics`
schemas.

An asset that satisfies this feature has at least one valid rigid body, valid
collider schema placement, valid mesh-collision usage, authored mass, no
invalid rigid-body instancing or transform skew, and collision-only geometry
organized so it can be interpreted by OpenUSD-compatible physics pipelines.

## Dependency Graph

This feature has no JSON feature dependencies. Runtime-specific FET003 variants
such as `FET003_RigidBody.PhysX` and `FET003_RigidBody.Newton` are sibling feature contracts that
carry their own runtime-specific requirement lists.

```{mermaid}
flowchart LR
    FET003S["FET003_RigidBody\n0-1-0, 0-2-0"]
    FET003P["FET003_RigidBody.PhysX\n0-1-0, 0-2-0, 0-3-0, 0-4-0"]
    FET003N["FET003_RigidBody.Newton\n0-1-0"]
    FET004S["FET004_Multibody\n0-2-0"]

    FET004S --> FET003S

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET003S current
    class FET003P,FET003N,FET004S other
```

## Use Cases

- Standard OpenUSD rigid-body simulation for props and robot components.
- Baseline rigid-body validation before multibody, grasp, or robot features.
- Asset conversion workflows that author portable `UsdPhysics` rigid bodies and
  colliders before adding runtime-specific schemas.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Physics Bodies/Rigid Bodies](../rules_and_reqs/physics_bodies/physics_rigid_bodies/capability-physics_rigid_bodies.md)
    * Requirements:
        * [Collider-Capability](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/collider-capability.md)
            * `RB.COL.001` | Version `0.1.0`
        * [Mesh-Collision-API](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/mesh-collision-api.md)
            * `RB.COL.002` | Version `0.1.0`
        * [Collider-Mesh](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/collider-mesh.md)
            * `RB.COL.003` | Version `0.1.0`
        * [Collider-Non-Uniform-Scale](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/collider-non-uniform-scale.md)
            * `RB.COL.004` | Version `0.1.0`
        * [Rigid-Body-Capability](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/rigid-body-capability.md)
            * `RB.001` | Version `0.1.0`
        * [Rigid-Body-Schema-Application](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/rigid-body-schema-application.md)
            * `RB.003` | Version `0.1.0`
        * [Rigid-Body-No-Instancing](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-instancing.md)
            * `RB.005` | Version `0.1.0`
        * [Rigid-Body-No-Nesting](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-nesting.md)
            * `RB.006` | Version `0.1.0`
        * [Rigid-Body-Mass](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass.md)
            * `RB.007` | Version `0.1.0`
        * [Rigid-Body-Schema-No-Skew-Matrix](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/rigid-body-schema-no-skew-matrix.md)
            * `RB.009` | Version `0.1.0`
        * [Invisible-Collision-Mesh-Has-Purpose](../rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/invisible-collision-mesh-has-purpose-guide.md)
            * `RB.010` | Version `0.1.0`

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): required in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): required in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): required in `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`

#### Feature Dependencies

None.

#### Changes From Version 0-1-0

Version 0-2-0 keeps all Version 0-1-0 requirements except:

| Change | Requirement | Reason |
|--------|-------------|--------|
| Removed | `RB.006` | Nested rigid-body behavior moved toward multibody and robot-specific validation instead of the base rigid-body gate. |

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

- SimReady validation - verifies the Standard Rigid Body Physics requirement
  IDs listed in the selected `FET003_RigidBody` manifest.
- SimReady Evaluate FET003 Physics - verifies rigid-body drop, collision, and
  sampled settling behavior through this source contract's explicit Core test
  bindings in a PhysX runtime scene. A separately selected PhysX contract is
  not required for that execution and is not automatically certified by it.

## Samples

- [sample_content/common_assets/props_general/obs_small_sledge_hammer_a01/simready_usd/sm_obs_small_sledge_hammer_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/obs_small_sledge_hammer_a01/simready_usd/sm_obs_small_sledge_hammer_a01_01.usd)
- [sample_content/common_assets/props_general/alcohol_a01/simready_usd/sm_alcohol_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/alcohol_a01/simready_usd/sm_alcohol_a01_01.usd)
- [sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd)
- [sample_content/common_assets/props_general/obs_orange_a01/simready_usd/sm_obs_orange_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/obs_orange_a01/simready_usd/sm_obs_orange_a01_01.usd)
- [sample_content/common_assets/props_general/coffee_cup_grasp_a01/simready_usd/sm_coffee_cup_grasp_a01_01.usd](../../../../../../../sample_content/common_assets/props_general/coffee_cup_grasp_a01/simready_usd/sm_coffee_cup_grasp_a01_01.usd)

## Evaluates

- Suite: [FET003 Physics](../runtime_tests/docs/fet003-physics.md)
  - Tests:
    - [ground_drop](../runtime_tests/docs/fet003/ground-drop.md)
    - [ground_stability](../runtime_tests/docs/fet003/ground-stability.md)
    - [slope_drop](../runtime_tests/docs/fet003/slope-drop.md)

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET003_RigidBody.PhysX.0-1-0` | `FET003_RigidBody.0-2-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Extracts legacy PhysX body/collider schemas and attributes to a dormant PhysX runnable layer, removes runtime opinions from the base, and refuses ambiguous collider topology. |
| `FET003_RigidBody.0-1-0` | `FET003_RigidBody.PhysX.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_physx` | Done | Computes mesh extents for the original prop PhysX rigid-body path. |
| `FET003_RigidBody.0-1-0` | `FET003_RigidBody.Newton.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_newton` | Done | Computes mesh extents and applies Newton mesh-collision schemas (`newton:contactGap`) for the prop Newton rigid-body path. |
| `FET003_RigidBody.0-1-0` | `CAP003_RigidBody.MuJoCo.0-1-0` | `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/neutral_to_mujoco` | Done | Computes mesh extents and applies MuJoCo mesh-collision schemas (`convexHull`) for the prop MuJoCo rigid-body path. |
| `FET003_RigidBody.0-2-0` | `FET003_RigidBody.PhysX.0-4-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Authors the PhysX SDF collider delta in `runnables/physics/physx.usda`. |
| `FET003_RigidBody.0-2-0` | `FET003_RigidBody.Newton.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Authors Newton collider, optional mass, and physics-material deltas in the Newton runnable payload. |
| `FET003_RigidBody.0-2-0` | `CAP003_RigidBody.MuJoCo.0-1-0` | `nv_core/cip_specs/asset_handler_modules/multiphysics_upgrade` | Done | Authors the MuJoCo convex-hull collider delta in the MuJoCo runnable payload. |
