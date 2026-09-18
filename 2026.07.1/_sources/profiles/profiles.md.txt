# Asset Profiles

Asset profiles bundle capabilities, so that assets can be reasoned about and validated for conformance with lists of capability requirements. Asset profiles can serve as a contract between creators and consumers of assets.

Feature requirements and dependency chains are defined in the [feature dependency graph](../features/feature-dependency-graph). Profile feature sets below align with the profile TOML files under `profiles/` and those specifications.

This section lists the profiles from every SimReady Foundation [tier](../guides/tiers.md) together. The tier that owns a profile indicates how broadly it applies: core-tier profiles are the most portable, while a profile owned by another tier is scoped to that tier's runtime, vendor, or domain.

(profile-comparison)=
## Profile comparison

| Profile | Versions | Summary | Feature set (from profile TOML) |
| --- | --- | --- | --- |
| Prop-Robotics-Neutral | 1.0.0, 2.0.0, 2.0.1, 2.1.0, 2.2.0 | Neutral format props for robotics | FET_000_STANDARD, FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_005_STANDARD, FET_006_MDL, FET_000_PHYSX, FET_000_NEWTON, FET_000_MUJOCO |
| Prop-Robotics-Physx | 1.0.0, 2.0.0, 2.0.1, 2.1.0, 2.2.0 | PhysX props for robotics | FET_000_STANDARD, FET_001_STANDARD, FET_003_PHYSX, FET_004_PHYSX, FET_005_STANDARD, FET_006_MDL, FET_000_PHYSX, FET_000_NEWTON, FET_000_MUJOCO |
| Prop-Robotics-Isaac | 1.0.0, 1.0.1, 1.1.0, 1.2.0 | Isaac Sim composition + PhysX props | FET_001_STANDARD, FET_003_PHYSX, FET_004_PHYSX, FET_005_STANDARD, FET_100_ISAAC |
| Robotics-Prop | 3.0.0, 3.1.0, 3.2.0 | Consolidated prop profile using Standard feature IDs; 3.2.0 adds required SimReady packaging + provenance metadata | FET_000_STANDARD, FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_005_STANDARD, FET_006_STANDARD, FET_006_MDL, FET_007_STANDARD, FET_031_STANDARD, FET_033_STANDARD, FET_000_PHYSX, FET_003_PHYSX, FET_004_PHYSX, FET_000_NEWTON, FET_003_NEWTON, FET_004_NEWTON, FET_000_MUJOCO, FET_003_MUJOCO, FET_004_MUJOCO |
| Robot-Body-Neutral | 1.0.0 | Neutral robot body physics | FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_022_STANDARD, FET_024_STANDARD |
| Robot-Body-Runnable | 1.0.0, 1.1.0 | PhysX robot body, runnable core | FET_001_STANDARD, FET_004_ROBOT_PHYSX, FET_021_ISAAC, FET_022_PHYSX, FET_024_PHYSX |
| Robot-Body-Isaac | 1.0.0, 1.1.0, 1.2.0 | Isaac robot core + PhysX | FET_001_STANDARD, FET_004_ROBOT_PHYSX or FET_003_PHYSX and FET_004_PHYSX, FET_021_ISAAC, FET_022_ISAAC, FET_024_PHYSX, FET_100_ISAAC (v1.0.0-v1.1.0) or FET_101_ISAAC (v1.2.0) |
| Robot-Body | 2.0.0, 2.1.0, 2.2.0 | Consolidated robot body profile; 2.1.0 adds required SimReady packaging + provenance metadata; 2.2.0 adds optional Isaac ROS-Ready bridge wiring | FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_022_STANDARD, FET_024_STANDARD, FET_025_ROS, FET_031_STANDARD, FET_033_STANDARD, FET_004_PHYSX, FET_022_PHYSX, FET_024_PHYSX, FET_000_ISAAC, FET_021_ISAAC, FET_022_ISAAC, FET_023_ISAAC, FET_100_ISAAC |
| Robot-Gripper-Neutral | 0.1.0, 0.2.0 | Neutral gripper end-effector with grasp site | FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_022_STANDARD, FET_024_STANDARD, FET_028_STANDARD |
| Robot-Gripper-Isaac | 0.1.0, 0.2.0 | Isaac gripper end-effector with grasp site | FET_001_STANDARD, FET_004_ROBOT_PHYSX or FET_004_PHYSX, FET_021_ISAAC, FET_022_ISAAC, FET_024_PHYSX, FET_028_ISAAC, FET_100_ISAAC |
| Robot-Gripper | 2.0.0, 2.1.0 | Consolidated gripper profile using Standard feature IDs; 2.1.0 adds required SimReady packaging + provenance metadata | FET_001_STANDARD, FET_003_STANDARD, FET_004_STANDARD, FET_022_STANDARD, FET_024_STANDARD, FET_028_STANDARD, FET_031_STANDARD, FET_033_STANDARD, FET_004_PHYSX, FET_022_PHYSX, FET_024_PHYSX, FET_021_ISAAC, FET_022_ISAAC, FET_028_ISAAC, FET_100_ISAAC |
| Package | 1.0.0 | Created package with a bill of materials | FET_030_STANDARD, FET_032_STANDARD |
| Package-NoBOM | 1.0.0 | Created package published without a BOM | FET_030_STANDARD |
| Package-Candidate | 1.0.0, 1.1.0, 1.2.0 | Source folder preflight before packaging; 1.2.0 adopts FET_033_STANDARD@0.3.0 (stricter SR.003 provenance) | FET_031_STANDARD, FET_033_STANDARD |

The packaging profiles validate a package folder and its sidecar JSON files
rather than the contents of a USD stage.

```{toctree}
:maxdepth: 1

Prop Robotics Neutral <prop-robotics-neutral>
Prop Robotics Physx <prop-robotics-physx>
Prop Robotics Isaac <prop-robotics-isaac>
Robotics Prop <robotics-prop>
Robot Body Neutral <robot-body-neutral>
Robot Body Runnable <robot-body-runnable>
Robot Body Isaac <robot-body-isaac>
Robot Body <robot-body>
Robot Gripper Neutral <robot-gripper-neutral>
Robot Gripper Isaac <robot-gripper-isaac>
Open Taxonomy COCO <open-taxonomy-coco>
Open Taxonomy Cityscapes <open-taxonomy-cityscapes>
Open Taxonomy ADE20K <open-taxonomy-ade20k>
Open Taxonomy PASCAL VOC <open-taxonomy-pascal_voc>
Open Taxonomy SUN RGB-D <open-taxonomy-sunrgbd>
Open Taxonomy ImageNet-1K <open-taxonomy-imagenet_1k>
```
