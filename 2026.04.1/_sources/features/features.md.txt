# Features

## Status Dashboard

<div class="full-width">

| Name | Status | Profile | Tier | Ver. | S | V | T | ID |
|---|---|---|---|---|---|---|---|---|
| [Core](FET_000-base_neutral-0.1.0-core.md) | {bdg-success}`Done` | <details><summary>1</summary>[Prop-Neutral](../profiles/prop-robotics-neutral.md)</details> | SRF.CORE | 0.1.0 | ✓ | ✓ | - | FET000_CORE |
| [Minimal](FET_001-minimal.md) | {bdg-success}`Done` | <details><summary>6</summary>[Prop-Neutral](../profiles/prop-robotics-neutral.md), [Prop-Physx](../profiles/prop-robotics-physx.md), [Prop-Isaac](../profiles/prop-robotics-isaac.md), [Robot-Neutral](../profiles/robot-body-neutral.md), [Robot-Runnable](../profiles/robot-body-runnable.md), [Robot-Isaac](../profiles/robot-body-isaac.md)</details> | OAV.CORE | <details><summary>latest - 1.0.0</summary>[> older: 0.1.0](FET_001-minimal.md#version-010)</details> | ✓ | ✓ | ✓ | FET001_BASE_NEUTRAL |
| [Posable Bodies](FET_002-posable_bodies.md) | {bdg-success}`Done` | - | - | 0.1.0 | ✓ | ✓ | ✓ | FET002_BASE_NEUTRAL |
| [Rigid Body Physics](FET_003-rigid_body_physics.md) | {bdg-success}`Done` | <details><summary>2</summary>[Prop-Neutral](../profiles/prop-robotics-neutral.md), [Robot-Neutral](../profiles/robot-body-neutral.md)</details> | SRF.CORE | 0.1.0 | ✓ | ✓ | ✓ | FET003_BASE_NEUTRAL |
| &emsp;&emsp;↳ Runnable | {bdg-success}`Done` | <details><summary>2</summary>[Prop-Physx](../profiles/prop-robotics-physx.md), [Prop-Isaac](../profiles/prop-robotics-isaac.md)</details> | SRF.PHYSX | <details><summary>latest - 0.2.0</summary>[> older: 0.1.0](FET_003-rigid_body_physics.md#version-010-1)</details> | ✓ | ✓ | ✓ | FET003_BASE_PHYSX |
| [Multi-Body Physics](FET_004-simulate_multi_body_physics.md) | {bdg-success}`Done` | <details><summary>2</summary>[Prop-Neutral](../profiles/prop-robotics-neutral.md), [Robot-Neutral](../profiles/robot-body-neutral.md)</details> | SRF.CORE | 0.1.0 | ✓ | ✓ | ✓ | FET004_BASE_NEUTRAL |
| &emsp;&emsp;↳ Runnable (PhysX) | {bdg-success}`Done` | <details><summary>2</summary>[Prop-Physx](../profiles/prop-robotics-physx.md), [Prop-Isaac](../profiles/prop-robotics-isaac.md)</details> | SRF.PHYSX | <details><summary>latest - 0.2.0</summary>[> older: 0.1.0](FET_004-simulate_multi_body_physics.md#version-010-1)</details> | ✓ | ✓ | ✓ | FET004_BASE_PHYSX |
| &emsp;&emsp;↳ Runnable (Robot) | {bdg-success}`Done` | <details><summary>2</summary>[Robot-Runnable](../profiles/robot-body-runnable.md), [Robot-Isaac](../profiles/robot-body-isaac.md)</details> | ROBOT.PHYSX | <details><summary>latest - 0.2.0</summary>> older: 0.1.0</details> | ✓ | ✓ | ✓ | FET004_ROBOT_PHYSX |
| [Grasp Physics](FET_005-simulate_grasp_physics.md) | {bdg-success}`Done` | <details><summary>3</summary>[Prop-Neutral](../profiles/prop-robotics-neutral.md), [Prop-Physx](../profiles/prop-robotics-physx.md), [Prop-Isaac](../profiles/prop-robotics-isaac.md)</details> | SRF.CORE | 0.1.0 | ✓ | ✓ | ✓ | FET005_BASE_NEUTRAL |
| [Materials - MDL](FET_006-materials.md) | {bdg-warning}`Stalled` | <details><summary>2</summary>[Prop-Neutral](../profiles/prop-robotics-neutral.md), [Prop-Physx](../profiles/prop-robotics-physx.md)</details> | SRF.CORE | 0.1.0 | ✓ | ✓ | ✓ | FET006_BASE_MDL |
| [Materials - USDPreview](FET_006-materials.md) | {bdg-warning}`Stalled` | - | SRF.CORE | 0.1.0 | ✓ | ✓ | ✓ | FET006_BASE_USDPREVIEW |
| &emsp;&emsp;↳ Runnable (Isaac) | {bdg-warning}`Stalled` | - | ISAAC | 0.1.0 | ✓ | ✓ | ✓ | FET006_BASE_ISAACSIM |
| [Non-Visual Materials](FET_007-nonvisual_materials.md) | {bdg-warning}`Stalled` | - | SRF.CORE | 0.2.0 | ✓ | ✓ | ✓ | FET007_BASE_NEUTRAL |
| [Semantic Labels](FET_011-semantic_labels.md) | {bdg-warning}`Stalled` | - | - | 0.2.0 | ✓ | - | - | FET011_BASE_NEUTRAL |
| [Robot Core](FET_021-robot_core.md) | {bdg-success}`Done` | <details><summary>1</summary>[Robot-Isaac](../profiles/robot-body-isaac.md)</details> | ISAAC | <details><summary>latest - 0.2.0</summary>[> older: 0.1.0](FET_021-robot_core.md#version-010)</details> | ✓ | ✓ | ✓ | FET021_ROBOT_CORE_ISAAC |
| &emsp;&emsp;↳ Runnable | {bdg-success}`Done` | <details><summary>1</summary>[Robot-Runnable](../profiles/robot-body-runnable.md)</details> | ISAAC | 0.2.0 | ✓ | ✓ | ✓ | FET021_ROBOT_CORE_RUNNABLE |
| [Driven Joints](FET_022-driven_joints.md) | {bdg-success}`Done` | <details><summary>1</summary>[Robot-Neutral](../profiles/robot-body-neutral.md)</details> | - | 0.1.0 | ✓ | ✓ | ✓ | FET022_DRIVEN_JOINTS_NEUTRAL |
| &emsp;&emsp;↳ Runnable (PhysX) | {bdg-success}`Done` | <details><summary>1</summary>[Robot-Runnable](../profiles/robot-body-runnable.md)</details> | PHYSX | 0.1.0 | ✓ | ✓ | ✓ | FET022_DRIVEN_JOINTS_PHYSX |
| &emsp;&emsp;↳ Runnable (Isaac) | {bdg-success}`Done` | <details><summary>1</summary>[Robot-Isaac](../profiles/robot-body-isaac.md)</details> | ISAAC | 0.1.0 | ✓ | ✓ | ✓ | FET022_DRIVEN_JOINTS_ISAAC |
| [Robot Materials](FET_023-robot_materials.md) | {bdg-success}`Done` | - | ISAAC | 0.1.0 | - | - | - | FET023_ROBOT_MATERIALS |
| [Base Articulation](FET_024-base_articulation.md) | {bdg-success}`Done` | <details><summary>1</summary>[Robot-Neutral](../profiles/robot-body-neutral.md)</details> | - | 0.1.0 | - | - | - | FET024_BASE_ARTICULATION_NEUTRAL |
| &emsp;&emsp;↳ Runnable (PhysX) | {bdg-success}`Done` | <details><summary>2</summary>[Robot-Runnable](../profiles/robot-body-runnable.md), [Robot-Isaac](../profiles/robot-body-isaac.md)</details> | PHYSX | 0.1.0 | - | - | - | FET024_BASE_ARTICULATION_PHYSX |
| [IsaacSim Composition](FET_100-isaacsim-0.1.0-composition.md) | {bdg-success}`Done` | <details><summary>2</summary>[Prop-Isaac](../profiles/prop-robotics-isaac.md), [Robot-Isaac](../profiles/robot-body-isaac.md)</details> | ISAAC | 0.1.0 | - | - | - | FET100_BASE_ISAACSIM |
| [Packaging Core](FET_030-packaging_core.md) | {bdg-success}`Done` | <details><summary>1</summary>Package</details> | PKG.CORE | 0.1.0 | ✓ | ✓ | - | FET030_PACKAGING_CORE |
| [Self-contained Package Source](FET_031-package_self_contained.md) | {bdg-success}`Done` | <details><summary>1</summary>Package-Candidate</details> | PKG.CORE | 0.1.0 | ✓ | ✓ | - | FET031_PACKAGE_SELF_CONTAINED |
| [Packaging Introspection](FET_032-packaging_introspection.md) | {bdg-success}`Done` | - | PKG.CORE | 0.1.0 | - | ✓ | - | FET032_PACKAGING_INTROSPECTION |
| [SimReady Packaging](FET_033-simready_packaging.md) | {bdg-success}`Done` | <details><summary>1</summary>Package-Candidate</details> | PKG.CORE | 0.1.0 | - | ✓ | - | FET033_SIMREADY_PACKAGING |

</div>

**Legend:** S = Samples, V = Validation, T = Testing | ✓ = ready, - = not available | Profile: click count to expand links | Ver.: shows latest; expand for older

```{toctree}
:maxdepth: 1
:hidden:

Feature dependency graph <feature-dependency-graph>
ID:000 - Core - Base <FET_000-base_neutral-0.1.0-core>
ID:001 - Minimal - Base <FET_001-minimal>
ID:002 - Posable Bodies - Base <FET_002-posable_bodies>
ID:003 - RBD Physics - Base <FET_003-rigid_body_physics>
ID:004 - Simulate Multi-Body Physics - Base <FET_004-simulate_multi_body_physics>
ID:005 - Simulate Grasp Physics - Base <FET_005-simulate_grasp_physics>
ID:006 - Materials - Base <FET_006-materials>
ID:007 - Non-Visual Materials - Base <FET_007-nonvisual_materials>
ID:011 - Semantic Labels - Base <FET_011-semantic_labels>
ID:100 - IsaacSim Composition <FET_100-isaacsim-0.1.0-composition>
ID:021 - Core Robot <FET_021-robot_core>
ID:022 - Driven Joints <FET_022-driven_joints>
ID:023 - Robot Materials - Isaac Sim <FET_023-robot_materials>
ID:024 - Base Articulation <FET_024-base_articulation>
ID:030 - Packaging Core <FET_030-packaging_core>
ID:031 - Package Self Contained <FET_031-package_self_contained>
ID:032 - Packaging Introspection <FET_032-packaging_introspection>
ID:033 - SimReady Packaging <FET_033-simready_packaging>
```
