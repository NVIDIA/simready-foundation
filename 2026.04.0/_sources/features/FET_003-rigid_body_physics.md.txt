# Feature: `ID:003 - RBD Physics - Base`

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET003_BASE_NEUTRAL`|

## Description
Support for rigid body dynamics (RBD). This feature enables simulation of physically accurate motion and collisions for props and dynamic assets. It is suitable for testing, validation, or reference applications where basic physical interactions are required.

## Dependency Graph

```{mermaid}
flowchart LR
    FET003N["FET003_BASE_NEUTRAL\n0.1.0"]
    FET003P["FET003_BASE_PHYSX\n0.1.0"]
    FET004N["FET004_BASE_NEUTRAL\n0.1.0"]
    FET004P["FET004_BASE_PHYSX\n0.1.0"]
    FET100["FET100_BASE_ISAACSIM\n0.1.0"]

    FET003P --> FET003N
    FET004N --> FET003N
    FET004P --> FET003P
    FET100 --> FET003P

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET003N,FET003P current
    class FET004N,FET004P,FET100 other
```

## Use Cases

Products that consume this feature:

- IsaacSim
- MEGA
- Lightwheel SOW1

## Neutral Format
### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Neutral Profile](../profiles/prop-robotics-neutral.md)** (v0.1.0) - Used as the core physics feature for basic rigid body dynamics

#### Requirements

* Capability: [Physics_Bodies/Physics_Rigid_Bodies](../capabilities/physics_bodies/physics_rigid_bodies/capability-physics_rigid_bodies.md)
  * Requirements:
    * [Collider-Capability](../capabilities/physics_bodies/physics_rigid_bodies/requirements/collider-capability.md)
      * RB.COL.001 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Collider-Non-Uniform-Scale](../capabilities/physics_bodies/physics_rigid_bodies/requirements/collider-non-uniform-scale.md)
      * RB.COL.004 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Rigid-Body-Capability](../capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-capability.md)
      * RB.001 | Version 0.1.0
    * [Rigid-Body-Mass](../capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass.md)
      * RB.007 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Rigid-Body-No-Instancing](../capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-instancing.md)
      * RB.005 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Rigid-Body-No-Nesting](../capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-nesting.md)
      * RB.006 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Rigid-Body-Schema-Application](../capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-schema-application.md)
      * RB.003 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Rigid-Body-Schema-No-Skew-Matrix](../capabilities/physics_bodies/physics_rigid_bodies/requirements/rigid-body-schema-no-skew-matrix.md)
      * RB.009 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Collider-Mesh](../capabilities/physics_bodies/physics_rigid_bodies/requirements/collider-mesh.md)
      * RB.COL.003 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Mesh-Collision-API](../capabilities/physics_bodies/physics_rigid_bodies/requirements/mesh-collision-api.md)
      * RB.COL.002 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
    * [Invisible-Collision-Mesh-Has-Purpose](../capabilities/physics_bodies/physics_rigid_bodies/requirements/invisible-collision-mesh-has-purpose-guide.md)
      * RB.010 | Version 0.1.0
      * [Rule | Implementation](../capabilities/physics_bodies/physics_rigid_bodies/validation.py)
* Capability: [Core/Atomic_Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)
  * Requirements
    * [Anchored-Asset-Paths](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md)
      * AA.001 | Version 0.1.0
      * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
    * [Supported-File-Type](../capabilities/core/atomic_asset/requirements/supported-file-types.md)
      * AA.002 | Version 0.1.0
      * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)
* Capability: [Core/Units](../capabilities/core/units/requirements.md)
  * Requirements
    * [Kilograms-Per-Unit](../capabilities/core/units/requirements/kilograms-per-unit.md)
      * UN.003 | Version 0.1.0
      * [Rule | Implementation](../capabilities/core/units/validation.py)
    * [Meters-Per-Unit](../capabilities/core/units/requirements/meters-per-unit.md)
      * UN.002 | Version 0.1.0
      * [Rule | Implementation](../capabilities/core/units/validation.py)
    * [Timecodes-Per-Second](../capabilities/core/units/requirements/timecodes-per-second.md)
      * UN.005 | Version 0.1.0
      * [Rule | Implementation](../capabilities/core/units/validation.py)
    * [Upaxis](../capabilities/core/units/requirements/upaxis.md)
      * UN.001 | Version 0.1.0
      * [Rule | Implementation](../capabilities/core/units/validation.py)

* Capability: [Visualization/Geometry](../capabilities/visualization/geometry/capability-geometry.md)
  * Requirements
    * [At-Least-One-Imageable-Geometry](../capabilities/visualization/geometry/requirements/at-least-one-imageable-geometry.md)
      * VG.001 | Version 0.1.0
      * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)
    * ***Proposed*** [UsdGeom-Mesh-Triangulation](../capabilities/visualization/geometry/requirements/usdgeom-mesh-triangulation.md)
      * VG.021 | Version 0.1.0
      * Description
        * Error should be thrown if mesh is NOT triangles.  This has a can throw off automatic convex-hull generation if mesh is composed of NGONS.
    * [UsdGeom-Mesh-Manifold](../capabilities/visualization/geometry/requirements/usdgeom-mesh-manifold.md)
      * VG.007 | Version 0.1.0
      * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

* Capability: [Visualization/Materials](../capabilities/visualization/materials/capability-materials.md)
  * Requirements
    * [Material-Bind-Scope](../capabilities/visualization/materials/requirements/material-bind-scope.md)
      * VM.BIND.001 | Version 0.1.0
    * [Material-Preview-Surface](../capabilities/visualization/materials/requirements/material-preview-surface.md)
      * VM.PS.001 | Version 0.1.0

#### Pipelines Supported for this Feature
Source file type:
* .blend
  * Via Blender SimReady Add-ons
* .mjcf
  * Via Blender SimReady Add-ons + MJCF2USD Tool
* .step
  * Via Blender SimReady Add-ons + CAD Converter

#### Unibody | Rigidbody Samples
* [simready_usd/sm_obs_small_sledge_hammer_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_small_sledge_hammer_a01/simready_usd/sm_obs_small_sledge_hammer_a01_01.usd)
* [simready_usd/sm_alcohol_a01_01.usd](../../../../sample_content/common_assets/props_general/alcohol_a01/simready_usd/sm_alcohol_a01_01.usd)
* [simready_usd/sm_apple_a01_01.usd](../../../../sample_content/common_assets/props_general/apple_a01/simready_usd/sm_apple_a01_01.usd)
* [simready_usd/sm_obs_orange_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_orange_a01/simready_usd/sm_obs_orange_a01_01.usd)
* [simready_usd/sm_coffee_cup_grasp_a01_01.usd](../../../../sample_content/common_assets/props_general/coffee_cup_grasp_a01/simready_usd/sm_coffee_cup_grasp_a01_01.usd)


#### Test Process

None

</details>


## NVIDIA Physx Format
### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET003_BASE_PHYSX`|
| Proprietary Techs       | `Physx`           |

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Physx Profile](../profiles/prop-robotics-physx.md)** (v0.1.0) - Used as the core physics feature with advanced PhysX rigid body dynamics

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [ID:003 - RBD Physics - Base - Neutral Format - v0.1.0](../features/FET_003-rigid_body_physics.md#version-010) |

* Capability: [Physics-Bodies/Physics-Rigid-Bodies](../capabilities/physics_bodies/physics_rigid_bodies/capability-physics_rigid_bodies.md)
  * Requirements:
    * [PhysX-Collider-Capability](../capabilities/physics_bodies/physics_rigid_bodies/requirements/physx-collider-capability.md)
      * PHYSX.COL.001 | Version 0.1.0


#### Pipelines Supported for this Feature

None; Neutral Format is acceptable.

#### Unibody | Rigidbody Samples
* [simready_physx_usd/sm_obs_small_sledge_hammer_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_small_sledge_hammer_a01/simready_physx_usd/sm_obs_small_sledge_hammer_a01_01.usd)
* [simready_physx_usd/sm_alcohol_a01_01.usd](../../../../sample_content/common_assets/props_general/alcohol_a01/simready_physx_usd/sm_alcohol_a01_01.usd)
* [simready_physx_usd/sm_apple_a01_01.usd](../../../../sample_content/common_assets/props_general/apple_a01/simready_physx_usd/sm_apple_a01_01.usd)
* [simready_physx_usd/sm_obs_orange_a01_01.usd](../../../../sample_content/common_assets/props_general/obs_orange_a01/simready_physx_usd/sm_obs_orange_a01_01.usd)
* [simready_physx_usd/sm_coffee_cup_grasp_a01_01.usd](../../../../sample_content/common_assets/props_general/coffee_cup_grasp_a01/simready_physx_usd/sm_coffee_cup_grasp_a01_01.usd)

#### Test Process

* Obtain Isaac Sim 5 (release build)
* Launch Isaacsim.bat
  * Launch isaacsim.bat
  * In Isaac Sim, open this usd: [test stage](../../../testing_tools/testing_data/runtime_physics_tests.usda)
    * Can be manually located here: ```nv_core/testing_tools/testing_data/runtime_physics_tests.usda```
* Activate correct prim (right click + activate)
  * Drop_On_Ground_Plane
  * Drop_On_Tilted_Plane
* Click on empty xform
  * ```/World/Drop_On_Tilted_Plane/StartPoint```
* Right click, add reference to (path), select Sample above.
  * ```sample_content/common_assets/props_general/obs_small_sledge_hammer_a01/simready_physx_usd/sm_obs_small_sledge_hammer_a01_01.usd```
* Hit play button in UI.
    * Press play to start sim
* Expected result:
  * Item should fall down and stop and settle after 5 seconds.
  * Video Examples:
    * [Drop test results video link](../_static/videos/drop_test.mp4)
    * [Slope test results video link](../_static/videos/slope_test.mp4)

</details>